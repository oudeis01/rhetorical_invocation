#!/usr/bin/env python3
"""
build_dmi_scores.py

Extracts DMI scores from the raw DMI analysis CSV, recomputing with
CONTRAST weight w=1.0 (paper's final choice), and resolves file paths
to URLs via basename_url_map.json.

Preserves file-level analysis unit (no URL dedup), matching the
weight_sensitivity_analysis.py that produced the paper's DMI numbers
(n_art=62,655).

Key conventions (matching weight_sensitivity_analysis.py):
  - Records with total_keyword_matches=0 get dmi=0.0 (not None)
  - All art + control_doaj records are included (no URL filter)
  - URL resolved from basename_url_map for cross-layer joins;
    document_id used as fallback when URL unavailable

Run on workstation:
    python scripts/build_dmi_scores.py
"""

import csv
import gzip
import json
import os
from pathlib import Path

BASE = Path("/home/choiharam/works/projects/namedrop_data/analysis_pipeline")
DMI_CSV = BASE / "syntactic_analysis/discourse_marker_interaction/results/dmi_analysis_20260312_180644_results.csv"
BN_URL_MAP = BASE / "cross_layer_analysis/results/basename_url_map.json"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "dmi_scores.jsonl.gz"

W = 1.0  # CONTRAST weight — paper's final choice


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load basename → URL map (art corpus only; DOAJ not included)
    print("Loading basename_url_map...")
    with open(BN_URL_MAP, encoding="utf-8") as f:
        bn_url = json.load(f)
    print(f"  {len(bn_url):,} entries")

    count = 0
    skipped_source = 0
    url_resolved = 0
    url_fallback = 0

    with open(DMI_CSV, encoding="utf-8", newline="") as f_in, \
         gzip.open(OUT_PATH, "wt", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            source_type = row["source_type"]
            if source_type not in ("art", "control_doaj"):
                skipped_source += 1
                continue

            institution = "doaj" if source_type == "control_doaj" else row["category"]
            doc_id = row["document_id"]

            # Resolve URL from file_path basename
            basename = os.path.basename(row["file_path"])
            url = bn_url.get(basename, "")
            if not url:
                stem = basename.replace(".json", "")
                url = bn_url.get(stem, "")

            if url:
                url = url.rstrip("/").lower()
                url_resolved += 1
            else:
                # Fallback: use document_id (needed for DOAJ and unmapped art files)
                url = doc_id
                url_fallback += 1

            total_kw = int(row["total_keyword_matches"])
            cc = int(row["cause_condition_count"])
            ct = int(row["contrast_count"])
            pcc = int(row["polysemous_cause_condition_count"])
            pct = int(row["polysemous_contrast_count"])

            # Recompute with w=1.0
            # Convention: dmi=0.0 when total_kw=0 (matching weight_sensitivity)
            if total_kw > 0:
                dmi_lib = (cc + W * ct) / total_kw
                cc_clean = max(0, cc - pcc)
                ct_clean = max(0, ct - pct)
                dmi_cons = (cc_clean + W * ct_clean) / total_kw
            else:
                dmi_lib = 0.0
                dmi_cons = 0.0

            dmi_zero = (dmi_lib == 0.0)

            # Also preserve CSV's original w=0.5 scores (used by cross-layer)
            dmi_csv_lib = float(row["dmi_score"])
            dmi_csv_cons = float(row["dmi_score_conservative"])

            rec = {
                "url": url,
                "institution": institution,
                "source_type": source_type,
                "total_keyword_matches": total_kw,
                "dmi_liberal": round(dmi_lib, 8),
                "dmi_conservative": round(dmi_cons, 8),
                "dmi_zero": dmi_zero,
                "dmi_csv_liberal": round(dmi_csv_lib, 8),
                "dmi_csv_conservative": round(dmi_csv_cons, 8),
            }
            f_out.write(json.dumps(rec) + "\n")
            count += 1

    print(f"Written {count:,} records to {OUT_PATH}")
    print(f"Skipped: {skipped_source:,} (source_type filter)")
    print(f"URL resolved: {url_resolved:,}, fallback (doc_id): {url_fallback:,}")

    # Sanity check: replicate weight_sensitivity numbers
    art_libs = []
    doaj_libs = []
    art_zero = 0
    doaj_zero = 0
    with gzip.open(OUT_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["source_type"] == "art":
                art_libs.append(d["dmi_liberal"])
                if d["dmi_zero"]:
                    art_zero += 1
            else:
                doaj_libs.append(d["dmi_liberal"])
                if d["dmi_zero"]:
                    doaj_zero += 1

    art_mean = sum(art_libs) / len(art_libs) if art_libs else 0
    doaj_mean = sum(doaj_libs) / len(doaj_libs) if doaj_libs else 0

    print(f"\nSanity check (should match weight_sensitivity w=1.0):")
    print(f"  Art:  N={len(art_libs):,}, lib mean={art_mean:.4f}, zero_rate={art_zero/len(art_libs):.4f}")
    print(f"  DOAJ: N={len(doaj_libs):,}, lib mean={doaj_mean:.4f}, zero_rate={doaj_zero/len(doaj_libs):.4f}")
    print(f"  Paper: Art N=62,655 lib=0.0915 zero=0.6009 | DOAJ N=1,673 lib=0.1267 zero=0.1996")


if __name__ == "__main__":
    main()
