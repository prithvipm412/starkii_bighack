"""Build the 4 prompt variants with Google Translate (mac4). Translation method for the whole study.

Same output as data_tools.build: for each English row, 4 rows (en, kn, kn_latn, kn_mix) sharing the
prompt_id, with the CLAUDE.md fields. Reuses mac2's code (imported, not edited):
  kn      = Google Translate en -> kn
  kn_latn = data_tools.transliterate (Kannada script -> ITRANS)
  kn_mix  = data_tools.codemix.TERM_PATTERN terms masked, Google-translated, terms restored

Translations are cached in data_tools/output/raw/gt_cache.json (gitignored), so reruns and
later sets resume. Only prompt ids with all 4 variants are written.

Usage:
  python -m analysis.build_google --in data_tools/output/raw/en_pilot.jsonl --out data_tools/output/pilot.jsonl \
      [--per-split 20]   # balanced mini set: N harmful + N harmless, spread across categories
"""
import argparse
import json
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from data_tools.codemix import TERM_PATTERN
from data_tools.transliterate import transliterate_texts

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data_tools" / "output" / "raw" / "gt_cache.json"
URL = "https://translate.googleapis.com/translate_a/single"
FIELDS = ["prompt_id", "split", "category", "source", "variant", "text"]
_lock = threading.Lock()


def load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict) -> None:
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE)


def google(text: str, retries: int = 6) -> str:
    for attempt in range(retries):
        try:
            r = requests.get(URL, params={"client": "gtx", "sl": "en", "tl": "kn", "dt": "t", "q": text},
                             timeout=20)
            if r.status_code == 429:
                raise RuntimeError("rate limited")
            r.raise_for_status()
            out = "".join(seg[0] for seg in r.json()[0] if seg and seg[0])
            if out.strip():
                return out
            raise RuntimeError("empty translation")
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"google translate failed: {type(e).__name__}: {e}") from e
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def mask(text: str):
    terms = []

    def repl(m):
        terms.append(m.group(0))
        return f"ZXQTERM{len(terms) - 1}QXZ"
    return TERM_PATTERN.sub(repl, text), terms


def unmask(text: str, terms: list) -> str:
    for i, term in enumerate(terms):
        text = re.sub(rf"ZXQ\s*TERM\s*{i}\s*QXZ", lambda _: term, text, flags=re.I)
    return text


def variants_for(text: str, cache: dict) -> dict:
    masked, terms = mask(text)
    out = {}
    for key, src in (("kn", text), ("mix", masked)):
        ck = f"{key}\t{src}"
        with _lock:
            hit = cache.get(ck)
        if hit is None:
            hit = google(src)
            with _lock:
                cache[ck] = hit
        out[key] = hit
    kn_mix = unmask(out["mix"], terms) if terms else out["kn"]
    return {"en": text, "kn": out["kn"], "kn_latn": transliterate_texts([out["kn"]], "Kannada")[0],
            "kn_mix": kn_mix}


def balanced_subset(rows: list, per_split: int) -> list:
    picked = []
    for split in ("harmful", "harmless"):
        by_cat = defaultdict(list)
        for r in rows:
            if r["split"] == split:
                by_cat[r["category"]].append(r)
        cats = sorted(by_cat)
        n = 0
        while n < per_split and any(by_cat.values()):
            for c in cats:
                if by_cat[c] and n < per_split:
                    picked.append(by_cat[c].pop(0)); n += 1
    return picked


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-split", type=int, help="balanced subset: N harmful + N harmless")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    try:
        rows = [json.loads(l) for l in Path(args.inp).read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: cannot read {args.inp}: {e}")
    if args.per_split:
        rows = balanced_subset(rows, args.per_split)
    cache = load_cache()
    results, errors = {}, 0
    t0 = time.time()

    def work(r):
        return r["prompt_id"], variants_for(r["text"], cache)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(work, r) for r in rows]
        for i, fut in enumerate(futures, 1):
            try:
                pid, v = fut.result()
                results[pid] = v
            except Exception as e:
                errors += 1
                print(f"error {rows[i - 1]['prompt_id']}: {str(e)[:120]}", file=sys.stderr)
            if i % 20 == 0 or i == len(rows):
                with _lock:
                    save_cache(cache)
                print(f"{i}/{len(rows)} prompts, {errors} errors, {time.time() - t0:.0f}s", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for r in rows:  # only prompts with all 4 variants
            v = results.get(r["prompt_id"])
            if not v:
                continue
            for variant in ("en", "kn", "kn_latn", "kn_mix"):
                row = {k: r[k] for k in FIELDS if k not in ("variant", "text")}
                f.write(json.dumps({**row, "variant": variant, "text": v[variant]}, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n * 4} rows ({n} prompts x 4 variants, {errors} failed) to {out}")


if __name__ == "__main__":
    main()
