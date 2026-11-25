# Evaluation Results

All results below use the frozen fixture in `eval/`: 100 documents, 50 graded queries, 35 development queries and 15 held-out queries. Regenerate with:

```
python3 eval/generate_fixtures.py
python3 eval/run_eval.py --source static --ranking tfidf --split test --json eval/results/baseline-test.json
python3 eval/run_eval.py --source live --api-url http://127.0.0.1:5000 --ranking <ranking> --retrieval <mode> --split test --json eval/results/<name>.json
python3 eval/train_ranker.py --api-url http://127.0.0.1:5000 --validation 10 --out backend/core/ranker_weights.json
```

Live queries explicitly send `fuzzy: false` for controlled ranking comparisons. Metric definitions, cutoff, and tie-breaking are fixed in `eval/BASELINE.md`.

## Results

| Configuration | Split | nDCG@10 | MRR | Recall@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|
| static TF-IDF baseline | test | 0.7668 | 1.0000 | 0.7515 | 0.143 | 0.171 |
| static TF-IDF baseline | all | 0.7817 | 1.0000 | 0.7836 | 0.085 | 0.110 |
| live TF-IDF, 100 docs | test | 0.9032 | 1.0000 | 0.7315 | 2.032 | 4.968 |
| live BM25, 100 docs | test | 0.8224 | 1.0000 | 0.7315 | 2.238 | 5.904 |
| live semantic, BGE small, corrected passage encoding | dev | 0.7853 | 0.9667 | 0.7434 | 13.957 | 40.744 |
| live hybrid, RRF k=60, corrected passage encoding | dev | 0.8012 | 1.0000 | 0.7468 | 16.916 | 43.862 |
| live hybrid, RRF k=10, pre-fix vectors | dev | 0.8145 | 1.0000 | 0.7577 | 24.728 | 36.183 |
| live semantic, BGE small, corrected passage encoding | test | 0.7399 | 0.9556 | 0.6994 | 12.706 | 22.646 |
| live hybrid, RRF k=10, pre-fix vectors | test | 0.8163 | 1.0000 | 0.7376 | 41.825 | 614.968 |
| live hybrid, RRF k=60, corrected passage encoding | test | 0.7987 | 1.0000 | 0.7242 | 26.982 | 49.550 |
| live learned, weights fit on all dev | dev | 0.8641 | 1.0000 | 0.7574 | 13.533 | 39.750 |
| live learned, weights fit on all dev | test | 0.8652 | 1.0000 | 0.7248 | 33.766 | 54.121 |
| live learned, 25/10 dev train/validation | dev | 0.8815 | 1.0000 | — | — | — |
| live learned, 25/10 dev train/validation | test | 0.8458 | 1.0000 | 0.7248 | 14.191 | 48.522 |
| live BM25, semantic-indexed corpus | test | 0.8224 | 1.0000 | 0.7315 | 5.896 | 15.511 |

Development sweeps over BM25 `k1`/`b`, field boosts, all-terms bonus, phrase proximity, and BM25/TF-IDF blending did not beat TF-IDF on dev, so those speculative knobs were removed. RRF `k=10` won on dev with the pre-fix vectors but lost on held-out, so the default remains `k=60`. A review found that indexed documents had been encoded with the query prefix; `embed_document` now uses the passage path and all corrected rows were regenerated from a fresh index.

The learned ranker linearly combines normalized BM25, TF-IDF and semantic scores. The committed weights come from a 25-query train / 10-query dev-validation split; held-out queries were never used for training or weight selection. The learned mode beats BM25 and hybrid on held-out but still loses to TF-IDF.

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

BM25, semantic, hybrid, and learned modes are implemented and measured, but none beats TF-IDF on the held-out split. Do not claim a relevance improvement without a new held-out result showing it.
