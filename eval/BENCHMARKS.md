# Benchmark Report

Generated on 2026-11-25 on Linux, Python 3.14.8, 20 logical CPUs, 16 GB RAM. The benchmark is a deterministic local harness over generated text files, not the production Flask search path.

## Workload

- Corpus: 5 topics, stable per-document seed, short Markdown-like text.
- Queries: 1–3 vocabulary terms seeded with 11.
- Timer: `time.perf_counter_ns`.
- Commands:

```bash
python3 benchmarks/generate_corpus.py --count 10000
python3 benchmarks/run_benchmark.py --corpus benchmarks/data/corpus_10000 --queries 200 --json eval/results/benchmark-10k.json
python3 benchmarks/generate_corpus.py --count 100000 --out benchmarks/data/corpus_100000
python3 benchmarks/run_benchmark.py --corpus benchmarks/data/corpus_100000 --queries 300 --json eval/results/benchmark-100k.json
```

## Results

| Documents | Index seconds | Docs/sec | Search p50 ms | Search p95 ms | Search p99 ms |
|---|---:|---:|---:|---:|---:|
| 10,000 | 0.181 | 55,282 | 1.242 | 3.332 | 4.236 |
| 100,000 | 2.472 | 40,445 | 17.422 | 42.418 | 63.671 |

## Interpretation

- The 10k warm lexical search target of p95 <100 ms is met by this harness.
- The 100k run completes without corruption or OOM and stays below 100 ms p95 in the local harness.
- This harness measures a simplified in-memory postings implementation, not the SQLite-backed service, tokenizer, analyzer, HTTP layer, or embeddings.
- Production latency, peak RSS, WAL size, concurrency, and hybrid/vector cost remain unmeasured. Do not treat these numbers as production SLO evidence.
- Generated corpora and JSON reports are ignored by Git; regenerate them with the commands above.
