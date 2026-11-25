import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from config import Config
from core.analysis import Analyzer
from core.file_parser import parse_file
from core.index_model import build_snapshot
from core.models import SnapshotData, StoredDocument
from core.tokenizer import Tokenizer
from utils.validation import QuerySpec, QueryTerm


BASE_CONFIG = Config(
    debug=False,
    host="127.0.0.1",
    port=5000,
    data_dir=Path("/tmp"),
    upload_dir=Path("/tmp"),
    db_path=Path("/tmp/index.db"),
    model_dir=Path("/tmp/models"),
    max_content_length=1024,
    max_file_size=1024,
    max_files=10,
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


def make_config(**overrides):
    return replace(BASE_CONFIG, **overrides)


def make_doc(doc_id, body="", title="", headings=(), filename=None, source_type="upload", file_type="text/plain", size=None):
    content = " ".join([title, *headings, body]).strip()
    return StoredDocument(
        doc_id=doc_id,
        generation=1,
        source_key=doc_id,
        filename=filename or f"{doc_id}.txt",
        source_type=source_type,
        source_url=None,
        title=title,
        headings=tuple(headings),
        body=body,
        content=content,
        content_hash=doc_id,
        byte_size=size if size is not None else len(content.encode("utf-8")),
        word_count=len(content.split()),
        indexed_at="2026-01-01T00:00:00+00:00",
        file_type=file_type,
    )


def make_snapshot(docs, config, generation=1, vectors=None):
    data = SnapshotData(
        generation=generation,
        documents={doc.doc_id: doc for doc in docs},
        vectors=vectors or {},
    )
    return build_snapshot(data, config)


def spec(raw, *words):
    return QuerySpec(raw=raw, terms=tuple(QueryTerm(word, word) for word in words))


class ParserTests(unittest.TestCase):
    def test_text_markdown_html_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.TXT").write_text("Hello world\nsecond line", encoding="utf-8")
            (root / "readme.MD").write_text("# Title\n## Section\nBody text", encoding="utf-8")
            (root / "page.HTML").write_text(
                "<html><head><title>Page Title</title></head><body>"
                "<h1>Heading One</h1><p>Hello &amp; welcome</p>"
                "<script>ignored words</script></body></html>",
                encoding="utf-8",
            )
            (root / "table.CSV").write_text("name,city\nAda,London", encoding="utf-8")

            text = parse_file(str(root / "note.TXT"))
            self.assertEqual(text.file_type, "text/plain")
            self.assertEqual(text.title, "Hello world")
            self.assertIn("second line", text.content)
            self.assertEqual(text.filename, "note.TXT")

            markdown = parse_file(str(root / "readme.MD"))
            self.assertEqual(markdown.file_type, "text/markdown")
            self.assertEqual(markdown.title, "Title")
            self.assertIn("Section", markdown.headings)

            page = parse_file(str(root / "page.HTML"), source_type="crawl", source_url="https://example.com")
            self.assertEqual(page.file_type, "text/html")
            self.assertEqual(page.title, "Page Title")
            self.assertEqual(page.headings, ("Heading One",))
            self.assertIn("Hello & welcome", page.body)
            self.assertNotIn("ignored words", page.body)
            self.assertEqual(page.source_type, "crawl")
            self.assertEqual(page.source_url, "https://example.com")

            table = parse_file(str(root / "table.CSV"))
            self.assertEqual(table.file_type, "text/csv")
            self.assertIn("Ada", table.content)

    def test_metadata_and_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cafe.txt"
            raw = "café naïve".encode("latin-1")
            path.write_bytes(raw)
            parsed = parse_file(str(path))
            self.assertEqual(parsed.byte_size, len(raw))
            self.assertIn("café", parsed.content)
            self.assertIn("naïve", parsed.content)
            self.assertEqual(parsed.word_count, 2)
            self.assertEqual(len(parsed.content_hash), 64)
            self.assertTrue(parsed.indexed_at.endswith("+00:00"))

    def test_unsupported_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.pdf"
            path.write_bytes(b"data")
            with self.assertRaises(ValueError):
                parse_file(str(path))
            with self.assertRaises(ValueError):
                parse_file(str(Path(directory) / "missing.txt"))


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.config = make_config()

    def test_positions_survive_stopword_removal(self):
        tokens = Analyzer(self.config, synonyms={}).analyze("the quick brown fox", "body")
        self.assertEqual(
            [(token.term, token.position, token.field) for token in tokens],
            [("quick", 1, "body"), ("brown", 2, "body"), ("fox", 3, "body")],
        )
        self.assertEqual(tokens[0].surface, "quick")

    def test_stemming_is_lightweight_and_stable(self):
        analyzer = Analyzer(self.config, synonyms={})
        for word in ("run", "runs", "running"):
            self.assertEqual(analyzer.canonical_terms(word), ("run",))
        self.assertEqual(analyzer.canonical_terms("stories"), ("story",))
        self.assertEqual(analyzer.canonical_terms("Café"), ("café",))

    def test_synonyms_loaded_without_downloads(self):
        analyzer = Analyzer(self.config)
        self.assertIn("automobile", [term for term, _ in analyzer.expand("car")[1:]])
        self.assertIn("car", [term for term, _ in analyzer.expand("automobile")[1:]])

    def test_tokenizer_wrapper(self):
        tokenizer = Tokenizer(self.config, synonyms={})
        self.assertEqual(tokenizer.tokenize("The running dogs"), ["run", "dog"])
        self.assertEqual(tokenizer.analyze("a big cat")[0].term, "big")


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.config = make_config()
        self.analyzer = Analyzer(self.config, synonyms={})

    def search(self, snapshot, spec_obj, **options):
        from core.models import SearchOptions

        return snapshot.search(spec_obj, SearchOptions(**options), self.analyzer)

    def test_bm25_formula(self):
        snapshot = make_snapshot(
            [make_doc("d1", "alpha alpha beta"), make_doc("d2", "alpha gamma")], self.config
        )
        raw = self.search(snapshot, spec("alpha", "alpha")).results
        by_id = {hit.doc_id: hit for hit in raw}
        idf = math.log(1.0 + (2 - 2 + 0.5) / (2 + 0.5))
        first = idf * (2 * 2.2) / (2 + 1.2 * (0.25 + 0.75 * 3 / 2.5))
        second = idf * (1 * 2.2) / (1 + 1.2 * (0.25 + 0.75 * 2 / 2.5))
        self.assertAlmostEqual(by_id["d1"].raw_score, first)
        self.assertAlmostEqual(by_id["d2"].raw_score, second)
        self.assertGreater(by_id["d1"].score, by_id["d2"].score)

    def test_field_boosts(self):
        snapshot = make_snapshot(
            [make_doc("title_doc", title="alpha"), make_doc("body_doc", body="alpha")], self.config
        )
        hits = {hit.doc_id: hit for hit in self.search(snapshot, spec("alpha", "alpha")).results}
        self.assertGreater(hits["title_doc"].raw_score, hits["body_doc"].raw_score)
        self.assertAlmostEqual(
            hits["title_doc"].raw_score / hits["body_doc"].raw_score, 3.0, places=5
        )

    def test_phrase_cannot_cross_fields_or_gaps(self):
        snapshot = make_snapshot(
            [
                make_doc("exact", body="quick brown fox jumps"),
                make_doc("gap", body="quick red brown fox"),
                make_doc("split", title="quick", body="brown fox"),
            ],
            self.config,
        )
        query = QuerySpec(raw='"quick brown"', phrases=(("quick", "brown"),))
        page = self.search(snapshot, query)
        self.assertEqual([hit.doc_id for hit in page.results], ["exact"])

    def test_deterministic_ties(self):
        snapshot = make_snapshot(
            [make_doc("b", "alpha"), make_doc("a", "alpha")], self.config
        )
        hits = self.search(snapshot, spec("alpha", "alpha"))
        self.assertEqual([hit.doc_id for hit in hits.results], ["a", "b"])

    def test_threshold_uses_normalized_score(self):
        snapshot = make_snapshot(
            [make_doc("high", "alpha alpha alpha alpha"), make_doc("low", "alpha beta beta beta")],
            self.config,
        )
        loose = self.search(snapshot, spec("alpha", "alpha"))
        strict = self.search(snapshot, spec("alpha", "alpha"), threshold=0.9)
        self.assertEqual(loose.total_results, 2)
        self.assertEqual(strict.total_results, 1)
        self.assertEqual(strict.results[0].doc_id, "high")
        self.assertAlmostEqual(loose.results[0].score, 1.0)

    def test_filters_pagination_facets_and_sort(self):
        snapshot = make_snapshot(
            [
                make_doc("d1", "alpha", filename="z.txt", source_type="upload", file_type="text/plain"),
                make_doc("d2", "alpha", filename="a.html", source_type="upload", file_type="text/html"),
                make_doc("d3", "alpha", filename="m.txt", source_type="crawl", file_type="text/plain"),
            ],
            self.config,
        )
        page = self.search(snapshot, spec("alpha", "alpha"))
        self.assertEqual(page.facets["source_type"], {"upload": 2, "crawl": 1})
        self.assertEqual(page.facets["file_type"], {"text/plain": 2, "text/html": 1})

        filtered = self.search(snapshot, spec("alpha", "alpha"), source_type="upload")
        self.assertEqual(filtered.total_results, 2)
        self.assertEqual([hit.doc_id for hit in filtered.results], ["d1", "d2"])

        paged = self.search(snapshot, spec("alpha", "alpha"), limit=1, offset=1)
        self.assertEqual(paged.total_results, 3)
        self.assertEqual(len(paged.results), 1)

        by_name = self.search(snapshot, spec("alpha", "alpha"), sort="filename")
        self.assertEqual([hit.filename for hit in by_name.results], ["a.html", "m.txt", "z.txt"])

    def test_explanation_and_match_counts(self):
        snapshot = make_snapshot([make_doc("d1", " ".join(["alpha"] * 30))], self.config)
        hit = self.search(snapshot, spec("alpha", "alpha")).results[0]
        self.assertAlmostEqual(sum(hit.explanation.values()), hit.raw_score)
        self.assertGreaterEqual(hit.total_matches, 30)
        self.assertLessEqual(len(hit.matched_positions), 20)
        self.assertTrue(hit.snippet)

    def test_empty_query(self):
        snapshot = make_snapshot([make_doc("d1", "alpha")], self.config)
        page = self.search(snapshot, QuerySpec(raw=""))
        self.assertEqual(page.total_results, 0)
        self.assertEqual(page.results, ())


if __name__ == "__main__":
    unittest.main()
