#!/usr/bin/env python3
"""
Cross-Layer Spearman Rank Correlation Matrix

Reproduces Section 7.4 cross-layer correlation table from the paper.
Computes TWO correlation matrices:

  (A) Paper-exact: matches the original inline computation
      - nMCE: IAE suffix filter
      - DMI: w=0.5 (CSV default dmi_score column)
      - AT: p0≥0.999 engagement filter (N≈37,476)

  (B) Consistent: uses the same data as per-layer analyses (§4-7)
      - nMCE: primary filter (all adj, pairs≥3, K≥2, nouns≥50)
      - DMI: w=1.0 (recomputed)
      - AT: all pairs including no-engagement

Input:
  data/npc_scores.jsonl.gz      (NPC-Pre, NPC-Post)
  data/nmce_scores.jsonl.gz     (adj_counter → filtered nMCE)
  data/dmi_scores.jsonl.gz      (DMI w=1.0 + w=0.5 CSV scores)
  data/at_scores_llama.jsonl.gz (AT)

Output: printed matrices + output/cross_layer_results.json

Usage:
    python analysis/cross_layer.py
"""

import argparse
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# IAE filter (for paper-exact nMCE)
# ---------------------------------------------------------------------------
IAE_SUFFIXES = ("ic", "al", "ive", "ary", "ist", "ous", "ian")
STOPLIST = {
    "national", "international", "digital", "visual", "local", "global",
    "social", "political", "historical", "cultural", "physical", "natural",
    "original", "traditional", "personal", "professional", "additional",
    "various", "special", "general", "technical", "individual", "practical",
    "logical", "functional", "experimental", "educational", "institutional",
    "environmental", "commercial", "regional", "urban", "rural", "economic",
    "classical", "structural", "central", "fundamental", "formal", "annual",
    "official", "final", "initial", "minimal", "virtual", "horizontal",
    "vertical",
}


def is_iae_adj(a):
    low = a.lower()
    if low in STOPLIST:
        return False
    for s in IAE_SUFFIXES:
        if low.endswith(s):
            return True
    return False


def compute_nmce_iae(adj_counter):
    """nMCE with IAE filter."""
    filtered = {a: c for a, c in adj_counter.items() if is_iae_adj(a)}
    K = len(filtered)
    if K < 2:
        return None
    total = sum(filtered.values())
    H = -sum((c / total) * math.log2(c / total) for c in filtered.values())
    return H / math.log2(K)


def compute_nmce_primary(adj_counter, total_nouns):
    """nMCE with primary filter (all adj, pairs≥3, K≥2, nouns≥50)."""
    K = len(adj_counter)
    if K < 2:
        return None
    total = sum(adj_counter.values())
    if total < 3:
        return None
    if total_nouns > 0 and total_nouns < 50:
        return None
    H = -sum((c / total) * math.log2(c / total) for c in adj_counter.values())
    return H / math.log2(K)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def spearman(xs, ys):
    n = len(xs)
    assert n == len(ys)
    if n < 20:
        return None, None

    def rank(vs):
        si = sorted(range(n), key=lambda i: vs[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and vs[si[j + 1]] == vs[si[j]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[si[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(
        sum((rx[i] - mx) ** 2 for i in range(n))
        * sum((ry[i] - my) ** 2 for i in range(n))
    )
    rho = num / den if den > 0 else 0.0
    t = rho * math.sqrt(n - 2) / math.sqrt(max(1e-12, 1 - rho**2))
    p = math.erfc(abs(t) / math.sqrt(2))
    return rho, p


def fisher_z_ci(rho, n, z=1.96):
    if n < 4 or rho is None:
        return None, None
    zr = 0.5 * math.log((1 + rho) / (1 - rho))
    se = 1 / math.sqrt(n - 3)
    lo = math.tanh(zr - z * se)
    hi = math.tanh(zr + z * se)
    return lo, hi


def norm_url(u):
    return u.rstrip("/").lower() if u else ""


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
def load_npc(path):
    """Returns {url: (npc_pre, npc_post)} for art docs only."""
    result = {}
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["institution"] == "doaj":
                continue
            pre = d.get("npc_pre")
            post = d.get("npc_post")
            if pre is None or post is None:
                continue
            url = norm_url(d.get("url", ""))
            result[url] = (pre, post)
    return result


def load_nmce(path):
    """Returns {url: (nmce_iae, nmce_primary)} for art docs."""
    iae_result = {}
    primary_result = {}
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["institution"] == "doaj":
                continue
            adj_counter = d.get("adj_counter", {})
            total_nouns = d.get("total_nouns", 0)
            url = norm_url(d.get("url", ""))

            v_iae = compute_nmce_iae(adj_counter)
            if v_iae is not None:
                iae_result[url] = v_iae

            v_primary = compute_nmce_primary(adj_counter, total_nouns)
            if v_primary is not None:
                primary_result[url] = v_primary
    return iae_result, primary_result


def load_dmi(path):
    """Returns {url: (w1_lib, w1_cons, w05_lib, w05_cons)} for art docs."""
    result = {}
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["institution"] == "doaj":
                continue
            url = norm_url(d.get("url", ""))
            w1_l = d.get("dmi_liberal", 0.0)
            w1_c = d.get("dmi_conservative", 0.0)
            w05_l = d.get("dmi_csv_liberal", 0.0)
            w05_c = d.get("dmi_csv_conservative", 0.0)
            # URL-level aggregation (average multi-chunk)
            if url in result:
                old = result[url]
                result[url] = (
                    old[0] + w1_l, old[1] + w1_c,
                    old[2] + w05_l, old[3] + w05_c,
                    old[4] + 1,
                )
            else:
                result[url] = (w1_l, w1_c, w05_l, w05_c, 1)
    return {
        url: (s[0]/s[4], s[1]/s[4], s[2]/s[4], s[3]/s[4])
        for url, s in result.items()
    }


def load_at(path):
    """Returns (at_all, at_engaged) dicts.
    at_all: {url: mean P(4)+P(5)} including no-engagement pairs.
    at_engaged: {url: mean P(4)+P(5)} excluding p0≥0.999 pairs (paper-exact).
    """
    by_doc_all = defaultdict(list)
    by_doc_engaged = defaultdict(list)
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("institution") == "doaj":
                continue
            alts = d.get("top_alternatives", [])
            if not alts:
                continue
            url = norm_url(d["doc_id"])

            # Compute p0 and p45
            p0 = sum(
                (a.get("prob", 0) if isinstance(a, dict) else float(a[1]))
                for a in alts
                if str(a.get("token", "") if isinstance(a, dict) else a[0]).strip()
                in ("0",)
            )
            p45 = sum(
                (a.get("prob", 0) if isinstance(a, dict) else float(a[1]))
                for a in alts
                if str(a.get("token", "") if isinstance(a, dict) else a[0]).strip()
                in ("4", "5")
            )

            by_doc_all[url].append(p45)
            if p0 < 0.999:
                by_doc_engaged[url].append(p45)

    at_all = {u: statistics.mean(v) for u, v in by_doc_all.items()}
    at_engaged = {u: statistics.mean(v) for u, v in by_doc_engaged.items() if v}
    return at_all, at_engaged


# ---------------------------------------------------------------------------
# Matrix computation
# ---------------------------------------------------------------------------
def compute_matrix(rows, metrics, label):
    """Compute and print Spearman ρ matrix. Returns results dict."""
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}")
    print(f"{'':20s}", end="")
    for _, name in metrics[1:]:
        print(f"  {name:14s}", end="")
    print()

    results = {}
    for i, (k1, n1) in enumerate(metrics):
        print(f"{n1:20s}", end="")
        for j, (k2, n2) in enumerate(metrics):
            if j <= i:
                print(f"  {'—':14s}", end="")
                continue
            pairs = [
                (r[k1], r[k2])
                for r in rows
                if r[k1] is not None and r[k2] is not None
            ]
            if len(pairs) < 20:
                print(f"  {'(N<20)':14s}", end="")
                continue
            xs, ys = zip(*pairs)
            rho, p = spearman(list(xs), list(ys))
            ci_lo, ci_hi = fisher_z_ci(rho, len(pairs))
            sig = (
                "***" if p < 0.001
                else ("**" if p < 0.01 else ("*" if p < 0.05 else " ns"))
            )
            cell = f"{rho:+.3f}{sig}"
            print(f"  {cell:14s}", end="")
            pair_key = f"{n1} × {n2}"
            results[pair_key] = {
                "rho": rho,
                "p": p,
                "n": len(pairs),
                "ci_95": [round(ci_lo, 3), round(ci_hi, 3)],
                "significant": p < 0.05,
            }
        print()
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Cross-layer Spearman correlation")
    p.add_argument("--npc", default="data/npc_scores.jsonl.gz")
    p.add_argument("--nmce", default="data/nmce_scores.jsonl.gz")
    p.add_argument("--dmi", default="data/dmi_scores.jsonl.gz")
    p.add_argument("--at", default="data/at_scores_llama.jsonl.gz")
    p.add_argument("--out", default="output/cross_layer_results.json")
    return p.parse_args()


def main():
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load all layers
    print("Loading NPC...", flush=True)
    npc_map = load_npc(args.npc)
    print(f"  {len(npc_map):,} art docs", flush=True)

    print("Loading nMCE (IAE + primary)...", flush=True)
    nmce_iae_map, nmce_primary_map = load_nmce(args.nmce)
    print(f"  {len(nmce_iae_map):,} art docs (IAE), {len(nmce_primary_map):,} (primary)", flush=True)

    print("Loading DMI (w=1.0 + w=0.5)...", flush=True)
    dmi_map = load_dmi(args.dmi)
    print(f"  {len(dmi_map):,} art docs", flush=True)

    print("Loading AT (all + engaged)...", flush=True)
    at_all_map, at_engaged_map = load_at(args.at)
    print(f"  {len(at_all_map):,} art docs (all), {len(at_engaged_map):,} (engaged p0<0.999)", flush=True)

    # =====================================================================
    # (A) Paper-exact: IAE nMCE + w=0.5 DMI + engaged AT
    # =====================================================================
    all_urls_paper = set(at_engaged_map)  # AT drives join (paper behavior)
    rows_paper = []
    for url in all_urls_paper:
        npc = npc_map.get(url)
        nmce = nmce_iae_map.get(url)
        dmi = dmi_map.get(url)
        at = at_engaged_map.get(url)
        row = {
            "npc_pre": npc[0] if npc else None,
            "npc_post": npc[1] if npc else None,
            "nmce": nmce,
            "dmi_lib": dmi[2] if dmi else None,   # w=0.5
            "dmi_cons": dmi[3] if dmi else None,   # w=0.5
            "at": at,
        }
        rows_paper.append(row)

    full_paper = sum(
        1 for r in rows_paper
        if all(r[k] is not None for k in ("npc_pre", "nmce", "dmi_lib", "at"))
    )
    print(f"\n(A) Paper-exact: {len(rows_paper):,} AT-driven docs, {full_paper:,} with all metrics")

    METRICS = [
        ("npc_pre", "NPC-Pre"),
        ("npc_post", "NPC-Post"),
        ("nmce", "nMCE"),
        ("dmi_lib", "DMI(lib)"),
        ("dmi_cons", "DMI(cons)"),
        ("at", "AT"),
    ]

    results_paper = compute_matrix(
        rows_paper, METRICS,
        "(A) PAPER-EXACT: nMCE=IAE, DMI=w0.5, AT=engaged (p0<0.999)",
    )

    # Print paper targets
    print("\n  Paper targets:")
    targets = {
        "NPC-Pre × AT": (+0.1641, 37472),
        "NPC-Post × DMI(lib)": (-0.0087, 37470),
        "nMCE × AT": (-0.2107, 34609),
        "DMI(cons) × AT": (+0.2983, 37474),
    }
    for pair_key, (target_rho, target_n) in targets.items():
        if pair_key in results_paper:
            v = results_paper[pair_key]
            print(f"    {pair_key:30s}: ρ={v['rho']:+.4f} n={v['n']:,}  (target: {target_rho:+.4f} n={target_n:,})")

    # =====================================================================
    # (B) Consistent: primary nMCE + w=1.0 DMI + all AT
    # =====================================================================
    all_urls_cons = set(npc_map) | set(nmce_primary_map) | set(dmi_map) | set(at_all_map)
    rows_cons = []
    for url in all_urls_cons:
        npc = npc_map.get(url)
        nmce = nmce_primary_map.get(url)
        dmi = dmi_map.get(url)
        at = at_all_map.get(url)
        row = {
            "npc_pre": npc[0] if npc else None,
            "npc_post": npc[1] if npc else None,
            "nmce": nmce,
            "dmi_lib": dmi[0] if dmi else None,   # w=1.0
            "dmi_cons": dmi[1] if dmi else None,   # w=1.0
            "at": at,
        }
        rows_cons.append(row)

    full_cons = sum(
        1 for r in rows_cons
        if all(r[k] is not None for k in ("npc_pre", "nmce", "dmi_lib", "at"))
    )
    print(f"\n(B) Consistent: {len(rows_cons):,} union docs, {full_cons:,} with all metrics")

    METRICS_CONS = [
        ("npc_pre", "NPC-Pre"),
        ("npc_post", "NPC-Post"),
        ("nmce", "nMCE"),
        ("dmi_lib", "DMI(Liberal)"),
        ("dmi_cons", "DMI(Cons.)"),
        ("at", "AT"),
    ]

    results_cons = compute_matrix(
        rows_cons, METRICS_CONS,
        "(B) CONSISTENT: nMCE=primary, DMI=w1.0, AT=all",
    )

    # Save both
    output = {
        "paper_exact": results_paper,
        "consistent": results_cons,
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
