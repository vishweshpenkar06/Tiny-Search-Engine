# Evaluation Results

This file is the reporting template for ranking changes. Fill one row per configuration, keep the command that produced it, and never overwrite the baseline in `BASELINE.md`.

## How to produce a row

```
python3 eval/run_eval.py --source static --ranking tfidf --json eval/results/<name>.json
python3 eval/run_eval.py --source live --api-url http://127.0.0.1:5000 --ranking bm25 --retrieval lexical --json eval/results/<name>.json
```

Metric definitions, cut-off and tie-breaking are fixed in `BASELINE.md` and implemented once in `eval/run_eval.py`.

## Results

| Configuration | nDCG@10 | MRR | Recall@10 | p50 ms | p95 ms | Command / commit |
|---|---|---|---|---|---|---|
| static TF-IDF (baseline) | 0.9732 | 1.0000 | 0.9167 | 0.030 | 0.053 | `python3 eval/run_eval.py --source static --ranking tfidf` |
| live BM25, 20 docs | 0.9653 | 1.0000 | 0.8333 | 1.831 | 6.612 | `python3 eval/run_eval.py --source live --ranking bm25 --api-url http://127.0.0.1:5000 --json eval/results/live-bm25.json` |
| live TF-IDF, 20 docs | 0.9636 | 1.0000 | 0.8333 | 1.351 | 4.670 | `python3 eval/run_eval.py --source live --ranking tfidf --api-url http://127.0.0.1:5000 --json eval/results/live-tfidf.json` |

## Honest limitations

- The fixture has 20 documents and 12 queries. It is a CI smoke test, not a quality benchmark.
- Five topics with one obvious keyword per query make MRR saturate at 1.0. MRR cannot discriminate between configurations here.
- Grades are hand authored by the same person who wrote the documents, so they encode intent rather than user behaviour.
- Static mode measures a small Python loop, not the production index, tokenizer or ORM. Live mode is required to exercise the real service.
- Live mode maps results to fixture ids through the returned filename stem. It assumes the fixtures were uploaded with their original names; otherwise metrics are undefined.
- Latency is ranking time only. It excludes HTTP transport, JSON encoding and network variation, and it was measured on one machine with no concurrency.
- No confidence intervals or significance tests are computed. Treat differences below 0.02 nDCG@10 as noise.
- The IMPROVE spec asks for 50 queries, 100 documents and a 100k-doc load test. Those targets are not met by this smoke set; use `benchmarks/` for scale measurements.
- Semantic and hybrid modes require a local embedding model and are not evaluated here. Their interface is wired in the API but no scores are claimed.

## Claim discipline

Do not claim that BM25, synonyms, fuzzy matching or hybrid retrieval improves this dataset unless a row above shows it with the same command and fixture revision. A missing row means an unmeasured claim.
