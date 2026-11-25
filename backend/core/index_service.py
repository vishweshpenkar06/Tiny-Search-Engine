import hashlib
import importlib
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from config import Config
from core.models import ParsedDocument, StoredDocument
from crawler.crawl import CrawlError, crawl_site, validate_target


class JobRef(dict):
    def __str__(self) -> str:
        return str(self.get("job_id", ""))


class _Cancelled(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _import_one(modules: tuple[str, ...], name: str):
    for module in modules:
        try:
            loaded = importlib.import_module(module)
        except ImportError:
            continue
        value = getattr(loaded, name, None)
        if value is not None:
            return value
    raise ImportError(f"Could not import {name} from any of {', '.join(modules)}")


_INTERFACES = None


def _interfaces():
    global _INTERFACES
    if _INTERFACES is None:
        _INTERFACES = (
            _import_one(("core.file_parser", "core.parsing", "core.parser"), "parse_file"),
            _import_one(("core.analysis", "core.analyzer"), "Analyzer"),
            _import_one(("core.index_model", "core.search_engine", "core.snapshot"), "build_snapshot"),
        )
    return _INTERFACES


def _value(item, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _embed_document(config: Config, document):
    if not config.embeddings_enabled:
        return None
    module = importlib.import_module("core.embeddings")
    text = " ".join(
        str(value)
        for value in (
            _value(document, "title", ""),
            " ".join(_value(document, "headings", ()) or ()),
            _value(document, "body", ""),
        )
        if value
    )
    return module.model_name(), module.embed_document(text)


class IndexService:
    def __init__(self, config: Config, store):
        self.config = config
        self.store = store
        self._snapshot = None
        self._generation = 0
        self._analyzer = None
        self._lock = threading.RLock()
        self._cancel_events: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}

    def initialize(self) -> None:
        self.store.initialize()
        _, analyzer_type, build_snapshot = _interfaces()
        self._analyzer = self._make_analyzer(analyzer_type)
        self.store.set_analyzer(self._analyzer)
        for job in self.store.interrupted_jobs():
            self.store.update_job(
                job["job_id"],
                status="interrupted",
                error="Interrupted by restart",
                finished_at=_now(),
            )
        generation = self.store.active_generation()
        data = self.store.load_snapshot_data(generation)
        snapshot = build_snapshot(data, self.config)
        self._adopt_snapshot(snapshot, data)
        with self._lock:
            self._generation = generation
            self._snapshot = snapshot

    @property
    def snapshot(self):
        return self._snapshot

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def analyzer(self):
        return self._analyzer

    def start_upload_index(self, upload_id: str, ranking: str = "bm25") -> JobRef:
        job = self.store.claim_job("upload", {"upload_id": upload_id, "ranking": ranking})
        if job is None:
            raise RuntimeError("Another indexing job is already running")
        job_id = job["job_id"]
        event = threading.Event()
        self._cancel_events[job_id] = event
        thread = threading.Thread(
            target=self._run_upload,
            args=(job_id, upload_id, ranking, event),
            daemon=True,
            name=f"index-upload-{job_id[:8]}",
        )
        self._threads[job_id] = thread
        thread.start()
        return JobRef(self.get_job(job_id) or job)

    def start_crawl(self, url: str, max_pages: int = 50, max_depth: int = 2) -> JobRef:
        if not self.config.crawler_enabled:
            raise RuntimeError("Crawler is disabled")
        validate_target(url, self.config.crawler_allowed_domains)
        job = self.store.claim_job(
            "crawl", {"url": url, "max_pages": max_pages, "max_depth": max_depth}
        )
        if job is None:
            raise RuntimeError("Another indexing job is already running")
        job_id = job["job_id"]
        event = threading.Event()
        self._cancel_events[job_id] = event
        thread = threading.Thread(
            target=self._run_crawl,
            args=(job_id, url, max_pages, max_depth, event),
            daemon=True,
            name=f"index-crawl-{job_id[:8]}",
        )
        self._threads[job_id] = thread
        thread.start()
        return JobRef(self.get_job(job_id) or job)

    def get_job(self, job_id: str) -> dict | None:
        try:
            job = dict(self.store.get_job(job_id))
        except ValueError:
            return None
        job["job_id"] = job_id
        job["generation"] = job.get("generation_id")
        return job

    def cancel_job(self, job_id: str) -> dict | None:
        event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()
        job = self.get_job(job_id)
        if job is None:
            return None
        if job.get("status") in ("queued", "running", "cancelling"):
            return self.store.update_job(job_id, status="cancelling")
        return job

    def active_generation(self) -> int:
        return self._generation or self.store.active_generation()

    def ready(self) -> tuple[bool, str | None]:
        if self._snapshot is None:
            return False, "index_not_initialized"
        if self._snapshot.document_count == 0:
            return False, "index_empty"
        return True, None

    def get_document(self, doc_id: str) -> StoredDocument | None:
        return self._documents().get(doc_id)

    def upload_batch(self, upload_id: str) -> dict | None:
        try:
            return self.store.get_upload_batch(upload_id)
        except ValueError:
            return None

    def register_upload(self, upload_id: str, files: list[dict]) -> dict | None:
        self.store.create_upload_batch(upload_id, upload_id)
        for item in files:
            self.store.add_upload_file(
                upload_id,
                str(item["filename"]),
                str(item["blob_name"]),
                int(item["byte_size"]),
                str(item["content_hash"]),
            )
        return self.upload_batch(upload_id)

    def search(self, query_spec, options, query_vector=None):
        if self._snapshot is None:
            raise RuntimeError("Index is not initialized")
        return self._snapshot.search(query_spec, options, query_vector=query_vector)

    def _documents(self) -> dict:
        if self._snapshot is None:
            return {}
        documents = getattr(self._snapshot, "documents", None)
        if documents is None:
            data = getattr(self._snapshot, "data", None)
            documents = getattr(data, "documents", {})
        return documents or {}

    @staticmethod
    def _adopt_snapshot(snapshot, data) -> None:
        if not hasattr(snapshot, "document_count"):
            try:
                snapshot.document_count = data.document_count
            except (AttributeError, TypeError):
                pass

    def _make_analyzer(self, analyzer_type):
        try:
            return analyzer_type(self.config)
        except TypeError:
            return analyzer_type()

    def _publish(self, generation_id: int, ranking: str) -> None:
        _, _, build_snapshot = _interfaces()
        data = self.store.load_snapshot_data(generation_id)
        snapshot = build_snapshot(data, self.config)
        self._adopt_snapshot(snapshot, data)
        version = _value(self._analyzer, "version", "unknown")
        if callable(version):
            version = version()
        self.store.publish_generation(generation_id, str(version), str(ranking))
        with self._lock:
            self._generation = generation_id
            self._snapshot = snapshot

    def _cancelled(self, job_id: str, event: threading.Event) -> bool:
        if event.is_set():
            return True
        job = self.get_job(job_id)
        if job is None:
            return True
        return job.get("status") in ("cancelling", "cancelled")

    def _ensure_batch(self, upload_id: str) -> dict:
        batch = self.upload_batch(upload_id)
        if batch is not None:
            return batch
        root = self.config.upload_dir.resolve()
        candidate = (root / upload_id).resolve()
        if candidate == root or root not in candidate.parents:
            raise ValueError("Upload folder escapes the configured upload directory")
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("Upload folder is not a safe directory")
        files: list[tuple[str, str, int, str]] = []
        for path in sorted(candidate.iterdir()):
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            if root not in resolved.parents or candidate not in resolved.parents:
                raise ValueError("Upload file escapes the configured upload directory")
            files.append((path.name, path.name, path.stat().st_size, _hash_file(path)))
        self.store.create_upload_batch(upload_id, upload_id)
        for filename, blob_name, size, digest in files:
            self.store.add_upload_file(upload_id, filename, blob_name, size, digest)
        return self.store.get_upload_batch(upload_id)

    def _resolve_upload_files(self, batch: dict):
        root = self.config.upload_dir.resolve()
        folder = Path(batch["folder_path"]).resolve()
        if folder == root or root not in folder.parents:
            raise ValueError("Upload folder escapes the configured upload directory")
        for item in batch.get("files", []):
            blob_name = str(item["blob_name"])
            if Path(blob_name).is_absolute() or ".." in Path(blob_name).parts:
                continue
            candidate = (folder / blob_name).resolve()
            if candidate == folder or root not in candidate.parents or folder not in candidate.parents:
                continue
            if candidate.is_symlink() or not candidate.is_file():
                continue
            yield item, candidate

    def _normalize_parsed(self, parsed, blob_name: str, filename: str):
        if parsed is None:
            return None
        source_key = _value(parsed, "source_key", blob_name)
        if not isinstance(source_key, str) or not source_key:
            source_key = blob_name
        if Path(source_key).is_absolute():
            source_key = blob_name
        source_type = _value(parsed, "source_type", "upload") or "upload"
        defaults = {
            "source_key": source_key,
            "filename": _value(parsed, "filename", filename) or filename,
            "source_type": source_type,
            "source_url": _value(parsed, "source_url", None),
            "title": _value(parsed, "title", "") or "",
            "headings": tuple(_value(parsed, "headings", ()) or ()),
            "body": _value(parsed, "body", "") or "",
            "content": _value(parsed, "content", "") or "",
            "content_hash": _value(parsed, "content_hash", "") or hashlib.sha256(
                str(_value(parsed, "content", "") or "").encode("utf-8")
            ).hexdigest(),
            "byte_size": int(_value(parsed, "byte_size", 0) or 0),
            "word_count": int(_value(parsed, "word_count", 0) or 0),
            "indexed_at": _value(parsed, "indexed_at", _now()) or _now(),
            "file_type": _value(parsed, "file_type", "") or "",
        }
        if isinstance(parsed, ParsedDocument):
            return replace(parsed, **defaults)
        return ParsedDocument(**defaults)

    def _run_upload(
        self, job_id: str, upload_id: str, ranking: str, event: threading.Event
    ) -> None:
        parse_file, _, _ = _interfaces()
        generation_id = None
        try:
            self.store.update_job(job_id, status="running")
            batch = self._ensure_batch(upload_id)
            parent = self.generation or self.store.active_generation()
            generation_id = self.store.create_generation(parent, "upload")
            self.store.update_job(job_id, generation_id=generation_id)
            items = list(self._resolve_upload_files(batch))
            succeeded = skipped = failed = 0
            total = max(1, len(items))
            for index, (item, path) in enumerate(items, start=1):
                if self._cancelled(job_id, event):
                    raise _Cancelled()
                try:
                    parsed = parse_file(
                        str(path), "upload", None, str(item["filename"])
                    )
                    parsed = self._normalize_parsed(
                        parsed, str(item["blob_name"]), str(item["filename"])
                    )
                    if parsed is None or not parsed.content:
                        skipped += 1
                    else:
                        stored = self.store.insert_document(generation_id, parsed)
                        embedded = _embed_document(self.config, stored)
                        if embedded is not None:
                            self.store.insert_vector(generation_id, stored.doc_id, *embedded)
                        succeeded += 1
                except Exception:
                    failed += 1
                self.store.update_job(
                    job_id,
                    progress=index / total,
                    processed=index,
                    succeeded=succeeded,
                    skipped=skipped,
                    failed=failed,
                )
            if self._cancelled(job_id, event):
                raise _Cancelled()
            self._publish(generation_id, ranking)
            self.store.update_job(
                job_id, status="completed", progress=1.0, finished_at=_now()
            )
        except _Cancelled:
            self._abandon(generation_id)
            self.store.update_job(
                job_id,
                status="cancelled",
                error="Cancelled by user",
                finished_at=_now(),
            )
        except CrawlError as exc:
            self._abandon(generation_id)
            self.store.update_job(
                job_id, status="failed", error=str(exc), finished_at=_now()
            )
        except Exception as exc:
            self._abandon(generation_id)
            self.store.update_job(
                job_id, status="failed", error=str(exc), finished_at=_now()
            )
        finally:
            self._cancel_events.pop(job_id, None)
            self._threads.pop(job_id, None)

    def _run_crawl(
        self, job_id: str, url: str, max_pages: int, max_depth: int, event: threading.Event
    ) -> None:
        generation_id = None
        try:
            self.store.update_job(job_id, status="running")
            parent = self.generation or self.store.active_generation()
            generation_id = self.store.copy_generation(parent, "crawl")
            succeeded = 0
            for page in crawl_site(
                url,
                self.config,
                max_pages,
                max_depth,
                allowed_domains=self.config.crawler_allowed_domains,
                cancel=lambda: self._cancelled(job_id, event),
            ):
                if self._cancelled(job_id, event):
                    raise _Cancelled()
                stored = self.store.insert_document(generation_id, self._page_to_parsed(page))
                embedded = _embed_document(self.config, stored)
                if embedded is not None:
                    self.store.insert_vector(generation_id, stored.doc_id, *embedded)
                succeeded += 1
                self.store.update_job(
                    job_id,
                    processed=succeeded,
                    succeeded=succeeded,
                    progress=min(1.0, succeeded / max(1, max_pages)),
                )
            if self._cancelled(job_id, event):
                raise _Cancelled()
            self._publish(generation_id, "crawl")
            self.store.update_job(
                job_id, status="completed", progress=1.0, finished_at=_now()
            )
        except _Cancelled:
            self._abandon(generation_id)
            self.store.update_job(
                job_id,
                status="cancelled",
                error="Cancelled by user",
                finished_at=_now(),
            )
        except Exception as exc:
            self._abandon(generation_id)
            self.store.update_job(
                job_id, status="failed", error=str(exc), finished_at=_now()
            )
        finally:
            self._cancel_events.pop(job_id, None)
            self._threads.pop(job_id, None)

    def _abandon(self, generation_id: int | None) -> None:
        if generation_id is None:
            return
        try:
            self.store.discard_generation(generation_id)
        except ValueError:
            pass

    @staticmethod
    def _page_to_parsed(page) -> ParsedDocument:
        path = urlsplit(page.url).path
        filename = Path(path).name or "index.html"
        text = page.text or ""
        return ParsedDocument(
            source_key=page.url,
            filename=filename,
            source_type="web",
            source_url=page.url,
            title=page.title,
            headings=tuple(page.headings),
            body=page.body,
            content=text,
            content_hash=page.content_hash,
            byte_size=len(text.encode("utf-8")),
            word_count=len(text.split()),
            indexed_at=_now(),
            file_type="text/html",
        )
