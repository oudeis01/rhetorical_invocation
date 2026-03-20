# Data

All data files are included in this repository. No external download required.

## Files

| File | Size | Description |
|:-----|:-----|:------------|
| corpus_features.jsonl.gz | 3.1 MB | NPC, nMCE, DMI per document (60,480 art + 1,657 DOAJ docs) |
| at_scores_llama.jsonl.gz | 2.7 MB | Logprob pairs, Llama-3.3-70B-Instruct (177,123 art + 10,143 DOAJ pairs) |
| at_scores_qwen.jsonl.gz | 2.0 MB | Logprob pairs, Qwen-2.5-72B-Instruct (77,219 art + 6,586 DOAJ pairs) |
| url_category_map.json.gz | 1.4 MB | URL to {institution, category} for 60,480 art docs |
| discourse_keywords_v3.json | 13 KB | 530 discourse keywords across 8 categories |

A Zenodo DOI will be added at paper submission for archival citation.

## corpus_features.jsonl.gz schema

```json
{
  "doc_id":                 "https://...",
  "institution":            "artforum",
  "url_category":           "features",
  "word_count":             1423,
  "total_nouns":            312,
  "npc_pre":                0.221,
  "npc_post":               0.318,
  "nmce":                   0.971,
  "dmi_liberal":            0.089,
  "dmi_conservative":       0.027,
  "dmi_zero":               false,
  "total_keyword_matches":  14
}
```

DOAJ docs have "institution": "doaj" and "url_category": "article".
Fields are null where not computable (e.g., npc_pre when total_nouns < 5).

## at_scores_llama.jsonl.gz / at_scores_qwen.jsonl.gz schema

```json
{
  "doc_id":          "https://...",
  "institution":     "artforum",
  "url_category":    "features",
  "discourse":       "ecology",
  "at_value":        0.034,
  "top_alternatives": [
    {"token": "3", "prob": 0.72},
    {"token": "2", "prob": 0.18},
    {"token": "4", "prob": 0.06}
  ]
}
```

Each row is one (document, discourse) pair. at_value = P(depth=4) + P(depth=5)
extracted from the model's log-probabilities at the depth_level token position.

## url_category_map notes

Categories combine URL path patterns with raw HTML metadata for five institutions
(stedelijk, spikeart, afterall, moussemagazine, neuralit). The generation script
requires raw crawl data not distributed here. The pre-computed map is sufficient
to reproduce all paper analyses.
