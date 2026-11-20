"""python -m guard.smoke_test [--prompts PATH]: one verdict and score per line (no prompt text printed).

The smoke prompts are kept OUTSIDE the repo (they include harmful requests). Path: --prompts, else the
GUARD_SMOKETEST env var, else ~/Desktop/guard_smoketest.jsonl. JSONL rows: {"harmful": bool, "text": str}.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from guard.guard import LanguageBarrierGuard


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", help="JSONL smoke prompts (outside the repo); default $GUARD_SMOKETEST")
    args = ap.parse_args()
    path = Path(args.prompts or os.environ.get("GUARD_SMOKETEST") or Path.home() / "Desktop" / "guard_smoketest.jsonl")
    try:
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: cannot read smoke prompts {path}: {e} (set --prompts or GUARD_SMOKETEST)")
    guard = LanguageBarrierGuard()
    for r in rows:
        result = guard.check(r["text"])
        print(f"{'harmful ' if r.get('harmful') else 'harmless'} {result['verdict']} {result['p_unsafe']:.4f}", flush=True)


if __name__ == "__main__":
    main()
