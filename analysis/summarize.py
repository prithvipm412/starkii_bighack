"""Summarize every results/mac*/*.csv (standard header) into analysis/summary.csv. Numbers only.

Per model x condition x variant:
  harmful refusal %       (refused=1 on split=harmful)
  harmless wrong-refusal % (refused=1 on split=harmless)
  harmful_compliance %     (only if a harmful_compliance column exists)
each with n and a 95% Wilson CI; plus median latency_ms.

Skipped: files without the standard header, sweep_* files (same conditions, different settings),
subfolders (gate/, smoke/). Duplicate (model, condition, prompt_id, variant) rows: the last one wins.
Usage: python -m analysis.summarize
"""
import csv
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
    return int(float(v)) if v not in ("", "nan", "None") else None


def load():
    rows = {}
    files = []
    for f in sorted(ROOT.glob("results/mac*/*.csv")):
        if f.name.startswith("sweep_"):
            continue
        try:
            with f.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames or any(c not in reader.fieldnames for c in STD):
                    continue
                files.append(f.relative_to(ROOT))
                for r in reader:
                    rows[(r["model"], r["condition"], r["prompt_id"], r["variant"])] = r
        except (OSError, csv.Error, UnicodeDecodeError) as e:
            print(f"skip {f}: {e}", file=sys.stderr)
    return list(rows.values()), files


def rate(rows, col):
    vals = [as01(r.get(col)) for r in rows]
    vals = [v for v in vals if v is not None]
    n, k = len(vals), sum(vals)
    lo, hi = wilson(k, n)
    return n, k, (round(100 * k / n, 1) if n else None), lo, hi


def main():
    rows, files = load()
    if not rows:
        sys.exit("no result rows found")
    cells = defaultdict(list)
    for r in rows:
        cells[(r["model"], r["condition"], r["variant"])].append(r)
    out = []
    for (model, cond, var), rs in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1], VARIANT_ORDER.get(kv[0][2], 9))):
        harmful = [r for r in rs if r["split"] == "harmful"]
        harmless = [r for r in rs if r["split"] == "harmless"]
        row = {"model": model, "condition": cond, "variant": var}
        for name, sub, col in (("harmful_refusal", harmful, "refused"),
                               ("harmless_wrong_refusal", harmless, "refused"),
                               ("harmful_compliance", harmful, "harmful_compliance")):
            n, k, pct, lo, hi = rate(sub, col)
            row.update({f"{name}_n": n, f"{name}_k": k, f"{name}_pct": pct,
                        f"{name}_ci_lo": lo, f"{name}_ci_hi": hi})
        lat = [float(r["latency_ms"]) for r in rs if (r.get("latency_ms") or "").strip()]
        row["median_latency_ms"] = round(statistics.median(lat)) if lat else None
        out.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{len(files)} files, {len(rows)} rows -> {len(out)} cells -> {OUT.relative_to(ROOT)}")
    for r in out:
        print(f"{r['model'][:28]:28s} {r['condition']:13s} {r['variant']:8s} "
              f"harmful {r['harmful_refusal_pct']}% (n={r['harmful_refusal_n']})  "
              f"harmless {r['harmless_wrong_refusal_pct']}% (n={r['harmless_wrong_refusal_n']})")


if __name__ == "__main__":
    main()
