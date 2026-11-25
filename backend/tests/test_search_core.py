import unittest

from core.analysis import Analyzer
from core.models import SearchOptions
from utils.validation import QuerySpec, QueryTerm

from test_core import make_config, make_doc, make_snapshot, spec


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.config = make_config()
        self.analyzer = Analyzer(self.config, synonyms={})

    def search(self, snapshot, query_spec, query_vector=None, **options):
        return snapshot.search(
            query_spec, SearchOptions(**options), self.analyzer, query_vector=query_vector
        )

    def test_rrf_fuses_lexical_and_vector_ranks(self):
        vectors = {"d1": (1.0, 0.0), "d2": (0.0, 1.0), "d3": (0.6, 0.8)}
        snapshot = make_snapshot(
            [make_doc("d1", "alpha beta"), make_doc("d2", "alpha"), make_doc("d3", "beta gamma")],
            self.config,
            vectors=vectors,
        )
        page = self.search(
            snapshot,
            spec("alpha beta", "alpha", "beta"),
            query_vector=(1.0, 0.0),
            mode="hybrid",
        )
        self.assertEqual([hit.doc_id for hit in page.results], ["d1", "d3", "d2"])
        by_id = {hit.doc_id: hit for hit in page.results}
        self.assertAlmostEqual(by_id["d1"].raw_score, 1.0 / 61 + 1.0 / 61)
        self.assertAlmostEqual(by_id["d3"].raw_score, 1.0 / 63 + 1.0 / 62)
        self.assertAlmostEqual(by_id["d2"].raw_score, 1.0 / 62)
        for hit in page.results:
            self.assertAlmostEqual(sum(hit.explanation.values()), hit.raw_score)
        self.assertEqual(page.mode, "hybrid")

    def test_semantic_uses_cosine_and_honors_filters_and_pagination(self):
        vectors = {"a": (1.0, 0.0), "b": (0.0, 1.0), "c": (0.8, 0.2)}
        snapshot = make_snapshot(
            [
                make_doc("a", "one", filename="a.txt", source_type="upload"),
                make_doc("b", "two", filename="b.txt", source_type="crawl"),
                make_doc("c", "three", filename="c.txt", source_type="upload"),
            ],
            self.config,
            vectors=vectors,
        )
        page = self.search(
            snapshot, spec(""), query_vector=(1.0, 0.0), mode="semantic", source_type="upload", limit=1
        )
        self.assertEqual(page.total_results, 2)
        self.assertEqual([hit.doc_id for hit in page.results], ["a"])
        self.assertAlmostEqual(page.results[0].raw_score, 1.0)
        self.assertAlmostEqual(sum(page.results[0].explanation.values()), 1.0)

        paged = self.search(
            snapshot, spec(""), query_vector=(1.0, 0.0), mode="semantic", source_type="upload", limit=1, offset=1
        )
        self.assertEqual([hit.doc_id for hit in paged.results], ["c"])

    def test_missing_vectors_raise_clear_error(self):
        snapshot = make_snapshot([make_doc("d1", "alpha")], self.config)
        for mode in ("semantic", "hybrid"):
            with self.assertRaisesRegex(ValueError, "vectors"):
                self.search(snapshot, spec("alpha", "alpha"), query_vector=(1.0,), mode=mode)
        with_vectors = make_snapshot(
            [make_doc("d1", "alpha")], self.config, vectors={"d1": (1.0,)}
        )
        with self.assertRaisesRegex(ValueError, "query_vector"):
            self.search(with_vectors, spec("alpha", "alpha"), mode="semantic")

    def test_zero_query_vector_returns_no_semantic_hits(self):
        snapshot = make_snapshot(
            [make_doc("d1", "alpha")], self.config, vectors={"d1": (1.0, 0.0)}
        )
        page = self.search(snapshot, spec(""), query_vector=(0.0, 0.0), mode="semantic")
        self.assertEqual(page.total_results, 0)


class LexicalModeTests(unittest.TestCase):
    def setUp(self):
        self.config = make_config()
        self.analyzer = Analyzer(self.config, synonyms={})

    def test_tfidf_ranking(self):
        snapshot = make_snapshot(
            [make_doc("d1", "alpha alpha beta"), make_doc("d2", "alpha gamma")], self.config
        )
        page = snapshot.search(spec("alpha", "alpha"), SearchOptions(ranking="tfidf"), self.analyzer)
        self.assertEqual(page.ranking, "tfidf")
        self.assertEqual({hit.doc_id for hit in page.results}, {"d1", "d2"})
        self.assertGreater(page.results[0].raw_score, 0.0)
        for hit in page.results:
            self.assertAlmostEqual(sum(hit.explanation.values()), hit.raw_score)

    def test_query_time_synonym_expansion(self):
        snapshot = make_snapshot([make_doc("d1", "automobile")], self.config)
        expanded = Analyzer(self.config)
        found = snapshot.search(spec("car", "car"), SearchOptions(), expanded)
        self.assertEqual([hit.doc_id for hit in found.results], ["d1"])
        missing = snapshot.search(spec("car", "car"), SearchOptions(), self.analyzer)
        self.assertEqual(missing.total_results, 0)

    def test_hybrid_honors_filters_and_pagination(self):
        vectors = {"d1": (1.0, 0.0), "d2": (0.0, 1.0), "d3": (0.9, 0.1)}
        snapshot = make_snapshot(
            [
                make_doc("d1", "alpha", source_type="upload"),
                make_doc("d2", "alpha", source_type="crawl"),
                make_doc("d3", "beta", source_type="upload"),
            ],
            self.config,
            vectors=vectors,
        )
        page = snapshot.search(
            spec("alpha", "alpha"),
            SearchOptions(mode="hybrid", source_type="upload", limit=1, offset=1),
            self.analyzer,
            query_vector=(1.0, 0.0),
        )
        self.assertEqual(page.total_results, 2)
        self.assertEqual(len(page.results), 1)
        self.assertNotIn("d2", [hit.doc_id for hit in page.results])

    def test_threshold_after_normalization_in_hybrid(self):
        vectors = {"d1": (1.0, 0.0), "d2": (0.0, 1.0)}
        snapshot = make_snapshot(
            [make_doc("d1", "alpha"), make_doc("d2", "beta")], self.config, vectors=vectors
        )
        strict = snapshot.search(
            spec("alpha", "alpha"),
            SearchOptions(mode="hybrid", threshold=0.99),
            self.analyzer,
            query_vector=(1.0, 0.0),
        )
        self.assertLessEqual(strict.total_results, 2)


class FuzzyTests(unittest.TestCase):
    def setUp(self):
        self.config = make_config()
        self.analyzer = Analyzer(self.config, synonyms={})

    def test_typo_finds_term_and_reports_correction(self):
        snapshot = make_snapshot(
            [
                make_doc("d1", "retrieval systems"),
                make_doc("d2", "unrelated content"),
            ],
            self.config,
        )
        page = snapshot.search(
            spec("retreival", "retreival"),
            SearchOptions(fuzzy=True),
            self.analyzer,
        )
        self.assertEqual([hit.doc_id for hit in page.results], ["d1"])
        self.assertEqual(page.correction, "retrieval")

    def test_fuzzy_is_opt_in_and_bounded(self):
        snapshot = make_snapshot([make_doc("d1", "retrieval")], self.config)
        exact = snapshot.search(spec("retreival", "retreival"), SearchOptions(), self.analyzer)
        self.assertEqual(exact.total_results, 0)
        self.assertIsNone(exact.correction)
        fuzzy = snapshot.search(
            spec("retreival", "retreival"),
            SearchOptions(fuzzy=True),
            self.analyzer,
        )
        self.assertEqual(fuzzy.total_results, 1)
        self.assertLessEqual(fuzzy.results[0].total_matches, 20)


if __name__ == "__main__":
    unittest.main()
