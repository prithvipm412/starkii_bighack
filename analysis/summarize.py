"""Summarize every results/mac*/ result CSV (standard header) into analysis/summary.csv. Numbers only.

Per run x scope x model x condition x variant:
  harmful refusal %         refused=1 on split=harmful (phrase match)
  harmless wrong-refusal %  refused=1 on split=harmless
  harmful_compliance %      harmful split, Llama Guard on the reply (only if the column exists)
  label breakdown           refused / not_understood / complied % per split (only if `label` exists)
Each rate has n, k and a 95% Wilson CI; plus median latency_ms.

run   = "main" for results/macN/*.csv, else the subfolder name (e.g. pilot64 = 64-token pilot).
scope = "all"; plus "pilot" (only the pilot's prompt_ids) for cells that also hold non-pilot rows,
        so full-set files can be compared with pilot-only ones. Pilot ids come from
        data_tools/output/pilot.jsonl (or raw/en_pilot.jsonl); without them, no pilot scope.
Skipped: files without the standard header, sweep_* files, gate/ and smoke/ folders.
Duplicate (run, model, condition, prompt_id, variant) rows: the last one wins.
Usage: python -m analysis.summarize
"""
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "summary.csv"
STD = ["prompt_id", "split", "category", "variant", "model", "condition",
       "refused", "judge_score", "latency_ms", "commit"]
VARIANT_ORDER = {"en": 0, "kn": 1, "kn_latn": 2, "kn_mix": 3}
PILOT_FILES = [ROOT / "data_tools" / "output" / "pilot.jsonl", ROOT / "data_tools" / "output" / "raw" / "en_pilot.jsonl"]


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)


def as01(v):
    v = (v or "").strip()
    try:
        return int(float(v)) if v not in ("", "nan", "None") else None
    except ValueError:
        return None


def pilot_ids():
    for f in PILOT_FILES:
        try:
            with f.open(encoding="utf-8") as fh:
                return {json.loads(l)["prompt_id"] for l in fh if l.strip()}
        except (OSError, ValueError, KeyError):
            continue
    return set()


def load():
    rows, files = {}, []
    paths = sorted(ROOT.glob("results/mac*/*.csv")) + sorted(ROOT.glob("results/mac*/*/*.csv"))
    for f in paths:
        run = "main" if f.parent.parent.name == "results" else f.parent.name
        if f.name.startswith("sweep_") or run in ("gate", "smoke"):
            continue
        try:
            with f.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames or any(c not in reader.fieldnames for c in STD):
                    continue
                files.append(f.relative_to(ROOT))
                for r in reader:
                    r["_run"] = run
                    rows[(run, r["model"], r["condition"], r["prompt_id"], r["variant"])] = r
        except (OSError, csv.Error, UnicodeDecodeError) as e:
            print(f"skip {f}: {e}", file=sys.stderr)
    return list(rows.values()), files


def rate(rows, col):
    vals = [as01(r.get(col)) for r in rows]
    vals = [v for v in vals if v is not None]
    n, k = len(vals), sum(vals)
    lo, hi = wilson(k, n)
    return n, k, (round(100 * k / n, 1) if n else None), lo, hi


def cell_row(run, scope, model, cond, var, rs):
    harmful = [r for r in rs if r["split"] == "harmful"]
    harmless = [r for r in rs if r["split"] == "harmless"]
    row = {"run": run, "scope": scope, "model": model, "condition": cond, "variant": var}
    for name, sub, col in (("harmful_refusal", harmful, "refused"),
                           ("harmless_wrong_refusal", harmless, "refused"),
                           ("harmful_compliance", harmful, "harmful_compliance")):
        n, k, pct, lo, hi = rate(sub, col)
        row.update({f"{name}_n": n, f"{name}_k": k, f"{name}_pct": pct,
                    f"{name}_ci_lo": lo, f"{name}_ci_hi": hi})
    for split, sub in (("harmful", harmful), ("harmless", harmless)):
        labs = [(r.get("label") or "").strip() for r in sub]
        labs = [l for l in labs if l]
        row[f"{split}_label_n"] = len(labs)
        for lab in ("refused", "not_understood", "complied"):
            row[f"{split}_label_{lab}_pct"] = round(100 * labs.count(lab) / len(labs), 1) if labs else None
    lat = []
    for r in rs:
        try:
            lat.append(float(r["latency_ms"]))
        except (TypeError, ValueError):
            pass
    row["median_latency_ms"] = round(statistics.median(lat)) if lat else None
    return row


def main():
    rows, files = load()
    if not rows:
        sys.exit("no result rows found")
    pids = pilot_ids()
    cells = defaultdict(list)
    for r in rows:
        cells[(r["_run"], r["model"], r["condition"], r["variant"])].append(r)
    out = []
    key = lambda kv: (kv[0][0], kv[0][1], kv[0][2], VARIANT_ORDER.get(kv[0][3], 9))
    for (run, model, cond, var), rs in sorted(cells.items(), key=key):
        out.append(cell_row(run, "all", model, cond, var, rs))
        if pids and any(r["prompt_id"] not in pids for r in rs):
            sub = [r for r in rs if r["prompt_id"] in pids]
            if sub:
                out.append(cell_row(run, "pilot", model, cond, var, sub))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{len(files)} files, {len(rows)} rows -> {len(out)} cells -> {OUT.relative_to(ROOT)}")
    for r in out:
        print(f"{r['run'][:7]:7s} {r['scope']:5s} {r['model'].split('/')[-1][:16]:16s} {r['condition'][:12]:12s} {r['variant']:7s} "
              f"H n={r['harmful_refusal_n']} ref {r['harmful_refusal_pct']} comp {r['harmful_compliance_pct']} "
              f"R/NU/C {r['harmful_label_refused_pct']}/{r['harmful_label_not_understood_pct']}/{r['harmful_label_complied_pct']} | "
              f"S ref {r['harmless_wrong_refusal_pct']} "
              f"R/NU/C {r['harmless_label_refused_pct']}/{r['harmless_label_not_understood_pct']}/{r['harmless_label_complied_pct']}")


if __name__ == "__main__":
    main()
