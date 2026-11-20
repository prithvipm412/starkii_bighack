"""python -m guard.eval [--testset PATH] [--threshold 0.5]: default vs optional Kanglish mode on a test set.

Compares LanguageBarrierGuard(kanglish="itrans") (default, = study baseline) with kanglish="romanized"
(mac3's guard/romanized.py, off by default) on the input layer, per variant: accuracy, harmful recall,
harmless false-block rate. Prints numbers only.

The test set holds prompt text, so it is kept OUTSIDE the repo. Path: --testset, else the
GUARD_TESTSET env var, else ~/Desktop/guard_testset.jsonl. JSONL rows: {"id", "variant", "harmful", "text"}.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from statistics import median

from guard.guard import THRESHOLD, LanguageBarrierGuard

VARIANTS = ("en", "kn", "kn_latn", "kn_mix")


def testset_path(arg=None):
    return Path(arg or os.environ.get("GUARD_TESTSET") or Path.home() / "Desktop" / "guard_testset.jsonl")


def metrics(labels, blocks):
    pos = sum(labels)
    neg = len(labels) - pos
    acc = 100 * sum(l == b for l, b in zip(labels, blocks)) / len(labels)
    rec = 100 * sum(l and b for l, b in zip(labels, blocks)) / pos if pos else float("nan")
    fb = 100 * sum((not l) and b for l, b in zip(labels, blocks)) / neg if neg else float("nan")
    return acc, rec, fb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--testset", help="JSONL test set (outside the repo); default $GUARD_TESTSET")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    args = ap.parse_args()
    path = testset_path(args.testset)
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: cannot read test set {path}: {e} (set --testset or GUARD_TESTSET)")

    default = LanguageBarrierGuard(threshold=args.threshold)
    optional = LanguageBarrierGuard(threshold=args.threshold, kanglish="romanized")
    optional._guard, optional._translator = default.guard, default.translator  # share the two models
    res = {}
    for name, g in (("default", default), ("romanized", optional)):
        res[name] = [g.input_check(r["text"]) for r in rows]

    print(f"threshold {args.threshold}; n = {len(rows)}")
    print("| Variant | N | default acc | default recall | default false-blocks | romanized acc | romanized recall | romanized false-blocks |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for v in (*VARIANTS, "ALL"):
        idx = [i for i, r in enumerate(rows) if v == "ALL" or r["variant"] == v]
        labels = [bool(rows[i]["harmful"]) for i in idx]
        rates = metrics(labels, [res["default"][i]["blocked"] for i in idx]) + \
            metrics(labels, [res["romanized"][i]["blocked"] for i in idx])
        print(f"| {v} | {len(idx)} | " + " | ".join(f"{x:.1f}%" for x in rates) + " |")
    for name in res:
        t = [x["latency_ms"] for x in res[name]]
        print(f"{name}: warm latency median {median(t):.0f} ms, max {max(t)} ms")


if __name__ == "__main__":
    main()
