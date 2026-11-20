"""python -m guard.cli "text" [--reply "model reply"]  ->  JSON verdict (never echoes the text).

Exit code: 0 allow, 1 block, 2 error.
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="user prompt (any of en / Kannada / Kanglish / code-mixed)")
    ap.add_argument("--reply", help="optional chatbot reply: also runs the output layer")
    ap.add_argument("--device", choices=("mps", "cpu"))
    args = ap.parse_args()
    try:
        from guard.guard import LanguageBarrierGuard
        verdict = LanguageBarrierGuard(device=args.device).check(args.text, reply=args.reply)
    except Exception as e:  # model load / runtime failures: report, never crash with text in the trace
        print(json.dumps({"verdict": "error", "error": f"{type(e).__name__}: {str(e)[:200]}"}))
        sys.exit(2)
    print(json.dumps(verdict, ensure_ascii=False))
    sys.exit(1 if verdict["verdict"] == "block" else 0)


if __name__ == "__main__":
    main()
