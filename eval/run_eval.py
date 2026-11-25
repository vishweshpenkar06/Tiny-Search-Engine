import argparse
import base64
import json
import math
import os
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset(
    "a an and are as at be by for from has have in is it of on or that the this to was were with".split()
)


def load_queries(path):
    queries = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def load_docs(path):
    docs = {}
    for file in sorted(path.glob("*.md")):
        docs[file.stem] = file.read_text(encoding="utf-8")
    return docs


def tokenize(text):
    return [token for token in TOKEN_RE.findall(text.lower()) if len(token) > 1 and token not in STOP_WORDS]


def build_index(docs):
    terms = {doc_id: Counter(tokenize(text)) for doc_id, text in docs.items()}
    df = Counter()
    for counts in terms.values():
        df.update(counts.keys())
    return terms, df


def static_rank(query, doc_ids, terms, df):
    query_terms = Counter(tokenize(query))
    if not query_terms:
        return list(doc_ids)
    total = len(doc_ids)
    scores = {}
    for doc_id in doc_ids:
        counts = terms[doc_id]
        length = sum(counts.values()) or 1
        score = 0.0
        for term, weight in query_terms.items():
            tf = counts.get(term, 0) / length
            idf = math.log(1.0 + total / (1 + df.get(term, 0)))
            score += weight * tf * idf
        scores[doc_id] = score
    return sorted(doc_ids, key=lambda item: (-scores[item], item))


def live_rank(query, api_url, retrieval, ranking, limit, credentials):
    payload = json.dumps(
        {"query": query, "mode": retrieval, "ranking": ranking, "limit": limit, "sort": "relevance"}
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if credentials:
        token = base64.b64encode(f"{credentials[0]}:{credentials[1]}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token
    request = urllib.request.Request(api_url + "/api/search", data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    ranked = []
    for hit in body.get("results", []):
        name = Path(str(hit.get("filename") or hit.get("doc_id"))).stem
        ranked.append(name)
    return ranked


def dcg(grades):
    return sum((2 ** int(grade) - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def relevance_grades(ranked, qrels, k):
    return [qrels.get(doc_id, 0) for doc_id in ranked[:k]]


def ndcg_at_k(ranked, qrels, k):
    actual = dcg(relevance_grades(ranked, qrels, k))
    ideal_source = sorted(qrels.values(), reverse=True)[:k]
    ideal = dcg(ideal_source)
    return actual / ideal if ideal > 0 else 0.0


def mrr(ranked, qrels, k):
    for index, doc_id in enumerate(ranked[:k], start=1):
        if qrels.get(doc_id, 0) >= 1:
            return 1.0 / index
    return 0.0


def recall_at_k(ranked, qrels, k):
    relevant = {doc_id for doc_id, grade in qrels.items() if grade >= 1}
    if not relevant:
        return 0.0
    found = relevant.intersection(ranked[:k])
    return len(found) / len(relevant)


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[position]


def evaluate(queries, rank_fn, k):
    rows = []
    latencies = []
    for query in queries:
        started = time.perf_counter_ns()
        ranked = rank_fn(query["query"])
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        qrels = {item["doc_id"]: int(item["grade"]) for item in query["relevant"]}
        rows.append(
            {
                "id": query["id"],
                "query": query["query"],
                "ndcg": ndcg_at_k(ranked, qrels, k),
                "mrr": mrr(ranked, qrels, k),
                "recall": recall_at_k(ranked, qrels, k),
                "top": ranked[:k],
            }
        )
    summary = {
        "queries": len(rows),
        "k": k,
        "ndcg_at_k": sum(row["ndcg"] for row in rows) / len(rows) if rows else 0.0,
        "mrr": sum(row["mrr"] for row in rows) / len(rows) if rows else 0.0,
        "recall_at_k": sum(row["recall"] for row in rows) / len(rows) if rows else 0.0,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
    }
    return summary, rows


def main():
    parser = argparse.ArgumentParser(description="Deterministic smoke-scale IR evaluation.")
    parser.add_argument("--queries", type=Path, default=ROOT / "queries.jsonl")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--source", choices=["static", "live"], default="static")
    parser.add_argument("--api-url", default="http://127.0.0.1:5000")
    parser.add_argument("--retrieval", choices=["lexical", "semantic", "hybrid"], default="lexical")
    parser.add_argument("--ranking", choices=["tfidf", "bm25"], default="tfidf")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    queries = load_queries(args.queries)
    docs = load_docs(args.docs)
    if args.source == "static":
        terms, df = build_index(docs)
        doc_ids = sorted(docs)
        rank_fn = lambda text: static_rank(text, doc_ids, terms, df)
    else:
        credentials = None
        if os.getenv("EVAL_BASIC_USER") and os.getenv("EVAL_BASIC_PASS"):
            credentials = (os.environ["EVAL_BASIC_USER"], os.environ["EVAL_BASIC_PASS"])
        rank_fn = lambda text: live_rank(
            text, args.api_url.rstrip("/"), args.retrieval, args.ranking, args.k, credentials
        )

    summary, rows = evaluate(queries, rank_fn, args.k)
    print(f"source={args.source} documents={len(docs)} queries={summary['queries']} k={args.k}")
    print(
        f"nDCG@{args.k}={summary['ndcg_at_k']:.4f} "
        f"MRR={summary['mrr']:.4f} Recall@{args.k}={summary['recall_at_k']:.4f} "
        f"p50={summary['latency_p50_ms']:.3f}ms p95={summary['latency_p95_ms']:.3f}ms"
    )
    if args.verbose:
        for row in rows:
            print(f"{row['id']} {row['query']!r} ndcg={row['ndcg']:.3f} mrr={row['mrr']:.3f} recall={row['recall']:.3f}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"summary": summary, "queries": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
