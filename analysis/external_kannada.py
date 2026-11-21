"""External check: the guard's input layer on HUMAN-WRITTEN Kannada prompts (SurakshaEval). Scores only.

Dataset: SurakshaEval (Banerjee et al., AAAI/ACM AIES 2026), Hugging Face SurakshaAI/SurakshaEval (gated,
CC BY-NC-SA 4.0). The file stays OUTSIDE the repo: --data, else $SURAKSHA_KN, else
~/Desktop/datasets/surakshaeval/data/kannada/test.jsonl. Prompt text is never written or printed.

Runs ONLY LanguageBarrierGuard().input_check (threshold 0.5, default settings; no chatbot model) on
  view = kn_human : question_indic (human-written Kannada)
  view = en_paired: question_en (the dataset's own English version of the same question)
SurakshaEval has no harmful/safe label per item: every item is a Kannada-specific risk probe whose
*response* the benchmark grades. So label = "risk" for every row, and "flagged %" is a sensitivity
measure, not accuracy; there are no safe items, so no wrongly-blocked rate.

Writes results/mac4/external_kannada_guard.csv:
  dataset, item_id, harm_category, label, view, detected_variant, p_unsafe, blocked, latency_ms
and prints flagged % with Wilson 95% CIs overall and per harm category, plus detected-variant counts.
Usage: python -m analysis.external_kannada [--data PATH] [--summary-only]
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analysis.combined import ROOT, wilson

OUT = ROOT / "results" / "mac4" / "external_kannada_guard.csv"
FIELDS = ["dataset", "item_id", "harm_category", "label", "view", "detected_variant",
          "p_unsafe", "blocked", "latency_ms"]
DATASET = "SurakshaEval-kn"


def data_path(arg=None):
    return Path(arg or os.environ.get("SURAKSHA_KN")
                or Path.home() / "Desktop" / "datasets" / "surakshaeval" / "data" / "kannada" / "test.jsonl")


def run(path):
    try:
        items = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: cannot read {path}: {e} (set --data or SURAKSHA_KN)")
    from guard.guard import LanguageBarrierGuard
    g = LanguageBarrierGuard()  # threshold 0.5, kanglish="itrans" (defaults)
    if g.threshold != 0.5 or g.kanglish != "itrans":
        sys.exit("ERROR: guard is not at default settings")
    g.input_check("hello")  # load models before timing
    out = []
    for i, it in enumerate(items, 1):
        for view, field in (("kn_human", "question_indic"), ("en_paired", "question_en")):
            text = it.get(field)
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                v = g.input_check(text)
            except Exception as e:  # report and continue; never print the text
                print(f"error {it.get('id')} {view}: {type(e).__name__}", file=sys.stderr)
                continue
            out.append({"dataset": DATASET, "item_id": it.get("id"), "harm_category": it.get("type_of_harm", ""),
                        "label": "risk", "view": view, "detected_variant": v["detected"],
                        "p_unsafe": v["p_unsafe"], "blocked": int(v["blocked"]), "latency_ms": v["latency_ms"]})
        if i % 25 == 0 or i == len(items):
            print(f"{i}/{len(items)} items", flush=True)
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    tmp.replace(OUT)
    print(f"{len(out)} rows -> {OUT.relative_to(ROOT)}")


def rate(rows):
    n, k = len(rows), sum(int(r["blocked"]) for r in rows)
    lo, hi = wilson(k, n)
    return n, k, (round(100 * k / n, 1) if n else None), lo, hi


def summarize():
    with OUT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by = defaultdict(list)
    for r in rows:
        by[(r["view"], "ALL")].append(r)
        by[(r["view"], r["harm_category"])].append(r)
    cats = ["ALL"] + sorted({r["harm_category"] for r in rows})
    print("\n| harm category | n | flagged, human Kannada | flagged, paired English |\n|---|---|---|---|")
    for c in cats:
        cells = []
        for view in ("kn_human", "en_paired"):
            n, k, p, lo, hi = rate(by[(view, c)])
            cells.append(f"{p} [{lo}–{hi}] ({k}/{n})")
        print(f"| {c} | {len(by[('kn_human', c)])} | {cells[0]} | {cells[1]} |")
    for view in ("kn_human", "en_paired"):
        vs = [r for r in rows if r["view"] == view]
        print(f"{view}: detected {dict(Counter(r['detected_variant'] for r in vs))}; "
              f"median latency {sorted(int(r['latency_ms']) for r in vs)[len(vs) // 2]} ms")
    kn = {r["item_id"]: int(r["blocked"]) for r in rows if r["view"] == "kn_human"}
    en = {r["item_id"]: int(r["blocked"]) for r in rows if r["view"] == "en_paired"}
    both = set(kn) & set(en)
    print("paired (n=%d): both flagged %d, en only %d, kn only %d, neither %d" % (
        len(both), sum(kn[i] and en[i] for i in both), sum(en[i] and not kn[i] for i in both),
        sum(kn[i] and not en[i] for i in both), sum(not kn[i] and not en[i] for i in both)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()
    if not args.summary_only:
        run(data_path(args.data))
    summarize()


if __name__ == "__main__":
    main()
