#!/usr/bin/env python3
"""
Layer III: Discourse Marker Interaction (DMI)

Reproduces Table 6.1 and the zero-rate analysis from the paper:
  - Art corpus vs DOAJ: Liberal DMI, Conservative DMI, zero-rate
  - Odds Ratio (zero-DMI) with 95% CI
  - Breakdown by institution and url_category

Input:  data/corpus_features.jsonl.gz
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
    p.add_argument("--data", default="data/corpus_features.jsonl.gz")
    p.add_argument("--out",  default="output/layer3_dmi_results.json")
    return p.parse_args()


def cohen_d(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2: return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    sp = math.sqrt(((na-1)*sa**2 + (nb-1)*sb**2) / (na+nb-2))
    return (ma - mb) / sp if sp > 0 else 0.0


def odds_ratio_woolf_ci(a, b, c, d_count, z=1.96):
    """
    OR for 2×2 table:
      a = art zero,  b = art nonzero
      c = doaj zero, d = doaj nonzero
    Woolf 95% CI.
    """
    # Avoid zero cells
    a, b, c, d_count = a+0.5, b+0.5, c+0.5, d_count+0.5
    OR = (a * d_count) / (b * c)
    se_ln = math.sqrt(1/a + 1/b + 1/c + 1/d_count)
    lo = math.exp(math.log(OR) - z * se_ln)
    hi = math.exp(math.log(OR) + z * se_ln)
    return OR, lo, hi


def chi2_2x2(a, b, c, d_count):
    n = a + b + c + d_count
    e_a = (a+b)*(a+c)/n; e_b = (a+b)*(b+d_count)/n
    e_c = (a+c)*(c+d_count)/n; e_d = (b+d_count)*(c+d_count)/n
    return ((a-e_a)**2/e_a + (b-e_b)**2/e_b +
            (c-e_c)**2/e_c + (d_count-e_d)**2/e_d)


def main():
    args = parse_args()
    data_path = Path(args.data)
    out_path  = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Only docs with at least one keyword match contribute to DMI
    art_lib, art_cons, art_zero_n, art_total = [], [], 0, 0
    doaj_lib, doaj_cons, doaj_zero_n, doaj_total = [], [], 0, 0
    by_inst = defaultdict(lambda: {"lib":[], "cons":[], "zero":0, "total":0})
    by_cat  = defaultdict(lambda: {"lib":[], "cons":[], "zero":0, "total":0})

    opener = gzip.open if str(data_path).endswith(".gz") else open
    with opener(data_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            kw = d.get("total_keyword_matches", 0)
            dmi_l = d.get("dmi_liberal")
            dmi_c = d.get("dmi_conservative")
            inst  = d["institution"]
            cat   = d.get("url_category", "other")

            # All docs (including no-keyword ones) contribute to zero-rate denominator
            # The paper counts: "Among documents containing at least one discourse keyword"
            if kw == 0 or dmi_l is None:
                continue

            zero = dmi_c == 0.0
            if inst == "doaj":
                doaj_lib.append(dmi_l); doaj_cons.append(dmi_c)
                if zero: doaj_zero_n += 1
                doaj_total += 1
            else:
                art_lib.append(dmi_l); art_cons.append(dmi_c)
                if zero: art_zero_n += 1
                art_total += 1
                bucket = by_inst[inst]
                bucket["lib"].append(dmi_l); bucket["cons"].append(dmi_c)
                if zero: bucket["zero"] += 1
                bucket["total"] += 1
                bucket2 = by_cat[f"{inst}/{cat}"]
                bucket2["lib"].append(dmi_l); bucket2["cons"].append(dmi_c)
                if zero: bucket2["zero"] += 1
                bucket2["total"] += 1

    print(f"Docs with keyword matches: Art={art_total:,}, DOAJ={doaj_total:,}\n")

    # Aggregate
    art_lib_mean  = statistics.mean(art_lib)
    art_cons_mean = statistics.mean(art_cons)
    doaj_lib_mean  = statistics.mean(doaj_lib)
    doaj_cons_mean = statistics.mean(doaj_cons)
    art_zero_rate  = art_zero_n / art_total
    doaj_zero_rate = doaj_zero_n / doaj_total

    d_lib  = cohen_d(art_lib,  doaj_lib)
    d_cons = cohen_d(art_cons, doaj_cons)

    OR, or_lo, or_hi = odds_ratio_woolf_ci(
        art_zero_n, art_total - art_zero_n,
        doaj_zero_n, doaj_total - doaj_zero_n
    )
    chi2 = chi2_2x2(
        art_zero_n, art_total - art_zero_n,
        doaj_zero_n, doaj_total - doaj_zero_n
    )

    print("=== DMI Aggregate ===")
    print(f"  Liberal  — Art: {art_lib_mean:.4f}  DOAJ: {doaj_lib_mean:.4f}  d={d_lib:.3f}")
    print(f"  Conserv. — Art: {art_cons_mean:.4f}  DOAJ: {doaj_cons_mean:.4f}  d={d_cons:.3f}")
    print(f"  Zero-rate — Art: {art_zero_rate:.3f} ({art_zero_n}/{art_total})  DOAJ: {doaj_zero_rate:.3f} ({doaj_zero_n}/{doaj_total})")
    print(f"  OR (zero): {OR:.2f}  [95% CI: {or_lo:.2f}, {or_hi:.2f}]  χ²={chi2:.1f}")
    print()

    print("=== Conservative DMI by Institution ===")
    inst_results = {}
    for inst, bkt in sorted(by_inst.items(), key=lambda x: -x[1]["total"]):
        if bkt["total"] < 5: continue
        cons_mean = statistics.mean(bkt["cons"]) if bkt["cons"] else 0
        zero_r    = bkt["zero"] / bkt["total"]
        dmi_d     = cohen_d(bkt["cons"], doaj_cons)
        print(f"  {inst:30s}  N={bkt['total']:5,}  cons={cons_mean:.4f}  zero={zero_r:.3f}  d={dmi_d:+.3f}")
        inst_results[inst] = {
            "n": bkt["total"], "cons_mean": cons_mean, "zero_rate": zero_r,
            "cohen_d_vs_doaj": dmi_d,
        }

    results = {
        "aggregate": {
            "art_n": art_total, "doaj_n": doaj_total,
            "art_lib_mean": art_lib_mean, "doaj_lib_mean": doaj_lib_mean, "d_liberal": d_lib,
            "art_cons_mean": art_cons_mean, "doaj_cons_mean": doaj_cons_mean, "d_conservative": d_cons,
            "art_zero_rate": art_zero_rate, "doaj_zero_rate": doaj_zero_rate,
            "zero_OR": OR, "zero_OR_ci95": [or_lo, or_hi], "chi2": chi2,
        },
        "by_institution": inst_results,
    }
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
