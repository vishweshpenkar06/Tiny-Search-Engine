import hashlib
import importlib
import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import Config
from core.models import AnalyzedToken, ParsedDocument, Posting, SnapshotData, StoredDocument

SCHEMA_VERSION = "1"
ACTIVE_JOB_STATUSES = ("queued", "running", "cancelling")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES generations(id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    analyzer_version TEXT,
    ranker_version TEXT,
    vector_model TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT NOT NULL,
    generation_id INTEGER NOT NULL REFERENCES generations(id),
    ordinal INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT,
    title TEXT NOT NULL,
    headings_json TEXT NOT NULL,
    body TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    word_count INTEGER NOT NULL,
    indexed_at TEXT NOT NULL,
    file_type TEXT NOT NULL,
    PRIMARY KEY (id, generation_id)
);
CREATE INDEX IF NOT EXISTS idx_documents_generation
    ON documents(generation_id, ordinal);
CREATE TABLE IF NOT EXISTS vectors (
    generation_id INTEGER NOT NULL REFERENCES generations(id),
    doc_id TEXT NOT NULL,
    model TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    PRIMARY KEY (generation_id, doc_id, model)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    claimed INTEGER NOT NULL DEFAULT 0,
    progress REAL NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    succeeded INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    generation_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, claimed, created_at);
CREATE TABLE IF NOT EXISTS upload_batches (
    upload_id TEXT PRIMARY KEY,
    folder_name TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS upload_files (
    upload_id TEXT NOT NULL REFERENCES upload_batches(upload_id),
    filename TEXT NOT NULL,
    blob_name TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (upload_id, blob_name)
);
"""

_JOB_FIELDS = {
    "kind",
    "payload",
    "status",
    "claimed",
    "progress",
    "processed",
    "succeeded",
    "skipped",
    "failed",
    "error",
    "generation_id",
    "finished_at",
}

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_DOC_NAMESPACE = uuid.UUID("1b671a64-40d5-491e-99b0-da01ff1f3341")


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


class IndexStore:
    def __init__(self, config: Config):
        self.config = config
        self._lock = threading.RLock()
        self._analyzer = None
        self._initialized = False
        self._closed = False
        Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(config.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def initialize(self) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.executescript(_SCHEMA)
            cur.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
            cur.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('created_at', ?)",
                (_now(),),
            )
            row = cur.execute(
                "SELECT value FROM schema_meta WHERE key='active_generation'"
            ).fetchone()
            if row is None:
                generation_id = self._create_generation(None, "bootstrap", "active")
                cur.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('active_generation', ?)",
                    (str(generation_id),),
                )
            else:
                generation_id = int(row["value"])
                existing = cur.execute(
                    "SELECT id FROM generations WHERE id=?", (generation_id,)
                ).fetchone()
                if existing is None:
                    generation_id = self._create_generation(None, "bootstrap", "active")
                    cur.execute(
                        "UPDATE schema_meta SET value=? WHERE key='active_generation'",
                        (str(generation_id),),
                    )
                else:
                    cur.execute(
                        "UPDATE generations SET status='active' WHERE id=? AND status != 'active'",
                        (generation_id,),
                    )
            self._conn.commit()
            self._initialized = True
            return generation_id

    def set_analyzer(self, analyzer) -> None:
        with self._lock:
            self._analyzer = analyzer

    def active_generation(self) -> int:
        with self._lock:
            self._require_init()
            row = self._conn.execute(
                "SELECT value FROM schema_meta WHERE key='active_generation'"
            ).fetchone()
            if row is None:
                raise RuntimeError("No active generation")
            return int(row["value"])

    def create_generation(self, parent_id: int | None, kind: str) -> int:
        with self._lock:
            self._require_init()
            if parent_id is not None:
                row = self._conn.execute(
                    "SELECT id FROM generations WHERE id=?", (parent_id,)
                ).fetchone()
                if row is None:
                    raise ValueError(f"Unknown parent generation {parent_id}")
            generation_id = self._create_generation(parent_id, kind, "staging")
            self._conn.commit()
            return generation_id

    def copy_generation(self, parent_id: int, kind: str) -> int:
        with self._lock:
            self._require_init()
            parent = self._conn.execute(
                "SELECT id FROM generations WHERE id=?", (parent_id,)
            ).fetchone()
            if parent is None:
                raise ValueError(f"Unknown generation {parent_id}")
            generation_id = self._create_generation(parent_id, kind, "staging")
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO documents (
                    id, generation_id, ordinal, source_key, filename, source_type,
                    source_url, title, headings_json, body, content, content_hash,
                    byte_size, word_count, indexed_at, file_type
                )
                SELECT id, ?, ordinal, source_key, filename, source_type, source_url,
                       title, headings_json, body, content, content_hash, byte_size,
                       word_count, indexed_at, file_type
                FROM documents WHERE generation_id=?
                """,
                (generation_id, parent_id),
            )
            cur.execute(
                """
                INSERT INTO vectors(generation_id, doc_id, model, vector_json)
                SELECT ?, doc_id, model, vector_json FROM vectors WHERE generation_id=?
                """,
                (generation_id, parent_id),
            )
            model = cur.execute(
                "SELECT vector_model FROM generations WHERE id=?", (parent_id,)
            ).fetchone()
            if model is not None and model["vector_model"]:
                cur.execute(
                    "UPDATE generations SET vector_model=? WHERE id=?",
                    (model["vector_model"], generation_id),
                )
            self._conn.commit()
            return generation_id

    def insert_document(
        self, generation_id: int, parsed: ParsedDocument
    ) -> StoredDocument:
        with self._lock:
            self._require_init()
            self._require_generation(generation_id, writable=True)
            doc_id = self._doc_id(parsed.source_type, parsed.source_key)
            row = self._conn.execute(
                "SELECT COALESCE(MAX(ordinal), -1) + 1 AS ordinal FROM documents WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
            ordinal = int(row["ordinal"])
            headings = tuple(str(item) for item in parsed.headings)
            self._conn.execute(
                """
                INSERT INTO documents (
                    id, generation_id, ordinal, source_key, filename, source_type,
                    source_url, title, headings_json, body, content, content_hash,
                    byte_size, word_count, indexed_at, file_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, generation_id) DO UPDATE SET
                    ordinal=excluded.ordinal,
                    source_key=excluded.source_key,
                    filename=excluded.filename,
                    source_type=excluded.source_type,
                    source_url=excluded.source_url,
                    title=excluded.title,
                    headings_json=excluded.headings_json,
                    body=excluded.body,
                    content=excluded.content,
                    content_hash=excluded.content_hash,
                    byte_size=excluded.byte_size,
                    word_count=excluded.word_count,
                    indexed_at=excluded.indexed_at,
                    file_type=excluded.file_type
                """,
                (
                    doc_id,
                    generation_id,
                    ordinal,
                    parsed.source_key,
                    parsed.filename,
                    parsed.source_type,
                    parsed.source_url,
                    parsed.title,
                    json.dumps(list(headings)),
                    parsed.body,
                    parsed.content,
                    parsed.content_hash,
                    int(parsed.byte_size),
                    int(parsed.word_count),
                    parsed.indexed_at,
                    parsed.file_type,
                ),
            )
            self._conn.commit()
            return StoredDocument(
                doc_id=doc_id,
                generation=generation_id,
                source_key=parsed.source_key,
                filename=parsed.filename,
                source_type=parsed.source_type,
                source_url=parsed.source_url,
                title=parsed.title,
                headings=headings,
                body=parsed.body,
                content=parsed.content,
                content_hash=parsed.content_hash,
                byte_size=int(parsed.byte_size),
                word_count=int(parsed.word_count),
                indexed_at=parsed.indexed_at,
                file_type=parsed.file_type,
            )

    def insert_vector(
        self,
        generation_id: int,
        doc_id: str,
        model: str,
        vector: tuple[float, ...],
    ) -> None:
        with self._lock:
            self._require_init()
            self._require_generation(generation_id, writable=True)
            exists = self._conn.execute(
                "SELECT 1 FROM documents WHERE generation_id=? AND id=?",
                (generation_id, doc_id),
            ).fetchone()
            if exists is None:
                raise ValueError(f"Unknown document {doc_id} in generation {generation_id}")
            values = [float(value) for value in vector]
            self._conn.execute(
                """
                INSERT INTO vectors(generation_id, doc_id, model, vector_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(generation_id, doc_id, model)
                DO UPDATE SET vector_json=excluded.vector_json
                """,
                (generation_id, doc_id, model, json.dumps(values)),
            )
            self._conn.execute(
                """
                UPDATE generations SET vector_model=?
                WHERE id=? AND vector_model IS NULL
                """,
                (model, generation_id),
            )
            self._conn.commit()

    def publish_generation(
        self, generation_id: int, analyzer_version: str, ranker_version: str
    ) -> None:
        with self._lock:
            self._require_init()
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._require_generation(generation_id, writable=False)
                row = self._conn.execute(
                    "SELECT status FROM generations WHERE id=?", (generation_id,)
                ).fetchone()
                if row["status"] not in ("staging", "active"):
                    raise ValueError(f"Generation {generation_id} cannot be published")
                published_at = _now()
                self._conn.execute(
                    "UPDATE generations SET status='retired' WHERE status='active' AND id != ?",
                    (generation_id,),
                )
                self._conn.execute(
                    """
                    UPDATE generations
                    SET status='active', analyzer_version=?, ranker_version=?, published_at=?
                    WHERE id=?
                    """,
                    (analyzer_version, ranker_version, published_at, generation_id),
                )
                self._conn.execute(
                    "UPDATE schema_meta SET value=? WHERE key='active_generation'",
                    (str(generation_id),),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def discard_generation(self, generation_id: int) -> None:
        with self._lock:
            self._require_init()
            row = self._conn.execute(
                "SELECT status FROM generations WHERE id=?", (generation_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown generation {generation_id}")
            if row["status"] == "active":
                raise ValueError("Cannot discard the active generation")
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "DELETE FROM vectors WHERE generation_id=?", (generation_id,)
                )
                self._conn.execute(
                    "DELETE FROM documents WHERE generation_id=?", (generation_id,)
                )
                self._conn.execute(
                    "UPDATE generations SET status='discarded' WHERE id=?", (generation_id,)
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def load_snapshot_data(self, generation_id: int) -> SnapshotData:
        with self._lock:
            self._require_init()
            generation = self._conn.execute(
                "SELECT vector_model FROM generations WHERE id=?", (generation_id,)
            ).fetchone()
            if generation is None:
                raise ValueError(f"Unknown generation {generation_id}")
            documents: dict[str, StoredDocument] = {}
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE generation_id=? ORDER BY ordinal, id",
                (generation_id,),
            ).fetchall()
            for row in rows:
                documents[row["id"]] = StoredDocument(
                    doc_id=row["id"],
                    generation=row["generation_id"],
                    source_key=row["source_key"],
                    filename=row["filename"],
                    source_type=row["source_type"],
                    source_url=row["source_url"],
                    title=row["title"],
                    headings=tuple(json.loads(row["headings_json"])),
                    body=row["body"],
                    content=row["content"],
                    content_hash=row["content_hash"],
                    byte_size=row["byte_size"],
                    word_count=row["word_count"],
                    indexed_at=row["indexed_at"],
                    file_type=row["file_type"],
                )
            vectors: dict[str, tuple[float, ...]] = {}
            vector_rows = self._conn.execute(
                "SELECT doc_id, vector_json FROM vectors WHERE generation_id=?",
                (generation_id,),
            ).fetchall()
            for row in vector_rows:
                vectors[row["doc_id"]] = tuple(float(value) for value in json.loads(row["vector_json"]))
            postings: dict[tuple[str, str], dict[str, Posting]] = {}
            field_lengths: dict[str, dict[str, int]] = {}
            for doc_id, document in documents.items():
                counts: dict[tuple[str, str], list[int]] = {}
                lengths: dict[str, int] = {}
                for token in self._analyze(document):
                    field = token.field or "body"
                    key = (token.term, field)
                    counts.setdefault(key, []).append(int(token.position))
                    lengths[field] = lengths.get(field, 0) + 1
                for (term, field), positions in counts.items():
                    postings.setdefault((term, field), {})[doc_id] = Posting(
                        tf=len(positions), positions=tuple(positions)
                    )
                field_lengths[doc_id] = lengths
            return SnapshotData(
                generation=generation_id,
                documents=documents,
                postings=postings,
                field_lengths=field_lengths,
                vectors=vectors,
                vector_model=generation["vector_model"],
            )

    def create_job(self, kind: str, payload: dict | None = None) -> dict:
        with self._lock:
            self._require_init()
            job_id = uuid.uuid4().hex
            now = _now()
            self._conn.execute(
                """
                INSERT INTO jobs (
                    id, kind, payload_json, status, claimed, created_at, updated_at, generation_id
                ) VALUES (?, ?, ?, 'queued', 0, ?, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    json.dumps(payload or {}),
                    now,
                    now,
                    self.active_generation(),
                ),
            )
            self._conn.commit()
            return self.get_job(job_id)

    def claim_job(self, kind: str, payload: dict | None = None) -> dict | None:
        with self._lock:
            self._require_init()
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                active = self._conn.execute(
                    "SELECT id FROM jobs WHERE status IN ('queued', 'running', 'cancelling') OR claimed=1 LIMIT 1"
                ).fetchone()
                if active is not None:
                    self._conn.rollback()
                    return None
                job_id = uuid.uuid4().hex
                now = _now()
                self._conn.execute(
                    """
                    INSERT INTO jobs (
                        id, kind, payload_json, status, claimed, created_at, updated_at, generation_id
                    ) VALUES (?, ?, ?, 'queued', 1, ?, ?, ?)
                    """,
                    (
                        job_id,
                        kind,
                        json.dumps(payload or {}),
                        now,
                        now,
                        self.active_generation(),
                    ),
                )
                self._conn.commit()
                return self.get_job(job_id)
            except Exception:
                self._conn.rollback()
                raise

    def update_job(self, job_id: str, **fields) -> dict:
        with self._lock:
            self._require_init()
            existing = self._conn.execute(
                "SELECT id FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"Unknown job {job_id}")
            assignments: list[str] = []
            values: list = []
            for name, value in fields.items():
                if name not in _JOB_FIELDS:
                    raise ValueError(f"Unknown job field {name}")
                assignments.append(f"{name}=?")
                if name == "payload":
                    values.append(json.dumps(value or {}))
                else:
                    values.append(value)
            if fields.get("status") in ("completed", "failed", "cancelled", "interrupted"):
                assignments.append("claimed=0")
            assignments.append("updated_at=?")
            values.append(_now())
            values.append(job_id)
            self._conn.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id=?", values
            )
            self._conn.commit()
            return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown job {job_id}")
            return self._job_dict(row)

    def find_running_job(self) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM jobs
                WHERE status IN ('queued', 'running', 'cancelling') OR claimed=1
                ORDER BY created_at LIMIT 1
                """
            ).fetchone()
            return self._job_dict(row) if row is not None else None

    def interrupted_jobs(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM jobs
                WHERE status IN ('queued', 'running', 'cancelling') OR claimed=1
                ORDER BY created_at
                """
            ).fetchall()
            return [self._job_dict(row) for row in rows]

    def create_upload_batch(self, upload_id: str, folder_name: str) -> None:
        with self._lock:
            self._require_init()
            if not isinstance(folder_name, str) or not folder_name.strip():
                raise ValueError("folder_name is required")
            root = self.config.upload_dir.resolve()
            candidate = (root / folder_name).resolve()
            if candidate != root and root not in candidate.parents:
                raise ValueError("Upload folder escapes the configured upload directory")
            candidate.mkdir(parents=True, exist_ok=True)
            self._conn.execute(
                """
                INSERT INTO upload_batches(upload_id, folder_name, folder_path, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(upload_id) DO UPDATE SET
                    folder_name=excluded.folder_name,
                    folder_path=excluded.folder_path
                """,
                (upload_id, folder_name, str(candidate), _now()),
            )
            self._conn.commit()

    def add_upload_file(
        self,
        upload_id: str,
        filename: str,
        blob_name: str,
        byte_size: int,
        content_hash: str,
    ) -> None:
        with self._lock:
            self._require_init()
            batch = self._conn.execute(
                "SELECT upload_id FROM upload_batches WHERE upload_id=?", (upload_id,)
            ).fetchone()
            if batch is None:
                raise ValueError(f"Unknown upload batch {upload_id}")
            row = self._conn.execute(
                "SELECT COALESCE(MAX(ordinal), -1) + 1 AS ordinal FROM upload_files WHERE upload_id=?",
                (upload_id,),
            ).fetchone()
            self._conn.execute(
                """
                INSERT INTO upload_files (
                    upload_id, filename, blob_name, byte_size, content_hash, ordinal
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(upload_id, blob_name) DO UPDATE SET
                    filename=excluded.filename,
                    byte_size=excluded.byte_size,
                    content_hash=excluded.content_hash
                """,
                (upload_id, filename, blob_name, int(byte_size), content_hash, int(row["ordinal"])),
            )
            self._conn.commit()

    def get_upload_batch(self, upload_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM upload_batches WHERE upload_id=?", (upload_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown upload batch {upload_id}")
            files = self._conn.execute(
                """
                SELECT filename, blob_name, byte_size, content_hash
                FROM upload_files WHERE upload_id=? ORDER BY ordinal, blob_name
                """,
                (upload_id,),
            ).fetchall()
            return {
                "upload_id": row["upload_id"],
                "folder_name": row["folder_name"],
                "folder_path": row["folder_path"],
                "created_at": row["created_at"],
                "files": [
                    {
                        "filename": item["filename"],
                        "blob_name": item["blob_name"],
                        "byte_size": item["byte_size"],
                        "content_hash": item["content_hash"],
                    }
                    for item in files
                ],
            }

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def _require_init(self) -> None:
        if not self._initialized:
            raise RuntimeError("IndexStore is not initialized")

    def _require_generation(self, generation_id: int, writable: bool) -> None:
        row = self._conn.execute(
            "SELECT status FROM generations WHERE id=?", (generation_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown generation {generation_id}")
        if writable and row["status"] not in ("staging", "active"):
            raise ValueError(f"Generation {generation_id} is not writable")

    def _create_generation(
        self, parent_id: int | None, kind: str, status: str
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO generations(parent_id, kind, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (parent_id, kind, status, _now()),
        )
        return int(cur.lastrowid or 0)

    @staticmethod
    def _doc_id(source_type: str, source_key: str) -> str:
        safe_type = re.sub(r"[^a-z0-9_-]+", "-", str(source_type).lower()).strip("-") or "doc"
        digest = hashlib.sha256(str(source_key).encode("utf-8")).hexdigest()
        return str(uuid.uuid5(_DOC_NAMESPACE, f"{safe_type}:{digest}"))

    @staticmethod
    def _job_dict(row: sqlite3.Row) -> dict:
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json") or "{}")
        result["job_id"] = result["id"]
        result["generation"] = result["generation_id"]
        return result

    def _analyze(self, document: StoredDocument) -> list[AnalyzedToken]:
        analyzer = self._analyzer
        if analyzer is not None:
            method = getattr(analyzer, "analyze", None)
            if callable(method):
                for args in ((document,), (document.content,)):
                    try:
                        tokens = method(*args)
                        normalized = self._normalize_tokens(tokens)
                        if normalized:
                            return normalized
                    except (TypeError, ValueError):
                        continue
        return self._fallback_tokens(document)

    @staticmethod
    def _normalize_tokens(tokens) -> list[AnalyzedToken]:
        result: list[AnalyzedToken] = []
        for index, item in enumerate(tokens or ()):
            if isinstance(item, AnalyzedToken):
                result.append(item)
                continue
            if isinstance(item, dict):
                term = item.get("term")
                if term is None:
                    continue
                result.append(
                    AnalyzedToken(
                        term=str(term),
                        surface=str(item.get("surface", term)),
                        position=int(item.get("position", index)),
                        field=str(item.get("field") or "body"),
                    )
                )
                continue
            if isinstance(item, (tuple, list)) and item:
                term = item[0]
                surface = item[1] if len(item) > 1 else term
                position = item[2] if len(item) > 2 else index
                field = item[3] if len(item) > 3 else "body"
                result.append(
                    AnalyzedToken(
                        term=str(term),
                        surface=str(surface),
                        position=int(position),
                        field=str(field or "body"),
                    )
                )
                continue
            if isinstance(item, str):
                result.append(
                    AnalyzedToken(term=item.lower(), surface=item, position=index, field="body")
                )
        return result

    @staticmethod
    def _fallback_tokens(document: StoredDocument) -> list[AnalyzedToken]:
        sections = (
            ("title", document.title),
            ("headings", " ".join(document.headings)),
            ("body", document.body or document.content),
        )
        result: list[AnalyzedToken] = []
        for field, text in sections:
            for position, match in enumerate(_WORD_RE.finditer(text or "")):
                surface = match.group(0)
                result.append(
                    AnalyzedToken(
                        term=surface.lower(),
                        surface=surface,
                        position=position,
                        field=field,
                    )
                )
        return result
