# Layer IV Depth Rubric (L0–L5)

This rubric defines the six-level ordinal scale used to classify how deeply
a text engages with a discourse keyword constellation. Applied via
log-probability extraction (not free-form LLM generation).

This file is a standalone citable document. The rubric can be applied
independently of the computational pipeline.

---

## Depth Scale

| Level | Label | Definition |
|:------|:------|:-----------|
| 0 | NO_ENGAGEMENT | Keywords appear but text does not discuss the discourse topics |
| 1 | MENTION | Discourse topics listed or tagged without discussion |
| 2 | DECORATIVE | Keywords used for rhetorical effect or atmosphere only |
| 3 | CONTEXTUAL | Artwork/event engages with discourse as subject matter; descriptive stance |
| 4 | ANALYTICAL | Sustained critical analysis; author's own argument; causal/relational reasoning |
| 5 | THEORETICAL | Extends, challenges, or synthesizes existing theory with novel contributions |

---

## Level Descriptions

### Level 0 — NO_ENGAGEMENT
Keywords from the discourse appear in the text, but the text does not actually
discuss the discourse topics.

Examples:
- "her paintings" contains *her* but is not about gender discourse
- "the green curtain" is about color, not ecology
- "watched via streaming on Netflix" — platform as consumption tool, not technology discourse

### Level 1 — MENTION
Discourse topics are listed or tagged without discussion.

Example: "This exhibition addresses ecology, gender, and race." (bare listing)

### Level 2 — DECORATIVE
Discourse keywords used for rhetorical effect or atmosphere only.

Example: "in our era of climate crisis" used only as contextual backdrop

### Level 3 — CONTEXTUAL
Artwork, artist, or event engages with discourse as subject matter or thematic concern.

Signals:
- Descriptive verbs: *addresses*, *explores*, *examines*, *deals with*, *depicts*
- Reporter stance: describes what the artwork does without the author's own analysis
- Theory citation without application: naming a theorist in their original meaning
- Single-sentence critical claims without elaboration

Example (L3): "The work critiques surveillance capitalism by exposing how data
is harvested from users."

### Level 4 — ANALYTICAL
Sustained critical analysis. All four criteria must be met:

(a) SUSTAINED: minimum one full paragraph (~100+ words) of connected argument  
(b) AUTHOR'S OWN VOICE: independent interpretive claim, not reporting others  
(c) CAUSAL/RELATIONAL: explains why or how, identifies mechanisms or contradictions  
(d) GOES BEYOND: connects to broader discourse implications beyond the work

Example (L4): "The work critiques surveillance capitalism, but more significantly,
it reveals a fundamental contradiction in platform economies: users simultaneously
produce and consume the very mechanisms of their own surveillance. This paradox,
which Zuboff's framework fails to fully address, suggests that resistance cannot
come from individual opt-out but requires structural intervention at the level
of data infrastructure itself."

### Level 5 — THEORETICAL
Extends, challenges, or synthesizes existing theory with novel contributions.

Example: "Extending Haraway's sympoiesis beyond its original scope, the work proposes..."

---

## Classification Rules (1–15)

1. Keyword presence does NOT equal discourse engagement. Be strict about Level 0.
2. Pronouns (her, she, his) are NOT gender discourse unless actually discussing gender.
3. Color words (black, white, green) may be literal colors, not discourse-related.
4. Geographic names alone are NOT postcolonial discourse without colonial/decolonial context.
5. Level 4-5 require explicit conceptual work, not just complex sentences.
6. Technology platform names used as consumption tools are NOT technology discourse.
7. Level 3 requires the discourse to be a SUBJECT of discussion, not merely a tool or medium.
8. QUANTITY MATTERS for Level 4+: A single analytical sentence does NOT qualify.
   Level 4 requires sustained engagement over at least one full paragraph (~100+ words).
9. OPINION vs DESCRIPTION: Level 4 requires the author's own critical opinion/argument.
10. THEORY USAGE:
    - Citing a theory in its original meaning = Level 3
    - Applying a theory to make new analytical claims = Level 4
    - Extending/challenging/synthesizing theories = Level 5
11. INTERVIEWS/CONVERSATIONS: Personal observations do NOT count toward Level 4+.
12. CAPITALISM DISCOURSE: Economic terms in critical context indicate engagement.
    - "capitalist critique", "labor exploitation" with analysis = L2+
    - Critique of unpaid work shifting burden from institutions = L3+
13. POWER DISCOURSE: Governance and institutional power analysis indicate engagement.
    - Analysis of power structures, state-citizen relations = L2+
14. STRUCTURAL/STATISTICAL ANALYSIS elevates engagement level across all discourses.
15. L3 vs L4 MISCLASSIFICATION TRAPS:
    - Complex vocabulary or jargon does NOT elevate L3 to L4
    - Multiple L3-level sentences in a row do NOT automatically become L4
    - Quoting a theorist approvingly without adding new claims = L3
    - Press releases with sophisticated language are almost always L3 or below

---

## Analytical Tendency (AT) Metric

AT = P(depth=4) + P(depth=5), computed from the model's internal log-probabilities
projected onto the rubric labels (not from generated text).

Corpus-level AT is the per-pair mean over all (doc, discourse) pairs where
top_alternatives is non-empty.
