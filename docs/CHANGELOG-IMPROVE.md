# Changelog — IMPROVE

All notable changes for the real-IR improvement effort. Entries are grouped by workstream and record measured results only when a command exists to reproduce them.

## [Unreleased] — 2026-11-25

### API wiring and delivery

- Replaced the global Flask server with `create_app(config=None, service=None)` and a module-level `app` for WSGI.
- Added HTTP Basic auth on all API routes except `/api/health`, `/livez` and `/readyz`, plus `Origin` checks on mutations when auth is enabled.
- Added stable error envelopes for 400, 401, 403, 404, 405, 413, 415, 429 and 500, request ids, JSON-only helpers and security headers.
- Implemented `/api/config`, `/api/upload`, `/api/index`, `/api/index/status`, `/api/index/jobs/<job_id>/cancel`, `/api/index/cancel`, `/api/search`, `/api/documents/<doc_id>` and `/api/crawl` per `docs/API.md`.
- Uploads are streamed in bounded chunks into `upload_dir/<uuid>` with deterministic blob names and a per-file rejection list.
- Search validates ranking, mode, fuzzy, threshold, limit, offset, sort and filters, and computes a query vector only for semantic or hybrid modes with embeddings enabled.
- Responses avoid absolute filesystem paths; logs avoid query text, content and paths.
- Pinned Flask, flask-cors, Werkzeug and gunicorn; backend image runs as a non-root user without build tools and with one gunicorn worker.
- Compose publishes only the frontend port, keeps the backend on an internal network, uses one durable `/data` volume, resource limits, read-only backend rootfs, tmpfs and healthchecks.
- Added `packageManager`, `typecheck`, `lint` and `test` scripts; `tsconfig.json` already has `noEmit`, so `npx tsc --noEmit` is the typecheck command.
- Added CI for Python unittest, compileall, frontend typecheck and build, `docker compose config -q`, and a basic secret scan.

### Tests

- Added `backend/tests/test_api.py` with 11 unittest cases covering health, readiness, config, auth, origin rejection, malformed JSON, wrong types, rate limiting, upload limits, UUID isolation, opaque ids, job lifecycle, cancellation, search validation, document retrieval with safe disposition, crawl gating, error envelopes and path leakage.
- API tests inject a fake service and use temporary directories, so they need no network and no SQLite state.

### Evaluation and benchmarks

- Added 20 deterministic documents across five topics and 12 graded queries.
- Added `eval/run_eval.py` with fixed nDCG@10, MRR and Recall@10 definitions, static and live modes, and `perf_counter_ns` latency.
- Recorded the legacy TF-IDF baseline in `eval/BASELINE.md`: nDCG@10 0.9732, MRR 1.0000, Recall@10 0.9167.
- Added `eval/RESULTS.md` with a reporting template and explicit limitations.
- Added deterministic 10k/100k corpus generation and a benchmark runner with a declared workload and percentile latency.

### Documentation

- Added `docs/ARCHITECTURE.md` and `docs/CHANGELOG-IMPROVE.md`.
- Rewrote `docs/DEPLOYMENT.md` and `README.md` to match implemented behaviour.
- Added `LICENSE` and `SECURITY.md`.

### Integration follow-up

- Added bounded fuzzy matching with a per-generation deletion index, 20-term expansion cap, typo correction reporting, and opt-in `fuzzy` requests.
- Added `core/embeddings.py` with deterministic offline hashing vectors and optional pinned local `sentence-transformers` models; upload and crawl jobs persist vectors when embeddings are enabled.
- Added `/api/readyz` as the browser-relative readiness alias and preserved original upload filenames in SQLite metadata.
- Removed Vercel Analytics from the self-hosted layout and added a working ESLint flat config.
- Fixed the benchmark runner's `--limit-docs` default and recorded real 10k and 100k local harness results in `eval/BENCHMARKS.md`.
- Recorded live 20-document evaluations in `eval/RESULTS.md`: BM25 nDCG@10 0.9653 and TF-IDF 0.9636. The difference is below the noise threshold for this fixture.
- Backend suite grew to 65 passing tests; frontend lint, typecheck and production build pass.

### Not claimed

- No meaningful ranking improvement is claimed: the smoke fixture saturates MRR and the BM25/TF-IDF difference is below the stated noise threshold.
- The full 50-query / 100-document gold set is not present; this repository contains a 20-document / 12-query CI smoke set.
- Benchmarks use the simplified local harness, not the production Flask path or concurrent HTTP load.
- Hybrid relevance is not evaluated on the gold set; it is wired and smoke-tested but not claimed as better than BM25.
