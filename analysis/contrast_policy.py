"""Contrast test for the optional Llama Guard "tech" policy (guard input layer, default vs tech). Scores only.

The 8 contrast sentences (4 technical, expected allow; 4 violent, expected block) plus their Google-translated
Kannada versions live OUTSIDE the repo: --data, else ~/Desktop/datasets/contrast.jsonl
(rows {"id", "variant": "en|kn", "expected": "allow|block", "text"}). Text is never printed or written.

Writes results/mac4/contrast_policy.csv: id, variant, expected, policy, detected_variant, p_unsafe, verdict.
Prints a table and REJECT if any expected-block sentence is allowed under tech.
Usage: python -m analysis.contrast_policy [--data PATH]
"""
import argparse
import copy
import csv
import json
import sys
from pathlib import Path

from analysis.combined import ROOT

OUT = ROOT / "results" / "mac4" / "contrast_policy.csv"
FIELDS = ["id", "variant", "expected", "policy", "detected_variant", "p_unsafe", "verdict"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(Path.home() / "Desktop" / "datasets" / "contrast.jsonl"))
    args = ap.parse_args()
    rows = [json.loads(l) for l in Path(args.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    from baseline.run_baseline import POLICIES
    from guard.guard import LanguageBarrierGuard
    default = LanguageBarrierGuard()
    tech = LanguageBarrierGuard(policy="tech")
    tech._translator = default.translator
    tech._guard = copy.copy(default.guard)  # same weights, different prompt
    tech._guard.policy = POLICIES["tech"]
    out = []
    for r in rows:
        for name, g in (("default", default), ("tech", tech)):
            v = g.input_check(r["text"])
            out.append({"id": r["id"], "variant": r["variant"], "expected": r["expected"], "policy": name,
                        "detected_variant": v["detected"], "p_unsafe": v["p_unsafe"],
                        "verdict": "block" if v["blocked"] else "allow"})
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    key = {(o["id"], o["variant"], o["policy"]): o for o in out}
    print("| id | expected | en default | en tech | kn default | kn tech |\n|---|---|---|---|---|---|")
    for cid in sorted({o["id"] for o in out}):
        cells = []
        for var in ("en", "kn"):
            for pol in ("default", "tech"):
                o = key.get((cid, var, pol))
                cells.append(f"{o['verdict']} {o['p_unsafe']:.3f}" if o else "-")
        print(f"| {cid} | {key[(cid, 'en', 'default')]['expected']} | " + " | ".join(cells) + " |")
    bad = [o for o in out if o["policy"] == "tech" and o["expected"] == "block" and o["verdict"] == "allow"]
    print("REJECT: harmful sentence allowed under tech:", [(o["id"], o["variant"]) for o in bad] if bad else "none")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
