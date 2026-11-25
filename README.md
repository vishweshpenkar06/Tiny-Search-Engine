# Tiny Search Engine

A small full-stack search engine built without Elasticsearch or a hosted search API. The backend implements the index and ranking in Python; the frontend is Next.js and talks to it through a browser-relative `/api/*` proxy.

## What is implemented

- Backend API matching `docs/API.md`: health, readiness, config, upload, index jobs, search, document retrieval and opt-in crawling.
- HTTP Basic auth on API routes, with `Origin` checks on mutations when auth is enabled.
- Streaming uploads with per-file limits, rejection lists and opaque UUID batch ids.
- Typed search options: `tfidf` or `bm25` ranking, `lexical`, `semantic` or `hybrid` mode, fuzzy flag, threshold, pagination, sort and filters.
- SQLite-backed index service with generations and job tracking.
- Deterministic evaluation fixtures and a benchmark generator.
- Docker Compose deployment with one published port and a durable data volume.

Ranking quality numbers are reported in `eval/BASELINE.md` and `eval/RESULTS.md`. No improvement over TF-IDF is claimed without a measured row there.

## Quick start

```
docker compose up --build
```

Open `http://localhost:3000`. The backend is intentionally not published on the host.

For local development:

```
cd backend && python3 -m pip install -r requirements.txt && python3 app.py
npm ci && npm run dev
```

## API

The authoritative contract is `docs/API.md`. Success responses are the resource object plus `request_id`. Errors are `{"error": {"code", "message"}, "request_id"}`. `generation` is monotonic and clients should key caches by it.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health`, `/livez`, `/readyz` | Liveness and readiness |
| `GET` | `/api/config` | Public limits and capabilities |
| `POST` | `/api/upload` | Stream files to a UUID batch |
| `POST` | `/api/index` | Start an indexing job |
| `GET` | `/api/index/status?job_id=...` | Job progress |
| `POST` | `/api/index/jobs/<id>/cancel` | Cancel a job |
| `POST` | `/api/search` | Search the active generation |
| `GET` | `/api/documents/<id>` | Retrieve one document as plain text |
| `POST` | `/api/crawl` | Start a crawl when enabled |

`/api/index/cancel` remains as a compatibility alias that cancels the most recent job started through this process.

## Verification

```
python3 -m compileall -q backend eval benchmarks
cd backend && python3 -m unittest discover -s tests -v
python3 eval/run_eval.py
npm ci && npm run typecheck && npm run build
docker compose config -q
```

`npm run test` runs the same backend unittest suite from the repository root.

## Structure

```
app/                  Next.js routes
components/           UI components
hooks/, lib/          Client hooks and API helpers
backend/app.py        HTTP layer and app factory
backend/config.py     Environment configuration
backend/core/         Index service, store, parser, tokenizer, ranking
backend/crawler/      Polite crawler
backend/tests/        API tests
eval/                 Queries, fixtures, metric harness, baseline and results
benchmarks/           Corpus generator and benchmark runner
docs/                 API, architecture, deployment and changelog
```

## Notes and limits

- One gunicorn worker is intentional: generation state is held in that process. Run a single backend replica.
- Semantic and hybrid modes need a local embeddings module and model; lexical modes work without one.
- The crawler is disabled unless `ENABLE_CRAWLER=true` and should only be pointed at sites you are allowed to fetch.
- The evaluation set is a CI smoke fixture, not a production quality signal.

## Documentation

- `docs/API.md` — HTTP contract
- `docs/ARCHITECTURE.md` — components and request lifecycle
- `docs/DEPLOYMENT.md` — configuration and operations
- `docs/CHANGELOG-IMPROVE.md` — improvement workstream
- `SECURITY.md` — reporting and hardening notes

## License

MIT. See `LICENSE`.
