import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
QUERIES = ROOT / "queries.jsonl"

TOPICS = {
    "python": ["python", "generator", "comprehension", "decorator", "context", "memory", "function", "list"],
    "database": ["sqlite", "transaction", "rollback", "join", "table", "schema", "query", "commit"],
    "network": ["tcp", "http", "dns", "tls", "latency", "packet", "socket", "cache"],
    "algorithms": ["retrieval", "index", "ranking", "bm25", "tfidf", "relevance", "snippet", "corpus"],
    "operations": ["docker", "container", "compose", "volume", "deploy", "healthcheck", "limit", "image"],
}

DETAIL = "measure compare describe explain improve track report guide"


def document_text(topic, words, number, primary, secondary):
    detail = DETAIL[number % len(DETAIL)]
    return (
        f"# {primary.title()} note {number:02d}\n\n"
        f"## {secondary.title()} in {topic}\n\n"
        f"This {topic} document will {detail} {primary} together with {secondary}. "
        f"It records how {primary} affects {secondary} and why the result is reproducible. "
        f"Queries for {primary} should rank this note above unrelated {topic} material. "
        f"The note also discusses {words[(number + 5) % len(words)]} and {words[(number + 6) % len(words)]}.\n"
    )


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)

    grades = {}
    for topic, words in TOPICS.items():
        for number in range(1, 21):
            doc_id = f"{topic}-{number:02d}"
            primary = words[number % len(words)]
            secondary = words[(number + 3) % len(words)]
            (DOCS / f"{doc_id}.md").write_text(
                document_text(topic, words, number, primary, secondary), encoding="utf-8"
            )
            grades[doc_id] = (topic, primary, secondary, number)

    rows = []
    for topic, words in TOPICS.items():
        for index in range(10):
            primary = words[index % len(words)]
            secondary = words[(index + 2) % len(words)]
            relevant = []
            for doc_id, (doc_topic, doc_primary, doc_secondary, number) in grades.items():
                if doc_topic != topic:
                    continue
                grade = 0
                if doc_primary == primary:
                    grade = 3
                elif doc_secondary == primary or doc_primary == secondary:
                    grade = 2
                elif number <= 5:
                    grade = 1
                if grade:
                    relevant.append({"doc_id": doc_id, "grade": grade})
            rows.append(
                {
                    "id": f"{topic[:3]}-{index + 1:02d}",
                    "topic": topic,
                    "split": "dev" if index < 7 else "test",
                    "query": f"{primary} {secondary}",
                    "relevant": relevant,
                }
            )

    QUERIES.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"generated {len(grades)} documents and {len(rows)} queries")


if __name__ == "__main__":
    main()
