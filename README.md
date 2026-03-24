# Rhetorical Invocation: Replication Repository

Replication code and data for:

> Rhetorical Invocation: A Four-Layer Computational Analysis of Discourse Vocabulary in Institutional Art Writing
> Haram Choi, 2026


---

## Quick Start

```bash
git clone https://github.com/oudeis01/rhetorical_invocation
cd rhetorical_invocation

pip install -r requirements.txt

python analysis/layer1_npc.py
python analysis/layer2_nmce.py
python analysis/layer3_dmi.py
python analysis/layer4_at.py
python analysis/cross_layer.py
```

Results are written to `output/`.

---

## Repository Structure

```
rhetorical_invocation/
├── analysis/
│   ├── layer1_npc.py               Section 4: Noun Phrase Complexity
│   ├── layer2_nmce.py              Section 5: Normalized Modifier Collocation Entropy
│   ├── layer3_dmi.py               Section 6: Discourse Marker Interaction
│   ├── layer4_at.py                Section 7: Analytical Tendency (logprob-based)
│   ├── cross_layer.py              Section 7.4: Cross-layer Spearman correlation matrix
│   └── collocation_concentration.py  Table 5.0: Corpus-level collocation top-1 share
│
├── data/
│   ├── README.md
│   ├── at_scores_llama.jsonl.gz     Logprob pairs, Llama-3.3-70B-Instruct
│   ├── at_scores_qwen.jsonl.gz      Logprob pairs, Qwen-2.5-72B-Instruct
│   ├── corpus_features.jsonl.gz     NPC, nMCE, DMI per document
│   ├── discourse_keywords.json      530 keywords across 8 discourses
│   ├── url_category_map.json.gz     URL → {institution, category} mapping
│   └── samples/
│       └── corpus_features_sample.jsonl  100-doc stratified sample
│
├── docs/
│   ├── pipeline_overview.md   Full pipeline description (crawling → scoring)
│   ├── corpus_construction.md Crawling methodology (documentation only)
│   ├── llm_preprocessing.md   LLM filter methodology (documentation only)
│   └── prompts/
│       ├── depth_rubric.md         L0–L5 rubric (standalone citable)
│       ├── layer4_system_prompt.md System prompt template
│       └── layer4_user_prompt.md   User prompt template
│
├── output/                    Generated results (gitignored except .gitkeep)
├── requirements.txt
├── LICENSE                    MIT (code)
└── LICENSE_DATA               CC BY 4.0 (derived data)
```

---

## Data

### Included in this repository

- `corpus_features.jsonl.gz` — NPC, nMCE, DMI per document (60,480 art + 1,657 DOAJ docs)
- `at_scores_llama.jsonl.gz` — Logprob pairs, Llama-3.3-70B-Instruct (177,123 art + 10,143 DOAJ pairs)
- `at_scores_qwen.jsonl.gz` — Logprob pairs, Qwen-2.5-72B-Instruct (77,219 art + 6,586 DOAJ pairs)
- `data/discourse_keywords.json` — 530 discourse keywords across 8 categories
- `data/url_category_map.json.gz` — URL-to-category mapping (60,480 art docs)
- `data/samples/` — 100-doc stratified sample for testing

### corpus_features.jsonl.gz Schema

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

DOAJ docs have `"institution": "doaj"` and `"url_category": "article"`.
Fields are `null` where not computable (e.g., `npc_pre` when `total_nouns < 5`).

---

## Analysis Scripts

Each script reads from `data/` and writes to `output/`. All scripts accept
`--help` for options.

### Section 4 — NPC (`analysis/layer1_npc.py`)

Reproduces the NPC aggregate and length-adjusted tables (Section 4).
Computes NPC-Pre and NPC-Post, Cohen's d, TOST equivalence test (Δ = ±0.20),
and OLS length-adjusted d.

```bash
python analysis/layer1_npc.py --data data/corpus_features.jsonl.gz
```

Expected output (Art vs DOAJ):
- NPC-Post adjusted d = −0.12 (paper: −0.12)

### Section 5 — nMCE (`analysis/layer2_nmce.py`)

Reproduces the nMCE aggregate table and institution breakdown (Section 5).
Computes normalized Modifier Collocation Entropy, Cohen's d, length-adjusted d,
and per-institution values.

```bash
python analysis/layer2_nmce.py --data data/corpus_features.jsonl.gz
```

Expected output:
- Art mean nMCE = 0.972, d = +2.00 (paper: confirmed)
- All 13 institutions above DOAJ baseline, minimum d = +1.07

### Table 5.0 — Corpus-level collocations (`analysis/collocation_concentration.py`)

Reproduces Table 5.0 (top-1 collocation share per adjective, Art vs DOAJ).
Requires the raw `structural_results.jsonl` file (not distributed; see docs).

```bash
python analysis/collocation_concentration.py --data structural_results.jsonl
python analysis/collocation_concentration.py --data structural_results.jsonl --table-only
```

### Section 6 — DMI (`analysis/layer3_dmi.py`)

Reproduces the DMI aggregate table and zero-rate analysis (Section 6).
Computes Conservative/Liberal DMI, zero-rate, and Odds Ratio with 95% CI.

```bash
python analysis/layer3_dmi.py --data data/corpus_features.jsonl.gz
```

Expected output:
- Zero-rate: Art 60.1%, DOAJ 20.0% (paper: confirmed)
- OR = 5.48 [95% CI: 4.86, 6.18]

### Section 7 — AT (`analysis/layer4_at.py`)

Reproduces the AT aggregate, depth distribution, and content format tables
(Section 7). Computes Analytical Tendency from logprob data.

```bash
python analysis/layer4_at.py \
  --llama data/at_scores_llama.jsonl.gz \
  --catmap data/url_category_map.json.gz
```

Expected output:
- Art AT = 0.0523, DOAJ AT = 0.1851, ratio = 3.54× (paper: confirmed)

### Section 7.4 — Cross-layer (`analysis/cross_layer.py`)

Reproduces the Spearman rank correlation matrix (Section 7.4).

```bash
python analysis/cross_layer.py \
  --features data/corpus_features.jsonl.gz \
  --at data/at_scores_llama.jsonl.gz
```

Expected: NPC-Post × DMI(Liberal) ≈ 0 (paper: ρ = −0.009, ns)

---

## Reproducibility Notes

### What is fully reproducible

All four layer statistics and cross-layer correlations reproduce from the
provided data without GPU access.

### What requires GPU (documented only)

- Layer IV logprob scoring: requires vLLM + Llama-3.3-70B or Qwen-2.5-72B
- LLM corpus filtering: requires any instruction-following model
- Full pipeline: crawling → filtering → NPC/nMCE/DMI parsing → LLM scoring

See `docs/pipeline_overview.md` for the complete pipeline description.
See `docs/prompts/` for all prompts and rubrics.

### Minor numerical differences

Computed values may differ slightly from paper values due to corpus version
differences. The analysis pipeline was applied to the corpus as it existed
at time of writing (2026-03-07 for LLM runs).

Key paper values that are exactly reproduced from the data:
- Art AT = 0.0523, DOAJ AT = 0.1851, ratio 3.54×
- spikeart/essay AT = 0.3406, 184% of DOAJ
- stedelijk/Journal Article AT = 0.2634, 142%
- afterall/essay AT = 0.2164, 117%

---

## Citation

If you use this code or data, please cite:

```bibtex
@misc{choi2026rhetorical,
  title     = {Rhetorical Invocation: A Four-Layer Computational Analysis 
               of Discourse Vocabulary in Institutional Art Writing},
  author    = {Choi, Haram},
  year      = {2026},
  publisher = {SocArXiv},
  doi       = {10.31235/osf.io/4au72_v1},
  url       = {https://doi.org/10.31235/osf.io/4au72_v2},
  note      = {Preprint. Submitted to \textit{Humanities and Social 
               Sciences Communications}}
}
}
```

For the depth rubric specifically:

```bibtex
@misc{rhetorical_invocation_rubric,
  title  = {Layer IV Depth Rubric (L0-L5) for Discourse Engagement Analysis},
  author = {Choi, Haram},
  year   = {2026},
  url    = {https://github.com/oudeis01/rhetorical_invocation/blob/main/docs/prompts/depth_rubric.md}
}
```

---

## License

- Code: MIT License (see `LICENSE`)
- Derived data: CC BY 4.0 (see `LICENSE_DATA`)
- Original corpus texts: copyright of respective publishers; not distributed
