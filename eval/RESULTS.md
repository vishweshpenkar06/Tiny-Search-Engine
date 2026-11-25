# Evaluation Results

All results below use the frozen fixture in `eval/`: 100 documents, 50 graded queries, 35 development queries and 15 held-out queries. Regenerate with:

```
python3 eval/generate_fixtures.py
python3 eval/run_eval.py --source static --ranking tfidf --split test --json eval/results/baseline-test.json
python3 eval/run_eval.py --source live --api-url http://127.0.0.1:5000 --ranking <ranking> --split test --json eval/results/<name>.json
```

Live queries explicitly send `fuzzy: false` for controlled ranking comparisons. Metric definitions, cutoff, and tie-breaking are fixed in `eval/BASELINE.md`.

## Results

| Configuration | Split | nDCG@10 | MRR | Recall@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|
| static TF-IDF baseline | test | 0.7668 | 1.0000 | 0.7515 | 0.143 | 0.171 |
| static TF-IDF baseline | all | 0.7817 | 1.0000 | 0.7836 | 0.085 | 0.110 |
| live TF-IDF, 100 docs | test | 0.9032 | 1.0000 | 0.7315 | 2.032 | 4.968 |
| live BM25, 100 docs | test | 0.8224 | 1.0000 | 0.7315 | 2.238 | 5.904 |

Development-set BM25 sweeps over `BM25_K1`/`BM25_B` reached at most 0.8058 nDCG@10, so no held-out BM25 win was claimed.

## Honest limitations

- Queries are synthetic and hand-authored alongside the documents. MRR saturates at 1.0 and cannot discriminate between configurations.
- The held-out set has only 15 queries. Differences below 0.02 nDCG@10 should be treated as noise.
- No paired-bootstrap confidence intervals are computed.
- Live results exercise the real API, index, analyzer, and score normalization, but use one process and no concurrency.
- The live fixture maps results to qrels through original upload filenames.
- Hybrid and semantic modes are wired and smoke-tested but are not evaluated on this gold set.
- The spec's 15% relative nDCG improvement target is **not met** by these results.

## Claim discipline

BM25 is implemented and selectable, but on this fixture it does **not** beat TF-IDF. Do not claim a relevance improvement without a new held-out result showing it.
