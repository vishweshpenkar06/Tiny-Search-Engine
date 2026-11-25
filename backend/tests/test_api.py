import importlib.util
import os
import sys
import tempfile
import types
import unittest
import uuid
from dataclasses import asdict, replace
from pathlib import Path

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


class _StubService:
    def __init__(self, config, store=None):
        self.config = config

    def initialize(self):
        return None


class _StubStore:
    def __init__(self, config):
        self.config = config

    def initialize(self):
        return None


def _install(name, attribute, value):
    if importlib.util.find_spec(name) is not None:
        return
    module = types.ModuleType(name)
    setattr(module, attribute, value)
    sys.modules[name] = module


_install("core.index_service", "IndexService", _StubService)
_install("core.index_store", "IndexStore", _StubStore)
_install("core.embeddings", "embed_query", lambda text: None)

from werkzeug.security import generate_password_hash

from app import create_app
from config import load_config
from core.models import SearchHit, SearchPage
from utils.validation import QuerySpec, QueryTerm

DOC_ID = "11111111-1111-4111-8111-111111111111"
OTHER_DOC_ID = "22222222-2222-4222-8222-222222222222"
BASIC_OK = {
    "Authorization": "Basic " + __import__("base64").b64encode(b"admin:secret").decode("ascii")
}


class FakeService:
    def __init__(self, config, raise_on_search=False):
        self.config = config
        self.generation_value = 7
        self.ready_value = (True, None)
        self.jobs = {}
        self.counter = 0
        self.documents = {
            DOC_ID: {
                "doc_id": DOC_ID,
                "filename": "guide.txt",
                "content": "Retrieval guide content",
            },
            OTHER_DOC_ID: {
                "doc_id": OTHER_DOC_ID,
                "filename": "../secret.txt",
                "content": "Other content",
            },
        }
        self.search_calls = []
        self.raise_on_search = raise_on_search
        self.analyzer = object()

    def initialize(self):
        return None

    @property
    def snapshot(self):
        return types.SimpleNamespace(document_count=len(self.documents))

    @property
    def generation(self):
        return self.generation_value

    def active_generation(self):
        return self.generation_value

    def ready(self):
        return self.ready_value

    def _new_job(self, kind):
        self.counter += 1
        job_id = f"job-{self.counter}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0.0,
            "processed": 0,
            "succeeded": 0,
            "skipped": 0,
            "failed": 0,
            "error": None,
            "generation": self.generation_value,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "finished_at": None,
        }
        return job_id

    def start_upload_index(self, upload_id, ranking="bm25"):
        return self._new_job(f"upload:{ranking}")

    def start_crawl(self, url, max_pages, max_depth):
        return self._new_job("crawl")

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def cancel_job(self, job_id):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "cancelling"
        return True

    def get_document(self, doc_id):
        return self.documents.get(doc_id)

    def upload_batch(self, upload_id):
        return []

    def register_upload(self, upload_id, files):
        return []

    def search(self, query_spec, options, query_vector=None):
        self.search_calls.append((query_spec, options, query_vector))
        if self.raise_on_search:
            raise RuntimeError("search exploded")
        hit = SearchHit(
            doc_id=DOC_ID,
            filename="guide.txt",
            source_type="upload",
            source_url=None,
            score=1.0,
            raw_score=12.5,
            snippet="A retrieval guide",
            word_count=3,
            file_size_bytes=120,
            indexed_at="2026-01-01T00:00:00+00:00",
            total_matches=1,
            matched_positions=(0,),
            explanation={"bm25": {"idf": 2.0}},
        )
        return SearchPage(
            query=query_spec.raw,
            ranking=options.ranking,
            mode=options.mode,
            generation=self.generation_value,
            total_results=1,
            results=(hit,),
            correction=None,
            facets={"source_type": {"upload": 1}, "file_type": {".txt": 1}},
            elapsed_ms=0.0,
        )


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.upload_dir = self.root / "uploads"
        self.upload_dir.mkdir()
        self.config = replace(
            load_config(),
            data_dir=self.root,
            upload_dir=self.upload_dir,
            db_path=self.root / "index.db",
            model_dir=self.root / "models",
            debug=False,
            admin_username=None,
            admin_password_hash=None,
            public_origin=None,
            rate_limit_per_minute=1000,
            max_file_size=64,
            max_files=4,
            max_query_length=500,
            crawler_enabled=False,
            embeddings_enabled=False,
        )
        self.service = FakeService(self.config)
        self.app = create_app(config=self.config, service=self.service)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_livez_readyz_and_config(self):
        for path in ("/api/health", "/livez", "/readyz"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.json["status"] in ("ok", "ready", "unready"), True)
            self.assertIn("request_id", response.json)
            self.assertEqual(response.headers["X-Request-ID"], response.json["request_id"])
        self.assertEqual(self.client.get("/api/health").json["status"], "ok")
        ready = self.client.get("/readyz").json
        self.assertEqual(ready["generation"], 7)
        self.assertEqual(ready["document_count"], 2)
        self.assertIsNone(ready["reason"])

        self.service.ready_value = (False, "cold_start")
        unready = self.client.get("/readyz").json
        self.assertEqual(unready["status"], "unready")
        self.assertEqual(unready["reason"], "cold_start")

        config = self.client.get("/api/config").json
        self.assertEqual(config["ranking_modes"], ["tfidf", "bm25"])
        self.assertEqual(config["retrieval_modes"], ["lexical", "semantic", "hybrid"])
        self.assertEqual(config["max_file_size"], 64)
        self.assertFalse(config["auth_enabled"])

    def test_error_envelopes(self):
        cases = [
            (self.client.post("/api/search", data="not json", content_type="text/plain"), 415, "unsupported_media_type"),
            (self.client.post("/api/search", data="{", content_type="application/json"), 400, "invalid_json"),
            (self.client.get("/api/search"), 405, "method_not_allowed"),
            (self.client.get("/api/documents/" + str(uuid.uuid4())), 404, "document_not_found"),
            (self.client.get("/api/documents/not-a-uuid"), 400, "invalid_document_id"),
            (self.client.get("/api/index/status"), 400, "invalid_job_id"),
            (self.client.get("/api/index/status?job_id=missing"), 404, "job_not_found"),
        ]
        for response, status, code in cases:
            self.assertEqual(response.status_code, status)
            self.assertIn("error", response.json)
            self.assertEqual(response.json["error"]["code"], code)
            self.assertIsInstance(response.json["error"]["message"], str)
            self.assertIn("request_id", response.json)

        failing = FakeService(self.config, raise_on_search=True)
        broken = create_app(config=self.config, service=failing)
        broken.config["TESTING"] = True
        response = broken.test_client().post(
            "/api/search", json={"query": "test"}, headers={"Origin": "http://localhost:3000"}
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["error"]["code"], "internal_error")
        self.assertNotIn("exploded", response.json["error"]["message"])

    def test_authentication_and_origin(self):
        secured = replace(
            self.config,
            admin_username="admin",
            admin_password_hash=generate_password_hash("secret"),
            public_origin="http://localhost:3000",
        )
        app = create_app(config=secured, service=FakeService(secured))
        app.config["TESTING"] = True
        client = app.test_client()

        self.assertEqual(client.get("/api/config").status_code, 401)
        unauthorized = client.get("/api/config")
        self.assertIn("WWW-Authenticate", unauthorized.headers)
        self.assertEqual(unauthorized.json["error"]["code"], "unauthorized")

        self.assertEqual(client.get("/api/config", headers=BASIC_OK).status_code, 200)
        bad = {"Authorization": "Basic " + __import__("base64").b64encode(b"admin:wrong").decode("ascii")}
        self.assertEqual(client.get("/api/config", headers=bad).status_code, 401)

        for path in ("/api/health", "/livez", "/readyz"):
            self.assertEqual(client.get(path).status_code, 200, path)

        mutation = {"Authorization": BASIC_OK["Authorization"], "Origin": "http://evil.example"}
        response = client.post("/api/search", json={"query": "test"}, headers=mutation)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json["error"]["code"], "forbidden_origin")

        missing_origin = {"Authorization": BASIC_OK["Authorization"]}
        self.assertEqual(client.post("/api/search", json={"query": "test"}, headers=missing_origin).status_code, 403)

        good = dict(BASIC_OK)
        good["Origin"] = "http://localhost:3000/"
        self.assertEqual(client.post("/api/search", json={"query": "test"}, headers=good).status_code, 200)

    def test_rate_limit(self):
        limited = replace(self.config, rate_limit_per_minute=1)
        app = create_app(config=limited, service=FakeService(limited))
        app.config["TESTING"] = True
        client = app.test_client()
        self.assertEqual(client.get("/api/config").status_code, 200)
        second = client.get("/api/config")
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json["error"]["code"], "rate_limited")
        self.assertEqual(client.get("/api/health").status_code, 200)

    def test_upload_streams_validates_and_isolates_batches(self):
        response = self.client.post(
            "/api/upload",
            data={
                "files": [
                    (__import__("io").BytesIO(b"hello world one"), "first.txt"),
                    (__import__("io").BytesIO(b"x" * 100), "too_big.md"),
                    (__import__("io").BytesIO(b"data"), "bad.exe"),
                    (__import__("io").BytesIO(b""), "empty.txt"),
                ]
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json
        self.assertEqual(body["file_count"], 1)
        self.assertEqual(len(body["rejected"]), 3)
        self.assertTrue(all("too_big" in item or "bad.exe" in item or "empty" in item for item in body["rejected"]))
        self.assertTrue(_valid_uuid(body["upload_id"]))
        self.assertEqual(body["generation"], 7)

        batch_dir = self.upload_dir / body["upload_id"]
        blobs = sorted(p.name for p in batch_dir.iterdir())
        self.assertEqual(len(blobs), 1)
        self.assertTrue(blobs[0].startswith("0000_"))
        self.assertTrue(blobs[0].endswith(".txt"))
        self.assertNotIn("first.txt", blobs[0])

        second = self.client.post(
            "/api/upload",
            data={"files": [(__import__("io").BytesIO(b"second batch"), "second.md")]},
            content_type="multipart/form-data",
        )
        self.assertNotEqual(second.json["upload_id"], body["upload_id"])
        self.assertTrue((self.upload_dir / second.json["upload_id"]).is_dir())
        self.assertEqual(second.json["file_count"], 1)

        traversal = self.client.post(
            "/api/upload",
            data={"files": [(__import__("io").BytesIO(b"safe"), "../escape.txt")]},
            content_type="multipart/form-data",
        )
        self.assertEqual(traversal.status_code, 200)
        self.assertEqual(traversal.json["file_count"], 1)
        self.assertNotIn("..", traversal.get_data(as_text=True))

        no_files = self.client.post("/api/upload", data={}, content_type="multipart/form-data")
        self.assertEqual(no_files.status_code, 400)
        self.assertEqual(no_files.json["error"]["code"], "no_files")

    def test_upload_limits(self):
        limited = replace(self.config, max_files=1)
        app = create_app(config=limited, service=FakeService(limited))
        app.config["TESTING"] = True
        response = app.test_client().post(
            "/api/upload",
            data={
                "files": [
                    (__import__("io").BytesIO(b"one"), "a.txt"),
                    (__import__("io").BytesIO(b"two"), "b.txt"),
                ]
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json["error"]["code"], "too_many_files")

    def test_opaque_ids_and_job_lifecycle(self):
        uploaded = self.client.post(
            "/api/upload",
            data={"files": [(__import__("io").BytesIO(b"index me"), "doc.txt")]},
            content_type="multipart/form-data",
        ).json
        upload_id = uploaded["upload_id"]

        started = self.client.post("/api/index", json={"upload_id": upload_id, "ranking": "bm25"})
        self.assertEqual(started.status_code, 202)
        self.assertEqual(started.json["status"], "queued")
        job_id = started.json["job_id"]
        self.assertNotIn(str(self.root), started.get_data(as_text=True))

        status = self.client.get("/api/index/status?job_id=" + job_id)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json["job_id"], job_id)
        self.assertEqual(status.json["status"], "queued")
        self.assertEqual(status.json["generation"], 7)

        cancelled = self.client.post(f"/api/index/jobs/{job_id}/cancel")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json["status"], "cancelling")
        self.assertEqual(self.client.get("/api/index/status?job_id=" + job_id).json["status"], "cancelling")

        alias = self.client.post("/api/index/cancel")
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.json["job_id"], job_id)

        self.assertEqual(
            self.client.post("/api/index", json={"upload_id": "../../etc/passwd"}).json["error"]["code"],
            "invalid_upload_id",
        )
        self.assertEqual(
            self.client.post("/api/index", json={"upload_id": str(uuid.uuid4())}).status_code,
            404,
        )
        self.assertEqual(
            self.client.post("/api/index", json={"upload_id": upload_id, "ranking": "magic"}).status_code,
            400,
        )

    def test_search_validation_and_result_shape(self):
        valid = {"query": "retrieval guide", "ranking": "bm25", "mode": "lexical", "fuzzy": False}
        response = self.client.post("/api/search", json=valid)
        self.assertEqual(response.status_code, 200)
        body = response.json
        self.assertEqual(body["query"], "retrieval guide")
        self.assertEqual(body["ranking"], "bm25")
        self.assertEqual(body["mode"], "lexical")
        self.assertEqual(body["generation"], 7)
        self.assertEqual(body["total_results"], 1)
        self.assertEqual(body["results"][0]["doc_id"], DOC_ID)
        self.assertIsInstance(body["elapsed_ms"], (int, float))
        self.assertIn("request_id", body)
        self.assertNotIn(str(self.root), response.get_data(as_text=True))

        spec, options, vector = self.service.search_calls[-1]
        self.assertIsInstance(spec, QuerySpec)
        self.assertEqual(options.ranking, "bm25")
        self.assertEqual(options.mode, "lexical")
        self.assertFalse(options.fuzzy)
        self.assertEqual(options.limit, 10)
        self.assertEqual(options.offset, 0)
        self.assertIsNone(vector)

        invalid = [
            ({}, "invalid_query"),
            ({"query": 123}, "invalid_query"),
            ({"query": "   "}, "invalid_query"),
            ({"query": "x" * 501}, "invalid_query"),
            ({"query": "x", "ranking": "magic"}, "invalid_parameter"),
            ({"query": "x", "mode": "magic"}, "invalid_parameter"),
            ({"query": "x", "fuzzy": "yes"}, "invalid_parameter"),
            ({"query": "x", "sort": "magic"}, "invalid_parameter"),
            ({"query": "x", "threshold": 1.5}, "invalid_threshold"),
            ({"query": "x", "threshold": "high"}, "invalid_threshold"),
            ({"query": "x", "limit": 0}, "invalid_pagination"),
            ({"query": "x", "limit": 101}, "invalid_pagination"),
            ({"query": "x", "limit": 2.5}, "invalid_pagination"),
            ({"query": "x", "offset": -1}, "invalid_pagination"),
            ({"query": "x", "filters": []}, "invalid_parameter"),
            ({"query": "x", "filters": {"unknown": "a"}}, "invalid_parameter"),
            ({"query": "x", "filters": {"source_type": 5}}, "invalid_parameter"),
        ]
        for payload, code in invalid:
            result = self.client.post("/api/search", json=payload)
            self.assertEqual(result.status_code, 400, payload)
            self.assertEqual(result.json["error"]["code"], code, payload)

        array_body = self.client.post("/api/search", json=["x"])
        self.assertEqual(array_body.status_code, 400)
        self.assertEqual(array_body.json["error"]["code"], "invalid_json")

        pagination = self.client.post(
            "/api/search",
            json={"query": "x", "limit": 5, "offset": 2, "sort": "size", "threshold": 0.5, "fuzzy": True,
                  "filters": {"source_type": "upload", "file_type": ".txt"}},
        )
        self.assertEqual(pagination.status_code, 200)
        _, options, _ = self.service.search_calls[-1]
        self.assertEqual((options.limit, options.offset, options.sort), (5, 2, "size"))
        self.assertEqual(options.threshold, 0.5)
        self.assertTrue(options.fuzzy)
        self.assertEqual((options.source_type, options.file_type), ("upload", ".txt"))

    def test_document_retrieval_and_safe_disposition(self):
        response = self.client.get("/api/documents/" + DOC_ID)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/plain")
        self.assertEqual(response.get_data(as_text=True), "Retrieval guide content")
        self.assertIn('filename="guide.txt"', response.headers["Content-Disposition"])
        self.assertIn("X-Request-ID", response.headers)

        other = self.client.get("/api/documents/" + OTHER_DOC_ID)
        self.assertEqual(other.status_code, 200)
        self.assertNotIn("..", other.headers["Content-Disposition"])
        self.assertEqual(other.headers["Content-Disposition"], 'inline; filename="secret.txt"')

    def test_crawl_disabled_and_enabled(self):
        response = self.client.post("/api/crawl", json={"url": "https://example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json["error"]["code"], "crawler_disabled")

        enabled = replace(self.config, crawler_enabled=True)
        app = create_app(config=enabled, service=FakeService(enabled))
        app.config["TESTING"] = True
        client = app.test_client()
        invalid = client.post("/api/crawl", json={"url": "file:///etc/passwd"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json["error"]["code"], "invalid_url")
        started = client.post(
            "/api/crawl", json={"url": "https://example.com/docs", "max_pages": 3, "max_depth": 1}
        )
        self.assertEqual(started.status_code, 202)
        self.assertEqual(started.json["status"], "queued")
        too_many = client.post("/api/crawl", json={"url": "https://example.com", "max_pages": 999})
        self.assertEqual(too_many.status_code, 400)

    def test_no_absolute_path_leakage(self):
        paths = [
            self.client.get("/api/health").get_data(as_text=True),
            self.client.get("/api/config").get_data(as_text=True),
            self.client.get("/readyz").get_data(as_text=True),
            self.client.post("/api/search", json={"query": "guide"}).get_data(as_text=True),
        ]
        for body in paths:
            self.assertNotIn(str(self.root), body)
            self.assertNotIn(str(self.upload_dir), body)


def _valid_uuid(value):
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


if __name__ == "__main__":
    unittest.main()
