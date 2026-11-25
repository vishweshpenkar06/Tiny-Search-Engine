import hashlib
import hmac
import logging
import re
import shutil
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flask import Flask, Response, g, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from config import Config, load_config
from core.models import SearchOptions
from utils.error_handler import ApiError, api_error, api_success, error_response
from utils.logger import log
from utils.validation import (
    parse_query,
    validate_file_upload,
    validate_pagination,
    validate_threshold,
)

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

ALLOWED_EXTENSIONS = (".txt", ".md", ".html", ".htm", ".csv")
RANKING_MODES = ("tfidf", "bm25")
RETRIEVAL_MODES = ("lexical", "semantic", "hybrid")
SORT_MODES = ("relevance", "filename", "size")
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
PUBLIC_ROUTES = frozenset({"/api/health", "/livez", "/readyz", "/api/readyz"})
FILTER_KEYS = frozenset({"source_type", "file_type"})
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_UPLOAD_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

_HTTP_ERRORS = {
    400: ("bad_request", "Bad request"),
    401: ("unauthorized", "Authentication required"),
    403: ("forbidden", "Forbidden"),
    404: ("not_found", "Not found"),
    405: ("method_not_allowed", "Method not allowed"),
    413: ("payload_too_large", "Request entity too large"),
    415: ("unsupported_media_type", "Unsupported media type"),
}


class _RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.limit = per_minute
        self.window = 60.0
        self.hits: dict[str, tuple[float, int]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            bucket = self.hits.get(key)
            if bucket is None or now - bucket[0] >= self.window:
                self.hits[key] = (now, 1)
                return True
            count = bucket[1] + 1
            self.hits[key] = (bucket[0], count)
            if len(self.hits) > 8192:
                stale = [k for k, v in self.hits.items() if now - v[0] >= self.window]
                for k in stale:
                    self.hits.pop(k, None)
            return count <= self.limit


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _safe_id(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID_RE.fullmatch(value))


def _same_origin(origin: str, allowed: str) -> bool:
    return origin.rstrip("/").lower() == allowed.rstrip("/").lower()


def _authorized(auth: Any, config: Config) -> bool:
    if auth is None or getattr(auth, "type", None) != "basic":
        return False
    username = getattr(auth, "username", "") or ""
    password = getattr(auth, "password", "") or ""
    if not hmac.compare_digest(username, config.admin_username or ""):
        return False
    try:
        return check_password_hash(config.admin_password_hash or "", password)
    except (ValueError, TypeError):
        return False


def _default_service(config: Config):
    from core.index_service import IndexService
    from core.index_store import IndexStore

    store = IndexStore(config)
    store.initialize()
    service = IndexService(config, store)
    service.initialize()
    return service


def _job_to_dict(job: Any) -> dict[str, Any]:
    if is_dataclass(job) and not isinstance(job, type):
        return asdict(job)
    if isinstance(job, dict):
        return dict(job)
    raise ApiError("Invalid job record", 500, "internal_error")


def _page_to_dict(page: Any) -> dict[str, Any]:
    if is_dataclass(page) and not isinstance(page, type):
        return asdict(page)
    if isinstance(page, dict):
        return dict(page)
    raise ApiError("Invalid search result", 500, "internal_error")


def _bounded_int(data: dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(f"{key} must be an integer", 400, "invalid_parameter")
    if not low <= value <= high:
        raise ApiError(f"{key} must be between {low} and {high}", 400, "invalid_parameter")
    return value


def create_app(config: Config | None = None, service=None) -> Flask:
    cfg = config or load_config()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_content_length
    app.config["JSON_SORT_KEYS"] = False
    app.config["TSE_CONFIG"] = cfg
    app.config["TSE_SERVICE"] = service if service is not None else _default_service(cfg)

    if CORS is not None and cfg.public_origin:
        CORS(
            app,
            resources={r"/api/*": {"origins": [cfg.public_origin], "methods": ["GET", "POST", "OPTIONS"]}},
        )

    limiter = _RateLimiter(cfg.rate_limit_per_minute)
    state: dict[str, str | None] = {"last_job_id": None}

    @app.before_request
    def _prepare() -> Response | None:
        g.request_id = uuid.uuid4().hex
        if request.path in PUBLIC_ROUTES:
            return None
        if cfg.auth_enabled:
            if not _authorized(request.authorization, cfg):
                response = api_error("Authentication required", 401, "unauthorized")
                response.headers["WWW-Authenticate"] = 'Basic realm="tiny-search", charset="UTF-8"'
                return response
            if request.method in MUTATING_METHODS:
                origin = request.headers.get("Origin")
                if not cfg.public_origin or not origin or not _same_origin(origin, cfg.public_origin):
                    raise ApiError("Origin not allowed", 403, "forbidden_origin")
        if not limiter.allow(request.remote_addr or "unknown"):
            raise ApiError("Rate limit exceeded", 429, "rate_limited")
        return None

    @app.after_request
    def _finalize(response: Response) -> Response:
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ApiError)
    def _handle_api_error(error: ApiError):
        return error_response(error)

    @app.errorhandler(HTTPException)
    def _handle_http_error(error: HTTPException):
        code, message = _HTTP_ERRORS.get(error.code or 500, ("http_error", str(error.description or "HTTP error")))
        return api_error(message, error.code or 500, code)

    @app.errorhandler(Exception)
    def _handle_unexpected(error: Exception):
        log(
            logging.ERROR,
            "unexpected_error",
            error_type=type(error).__name__,
            request_id=getattr(g, "request_id", None),
        )
        return api_error("Internal server error", 500, "internal_error")

    def json_body() -> dict[str, Any]:
        if not request.is_json:
            raise ApiError("Content-Type must be application/json", 415, "unsupported_media_type")
        data = request.get_json(silent=True)
        if data is None:
            raise ApiError("Malformed JSON body", 400, "invalid_json")
        if not isinstance(data, dict):
            raise ApiError("JSON body must be an object", 400, "invalid_json")
        return data

    def enum_value(data: dict[str, Any], key: str, allowed: tuple[str, ...], default: str) -> str:
        value = data.get(key, default)
        if not isinstance(value, str) or value not in allowed:
            raise ApiError(f"{key} must be one of: {', '.join(allowed)}", 400, "invalid_parameter")
        return value

    def bool_value(data: dict[str, Any], key: str, default: bool) -> bool:
        value = data.get(key, default)
        if not isinstance(value, bool):
            raise ApiError(f"{key} must be a boolean", 400, "invalid_parameter")
        return value

    def query_vector(mode: str, text: str):
        if not cfg.embeddings_enabled or mode not in ("semantic", "hybrid"):
            return None
        from core.embeddings import embed_query

        return embed_query(text)

    @app.route("/api/health", methods=["GET"])
    def health():
        return api_success({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

    @app.route("/livez", methods=["GET"])
    def livez():
        return api_success({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

    @app.route("/readyz", methods=["GET"])
    @app.route("/api/readyz", methods=["GET"])
    def readyz():
        service = app.config["TSE_SERVICE"]
        ready, reason = service.ready()
        snapshot = service.snapshot
        return api_success(
            {
                "status": "ready" if ready else "unready",
                "generation": int(service.generation),
                "document_count": int(snapshot.document_count),
                "reason": reason,
            }
        )

    @app.route("/api/config", methods=["GET"])
    def config_info():
        return api_success(
            {
                "allowed_extensions": list(ALLOWED_EXTENSIONS),
                "max_file_size": cfg.max_file_size,
                "max_files": cfg.max_files,
                "max_query_length": cfg.max_query_length,
                "ranking_modes": list(RANKING_MODES),
                "retrieval_modes": list(RETRIEVAL_MODES),
                "sort_modes": list(SORT_MODES),
                "embeddings_enabled": cfg.embeddings_enabled,
                "crawler_enabled": cfg.crawler_enabled,
                "auth_enabled": cfg.auth_enabled,
            }
        )

    @app.route("/api/upload", methods=["POST"])
    def upload():
        service = app.config["TSE_SERVICE"]
        incoming = [item for item in request.files.getlist("files") if item and item.filename]
        if not incoming:
            raise ApiError("No files provided", 400, "no_files")
        if len(incoming) > cfg.max_files:
            raise ApiError(f"Too many files (maximum {cfg.max_files})", 413, "too_many_files")

        upload_id = str(uuid.uuid4())
        batch_dir = cfg.upload_dir / upload_id
        batch_dir.mkdir(parents=True, exist_ok=False)
        accepted_items: list[dict[str, object]] = []
        rejected: list[str] = []
        try:
            for index, item in enumerate(incoming):
                label = Path(item.filename or "").name[:200] or "unnamed"
                original = secure_filename(label)
                extension = Path(label).suffix.lower()
                blob_digest = uuid.uuid5(_UPLOAD_NAMESPACE, f"{upload_id}:{label}:{index}").hex[:16]
                blob_name = f"{index:04d}_{blob_digest}{extension}"
                partial = batch_dir / f".{blob_name}.part"
                size = 0
                content_hash = hashlib.sha256()
                too_large = False
                with partial.open("wb") as out:
                    while True:
                        chunk = item.stream.read(65536)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > cfg.max_file_size:
                            too_large = True
                            break
                        content_hash.update(chunk)
                        out.write(chunk)
                if too_large:
                    partial.unlink(missing_ok=True)
                    rejected.append(f"{label}: file too large")
                    continue
                valid, reason = validate_file_upload(original, size, cfg)
                if not valid:
                    partial.unlink(missing_ok=True)
                    rejected.append(f"{label}: {reason}")
                    continue
                partial.replace(batch_dir / blob_name)
                accepted_items.append(
                    {
                        "filename": label,
                        "blob_name": blob_name,
                        "byte_size": size,
                        "content_hash": content_hash.hexdigest(),
                    }
                )
            service.register_upload(upload_id, accepted_items)
        except Exception as exc:
            shutil.rmtree(batch_dir, ignore_errors=True)
            log(logging.ERROR, "upload_failed", error_type=type(exc).__name__, request_id=getattr(g, "request_id", None))
            raise ApiError("Upload failed", 500, "upload_failed") from exc

        log(logging.INFO, "upload_complete", file_count=len(accepted_items), rejected_count=len(rejected))
        return api_success(
            {
                "upload_id": upload_id,
                "file_count": len(accepted_items),
                "rejected": rejected,
                "generation": int(service.generation),
            }
        )

    @app.route("/api/index", methods=["POST"])
    def start_index():
        service = app.config["TSE_SERVICE"]
        data = json_body()
        upload_id = data.get("upload_id")
        if not _valid_uuid(upload_id):
            raise ApiError("upload_id must be a UUID", 400, "invalid_upload_id")
        ranking = enum_value(data, "ranking", RANKING_MODES, "bm25")
        batch_id = str(upload_id)
        if not (cfg.upload_dir / batch_id).is_dir():
            raise ApiError("Upload not found", 404, "upload_not_found")
        job_id = str(service.start_upload_index(batch_id, ranking=ranking))
        state["last_job_id"] = job_id
        return api_success(
            {"job_id": job_id, "status": "queued", "generation": int(service.generation)},
            202,
        )

    @app.route("/api/index/status", methods=["GET"])
    def index_status():
        service = app.config["TSE_SERVICE"]
        job_id = request.args.get("job_id")
        if not _safe_id(job_id):
            raise ApiError("A valid job_id is required", 400, "invalid_job_id")
        job = service.get_job(job_id)
        if job is None:
            raise ApiError("Job not found", 404, "job_not_found")
        return api_success(_job_to_dict(job))

    @app.route("/api/index/jobs/<job_id>/cancel", methods=["POST"])
    def cancel_job(job_id: str):
        service = app.config["TSE_SERVICE"]
        if not _safe_id(job_id):
            raise ApiError("Invalid job_id", 400, "invalid_job_id")
        if service.get_job(job_id) is None:
            raise ApiError("Job not found", 404, "job_not_found")
        service.cancel_job(job_id)
        return api_success({"job_id": job_id, "status": "cancelling"})

    @app.route("/api/index/cancel", methods=["POST"])
    def cancel_index_alias():
        service = app.config["TSE_SERVICE"]
        job_id = state.get("last_job_id")
        if job_id:
            service.cancel_job(job_id)
            return api_success({"job_id": job_id, "status": "cancelling"})
        return api_success({"status": "cancelled"})

    @app.route("/api/search", methods=["POST"])
    def search():
        service = app.config["TSE_SERVICE"]
        started = time.perf_counter_ns()
        data = json_body()
        if "query" not in data:
            raise ApiError("query is required", 400, "invalid_query")
        try:
            spec = parse_query(data["query"], cfg)
        except ValueError as exc:
            raise ApiError(str(exc), 400, "invalid_query") from exc
        if spec.is_empty:
            raise ApiError("Query cannot be empty", 400, "invalid_query")

        ranking_value = data.get("ranking", data.get("rank", "bm25"))
        ranking = enum_value({"value": ranking_value}, "value", RANKING_MODES, "bm25")
        mode = enum_value(data, "mode", RETRIEVAL_MODES, "lexical")
        fuzzy = bool_value(data, "fuzzy", True)
        sort = enum_value(data, "sort", SORT_MODES, "relevance")
        try:
            threshold = validate_threshold(data.get("threshold", 0.0))
        except ValueError as exc:
            raise ApiError(str(exc), 400, "invalid_threshold") from exc
        try:
            limit, offset = validate_pagination(data.get("limit", 10), data.get("offset", 0), 100)
        except ValueError as exc:
            raise ApiError(str(exc), 400, "invalid_pagination") from exc

        filters = data.get("filters")
        if filters is None:
            filters = {}
        if not isinstance(filters, dict):
            raise ApiError("filters must be an object", 400, "invalid_parameter")
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ApiError(f"Unknown filters: {', '.join(sorted(unknown))}", 400, "invalid_parameter")
        source_type = filters.get("source_type")
        file_type = filters.get("file_type")
        if source_type is not None and not isinstance(source_type, str):
            raise ApiError("filters.source_type must be a string", 400, "invalid_parameter")
        if file_type is not None and not isinstance(file_type, str):
            raise ApiError("filters.file_type must be a string", 400, "invalid_parameter")

        options = SearchOptions(
            ranking=ranking,
            mode=mode,
            fuzzy=fuzzy,
            threshold=threshold,
            limit=limit,
            offset=offset,
            sort=sort,
            source_type=source_type,
            file_type=file_type,
        )
        page = service.search(spec, options, query_vector=query_vector(mode, spec.raw))
        body = _page_to_dict(page)
        body["elapsed_ms"] = round((time.perf_counter_ns() - started) / 1_000_000, 3)
        return api_success(body)

    @app.route("/api/documents/<doc_id>", methods=["GET"])
    def get_document(doc_id: str):
        service = app.config["TSE_SERVICE"]
        if not _valid_uuid(doc_id):
            raise ApiError("Invalid document id", 400, "invalid_document_id")
        document = service.get_document(doc_id)
        if document is None:
            raise ApiError("Document not found", 404, "document_not_found")
        content = document.get("content", "") if isinstance(document, dict) else getattr(document, "content", "")
        filename = document.get("filename", "document.txt") if isinstance(document, dict) else getattr(document, "filename", "document.txt")
        safe_name = secure_filename(str(filename)) or "document.txt"
        response = Response(str(content or ""), mimetype="text/plain; charset=utf-8")
        response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
        return response

    @app.route("/api/crawl", methods=["POST"])
    def crawl():
        service = app.config["TSE_SERVICE"]
        if not cfg.crawler_enabled:
            raise ApiError("Crawler is disabled", 403, "crawler_disabled")
        data = json_body()
        url = data.get("url")
        if not isinstance(url, str):
            raise ApiError("url must be a string", 400, "invalid_url")
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ApiError("url must be an http(s) URL", 400, "invalid_url")
        max_pages = _bounded_int(data, "max_pages", 10, 1, 100)
        max_depth = _bounded_int(data, "max_depth", 2, 0, 5)
        job_id = str(service.start_crawl(url, max_pages, max_depth))
        state["last_job_id"] = job_id
        return api_success(
            {"job_id": job_id, "status": "queued", "generation": int(service.generation)},
            202,
        )

    return app


app = create_app()


if __name__ == "__main__":
    runtime_config: Config = app.config["TSE_CONFIG"]
    app.run(
        host=runtime_config.host,
        port=runtime_config.port,
        debug=runtime_config.debug,
        use_reloader=False,
    )
