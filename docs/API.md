# API Contract v1

All paths are browser-relative through the Next.js `/api/*` proxy. The browser never learns the Flask origin.

## Conventions

- Success body is the resource object plus `request_id`.
- Error body is `{"error": {"code": string, "message": string}, "request_id": string}`.
- Authentication is HTTP Basic when `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` are configured.
- Mutating requests require an `Origin` matching `PUBLIC_ORIGIN` when auth is enabled.
- `generation` is a monotonically increasing integer. Clients must key caches by it.

## Endpoints

### `GET /api/health`

Liveness only: `{"status": "ok", "timestamp": string}`.

### `GET /api/readyz`

Readiness: `{"status": "ready" | "unready", "generation": number, "document_count": number, "reason": string | null}`.

### `GET /api/config`

Returns public limits and capabilities: allowed extensions, max file size, max files, max query length, ranking modes, retrieval modes.

### `POST /api/upload`

Multipart field `files`. Returns `{"upload_id": string, "file_count": number, "rejected": [string], "generation": number}`.

### `POST /api/index`

Request `{"upload_id": string, "ranking": "tfidf" | "bm25"}`. Returns `202 {"job_id": string, "status": "queued", "generation": number}`.

### `GET /api/index/status?job_id=...`

Returns `{"job_id": string, "kind": string, "status": string, "progress": number, "processed": number, "succeeded": number, "skipped": number, "failed": number, "error": string | null, "generation": number, "created_at": string, "updated_at": string, "finished_at": string | null}`.

### `POST /api/index/jobs/{job_id}/cancel`

Returns `{"job_id": string, "status": "cancelling"}`.

### `POST /api/search`

Request fields:

- `query`: string, required, max 500 chars.
- `ranking`: `tfidf` | `bm25` | `learned`, default `bm25`. `rank` is accepted as an alias. `learned` blends normalized BM25, TF-IDF and optional semantic scores using `backend/core/ranker_weights.json`.
- `mode`: `lexical` | `semantic` | `hybrid`, default `lexical`.
- `fuzzy`: boolean, default true. Set false for controlled ranking comparisons.
- `threshold`: number 0–1 applied to the normalized score.
- `limit`: integer 1–100, default 10.
- `offset`: integer ≥ 0, default 0.
- `sort`: `relevance` | `filename` | `size`, default `relevance`.
- `filters`: optional `{"source_type": string, "file_type": string}`.

Response:

```json
{
  "query": string,
  "ranking": string,
  "mode": string,
  "generation": number,
  "total_results": number,
  "results": [
    {
      "doc_id": string,
      "filename": string,
      "source_type": string,
      "source_url": string | null,
      "score": number,
      "raw_score": number,
      "snippet": string,
      "word_count": number,
      "file_size_bytes": number,
      "indexed_at": string,
      "total_matches": number,
      "matched_positions": number[],
      "explanation": object
    }
  ],
  "correction": string | null,
  "facets": {"source_type": object, "file_type": object},
  "elapsed_ms": number
}
```

### `GET /api/documents/{doc_id}`

Returns document content as `text/plain; charset=utf-8` with safe `Content-Disposition`.

### `POST /api/crawl`

Admin-only. Request `{"url": string, "max_pages": number, "max_depth": number}`. Returns a crawl job. Disabled unless `ENABLE_CRAWLER=true`.

## Score semantics

`score` is `raw_score / max_raw_score` for the current query and is capped at 1. `threshold` filters on `score`. Ranking explanations expose the original components.
