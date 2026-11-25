import tempfile
import threading
import time
import unittest
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from unittest import mock

import core.file_parser as file_parser
import core.index_service as index_service_module
from config import Config
from core.index_service import IndexService
from core.index_store import IndexStore
from core.models import ParsedDocument, SearchOptions
from crawler.crawl import CrawlError
from utils.validation import parse_query


def make_config(root: Path, **overrides) -> Config:
    base = Config(
        debug=False,
        host="127.0.0.1",
        port=5000,
        data_dir=root,
        upload_dir=root / "uploads",
        db_path=root / "index.db",
        model_dir=root / "models",
        max_content_length=1024 * 1024,
        max_file_size=1024 * 1024,
        max_files=100,
        max_query_length=500,
        admin_username=None,
        admin_password_hash=None,
        public_origin=None,
        rate_limit_per_minute=120,
        embeddings_enabled=False,
        crawler_enabled=False,
        crawler_allowed_domains=(),
        bm25_k1=1.2,
        bm25_b=0.75,
        rrf_k=60,
    )
    return replace(base, **overrides) if overrides else base


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "uploads").mkdir()
        self.config = make_config(self.root)
        self.store = IndexStore(self.config)
        self.store.initialize()
        index_service_module._INTERFACES = None
        self.service = IndexService(self.config, self.store)
        self.service.initialize()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _docs(self):
        return self.service._documents()

    def _write_batch(self, upload_id: str, files: dict[str, str]) -> Path:
        folder = self.config.upload_dir / upload_id
        folder.mkdir(parents=True, exist_ok=True)
        for blob, text in files.items():
            (folder / blob).write_text(text, encoding="utf-8")
        return folder

    def _wait(self, job_id: str, timeout: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.service.get_job(job_id)
            if job is not None and job["status"] in (
                "completed",
                "failed",
                "cancelled",
                "interrupted",
            ):
                return job
            time.sleep(0.01)
        self.fail(f"Job {job_id} did not finish")

    def test_initialize_marks_interrupted_jobs(self):
        job = self.store.create_job("upload", {"upload_id": "unfinished"})
        self.store.update_job(job["job_id"], status="running")
        index_service_module._INTERFACES = None
        service = IndexService(self.config, self.store)
        service.initialize()
        recovered = self.service.get_job(job["job_id"]) or {}
        self.assertEqual(recovered["status"], "interrupted")
        self.assertIs(service.analyzer, service.analyzer)
        self.assertEqual(service.generation, self.store.active_generation())

    def test_add_update_delete_through_new_generations(self):
        first_generation = self.service.generation
        self._write_batch("batch-one", {"0000_a.txt": "alpha bravo"})
        job = self.service.start_upload_index("batch-one")
        self.assertEqual(self._wait(str(job))["status"], "completed")
        self.assertGreater(self.service.generation, first_generation)
        self.assertEqual(len(self._docs()), 1)
        original_id = next(iter(self._docs()))

        self._write_batch(
            "batch-two",
            {
                "0000_renamed.txt": "alpha bravo",
                "0001_new.txt": "delta gamma",
            },
        )
        job = self.service.start_upload_index("batch-two")
        self.assertEqual(self._wait(str(job))["status"], "completed")
        docs = self._docs()
        self.assertEqual(len(docs), 2)
        self.assertIn(original_id, docs)
        self.assertEqual(docs[original_id].filename, "0000_renamed.txt")

        staged = self.store.copy_generation(self.service.generation, "test-update")
        updated = ParsedDocument(
            source_key=docs[original_id].source_key,
            filename="0000_renamed.txt",
            source_type="upload",
            source_url=None,
            title="updated",
            headings=(),
            body="updated body content",
            content="updated body content",
            content_hash="updated-hash",
            byte_size=20,
            word_count=3,
            indexed_at="2026-01-02T00:00:00+00:00",
            file_type="text/plain",
        )
        self.store.insert_document(staged, updated)
        self.store.publish_generation(staged, "v1", "bm25")
        index_service_module._INTERFACES = None
        self.service.initialize()
        updated_document = self.service.get_document(original_id)
        self.assertIsNotNone(updated_document)
        self.assertEqual(getattr(updated_document, "content", None), "updated body content")

        self._write_batch("batch-three", {"0002_other.txt": "completely different"})
        job = self.service.start_upload_index("batch-three")
        self.assertEqual(self._wait(str(job))["status"], "completed")
        docs = self._docs()
        self.assertEqual(len(docs), 1)
        self.assertNotIn(original_id, docs)
        self.assertEqual(next(iter(docs.values())).filename, "0002_other.txt")

    def test_single_running_job_and_cooperative_cancellation(self):
        self._write_batch("batch-slow", {"0000_slow.txt": "alpha beta"})
        gate = threading.Event()
        original = file_parser.parse_file

        def slow_parse(path, source_type="upload", source_url=None, filename=None):
            gate.wait(timeout=5)
            return original(path, source_type, source_url, filename)

        generation_before = self.service.generation
        with mock.patch.object(file_parser, "parse_file", side_effect=slow_parse):
            index_service_module._INTERFACES = None
            job = self.service.start_upload_index("batch-slow")
            with self.assertRaises(RuntimeError):
                self.service.start_upload_index("batch-slow")
            canceller = self.service.cancel_job(str(job)) or {}
            self.assertEqual(canceller["status"], "cancelling")
            gate.set()
            finished = self._wait(str(job))
        self.assertEqual(finished["status"], "cancelled")
        self.assertEqual(self.service.generation, generation_before)
        self.assertEqual(len(self._docs()), 0)

    def test_upload_containment_and_symlinks(self):
        folder = self._write_batch("batch-evil", {})
        outside = self.root / "outside.txt"
        outside.write_text("secret outside content", encoding="utf-8")
        (folder / "0000_link.txt").symlink_to(outside)
        job = self.service.start_upload_index("batch-evil")
        self.assertEqual(self._wait(str(job))["status"], "completed")
        self.assertEqual(len(self._docs()), 0)

        self.store.create_upload_batch("batch-meta", "batch-meta")
        self.store.add_upload_file("batch-meta", "evil.txt", "../evil.txt", 1, "digest")
        job = self.service.start_upload_index("batch-meta")
        self.assertEqual(self._wait(str(job))["status"], "completed")
        self.assertEqual(len(self._docs()), 0)

    def test_crawl_disabled_and_ssrf_guard(self):
        with self.assertRaises(RuntimeError):
            self.service.start_crawl("https://example.com")
        enabled = replace(self.config, crawler_enabled=True)
        index_service_module._INTERFACES = None
        service = IndexService(enabled, self.store)
        service.initialize()
        with self.assertRaises(CrawlError):
            service.start_crawl("http://127.0.0.1:9/")
        self.assertIsNone(service.get_job(uuid.uuid4().hex))

    def test_search_delegates_to_snapshot(self):
        @dataclass
        class FakeSnapshot:
            calls: list = field(default_factory=list)

            @property
            def document_count(self):
                return 1

            def search(self, spec, options, query_vector=None):
                self.calls.append((spec, options, query_vector))
                return "sentinel"

        fake = FakeSnapshot()
        self.service._snapshot = fake
        spec = parse_query("alpha", self.config)
        options = SearchOptions()
        vector = (0.1, 0.2)
        self.assertEqual(self.service.search(spec, options, vector), "sentinel")
        self.assertEqual(fake.calls, [(spec, options, vector)])
        self.assertEqual(self.service.ready(), (True, None))

    def test_ready_before_initialization_and_missing_job(self):
        fresh = IndexService(self.config, IndexStore(self.config))
        self.assertEqual(fresh.ready(), (False, "index_not_initialized"))
        self.assertIsNone(fresh.get_job(uuid.uuid4().hex))
        self.assertIsNone(fresh.get_document(uuid.uuid4().hex))

    def test_upload_batch_lookup(self):
        self.store.create_upload_batch("batch-lookup", "batch-lookup")
        self.store.add_upload_file("batch-lookup", "a.txt", "0000_a.txt", 4, "hash")
        batch = self.service.upload_batch("batch-lookup") or {}
        self.assertEqual(batch["folder_name"], "batch-lookup")
        self.assertEqual(batch["files"][0]["blob_name"], "0000_a.txt")
        self.assertIsNone(self.service.upload_batch("unknown"))


if __name__ == "__main__":
    unittest.main()
