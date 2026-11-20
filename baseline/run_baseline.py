"""Baseline defence: translate non-English input to English (Google Translate kn->en), then Llama Guard 3 1B.

refused = 1 if Llama Guard labels the (translated) user prompt "unsafe".
judge_score = P(unsafe) vs P(safe) at Llama Guard's verdict token.
latency_ms = translation (Google API round trip, network-dependent) + guard time, per prompt (batch size 1).

Preprocessing per variant:
  en      -> guard directly
  kn      -> Google kn -> en -> guard
  kn_mix  -> Google kn -> en -> guard (English technical terms pass through)
  kn_latn -> guard UNTRANSLATED (Roman-script Kanglish; kept as decided before the switch to Google)

Writes results/mac4/llama-guard-3-1b_baseline.csv (CLAUDE.md results format), appending after
every prompt and resuming on restart. Translations and prompt text are never written to disk.

Usage: python -m baseline.run_baseline --prompts data_tools/output/pilot.jsonl [--out ...] [--limit N]
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = "meta-llama/Llama-Guard-3-1B"
MODEL_NAME = "llama-guard-3-1b"
CONDITION = "baseline"
FIELDS = ["prompt_id", "split", "category", "variant", "model", "condition",
          "refused", "judge_score", "latency_ms", "commit"]


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10, check=True).stdout.strip()
    except Exception:
        return "unknown"


def load_prompts(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"skip line {n}: bad JSON ({e})", file=sys.stderr)
                continue
            if not isinstance(r, dict) or not isinstance(r.get("text"), str) or not r.get("prompt_id"):
                print(f"skip line {n}: missing prompt_id/text", file=sys.stderr)
                continue
            if r.get("split") == "direction":
                continue  # never evaluated
            rows.append(r)
    return rows


def done_keys(out: Path) -> set:
    if not out.exists():
        return set()
    with out.open(newline="", encoding="utf-8") as f:
        return {(r["prompt_id"], r["variant"]) for r in csv.DictReader(f)}


class Translator:
    """Google Translate kn -> en (the study's translator; IndicTrans2 was not downloadable in time)."""
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self, device=None):
        import requests
        self.requests = requests

    def __call__(self, text: str, retries: int = 5) -> str:
        for attempt in range(retries):
            try:
                r = self.requests.get(self.URL, params={"client": "gtx", "sl": "kn", "tl": "en", "dt": "t",
                                                        "q": text}, timeout=20)
                r.raise_for_status()
                out = "".join(seg[0] for seg in r.json()[0] if seg and seg[0])
                if out.strip():
                    return out
                raise RuntimeError("empty translation")
            except Exception as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"google kn->en failed: {type(e).__name__}") from e
                time.sleep(2 * (attempt + 1))
        raise AssertionError("unreachable")


class Guard:
    def __init__(self, device):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch, self.device = torch, device
        self.tok = AutoTokenizer.from_pretrained(GUARD)
        self.model = AutoModelForCausalLM.from_pretrained(GUARD, torch_dtype=torch.bfloat16).to(device).eval()
        self.safe_id = self.tok.encode("safe", add_special_tokens=False)[0]
        self.unsafe_id = self.tok.encode("unsafe", add_special_tokens=False)[0]

    def __call__(self, text: str) -> tuple[int, float]:
        conv = [{"role": "user", "content": [{"type": "text", "text": text}]}]
        ids = self.tok.apply_chat_template(conv, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            out = self.model.generate(ids, max_new_tokens=10, do_sample=False, pad_token_id=0,
                                      output_scores=True, return_dict_in_generate=True)
        new = out.sequences[0, ids.shape[1]:]
        verdict = self.tok.decode(new, skip_special_tokens=True).strip().lower()
        refused = int(verdict.startswith("unsafe"))
        score = float(refused)
        for step, tid in enumerate(new.tolist()):  # first step that emits the verdict token
            if tid in (self.safe_id, self.unsafe_id):
                pair = out.scores[step][0, [self.safe_id, self.unsafe_id]].float()
                score = float(self.torch.softmax(pair, dim=0)[1])
                break
        return refused, round(score, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", default=str(ROOT / "results" / "mac4" / f"{MODEL_NAME}_{CONDITION}.csv"))
    ap.add_argument("--device", choices=("mps", "cpu"))
    ap.add_argument("--limit", type=int, help="only the first N rows (smoke test)")
    args = ap.parse_args()

    path = Path(args.prompts)
    if not path.exists():
        sys.exit(f"ERROR: prompts file not found: {path}")
    rows = load_prompts(path)[: args.limit] if args.limit else load_prompts(path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = done_keys(out)
    todo = [r for r in rows if (r["prompt_id"], r.get("variant", "en")) not in done]
    print(f"{len(rows)} rows, {len(done)} already done, {len(todo)} to run")
    if not todo:
        return

    import torch
    device = args.device or ("mps" if torch.backends.mps.is_available() else "cpu")
    torch.manual_seed(0)
    try:
        guard = Guard(device)
        translator = Translator(device) if any(r.get("variant") in ("kn", "kn_mix") for r in todo) else None
    except Exception as e:
        sys.exit(f"ERROR: model load failed ({type(e).__name__}: {e}). Gated repo? run: hf auth login")

    commit = git_commit()
    new_file = not out.exists() or out.stat().st_size == 0
    errors = 0
    t_start = time.time()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for i, r in enumerate(todo, 1):
            variant = r.get("variant", "en")
            try:
                t0 = time.perf_counter()
                text = r["text"].strip()
                if not text:
                    raise ValueError("empty text")
                if variant in ("kn", "kn_mix"):
                    text = translator(text)
                elif variant not in ("en", "kn_latn"):  # kn_latn goes to the guard untranslated
                    raise ValueError(f"unknown variant {variant!r}")
                refused, score = guard(text)
                latency = round((time.perf_counter() - t0) * 1000)
            except Exception as e:
                errors += 1
                print(f"error {r['prompt_id']}/{variant}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
                continue
            w.writerow({"prompt_id": r["prompt_id"], "split": r.get("split", ""), "category": r.get("category", ""),
                        "variant": variant, "model": MODEL_NAME, "condition": CONDITION, "refused": refused,
                        "judge_score": score, "latency_ms": latency, "commit": commit})
            f.flush()
            if i % 25 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} done, {errors} errors, {time.time() - t_start:.0f}s")
    print(f"wrote {out} ({errors} errors)")


if __name__ == "__main__":
    main()
