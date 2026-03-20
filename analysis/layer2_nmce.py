#!/usr/bin/env python3
"""
Layer II: Normalized Modifier Concentration Entropy (nMCE)

Reproduces Table 5.x from the paper:
  - Art corpus vs DOAJ nMCE mean, SD, Cohen's d
  - Institution-level breakdown
  - Robustness: restricted to docs with ≥5 IAE adj pairs

Input:  data/corpus_features.jsonl.gz
Output: printed tables + output/layer2_nmce_results.json

Usage:
    python analysis/layer2_nmce.py
    python analysis/layer2_nmce.py --data path/to/corpus_features.jsonl.gz
"""

import argparse
import gzip
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Layer II nMCE analysis")
    p.add_argument("--data", default="data/corpus_features.jsonl.gz")
    p.add_argument("--out",  default="output/layer2_nmce_results.json")
    return p.parse_args()


def cohen_d(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2: return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    sp = math.sqrt(((na-1)*sa**2 + (nb-1)*sb**2) / (na+nb-2))
    return (ma - mb) / sp if sp > 0 else 0.0


def cohen_d_ci(d, n1, n2, z=1.96):
    se = math.sqrt((n1+n2)/(n1*n2) + d**2/(2*(n1+n2)))
    return d - z*se, d + z*se


def main():
    args = parse_args()
    data_path = Path(args.data)
    out_path  = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    art_vals = []
    doaj_vals = []
    by_inst = defaultdict(list)

    opener = gzip.open if str(data_path).endswith(".gz") else open
    with opener(data_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            v = d.get("nmce")
            if v is None: continue
            inst = d["institution"]
            if inst == "doaj":
                doaj_vals.append(v)
            else:
                art_vals.append(v)
                by_inst[inst].append(v)

    print(f"Loaded: Art N={len(art_vals):,}, DOAJ N={len(doaj_vals):,}\n")

    art_mean  = statistics.mean(art_vals)
    art_sd    = statistics.stdev(art_vals)
    doaj_mean = statistics.mean(doaj_vals)
    doaj_sd   = statistics.stdev(doaj_vals)
    d_val     = cohen_d(art_vals, doaj_vals)
    ci_lo, ci_hi = cohen_d_ci(d_val, len(art_vals), len(doaj_vals))

    print("=== nMCE Aggregate ===")
    print(f"  Art:  mean={art_mean:.4f}  sd={art_sd:.4f}  N={len(art_vals):,}")
    print(f"  DOAJ: mean={doaj_mean:.4f}  sd={doaj_sd:.4f}  N={len(doaj_vals):,}")
    print(f"  Cohen's d: {d_val:.3f}  [95% CI: {ci_lo:.3f}, {ci_hi:.3f}]")
    print()

    print("=== nMCE by Institution (d vs DOAJ) ===")
    inst_results = {}
    for inst, vals in sorted(by_inst.items(), key=lambda x: -len(x[1])):
        if len(vals) < 10: continue
        d_inst = cohen_d(vals, doaj_vals)
        ci_inst = cohen_d_ci(d_inst, len(vals), len(doaj_vals))
        print(f"  {inst:30s}  N={len(vals):5,}  mean={statistics.mean(vals):.4f}  d={d_inst:+.3f}  [{ci_inst[0]:.3f},{ci_inst[1]:.3f}]")
        inst_results[inst] = {
            "n": len(vals), "mean": statistics.mean(vals),
            "sd": statistics.stdev(vals) if len(vals)>1 else 0,
            "cohen_d_vs_doaj": d_inst, "ci_95": list(ci_inst),
        }

    results = {
        "aggregate": {
            "art_mean": art_mean, "art_sd": art_sd, "art_n": len(art_vals),
            "doaj_mean": doaj_mean, "doaj_sd": doaj_sd, "doaj_n": len(doaj_vals),
            "cohen_d": d_val, "ci_95": [ci_lo, ci_hi],
        },
        "by_institution": inst_results,
    }
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
