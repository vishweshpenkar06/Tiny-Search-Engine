import importlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from core.models import AnalyzedToken, StoredDocument


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_VOWELS = frozenset("aeiouy")

_STOP_WORDS = frozenset(
    """a about above after again against all am an and any are aren't as at be because been
    before being below between both but by can't cannot could couldn't did didn't do does
    doesn't doing don't down during each few for from further had hadn't has hasn't have
    haven't having he he'd he'll he's her here here's hers herself him himself his how
    how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most
    mustn't my myself no nor not of off on once only or other ought our ours ourselves out
    over own same shan't she she'd she'll she's should shouldn't so some such than that
    that's the their theirs them themselves then there there's these they they'd they'll
    they're they've this those through to too under until up very was wasn't we we'd we'll
    we're we've were weren't what what's when when's where where's which while who who's
    whom why why's with won't would wouldn't you you'd you'll you're you've your yours
    yourself yourselves""".split()
)

STOP_WORDS = _STOP_WORDS

_FIELD_BOOSTS = {"title": 3.0, "headings": 2.0, "body": 1.0}
_FIELDS = ("title", "headings", "body")

_DEFAULT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "car": ("automobile", "vehicle"),
    "automobile": ("car", "vehicle"),
    "fast": ("quick", "rapid", "speedy"),
    "big": ("large", "huge"),
}


def field_boost(field: str) -> float:
    return _FIELD_BOOSTS.get(field, 1.0)


def search_fields() -> tuple[str, ...]:
    return _FIELDS


try:
    _SNOWBALL = importlib.import_module("snowballstemmer").stemmer("english")
except ImportError:
    _SNOWBALL = None


def stem(word: str) -> str:
    value = word.lower()
    if _SNOWBALL is not None:
        return _SNOWBALL.stemWord(value)
    if len(value) > 4 and value.endswith("ies"):
        value = value[:-3] + "y"
    elif len(value) > 5 and value.endswith("ing") and any(c in _VOWELS for c in value[:-3]):
        value = value[:-3]
    elif len(value) > 4 and value.endswith("ed") and any(c in _VOWELS for c in value[:-2]):
        value = value[:-2]
    elif len(value) > 4 and value.endswith("ly") and any(c in _VOWELS for c in value[:-2]):
        value = value[:-2]
    elif len(value) > 5 and value.endswith("ness"):
        value = value[:-4]
    elif len(value) > 4 and value.endswith("es") and any(c in _VOWELS for c in value[:-2]):
        value = value[:-2]
    elif len(value) > 3 and value.endswith("s") and not value.endswith(("ss", "us", "is")):
        value = value[:-1]
    if len(value) > 3 and value[-1] == value[-2] and value[-1] not in "lsz":
        value = value[:-1]
    return value


class Analyzer:
    def __init__(self, config: Any = None, synonyms: Any = None) -> None:
        self.config = config
        self.k1 = float(getattr(config, "bm25_k1", 1.2))
        self.b = float(getattr(config, "bm25_b", 0.75))
        self.synonyms = self._load_synonyms(synonyms)

    @staticmethod
    def _load_synonyms(source: Any) -> dict[str, tuple[str, ...]]:
        if source is None:
            source = Path(__file__).with_name("synonyms.json")
        if isinstance(source, (str, Path)):
            try:
                raw = json.loads(Path(source).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = _DEFAULT_SYNONYMS
        elif isinstance(source, Mapping):
            raw = source
        else:
            raw = _DEFAULT_SYNONYMS
        result: dict[str, set[str]] = {}
        for key, values in raw.items():
            canonical = stem(str(key))
            bucket = result.setdefault(canonical, set())
            if isinstance(values, str):
                values = (values,)
            for value in values or ():
                bucket.add(stem(str(value)))
            bucket.discard(canonical)
        for key, values in list(result.items()):
            for value in values:
                result.setdefault(value, set()).add(key)
        return {key: tuple(sorted(values)) for key, values in result.items()}

    def analyze(self, text: Any, field: str = "body") -> tuple[AnalyzedToken, ...]:
        if isinstance(text, StoredDocument):
            result: list[AnalyzedToken] = []
            for name in _FIELDS:
                result.extend(self.analyze(getattr(text, name, ""), name))
            return tuple(result)
        tokens: list[AnalyzedToken] = []
        if text is None:
            return ()
        if isinstance(text, (list, tuple)):
            text = " ".join(str(part) for part in text)
        for position, match in enumerate(_TOKEN_RE.finditer(str(text))):
            surface = match.group(0).lower()
            if surface in _STOP_WORDS:
                continue
            tokens.append(AnalyzedToken(stem(surface), surface, position, field))
        return tuple(tokens)

    def canonical_terms(self, text: Any) -> tuple[str, ...]:
        return tuple(token.term for token in self.analyze(text, "body"))

    def expand(self, term: str) -> tuple[tuple[str, float], ...]:
        canonical = stem(term)
        result: list[tuple[str, float]] = [(canonical, 1.0)]
        for synonym in self.synonyms.get(canonical, ()):
            if synonym != canonical:
                result.append((synonym, 0.5))
        return tuple(result)
