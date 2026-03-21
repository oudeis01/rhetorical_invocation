"""
Corpus-level collocation concentration analysis for Table 5.0.

Computes top-1 share (%) for selected adjectives across Art and DOAJ corpora.
This supplements the document-level nMCE metric with corpus-level context.

Input: corpus_features.jsonl.gz (not used), structural_results.jsonl (mce_pairs)
Output: Table showing per-adjective top-1 noun partner and concentration % for each corpus.

Usage:
    python collocation_concentration.py --data structural_results.jsonl

Note: This script requires the raw structural_results.jsonl (130MB) which contains
mce_pairs per document. It is NOT included in the GitHub repo data files.
For reproduction from repo data, the collocation_patterns_*.md files contain
pre-computed results.
"""

import json
import argparse
from collections import Counter


# Adjectives selected for Table 5.0: illustrate diverse corpus-level patterns
TABLE_ADJECTIVES = ['natural', 'critical', 'political', 'social', 'contemporary']

# Extended set for full analysis
ALL_TARGET_ADJECTIVES = [
    'social', 'political', 'cultural', 'critical', 'economic', 'natural',
    'contemporary', 'environmental', 'historical', 'feminist', 'international',
    'artistic', 'digital', 'visual', 'physical', 'global'
]

# Institutions excluded from 13-institution art corpus
EXCLUDE_INSTITUTIONS = {'aeon', 'theconversation', 'pages', 'doaj'}


def load_collocation_data(jsonl_path, target_adjectives):
    """Extract adjective-noun pair counts from structural_results.jsonl."""
    target_set = set(target_adjectives)
    art_pairs = {adj: Counter() for adj in target_adjectives}
    doaj_pairs = {adj: Counter() for adj in target_adjectives}

    n_art = n_doaj = 0
    with open(jsonl_path) as f:
        for line in f:
            doc = json.loads(line)
            pairs = doc.get('mce_pairs', [])
            if not pairs:
                continue
            inst = doc.get('institution', '')

            for adj, noun in pairs:
                if adj not in target_set:
                    continue
                if inst == 'doaj':
                    doaj_pairs[adj][noun] += 1
                elif inst not in EXCLUDE_INSTITUTIONS:
                    art_pairs[adj][noun] += 1

            if inst == 'doaj':
                n_doaj += 1
            elif inst not in EXCLUDE_INSTITUTIONS:
                n_art += 1

    return art_pairs, doaj_pairs, n_art, n_doaj


def compute_top1_share(counter):
    """Compute top-1 noun and its share of total pairings."""
    total = sum(counter.values())
    if total == 0:
        return '—', 0, 0, 0.0
    top_noun, top_count = counter.most_common(1)[0]
    share = top_count / total * 100
    return top_noun, top_count, total, share


def print_table(art_pairs, doaj_pairs, adjectives):
    """Print markdown table of corpus-level collocation concentration."""
    print('| Adjective | DOAJ top-1 collocation | Share | Art top-1 collocation | Share |')
    print('|:--|:--|:--|:--|:--|')

    for adj in adjectives:
        d_noun, d_cnt, d_total, d_share = compute_top1_share(doaj_pairs[adj])
        a_noun, a_cnt, a_total, a_share = compute_top1_share(art_pairs[adj])

        d_col = f'*{adj} {d_noun}*' if d_noun != '—' else '—'
        a_col = f'*{adj} {a_noun}*' if a_noun != '—' else '—'

        print(f'| {adj} | {d_col} | {d_share:.1f}% | {a_col} | {a_share:.1f}% |')


def print_full_report(art_pairs, doaj_pairs, adjectives, n_art, n_doaj):
    """Print detailed collocation report."""
    print(f'Corpus-level collocation concentration analysis')
    print(f'Art corpus: {n_art:,} docs (13 institutions)')
    print(f'DOAJ corpus: {n_doaj:,} docs')
    print()

    print('## Table 5.0 (paper insertion)')
    print()
    print_table(art_pairs, doaj_pairs, TABLE_ADJECTIVES)
    print()

    print('## Full analysis (all target adjectives)')
    print()
    print_table(art_pairs, doaj_pairs, adjectives)
    print()

    print('## Top-3 collocations per adjective')
    print()
    for adj in adjectives:
        d_total = sum(doaj_pairs[adj].values())
        a_total = sum(art_pairs[adj].values())

        d_top3 = doaj_pairs[adj].most_common(3)
        a_top3 = art_pairs[adj].most_common(3)

        d_str = ', '.join(
            f'{adj} {n} ({c}/{d_total}={c/d_total*100:.1f}%)'
            for n, c in d_top3
        ) if d_top3 else '—'
        a_str = ', '.join(
            f'{adj} {n} ({c}/{a_total}={c/a_total*100:.1f}%)'
            for n, c in a_top3
        ) if a_top3 else '—'

        print(f'**{adj}**')
        print(f'  DOAJ ({d_total:,}): {d_str}')
        print(f'  Art  ({a_total:,}): {a_str}')
        print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Compute corpus-level collocation concentration for Table 5.0'
    )
    parser.add_argument('--data', required=True, help='Path to structural_results.jsonl')
    parser.add_argument('--table-only', action='store_true', help='Print only Table 5.0')
    args = parser.parse_args()

    art_pairs, doaj_pairs, n_art, n_doaj = load_collocation_data(
        args.data, ALL_TARGET_ADJECTIVES
    )

    if args.table_only:
        print_table(art_pairs, doaj_pairs, TABLE_ADJECTIVES)
    else:
        print_full_report(art_pairs, doaj_pairs, ALL_TARGET_ADJECTIVES, n_art, n_doaj)
