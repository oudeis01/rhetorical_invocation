#!/usr/bin/env python3
"""
build_nmce_scores.py

Extracts adjective frequency data from structural_results.jsonl into
data/nmce_scores.jsonl.gz. Stores raw adj_counter per document so the
analysis script can compute nMCE under multiple filter variants
(primary/IAE/top-100).

File-level (NO URL dedup). Uses results_with_evidence/ version which
has the npmd.total_nouns field needed for the paper's primary nMCE filter.

Run on workstation:
    python scripts/build_nmce_scores.py
"""

import gzip
import json
from collections import Counter
from pathlib import Path

BASE = Path("/home/choiharam/works/projects/namedrop_data/analysis_pipeline")
STRUCTURAL_JSONL = (
    BASE
    / "syntactic_analysis/structural_bloat_analyzer"
    / "results_with_evidence/2026-02-26-205346_full_run/structural_results.jsonl"
)
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "nmce_scores.jsonl.gz"

# Institution mapping: structural_results uses "control" for DOAJ
INST_MAP = {"control": "doaj"}

# Exclude only aeon and theconversation (matching plot_nmce_figures.py)
EXCLUDE_INSTITUTIONS = {"aeon", "theconversation"}


def norm_url(u):
    return u.rstrip("/").lower() if u else ""


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    skipped = 0

    with open(STRUCTURAL_JSONL, encoding="utf-8") as f_in, \
         gzip.open(OUT_PATH, "wt", encoding="utf-8") as f_out:
        for line in f_in:
            d = json.loads(line)
            inst = d.get("institution", "")
            if inst in EXCLUDE_INSTITUTIONS:
                skipped += 1
                continue
            url = norm_url(d.get("url", ""))
            if not url:
                skipped += 1
                continue

            mce_pairs = d.get("mce_pairs", [])
            adj_counter = Counter(pair[0] for pair in mce_pairs)
            if not adj_counter:
                skipped += 1
                continue

            total_nouns = d.get("npmd", {}).get("total_nouns", 0)
            # In results_with_evidence: "doaj"; in results/: "control"
            mapped_inst = INST_MAP.get(inst, inst)

            rec = {
                "url": url,
                "institution": mapped_inst,
                "adj_counter": dict(adj_counter),
                "total_nouns": total_nouns,
            }
            f_out.write(json.dumps(rec) + "\n")
            count += 1

    print(f"Written {count:,} records to {OUT_PATH}")
    print(f"Skipped: {skipped:,}")

    # Sanity check
    inst_counts = Counter()
    with gzip.open(OUT_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            inst_counts[d["institution"]] += 1

    print("\nPer-institution N:")
    art_total = 0
    for inst in sorted(inst_counts):
        n = inst_counts[inst]
        label = "DOAJ" if inst == "doaj" else "Art"
        print(f"  {inst:25s} {n:>6,}  [{label}]")
        if inst != "doaj":
            art_total += n
    print(f"  {'Art total':25s} {art_total:>6,}")
    print(f"  {'DOAJ':25s} {inst_counts.get('doaj', 0):>6,}")
    print(f"\nNote: Analysis script applies filters (primary/IAE/top-100) at compute time.")
    print(f"Paper primary target (all adj, pairs>=3, K>=2, nouns>=50): Art N=49,791 DOAJ N=1,669")


if __name__ == "__main__":
    main()
