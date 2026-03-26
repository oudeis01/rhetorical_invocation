"""
run_npc_ars_only.py

Re-runs NPC extraction for ars_electronica only, with the doc_id dedup bug fixed.

Bug in original run_npc_post.py:
    doc_id = data.get('id', '') or data.get('url', '') or file_path.name
    if doc_id in processed_ids: continue
    ...
    processed_ids.add(r['doc_id'])   # ← adds URL
All chunk files sharing the same URL are deduplicated to 1. ars_electronica
has 3,439 chunk files but only ~1,520 unique URLs, so ~1,919 chunks were lost.

Fix: use file_path.stem as the dedup key. URL remains the doc_id in output
so build_npc_scores.py can still join by URL.

Output:
    results/20260324_ars_npc_fixed/npc_results.jsonl   (3,439 records)
    results/20260324_ars_npc_fixed/checkpoint_processed_ids.json

After this run, update build_npc_scores.py to load ars NPC from this file
instead of (or in addition to) the original npc_results.jsonl.
"""

import json
import os
import re
import time
import argparse
from pathlib import Path
from tqdm import tqdm

# --- GPU init before spaCy ---
import torch
try:
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    from thinc.api import set_gpu_allocator, require_gpu
    set_gpu_allocator("pytorch")
    require_gpu(0)
    print(f"GPU enabled: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"WARNING: GPU init failed: {e}. Falling back to CPU.")

import spacy
from lingua import Language, LanguageDetectorBuilder

languages = [
    Language.ENGLISH, Language.INDONESIAN, Language.GERMAN, Language.FRENCH,
    Language.SPANISH, Language.DUTCH, Language.ITALIAN, Language.PORTUGUESE,
    Language.RUSSIAN, Language.POLISH, Language.TURKISH, Language.SWEDISH,
    Language.CROATIAN, Language.ESTONIAN, Language.MACEDONIAN,
]
lingua_detector = LanguageDetectorBuilder.from_languages(*languages).build()


# ─── helpers (copied verbatim from run_npc_post.py) ───────────────────────────

def is_valid_english_sentence(sent_text):
    if len(sent_text) < 20 or len(sent_text) > 1000:
        return False
    alpha_chars = sum(c.isalpha() for c in sent_text)
    if len(sent_text) > 0 and (alpha_chars / len(sent_text)) < 0.6:
        return False
    single_char_words = len(re.findall(r"\b[a-zA-Z]\b", sent_text))
    if single_char_words > 5:
        return False
    try:
        detected_lang = lingua_detector.detect_language_of(sent_text)
        if not detected_lang or detected_lang.iso_code_639_1.name.lower() != "en":
            return False
    except Exception:
        return False
    return True


def process_batch(nlp, batch_docs, batch_metas):
    results = []
    for i, doc in enumerate(nlp.pipe(batch_docs, batch_size=8)):
        meta = batch_metas[i]
        stats = {
            "total_nouns": 0,
            "total_amod": 0,
            "total_advmod": 0,
            "total_prep": 0,
            "total_relcl": 0,
            "total_appos": 0,
            "total_acl": 0,
        }
        best_post_sentence = ""
        max_post_count = 0
        best_pre_sentence = ""
        max_pre_count = 0

        for token in doc:
            if token.pos_ not in ("NOUN", "PROPN"):
                continue
            stats["total_nouns"] += 1
            pre_count = 0
            post_count = 0
            pre_mods = []
            post_mods = []
            for child in token.children:
                dep = child.dep_
                if dep == "amod":
                    stats["total_amod"] += 1
                    pre_count += 1
                    pre_mods.append(child)
                    for subchild in child.children:
                        if subchild.dep_ == "advmod":
                            stats["total_advmod"] += 1
                            pre_count += 1
                            pre_mods.append(subchild)
                elif dep == "prep":
                    stats["total_prep"] += 1
                    post_count += 1
                    post_mods.append(child)
                elif dep == "relcl":
                    stats["total_relcl"] += 1
                    post_count += 1
                    post_mods.append(child)
                elif dep == "appos":
                    stats["total_appos"] += 1
                    post_count += 1
                    post_mods.append(child)
                elif dep == "acl":
                    stats["total_acl"] += 1
                    post_count += 1
                    post_mods.append(child)

            if post_count > max_post_count and post_count >= 2:
                try:
                    sent = token.sent
                    if is_valid_english_sentence(sent.text):
                        max_post_count = post_count
                        marked = sent.text
                        marked = marked.replace(token.text, f"[HEAD:**{token.text}**]", 1)
                        for m in post_mods:
                            marked = marked.replace(m.text, f"[POST:{m.dep_}:{m.text}]", 1)
                        best_post_sentence = marked.strip()
                except Exception:
                    pass

            if pre_count > max_pre_count and pre_count >= 2:
                try:
                    sent = token.sent
                    if is_valid_english_sentence(sent.text):
                        max_pre_count = pre_count
                        marked = sent.text
                        marked = marked.replace(token.text, f"[HEAD:**{token.text}**]", 1)
                        for m in pre_mods:
                            marked = marked.replace(m.text, f"[PRE:{m.dep_}:{m.text}]", 1)
                        best_pre_sentence = marked.strip()
                except Exception:
                    pass

        results.append({
            "doc_id": meta["url"],          # URL — join key for build_npc_scores
            "chunk_key": meta["chunk_key"], # file stem — for reference/debugging
            "url": meta["url"],
            "institution": "ars_electronica",
            "depth_category": meta["depth_cat"],
            "npc_counts": stats,
            "evidence": {
                "post_max_mods": max_post_count,
                "post_best_sentence": best_post_sentence if max_post_count >= 2 else None,
                "pre_max_mods": max_pre_count,
                "pre_best_sentence": best_pre_sentence if max_pre_count >= 2 else None,
            },
        })
    return results


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--test-run", type=int, default=0, help="Process only N files (0=all)")
    args = parser.parse_args()

    ARS_DIR = Path(
        "/home/choiharam/works/projects/namedrop_data"
        "/analysis_pipeline/corpus_preparation/filtered_corpus/ars_electronica/pages"
    )
    OUT_DIR = Path(
        "/home/choiharam/works/projects/namedrop_data"
        "/analysis_pipeline/syntactic_analysis/npc_noun_phrase_complexity"
        "/post/results/20260324_ars_npc_fixed"
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    OUT_FILE = OUT_DIR / "npc_results.jsonl"
    CHECKPOINT = OUT_DIR / "checkpoint_processed_ids.json"

    # Resume from checkpoint — keys are file STEMS (not URLs)
    processed_ids = set()
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            processed_ids = set(json.load(f))
        print(f"Resuming: {len(processed_ids)} chunks already done.")

    files = sorted(ARS_DIR.glob("*.json"))
    print(f"ars_electronica corpus files: {len(files)}")

    if args.test_run > 0:
        files = files[: args.test_run]
        print(f"TEST MODE: {args.test_run} files only.")

    # Filter out A3 depth category upfront (paper only uses A1 + A2)
    KEEP_DEPTH = {"A1", "A2", ""}

    print("Loading spaCy en_core_web_trf ...")
    nlp = spacy.load("en_core_web_trf", disable=["ner"])

    batch_docs = []
    batch_metas = []
    batch_chunk_keys = []   # parallel list for checkpoint tracking
    processed_count = 0
    skipped_depth = 0
    start_time = time.time()

    with open(OUT_FILE, "a" if processed_ids else "w", encoding="utf-8") as f_out:
        for file_path in tqdm(files, desc="NPC ars_electronica"):
            chunk_key = file_path.stem  # ← THE FIX: unique per chunk file

            if chunk_key in processed_ids:
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                depth_cat = (
                    data.get("page_level_depth_classification", {})
                    .get("depth_category", "")
                )
                if depth_cat not in KEEP_DEPTH:
                    skipped_depth += 1
                    processed_ids.add(chunk_key)  # mark so we don't revisit
                    continue

                text = ""
                if "text" in data and data["text"]:
                    text = data["text"]
                elif "blocks" in data:
                    text = " ".join(b.get("content", "") for b in data["blocks"])

                if not text.strip():
                    processed_ids.add(chunk_key)
                    continue

                url = data.get("url", "").rstrip("/").lower()

                batch_docs.append(text)
                batch_metas.append({
                    "chunk_key": chunk_key,
                    "url": url,
                    "depth_cat": depth_cat,
                })
                batch_chunk_keys.append(chunk_key)

                if len(batch_docs) >= args.batch_size:
                    results = process_batch(nlp, batch_docs, batch_metas)
                    for r in results:
                        f_out.write(json.dumps(r) + "\n")
                    for ck in batch_chunk_keys:
                        processed_ids.add(ck)
                    f_out.flush()

                    processed_count += len(batch_docs)
                    batch_docs = []
                    batch_metas = []
                    batch_chunk_keys = []

                    if processed_count % 500 < args.batch_size:
                        with open(CHECKPOINT, "w") as f_cp:
                            json.dump(list(processed_ids), f_cp)
                        elapsed = time.time() - start_time
                        rate = processed_count / (elapsed / 3600) if elapsed > 0 else 0
                        print(f"  {processed_count} chunks done  ({rate:.0f}/hr)")

            except Exception as e:
                tqdm.write(f"Error on {file_path}: {e}")

        # Flush remaining batch
        if batch_docs:
            results = process_batch(nlp, batch_docs, batch_metas)
            for r in results:
                f_out.write(json.dumps(r) + "\n")
            for ck in batch_chunk_keys:
                processed_ids.add(ck)
            processed_count += len(batch_docs)

    # Final checkpoint
    with open(CHECKPOINT, "w") as f_cp:
        json.dump(list(processed_ids), f_cp)

    total_time = time.time() - start_time
    print(
        f"\nDone: {processed_count} chunks processed in {total_time / 60:.1f} min"
        f"  ({skipped_depth} skipped as A3/unknown depth)"
    )

    # Quick sanity check
    count = 0
    unique_urls = set()
    with open(OUT_FILE) as f:
        for line in f:
            r = json.loads(line)
            count += 1
            unique_urls.add(r["url"])
    print(f"Output: {count} records, {len(unique_urls)} unique URLs")
    print(f"Saved to: {OUT_FILE}")
    print(
        f"\nNext step — update build_npc_scores.py NPC_ARS_JSONL path to:\n"
        f"  {OUT_FILE}"
    )


if __name__ == "__main__":
    main()
