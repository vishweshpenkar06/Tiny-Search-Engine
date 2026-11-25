import hashlib
import importlib
import math
import os
import re

from config import load_config


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_DIMENSIONS = 384


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
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(value / norm for value in vector)

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._vector(text)

    def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._vector(text) for text in texts]


class FastEmbedEmbedder:
    def __init__(self, model: str, cache_dir):
        module = importlib.import_module("fastembed")
        self.name = f"fastembed:{model}"
        self.model = module.TextEmbedding(model_name=model, cache_dir=str(cache_dir))

    @staticmethod
    def _normalize(values) -> tuple[float, ...]:
        vector = [float(value) for value in values]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(value / norm for value in vector)

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._normalize(next(self.model.query_embed([text])))

    def embed_documents(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._normalize(values) for values in self.model.passage_embed(texts)]


_PROVIDER = None


def model_name() -> str:
    return _provider().name


def embed_query(text: str) -> tuple[float, ...]:
    return _provider().embed_query(text)


def embed_documents(texts: list[str]) -> list[tuple[float, ...]]:
    return _provider().embed_documents(texts)


def embed_document(text: str) -> tuple[float, ...]:
    return embed_query(text)


def _provider():
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    config = load_config()
    model = os.getenv("EMBEDDING_MODEL", "")
    if model:
        try:
            _PROVIDER = FastEmbedEmbedder(model, config.model_dir)
            return _PROVIDER
        except Exception:
            pass
    _PROVIDER = HashingEmbedder()
    return _PROVIDER
