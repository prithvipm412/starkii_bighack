"""Check the pipeline's `refused` scorer against human hand labels. Numbers only.

Reads results/mac*/handlabels.csv. Required columns: prompt_id, condition, and one of
  human_label    refused | complied | not_understood | other   (preferred)
  human_refused  0/1                                           (older format)
Optional: variant (default "en"), model (default: the only model in that mac's results).
Each label is joined to the same mac's results/<mac>/*.csv row on (model, condition, prompt_id, variant).

Writes analysis/scorer_check.csv, one row per model x variant plus an ALL row per model:
  n, accuracy (pipeline refused == human refused), pipeline refused-rate, human refused-rate,
  confusion: pipe1_human_refused, pipe1_human_not_understood, pipe1_human_complied_other,
             pipe0_human_refused, pipe0_human_not_understood, pipe0_human_complied_other,
  unmatched labels (no pipeline row).
Usage: python -m analysis.scorer_check [--root DIR]
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STD = {"prompt_id", "split", "variant", "model", "condition", "refused"}
VARIANTS = ["en", "kn", "kn_latn", "kn_mix"]


def read_csv(path: Path):
    try:
        with path.open(newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            return list(r.fieldnames or []), list(r)
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        print(f"skip {path}: {e}", file=sys.stderr)
        return [], []


def human_class(row) -> str | None:
    lab = (row.get("human_label") or "").strip().lower().replace(" ", "_").replace("'", "")
    if lab:
        if lab in ("refused", "refusal", "1"):
            return "refused"
        if lab in ("not_understood", "dont_understand", "confused", "clarify", "clarification"):
            return "not_understood"
        return "complied_other"
    v = (row.get("human_refused") or "").strip()
    if v in ("0", "1"):
        return "refused" if v == "1" else "complied_other"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT), help="repo root holding results/ (for testing)")
    ap.add_argument("--out", default=str(ROOT / "analysis" / "scorer_check.csv"))
    args = ap.parse_args()
    root = Path(args.root)

    cells = defaultdict(lambda: defaultdict(int))
    n_labels = 0
    for hl in sorted(root.glob("results/mac*/handlabels.csv")):
        cols, labels = read_csv(hl)
        if not {"prompt_id", "condition"} <= set(cols) or not ({"human_label", "human_refused"} & set(cols)):
            print(f"skip {hl}: needs prompt_id, condition and human_label or human_refused", file=sys.stderr)
            continue
        pipe = {}
        models = set()
        for f in hl.parent.glob("*.csv"):
            if f.name == "handlabels.csv" or f.name.startswith("sweep_"):
                continue
            fc, rows = read_csv(f)
            if not STD <= set(fc):
                continue
            for r in rows:
                pipe[(r["model"], r["condition"], r["prompt_id"], r["variant"])] = r
                models.add(r["model"])
        for lab in labels:
            hc = human_class(lab)
            if hc is None:
                continue
            n_labels += 1
            variant = (lab.get("variant") or "en").strip()
            model = (lab.get("model") or "").strip() or (next(iter(models)) if len(models) == 1 else "?")
            p = pipe.get((model, lab["condition"].strip(), lab["prompt_id"].strip(), variant))
            for key in ((model, variant), (model, "ALL")):
                c = cells[key]
                if p is None or (p.get("refused") or "").strip() not in ("0", "1"):
                    c["unmatched"] += 1
                    continue
                pr = int(p["refused"])
                c["n"] += 1
                c["correct"] += int(pr == (hc == "refused"))
                c["pipe_refused"] += pr
                c["human_refused"] += int(hc == "refused")
                c[f"pipe{pr}_human_{hc}"] += 1

    if not cells:
        sys.exit("no hand labels found (results/mac*/handlabels.csv)")
    conf = [f"pipe{p}_human_{h}" for p in (1, 0) for h in ("refused", "not_understood", "complied_other")]
    out = []
    order = {v: i for i, v in enumerate(VARIANTS + ["ALL"])}
    for (model, variant), c in sorted(cells.items(), key=lambda kv: (kv[0][0], order.get(kv[0][1], 8))):
        n = c["n"]
        out.append({"model": model, "variant": variant, "n": n,
                    "accuracy_pct": round(100 * c["correct"] / n, 1) if n else None,
                    "pipeline_refused_pct": round(100 * c["pipe_refused"] / n, 1) if n else None,
                    "human_refused_pct": round(100 * c["human_refused"] / n, 1) if n else None,
                    **{k: c[k] for k in conf}, "unmatched": c["unmatched"]})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{n_labels} labels -> {args.out}")
    for r in out:
        print(f"{r['model'][:28]:28s} {r['variant']:8s} n={r['n']:3d} acc={r['accuracy_pct']}%  "
              f"pipe-refused but human not_understood={r['pipe1_human_not_understood']}  unmatched={r['unmatched']}")


if __name__ == "__main__":
    main()
