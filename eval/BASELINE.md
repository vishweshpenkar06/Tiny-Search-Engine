# Baseline — Legacy TF-IDF

Command used to record this baseline:

```
python3 eval/run_eval.py --source static --ranking tfidf --json eval/results/baseline.json
```

## Fixture set

- 20 Markdown documents in `eval/docs/`, five topics, four documents per topic.
- 12 graded queries in `eval/queries.jsonl`; grades are 0–3 and an unlisted document has grade 0.
- Cut-off `k = 10`. Ties are broken by document id so repeated runs are byte-identical.

## Exact metric definitions

For a query with relevance grades `g_1 ... g_k` in retrieved rank order and a set of relevant documents `R` (grade >= 1):

- `DCG@k = sum over i=1..k of (2 ** g_i - 1) / log2(i + 1)`
- `IDCG@k = DCG@k` over the grades sorted descending, padded with zeros to length k.
- `nDCG@k = DCG@k / IDCG@k`, or `0` when `IDCG@k` is `0`.
- `MRR = mean over queries of 1 / rank_of_first_document_with_grade >= 1`, or `0` when none is found.
- `Recall@k = |top_k retrieved intersect R| / |R|`, or `0` when `R` is empty.
- Latency is measured with `time.perf_counter_ns` around ranking only; p50 and p95 are nearest-rank percentiles in milliseconds.

The aggregate nDCG, MRR and Recall are unweighted means over all 12 queries. These definitions are implemented once in `eval/run_eval.py` and are shared by the static and live modes.

## Recorded result

| Source | nDCG@10 | MRR | Recall@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|
| static TF-IDF | 0.9732 | 1.0000 | 0.9167 | 0.030 | 0.053 |

The static ranker is the legacy TF-IDF implementation: lowercase alphanumeric tokens, a small stop-word list, `tf = count / document_length`, `idf = log(1 + N / (1 + df))`, and score `sum(tf * idf)` over query terms. No stemming, synonyms, fuzzy expansion, field boosts or vectors are used.

## Interpretation

This is a CI smoke fixture, not a meaningful quality estimate. With only 20 documents and one dominant term per query, TF-IDF already places the top document first for all 12 queries. The remaining gap comes from secondary relevant documents that are pushed past rank 10. Differences below roughly 0.02 nDCG on this set should not be treated as improvements.

See `eval/RESULTS.md` for the template used to record later ranking changes and for the full list of limitations.
