#!/usr/bin/env python3
"""
build_at_scores.py

Convert raw cascade_scoring JSONL files (one record per document, 8 discourses)
into the repo's at_scores format (one record per (document, discourse) pair).

Key difference from the existing repo at_scores:
  - No-engagement pairs (empty top_alternatives) are INCLUDED with AT=0
    and a synthetic top_alternatives=[{"token":"0","prob":1.0}].
  - This allows layer4_at.py to count N=60,777 (full corpus) rather than
    only the 52,753 docs that had at least one engaged discourse.

Source files (workstation paths):
  Llama art:  cascade_scoring_20260307_001402.jsonl  (60,777 lines)
  Llama DOAJ: llama_70b_fp8_doaj/cascade_scoring_*.jsonl
  Qwen art:   qwen72b_fp8/cascade_scoring_*.jsonl (4 files, 60,777 total)
  Qwen DOAJ:  qwen72b_fp8_doaj/cascade_scoring_*.jsonl

Output (repo data dir):
  at_scores_llama.jsonl.gz
  at_scores_qwen.jsonl.gz

Run on workstation (conda base):
  /home/choiharam/miniconda3/bin/conda run -n base python3 build_at_scores.py
"""

import gzip
import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REMOTE_BASE = (
    "/home/choiharam/works/projects/namedrop_data"
    "/analysis_pipeline/llm_depth_scoring/remote_backup"
)

LLAMA_ART_JSONL = (
    f"{REMOTE_BASE}/Llama-3.3-70B-Instruct-FP8-dynamic"
    "/namedrop/cascade_scoring/results/llama_70b_fp8"
    "/cascade_scoring_20260307_001402.jsonl"
)
LLAMA_DOAJ_DIR = (
    f"{REMOTE_BASE}/Llama-3.3-70B-Qwen-2.5-72B-doaj-only"
    "/namedrop/cascade_scoring/results/llama_70b_fp8_doaj"
)
QWEN_ART_DIR = (
    f"{REMOTE_BASE}/qwen2.5-72B-Instruct-fp8-dynamic"
    "/namedrop/cascade_scoring/results/qwen72b_fp8"
)
QWEN_DOAJ_DIR = (
    f"{REMOTE_BASE}/Llama-3.3-70B-Qwen-2.5-72B-doaj-only"
    "/namedrop/cascade_scoring/results/qwen72b_fp8_doaj"
)

OUT_DIR = Path("/home/choiharam/tmp-jobs/rhetorical_invocation/scripts")

# Synthetic no-engagement alternatives (AT=0)
NO_ENG_ALTS = [{"token": "0", "prob": 1.0}]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def jsonl_files_in(directory):
    """Return sorted list of .jsonl files in a directory."""
    d = Path(directory)
    if not d.exists():
        return []
    return sorted(d.glob("*.jsonl"))


def compute_at(top_alternatives):
    """Compute AT = P(depth=4) + P(depth=5) from top_alternatives list."""
    if not top_alternatives:
        return 0.0
    total = 0.0
    for alt in top_alternatives:
        token = (
            str(alt.get("token", "")).strip()
            if isinstance(alt, dict)
            else str(alt[0]).strip()
        )
        prob = alt.get("prob", 0.0) if isinstance(alt, dict) else float(alt[1])
        if token in ("4", "5"):
            total += prob
    return total


def process_doc(doc, is_doaj=False):
    """
    Yield one output record per (document, discourse) pair.

    For no-engagement pairs: include with synthetic alts and at_value=0.0
    so layer4_at.py can count them in N without inflating AT.
    """
    url = doc.get("url") or doc.get("document_id", "")
    source = doc.get("source", "doaj" if is_doaj else "unknown")
    disc_results = doc.get("discourse_results", {})

    for discourse, dr in disc_results.items():
        alts = dr.get("top_alternatives", [])
        level = dr.get("depth_level", 0)
        conf = dr.get("confidence", 0.0)

        # Skip completely invalid records (parse failure)
        if conf == 0 and level == 0 and not alts:
            # Still include as no-engagement
            pass

        if alts:
            at_val = compute_at(alts)
            out_alts = alts
        else:
            # No-engagement: depth_level=0, empty top_alternatives
            at_val = 0.0
            out_alts = NO_ENG_ALTS

        yield {
            "doc_id": url,
            "institution": "doaj" if is_doaj else source,
            "discourse": discourse,
            "at_value": round(at_val, 8),
            "top_alternatives": out_alts,
        }


# ---------------------------------------------------------------------------
# Build one output file
# ---------------------------------------------------------------------------
def build_at_file(art_sources, doaj_sources, out_path):
    """
    art_sources:  list of Path objects (art JSONL files)
    doaj_sources: list of Path objects (DOAJ JSONL files)
    out_path:     output .jsonl.gz path
    """
    print(f"\n[BUILD] -> {out_path}", flush=True)
    n_art_docs = n_doaj_docs = 0
    n_pairs = 0

    with gzip.open(out_path, "wt", encoding="utf-8") as out:
        # Art
        for src_path in art_sources:
            print(f"  art:  {src_path.name}", flush=True)
            for doc in iter_jsonl(src_path):
                n_art_docs += 1
                for rec in process_doc(doc, is_doaj=False):
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_pairs += 1
                if n_art_docs % 10000 == 0:
                    print(f"    {n_art_docs:,} docs / {n_pairs:,} pairs", flush=True)

        # DOAJ
        for src_path in doaj_sources:
            print(f"  doaj: {src_path.name}", flush=True)
            for doc in iter_jsonl(src_path):
                n_doaj_docs += 1
                for rec in process_doc(doc, is_doaj=True):
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_pairs += 1

    mb = os.path.getsize(out_path) / 1024 / 1024
    print(
        f"  Done. art={n_art_docs:,} docs  doaj={n_doaj_docs:,} docs  "
        f"total pairs={n_pairs:,}  {mb:.1f} MB",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ----- Llama -----
    llama_art = [Path(LLAMA_ART_JSONL)]
    llama_doaj = jsonl_files_in(LLAMA_DOAJ_DIR)
    print(f"Llama art files:  {[p.name for p in llama_art]}")
    print(f"Llama DOAJ files: {[p.name for p in llama_doaj]}")

    build_at_file(
        art_sources=llama_art,
        doaj_sources=llama_doaj,
        out_path=OUT_DIR / "at_scores_llama.jsonl.gz",
    )

    # ----- Qwen -----
    qwen_art = jsonl_files_in(QWEN_ART_DIR)
    qwen_doaj = jsonl_files_in(QWEN_DOAJ_DIR)
    print(f"\nQwen art files:  {[p.name for p in qwen_art]}")
    print(f"Qwen DOAJ files: {[p.name for p in qwen_doaj]}")

    build_at_file(
        art_sources=qwen_art,
        doaj_sources=qwen_doaj,
        out_path=OUT_DIR / "at_scores_qwen.jsonl.gz",
    )

    print("\n[DONE] Deploy commands:")
    for model in ("llama", "qwen"):
        src = OUT_DIR / f"at_scores_{model}.jsonl.gz"
        dst = (
            "/home/choiharam/tmp-jobs/rhetorical_invocation/data"
            f"/at_scores_{model}.jsonl.gz"
        )
        print(f"  cp {src} {dst}")


if __name__ == "__main__":
    main()
