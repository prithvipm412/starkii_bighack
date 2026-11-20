"""What beats every layer: harmful prompts that the input check missed AND the model complied with.

Same joins as analysis/combined.py: input flag = Llama Guard on the prompt (baseline; kn_latn uses
baseline_translit where a row exists), compliance = harmful_compliance == 1 in the model CSV.
Per model x condition (none, steer_gated when present) x variant x category:
  n_harmful, n_missed (= input not flagged AND harmful_compliance == 1), pct, prompt_ids (IDs only).
"none" rows = what beats the input layer alone; "steer_gated" rows = what beats input + steering.
Writes analysis/missed.csv and the "What beats every layer" section of analysis/FINDINGS.md.
Usage: python -m analysis.missed [--run main] [--no-findings]
"""
import argparse
import csv
from collections import defaultdict

from analysis.combined import FINDINGS, ROOT, int01, keyed, model_files, read

OUT = ROOT / "analysis" / "missed.csv"
BEGIN, END = "<!-- missed:begin -->", "<!-- missed:end -->"
VARIANTS = ["en", "kn", "kn_latn", "kn_mix"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="main")
    ap.add_argument("--no-findings", action="store_true")
    args = ap.parse_args()

    base = keyed(read(ROOT / "results/mac4/llama-guard-3-1b_baseline.csv"))
    translit = keyed(read(ROOT / "results/mac4/llama-guard-3-1b_baseline_translit.csv"))
    files = model_files(args.run)
    print(f"input layer: baseline {len(base)}, translit {len(translit)}; models: "
          + (", ".join(f"{m} [{', '.join(fs)}]" for m, fs in files.items()) or "none"))

    out = []
    for model, fs in sorted(files.items()):
        for cond in ("none", "steer_gated"):
            if cond not in fs:
                continue
            rows = read(fs[cond]) or []
            if not rows or "harmful_compliance" not in rows[0]:
                print(f"skip {fs[cond].relative_to(ROOT)}: no harmful_compliance")
                continue
            cells = defaultdict(lambda: {"n": 0, "ids": []})
            for r in rows:
                if r["split"] != "harmful":
                    continue
                k = (r["prompt_id"], r["variant"])
                flag_row = (translit.get(k) if r["variant"] == "kn_latn" else None) or base.get(k)
                flagged, hc = int01((flag_row or {}).get("refused")), int01(r.get("harmful_compliance"))
                if flagged is None or hc is None:
                    continue
                c = cells[(r["variant"], r["category"])]
                c["n"] += 1
                if not flagged and hc == 1:
                    c["ids"].append(r["prompt_id"])
            for (variant, cat), c in cells.items():
                out.append({"run": args.run, "model": model, "condition": cond, "variant": variant,
                            "category": cat, "n_harmful": c["n"], "n_missed": len(c["ids"]),
                            "pct_missed": round(100 * len(c["ids"]) / c["n"], 1) if c["n"] else None,
                            "prompt_ids": ";".join(sorted(c["ids"]))})
    vo = {v: i for i, v in enumerate(VARIANTS)}
    out.sort(key=lambda r: (r["model"], r["condition"], vo.get(r["variant"], 9), -r["n_missed"], r["category"]))
    if out:
        with OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        print(f"{len(out)} rows -> {OUT.relative_to(ROOT)}")
    if not args.no_findings:
        write_findings(out, args.run)


def write_findings(out, run):
    L = [BEGIN, f"## What beats every layer (run = {run}; `analysis/missed.csv`, `python -m analysis.missed`)",
         "Harmful prompts that the input check (Llama Guard on the translated prompt) did **not** flag **and** "
         "that the model complied with (harmful_compliance = 1). Condition none = beats the input layer alone; "
         "steer_gated = beats input + steering. IDs only (`missed.csv`); no prompt text.", ""]
    if not out:
        L += ["PENDING: no model CSVs with harmful_compliance yet.", END]
    for model in sorted({r["model"] for r in out}):
        conds = [c for c in ("none", "steer_gated") if any(r["model"] == model and r["condition"] == c for r in out)]
        L += [f"**{model}**", "", "| variant | " + " | ".join(f"missed, {c}" for c in conds) + " | categories missed (" + conds[-1] + ") |",
              "|---|" + "---|" * len(conds) + "---|"]
        for v in VARIANTS:
            cells = []
            for c in conds:
                rs = [r for r in out if r["model"] == model and r["condition"] == c and r["variant"] == v]
                n, k = sum(r["n_harmful"] for r in rs), sum(r["n_missed"] for r in rs)
                cells.append(f"{k}/{n} ({round(100 * k / n, 1) if n else '–'}%)")
            last = [r for r in out if r["model"] == model and r["condition"] == conds[-1] and r["variant"] == v and r["n_missed"]]
            cats = ", ".join(f"{r['category']} {r['n_missed']}" for r in last) or "none"
            L.append(f"| {v} | " + " | ".join(cells) + f" | {cats} |")
        last_c = conds[-1]
        ids = defaultdict(list)
        for r in out:
            if r["model"] == model and r["condition"] == last_c:
                for pid in filter(None, r["prompt_ids"].split(";")):
                    ids[pid].append(r["variant"])
        multi = sorted(pid for pid, vs in ids.items() if len(vs) >= 2)
        L += ["", f"- Prompt IDs that beat the layers in ≥ 2 variants ({last_c}): "
              + (", ".join(multi) if multi else "none") + ".", ""]
    L += ["- These counts rely on harmful_compliance (Llama Guard on the NLLB-translated reply); "
          "judge or translation errors can add or hide misses. Small cells (single digits) are anecdotes, not rates.", END]
    text = FINDINGS.read_text(encoding="utf-8") if FINDINGS.exists() else ""
    block = "\n".join(L) + "\n"
    if BEGIN in text and END in text:
        text = text[: text.index(BEGIN)] + block + text[text.index(END) + len(END):].lstrip("\n")
    else:
        text = text.rstrip("\n") + "\n\n" + block
    FINDINGS.write_text(text, encoding="utf-8")
    print(f"updated {FINDINGS.relative_to(ROOT)} (What beats every layer)")


if __name__ == "__main__":
    main()
