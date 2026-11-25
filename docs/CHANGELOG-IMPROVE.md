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

- Added `eval/generate_fixtures.py`: 100 deterministic documents, 50 graded queries, and a frozen 35-query dev / 15-query test split.
- Added `eval/run_eval.py` with fixed nDCG@10, MRR and Recall@10 definitions, static and live modes, split filtering, and `perf_counter_ns` latency.
- Recorded the legacy TF-IDF baseline in `eval/BASELINE.md`: held-out nDCG@10 0.7668, MRR 1.0000, Recall@10 0.7515.
- Added `eval/RESULTS.md` with live results and explicit limitations.
- Added deterministic 10k/100k corpus generation and a benchmark runner with a declared workload and percentile latency.

### Documentation

- Added `docs/ARCHITECTURE.md` and `docs/CHANGELOG-IMPROVE.md`.
- Rewrote `docs/DEPLOYMENT.md` and `README.md` to match implemented behaviour.
- Added `LICENSE` and `SECURITY.md`.

### Integration follow-up

- Added bounded fuzzy matching with a per-generation deletion index, 20-term expansion cap, typo correction reporting, and `fuzzy` enabled by default.
- Added `core/embeddings.py` with deterministic offline hashing vectors and optional vendored FastEmbed ONNX models; upload and crawl jobs persist vectors when embeddings are enabled.
- Added `/api/readyz` as the browser-relative readiness alias and preserved original upload filenames in SQLite metadata.
- Removed Vercel Analytics from the self-hosted layout and added a working ESLint flat config.
- Fixed the benchmark runner's `--limit-docs` default and recorded real 10k and 100k local harness results in `eval/BENCHMARKS.md`.
- Recorded live 100-document held-out evaluations in `eval/RESULTS.md`: TF-IDF nDCG@10 0.9032 and BM25 0.8224. BM25 does not beat TF-IDF on this fixture.
- Added Snowball stemming, `rank` as a `ranking` alias, and fuzzy matching enabled by default per the spec.
- Added `backend/requirements-ml.txt` and `scripts/vendor_embedding_model.py` for offline model packaging with checksums.
- Replaced the unusable PyTorch install path with FastEmbed ONNX; vendored `BAAI/bge-small-en-v1.5` and verified query encoding with `HF_HUB_OFFLINE=1`.
- Exposed `EMBEDDING_MODEL` through `.env.example` and Compose.
- Ran dev-only tuning sweeps for BM25 parameters, field boosts, all-terms bonus, phrase proximity, and BM25/TF-IDF blending. None improved dev nDCG, so the speculative knobs were removed.
- Evaluated semantic and hybrid modes on dev and held-out splits; RRF `k=10` won on dev but lost on held-out, so the default remains `k=60`.
- Fixed a review blocker: `embed_document` now uses the passage embedding path instead of the query prefix; added a regression test.
- Extracted vector normalization into one helper and fail loudly when `EMBEDDING_MODEL` is set but FastEmbed is unavailable.
- Backend suite grew to 66 passing tests; frontend lint, typecheck and production build pass.

### Learned ranker phase

- Added `ranking=learned`, a linear blend of normalized BM25, TF-IDF and optional semantic scores using `backend/core/ranker_weights.json`.
- Added `eval/train_ranker.py` with dev-only grid search and an optional dev-internal train/validation split; held-out queries are never used for training.
- Exposed `learned` through the API contract, config, frontend ranking selector and evaluation CLI.
- Committed dev-validation weights: BM25 0.0404, TF-IDF 0.1010, semantic 0.8586.
- Recorded held-out learned nDCG@10 0.8458: better than BM25 and hybrid on this fixture, below TF-IDF.

### Not claimed

- No relevance improvement is claimed: BM25, semantic, hybrid and learned modes are all below TF-IDF on the held-out split and the 15% target is unmet.
- Benchmarks use the simplified local harness, not the production Flask path or concurrent HTTP load.
- Real model weights are not committed; the default runtime provider remains deterministic local hashing and operators must vendor a model for semantic modes.
