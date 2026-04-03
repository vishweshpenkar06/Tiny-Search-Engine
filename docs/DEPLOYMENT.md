# Deployment Guide — Tiny Search Engine

## Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Python | 3.10+ | `python --version` (dev only) |
| Node.js | 20+ | `node --version` (dev only) |

---

## Quick Start (Docker — Recommended)

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd "Tiny Search Engine AG"

# 2. Copy and configure environment
cp .env.example .env.local
# Edit .env.local if needed (defaults work for local Docker)

# 3. Build and start all services
docker compose up --build

# 4. Open in browser
# Frontend: http://localhost:3000
# Backend API: http://localhost:5000/api/health
```

> **First build takes ~3–5 minutes** (downloads base images, installs deps).
> Subsequent builds are cached and take ~30 seconds.

---

## Manual (Development) Setup

### Backend (Flask)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# Windows:  .\venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the Flask server
python app.py
# → Running on http://localhost:5000
```

### Frontend (Next.js)

```bash
# From the project root (not backend/)

# Install dependencies
npm install

# Start development server
npm run dev
# → Running on http://localhost:3000
```

---

## Production Deployment

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:5000` | Flask backend URL |
| `FLASK_ENV` | `development` | Flask env (`production` in Docker) |
| `PORT` | `5000` | Flask port |
| `MAX_CONTENT_LENGTH` | `10485760` | Max upload size (bytes) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins |

### Docker Compose Commands

```bash
# Start services in background
docker compose up -d

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f backend
docker compose logs -f frontend

# Stop services
docker compose down

# Stop and remove volumes (DELETES indexed data)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

### Checking Service Health

```bash
# Backend health check
curl http://localhost:5000/api/health

# Expected response:
# {"status": "healthy", "index_loaded": true, "documents_indexed": 42}
```

---

## Data Persistence

Uploaded files and the built search index are stored in named Docker volumes:

| Volume | Content | Purpose |
|--------|---------|---------|
| `uploads_data` | Raw uploaded files | Source documents |
| `index_data` | TF-IDF index files | Persist index between restarts |

To back up your index:
```bash
docker run --rm \
  -v tse_index_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/index_backup.tar.gz /data
```

---

## Architecture

```
┌─────────────────────────────────────┐
│            Docker Network           │
│                                     │
│  ┌──────────────┐  ┌─────────────┐  │
│  │  Next.js     │  │   Flask     │  │
│  │  Frontend    │──│   Backend   │  │
│  │  :3000       │  │   :5000     │  │
│  └──────────────┘  └──────┬──────┘  │
│                           │         │
│                    ┌──────┴──────┐  │
│                    │  TF-IDF     │  │
│                    │  Index      │  │
│                    │  (Volume)   │  │
│                    └─────────────┘  │
└─────────────────────────────────────┘
         │                   │
    localhost:3000      localhost:5000
      (browser)           (API only)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Frontend can't reach backend | Check `NEXT_PUBLIC_API_URL` in `.env.local` |
| `npm install` fails | Run `npm install --legacy-peer-deps` |
| Docker port already in use | Change ports in `docker-compose.yml` |
| Index lost after restart | Volumes must not be deleted; check `docker volume ls` |
| CORS errors in browser | Add your domain to `CORS_ORIGINS` in backend env |
