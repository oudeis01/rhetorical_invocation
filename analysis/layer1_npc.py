#!/usr/bin/env python3
"""
Layer I: Noun Phrase Complexity (NPC)

Reproduces Section 4 (NPC) tables from the paper:
  - Aggregate NPC-Pre and NPC-Post for art corpus vs DOAJ baseline
  - Cohen's d
  - TOST equivalence test (Δ = ±0.20)
  - OLS regression controlling for log(total_nouns) → length-adjusted d

Input:  data/corpus_features.jsonl.gz
Output: printed tables (stdout) + output/layer1_npc_results.json

Usage:
    python analysis/layer1_npc.py
    python analysis/layer1_npc.py --data path/to/corpus_features.jsonl.gz
"""

import argparse
import gzip
import json
import math
import statistics
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Layer I NPC analysis")
    p.add_argument("--data", default="data/corpus_features.jsonl.gz",
                   help="Path to corpus_features.jsonl.gz")
    p.add_argument("--out", default="output/layer1_npc_results.json",
                   help="Output JSON path")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def cohen_d(a, b):
    """Pooled-SD Cohen's d (a vs b)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    sp = math.sqrt(((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2))
    return (ma - mb) / sp if sp > 0 else 0.0


def cohen_d_ci(d, n1, n2, z=1.96):
    """95% CI on Cohen's d via large-sample normal approximation."""
    se = math.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))
    return d - z * se, d + z * se


def tost_result(d, ci_lo, ci_hi, bound=0.20):
    """TOST equivalence test: both 90% CI bounds inside ±bound."""
    # 90% CI (z=1.645)
    return "Equivalent" if ci_lo > -bound and ci_hi < bound else "Not Equivalent"


def ols_length_adjusted_d(art_vals, doaj_vals, art_log_nouns, doaj_log_nouns):
    """
    OLS: metric ~ intercept + is_doaj + log_nouns
    Returns length-adjusted Cohen's d (coefficient on is_doaj / pooled residual SD).
    """
    # Build design matrix [1, is_doaj, log_nouns]
    X = [(1, 0, ln) for ln in art_log_nouns] + [(1, 1, ln) for ln in doaj_log_nouns]
    y = list(art_vals) + list(doaj_vals)
    n = len(y)

    # OLS via normal equations (XtX)^-1 Xt y  — 3×3 system
    def dot(a, b): return sum(ai * bi for ai, bi in zip(a, b))
    Xt = [[row[j] for row in X] for j in range(3)]
    XtX = [[dot(Xt[i], Xt[j]) for j in range(3)] for i in range(3)]
    Xty = [dot(Xt[i], y) for i in range(3)]

    # 3×3 matrix inverse via cofactors
    def det3(m):
        return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
               -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
               +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
    def inv3(m):
        d = det3(m)
        cofactors = [
            [ (m[1][1]*m[2][2]-m[1][2]*m[2][1])/d, -(m[0][1]*m[2][2]-m[0][2]*m[2][1])/d,  (m[0][1]*m[1][2]-m[0][2]*m[1][1])/d],
            [-(m[1][0]*m[2][2]-m[1][2]*m[2][0])/d,  (m[0][0]*m[2][2]-m[0][2]*m[2][0])/d, -(m[0][0]*m[1][2]-m[0][2]*m[1][0])/d],
            [ (m[1][0]*m[2][1]-m[1][1]*m[2][0])/d, -(m[0][0]*m[2][1]-m[0][1]*m[2][0])/d,  (m[0][0]*m[1][1]-m[0][1]*m[1][0])/d],
        ]
        return cofactors

    inv = inv3(XtX)
    beta = [sum(inv[i][j] * Xty[j] for j in range(3)) for i in range(3)]

    # Residual SD
    y_hat = [sum(beta[j] * X[i][j] for j in range(3)) for i in range(n)]
    sse = sum((y[i] - y_hat[i])**2 for i in range(n))
    residual_sd = math.sqrt(sse / (n - 3)) if n > 3 else 1.0

    adj_d = beta[1] / residual_sd if residual_sd > 0 else 0.0
    return adj_d, beta


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    data_path = Path(args.data)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load
    art_pre, art_post, art_ln = [], [], []
    doaj_pre, doaj_post, doaj_ln = [], [], []

    opener = gzip.open if str(data_path).endswith(".gz") else open
    with opener(data_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            pre  = d.get("npc_pre")
            post = d.get("npc_post")
            nn   = d.get("total_nouns", 0)
            if pre is None or post is None or nn < 5:
                continue
            ln = math.log(nn)
            if d["institution"] == "doaj":
                doaj_pre.append(pre); doaj_post.append(post); doaj_ln.append(ln)
            else:
                art_pre.append(pre);  art_post.append(post);  art_ln.append(ln)

    print(f"Loaded: Art N={len(art_pre):,}, DOAJ N={len(doaj_pre):,}\n")

    results = {}

    for label, art_vals, doaj_vals, art_log_n, doaj_log_n in [
        ("NPC-Pre",  art_pre,  doaj_pre,  art_ln, doaj_ln),
        ("NPC-Post", art_post, doaj_post, art_ln, doaj_ln),
    ]:
        art_mean  = statistics.mean(art_vals)
        doaj_mean = statistics.mean(doaj_vals)
        art_sd    = statistics.stdev(art_vals)
        doaj_sd   = statistics.stdev(doaj_vals)
        d_val     = cohen_d(art_vals, doaj_vals)
        ci_lo, ci_hi = cohen_d_ci(d_val, len(art_vals), len(doaj_vals))

        # 90% CI for TOST
        z90 = 1.645
        se = math.sqrt((len(art_vals)+len(doaj_vals))/(len(art_vals)*len(doaj_vals))
                       + d_val**2/(2*(len(art_vals)+len(doaj_vals))))
        ci90_lo, ci90_hi = d_val - z90*se, d_val + z90*se
        tost = tost_result(d_val, ci90_lo, ci90_hi)

        # OLS length-adjusted d
        adj_d, _ = ols_length_adjusted_d(art_vals, doaj_vals, art_log_n, doaj_log_n)
        adj_ci_lo, adj_ci_hi = cohen_d_ci(adj_d, len(art_vals), len(doaj_vals))

        print(f"=== {label} ===")
        print(f"  Art:  mean={art_mean:.4f}  sd={art_sd:.4f}  N={len(art_vals):,}")
        print(f"  DOAJ: mean={doaj_mean:.4f}  sd={doaj_sd:.4f}  N={len(doaj_vals):,}")
        print(f"  Art/DOAJ ratio: {art_mean/doaj_mean:.3f}×")
        print(f"  Cohen's d:      {d_val:.3f}  [95% CI: {ci_lo:.3f}, {ci_hi:.3f}]")
        print(f"  TOST (Δ=±0.20, 90% CI [{ci90_lo:.3f},{ci90_hi:.3f}]): {tost}")
        print(f"  Length-adjusted d: {adj_d:.3f}  [95% CI: {adj_ci_lo:.3f}, {adj_ci_hi:.3f}]")
        print()

        results[label] = {
            "art_mean": art_mean, "art_sd": art_sd, "art_n": len(art_vals),
            "doaj_mean": doaj_mean, "doaj_sd": doaj_sd, "doaj_n": len(doaj_vals),
            "cohen_d": d_val, "ci_95": [ci_lo, ci_hi],
            "tost_90ci": [ci90_lo, ci90_hi], "tost": tost,
            "length_adjusted_d": adj_d, "length_adjusted_d_ci95": [adj_ci_lo, adj_ci_hi],
        }

    # Post/Pre ratio
    print("=== Post/Pre Ratio ===")
    art_ratio  = statistics.mean(art_post) / statistics.mean(art_pre)
    doaj_ratio = statistics.mean(doaj_post) / statistics.mean(doaj_pre)
    print(f"  Art:  {art_ratio:.2f}")
    print(f"  DOAJ: {doaj_ratio:.2f}")
    results["post_pre_ratio"] = {"art": art_ratio, "doaj": doaj_ratio}

    # Save
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
