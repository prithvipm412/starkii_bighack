"""Download public prompt sets and build English JSONL splits (mac4).

Outputs (gitignored, under data_tools/output/raw/):
  raw/<source>.csv|json          downloaded files
  raw/en_full.jsonl              ~300 harmful + 150 harmless (evaluation)
  raw/en_pilot.jsonl             50 harmful + 50 harmless, subset of full, category-balanced
  raw/en_direction.jsonl         64 harmful + 64 harmless, disjoint from full (never evaluated)
  raw/id_map.csv                 prompt_id -> source id (no text)
  direction.jsonl                copy of en_direction (English only; not passed through data_tools.build)

Record format = CLAUDE.md prompt format (English input to data_tools.build):
  {"prompt_id", "split": "harmful|harmless|direction", "category", "source", "variant": "en", "text"}
ids: h0001.. harmful, s0001.. harmless (pilot reuses full ids), d0001.. direction.
Direction rows: category = "harmful" | "harmless" (CLAUDE.md has no label field; this is how
extract_direction can tell the two sides apart).

Deterministic: fixed seed; ids assigned in sorted (category, source id) order.
Usage: python analysis/get_data.py [--force]
"""
import csv
import json
import random
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_tools" / "output" / "raw"
SEED = 1234
TIMEOUT = 60

SOURCES = {
    "harmbench.csv": "https://raw.githubusercontent.com/centerforaisafety/HarmBench/main/data/behavior_datasets/harmbench_behaviors_text_all.csv",
    "advbench.csv": "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv",
    "xstest.csv": "https://raw.githubusercontent.com/paul-rottger/exaggerated-safety/main/xstest_prompts.csv",
    "alpaca.json": "https://raw.githubusercontent.com/tatsu-lab/stanford_alpaca/main/alpaca_data.json",
}

N_FULL_HARMFUL = 300   # all HarmBench standard (200) + AdvBench fill
N_FULL_HARMLESS = 150  # XSTest safe + general
N_GENERAL_EVAL = 20    # general (alpaca) prompts inside the harmless eval set
N_PILOT = 50           # per label
N_DIR = 64             # per label


def download(force: bool) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 0 and not force:
            continue
        print(f"downloading {name}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dataset-fetch"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
        except Exception as e:  # python.org macOS builds often lack CA certs -> use system curl
            print(f"  urllib failed ({type(e).__name__}); trying curl")
            try:
                data = subprocess.run(["curl", "-fsSL", "--max-time", str(TIMEOUT), url],
                                      capture_output=True, check=True, timeout=TIMEOUT + 10).stdout
            except Exception as e2:
                sys.exit(f"ERROR: failed to download {name} from {url}: {e2}")
        if not data:
            sys.exit(f"ERROR: empty download for {name}")
        dest.write_bytes(data)


def read_csv(name: str) -> list[dict]:
    with open(RAW / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rec(src_id, label, category, source, text):
    # internal record; label/src_id are dropped before writing
    return {"src_id": src_id, "label": label, "category": category,
            "source": source, "text": " ".join(text.split())}


def assign_ids(rows: list[dict], prefix: str) -> None:
    for i, r in enumerate(sorted(rows, key=lambda r: (r["category"], r["src_id"])), 1):
        r["prompt_id"] = f"{prefix}{i:04d}"


def out_row(r: dict, direction: bool = False) -> dict:
    return {"prompt_id": r["prompt_id"],
            "split": "direction" if direction else r["label"],
            "category": r["label"] if direction else r["category"],
            "source": r["source"], "variant": "en", "text": r["text"]}


def balanced(records: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Round-robin across categories (shuffled within each) until n picked."""
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    for c in by_cat.values():
        rng.shuffle(c)
    cats = sorted(by_cat)
    out = []
    while len(out) < n and any(by_cat.values()):
        for c in cats:
            if by_cat[c] and len(out) < n:
                out.append(by_cat[c].pop())
    return out


def build() -> None:
    rng = random.Random(SEED)

    # --- harmful ---
    hb = [r for r in read_csv("harmbench.csv") if r.get("FunctionalCategory") == "standard"]
    hb_recs = [rec(f"hb_{r['BehaviorID']}", "harmful", r["SemanticCategory"], "harmbench", r["Behavior"])
               for r in hb if r.get("Behavior", "").strip()]
    seen = {r["text"].lower() for r in hb_recs}
    adv_recs = []
    for i, r in enumerate(read_csv("advbench.csv")):
        t = " ".join(r.get("goal", "").split())
        if t and t.lower() not in seen:
            seen.add(t.lower())
            adv_recs.append(rec(f"adv_{i:04d}", "harmful", "advbench_general", "advbench", t))
    rng.shuffle(adv_recs)
    n_adv_eval = max(0, N_FULL_HARMFUL - len(hb_recs))
    full_harmful = hb_recs + adv_recs[:n_adv_eval]
    dir_harmful = adv_recs[n_adv_eval:n_adv_eval + N_DIR]

    # --- harmless ---
    xs = [r for r in read_csv("xstest.csv") if r.get("label", "").strip() == "safe"]
    xs_recs = [rec(f"xs_{int(r['id']):03d}", "harmless", f"xstest_{r['type']}", "xstest", r["prompt"])
               for r in xs if r.get("prompt", "").strip()]
    with open(RAW / "alpaca.json", encoding="utf-8") as f:
        alpaca = json.load(f)
    alp_recs = [rec(f"alp_{i:05d}", "harmless", "general", "alpaca", a["instruction"])
                for i, a in enumerate(alpaca)
                if not a.get("input", "").strip() and 20 <= len(a.get("instruction", "")) <= 200]
    rng.shuffle(alp_recs)
    n_xs = N_FULL_HARMLESS - N_GENERAL_EVAL
    full_harmless = balanced(xs_recs, n_xs, rng) + alp_recs[:N_GENERAL_EVAL]
    dir_harmless = alp_recs[N_GENERAL_EVAL:N_GENERAL_EVAL + N_DIR]

    # --- pilot (subset of full, balanced) ---
    pilot = balanced(full_harmful, N_PILOT, rng) + balanced(full_harmless, N_PILOT, rng)
    full = full_harmful + full_harmless
    direction = dir_harmful + dir_harmless
    assign_ids(full_harmful, "h")
    assign_ids(full_harmless, "s")
    assign_ids(direction, "d")

    # sanity: ids unique, direction disjoint from eval (by source id), pilot within full
    full_src = {r["src_id"] for r in full}
    assert len(full_src) == len(full), "duplicate source ids in full"
    assert not full_src & {r["src_id"] for r in direction}, "direction overlaps eval"
    assert {r["src_id"] for r in pilot} <= full_src

    with open(RAW / "id_map.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["prompt_id", "source", "source_id"])
        for r in sorted(full + direction, key=lambda r: r["prompt_id"]):
            w.writerow([r["prompt_id"], r["source"], r["src_id"]])

    outputs = [("full", full, False), ("pilot", pilot, False), ("direction", direction, True)]
    for name, rows, is_dir in outputs:
        rows = [out_row(r, is_dir) for r in sorted(rows, key=lambda r: r["prompt_id"])]
        paths = [RAW / f"en_{name}.jsonl"] + ([RAW.parent / "direction.jsonl"] if is_dir else [])
        for path in paths:
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        counts = Counter((r["split"], r["category"]) for r in rows)
        print(f"\n{name}: {len(rows)} rows")
        for (sp, cat), n in sorted(counts.items()):
            print(f"  {sp:9s} {cat:40s} {n}")


if __name__ == "__main__":
    download(force="--force" in sys.argv)
    build()
