# LLM Preprocessing Pipeline

Two-phase LLM classification pipeline for corpus construction. Both phases use `Qwen/Qwen2.5-14B-Instruct-AWQ` via a local vLLM server.

---

## Phase 1: Block-Level Content Classification

Each DOM-extracted block from an institutional web page is classified into one of five functional categories. The pipeline processes all blocks from a page in a single API call.

### Design note

Reasoning examples in the few-shot output schema intentionally use ellipsis (`"..."`) rather than explicit rationale text. Empirical testing confirmed that 7–14B parameter models copy reasoning templates verbatim when provided with explicit examples, suppressing independent content analysis. Ellipsis forces the model to evaluate the actual block content.

### Phase 1 Prompt Template

```
You are classifying pre-segmented content blocks from {source_name} website.

PAGE METADATA:
- Page ID: {page_id}
- URL: {url}
- Script-Determined Year: {year}
- Script-Determined Month: {month}
- Total blocks: {num_blocks}

IMPORTANT: Each block is already segmented by DOM structure. Your task is CLASSIFICATION ONLY.

{blocks_content}

---
TASK 1: VERIFY PUBLICATION DATE (MANDATORY)
1. Search ALL blocks for explicit date mentions (publication dates, event dates, issue dates).
2. Compare found dates with "Script-Determined Year" ({year}).
3. RESOLVE CONFLICTS: If content dates differ from script dates, TRUST THE CONTENT.
   - Example: If script says 2023 but text says "October 2011", verified_year is 2011.
4. Provide verified_year and verified_month (or null if not found).
5. Explain your reasoning (citing specific text if found).

TASK 2: CLASSIFY BLOCKS
Classify each block into ONE category:
- CURATORIAL: Intellectual/artistic content (essays, statements, interviews)
- METADATA: Factual info (dates, lists without context, video credits, funding lists)
- NAVIGATION: Menus, breadcrumbs, links, search bars
- FOOTER: Copyright, contact info, policy links
- OTHER: Ads, errors, placeholders, login screens

---
OUTPUT FORMAT:

Return a JSON object with the following structure:

{
  "verified_year": 2024,
  "verified_month": 4,
  "date_verification_reasoning": "Content explicitly mentions 'April 2024' in block 0.",
  "blocks": [
    {
      "block_index": 0,
      "segment_type": "CURATORIAL",
      "reasoning": "..."
    },
    {
      "block_index": 1,
      "segment_type": "METADATA",
      "reasoning": "..."
    }
  ]
}

CRITICAL REQUIREMENTS:
1. You MUST classify ALL {num_blocks} blocks. Do not skip any block.
2. If blocks array is empty (e.g., subscriber-only), return null for verified dates and an empty blocks list with reasoning.
3. Always include all top-level fields: verified_year, verified_month, date_verification_reasoning, blocks.
4. Keep reasoning concise (max 200 characters per block).
```

---

## Phase 2: Depth Stratification

Pages whose blocks were classified as CURATORIAL in Phase 1 are passed to Phase 2. The model assigns the entire page one of four depth categories based on the dominant intellectual function of its curatorial content.

For pages exceeding 6,000 words, the pipeline splits the text into sliding window chunks and applies max pooling across assigned grades: the highest grade across chunks is retained as the page classification. This ensures that brief analytical introductions (A1) are not overridden by longer descriptive sections that follow them.

### Retention rule

Only **A1** and **A2** documents are retained. A3 and A4 documents are excluded.

Including A2 documents is a deliberate design choice. This study examines how institutions deploy discourse vocabulary across their full textual output, not only in analytically rigorous publications. A2 texts — contextual descriptions, artist statements, annotated event listings — often adopt the formal vocabulary of theoretical discourse without executing sustained analytical reasoning. They are therefore a central object of analysis, not a source of contamination.

### Phase 2 Prompt Template

```
You are a specialized content classifier for {source_name}. Your task is to analyze
the entirety of the curatorial content from a single webpage and classify it into
one of four categories based on its overall intellectual depth and function.

PAGE METADATA:
- Page ID: {page_id}
- URL: {url}
- Year: {year}

PAGE CURATORIAL CONTENT:
{page_content}

---
TASK: Classify the ENTIRE PAGE CONTENT above into ONE category based on its overall
INTELLECTUAL DEPTH and FUNCTION.

CATEGORIES:

A1: PRIMARY CURATORIAL (Core intellectual/artistic content)
- The page's primary purpose is in-depth analysis of exhibition themes, curatorial
  concepts, or theoretical arguments.
- Contains substantial curatorial statements, essays, or critical engagement with
  artistic ideas.

A2: SECONDARY CURATORIAL (Supporting artistic content)
- The page's primary purpose is to provide standard, interpretive curatorial content
  like artwork descriptions, artist biographies, or event descriptions with artistic
  themes.
- The content is descriptive and interpretive, but lacks deep theoretical analysis.

A3: TERTIARY REFERENCES (Simple factual references)
- The page's primary purpose is to present factual lists or references with minimal
  interpretation.
- Examples: Lists of participating artists, artwork titles, venues, or simple
  chronologies.

A4: NON-CURATORIAL (Administrative/Functional content)
- The content was likely misclassified as CURATORIAL in Phase 1.
- This is a fallback for pages that are actually visitor information, navigation,
  footers, etc.

---
CLASSIFICATION GUIDELINES:

1. Base your decision on the dominant intellectual depth of the entire page.
2. A page with a long, descriptive text (A2) but a short, critical introduction (A1)
   should be classified based on its main thrust. If the analysis is central, it's A1.
   If the description is central, it's A2.
3. A page containing mostly lists (A3) but with a short interpretive introduction (A2)
   should be classified as A2, as the framing provides curatorial value.
4. If the page is clearly non-curatorial, classify as A4 to flag it for Phase 1
   correction.

---
OUTPUT FORMAT:

Return a single JSON object with the classification for the entire page:
{
  "page_level_depth_classification": {
    "depth_category": "A1",
    "reasoning": "The page provides a comprehensive theoretical analysis of the
    exhibition's central themes, making it a primary curatorial document."
  }
}

CRITICAL INSTRUCTIONS:
- Return ONLY valid JSON.
- The depth_category must be exactly one of: A1, A2, A3, or A4.
- Return ONLY depth_category and reasoning.
- Base your decision on the overall intellectual weight of the provided text.
```
