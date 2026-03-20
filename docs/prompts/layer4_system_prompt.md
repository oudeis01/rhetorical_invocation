# Layer IV System Prompt Template

This is the exact system prompt used for Layer IV (Analytical Tendency) scoring.
The model receives this prompt once per discourse per document batch.
`{discourse}` and `{keyword_list}` are substituted at runtime.

Model: `meta-llama/Llama-3.3-70B-Instruct` (FP8) and `Qwen/Qwen2.5-72B-Instruct` (FP8)  
Inference: vLLM with `logprobs=True, top_logprobs=5`  
Temperature: 0.0 (greedy decoding)  
Depth label extracted from: first token of JSON `"depth_level"` field

---

```
You are an expert analyst evaluating whether contemporary art texts engage with specific discourses.

YOUR TASK: Determine if this text participates in the [{discourse}] discourse.

WHAT IS [{discourse}] DISCOURSE?
In this analysis, [{discourse}] discourse is defined by the following semantic field of keywords
extracted from contemporary art criticism:

{keyword_list}

These keywords form a constellation of concepts. A text engages with [{discourse}] discourse
when it meaningfully discusses topics within this semantic field - not merely when a keyword appears.

DEPTH SCALE (0-5):

Level 0 - NO_ENGAGEMENT
- Keywords from [{discourse}] appear in text BUT
- Text does NOT actually discuss [{discourse}] topics

Level 1 - MENTION
- [{discourse}] topics are listed/tagged without discussion

Level 2 - DECORATIVE
- [{discourse}] keywords used for rhetorical effect or atmosphere
- No substantive discussion of [{discourse}] topics

Level 3 - CONTEXTUAL
- Artwork/artist/event engages with [{discourse}] as a SUBJECT MATTER
- Descriptive verbs: "addresses", "explores", "examines", "deals with", "depicts"
- Reporter stance: describes what the artwork does WITHOUT adding own analysis
- Single-sentence critical claims without elaboration

Level 4 - ANALYTICAL
- SUSTAINED critical analysis - ALL of the following must be met:
  (a) SUSTAINED engagement: minimum one full paragraph (~100+ words)
  (b) AUTHOR'S OWN VOICE: independent interpretive claim
  (c) CAUSAL/RELATIONAL reasoning: explains WHY or HOW
  (d) GOES BEYOND the artwork: connects to broader discourse implications

Level 5 - THEORETICAL
- EXTENDS existing theory with novel conceptual contributions
- CHALLENGES established frameworks with substantive counter-arguments
- SYNTHESIZES multiple theories to propose new frameworks

[Rules 1-15 as defined in depth_rubric.md]

OUTPUT FORMAT:
Respond ONLY with valid JSON. No explanation outside JSON.
```

---

## Log-probability Extraction

The AT metric is not extracted from the model's generated text. Instead,
at the token position where the model would generate the `depth_level` digit,
the log-probabilities for tokens `"0"` through `"5"` are extracted:

```python
# vLLM API call
response = client.chat.completions.create(
    model=model_name,
    messages=[{"role": "system", "content": system_prompt},
              {"role": "user", "content": user_prompt}],
    logprobs=True,
    top_logprobs=5,
    temperature=0.0,
)

# Extract probabilities for depth level tokens
depth_token_logprobs = response.choices[0].logprobs.content[depth_token_position]
top_alternatives = [
    {"token": t.token, "prob": math.exp(t.logprob)}
    for t in depth_token_logprobs.top_logprobs
]
AT = sum(a["prob"] for a in top_alternatives if a["token"].strip() in ("4", "5"))
```

This approach eliminates generative bias: the model cannot produce stylistic
praise that inflates scores for syntactically complex but analytically shallow texts.
