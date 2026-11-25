# Evaluation Results

All results below use the frozen fixture in `eval/`: 100 documents, 50 graded queries, 35 development queries and 15 held-out queries. Regenerate with:

```
python3 eval/generate_fixtures.py
python3 eval/run_eval.py --source static --ranking tfidf --split test --json eval/results/baseline-test.json
python3 eval/run_eval.py --source live --api-url http://127.0.0.1:5000 --ranking <ranking> --retrieval <mode> --split test --json eval/results/<name>.json
```

Live queries explicitly send `fuzzy: false` for controlled ranking comparisons. Metric definitions, cutoff, and tie-breaking are fixed in `eval/BASELINE.md`.

## Results

| Configuration | Split | nDCG@10 | MRR | Recall@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|
| static TF-IDF baseline | test | 0.7668 | 1.0000 | 0.7515 | 0.143 | 0.171 |
| static TF-IDF baseline | all | 0.7817 | 1.0000 | 0.7836 | 0.085 | 0.110 |
| live TF-IDF, 100 docs | test | 0.9032 | 1.0000 | 0.7315 | 2.032 | 4.968 |
| live BM25, 100 docs | test | 0.8224 | 1.0000 | 0.7315 | 2.238 | 5.904 |
| live semantic, BGE small | dev | 0.7853 | 0.9667 | 0.7434 | 25.562 | 38.153 |
| live hybrid, RRF k=60 | dev | 0.8012 | 1.0000 | 0.7468 | 11.956 | 39.967 |
| live hybrid, RRF k=10 | dev | 0.8145 | 1.0000 | 0.7577 | 24.728 | 36.183 |
| live semantic, BGE small | test | 0.7399 | 0.9556 | 0.6994 | 14.557 | 18.610 |
| live hybrid, RRF k=10 | test | 0.8163 | 1.0000 | 0.7376 | 41.825 | 614.968 |
| live BM25, semantic-indexed corpus | test | 0.8224 | 1.0000 | 0.7315 | 5.896 | 15.511 |

Development sweeps over BM25 `k1`/`b`, field boosts, all-terms bonus, phrase proximity, and BM25/TF-IDF blending did not beat TF-IDF on dev, so those speculative knobs were removed. RRF `k=10` won on dev but lost on held-out, so the default remains `k=60`.

## Offline verification

The semantic and hybrid rows were produced with `HF_HUB_OFFLINE=1` and a vendored `BAAI/bge-small-en-v1.5` FastEmbed model. Model loading and query encoding succeeded with no network access.

## Honest limitations

- Queries are synthetic and hand-authored alongside the documents. MRR saturates at 1.0 and cannot discriminate between configurations.
- The held-out set has only 15 queries. Differences below 0.02 nDCG@10 should be treated as noise.
- No paired-bootstrap confidence intervals are computed.
- Live results exercise the real API, index, analyzer, normalization, and embedding provider, but use one process and no concurrency.
- The live fixture maps results to qrels through original upload filenames.
- Hybrid p95 includes outlier latency from the ONNX runtime and is not a production SLO measurement.
- The spec's 15% relative nDCG improvement target is **not met** by these results.

## Claim discipline

BM25, semantic, and hybrid modes are implemented and measured, but none beats TF-IDF on the held-out split. Do not claim a relevance improvement without a new held-out result showing it.
