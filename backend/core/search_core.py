import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass

from core.analysis import Analyzer, field_boost, search_fields, stem
from core.models import (
    Posting,
    SearchHit,
    SearchOptions,
    SearchPage,
    SnapshotData,
    StoredDocument,
)


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_MAX_POSITIONS = 20
_SNIPPET_TOKENS = 48
_PHRASE_BONUS = 3.0


@dataclass(frozen=True)
class _QueryTerm:
    term: str
    weight: float
    expanded: bool


def _field_length(data: SnapshotData, doc_id: str, field: str) -> int:
    lengths = data.field_lengths.get(doc_id)
    if lengths is None:
        lengths = data.field_lengths.get(field, {})
        return int(lengths.get(doc_id, 0))
    return int(lengths.get(field, 0))


def _average_field_length(data: SnapshotData, field: str) -> float:
    count = len(data.documents)
    if count == 0:
        return 1.0
    total = sum(_field_length(data, doc_id, field) for doc_id in data.documents)
    return total / count or 1.0


def build_postings(data: SnapshotData, analyzer: Analyzer) -> SnapshotData:
    data.postings.clear()
    data.field_lengths.clear()
    counts: dict[tuple[str, str], dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for doc_id, document in data.documents.items():
        lengths: dict[str, int] = {}
        for field in search_fields():
            tokens = analyzer.analyze(getattr(document, field, ""), field)
            lengths[field] = len(tokens)
            for token in tokens:
                counts[(token.term, field)][doc_id].append(token.position)
        data.field_lengths[doc_id] = lengths
    for key, per_doc in counts.items():
        data.postings[key] = {
            doc_id: Posting(tf=len(positions), positions=tuple(sorted(positions)))
            for doc_id, positions in per_doc.items()
        }
    return data


def _query_terms(query_spec, analyzer: Analyzer) -> tuple[_QueryTerm, ...]:
    result: list[_QueryTerm] = []
    for item in getattr(query_spec, "terms", ()):
        raw = getattr(item, "raw", None) or getattr(item, "term", "")
        weight = float(getattr(item, "weight", 1.0))
        canonical = analyzer.canonical_terms(raw)
        if not canonical:
            canonical = (stem(str(raw).lower()),)
        seen: set[str] = set()
        for term in canonical:
            for expanded_term, expansion_weight in analyzer.expand(term):
                if expanded_term in seen:
                    continue
                seen.add(expanded_term)
                result.append(
                    _QueryTerm(expanded_term, weight * expansion_weight, expansion_weight < 1.0)
                )
    return tuple(result)


def _query_phrases(query_spec, analyzer: Analyzer) -> tuple[tuple[str, ...], ...]:
    phrases: list[tuple[str, ...]] = []
    for phrase in getattr(query_spec, "phrases", ()):
        terms: list[str] = []
        for word in phrase:
            canonical = analyzer.canonical_terms(word)
            terms.append(canonical[0] if canonical else str(word).lower())
        if terms:
            phrases.append(tuple(terms))
    return tuple(phrases)


def _add_match(
    matched: dict[str, set[int]],
    totals: dict[str, int],
    snippet_positions: dict[str, int],
    doc_id: str,
    positions,
    field: str,
) -> None:
    values = tuple(positions)
    matched.setdefault(doc_id, set()).update(values)
    totals[doc_id] = totals.get(doc_id, 0) + len(values)
    if field == "body" and doc_id not in snippet_positions and values:
        snippet_positions[doc_id] = values[0]


def _lexical_scores(
    data: SnapshotData,
    config,
    analyzer: Analyzer,
    terms: tuple[_QueryTerm, ...],
    phrases: tuple[tuple[str, ...], ...],
    ranking: str,
) -> tuple[dict[str, float], dict[str, dict[str, float]], dict[str, set[int]], dict[str, int], dict[str, int]]:
    scores: dict[str, float] = defaultdict(float)
    components: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    matched: dict[str, set[int]] = {}
    totals: dict[str, int] = {}
    snippet_positions: dict[str, int] = {}
    total_docs = len(data.documents)
    k1 = float(getattr(config, "bm25_k1", 1.2))
    b = float(getattr(config, "bm25_b", 0.75))

    for item in terms:
        for field in search_fields():
            posting_map = data.postings.get((item.term, field))
            if not posting_map:
                continue
            df = len(posting_map)
            avgdl = _average_field_length(data, field)
            for doc_id, posting in posting_map.items():
                tf = posting.tf
                dl = _field_length(data, doc_id, field)
                if ranking == "bm25":
                    idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
                    normalizer = tf + k1 * (1.0 - b + b * dl / avgdl)
                    contribution = idf * (tf * (k1 + 1.0)) / normalizer if normalizer else 0.0
                else:
                    idf = math.log((total_docs + 1) / (df + 1)) + 1.0
                    contribution = (tf / dl if dl else 0.0) * idf
                contribution *= field_boost(field) * item.weight
                if contribution <= 0.0:
                    continue
                scores[doc_id] += contribution
                components[doc_id][field] += contribution
                _add_match(matched, totals, snippet_positions, doc_id, posting.positions, field)

    for phrase in phrases:
        for field in search_fields():
            first = data.postings.get((phrase[0], field), {})
            rest = [
                data.postings.get((term, field), {}) for term in phrase[1:]
            ]
            for doc_id, posting in first.items():
                position_sets = []
                valid = True
                for mapping in rest:
                    target = mapping.get(doc_id)
                    if target is None:
                        valid = False
                        break
                    position_sets.append(set(target.positions))
                if not valid:
                    continue
                found = 0
                for start in posting.positions:
                    if all(start + index in values for index, values in enumerate(position_sets, 1)):
                        found += 1
                if found == 0:
                    continue
                contribution = _PHRASE_BONUS * field_boost(field) * found
                scores[doc_id] += contribution
                components[doc_id]["phrase"] += contribution
                phrase_positions = [start + index for start in posting.positions for index in range(len(phrase))]
                _add_match(matched, totals, snippet_positions, doc_id, phrase_positions, field)

    return dict(scores), {key: dict(value) for key, value in components.items()}, matched, totals, snippet_positions


def _cosine(left, right) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b_point for a, b_point in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _semantic_scores(
    data: SnapshotData, query_vector
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    scores: dict[str, float] = {}
    components: dict[str, dict[str, float]] = {}
    for doc_id, vector in data.vectors.items():
        similarity = _cosine(query_vector, vector)
        if similarity <= 0.0:
            continue
        scores[doc_id] = similarity
        components[doc_id] = {"cosine": similarity}
    return scores, components


def _ranks(scores: dict[str, float]) -> dict[str, int]:
    return {
        doc_id: rank
        for rank, doc_id in enumerate(sorted(scores, key=lambda key: (-scores[key], key)), 1)
    }


def _hybrid_scores(
    data: SnapshotData,
    lexical: dict[str, float],
    semantic: dict[str, float],
    rrf_k: int,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    lexical_ranks = _ranks(lexical)
    semantic_ranks = _ranks(semantic)
    scores: dict[str, float] = {}
    components: dict[str, dict[str, float]] = {}
    for doc_id in set(lexical_ranks) | set(semantic_ranks):
        left = 1.0 / (rrf_k + lexical_ranks[doc_id]) if doc_id in lexical_ranks else 0.0
        right = 1.0 / (rrf_k + semantic_ranks[doc_id]) if doc_id in semantic_ranks else 0.0
        scores[doc_id] = left + right
        components[doc_id] = {"lexical_rrf": left, "semantic_rrf": right}
    return scores, components


def _passes_filters(document: StoredDocument, options: SearchOptions) -> bool:
    if options.source_type is not None:
        if str(document.source_type).lower() != str(options.source_type).lower():
            return False
    if options.file_type is not None:
        if str(document.file_type).lower() != str(options.file_type).lower():
            return False
    return True


def _snippet(text: str, position: int | None) -> str:
    tokens = _TOKEN_RE.findall(text or "")
    if not tokens:
        return (text or "")[:300]
    start = 0 if position is None else max(0, min(position - _SNIPPET_TOKENS // 3, len(tokens) - 1))
    end = min(len(tokens), start + _SNIPPET_TOKENS)
    snippet = " ".join(tokens[start:end])
    if start > 0:
        snippet = "..." + snippet
    if end < len(tokens):
        snippet += "..."
    return snippet


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 2:
        return 3
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, 1):
        current = [index]
        for column, other in enumerate(right, 1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (char != other),
                )
            )
        previous = current
    return previous[-1]


_FUZZY_CACHE: dict[int, dict[str, set[str]]] = {}
_SURFACE_CACHE: dict[int, dict[str, str]] = {}


def _fuzzy_index(data: SnapshotData) -> dict[str, set[str]]:
    cached = _FUZZY_CACHE.get(data.generation)
    if cached is not None:
        return cached
    index: dict[str, set[str]] = defaultdict(set)
    vocabulary = sorted({term for term, field in data.postings if field == "body"})
    for term in vocabulary:
        index[term].add(term)
        if len(term) > 3:
            for position in range(len(term)):
                index[term[:position] + term[position + 1:]].add(term)
    result = dict(index)
    _FUZZY_CACHE[data.generation] = result
    if len(_FUZZY_CACHE) > 8:
        oldest = next(iter(_FUZZY_CACHE))
        if oldest != data.generation:
            _FUZZY_CACHE.pop(oldest, None)
    return result


def _fuzzy_candidates(term: str, index: dict[str, set[str]]) -> list[str]:
    candidates: set[str] = set(index.get(term, ()))
    if len(term) > 3:
        for position in range(len(term)):
            candidates.update(index.get(term[:position] + term[position + 1:], ()))
        for position in range(len(term) - 1):
            candidates.update(index.get(term[:position] + term[position + 2:], ()))
    limit = 1 if len(term) <= 6 else 2
    ranked = sorted(
        (distance, word)
        for word in candidates
        if 0 < (distance := _edit_distance(term, word)) <= limit
    )
    return [word for _, word in ranked[:20]]


def _surface_term(term: str, analyzer: Analyzer, data: SnapshotData) -> str:
    cached = _SURFACE_CACHE.get(data.generation)
    if cached is None:
        cached = {}
        for document in data.documents.values():
            for text in (document.title, " ".join(document.headings), document.body):
                for match in _TOKEN_RE.finditer(text or ""):
                    surface = match.group(0).lower()
                    canonical = analyzer.canonical_terms(surface)
                    if canonical and canonical[0] not in cached:
                        cached[canonical[0]] = surface
        _SURFACE_CACHE[data.generation] = cached
        if len(_SURFACE_CACHE) > 8:
            oldest = next(iter(_SURFACE_CACHE))
            if oldest != data.generation:
                _SURFACE_CACHE.pop(oldest, None)
    return cached.get(term, term)


def _fuzzy_expansion(query_spec, analyzer: Analyzer, data: SnapshotData):
    index = _fuzzy_index(data)
    additions: list[_QueryTerm] = []
    correction: str | None = None
    seen: set[str] = set()
    for item in getattr(query_spec, "terms", ()):
        raw = getattr(item, "raw", None) or getattr(item, "term", "")
        canonical = analyzer.canonical_terms(raw)
        if not canonical:
            continue
        term = canonical[0]
        if any((candidate, "body") in data.postings for candidate in canonical):
            continue
        for candidate in _fuzzy_candidates(term, index):
            if candidate in seen or len(additions) >= 20:
                break
            seen.add(candidate)
            additions.append(_QueryTerm(candidate, 0.35, True))
            if correction is None:
                correction = _surface_term(candidate, analyzer, data)
    return tuple(additions), correction


def execute_search(
    data: SnapshotData,
    config,
    query_spec,
    options: SearchOptions,
    analyzer: Analyzer,
    query_vector=None,
) -> SearchPage:
    started = time.perf_counter()
    mode = str(getattr(options, "mode", "lexical") or "lexical").lower()
    ranking = str(getattr(options, "ranking", "bm25") or "bm25").lower()
    if mode not in ("lexical", "semantic", "hybrid"):
        raise ValueError(f"Unsupported search mode: {mode}")
    if mode in ("semantic", "hybrid"):
        if not data.vectors:
            raise ValueError(
                f"mode='{mode}' requires vectors, but the snapshot has no vectors"
            )
        if query_vector is None:
            raise ValueError(f"mode='{mode}' requires a query_vector")

    terms = _query_terms(query_spec, analyzer)
    phrases = _query_phrases(query_spec, analyzer)
    correction: str | None = None
    if bool(getattr(options, "fuzzy", False)) and mode == "lexical":
        additions, correction = _fuzzy_expansion(query_spec, analyzer, data)
        terms += additions
    scores: dict[str, float] = {}
    components: dict[str, dict[str, float]] = {}
    matched: dict[str, set[int]] = {}
    totals: dict[str, int] = {}
    snippet_positions: dict[str, int] = {}

    allowed = {
        doc_id for doc_id, document in data.documents.items()
        if _passes_filters(document, options)
    }

    if mode in ("lexical", "hybrid"):
        scores, components, matched, totals, snippet_positions = _lexical_scores(
            data, config, analyzer, terms, phrases, ranking
        )

    facet_ids = {doc_id for doc_id, value in scores.items() if value > 0.0}
    if mode in ("semantic", "hybrid"):
        semantic_scores, semantic_components = _semantic_scores(data, query_vector)
        if mode == "semantic":
            facet_ids = {doc_id for doc_id, value in semantic_scores.items() if value > 0.0}
            scores = {doc_id: value for doc_id, value in semantic_scores.items() if doc_id in allowed}
            components = {doc_id: semantic_components[doc_id] for doc_id in scores}
        else:
            facet_ids |= {doc_id for doc_id, value in semantic_scores.items() if value > 0.0}
            lexical = {doc_id: value for doc_id, value in scores.items() if doc_id in allowed}
            semantic = {doc_id: value for doc_id, value in semantic_scores.items() if doc_id in allowed}
            scores, components = _hybrid_scores(
                data, lexical, semantic, int(getattr(config, "rrf_k", 60))
            )

    candidate_ids = {doc_id for doc_id, value in scores.items() if value > 0.0}
    facets: dict[str, dict[str, int]] = {"source_type": {}, "file_type": {}}
    for doc_id in facet_ids:
        document = data.documents.get(doc_id)
        if document is None:
            continue
        for name, value in (("source_type", document.source_type), ("file_type", document.file_type)):
            bucket = facets[name]
            bucket[value] = bucket.get(value, 0) + 1

    filtered = [doc_id for doc_id in candidate_ids if doc_id in allowed]
    max_raw = max((scores[doc_id] for doc_id in filtered), default=0.0)
    threshold = float(getattr(options, "threshold", 0.0))

    hits: list[SearchHit] = []
    for doc_id in filtered:
        raw_score = scores[doc_id]
        normalized = min(1.0, raw_score / max_raw) if max_raw > 0.0 else 0.0
        if normalized < threshold:
            continue
        document = data.documents[doc_id]
        explanation = dict(components.get(doc_id, {}))
        if not explanation:
            explanation = {"score": raw_score}
        positions = sorted(matched.get(doc_id, ()))[:_MAX_POSITIONS]
        hits.append(
            SearchHit(
                doc_id=doc_id,
                filename=document.filename,
                source_type=document.source_type,
                source_url=document.source_url,
                score=round(normalized, 6),
                raw_score=raw_score,
                snippet=_snippet(document.body, snippet_positions.get(doc_id)),
                word_count=document.word_count,
                file_size_bytes=document.byte_size,
                indexed_at=document.indexed_at,
                total_matches=totals.get(doc_id, len(positions)),
                matched_positions=tuple(positions),
                explanation=explanation,
            )
        )

    sort = str(getattr(options, "sort", "relevance") or "relevance").lower()
    if sort == "filename":
        hits.sort(key=lambda hit: (hit.filename.lower(), hit.doc_id))
    elif sort == "size":
        hits.sort(key=lambda hit: (-hit.file_size_bytes, hit.doc_id))
    else:
        hits.sort(key=lambda hit: (-hit.score, hit.doc_id))

    total_results = len(hits)
    limit = max(1, int(getattr(options, "limit", 10)))
    offset = max(0, int(getattr(options, "offset", 0)))
    page = tuple(hits[offset:offset + limit])
    elapsed = (time.perf_counter() - started) * 1000.0
    return SearchPage(
        query=str(getattr(query_spec, "raw", "")),
        ranking=ranking,
        mode=mode,
        generation=data.generation,
        total_results=total_results,
        results=page,
        correction=correction,
        facets=facets,
        elapsed_ms=elapsed,
    )
