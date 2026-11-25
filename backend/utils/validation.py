import re
from dataclasses import dataclass, field

from config import Config


@dataclass(frozen=True)
class QueryTerm:
    raw: str
    term: str
    weight: float = 1.0
    expanded: bool = False


@dataclass(frozen=True)
class QuerySpec:
    raw: str
    terms: tuple[QueryTerm, ...] = field(default_factory=tuple)
    phrases: tuple[tuple[str, ...], ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.terms and not self.phrases


_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PHRASE_RE = re.compile(r'"([^"]+)"')
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def sanitize_query(value: object, config: Config) -> str:
    if not isinstance(value, str):
        raise ValueError("Query must be a string")
    text = _TAG_RE.sub(" ", value)
    text = _CONTROL_RE.sub(" ", text).strip()
    if not text:
        raise ValueError("Query cannot be empty")
    if len(text) > config.max_query_length:
        raise ValueError(f"Query is too long (maximum {config.max_query_length} characters)")
    return text


def parse_query(value: object, config: Config) -> QuerySpec:
    text = sanitize_query(value, config)
    phrases: list[tuple[str, ...]] = []
    remainder = _PHRASE_RE.sub(" ", text)
    for match in _PHRASE_RE.finditer(text):
        words = tuple(word.lower() for word in _WORD_RE.findall(match.group(1)))
        if words:
            phrases.append(words)
    terms = tuple(
        QueryTerm(raw=match.group(0), term=match.group(0).lower())
        for match in _WORD_RE.finditer(remainder)
    )
    return QuerySpec(raw=text, terms=terms, phrases=tuple(phrases))


def validate_file_upload(filename: object, size: int, config: Config) -> tuple[bool, str]:
    if not isinstance(filename, str) or not filename.strip():
        return False, "No filename provided"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {".txt", ".md", ".html", ".htm", ".csv"}
    if extension not in allowed:
        return False, f"Unsupported file type. Allowed types: {', '.join(sorted(allowed))}"
    if size <= 0:
        return False, "File is empty"
    if size > config.max_file_size:
        return False, f"File too large. Maximum size is {config.max_file_size} bytes"
    return True, ""


def validate_pagination(limit: object, offset: object, maximum: int = 100) -> tuple[int, int]:
    if isinstance(limit, bool) or isinstance(offset, bool) or not isinstance(limit, (int, str)) or not isinstance(offset, (int, str)):
        raise ValueError("limit and offset must be integers")
    try:
        result_limit = int(limit)
        result_offset = int(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit and offset must be integers") from exc
    if not 1 <= result_limit <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    if result_offset < 0:
        raise ValueError("offset must be non-negative")
    return result_limit, result_offset


def validate_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("threshold must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("threshold must be a number") from exc
    if not 0.0 <= result <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    return result
