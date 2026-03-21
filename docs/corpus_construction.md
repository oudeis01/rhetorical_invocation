# Corpus Construction

## Overview

The art corpus covers 13 major contemporary art institutions, period 2010–2025. The DOAJ academic baseline covers 1,673 peer-reviewed articles across 8 discourse categories, same period.

Both corpora target the same shared discourse vocabulary, making structural comparisons between the two registers meaningful.

---

## Art Corpus: Crawling and Extraction

### Institution selection

The 13 institutions were selected to represent a range of formats: critical magazines, artist-run platforms, museum publishing programmes, and international media art centres. The inclusion of ZKM, Ars Electronica, neuralit, and transmediale is deliberate: because these institutions concentrate on digital and technology-related practices, their presence serves as an internal control for the technology discourse category.

The corpus is limited to institutions with publicly accessible, structured English-language digital archives. These absences are systematic: commercial gallery texts, non-anglophone institutional output, and small-scale artist-run spaces are not represented. The corpus therefore captures the English-language, digitally native nodes of international institutional art communication.

### DOM-based extraction

Standard web scraping cannot isolate curatorial content from institutional web pages without structural contamination. Navigation menus, footer metadata, copyright notices, and event schedules appear in the same HTML document as critical essays and exhibition statements. Conflating these corrupts functional lexical analysis.

The extraction pipeline preserves the Document Object Model (DOM) of each page, maintaining the hierarchical structure of content blocks before any classification is applied. This block-level representation is the input to the LLM classification pipeline (see `docs/llm_preprocessing.md`).

### Document counts

| Institution | N (docs) | Type |
|:--|:--|:--|
| artforum | 17,344 | Critical magazine |
| e-flux | 10,815 | Artist platform / journal |
| moussemagazine | 10,771 | Critical magazine |
| neuralit | 9,640 | Media art centre |
| creative_app_net | 3,691 | Digital art platform |
| ars_electronica | 3,439 | Media art festival / centre |
| tate | 2,048 | Museum (UK) |
| v2lab | 967 | Media art institute |
| transmediale | 796 | Media art festival |
| spikeart | 394 | Critical magazine |
| afterall | 392 | Academic journal / platform |
| zkm | 388 | Media art centre |
| stedelijk | 322 | Museum (NL) |
| **Total** | **~62,400** | A1+A2 retained |

After deduplication, 60,777 documents were passed to Layer IV LLM scoring.

### Content format labels

The `url_category` field in `corpus_features.jsonl.gz` and `at_scores_*.jsonl.gz` is derived from URL directory structures and platform-specific metadata. These are operational definitions — probabilistic identifiers of document type, not strict genre classifications. The `url_category_map.json.gz` file provides the full mapping.

---

## DOAJ Academic Baseline

### Design rationale

The baseline requires peer-reviewed articles that deploy the same discourse vocabulary under strict epistemological constraints. Academic texts are bound by conventions requiring explicit argumentation, citation, and evidence. These conventions make academic writing a reliable structural reference point.

### Collection method

The DOAJ REST API was queried with Boolean OR search terms across 8 discourse categories. Year-balanced sampling across 2010–2025 restricted each journal to a maximum of three articles, preventing any single publication from dominating a category. PDF full texts were extracted using a GPU-accelerated parser. A language filter (lingua-py) removed 177 non-English documents and quarantined 8 ambiguous cases.

### DOAJ search queries

| Discourse | Search Query |
|:--|:--|
| ecology | `(anthropocene OR "climate change" OR "climate crisis" OR ecology OR "environmental crisis" OR biodiversity)` |
| gender | `(feminism OR feminist OR queer OR "gender studies" OR "gender identity" OR transgender)` |
| postcolonial | `(postcolonial OR decolonization OR decolonial OR colonialism OR "colonial history" OR imperialism)` |
| race | `(racism OR "racial discrimination" OR intersectionality OR "critical race" OR antiracism OR "ethnic studies")` |
| capitalism | `(capitalism OR neoliberalism OR commodification OR "political economy" OR marxism OR "labor exploitation")` |
| technology | `("artificial intelligence" OR algorithm OR "digital surveillance" OR "data privacy" OR "machine learning" OR cybernetics)` |
| identity | `(diaspora OR "cultural identity" OR migration OR "belonging" OR "identity politics" OR citizenship)` |
| power | `(biopolitics OR hegemony OR sovereignty OR "political power" OR "state violence" OR authoritarianism)` |

### DOAJ corpus metrics

| Metric | Value |
|:--|:--|
| Total documents | 1,673 |
| Unique journals | 835 |
| Median word count | 4,928 |
| Discourse categories | 8 |
| Year range | 2010–2025 |

**Per-discourse counts:** ecology (502), gender (390), technology (189), identity (184), power (153), postcolonial (109), capitalism (90), race (56). The imbalance reflects open-access publication availability in each domain, not a sampling design choice.

### Length disparity note

The art and DOAJ corpora differ substantially in median word count (617 vs. 4,928 words). This is a structural feature of the two registers. It is not incidental noise. All four analytical layers apply explicit length controls; see the analysis scripts and paper sections for details.

---

## Discourse Keywords

The `discourse_keywords.json` file contains 530 keywords distributed across 8 discourse categories (*ecology, gender, postcolonial, race, capitalism, technology, identity, power*). Terms were manually curated to represent discourse vocabulary shared by both institutional art writing and academic discourse in these domains. Proper nouns were strictly excluded to prevent false positive matches caused by named entities.

All downstream analyses apply only to documents containing at least one keyword from the relevant discourse category. Structural patterns observed in the paper hold within this defined lexical scope.
