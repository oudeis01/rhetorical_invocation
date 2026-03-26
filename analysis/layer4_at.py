#!/usr/bin/env python3
"""
Layer IV: Analytical Tendency (AT)

Reproduces Section 7 (AT) tables from the paper.

AT is computed as the per-pair mean of P(depth=4) + P(depth=5) over all
(doc, discourse) pairs where top_alternatives is non-empty.

Note on averaging: The paper reports corpus-level AT as the mean over
all pairs (not per-doc then re-averaged), which weights documents by
their number of discourse pairs. This matches the formula:
  AT = sum(P(L4)+P(L5) for all pairs) / N_pairs

Input:
  data/at_scores_llama.jsonl.gz  (art + DOAJ pairs, institution field marks DOAJ)
  data/at_scores_qwen.jsonl.gz   (optional)
  data/url_category_map.json.gz  (for institution/category disaggregation)

Output: printed tables + output/layer4_at_results.json

Usage:
  python analysis/layer4_at.py
  python analysis/layer4_at.py --llama data/at_scores_llama.jsonl.gz
"""

import argparse, gzip, json, math, statistics
from collections import defaultdict
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Layer IV AT analysis")
    p.add_argument("--llama", default="data/at_scores_llama.jsonl.gz")
    p.add_argument("--qwen", default="data/at_scores_qwen.jsonl.gz")
    p.add_argument("--catmap", default="data/url_category_map.json.gz")
    p.add_argument("--out", default="output/layer4_at_results.json")
    return p.parse_args()


def load_at_scores(path):
    """
    Returns:
      pairs_by_doc : dict  url -> list[float]  P(L4)+P(L5) per ENGAGED pair.
                          No-engagement pairs (synthetic token=0, prob=1.0) are
                          excluded from the AT values but their doc_ids are still
                          recorded so N_docs covers the full corpus.
      doaj_urls    : set   of DOAJ doc URLs
      all_doc_urls : set   of all doc URLs seen (including no-engagement-only docs)
      depth_counts : dict  level -> pair count (engaged pairs only)
    """
    pairs_by_doc = defaultdict(list)  # url -> [p45, ...]  engaged pairs only
    all_doc_urls = set()  # all doc_ids seen (for N_docs count)
    depth_counts = defaultdict(int)
    doaj_urls = set()

    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            alts = d.get("top_alternatives", [])
            if not alts:
                continue
            url = d["doc_id"]
            all_doc_urls.add(url)
            if d.get("institution", "") == "doaj":
                doaj_urls.add(url)

            # Detect synthetic no-engagement marker:
            # [{"token": "0", "prob": 1.0}]  => skip AT contribution
            is_no_eng = (
                len(alts) == 1
                and str(alts[0].get("token", "")).strip() == "0"
                and alts[0].get("prob", 0) >= 0.999
            )
            if is_no_eng:
                # Record doc existence but do not contribute to AT values
                pairs_by_doc[url]  # touch dict to ensure doc is counted
                continue

            p45 = sum(
                (a.get("prob", 0) if isinstance(a, dict) else float(a[1]))
                for a in alts
                if str((a.get("token", "") if isinstance(a, dict) else a[0])).strip()
                in ("4", "5")
            )
            pairs_by_doc[url].append(p45)

            # Depth-level distribution: infer from top alternative token
            level = d.get("depth_level", 0)
            if level == 0:
                top = max(
                    alts,
                    key=lambda a: (
                        a.get("prob", 0) if isinstance(a, dict) else float(a[1])
                    ),
                )
                tok = str(
                    top.get("token", "0") if isinstance(top, dict) else top[0]
                ).strip()
                level = int(tok) if tok.isdigit() else 0
            depth_counts[level] += 1

    return pairs_by_doc, doaj_urls, all_doc_urls, depth_counts


def corpus_at(pairs_by_doc, url_set=None):
    """Per-pair mean AT over a set of URLs (or all if url_set is None)."""
    all_vals = []
    for url, vals in pairs_by_doc.items():
        if url_set is not None and url not in url_set:
            continue
        all_vals.extend(vals)
    return statistics.mean(all_vals) if all_vals else None, len(all_vals)


def segment_ci(vals):
    """95% CI on per-doc mean AT (t-distribution, used for segment CIs)."""
    n = len(vals)
    if n == 0:
        return None, None, None
    m = statistics.mean(vals)
    if n < 2:
        return m, None, None
    se = statistics.stdev(vals) / math.sqrt(n)
    t = (
        1.96
        if n > 100
        else (2.01 if n > 50 else (2.04 if n > 30 else (2.23 if n > 10 else 2.78)))
    )
    return m, round(m - t * se, 4), round(m + t * se, 4)


def main():
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cat_map = {}
    cm_path = Path(args.catmap)
    if cm_path.exists():
        opener = gzip.open if str(cm_path).endswith(".gz") else open
        with opener(cm_path, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        cat_map = {k.rstrip("/").lower(): v for k, v in raw.items()}

    def get_seg(url):
        e = cat_map.get(url.rstrip("/").lower())
        return (e["institution"], e["category"]) if e else ("unknown", "other")

    results = {}

    for model_name, at_path in [("llama", args.llama), ("qwen", args.qwen)]:
        p = Path(at_path)
        if not p.exists():
            print(f"[{model_name}] not found: {at_path}, skipping.\n")
            continue

        print(f"\n{'=' * 60}")
        print(f"Model: {model_name.upper()}")
        print(f"{'=' * 60}")

        pairs_by_doc, doaj_urls, all_doc_urls, depth_counts = load_at_scores(p)

        # N_docs = all docs seen (including no-engagement-only docs)
        art_all_urls = all_doc_urls - doaj_urls
        doaj_all_urls = doaj_urls

        # AT mean over engaged pairs only (docs with no engagement contribute 0 pairs)
        art_at, n_art_pairs = corpus_at(pairs_by_doc, art_all_urls)
        doaj_at, n_doaj_pairs = corpus_at(pairs_by_doc, doaj_all_urls)

        print(f"\n--- Aggregate AT (per-pair mean, engaged pairs only) ---")
        print(
            f"  Art  N={len(art_all_urls):,} docs / {n_art_pairs:,} engaged pairs   AT={art_at:.4f}"
        )
        print(
            f"  DOAJ N={len(doaj_all_urls):,} docs / {n_doaj_pairs:,} engaged pairs   AT={doaj_at:.4f}"
        )
        if art_at and doaj_at:
            print(f"  DOAJ/Art ratio: {doaj_at / art_at:.2f}x")

        # Depth distribution (among engaged pairs only, i.e. level > 0)
        total_engaged = sum(v for k, v in depth_counts.items() if k > 0)
        print(
            f"\n--- Depth Level Distribution (among engaged pairs, N={total_engaged:,}) ---"
        )
        labels = {
            1: "Mention",
            2: "Decorative",
            3: "Contextual",
            4: "Analytical",
            5: "Theoretical",
        }
        for lv in sorted(k for k in depth_counts if k > 0):
            pct = 100 * depth_counts[lv] / total_engaged
            print(f"  L{lv} {labels.get(lv):12s}: {depth_counts[lv]:7,} ({pct:5.1f}%)")

        # Per-segment AT (per-doc mean for CIs)
        # Skip docs with no engaged pairs (no-engagement-only docs have empty list)
        per_doc_at = {
            u: statistics.mean(v)
            for u, v in pairs_by_doc.items()
            if v  # non-empty list only
        }
        segs = defaultdict(list)
        for url, at in per_doc_at.items():
            if url in doaj_urls:
                continue
            inst, cat = get_seg(url)
            segs[f"{inst}/{cat}"].append(at)

        print(f"\n--- Top Segments (min N=5, per-doc CI) vs DOAJ {doaj_at:.4f} ---")
        seg_rows = sorted(
            [(seg, v) for seg, v in segs.items() if "/" in seg and len(v) >= 5],
            key=lambda x: -statistics.mean(x[1]),
        )
        seg_results = {}
        for seg, vals in seg_rows[:15]:
            m, ci_lo, ci_hi = segment_ci(vals)
            pct = m / doaj_at * 100 if doaj_at else None
            ci_str = f"[{ci_lo:.3f},{ci_hi:.3f}]" if ci_lo else "—"
            pct_str = f"{pct:.0f}%" if pct else "—"
            print(f"  {seg:40s}  N={len(vals):5,}  AT={m:.4f}  {ci_str}  {pct_str}")
            seg_results[seg] = {
                "n": len(vals),
                "mean": round(m, 4),
                "ci_95": [ci_lo, ci_hi] if ci_lo else None,
                "pct_of_doaj": round(pct, 1) if pct else None,
            }

        results[model_name] = {
            "art_at": art_at,
            "art_docs": len(art_all_urls),
            "art_pairs": n_art_pairs,
            "doaj_at": doaj_at,
            "doaj_docs": len(doaj_all_urls),
            "doaj_pairs": n_doaj_pairs,
            "doaj_art_ratio": round(doaj_at / art_at, 2)
            if art_at and doaj_at
            else None,
            "depth_distribution": dict(depth_counts),
            "segments": seg_results,
        }

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
