# Tiny Search Engine Backend

## Setup Requirements
Python 3.10+

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python app.py
```

The server will start on `http://localhost:5000`.

## Features
- TF-IDF indexing and search.
- Stop word removal.
- File upload and parsing.
- Hash-based duplicate detection.
- Input validation.
- CORS enabled for the Next.js frontend.
