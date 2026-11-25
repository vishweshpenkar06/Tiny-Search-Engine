import math
import unittest
from unittest.mock import patch

from core import embeddings
from core.embeddings import HashingEmbedder, embed_documents, embed_query, model_name


class EmbeddingTests(unittest.TestCase):
    def test_hashing_embedder_is_deterministic_and_normalized(self):
        embedder = HashingEmbedder()
        left = embedder.embed_query("machine learning retrieval")
        right = embedder.embed_query("machine learning retrieval")
        self.assertEqual(left, right)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in left)), 1.0, places=6)
        self.assertNotEqual(left, embedder.embed_query("unrelated document"))

    def test_document_and_query_vectors_use_same_space(self):
        vectors = embed_documents(["machine learning retrieval systems"])
        query = embed_query("machine learning retrieval")
        self.assertEqual(len(vectors), 1)
        self.assertEqual(len(vectors[0]), len(query))
        self.assertGreater(sum(a * b for a, b in zip(vectors[0], query)), 0.0)

    def test_embed_document_uses_passage_path(self):
        class PassageOnlyProvider:
            name = "passage-only"

            def embed_query(self, text):
                raise AssertionError("documents must not use query encoding")

            def embed_documents(self, texts):
                return [tuple(float(index == 0) for index in range(2)) for _ in texts]

        with patch.object(embeddings, "_PROVIDER", PassageOnlyProvider()):
            self.assertEqual(embeddings.embed_document("document text"), (1.0, 0.0))

    def test_default_provider_name(self):
        self.assertTrue(model_name())


if __name__ == "__main__":
    unittest.main()
