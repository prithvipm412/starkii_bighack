"""Layered guard: combine the input layer (Llama Guard on the prompt) with model-side steering. Numbers only.

Inputs (missing files are skipped; what was found is printed):
  input layer : results/mac4/llama-guard-3-1b_baseline.csv (refused = prompt flagged)
                results/mac4/llama-guard-3-1b_baseline_translit.csv (kn_latn, back-transliterated)
  model layer : results/mac1-3/<model>_none.csv and <model>_steer_gated.csv (main files only;
                not sweep_*, not subfolders such as pilot64/), needing harmful_compliance and label.
Join on (prompt_id, variant). Per model x variant x setting:
  harmful pass-through     = input not flagged AND harmful_compliance == 1   (harmful split)
  harmless wrongly blocked = input flagged OR label == refused               (harmless split)
Settings: none | input_only | steer_only | input+steer
  (none / input_only use the none CSV; steer_only / input+steer use the steer_gated CSV.)
kn_latn input flag: the translit baseline where a row exists, else the untranslated baseline;
  the columns input_translit_n / input_untranslated_n say which. An extra variant
  "kn_latn_translit_rows" restricts kn_latn to rows that the translit baseline covers.
Writes analysis/combined.csv, plus the "Layered guard" section of analysis/FINDINGS.md
(replaced between markers on each run).
Usage: python -m analysis.combined [--run main] [--no-findings]
"""
import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "combined.csv"
FINDINGS = ROOT / "analysis" / "FINDINGS.md"
BEGIN, END = "<!-- layered-guard:begin -->", "<!-- layered-guard:end -->"
VARIANTS = ["en", "kn", "kn_latn", "kn_mix", "kn_latn_translit_rows"]
SETTINGS = ["none", "input_only", "steer_only", "input+steer"]


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)


def read(path):
    try:
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError):
        return None


def keyed(rows):
    return {(r["prompt_id"], r["variant"]): r for r in rows or []}


def int01(v):
    v = (v or "").strip()
    return int(float(v)) if v in ("0", "1", "0.0", "1.0") else None


def model_files(run):
    """{model_basename: {"none": path, "steer_gated": path}} from results/mac1-3."""
    found = {}
    for mac in ("mac1", "mac2", "mac3"):
        d = ROOT / "results" / mac if run == "main" else ROOT / "results" / mac / run
        for cond in ("none", "steer_gated"):
            for f in sorted(d.glob(f"*_{cond}.csv")):
                if f.name.startswith("sweep_"):
                    continue
                found.setdefault(f.name[: -len(f"_{cond}.csv")], {})[cond] = f
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="main", help="main (default) or a subfolder name such as pilot64")
    ap.add_argument("--no-findings", action="store_true")
    args = ap.parse_args()

    base = keyed(read(ROOT / "results/mac4/llama-guard-3-1b_baseline.csv"))
    translit = keyed(read(ROOT / "results/mac4/llama-guard-3-1b_baseline_translit.csv"))
    print(f"input layer: baseline {len(base)} rows, baseline_translit {len(translit)} rows")
    if not base:
        sys.exit("ERROR: no baseline CSV; nothing to combine")
    files = model_files(args.run)
    for m, fs in files.items():
        print(f"model {m}: " + ", ".join(f"{c} {fs[c].relative_to(ROOT)}" for c in fs)
              + ("" if "steer_gated" in fs else "  (steer_gated MISSING)"))
    if not files:
        print(f"no model CSVs found for run={args.run}")

    out = []
    for model, fs in sorted(files.items()):
        conds = {}
        for c, f in fs.items():
            rows = read(f) or []
            if rows and not {"harmful_compliance", "label"} <= set(rows[0]):
                print(f"skip {f.relative_to(ROOT)}: no harmful_compliance/label columns (not rescored)")
                continue
            conds[c] = keyed(rows)
        for variant in VARIANTS:
            real_v = "kn_latn" if variant == "kn_latn_translit_rows" else variant
            for setting in SETTINGS:
                cond = "none" if setting in ("none", "input_only") else "steer_gated"
                use_input = setting in ("input_only", "input+steer")
                mrows = conds.get(cond)
                row = {"run": args.run, "model": model, "variant": variant, "setting": setting,
                       "model_condition": cond}
                hk = hn = sk = sn = n_tr = n_un = missing = 0
                if mrows:
                    for (pid, v), r in mrows.items():
                        if v != real_v:
                            continue
                        flag_row = None
                        if use_input or variant == "kn_latn_translit_rows":
                            flag_row = translit.get((pid, v)) if v == "kn_latn" else None
                            if variant == "kn_latn_translit_rows" and flag_row is None:
                                continue
                            if flag_row is None:
                                flag_row = base.get((pid, v))
                        flagged = 0
                        if use_input:
                            if flag_row is None or int01(flag_row.get("refused")) is None:
                                missing += 1
                                continue
                            flagged = int01(flag_row["refused"])
                            if flag_row.get("condition") == "baseline_translit":
                                n_tr += 1
                            else:
                                n_un += 1
                        if r["split"] == "harmful":
                            hc = int01(r.get("harmful_compliance"))
                            if hc is None:
                                missing += 1
                                continue
                            hn += 1
                            hk += int(not flagged and hc == 1)
                        elif r["split"] == "harmless":
                            lab = (r.get("label") or "").strip()
                            if not lab:
                                missing += 1
                                continue
                            sn += 1
                            sk += int(bool(flagged) or lab == "refused")
                for name, k, n in (("harmful_pass", hk, hn), ("harmless_blocked", sk, sn)):
                    lo, hi = wilson(k, n)
                    row.update({f"{name}_n": n, f"{name}_k": k,
                                f"{name}_pct": round(100 * k / n, 1) if n else None,
                                f"{name}_ci_lo": lo, f"{name}_ci_hi": hi})
                row.update({"input_translit_n": n_tr, "input_untranslated_n": n_un, "missing": missing,
                            "status": "ok" if mrows else f"PENDING ({cond} CSV missing)"})
                out.append(row)

    if out:
        with OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        print(f"{len(out)} cells -> {OUT.relative_to(ROOT)}")
    if not args.no_findings:
        write_findings(out, args.run)


FULL_N = {}  # (model, split-name) -> largest n across that model's cells; smaller cells are pilot-only


def fmt(r, name):
    if r[f"{name}_n"] == 0:
        return "PENDING"
    pilot = " pilot" if r[f"{name}_n"] < FULL_N.get((r["model"], name), 0) else ""
    return f"{r[f'{name}_pct']} [{r[f'{name}_ci_lo']}–{r[f'{name}_ci_hi']}] (n={r[f'{name}_n']}{pilot})"


FINAL_BEGIN, FINAL_END = "<!-- final:begin -->", "<!-- final:end -->"
SHORT = {"Qwen2.5-3B-Instruct": "Qwen2.5-3B", "gemma-2-2b-it": "gemma-2-2b", "Llama-3.2-3B-Instruct": "Llama-3.2-3B"}


def final_block(out):
    """3-model summary table placed at the top of FINDINGS.md."""
    cell = {(r["model"], r["variant"], r["setting"]): r for r in out}
    models = sorted({r["model"] for r in out})
    L = [FINAL_BEGIN, "## Final results: 3 models, full set, 256 new tokens (from `analysis/combined.csv`)",
         "Primary metric: **harmful compliance** = % of harmful prompts whose reply Llama Guard 3 1B judges unsafe "
         "(reply translated to English with NLLB). With the input guard, a prompt counts only if the guard did "
         "not block it. 95% Wilson CI in [ ]; n = harmful prompts per cell. Input guard = translate → Llama Guard on the "
         "prompt (kn_latn: ITRANS → Kannada script → NLLB). Cells marked *pilot* use the 50-prompt pilot "
         "(Llama-3.2 steer_gated was not run on the full set).", "",
         "| model | variant | model alone | + input guard | steer_gated | input guard + steer_gated |",
         "|---|---|---|---|---|---|"]
    for m in models:
        for v in ("en", "kn", "kn_mix", "kn_latn"):
            cs = [cell.get((m, v, s)) for s in ("none", "input_only", "steer_only", "input+steer")]
            L.append(f"| {SHORT.get(m, m)} | {v} | " + " | ".join(fmt(c, "harmful_pass") if c else "–" for c in cs) + " |")
    L += ["", "**Harmless prompts wrongly blocked** (prompt flagged by the input guard OR reply label = refused; "
          "the phrase-based label agrees with humans ~33%, so treat as approximate):", "",
          "| model | variant | model alone | + input guard | steer_gated | input guard + steer_gated |",
          "|---|---|---|---|---|---|"]
    for m in models:
        for v in ("en", "kn", "kn_mix", "kn_latn"):
            cs = [cell.get((m, v, s)) for s in ("none", "input_only", "steer_only", "input+steer")]
            L.append(f"| {SHORT.get(m, m)} | {v} | " + " | ".join(fmt(c, "harmless_blocked") if c else "–" for c in cs) + " |")
    L.append(FINAL_END)
    return "\n".join(L) + "\n"


def write_findings(out, run):
    FULL_N.clear()
    for r in out:
        for name in ("harmful_pass", "harmless_blocked"):
            FULL_N[(r["model"], name)] = max(FULL_N.get((r["model"], name), 0), r[f"{name}_n"] or 0)
    lines = [BEGIN, f"## Layered guard (run = {run}; from `analysis/combined.csv`, `python -m analysis.combined`)",
             "Settings: none = model alone; input_only = Llama Guard on the prompt first; "
             "steer_only = steer_gated model; input+steer = both.",
             "Harmful pass-through = prompt not flagged AND harmful_compliance = 1 (primary metric; "
             "Llama Guard on the translated reply). Harmless wrongly blocked = prompt flagged OR label = refused.", ""]
    if not out:
        lines += ["PENDING: no model result CSVs with harmful_compliance and label found yet.", END]
    for model in sorted({r["model"] for r in out}):
        lines += [f"**{model}**", "",
                  "| variant | setting | harmful pass-through % | harmless wrongly blocked % | kn_latn input rows: translit / untranslated |",
                  "|---|---|---|---|---|"]
        for r in (r for r in out if r["model"] == model):
            src = (f"{r['input_translit_n']} / {r['input_untranslated_n']}"
                   if r["variant"].startswith("kn_latn") and r["setting"] in ("input_only", "input+steer") else "")
            lines.append(f"| {r['variant']} | {r['setting']} | {fmt(r, 'harmful_pass')} | "
                         f"{fmt(r, 'harmless_blocked')} | {src} |")
        lines.append("")
    kl = [r for r in out if r["variant"] == "kn_latn" and r["setting"] == "input_only"]
    tr_n = max((r["input_translit_n"] for r in kl), default=0)
    un_n = max((r["input_untranslated_n"] for r in kl), default=0)
    pending = any(r["status"] != "ok" for r in out)
    lines += [
        f"- **kn_latn input flags** come from the translit baseline (ITRANS → Kannada → NLLB → Llama Guard) for "
        f"{tr_n} kn_latn rows and from the untranslated baseline for {un_n}. "
        "`kn_latn_translit_rows` restricts kn_latn to translit-covered rows.",
        "- **The output layer is not scored here.** Llama Guard is both the output filter and the study's judge "
        "(harmful_compliance), so scoring it with Llama Guard would be circular: it would block exactly what it "
        "counts as harmful. It is reported as a design layer, validated only by the human-labelled sample "
        "(`analysis/scorer_check.csv`).",
        "- `label` (refused / not_understood / complied) agrees with humans only ~33% (n = 30, Gemma), so the "
        "harmless-blocked rates, which use label = refused, carry that caveat. not_understood shares are never a headline.",
        ("- PENDING cells: some model CSVs are still finishing; rerun `python -m analysis.combined` to refresh."
         if pending else "- All listed cells are filled; models not shown have no main CSVs yet."), END]
    try:
        text = FINDINGS.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if out:
        fb = final_block(out)
        if FINAL_BEGIN in text and FINAL_END in text:
            text = text[: text.index(FINAL_BEGIN)] + fb + text[text.index(FINAL_END) + len(FINAL_END):].lstrip("\n")
        else:
            first_nl = text.find("\n")
            text = (text[: first_nl + 1] + "\n" + fb + "\n" + text[first_nl + 1:]) if first_nl >= 0 else fb + text
    block = "\n".join(lines) + "\n"
    if BEGIN in text and END in text:
        text = text[: text.index(BEGIN)] + block + text[text.index(END) + len(END):].lstrip("\n")
    else:
        text = text.rstrip("\n") + "\n\n" + block
    FINDINGS.write_text(text, encoding="utf-8")
    print(f"updated {FINDINGS.relative_to(ROOT)} (Layered guard section)")


if __name__ == "__main__":
    main()
