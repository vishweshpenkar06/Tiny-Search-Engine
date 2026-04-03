# 🔍 Tiny Search Engine

A **production-ready, full-stack search engine** built from scratch — no Elasticsearch, no cloud search APIs. Just pure algorithms, data structures, and modern web engineering.

![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![Flask](https://img.shields.io/badge/Flask-3.0-blue?logo=flask)
![Python](https://img.shields.io/badge/Python-3.10+-green?logo=python)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?logo=typescript)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)

---

## ✨ Features

### Search Engine Core (Backend)
- **TF-IDF Ranking** — Term Frequency × Inverse Document Frequency scoring
- **Inverted Index** — O(1) term lookups with position tracking
- **Phrase Search** — `"exact phrase"` matching using positional data
- **Multi-Format Parsing** — `.txt`, `.md`, `.html`, `.csv` files
- **Stop-Word Removal & Tokenization** — Smart preprocessing pipeline

### Frontend
- **Real-Time Search** — 500ms debounced queries with skeleton loading states
- **Result Highlighting** — Query terms highlighted in snippets
- **Sort & Filter** — By relevance, filename, or file size; min-relevance slider
- **Pagination** — Load 10 results at a time with "Load More"
- **Export** — Download results as JSON or CSV
- **Keyboard Shortcuts** — `⌘K` / `Ctrl+K` to focus search instantly
- **Copy Path** — One-click path copying on any result

### Production Engineering
- **Security Headers** — CSP, X-Frame-Options, HSTS, Referrer-Policy
- **Input Sanitization** — Client + server-side validation
- **Error Boundaries** — Graceful degradation on API failures
- **Mock Fallback** — UI stays usable even when backend is offline
- **Docker** — Single `docker compose up` deploys everything
- **Health Checks** — Both services monitored by Docker

---

## 🚀 Quick Start

```bash
# Docker (recommended)
docker compose up --build
# → http://localhost:3000

# Manual development
# Terminal 1 — Backend
cd backend && pip install -r requirements.txt && python app.py

# Terminal 2 — Frontend
npm install && npm run dev
```

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for full setup instructions.

---

## 📁 Project Structure

```
Tiny Search Engine AG/
├── app/                    # Next.js App Router pages
│   ├── page.tsx            # Home (upload)
│   ├── progress/page.tsx   # Indexing progress
│   └── search/page.tsx     # Search results
├── backend/                # Flask API
│   ├── app.py              # Entry point & routes
│   ├── core/               # Search engine algorithms
│   │   ├── search_engine.py  # TF-IDF + inverted index
│   │   ├── tokenizer.py      # Text preprocessing
│   │   └── file_parser.py    # Multi-format file parsing
│   └── utils/              # Helpers (validation, logging, errors)
├── components/             # Reusable React components
├── hooks/                  # Custom React hooks
├── lib/                    # API client, types, utilities
├── docs/                   # Documentation
├── Dockerfile              # Frontend container
├── backend/Dockerfile      # Backend container
└── docker-compose.yml      # Orchestration
```

---

## 🧠 How It Works

1. **Upload** — Drop `.txt`, `.md`, `.html`, or `.csv` files onto the upload zone
2. **Index** — The Flask backend tokenizes, removes stop words, and builds an inverted index with TF-IDF weights
3. **Search** — Queries are tokenized the same way; results scored by TF-IDF and ranked; phrase positions verified for exact matches
4. **Display** — Top results shown with highlighted snippets, relevance scores, and metadata

### TF-IDF Formula

```
TF(term, doc) = count(term in doc) / total_words(doc)
IDF(term)     = log(total_docs / docs_containing_term)
Score         = TF × IDF
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| UI Components | shadcn/ui, Lucide Icons |
| Backend | Python 3.10+, Flask 3, Flask-CORS |
| Search Algorithms | Custom TF-IDF, Inverted Index, Tokenizer |
| Validation | Zod (frontend), custom validators (backend) |
| Deployment | Docker, Docker Compose |

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/upload` | Upload files for indexing |
| `POST` | `/api/index` | Start indexing a folder |
| `GET` | `/api/index/status` | Get indexing progress |
| `DELETE` | `/api/index/cancel` | Cancel ongoing indexing |
| `GET` | `/api/search?q=...` | Search the index |

---

## 📄 License

MIT — built for learning and demonstration purposes.
