from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedDocument:
    source_key: str
    filename: str
    source_type: str
    source_url: str | None
    title: str
    headings: tuple[str, ...]
    body: str
    content: str
    content_hash: str
    byte_size: int
    word_count: int
    indexed_at: str
    file_type: str


@dataclass(frozen=True)
class StoredDocument:
    doc_id: str
    generation: int
    source_key: str
    filename: str
    source_type: str
    source_url: str | None
    title: str
    headings: tuple[str, ...]
    body: str
    content: str
    content_hash: str
    byte_size: int
    word_count: int
    indexed_at: str
    file_type: str


@dataclass(frozen=True)
class Posting:
    tf: int
    positions: tuple[int, ...]


@dataclass(frozen=True)
class AnalyzedToken:
    term: str
    surface: str
    position: int
    field: str


@dataclass(frozen=True)
class SnapshotData:
    generation: int
    documents: dict[str, StoredDocument] = field(default_factory=dict)
    postings: dict[tuple[str, str], dict[str, Posting]] = field(default_factory=dict)
    field_lengths: dict[str, dict[str, int]] = field(default_factory=dict)
    vectors: dict[str, tuple[float, ...]] = field(default_factory=dict)
    vector_model: str | None = None

    @property
    def document_count(self) -> int:
        return len(self.documents)


@dataclass(frozen=True)
class SearchOptions:
    ranking: str = "bm25"
    mode: str = "lexical"
    fuzzy: bool = False
    threshold: float = 0.0
    limit: int = 10
    offset: int = 0
    sort: str = "relevance"
    source_type: str | None = None
    file_type: str | None = None


@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    filename: str
    source_type: str
    source_url: str | None
    score: float
    raw_score: float
    snippet: str
    word_count: int
    file_size_bytes: int
    indexed_at: str
    total_matches: int
    matched_positions: tuple[int, ...]
    explanation: dict[str, Any]


@dataclass(frozen=True)
class SearchPage:
    query: str
    ranking: str
    mode: str
    generation: int
    total_results: int
    results: tuple[SearchHit, ...]
    correction: str | None
    facets: dict[str, dict[str, int]]
    elapsed_ms: float
