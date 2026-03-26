#!/usr/bin/env python3
"""
Layer II: Normalized Modifier Concentration Entropy (nMCE)

Reproduces Section 5 (nMCE) tables from the paper:
  - Primary: all adjectives, pairs≥3, K≥2, total_nouns≥50
  - IAE/AWL variant: IAE suffix filter + stoplist
  - Top-100 variant: top-100 discriminating adjectives (chi²)
  - Per-institution breakdown (primary filter)

Input:  data/nmce_scores.jsonl.gz (adj_counter + total_nouns per doc)
Output: printed tables + output/layer2_nmce_results.json

Usage:
    python analysis/layer2_nmce.py
"""

import argparse
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# IAE filter (verbatim from cross_layer_correlation.py on workstation)
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


# ---------------------------------------------------------------------------
# nMCE computation
# ---------------------------------------------------------------------------
def compute_nmce(adj_counter):
    """Compute nMCE = H(adj distribution) / log2(K) from adjective counter."""
    K = len(adj_counter)
    if K < 2:
        return None
    total = sum(adj_counter.values())
    H = -sum((c / total) * math.log2(c / total) for c in adj_counter.values())
    return H / math.log2(K)


def filter_primary(adj_counter, total_nouns):
    """Primary filter: all adj, total pairs ≥ 3, K ≥ 2, total_nouns ≥ 50."""
    total = sum(adj_counter.values())
    if total < 3:
        return None
    if total_nouns > 0 and total_nouns < 50:
        return None
    return compute_nmce(adj_counter)


def filter_iae(adj_counter):
    """IAE/AWL filter: keep only IAE-suffix adjectives minus stoplist, K ≥ 2."""
    filtered = {a: c for a, c in adj_counter.items() if is_iae_adj(a)}
    if not filtered:
        return None
    return compute_nmce(filtered)


def filter_top100(adj_counter, top100_set):
    """Top-100 filter: keep only top-100 discriminating adjectives, K ≥ 2."""
    filtered = {a: c for a, c in adj_counter.items() if a.lower() in top100_set}
    if not filtered:
        return None
    return compute_nmce(filtered)


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def cohen_d(a, b):
    """Cohen's d using simple average of group variances (matching plot_nmce_figures.py)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    sp = math.sqrt((sa**2 + sb**2) / 2)
    return (ma - mb) / sp if sp > 0 else 0.0


def cohen_d_ci(d, n1, n2, z=1.96):
    se = math.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))
    return d - z * se, d + z * se


# ---------------------------------------------------------------------------
# Top-100 selection via chi²
# ---------------------------------------------------------------------------
def select_top100_chi2(records):
    """
    Select top-100 most discriminating adjectives using chi² test.
    Each record is (adj_counter, institution).
    """
    # Aggregate corpus-level counts
    art_adj_doc_count = Counter()   # how many art docs contain this adj
    doaj_adj_doc_count = Counter()  # how many doaj docs contain this adj
    n_art = 0
    n_doaj = 0

    for adj_counter, inst in records:
        if inst == "doaj":
            n_doaj += 1
            for a in adj_counter:
                doaj_adj_doc_count[a.lower()] += 1
        else:
            n_art += 1
            for a in adj_counter:
                art_adj_doc_count[a.lower()] += 1

    # Chi² for each adjective (2×2 table: present/absent × art/doaj)
    all_adjs = set(art_adj_doc_count) | set(doaj_adj_doc_count)
    N = n_art + n_doaj
    chi2_scores = {}

    for adj in all_adjs:
        a = art_adj_doc_count.get(adj, 0)    # art docs with adj
        b = doaj_adj_doc_count.get(adj, 0)   # doaj docs with adj
        c = n_art - a                         # art docs without adj
        d = n_doaj - b                        # doaj docs without adj

        expected_a = (a + b) * (a + c) / N if N > 0 else 0
        expected_b = (a + b) * (b + d) / N if N > 0 else 0
        expected_c = (c + d) * (a + c) / N if N > 0 else 0
        expected_d = (c + d) * (b + d) / N if N > 0 else 0

        chi2 = 0
        for obs, exp in [(a, expected_a), (b, expected_b), (c, expected_c), (d, expected_d)]:
            if exp > 0:
                chi2 += (obs - exp) ** 2 / exp

        # Require minimum frequency
        if a + b >= 5:
            chi2_scores[adj] = chi2

    # Top-100 by chi²
    sorted_adjs = sorted(chi2_scores.items(), key=lambda x: -x[1])
    return {adj for adj, _ in sorted_adjs[:100]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Layer II nMCE analysis")
    p.add_argument("--data", default="data/nmce_scores.jsonl.gz")
    p.add_argument("--out", default="output/layer2_nmce_results.json")
    return p.parse_args()


def main():
    args = parse_args()
    data_path = Path(args.data)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load all records
    records = []  # (adj_counter, total_nouns, institution)
    opener = gzip.open if str(data_path).endswith(".gz") else open
    with opener(data_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            adj_counter = d.get("adj_counter", {})
            total_nouns = d.get("total_nouns", 0)
            inst = d["institution"]
            records.append((adj_counter, total_nouns, inst))

    print(f"Loaded {len(records):,} records\n")

    # ------------------------------------------------------------------
    # 1. Primary filter (paper §5): all adj, pairs≥3, K≥2, nouns≥50
    # ------------------------------------------------------------------
    art_primary, doaj_primary = [], []
    by_inst_primary = defaultdict(list)

    for adj_counter, total_nouns, inst in records:
        v = filter_primary(adj_counter, total_nouns)
        if v is None:
            continue
        if inst == "doaj":
            doaj_primary.append(v)
        else:
            art_primary.append(v)
            by_inst_primary[inst].append(v)

    print("=" * 60)
    print("PRIMARY: All adjectives, pairs≥3, K≥2, total_nouns≥50")
    print("=" * 60)
    _print_comparison("nMCE (primary)", art_primary, doaj_primary)

    print("\n  Per-institution (d vs DOAJ):")
    inst_results_primary = {}
    for inst, vals in sorted(by_inst_primary.items(), key=lambda x: -len(x[1])):
        if len(vals) < 10:
            continue
        d_inst = cohen_d(vals, doaj_primary)
        ci_inst = cohen_d_ci(d_inst, len(vals), len(doaj_primary))
        print(f"    {inst:25s}  N={len(vals):5,}  mean={statistics.mean(vals):.4f}  d={d_inst:+.3f}  [{ci_inst[0]:.3f},{ci_inst[1]:.3f}]")
        inst_results_primary[inst] = {
            "n": len(vals),
            "mean": statistics.mean(vals),
            "sd": statistics.stdev(vals) if len(vals) > 1 else 0,
            "cohen_d_vs_doaj": d_inst,
            "ci_95": list(ci_inst),
        }

    # ------------------------------------------------------------------
    # 2. IAE/AWL filter: IAE suffix + stoplist, K≥2
    # ------------------------------------------------------------------
    art_iae, doaj_iae = [], []
    for adj_counter, _, inst in records:
        v = filter_iae(adj_counter)
        if v is None:
            continue
        if inst == "doaj":
            doaj_iae.append(v)
        else:
            art_iae.append(v)

    print("\n" + "=" * 60)
    print("IAE/AWL: IAE suffix adjectives only, K≥2")
    print("=" * 60)
    _print_comparison("nMCE (IAE)", art_iae, doaj_iae)

    # ------------------------------------------------------------------
    # 3. Top-100 discriminating adjectives (chi²)
    # ------------------------------------------------------------------
    # Use primary-filter-passing records for chi² selection
    chi2_input = []
    for adj_counter, total_nouns, inst in records:
        total = sum(adj_counter.values())
        if total < 3:
            continue
        if total_nouns > 0 and total_nouns < 50:
            continue
        chi2_input.append((adj_counter, inst))

    top100_set = select_top100_chi2(chi2_input)
    print(f"\n  Top-100 adjectives selected by chi² (sample: {list(top100_set)[:10]})")

    art_top100, doaj_top100 = [], []
    for adj_counter, total_nouns, inst in records:
        total = sum(adj_counter.values())
        if total < 3:
            continue
        if total_nouns > 0 and total_nouns < 50:
            continue
        v = filter_top100(adj_counter, top100_set)
        if v is None:
            continue
        if inst == "doaj":
            doaj_top100.append(v)
        else:
            art_top100.append(v)

    print("\n" + "=" * 60)
    print("TOP-100: Chi²-selected discriminating adjectives, K≥2")
    print("=" * 60)
    _print_comparison("nMCE (top-100)", art_top100, doaj_top100)

    # ------------------------------------------------------------------
    # Summary: all three d values
    # ------------------------------------------------------------------
    d_primary = cohen_d(art_primary, doaj_primary)
    d_iae = cohen_d(art_iae, doaj_iae)
    d_top100 = cohen_d(art_top100, doaj_top100)

    print("\n" + "=" * 60)
    print("SUMMARY: All three variants should produce d > +1.20")
    print("=" * 60)
    print(f"  Primary (all adj):  d = {d_primary:+.3f}  N_art={len(art_primary):,}  N_doaj={len(doaj_primary):,}")
    print(f"  IAE/AWL:            d = {d_iae:+.3f}  N_art={len(art_iae):,}  N_doaj={len(doaj_iae):,}")
    print(f"  Top-100 (chi²):     d = {d_top100:+.3f}  N_art={len(art_top100):,}  N_doaj={len(doaj_top100):,}")

    # ------------------------------------------------------------------
    # Build results JSON
    # ------------------------------------------------------------------
    def _build_variant(art, doaj, label):
        if not art or not doaj:
            return {"error": f"No data for {label}"}
        d_val = cohen_d(art, doaj)
        ci = cohen_d_ci(d_val, len(art), len(doaj))
        return {
            "art_mean": statistics.mean(art),
            "art_sd": statistics.stdev(art),
            "art_n": len(art),
            "doaj_mean": statistics.mean(doaj),
            "doaj_sd": statistics.stdev(doaj),
            "doaj_n": len(doaj),
            "cohen_d": d_val,
            "ci_95": list(ci),
        }

    results = {
        "primary": _build_variant(art_primary, doaj_primary, "primary"),
        "iae_awl": _build_variant(art_iae, doaj_iae, "IAE/AWL"),
        "top100_chi2": _build_variant(art_top100, doaj_top100, "top-100"),
        "by_institution": inst_results_primary,
    }

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


def _print_comparison(label, art_vals, doaj_vals):
    if not art_vals or not doaj_vals:
        print(f"  {label}: insufficient data")
        return
    art_mean = statistics.mean(art_vals)
    art_sd = statistics.stdev(art_vals)
    doaj_mean = statistics.mean(doaj_vals)
    doaj_sd = statistics.stdev(doaj_vals)
    d_val = cohen_d(art_vals, doaj_vals)
    ci_lo, ci_hi = cohen_d_ci(d_val, len(art_vals), len(doaj_vals))
    print(f"  Art:  mean={art_mean:.4f}  sd={art_sd:.4f}  N={len(art_vals):,}")
    print(f"  DOAJ: mean={doaj_mean:.4f}  sd={doaj_sd:.4f}  N={len(doaj_vals):,}")
    print(f"  Cohen's d: {d_val:+.3f}  [95% CI: {ci_lo:.3f}, {ci_hi:.3f}]")


if __name__ == "__main__":
    main()
