#!/usr/bin/env python3
"""
Cross-Layer Spearman Rank Correlation Matrix

Reproduces Section 7.4 cross-layer correlation table from the paper.
Joins all four metrics at the document URL level and computes:
  - Spearman ρ for all metric pairs
  - 95% CI via Fisher z-transformation
  - p-values (two-tailed)

Input:
  data/corpus_features.jsonl.gz   (NPC-Pre, NPC-Post, nMCE, DMI)
  data/at_scores_llama.jsonl.gz   (AT)

Output: printed matrix + output/cross_layer_results.json

Usage:
    python analysis/cross_layer.py
"""

import argparse
import gzip
import json
import math
import statistics
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Cross-layer Spearman correlation")
    p.add_argument("--features", default="data/corpus_features.jsonl.gz")
    p.add_argument("--at",       default="data/at_scores_llama.jsonl.gz")
    p.add_argument("--out",      default="output/cross_layer_results.json")
    return p.parse_args()


def spearman(xs, ys):
    n = len(xs)
    assert n == len(ys)
    if n < 20:
        return None, None
    def rank(vs):
        si = sorted(range(n), key=lambda i: vs[i])
        r = [0.0] * n; i = 0
        while i < n:
            j = i
            while j < n-1 and vs[si[j+1]] == vs[si[j]]: j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j+1): r[si[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
    den = math.sqrt(sum((rx[i]-mx)**2 for i in range(n)) *
                    sum((ry[i]-my)**2 for i in range(n)))
    rho = num/den if den > 0 else 0.0
    t = rho * math.sqrt(n-2) / math.sqrt(max(1e-12, 1 - rho**2))
    p = math.erfc(abs(t) / math.sqrt(2))
    return rho, p


def fisher_z_ci(rho, n, z=1.96):
    """95% CI on Spearman ρ via Fisher z-transformation."""
    if n < 4 or rho is None: return None, None
    zr = 0.5 * math.log((1+rho) / (1-rho))
    se = 1 / math.sqrt(n - 3)
    lo = math.tanh(zr - z*se)
    hi = math.tanh(zr + z*se)
    return lo, hi


def compute_at_per_doc(at_path):
    """Per-doc mean AT from logprob file."""
    from collections import defaultdict
    by_doc = defaultdict(list)
    opener = gzip.open if str(at_path).endswith(".gz") else open
    with opener(at_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            alts = d.get("top_alternatives", [])
            if not alts: continue
            url = d["doc_id"].rstrip("/").lower()
            p45 = sum(
                (a.get("prob",0) if isinstance(a,dict) else float(a[1]))
                for a in alts
                if str((a.get("token","") if isinstance(a,dict) else a[0])).strip() in ("4","5")
            )
            by_doc[url].append(p45)
    return {u: statistics.mean(v) for u, v in by_doc.items()}


def main():
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load AT per doc
    print("Loading AT scores...", flush=True)
    at_map = compute_at_per_doc(args.at)
    print(f"  {len(at_map):,} docs with AT", flush=True)

    # Load corpus features
    print("Loading corpus features...", flush=True)
    rows = []
    opener = gzip.open if str(args.features).endswith(".gz") else open
    with opener(args.features, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["institution"] == "doaj":
                continue  # cross-layer is art corpus only
            url = d["doc_id"].rstrip("/").lower()
            pre  = d.get("npc_pre")
            post = d.get("npc_post")
            nmce = d.get("nmce")
            dmi_l = d.get("dmi_liberal")
            dmi_c = d.get("dmi_conservative")
            at    = at_map.get(url)
            rows.append({
                "url": url, "npc_pre": pre, "npc_post": post,
                "nmce": nmce, "dmi_lib": dmi_l, "dmi_cons": dmi_c, "at": at,
            })
    print(f"  {len(rows):,} art docs loaded", flush=True)

    # Define metric pairs and their keys
    METRICS = [
        ("npc_pre",  "NPC-Pre"),
        ("npc_post", "NPC-Post"),
        ("nmce",     "nMCE"),
        ("dmi_lib",  "DMI(Liberal)"),
        ("dmi_cons", "DMI(Cons.)"),
        ("at",       "AT"),
    ]

    print("\n=== Cross-Layer Spearman ρ Matrix ===")
    print(f"{'':20s}", end="")
    for _, name in METRICS[1:]:
        print(f"  {name:14s}", end="")
    print()

    results = {}
    for i, (k1, n1) in enumerate(METRICS):
        print(f"{n1:20s}", end="")
        for j, (k2, n2) in enumerate(METRICS):
            if j <= i:
                print(f"  {'—':14s}", end="")
                continue
            # Filter to rows with both values
            pairs = [(r[k1], r[k2]) for r in rows
                     if r[k1] is not None and r[k2] is not None]
            if len(pairs) < 20:
                print(f"  {'(N<20)':14s}", end="")
                continue
            xs, ys = zip(*pairs)
            rho, p = spearman(list(xs), list(ys))
            ci_lo, ci_hi = fisher_z_ci(rho, len(pairs))
            sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else " ns"))
            cell = f"{rho:+.3f}{sig}"
            print(f"  {cell:14s}", end="")
            pair_key = f"{n1} × {n2}"
            results[pair_key] = {
                "rho": rho, "p": p, "n": len(pairs),
                "ci_95": [round(ci_lo,3), round(ci_hi,3)],
                "significant": p < 0.05,
            }
        print()

    # Highlight key findings
    print("\n--- Key pairs ---")
    for pair_key, v in results.items():
        if "NPC-Post" in pair_key and "DMI" in pair_key and "Liberal" in pair_key:
            print(f"  {pair_key}: ρ={v['rho']:+.3f}  p={v['p']:.3f}  n={v['n']:,}  (independence test)")
        if "DMI(Cons." in pair_key and "AT" in pair_key:
            print(f"  {pair_key}: ρ={v['rho']:+.3f}  p={v['p']:.2e}  n={v['n']:,}  (connectives→depth)")
        if "nMCE" in pair_key and "AT" in pair_key:
            print(f"  {pair_key}: ρ={v['rho']:+.3f}  p={v['p']:.2e}  n={v['n']:,}  (uniformity→void)")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
