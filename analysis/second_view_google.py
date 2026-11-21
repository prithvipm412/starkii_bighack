"""Verify the guard's optional Google translator for the English second view. Scores and IDs only.

GUARD_SECOND_VIEW_TRANSLATOR=google: en -> kn via Google (as analysis/build_google.py), kn -> en via NLLB,
Llama Guard again. Compared with the default nllb mode (results/mac4/second_view_en.csv, not modified).
  a/b. contrast set (~/Desktop/datasets/contrast.jsonl, outside the repo), en + kn
  c.   the English study prompts that are borderline in second_view_en.csv (0.5 < p < 0.9), re-scored;
       all other English verdicts are carried over (the rule does not touch them)
  d.   fallback: a Google failure (unreachable endpoint, raised error, timeout) must give "nllb (fallback)"
Writes results/mac4/guard_secondview_google.csv (new file).
Usage: python -m analysis.second_view_google [--contrast PATH] [--prompts PATH]
"""
import argparse
import csv
import json
from pathlib import Path

import guard.guard as gg
from analysis.combined import ROOT, wilson

R = ROOT / "results" / "mac4"
FIELDS = ["set", "id", "variant", "split", "category", "held_out", "p_unsafe", "p_second_view",
          "second_view_translator", "blocked", "blocked_nllb_mode"]


def jl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def cell(ks):
    n, k = len(ks), sum(ks)
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f} [{lo}–{hi}] ({k}/{n})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--contrast", default=str(Path.home() / "Desktop" / "datasets" / "contrast.jsonl"))
    ap.add_argument("--prompts", default=str(ROOT / "data_tools" / "output" / "full.jsonl"))
    args = ap.parse_args()
    g = gg.LanguageBarrierGuard(second_view=True, second_view_translator="google")
    nl = gg.LanguageBarrierGuard(second_view=True, second_view_translator="nllb")
    nl._guard, nl._translator = g.guard, g.translator
    out = []

    print("a/b. contrast set, google mode")
    print("| id | variant | expected | p_unsafe | p_second_view | translator | verdict | nllb-mode verdict |\n|---|---|---|---|---|---|---|---|")
    for r in jl(args.contrast):
        v, w = g.input_check(r["text"]), nl.input_check(r["text"])
        out.append({"set": "contrast", "id": r["id"], "variant": r["variant"], "split": r["expected"], "category": "",
                    "held_out": "", "p_unsafe": v["p_unsafe"], "p_second_view": v["p_second_view"],
                    "second_view_translator": v["second_view_translator"], "blocked": int(v["blocked"]),
                    "blocked_nllb_mode": int(w["blocked"])})
        p2 = "–" if v["p_second_view"] is None else f"{v['p_second_view']:.3f}"
        print(f"| {r['id']} | {r['variant']} | {r['expected']} | {v['p_unsafe']:.3f} | {p2} | "
              f"{v['second_view_translator'] or '–'} | {'block' if v['blocked'] else 'allow'} | "
              f"{'block' if w['blocked'] else 'allow'} |")
    harm_ok = all(o["blocked"] for o in out if o["set"] == "contrast" and o["split"] == "block")

    base = {r["prompt_id"]: r for r in csv.DictReader((R / "second_view_en.csv").open(encoding="utf-8"))}
    texts = {r["prompt_id"]: r["text"] for r in jl(args.prompts) if r.get("variant") == "en"}
    border = [i for i, b in base.items() if b["decided_by"] != "input"]
    final = {i: int(b["blocked"]) for i, b in base.items()}
    tr_counts = {}
    for i in border:
        v = g.input_check(texts[i])
        b = base[i]
        final[i] = int(v["blocked"])
        tr_counts[v["second_view_translator"]] = tr_counts.get(v["second_view_translator"], 0) + 1
        out.append({"set": "study_en_borderline", "id": i, "variant": "en", "split": b["split"],
                    "category": b["category"], "held_out": b["held_out"], "p_unsafe": v["p_unsafe"],
                    "p_second_view": v["p_second_view"], "second_view_translator": v["second_view_translator"],
                    "blocked": int(v["blocked"]), "blocked_nllb_mode": int(b["blocked"])})
    print(f"\nc. borderline re-scored: {len(border)}; translator used: {tr_counts}")
    print("| ids | harmful caught, nllb mode | harmful caught, google mode | harmless flagged, nllb mode | harmless flagged, google mode |\n|---|---|---|---|---|")
    for name, ids in (("all 450", list(base)), ("held-out 350", [i for i in base if base[i]["held_out"] == "1"])):
        cells = []
        for split in ("harmful", "harmless"):
            s = [i for i in ids if base[i]["split"] == split]
            cells += [cell([int(base[i]["blocked"]) for i in s]), cell([final[i] for i in s])]
        print(f"| {name} | " + " | ".join(cells) + " |")
    print("changed vs nllb mode:", [(o["id"], o["split"], o["category"], o["blocked_nllb_mode"], o["blocked"])
                                    for o in out if o["set"] == "study_en_borderline" and o["blocked"] != o["blocked_nllb_mode"]])

    print("\nd. fallback")
    probe = next(r["text"] for r in jl(args.contrast) if r["id"] == "c01" and r["variant"] == "en")
    real_url, real_fn = gg.GOOGLE_URL, gg.google_en_to_kn

    def raise_timeout(*a, **k):
        raise TimeoutError("simulated")

    for name, setup in (("unreachable endpoint", lambda: setattr(gg, "GOOGLE_URL", "http://127.0.0.1:9/x")),
                        ("simulated timeout", lambda: setattr(gg, "google_en_to_kn", raise_timeout))):
        setup()
        try:
            v = g.input_check(probe)
            print(f"{name}: translator={v['second_view_translator']!r}, p_unsafe={v['p_unsafe']:.3f}, "
                  f"p_second_view={v['p_second_view']:.3f}, blocked={v['blocked']}")
            ok = v["second_view_translator"] == "nllb (fallback)"
        finally:
            gg.GOOGLE_URL, gg.google_en_to_kn = real_url, real_fn
        out.append({"set": "fallback_test", "id": name, "variant": "en", "split": "allow", "category": "", "held_out": "",
                    "p_unsafe": v["p_unsafe"], "p_second_view": v["p_second_view"],
                    "second_view_translator": v["second_view_translator"], "blocked": int(v["blocked"]),
                    "blocked_nllb_mode": ""})
        print("  fallback OK" if ok else "  FALLBACK FAILED")

    with (R / "guard_secondview_google.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    print("\ncontrast harmful all blocked:", harm_ok, "->", "mode OK (optional, off by default)" if harm_ok else "REJECT")


if __name__ == "__main__":
    main()
