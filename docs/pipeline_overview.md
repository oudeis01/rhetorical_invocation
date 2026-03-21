# Pipeline Overview

End-to-end pipeline for *Rhetorical Invocation: A Four-Layer Computational Analysis of Discourse Vocabulary in Institutional Art Writing*.

This document describes the full pipeline from web crawling to Layer IV scoring. The analysis scripts in `analysis/` reproduce all paper statistics from the pre-computed data in `data/`. The crawling and LLM preprocessing stages are documented here for transparency but require raw crawl data not distributed in this repository.

---

## Pipeline Stages

```
Stage 1: Web crawl
   ↓ raw HTML / DOM
Stage 2: DOM extraction + block segmentation
   ↓ structured content blocks per page
Stage 3: Phase 1 LLM classification (block type)
   ↓ CURATORIAL blocks identified
Stage 4: Phase 2 LLM classification (depth grade)
   ↓ A1 + A2 pages retained
Stage 5: Structural parsing (NPC, nMCE, DMI)
   ↓ corpus_features.jsonl.gz
Stage 6: Layer IV LLM scoring (AT)
   ↓ at_scores_llama.jsonl.gz, at_scores_qwen.jsonl.gz
Stage 7: Analysis scripts
   ↓ paper statistics
```

See `docs/corpus_construction.md` for Stage 1–2. See `docs/llm_preprocessing.md` for Stages 3–4.

---

## Stage 5: Structural Parsing

**Parser:** spaCy `en_core_web_trf` (transformer-based dependency parser)

**NPC (Layers I):** Dependency relations counted per document:
- NPC-Pre: `amod` + `advmod` relations, normalised by total nouns
- NPC-Post: `prep` + `relcl` + `appos` + `acl` relations, normalised by total nouns
- Documents with fewer than 5 parsed nouns are excluded.

**nMCE (Layer II):** Shannon entropy of IAE-qualifying adjective–noun pairs within each document, normalised by log₂(K) where K = number of unique qualifying adjectives. Documents with K < 2 are excluded. IAE suffix filter: `-ic, -al, -ive, -ary, -ist, -ous, -ian`. Stop-list: 48 high-frequency non-specialised forms.

**DMI (Layer III):** For each discourse keyword match, the dependency tree is traversed to depth 4 (`max_depth=4`). Explicit logical connectives within that radius are counted. Two parallel metrics: Liberal (all connectives) and Conservative (unambiguous markers only: `because, therefore, thus, however, although` and equivalents). Connective lexicon follows Penn Discourse TreeBank (Prasad et al., 2008) and ISO 24617-8.

---

## Stage 6: Layer IV AT Scoring

### Hardware

| Stage | Hardware | Memory |
|:--|:--|:--|
| Corpus construction (Phase 1+2) | NVIDIA GeForce RTX 4080 | 16 GB GDDR6X |
| Layer IV scoring — art corpus (60,777 docs) | AMD Instinct MI300X | 191 GB HBM3 |
| Layer IV scoring — DOAJ baseline (1,673 docs) | AMD Instinct MI300X | 191 GB HBM3 |

The RTX 4080 workstation ran corpus filtering locally via a persistent vLLM server. The MI300X scoring ran in a containerised ROCm environment (`rocm/7.0` base image) on a cloud instance.

### Models

| Role | HuggingFace model ID | Quantization |
|:--|:--|:--|
| Corpus filtering (Phase 1+2) | `Qwen/Qwen2.5-14B-Instruct-AWQ` | AWQ (4-bit) |
| Layer IV primary scorer | `RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic` | FP8 dynamic |
| Layer IV cross-validation scorer | `CalamitousFelicitousness/Qwen2.5-72B-Instruct-fp8-dynamic` | FP8 dynamic |

### Inference Framework

| Stage | Framework | Version |
|:--|:--|:--|
| Corpus filtering | vLLM | 0.11.2 |
| Layer IV AT scoring (MI300X) | vLLM (ROCm container) | 0.10.1 |

### Logprob Extraction

Log-probabilities were extracted via the vLLM OpenAI-compatible API (`/v1/chat/completions`) with `logprobs=True` and `top_logprobs=5`.

For each (document, discourse) pair, the pipeline parses the model's response to identify the first output token of the `depth_level` JSON field. The probability of each candidate label token is read from the `top_logprobs` array. Tokens absent from the top-5 list receive residual probability mass divided equally among the remaining candidates.

The AT metric is defined as:

```
AT(doc, discourse) = P(depth=4) + P(depth=5)
```

where probabilities are read from the model's token-level distribution, not from its generated text. This bypasses the generative halo effect: the rubric criteria (causal explanation, sustained argument, theoretical integration) are defined independently of academic surface style, making scores structurally harder to inflate through vocabulary choice alone.

### Scoring scope

Each document is scored against every discourse category whose keywords appear in the document. The full art corpus produced 177,123 (document, discourse) pairs for Llama and 77,219 for Qwen. The DOAJ baseline produced 10,143 and 6,586 pairs respectively.

---

## Reproducibility

All four layer statistics and cross-layer correlations reproduce from the provided data files without GPU access. See `README.md` for the expected output values from each analysis script.

The raw corpus texts are not distributed (copyright of respective publishers). The crawling and LLM preprocessing stages therefore cannot be re-executed from this repository alone. The pre-computed data files (`corpus_features.jsonl.gz`, `at_scores_*.jsonl.gz`) are the reproducibility artefacts.
