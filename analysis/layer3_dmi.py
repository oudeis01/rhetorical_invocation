#!/usr/bin/env python3
"""
Layer III: Discourse Marker Interaction (DMI)

Reproduces Section 6 (DMI) tables from the paper:
  - Art corpus vs DOAJ: Liberal DMI, Conservative DMI, zero-rate
  - Odds Ratio (zero-DMI) with 95% CI
  - Breakdown by institution and url_category

Input:  data/dmi_scores.jsonl.gz
Output: printed tables + output/layer3_dmi_results.json

Usage:
    python analysis/layer3_dmi.py
"""

import argparse
import gzip
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Layer III DMI analysis")
    p.add_argument("--data", default="data/dmi_scores.jsonl.gz")
    p.add_argument("--out", default="output/layer3_dmi_results.json")
    return p.parse_args()


def cohen_d(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    sp = math.sqrt(((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2))
    return (ma - mb) / sp if sp > 0 else 0.0


def odds_ratio_woolf_ci(a, b, c, d_count, z=1.96):
    """
    OR for 2×2 table:
      a = art zero,  b = art nonzero
      c = doaj zero, d = doaj nonzero
    Woolf 95% CI.
    """
    # Avoid zero cells
    a, b, c, d_count = a + 0.5, b + 0.5, c + 0.5, d_count + 0.5
    OR = (a * d_count) / (b * c)
    se_ln = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d_count)
    lo = math.exp(math.log(OR) - z * se_ln)
    hi = math.exp(math.log(OR) + z * se_ln)
    return OR, lo, hi


def chi2_2x2(a, b, c, d_count):
    n = a + b + c + d_count
    e_a = (a + b) * (a + c) / n
    e_b = (a + b) * (b + d_count) / n
    e_c = (a + c) * (c + d_count) / n
    e_d = (b + d_count) * (c + d_count) / n
    return (
        (a - e_a) ** 2 / e_a
        + (b - e_b) ** 2 / e_b
        + (c - e_c) ** 2 / e_c
        + (d_count - e_d) ** 2 / e_d
    )


def main():
    args = parse_args()
    data_path = Path(args.data)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # All docs included (kw=0 docs have dmi=0.0, matching weight_sensitivity_analysis.py)
    art_lib, art_cons = [], []
    art_zero_lib, art_zero_cons, art_total = 0, 0, 0
    doaj_lib, doaj_cons = [], []
    doaj_zero_lib, doaj_zero_cons, doaj_total = 0, 0, 0
    # kw>0 subset for paper-exact OR (liberal zero in kw>0 subset)
    art_kw_pos_total, art_kw_pos_lib_zero = 0, 0
    doaj_kw_pos_total, doaj_kw_pos_lib_zero = 0, 0
    by_inst = defaultdict(lambda: {"lib": [], "cons": [], "zero_lib": 0, "zero_cons": 0, "total": 0})

    opener = gzip.open if str(data_path).endswith(".gz") else open
    with opener(data_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            dmi_l = d.get("dmi_liberal", 0.0)
            dmi_c = d.get("dmi_conservative", 0.0)
            kw = d.get("total_keyword_matches", 0)
            inst = d["institution"]

            zero_l = dmi_l == 0.0
            zero_c = dmi_c == 0.0
            if inst == "doaj":
                doaj_lib.append(dmi_l)
                doaj_cons.append(dmi_c)
                if zero_l:
                    doaj_zero_lib += 1
                if zero_c:
                    doaj_zero_cons += 1
                doaj_total += 1
                if kw > 0:
                    doaj_kw_pos_total += 1
                    if zero_l:
                        doaj_kw_pos_lib_zero += 1
            else:
                art_lib.append(dmi_l)
                art_cons.append(dmi_c)
                if zero_l:
                    art_zero_lib += 1
                if zero_c:
                    art_zero_cons += 1
                art_total += 1
                if kw > 0:
                    art_kw_pos_total += 1
                    if zero_l:
                        art_kw_pos_lib_zero += 1
                bucket = by_inst[inst]
                bucket["lib"].append(dmi_l)
                bucket["cons"].append(dmi_c)
                if zero_l:
                    bucket["zero_lib"] += 1
                if zero_c:
                    bucket["zero_cons"] += 1
                bucket["total"] += 1

    print(f"All docs: Art={art_total:,}, DOAJ={doaj_total:,}")
    print(f"kw>0 subset: Art={art_kw_pos_total:,}, DOAJ={doaj_kw_pos_total:,}\n")

    # Aggregate
    art_lib_mean = statistics.mean(art_lib)
    art_cons_mean = statistics.mean(art_cons)
    doaj_lib_mean = statistics.mean(doaj_lib)
    doaj_cons_mean = statistics.mean(doaj_cons)
    art_zero_rate_lib = art_zero_lib / art_total
    doaj_zero_rate_lib = doaj_zero_lib / doaj_total
    art_zero_rate_cons = art_zero_cons / art_total
    doaj_zero_rate_cons = doaj_zero_cons / doaj_total

    d_lib = cohen_d(art_lib, doaj_lib)
    d_cons = cohen_d(art_cons, doaj_cons)

    # OR for liberal zero
    OR_lib, or_lib_lo, or_lib_hi = odds_ratio_woolf_ci(
        art_zero_lib, art_total - art_zero_lib, doaj_zero_lib, doaj_total - doaj_zero_lib
    )
    chi2_lib = chi2_2x2(
        art_zero_lib, art_total - art_zero_lib, doaj_zero_lib, doaj_total - doaj_zero_lib
    )
    # OR for conservative zero
    OR_cons, or_cons_lo, or_cons_hi = odds_ratio_woolf_ci(
        art_zero_cons, art_total - art_zero_cons, doaj_zero_cons, doaj_total - doaj_zero_cons
    )
    chi2_cons = chi2_2x2(
        art_zero_cons, art_total - art_zero_cons, doaj_zero_cons, doaj_total - doaj_zero_cons
    )

    print("=== DMI Aggregate ===")
    print(
        f"  Liberal  — Art: {art_lib_mean:.4f}  DOAJ: {doaj_lib_mean:.4f}  d={d_lib:.3f}"
    )
    print(
        f"  Conserv. — Art: {art_cons_mean:.4f}  DOAJ: {doaj_cons_mean:.4f}  d={d_cons:.3f}"
    )
    print(
        f"  Zero-rate (liberal) — Art: {art_zero_rate_lib:.4f} ({art_zero_lib}/{art_total})  DOAJ: {doaj_zero_rate_lib:.4f} ({doaj_zero_lib}/{doaj_total})"
    )
    print(f"    OR (lib zero):  {OR_lib:.2f}  [95% CI: {or_lib_lo:.2f}, {or_lib_hi:.2f}]  χ²={chi2_lib:.1f}")
    print(
        f"  Zero-rate (conserv.) — Art: {art_zero_rate_cons:.4f} ({art_zero_cons}/{art_total})  DOAJ: {doaj_zero_rate_cons:.4f} ({doaj_zero_cons}/{doaj_total})"
    )
    print(f"    OR (cons zero): {OR_cons:.2f}  [95% CI: {or_cons_lo:.2f}, {or_cons_hi:.2f}]  χ²={chi2_cons:.1f}")

    # Paper-exact OR: kw>0 subset, liberal zero
    OR_paper, or_paper_lo, or_paper_hi = odds_ratio_woolf_ci(
        art_kw_pos_lib_zero, art_kw_pos_total - art_kw_pos_lib_zero,
        doaj_kw_pos_lib_zero, doaj_kw_pos_total - doaj_kw_pos_lib_zero,
    )
    chi2_paper = chi2_2x2(
        art_kw_pos_lib_zero, art_kw_pos_total - art_kw_pos_lib_zero,
        doaj_kw_pos_lib_zero, doaj_kw_pos_total - doaj_kw_pos_lib_zero,
    )
    print(f"  Paper-exact OR (kw>0, liberal zero):")
    print(f"    Art: {art_kw_pos_lib_zero}/{art_kw_pos_total} ({art_kw_pos_lib_zero/art_kw_pos_total:.4f})")
    print(f"    DOAJ: {doaj_kw_pos_lib_zero}/{doaj_kw_pos_total} ({doaj_kw_pos_lib_zero/doaj_kw_pos_total:.4f})")
    print(f"    OR = {OR_paper:.2f}  [95% CI: {or_paper_lo:.2f}, {or_paper_hi:.2f}]  χ²={chi2_paper:.1f}")
    print(f"    Paper target: OR=5.48 [4.86, 6.18]")
    print()

    print("=== Conservative DMI by Institution ===")
    inst_results = {}
    for inst, bkt in sorted(by_inst.items(), key=lambda x: -x[1]["total"]):
        if bkt["total"] < 5:
            continue
        cons_mean = statistics.mean(bkt["cons"]) if bkt["cons"] else 0
        zero_r = bkt["zero_cons"] / bkt["total"]
        dmi_d = cohen_d(bkt["cons"], doaj_cons)
        print(
            f"  {inst:30s}  N={bkt['total']:5,}  cons={cons_mean:.4f}  zero={zero_r:.3f}  d={dmi_d:+.3f}"
        )
        inst_results[inst] = {
            "n": bkt["total"],
            "cons_mean": cons_mean,
            "zero_rate_cons": zero_r,
            "cohen_d_vs_doaj": dmi_d,
        }

    results = {
        "aggregate": {
            "art_n": art_total,
            "doaj_n": doaj_total,
            "art_lib_mean": art_lib_mean,
            "doaj_lib_mean": doaj_lib_mean,
            "d_liberal": d_lib,
            "art_cons_mean": art_cons_mean,
            "doaj_cons_mean": doaj_cons_mean,
            "d_conservative": d_cons,
            "art_zero_rate_lib": art_zero_rate_lib,
            "doaj_zero_rate_lib": doaj_zero_rate_lib,
            "art_zero_rate_cons": art_zero_rate_cons,
            "doaj_zero_rate_cons": doaj_zero_rate_cons,
            "zero_OR_lib": OR_lib,
            "zero_OR_lib_ci95": [or_lib_lo, or_lib_hi],
            "zero_OR_cons": OR_cons,
            "zero_OR_cons_ci95": [or_cons_lo, or_cons_hi],
            "paper_OR_kw_pos_lib": OR_paper,
            "paper_OR_kw_pos_lib_ci95": [or_paper_lo, or_paper_hi],
        },
        "by_institution": inst_results,
    }
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
