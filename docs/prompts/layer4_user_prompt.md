# Layer IV User Prompt Template

This is the user prompt sent per (document, discourse) pair.
`{discourse}`, `{kw_section}`, and `{text}` are substituted at runtime.
Texts longer than ~4,000 tokens are truncated at the token boundary.

---

```
Analyze this text for engagement with [{discourse}] discourse.

KEYWORDS FROM [{discourse}] FOUND IN THIS TEXT:
{kw_section}

TEXT:
---
{text}
---

Evaluate whether this text engages with [{discourse}] discourse (as defined by the
keyword constellation above), and if so, at what depth.

Respond with this JSON structure:

{
  "discourse": "{discourse}",
  "engages_with_discourse": true or false,
  "depth_level": 0 to 5,
  "depth_label": "NO_ENGAGEMENT or MENTION or DECORATIVE or CONTEXTUAL or ANALYTICAL or THEORETICAL",
  "primary_evidence": "Keyword-containing quote (max 50 chars). null if Level 0.",
  "reasoning": "Max 20 words: key reason for this depth level.",
  "keywords_in_discourse_context": ["list", "of", "keywords"],
  "keywords_not_in_discourse_context": ["keywords", "present", "but", "not", "discourse", "related"]
}

EVIDENCE SELECTION RULES:
0. BREVITY: reasoning must be 20 words or fewer. primary_evidence must be 50 characters or fewer.
1. primary_evidence MUST contain at least one keyword from the matched keyword list above.
2. If claiming Level 3+, the evidence must show the discourse being DISCUSSED as subject matter.
3. Do NOT select quotes about creative process or personal preferences unless directly relevant.
4. If no suitable evidence containing keywords exists, reconsider whether engagement is truly at that level.

IMPORTANT: If the text does NOT engage with [{discourse}] discourse despite keyword presence,
set engages_with_discourse to false and depth_level to 0.
```

---

## Keyword Section Format

`{kw_section}` is populated as:

```
- ecology (3 occurrences)
- environment (1 occurrence)
- climate (2 occurrences)
```

If no keywords are found, `{kw_section}` = `(none found)`, and Level 0 is expected.
