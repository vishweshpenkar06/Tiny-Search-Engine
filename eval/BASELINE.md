# Baseline — Legacy TF-IDF

Command used to record the frozen baseline:

```
python3 eval/generate_fixtures.py
python3 eval/run_eval.py --source static --ranking tfidf --split test --json eval/results/baseline-test.json
```

## Fixture set

- 100 Markdown documents in `eval/docs/`, five topics, 20 documents per topic.
- 50 graded queries in `eval/queries.jsonl`; grades are 0–3 and an unlisted document has grade 0.
- 35 development queries (`split=dev`) and 15 held-out queries (`split=test`). Ranking features must be tuned only on `dev`.
- Cut-off `k = 10`. Ties are broken by document id so repeated runs are byte-identical.
- Fixtures are regenerated deterministically by `eval/generate_fixtures.py`.

## Exact metric definitions

For a query with relevance grades `g_1 ... g_k` in retrieved rank order and a set of relevant documents `R` (grade >= 1):

- `DCG@k = sum over i=1..k of (2 ** g_i - 1) / log2(i + 1)`
- `IDCG@k = DCG@k` over the grades sorted descending, padded with zeros to length k.
- `nDCG@k = DCG@k / IDCG@k`, or `0` when `IDCG@k` is `0`.
- `MRR = mean over queries of 1 / rank_of_first_document_with_grade >= 1`, or `0` when none is found.
- `Recall@k = |top_k retrieved intersect R| / |R|`, or `0` when `R` is empty.
- Latency is measured with `time.perf_counter_ns` around ranking only; p50 and p95 are nearest-rank percentiles in milliseconds.

The aggregate nDCG, MRR and Recall are unweighted means over the selected split. These definitions are implemented once in `eval/run_eval.py` and are shared by the static and live modes.

## Recorded results

| Split | Queries | nDCG@10 | MRR | Recall@10 | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| all | 50 | 0.7817 | 1.0000 | 0.7836 | 0.085 | 0.110 |
| dev | 35 | 0.7881 | 1.0000 | 0.7974 | 0.086 | 0.111 |
| test | 15 | 0.7668 | 1.0000 | 0.7515 | 0.143 | 0.171 |

The static ranker is the legacy TF-IDF implementation: lowercase alphanumeric tokens, a small stop-word list, `tf = count / document_length`, `idf = log(1 + N / (1 + df))`, and score `sum(tf * idf)` over query terms. No stemming, synonyms, fuzzy expansion, field boosts or vectors are used.

## Interpretation

Use the `test` row as the comparison baseline. Queries are synthetic and each contains a dominant term, so MRR saturates at 1.0 and cannot discriminate ranking systems. Differences below roughly 0.02 nDCG on a 15-query split should not be treated as improvements; report paired per-query differences and confidence intervals before claiming a win.

See `eval/RESULTS.md` for recorded ranking variants and limitations.
