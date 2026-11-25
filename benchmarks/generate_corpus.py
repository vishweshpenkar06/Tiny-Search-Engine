import argparse
import random
from pathlib import Path

TOPICS = (
    ("retrieval", "index query rankingbm25 tfidf relevance snippet document corpus search"),
    ("database", "sqlite transaction rollback index join table schema query row commit"),
    ("network", "tcp http dns tls latency packet socket status cache handshake"),
    ("python", "generator comprehension decorator context manager list memory function"),
    ("operations", "docker container compose network volume deploy healthcheck limit image"),
)

CONNECTORS = ("with", "using", "for", "through", "during", "about", "across", "after")
VERBS = ("explains", "measures", "compares", "describes", "improves", "tracks", "reports", "guides")


def build_text(rng, topic):
    words = topic[1].split()
    subject = rng.choice(words)
    detail = rng.choice(words)
    action = rng.choice(VERBS)
    connector = rng.choice(CONNECTORS)
    extra = " ".join(rng.sample(words, k=min(8, len(words))))
    return (
        f"# {subject.title()} note {rng.randrange(1, 9999)}\n\n"
        f"This note {action} {subject} {connector} {detail}. "
        f"It records {extra} and keeps the result reproducible.\n\n"
        f"The topic is {topic[0]}. Each document has a stable identifier and a bounded length. "
        f"Queries for {subject} should find this note before unrelated topics.\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Generate a deterministic benchmark corpus.")
    parser.add_argument("--count", type=int, choices=[10000, 100000], default=10000)
    parser.add_argument("--out", type=Path, default=Path("benchmarks/data/corpus_10000"))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for number in range(args.count):
        rng = random.Random(args.seed * 1_000_003 + number)
        topic = TOPICS[number % len(TOPICS)]
        shard = args.out / f"shard-{number // 1000:04d}"
        shard.mkdir(exist_ok=True)
        target = shard / f"doc-{number:06d}.txt"
        target.write_text(build_text(rng, topic), encoding="utf-8")
    print(f"generated {args.count} documents in {args.out} with seed {args.seed}")


if __name__ == "__main__":
    main()
