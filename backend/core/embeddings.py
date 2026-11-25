import hashlib
import importlib
import math
import os
import re

from config import load_config


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_DIMENSIONS = 384


def normalize(values) -> tuple[float, ...]:
    vector = [float(value) for value in values]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


class HashingEmbedder:
    name = "local-hashing-v1"

    @staticmethod
    def _vector(text: str) -> tuple[float, ...]:
        vector = [0.0] * _DIMENSIONS
        tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(str(text or ""))]
        if not tokens:
            return tuple(vector)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % _DIMENSIONS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return normalize(vector)

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._vector(text)

    def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._vector(text) for text in texts]


class FastEmbedEmbedder:
    def __init__(self, model_id: str, cache_dir):
        module = importlib.import_module("fastembed")
        self.name = f"fastembed:{model_id}"
        self.model = module.TextEmbedding(model_name=model_id, cache_dir=str(cache_dir))

    def embed_query(self, text: str) -> tuple[float, ...]:
        return normalize(next(self.model.query_embed([text])))

    def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [normalize(values) for values in self.model.passage_embed(texts)]


_PROVIDER = None


def model_name() -> str:
    return _provider().name


def embed_query(text: str) -> tuple[float, ...]:
    return _provider().embed_query(text)


def embed_documents(texts: list[str]) -> list[tuple[float, ...]]:
    return _provider().embed_documents(texts)


def embed_document(text: str) -> tuple[float, ...]:
    return embed_documents([text])[0]


def _provider():
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    config = load_config()
    model_id = os.getenv("EMBEDDING_MODEL", "")
    if model_id:
        try:
            _PROVIDER = FastEmbedEmbedder(model_id, config.model_dir)
        except ImportError as exc:
            raise RuntimeError("EMBEDDING_MODEL requires fastembed; install backend/requirements-ml.txt") from exc
        return _PROVIDER
    _PROVIDER = HashingEmbedder()
    return _PROVIDER
