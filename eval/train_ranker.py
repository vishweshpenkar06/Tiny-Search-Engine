import argparse
import json
import math
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT.parent / "backend" / "core" / "ranker_weights.json"


def fetch_scores(api_url, query, ranking, mode, limit):
    payload = json.dumps(
        {
            "query": query,
            "ranking": ranking,
            "mode": mode,
            "fuzzy": False,
            "limit": limit,
            "sort": "relevance",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        api_url.rstrip("/") + "/api/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    return {Path(str(hit.get("filename", hit["doc_id"]))).stem: float(hit["raw_score"]) for hit in body.get("results", [])}


def normalize(scores):
    maximum = max(scores.values(), default=0.0)
    if maximum <= 0.0:
        return {}
    return {doc_id: value / maximum for doc_id, value in scores.items() if value > 0.0}


def ndcg_at_k(ranked, qrels, k):
    actual = sum((2 ** qrels.get(doc_id, 0) - 1) / math.log2(index + 2) for index, doc_id in enumerate(ranked[:k]))
    ideal = sorted(qrels.values(), reverse=True)[:k]
    ideal_dcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal))
    return actual / ideal_dcg if ideal_dcg > 0 else 0.0


def load_queries(path, split):
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if split == "all" or row.get("split", "dev") == split:
                rows.append(row)
    return rows


def build_examples(queries, api_url, limit):
    examples = []
    for row in queries:
        bm25 = normalize(fetch_scores(api_url, row["query"], "bm25", "lexical", limit))
        tfidf = normalize(fetch_scores(api_url, row["query"], "tfidf", "lexical", limit))
        semantic = normalize(fetch_scores(api_url, row["query"], "bm25", "semantic", limit))
        qrels = {item["doc_id"]: int(item["grade"]) for item in row["relevant"]}
        examples.append((bm25, tfidf, semantic, qrels))
    return examples


def evaluate_weights(examples, weights, k=10):
    total = 0.0
    for bm25, tfidf, semantic, qrels in examples:
        scores = {}
        for doc_id in set(bm25) | set(tfidf) | set(semantic):
            scores[doc_id] = (
                weights["bm25"] * bm25.get(doc_id, 0.0)
                + weights["tfidf"] * tfidf.get(doc_id, 0.0)
                + weights["semantic"] * semantic.get(doc_id, 0.0)
            )
        ranked = sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))
        total += ndcg_at_k(ranked, qrels, k)
    return total / len(examples) if examples else 0.0


def search_weights(examples, validation_examples=None):
    target = validation_examples if validation_examples else examples
    best = {"bm25": 0.34, "tfidf": 0.33, "semantic": 0.33}
    best_score = evaluate_weights(target, best)
    for a in range(0, 101, 5):
        for b in range(0, 101 - a, 5):
            candidate = {"bm25": a / 100, "tfidf": b / 100, "semantic": (100 - a - b) / 100}
            score = evaluate_weights(target, candidate)
            if score > best_score:
                best, best_score = candidate, score
    for key in best:
        for delta in (-0.02, -0.01, 0.01, 0.02):
            candidate = dict(best)
            candidate[key] = max(0.0, min(1.0, candidate[key] + delta))
            total = sum(candidate.values())
            candidate = {name: value / total for name, value in candidate.items()}
            score = evaluate_weights(target, candidate)
            if score > best_score:
                best, best_score = candidate, score
    return best, best_score


def main():
    parser = argparse.ArgumentParser(description="Train linear ranking weights on dev queries only.")
    parser.add_argument("--api-url", default="http://127.0.0.1:5000")
    parser.add_argument("--queries", type=Path, default=ROOT / "queries.jsonl")
    parser.add_argument("--split", choices=["dev"], default="dev")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--validation", type=int, default=0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    queries = load_queries(args.queries, args.split)
    if not queries:
        raise SystemExit("no dev queries found")
    examples = build_examples(queries, args.api_url, args.limit)
    validation = examples[-args.validation:] if args.validation > 0 else None
    train = examples[:-args.validation] if args.validation > 0 else examples
    weights, score = search_weights(train, validation)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(weights, sort_keys=True) + "\n", encoding="utf-8")
    print(f"dev_ndcg@10={score:.4f} queries={len(queries)} weights={json.dumps(weights, sort_keys=True)}")


if __name__ == "__main__":
    main()
