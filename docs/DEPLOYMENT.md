# Deployment

## Prerequisites

| Tool | Minimum | Check |
|---|---|---|
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Python | 3.10+ | `python3 --version` (development and tests) |
| Node.js | 20+ | `node --version` (development) |

## Compose deployment

```
cp .env.example .env.local
docker compose up --build
```

The frontend is available on `http://localhost:${FRONTEND_PORT:-3000}`. The backend publishes no host port. Its health endpoint is reachable only from the frontend container and from compose healthchecks.

Compose mounts a single named volume at `/data` and sets `DATA_DIR`, `UPLOAD_DIR`, `INDEX_PATH` and `MODEL_DIR` inside it. The backend container runs read-only with a `tmpfs` at `/tmp`. CPU and memory limits are declared for both services.

Stop with `docker compose down`. Use `docker compose down -v` only when you intend to delete the index.

## Environment

All values are read by `backend/config.py` unless marked as compose-only. See `.env.example` for the complete list.

| Variable | Default | Notes |
|---|---|---|
| `ADMIN_USERNAME` | unset | Enables HTTP Basic auth together with the hash |
| `ADMIN_PASSWORD_HASH` | unset | Werkzeug hash, not a plaintext password |
| `PUBLIC_ORIGIN` | `http://localhost:3000` | Origin required on mutating requests when auth is on |
| `DATA_DIR` | `backend/data` locally, `/data` in compose | Root of all durable state |
| `MAX_CONTENT_LENGTH` | `52428800` | Whole request cap enforced by Flask |
| `MAX_FILE_SIZE` | `10485760` | Per-file cap enforced while streaming |
| `MAX_FILES` | `100` | Files per upload batch |
| `MAX_QUERY_LENGTH` | `500` | Characters after sanitization |
| `RATE_LIMIT_RPM` | `120` | Fixed-window limit per client address |
| `ENABLE_EMBEDDINGS` | `false` | Requires a local embedding module and model |
| `ENABLE_CRAWLER` | `false` | Crawl endpoint returns 403 while off |
| `CRAWLER_ALLOWED_DOMAINS` | empty | Comma-separated allowlist |
| `BM25_K1`, `BM25_B`, `RRF_K` | `1.2`, `0.75`, `60` | Ranking parameters |
| `BACKEND_ORIGIN` | `http://backend:5000` | Server-side proxy target in the frontend container |
| `FRONTEND_PORT` | `3000` | Compose-only host port for the frontend |

Generate a password hash with:

```
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('choose-a-long-password'))"
```

Keep it out of shell history if that matters in your environment. A plaintext password must never be committed.

## Offline embeddings

The default provider is deterministic local hashing and needs no model. To use a sentence-transformer model:

```
python3 -m pip install -r backend/requirements-ml.txt
python3 scripts/vendor_embedding_model.py --model BAAI/bge-small-en-v1.5
```

The script writes the model under `backend/data/models`, records `SHA256SUMS`, and prints the `EMBEDDING_MODEL` value to set. At runtime the backend loads only from that local directory with `local_files_only=True`; no network access is required. Re-embed existing documents after changing the model because vectors are versioned by model name.

## Health and readiness

| Path | Purpose | Auth |
|---|---|---|
| `GET /api/health` | Process liveness | none |
| `GET /livez` | Process liveness alias | none |
| `GET /readyz` | Generation, document count, reason | none |

Compose uses `/api/health` for the backend healthcheck and `/` for the frontend. Readiness is intended for orchestrators that gate traffic.

## Local development

```
cd backend && python3 -m pip install -r requirements.txt && python3 app.py
npm ci && npm run dev
```

`app.py` only calls `app.run` under `__main__` and uses `HOST`, `PORT` and `DEBUG` from configuration. WSGI servers import the module-level `app` object; gunicorn runs it with one worker and four threads.

## Verification

```
python3 -m compileall -q backend eval benchmarks
cd backend && python3 -m unittest discover -s tests -v
python3 eval/run_eval.py
npm ci && npm run typecheck && npm run build
docker compose config -q
```

`npm run test` runs the backend unittest suite from the repository root. CI runs the same checks plus a basic secret scan.

## Data and backups

Back up the compose volume rather than individual files:

```
docker run --rm -v tiny-search-engine_backend_data:/data -v "$PWD":/backup alpine tar czf /backup/index_backup.tar.gz -C /data .
```

Confirm the volume name with `docker volume ls`; compose prefixes it with the project name.

## Operational limits

The backend uses one gunicorn worker with threads. Index state is shared in-process and published by generation. Horizontal scaling requires a shared store and a coordination strategy that is not implemented here; run a single backend replica.
