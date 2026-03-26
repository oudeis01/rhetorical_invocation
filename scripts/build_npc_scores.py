#!/usr/bin/env python3
"""
build_npc_scores.py

Extracts NPC scores from the raw npc_results.jsonl into a lightweight
data/npc_scores.jsonl.gz for the repo.

Uses the ORIGINAL npc_results.jsonl (with ars_electronica doc_id dedup bug,
~1,739 ars records instead of 3,439). This matches the data used for the
published paper.

Run on workstation:
    python scripts/build_npc_scores.py
    scp data/npc_scores.jsonl.gz local:path/to/repo/data/
"""

import gzip
import json
from pathlib import Path

BASE = Path("/home/choiharam/works/projects/namedrop_data/analysis_pipeline")
NPC_JSONL = BASE / "syntactic_analysis/npc_noun_phrase_complexity/post/results/20260310_051227_full_run/npc_results.jsonl"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "npc_scores.jsonl.gz"

KEEP_INSTITUTIONS = {
    "afterall", "ars_electronica", "artforum", "creative_app_net",
    "e-flux", "moussemagazine", "neuralit", "spikeart",
    "stedelijk", "tate", "transmediale", "v2lab", "zkm",
    "doaj",
}
KEEP_DEPTH = {"A1", "A2", ""}


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0

    with open(NPC_JSONL, encoding="utf-8") as f_in, \
         gzip.open(OUT_PATH, "wt", encoding="utf-8") as f_out:
        for line in f_in:
            d = json.loads(line)
            inst = d.get("institution", "")
            if inst not in KEEP_INSTITUTIONS:
                skipped += 1
                continue

            depth = d.get("depth_category", "")
            if depth not in KEEP_DEPTH:
                skipped += 1
                continue

            c = d.get("npc_counts", {})
            nn = c.get("total_nouns", 0)
            if nn < 5:
                skipped += 1
                continue

            url = d.get("url", "").rstrip("/").lower()
            npc_pre = (c.get("total_amod", 0) + c.get("total_advmod", 0)) / nn
            npc_post = (c.get("total_prep", 0) + c.get("total_relcl", 0)
                        + c.get("total_appos", 0) + c.get("total_acl", 0)) / nn

            rec = {
                "url": url,
                "institution": inst,
                "total_nouns": nn,
                "npc_pre": round(npc_pre, 8),
                "npc_post": round(npc_post, 8),
            }
            f_out.write(json.dumps(rec) + "\n")
            count += 1

    print(f"Written {count:,} records to {OUT_PATH}")
    print(f"Skipped {skipped:,} (institution/depth/noun filter)")

    # Sanity check
    art_n = 0
    doaj_n = 0
    with gzip.open(OUT_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["institution"] == "doaj":
                doaj_n += 1
            else:
                art_n += 1
    print(f"Art: {art_n:,}, DOAJ: {doaj_n:,}")


if __name__ == "__main__":
    main()
