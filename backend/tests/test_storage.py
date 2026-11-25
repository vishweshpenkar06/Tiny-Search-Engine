import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from config import Config
from core.index_store import IndexStore
from core.models import ParsedDocument


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


def make_parsed(
    source_key: str, text: str, filename: str = "doc.txt", source_type: str = "upload"
) -> ParsedDocument:
    return ParsedDocument(
        source_key=source_key,
        filename=filename,
        source_type=source_type,
        source_url=None,
        title="Alpha title",
        headings=("Heading One",),
        body=text,
        content=text,
        content_hash=source_key,
        byte_size=len(text.encode("utf-8")),
        word_count=len(text.split()),
        indexed_at="2026-01-01T00:00:00+00:00",
        file_type="text/plain",
    )


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "uploads").mkdir()
        self.config = make_config(self.root)
        self.store = IndexStore(self.config)
        self.generation = self.store.initialize()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_initialize_creates_schema_and_active_generation(self):
        names = {
            row[0]
            for row in self.store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for table in (
            "schema_meta",
            "generations",
            "documents",
            "vectors",
            "jobs",
            "upload_batches",
            "upload_files",
        ):
            self.assertIn(table, names)
        self.assertEqual(self.store._conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.store._conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.store.active_generation(), self.generation)
        self.assertEqual(self.store.initialize(), self.generation)

    def test_stable_document_ids(self):
        first = self.store.insert_document(self.generation, make_parsed("key-one", "alpha"))
        second_gen = self.store.create_generation(self.generation, "upload")
        again = self.store.insert_document(second_gen, make_parsed("key-one", "alpha changed"))
        other = self.store.insert_document(second_gen, make_parsed("key-two", "alpha"))
        other_type = self.store.insert_document(
            second_gen, make_parsed("key-one", "alpha", source_type="web")
        )
        self.assertEqual(first.doc_id, again.doc_id)
        self.assertNotEqual(first.doc_id, other.doc_id)
        self.assertNotEqual(first.doc_id, other_type.doc_id)
        self.assertEqual(len(first.doc_id.split("-")), 5)
        self.assertNotIn(str(self.root), first.doc_id)

    def test_atomic_publication_switches_active_pointer(self):
        self.store.insert_document(self.generation, make_parsed("old", "old content"))
        staged = self.store.create_generation(self.generation, "upload")
        self.store.insert_document(staged, make_parsed("new", "new content"))
        self.assertEqual(self.store.active_generation(), self.generation)
        self.store.publish_generation(staged, "v1", "bm25")
        self.assertEqual(self.store.active_generation(), staged)
        self.assertEqual(self.store.load_snapshot_data(staged).document_count, 1)
        self.assertEqual(self.store.load_snapshot_data(self.generation).document_count, 1)
        self.assertEqual(
            self.store._conn.execute("SELECT status FROM generations WHERE id=?", (self.generation,)).fetchone()[0],
            "retired",
        )
        with self.assertRaises(ValueError):
            self.store.publish_generation(9999, "v1", "bm25")
        with self.assertRaises(ValueError):
            self.store.insert_document(self.generation, make_parsed("late", "too late"))

    def test_discard_generation_removes_staged_documents(self):
        staged = self.store.create_generation(self.generation, "crawl")
        self.store.insert_document(staged, make_parsed("staged", "staged content"))
        self.store.discard_generation(staged)
        self.assertEqual(self.store.load_snapshot_data(staged).document_count, 0)
        with self.assertRaises(ValueError):
            self.store.discard_generation(self.generation)

    def test_copy_generation_preserves_documents_and_vectors(self):
        document = self.store.insert_document(self.generation, make_parsed("copied", "alpha beta"))
        self.store.insert_vector(self.generation, document.doc_id, "local-v1", (0.1, 0.2))
        copied = self.store.copy_generation(self.generation, "crawl")
        data = self.store.load_snapshot_data(copied)
        self.assertEqual(set(data.documents), {document.doc_id})
        self.assertEqual(data.vectors[document.doc_id], (0.1, 0.2))
        self.assertEqual(data.vector_model, "local-v1")

    def test_job_claim_and_interrupted_recovery(self):
        job = self.store.create_job("upload", {"upload_id": "abc"})
        self.store.update_job(job["job_id"], status="running", progress=0.5)
        interrupted = [item["job_id"] for item in self.store.interrupted_jobs()]
        self.assertIn(job["job_id"], interrupted)
        running = self.store.find_running_job()
        self.assertIsNotNone(running)
        self.assertEqual((running or {})["job_id"], job["job_id"])
        self.assertIsNone(self.store.claim_job("upload", {}))
        self.store.update_job(job["job_id"], status="completed", finished_at="now")
        self.assertEqual(self.store.interrupted_jobs(), [])
        claimed = self.store.claim_job("crawl", {"url": "https://example.test"}) or {}
        self.assertEqual(claimed["status"], "queued")
        self.assertEqual(claimed["kind"], "crawl")
        self.assertEqual(claimed["generation"], self.generation)

    def test_upload_batch_metadata_and_containment(self):
        self.store.create_upload_batch("batch-1", "batch-1")
        self.store.add_upload_file("batch-1", "one.txt", "0000_one.txt", 12, "digest")
        batch = self.store.get_upload_batch("batch-1")
        self.assertEqual(batch["folder_path"], str(self.config.upload_dir / "batch-1"))
        self.assertEqual(batch["files"][0]["filename"], "one.txt")
        with self.assertRaises(ValueError):
            self.store.create_upload_batch("bad-1", "../escape")
        with self.assertRaises(ValueError):
            self.store.create_upload_batch("bad-2", str(self.root / "absolute"))
        with self.assertRaises(ValueError):
            self.store.add_upload_file("missing", "a.txt", "a.txt", 1, "x")
        with self.assertRaises(ValueError):
            self.store.get_upload_batch("missing")

    def test_snapshot_data_consistency(self):
        one = self.store.insert_document(self.generation, make_parsed("alpha-key", "alpha beta alpha"))
        two = self.store.insert_document(self.generation, make_parsed("beta-key", "beta gamma"))
        self.store.insert_vector(self.generation, one.doc_id, "model-v1", (1.0, 0.0, 0.5))
        data = self.store.load_snapshot_data(self.generation)
        self.assertEqual(data.generation, self.generation)
        self.assertEqual(set(data.documents), {one.doc_id, two.doc_id})
        self.assertEqual(data.vector_model, "model-v1")
        self.assertEqual(data.vectors[one.doc_id], (1.0, 0.0, 0.5))
        self.assertTrue(data.postings)
        for (term, field), postings in data.postings.items():
            self.assertIn(field, ("title", "headings", "body"))
            self.assertTrue(term)
            for doc_id, posting in postings.items():
                self.assertIn(doc_id, data.documents)
                self.assertEqual(posting.tf, len(posting.positions))
        self.assertEqual(set(data.field_lengths), {one.doc_id, two.doc_id})
        for doc_id, lengths in data.field_lengths.items():
            self.assertGreater(sum(lengths.values()), 0)
            self.assertEqual(doc_id, data.documents[doc_id].doc_id)

    def test_snapshot_data_uses_configured_analyzer(self):
        from core.analysis import Analyzer

        self.store.set_analyzer(Analyzer(self.config))
        document = self.store.insert_document(
            self.generation, make_parsed("stem-key", "running runner jumps")
        )
        data = self.store.load_snapshot_data(self.generation)
        self.assertTrue(any(term == "run" for term, _ in data.postings))
        self.assertIn(document.doc_id, data.field_lengths)


if __name__ == "__main__":
    unittest.main()
