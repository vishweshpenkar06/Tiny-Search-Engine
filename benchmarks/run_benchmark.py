import argparse
import json
import math
import random
import re
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z0-9]+")
VOCAB = (
    "retrieval index query ranking bm25 tfidf relevance snippet document corpus search "
    "database sqlite transaction rollback join table schema row commit "
    "network tcp http dns tls latency packet socket status cache handshake "
    "python generator comprehension decorator context manager list memory function "
    "docker container compose volume deploy healthcheck limit image"
).split()


def tokenize(text):
    return TOKEN_RE.findall(text.lower())


def load_corpus(path, limit):
    files = sorted(path.rglob("*.txt"))
    if limit > 0:
        files = files[:limit]
    return [(file.stem, file.read_text(encoding="utf-8")) for file in files]


def build_index(docs):
    postings = defaultdict(dict)
    for doc_id, text in docs:
        counts = Counter(tokenize(text))
        length = sum(counts.values()) or 1
        for term, count in counts.items():
            postings[term][doc_id] = count / length
    return dict(postings)


def search(postings, query, limit):
    terms = tokenize(query)
    scores = Counter()
    for term in terms:
        for doc_id, weight in postings.get(term, {}).items():
            scores[doc_id] += weight
    return scores.most_common(limit)


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[position]


def live_search(api_url, query, limit, credentials):
    body = json.dumps({"query": query, "limit": limit, "ranking": "bm25", "mode": "lexical"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if credentials:
        import base64

        token = base64.b64encode(f"{credentials[0]}:{credentials[1]}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token
    request = urllib.request.Request(api_url.rstrip("/") + "/api/search", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return len(json.loads(response.read().decode("utf-8")).get("results", []))


def main():
    parser = argparse.ArgumentParser(description="Deterministic 10k/100k benchmark runner.")
    parser.add_argument("--corpus", type=Path, default=Path("benchmarks/data/corpus_10000"))
    parser.add_argument("--limit-docs", type=int, default=0)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--source", choices=["local", "live"], default="local")
    parser.add_argument("--api-url", default="http://127.0.0.1:5000")
    parser.add_argument("--basic-user", default=None)
    parser.add_argument("--basic-pass", default=None)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    docs = load_corpus(args.corpus, args.limit_docs)
    rng = random.Random(args.seed)
    workload = {
        "corpus": str(args.corpus),
        "documents": len(docs),
        "queries": args.queries,
        "top_k": args.top_k,
        "seed": args.seed,
        "source": args.source,
        "timer": "time.perf_counter_ns",
    }
    credentials = (args.basic_user, args.basic_pass) if args.basic_user and args.basic_pass else None

    if args.source == "local":
        started = time.perf_counter_ns()
        postings = build_index(docs)
        index_ns = time.perf_counter_ns() - started

        def run(query):
            return len(search(postings, query, args.top_k))
    else:
        index_ns = 0

        def run(query):
            return live_search(args.api_url, query, args.top_k, credentials)

    latencies = []
    hits = []
    for _ in range(args.queries):
        query = " ".join(rng.sample(VOCAB, k=rng.choice((1, 2, 3))))
        started = time.perf_counter_ns()
        hits.append(run(query))
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)

    report = {
        "workload": workload,
        "index_seconds": index_ns / 1_000_000_000,
        "documents_per_second": len(docs) / (index_ns / 1_000_000_000) if index_ns else None,
        "search_p50_ms": percentile(latencies, 0.50),
        "search_p95_ms": percentile(latencies, 0.95),
        "search_p99_ms": percentile(latencies, 0.99),
        "mean_hits": sum(hits) / len(hits) if hits else 0.0,
    }
    print(json.dumps(report, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
