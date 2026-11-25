# Architecture

## Shape

```
Browser
  |
  v  browser-relative /api/* (same origin)
Next.js server (server-side proxy, BACKEND_ORIGIN)
  |
  v  internal Docker network only
Flask API (gunicorn, one worker, non-root)
  |
  v
IndexService -> IndexStore (SQLite, /data) -> snapshot -> ranker
       |                                      |
       +-> upload streams /data/uploads/<uuid> +
       +-> crawler (opt-in)                   +-> local embeddings (opt-in)
```

The browser never learns the Flask origin. Only the Next.js container publishes a host port; the backend is reached through the internal network.

## Backend layers

| Layer | Owns | Key interface |
|---|---|---|
| `backend/app.py` | HTTP, auth, validation, error envelopes, request ids | `create_app(config=None, service=None)` |
| `backend/config.py` | typed environment configuration | `load_config()` |
| `backend/core/index_service.py` | jobs, generations, snapshots, search orchestration | `IndexService(config, store)` |
| `backend/core/index_store.py` | SQLite persistence, jobs, batches, snapshots | `IndexStore(config)` |
| `backend/core/search_engine.py` | lexical ranking primitives | engine helpers |
| `backend/core/analysis.py` | stemming and synonyms | analysis helpers |
| `backend/crawler/` | polite fetching, robots, extraction | crawler helpers |
| `backend/utils/` | JSON logging, error envelopes, validators | `ApiError`, `parse_query`, validators |

`create_app` accepts an injected service. Production builds one via `IndexStore(config)` followed by `IndexService(config, store)`, then calls `initialize()` on both. Tests inject a fake service, so they never touch SQLite or the network.

## Request lifecycle

1. `before_request` assigns a request id, enforces HTTP Basic auth except on `/api/health`, `/livez`, `/readyz`, checks the `Origin` header on mutations when auth is enabled, and applies a fixed-window per-IP rate limit.
2. Route helpers require `application/json`, reject malformed bodies, and translate validation failures into stable `ApiError` codes.
3. `IndexService` does the work. Responses are plain resource objects or `SearchPage` dictionaries plus `request_id`.
4. `after_request` adds `X-Request-ID`, security headers and `Cache-Control: no-store` for API paths.
5. Registered handlers map `ApiError`, Werkzeug HTTP exceptions and unexpected errors to `{"error": {"code", "message"}, "request_id"}`.

## Security decisions

- Auth is on or off based on `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH`. Passwords are verified with Werkzeug hashes and usernames with a constant-time comparison.
- Mutations with auth enabled require `Origin` to match `PUBLIC_ORIGIN`. Without auth the endpoint is reachable only from the internal network.
- Upload ids and doc ids are UUIDs; job ids are restricted to a conservative character set. They are used as opaque handles, never as client-supplied paths.
- Uploads are streamed to disk in bounded chunks, validated per file, and written as deterministic blob names under `upload_dir/<upload_id>`.
- Responses contain no absolute filesystem paths, and structured logs contain no query text, document content or paths.

## Generation model

`generation` is a monotonic integer owned by the store. Clients key caches by it. `/readyz` reports the active generation, document count and a reason when unready. A new published generation is the only signal that search results changed.

## Ranking and modes

`ranking` selects `tfidf` or `bm25`. `mode` selects `lexical`, `semantic` or `hybrid`. The API builds `SearchOptions`, and only computes a query vector when `ENABLE_EMBEDDINGS=true` and the mode is `semantic` or `hybrid`. The embedding provider is `core.embeddings`: local hashing by default, or a vendored FastEmbed ONNX model when `EMBEDDING_MODEL` is set.

`threshold` filters on normalized `score` (`raw_score / max_raw_score`, capped at 1). Ranking explanations expose the original components.

## Evaluation and benchmarks

`eval/` is a deterministic CI smoke set: 20 documents, 12 graded queries, fixed metric definitions in `eval/BASELINE.md`. `eval/run_eval.py` computes nDCG@10, MRR and Recall@10 either with a static TF-IDF ranker or against a live API. `benchmarks/` generates 10k or 100k documents and measures index build and query latency with `perf_counter_ns`. Neither is a substitute for the full 50-query, 100-document gold set in the IMPROVE spec.
