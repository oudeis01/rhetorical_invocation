#!/usr/bin/env python3
"""
generate_figures.py

Generates all five figures for the rhetorical_invocation repo.
All figures are produced solely from data files in data/.

Output: figures/fig1_at_institution.png
        figures/fig2_at_format.png
        figures/fig3_nmce_distribution.png
        figures/fig4_dmi_zerorate.png
        figures/fig5_crosslayer_heatmap.png

Usage:
    python scripts/generate_figures.py [--out figures/]
"""

import argparse
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from scipy import stats
import seaborn as sns


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
DOAJ_COLOR = "#E05A2B"   # orange-red for DOAJ baseline
ART_COLOR  = "#2B6CB0"   # blue for art institutions
GRAY       = "#9E9E9E"

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        10,
    "axes.titlesize":   11,
    "axes.titleweight": "bold",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "figure.dpi":       150,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
})

INST_LABELS = {
    "artforum":         "Artforum",
    "e-flux":           "e-flux",
    "moussemagazine":   "Mousse Magazine",
    "neuralit":         "Neural.it",
    "creative_app_net": "Creative Applications",
    "ars_electronica":  "Ars Electronica",
    "tate":             "Tate",
    "v2lab":            "V2_Lab",
    "transmediale":     "Transmediale",
    "spikeart":         "Spike Art",
    "afterall":         "Afterall",
    "zkm":              "ZKM",
    "stedelijk":        "Stedelijk",
    "timothy_morton_corpus": "T. Morton (corpus)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _opener(path):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")


def cohen_d_simple(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    sp = math.sqrt((sa**2 + sb**2) / 2)
    return (ma - mb) / sp if sp > 0 else 0.0


def spearman_r(x, y):
    r, p = stats.spearmanr(x, y)
    return float(r), float(p)


def sig_stars(p):
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "ns"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
def load_at(path):
    """Returns {doc_id: at_mean} for docs with non-empty top_alternatives, art only."""
    doc_vals = defaultdict(list)
    doc_inst = {}
    with _opener(path) as f:
        for line in f:
            d = json.loads(line)
            if d["top_alternatives"]:
                doc_vals[d["doc_id"]].append(d["at_value"])
                doc_inst[d["doc_id"]] = d["institution"]
    return {doc: sum(v)/len(v) for doc, v in doc_vals.items()}, doc_inst


def load_npc(path):
    """Returns {url: (npc_pre, npc_post, total_nouns, institution)}"""
    records = {}
    with _opener(path) as f:
        for line in f:
            d = json.loads(line)
            records[d["url"]] = (d["npc_pre"], d["npc_post"], d["total_nouns"], d["institution"])
    return records


def load_nmce(path):
    """Returns raw records list: (adj_counter, total_nouns, institution, url)"""
    records = []
    with _opener(path) as f:
        for line in f:
            d = json.loads(line)
            records.append((d["adj_counter"], d["total_nouns"], d["institution"], d["url"]))
    return records


def load_dmi(path):
    """Returns {url: record_dict} for all docs."""
    records = {}
    with _opener(path) as f:
        for line in f:
            d = json.loads(line)
            records[d["url"]] = d
    return records


def compute_nmce_primary(adj_counter, total_nouns):
    K = len(adj_counter)
    if K < 2:
        return None
    total = sum(adj_counter.values())
    if total < 3:
        return None
    if total_nouns > 0 and total_nouns < 50:
        return None
    H = -sum((c/total)*math.log2(c/total) for c in adj_counter.values())
    return H / math.log2(K)


IAE_SUFFIXES = ("ic", "al", "ive", "ary", "ist", "ous", "ian")
IAE_STOPLIST = {
    "national", "international", "digital", "visual", "local", "global",
    "social", "political", "historical", "cultural", "physical", "natural",
    "original", "traditional", "personal", "professional", "additional",
    "various", "special", "general", "technical", "individual", "practical",
    "logical", "functional", "experimental", "educational", "institutional",
    "environmental", "commercial", "regional", "urban", "rural", "economic",
    "classical", "structural", "central", "fundamental", "formal", "annual",
    "official", "final", "initial", "minimal", "virtual", "horizontal", "vertical",
}

def is_iae(a):
    low = a.lower()
    if low in IAE_STOPLIST:
        return False
    return any(low.endswith(s) for s in IAE_SUFFIXES)

def compute_nmce_iae(adj_counter):
    filtered = {a: c for a, c in adj_counter.items() if is_iae(a)}
    K = len(filtered)
    if K < 2:
        return None
    total = sum(filtered.values())
    if total < 1:
        return None
    H = -sum((c/total)*math.log2(c/total) for c in filtered.values())
    return H / math.log2(K)


# ---------------------------------------------------------------------------
# Fig 1: AT by institution
# ---------------------------------------------------------------------------
def fig1_at_institution(at_path, out_path):
    print("Generating Fig 1: AT by institution...")
    at_map, doc_inst = load_at(at_path)

    # AT per institution
    inst_vals = defaultdict(list)
    doaj_vals = []
    for doc, at_val in at_map.items():
        inst = doc_inst[doc]
        if inst == "doaj":
            doaj_vals.append(at_val)
        else:
            inst_vals[inst].append(at_val)

    doaj_mean = statistics.mean(doaj_vals) if doaj_vals else 0

    rows = []
    for inst, vals in inst_vals.items():
        if len(vals) < 10:
            continue
        rows.append((INST_LABELS.get(inst, inst), statistics.mean(vals), len(vals)))
    rows.sort(key=lambda x: x[1])

    labels = [r[0] for r in rows]
    means  = [r[1] for r in rows]
    ns     = [r[2] for r in rows]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    y = np.arange(len(labels))
    bars = ax.barh(y, means, color=ART_COLOR, height=0.6, zorder=3)
    ax.axvline(doaj_mean, color=DOAJ_COLOR, linewidth=1.8, linestyle="--", zorder=4,
               label=f"DOAJ baseline ({doaj_mean:.4f}, N={len(doaj_vals):,})")

    # N labels
    for i, (m, n) in enumerate(zip(means, ns)):
        ax.text(m + 0.001, i, f"N={n:,}", va="center", ha="left", fontsize=7.5, color=GRAY)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Analytical Tendency (AT)", fontsize=10)
    ax.set_title("Analytical Tendency by Institution vs. DOAJ Baseline")
    ax.legend(fontsize=9, frameon=False)
    ax.set_xlim(0, doaj_mean * 2.2)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6, zorder=0)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ---------------------------------------------------------------------------
# Fig 2: AT by content format (url_category)
# ---------------------------------------------------------------------------
def fig2_at_format(at_path, ucat_path, out_path, min_n=50):
    print("Generating Fig 2: AT by content format...")
    at_map, doc_inst = load_at(at_path)

    with _opener(ucat_path) as f:
        umap = json.load(f)

    # Normalise URL keys: lowercase, strip trailing slash
    umap_norm = {k.rstrip("/").lower(): v for k, v in umap.items()}

    doaj_vals = [v for doc, v in at_map.items() if doc_inst[doc] == "doaj"]
    doaj_mean = statistics.mean(doaj_vals) if doaj_vals else 0

    cat_vals = defaultdict(list)
    for doc, at_val in at_map.items():
        if doc_inst[doc] == "doaj":
            continue
        key = doc.rstrip("/").lower()
        meta = umap_norm.get(key)
        if meta:
            cat_vals[meta["category"]].append(at_val)

    rows = [(cat, statistics.mean(vals), len(vals))
            for cat, vals in cat_vals.items() if len(vals) >= min_n]
    # Sort descending by AT, then split into two halves for side-by-side panels
    rows.sort(key=lambda x: -x[1])
    mid = math.ceil(len(rows) / 2)
    # Left panel: higher AT (top half), Right panel: lower AT (bottom half)
    # Each panel sorted ascending (lowest at bottom) for reading direction
    left  = list(reversed(rows[:mid]))   # ascending within top-half
    right = list(reversed(rows[mid:]))   # ascending within bottom-half

    x_max = doaj_mean * 2.4

    def _draw_panel(ax, panel_rows, show_legend):
        lbls   = [r[0] for r in panel_rows]
        vals   = [r[1] for r in panel_rows]
        counts = [r[2] for r in panel_rows]
        colors = [DOAJ_COLOR if v >= doaj_mean else ART_COLOR for v in vals]
        y = np.arange(len(lbls))
        ax.barh(y, vals, color=colors, height=1.0, zorder=3)   # height=1.0 → no gap
        ax.axvline(doaj_mean, color=DOAJ_COLOR, linewidth=1.5, linestyle="--", zorder=4,
                   label=f"DOAJ ({doaj_mean:.4f})")
        for i, (v, cnt) in enumerate(zip(vals, counts)):
            ax.text(v + 0.002, i, f"N={cnt:,}", va="center", ha="left",
                    fontsize=7, color=GRAY)
        ax.set_yticks(y)
        ax.set_yticklabels(lbls, fontsize=8.5)
        ax.set_xlim(0, x_max)
        ax.set_xlabel("AT", fontsize=9)
        ax.grid(axis="x", linestyle=":", linewidth=0.5, alpha=0.5, zorder=0)
        ax.tick_params(axis="y", length=0)
        if show_legend:
            ax.legend(fontsize=8, frameon=False, loc="lower right")

    n_rows = max(len(left), len(right))
    fig_h  = max(3.5, n_rows * 0.32 + 0.8)
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(11, fig_h),
                                      gridspec_kw={"wspace": 0.5})
    _draw_panel(ax_l, left,  show_legend=False)
    _draw_panel(ax_r, right, show_legend=True)
    fig.suptitle("Analytical Tendency by Content Format vs. DOAJ Baseline",
                 fontsize=11, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ---------------------------------------------------------------------------
# Fig 3: nMCE distribution — Art vs DOAJ (violin)
# ---------------------------------------------------------------------------
def fig3_nmce_distribution(nmce_path, out_path):
    print("Generating Fig 3: nMCE distribution...")
    records = load_nmce(nmce_path)

    art_vals, doaj_vals = [], []
    for adj_counter, total_nouns, inst, _ in records:
        v = compute_nmce_primary(adj_counter, total_nouns)
        if v is None:
            continue
        if inst == "doaj":
            doaj_vals.append(v)
        else:
            art_vals.append(v)

    d = cohen_d_simple(art_vals, doaj_vals)
    art_mean  = statistics.mean(art_vals)
    doaj_mean = statistics.mean(doaj_vals)

    fig, ax = plt.subplots(figsize=(5, 5))

    data   = [art_vals, doaj_vals]
    labels = [f"Art corpus\n(N={len(art_vals):,})", f"DOAJ\n(N={len(doaj_vals):,})"]
    colors = [ART_COLOR, DOAJ_COLOR]

    parts = ax.violinplot(data, positions=[1, 2], widths=0.6,
                          showmedians=False, showextrema=False)
    for pc, col in zip(parts["bodies"], colors):
        pc.set_facecolor(col)
        pc.set_alpha(0.75)
        pc.set_edgecolor("white")

    # Mean markers
    ax.scatter([1, 2], [art_mean, doaj_mean], color="white", s=40, zorder=5,
               edgecolors=[ART_COLOR, DOAJ_COLOR], linewidths=1.5)

    # Mean text
    ax.text(1, art_mean - 0.025, f"{art_mean:.4f}", ha="center", va="top",
            fontsize=8.5, color=ART_COLOR, fontweight="bold")
    ax.text(2, doaj_mean + 0.025, f"{doaj_mean:.4f}", ha="center", va="bottom",
            fontsize=8.5, color=DOAJ_COLOR, fontweight="bold")

    ax.set_xticks([1, 2])
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("nMCE (primary filter)", fontsize=10)
    ax.set_title("nMCE Distribution: Art Corpus vs. DOAJ")
    ax.set_xlim(0.3, 2.7)
    ax.set_ylim(-0.05, 1.15)

    ax.text(0.97, 0.97, f"Cohen's d = +{d:.2f}", transform=ax.transAxes,
            ha="right", va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#CCCCCC", alpha=0.9))

    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ---------------------------------------------------------------------------
# Fig 4: DMI zero-rate by institution (kw>0, liberal zero)
# ---------------------------------------------------------------------------
def fig4_dmi_zerorate(dmi_path, out_path):
    print("Generating Fig 4: DMI zero-rate by institution...")
    records = load_dmi(dmi_path)

    inst_kw_pos  = defaultdict(int)
    inst_zero    = defaultdict(int)
    doaj_kw_pos  = 0
    doaj_zero    = 0

    for url, d in records.items():
        kw   = d["total_keyword_matches"]
        zero = d["dmi_liberal"] == 0.0
        inst = d["institution"]
        if kw == 0:
            continue
        if inst == "doaj":
            doaj_kw_pos += 1
            if zero:
                doaj_zero += 1
        else:
            inst_kw_pos[inst] += 1
            if zero:
                inst_zero[inst] += 1

    doaj_rate = doaj_zero / doaj_kw_pos if doaj_kw_pos else 0

    EXCLUDE_INST = {"timothy_morton_corpus"}
    rows = []
    for inst, n in inst_kw_pos.items():
        if n < 5 or inst in EXCLUDE_INST:
            continue
        rate = inst_zero[inst] / n
        rows.append((INST_LABELS.get(inst, inst), rate, n))
    rows.sort(key=lambda x: x[1])

    labels = [r[0] for r in rows]
    rates  = [r[1] for r in rows]
    ns     = [r[2] for r in rows]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    y = np.arange(len(labels))
    ax.barh(y, rates, color=ART_COLOR, height=0.6, zorder=3)
    ax.axvline(doaj_rate, color=DOAJ_COLOR, linewidth=1.8, linestyle="--", zorder=4,
               label=f"DOAJ baseline ({doaj_rate:.3f}, N={doaj_kw_pos:,})")

    for i, (r, n) in enumerate(zip(rates, ns)):
        ax.text(r + 0.004, i, f"N={n:,}", va="center", ha="left", fontsize=7.5, color=GRAY)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("DMI Zero-rate (kw>0 subset, liberal)", fontsize=10)
    ax.set_title("DMI Zero-rate by Institution vs. DOAJ Baseline")
    ax.legend(fontsize=9, frameon=False)
    ax.set_xlim(0, 1.05)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.6, zorder=0)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ---------------------------------------------------------------------------
# Fig 5: Cross-layer Spearman ρ heatmap (dual: paper-exact + consistent)
# ---------------------------------------------------------------------------
def fig5_crosslayer_heatmap(npc_path, nmce_path, dmi_path, at_path, out_path):
    print("Generating Fig 5: Cross-layer Spearman ρ heatmap...")

    # --- Load raw data ---
    npc_recs  = load_npc(npc_path)
    nmce_recs = load_nmce(nmce_path)
    dmi_recs  = load_dmi(dmi_path)
    at_map, doc_inst = load_at(at_path)

    # nMCE maps: url → nmce
    nmce_iae_map     = {}
    nmce_primary_map = {}
    for adj_counter, total_nouns, inst, url in nmce_recs:
        if inst == "doaj":
            continue
        v_iae = compute_nmce_iae(adj_counter)
        if v_iae is not None:
            nmce_iae_map[url] = v_iae
        v_pri = compute_nmce_primary(adj_counter, total_nouns)
        if v_pri is not None:
            nmce_primary_map[url] = v_pri

    # AT maps: url → at (all pairs) and url → at (engaged, p0<0.999)
    at_all_map      = {}
    at_engaged_map  = {}
    at_doc_vals_all = defaultdict(list)
    at_doc_vals_eng = defaultdict(list)
    with _opener(at_path) as f:
        for line in f:
            d = json.loads(line)
            if d["institution"] == "doaj":
                continue
            if not d["top_alternatives"]:
                continue
            url = d["doc_id"].rstrip("/").lower()
            at_doc_vals_all[url].append(d["at_value"])
            p0 = next((t["prob"] for t in d["top_alternatives"] if t["token"] == "0"), 0.0)
            if p0 < 0.999:
                at_doc_vals_eng[url].append(d["at_value"])

    at_all_map     = {u: sum(v)/len(v) for u, v in at_doc_vals_all.items()}
    at_engaged_map = {u: sum(v)/len(v) for u, v in at_doc_vals_eng.items()}

    def _build_matrix(use_iae, use_w05_dmi, use_engaged_at):
        nmce_map = nmce_iae_map if use_iae else nmce_primary_map
        at_use   = at_engaged_map if use_engaged_at else at_all_map
        dmi_lib_key  = "dmi_csv_liberal"  if use_w05_dmi else "dmi_liberal"
        dmi_cons_key = "dmi_csv_conservative" if use_w05_dmi else "dmi_conservative"

        # Collect per-URL vectors (art only, exclude doaj)
        urls = set(npc_recs) & set(at_use)
        vecs = {"NPC-Pre": [], "NPC-Post": [], "nMCE": [],
                "DMI(lib)": [], "DMI(cons)": [], "AT": []}
        for url in urls:
            u_norm = url.rstrip("/").lower()
            if url not in npc_recs or npc_recs[url][3] == "doaj":
                continue
            if u_norm not in nmce_map:
                continue
            if url not in dmi_recs and u_norm not in dmi_recs:
                continue
            dmi_rec = dmi_recs.get(url) or dmi_recs.get(u_norm)
            vecs["NPC-Pre"].append(npc_recs[url][0])
            vecs["NPC-Post"].append(npc_recs[url][1])
            vecs["nMCE"].append(nmce_map[u_norm])
            vecs["DMI(lib)"].append(dmi_rec[dmi_lib_key])
            vecs["DMI(cons)"].append(dmi_rec[dmi_cons_key])
            vecs["AT"].append(at_use[url])

        n = len(vecs["NPC-Pre"])
        keys = list(vecs.keys())
        mat_r = np.zeros((len(keys), len(keys)))
        mat_p = np.ones((len(keys), len(keys)))
        for i, k1 in enumerate(keys):
            for j, k2 in enumerate(keys):
                if i == j:
                    mat_r[i, j] = 1.0
                    mat_p[i, j] = 0.0
                elif j > i:
                    r, p = spearman_r(vecs[k1], vecs[k2])
                    mat_r[i, j] = mat_r[j, i] = r
                    mat_p[i, j] = mat_p[j, i] = p
        return keys, mat_r, mat_p, n

    keys_a, mat_a, pmat_a, n_a = _build_matrix(use_iae=True,  use_w05_dmi=True,  use_engaged_at=True)
    keys_b, mat_b, pmat_b, n_b = _build_matrix(use_iae=False, use_w05_dmi=False, use_engaged_at=False)

    def _render_heatmap(ax, keys, mat, pmat, title, annot_size=8):
        mask = np.tril(np.ones_like(mat, dtype=bool), k=-1)
        annot = np.empty_like(mat, dtype=object)
        for i in range(len(keys)):
            for j in range(len(keys)):
                if i == j:
                    annot[i, j] = ""
                elif j > i:
                    stars = sig_stars(pmat[i, j])
                    annot[i, j] = f"{mat[i,j]:+.3f}\n{stars}"
                else:
                    annot[i, j] = ""
        sns.heatmap(
            mat, ax=ax,
            mask=mask,
            annot=annot, fmt="",
            annot_kws={"size": annot_size},
            cmap="RdBu_r", center=0, vmin=-0.6, vmax=0.6,
            linewidths=0.5, linecolor="#DDDDDD",
            cbar_kws={"shrink": 0.7},
            xticklabels=keys, yticklabels=keys,
            square=True,
        )
        for i in range(len(keys)):
            for j in range(i):
                ax.add_patch(plt.Rectangle((j, i), 1, 1,
                             fill=True, color="#F5F5F5", zorder=3))
        ax.set_title(title, fontsize=10, pad=8)
        ax.tick_params(axis="x", rotation=30, labelsize=9)
        ax.tick_params(axis="y", rotation=0,  labelsize=9)

    # Horizontal version (figures/README.md)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    _render_heatmap(axes[0], keys_a, mat_a, pmat_a,
                    f"(A) Paper-exact\n(IAE nMCE, DMI w=0.5, engaged AT, N≈{n_a//1000}k)")
    _render_heatmap(axes[1], keys_b, mat_b, pmat_b,
                    f"(B) Consistent\n(primary nMCE, DMI w=1.0, all AT, N≈{n_b//1000}k)")
    fig.suptitle("Cross-layer Spearman ρ (art corpus, Llama-3.3-70B-FP8)", fontsize=11, y=1.01)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)

    # Vertical version (main README.md)
    out_vertical = Path(str(out_path).replace(".png", "_vertical.png"))
    fig, axes = plt.subplots(2, 1, figsize=(7, 10))
    _render_heatmap(axes[0], keys_a, mat_a, pmat_a,
                    f"(A) Paper-exact  —  IAE nMCE, DMI w=0.5, engaged AT  (N≈{n_a//1000}k)",
                    annot_size=9)
    _render_heatmap(axes[1], keys_b, mat_b, pmat_b,
                    f"(B) Consistent  —  primary nMCE, DMI w=1.0, all AT  (N≈{n_b//1000}k)",
                    annot_size=9)
    fig.suptitle("Cross-layer Spearman ρ (art corpus, Llama-3.3-70B-FP8)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_vertical)
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Generate all figures")
    p.add_argument("--data", default="data")
    p.add_argument("--out",  default="figures")
    return p.parse_args()


def main():
    args = parse_args()
    data = Path(args.data)
    out  = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    fig1_at_institution(
        data / "at_scores_llama.jsonl.gz",
        out  / "fig1_at_institution.png",
    )
    fig2_at_format(
        data / "at_scores_llama.jsonl.gz",
        data / "url_category_map.json.gz",
        out  / "fig2_at_format.png",
    )
    fig3_nmce_distribution(
        data / "nmce_scores.jsonl.gz",
        out  / "fig3_nmce_distribution.png",
    )
    fig4_dmi_zerorate(
        data / "dmi_scores.jsonl.gz",
        out  / "fig4_dmi_zerorate.png",
    )
    fig5_crosslayer_heatmap(
        data / "npc_scores.jsonl.gz",
        data / "nmce_scores.jsonl.gz",
        data / "dmi_scores.jsonl.gz",
        data / "at_scores_llama.jsonl.gz",
        out  / "fig5_crosslayer_heatmap.png",
    )
    print(f"\nAll figures saved to {out}/")


if __name__ == "__main__":
    main()
