#!/usr/bin/env python3
"""
Generates dashboard/sample/results_sample.csv
⚠️  SAMPLE DATA — not real experimental results.

Schema (must match AGENTS.md exactly):
  prompt_id,split,category,variant,model,condition,refused,judge_score,latency_ms,commit

Models (short names, matching the model column written by the pipeline):
  qwen2.5-3b-instruct          — mac1
  llama-3.2-3b-instruct        — mac2
  gemma-2-2b-it                — mac3
  llama-guard-3-1b             — mac4, baseline condition only

Conditions: none | baseline | steer_always | steer_gated
Splits:     harmful | harmless
Variants:   en | kn | kn_latn | kn_mix

Categories are read from the data at runtime in the dashboard; they are listed
here only to generate the sample. No category names are hard-coded in index.html.
"""
import csv, random, itertools

random.seed(42)

CATEGORIES = [
    "violence", "hate_speech", "self_harm", "illegal_weapons",
    "misinformation", "adult_content", "privacy", "cybercrime",
]
VARIANTS   = ["en", "kn", "kn_latn", "kn_mix"]

# Short model IDs (no org prefix)
MODELS = [
    "qwen2.5-3b-instruct",
    "llama-3.2-3b-instruct",
    "gemma-2-2b-it",
]
GUARD_MODEL = "llama-guard-3-1b"   # baseline-only judge (mac4)

CONDITIONS = ["none", "baseline", "steer_always", "steer_gated"]
SPLITS     = ["harmful", "harmless"]

# Base refusal rates: harmful/harmless × condition × variant
# Story: en has the highest refusal; kn/kn_latn/kn_mix lower → "the gap"
# steer_gated closes most of the gap without over-refusing harmless
HARM_REF = {
    "none":        {"en": 0.88, "kn": 0.52, "kn_latn": 0.49, "kn_mix": 0.44},
    "baseline":    {"en": 0.91, "kn": 0.68, "kn_latn": 0.65, "kn_mix": 0.60},
    "steer_always":{"en": 0.95, "kn": 0.87, "kn_latn": 0.84, "kn_mix": 0.81},
    "steer_gated": {"en": 0.94, "kn": 0.85, "kn_latn": 0.83, "kn_mix": 0.80},
}
SAFE_REF = {
    "none":        {"en": 0.04, "kn": 0.06, "kn_latn": 0.07, "kn_mix": 0.08},
    "baseline":    {"en": 0.07, "kn": 0.09, "kn_latn": 0.10, "kn_mix": 0.11},
    "steer_always":{"en": 0.22, "kn": 0.26, "kn_latn": 0.28, "kn_mix": 0.30},
    "steer_gated": {"en": 0.08, "kn": 0.10, "kn_latn": 0.11, "kn_mix": 0.12},
}
# Base latency ms per condition
LAT = {"none": 820, "baseline": 1100, "steer_always": 950, "steer_gated": 1050}
# Small relative spread per model
MODEL_LAT = {
    "qwen2.5-3b-instruct":  1.00,
    "llama-3.2-3b-instruct": 1.05,
    "gemma-2-2b-it":          0.90,
    GUARD_MODEL:              0.60,  # 1B classifier only
}

ROWS_PER_COMBO = 20   # rows per (split, category, variant, model, condition)
COMMIT = "a1b2c3d"

rows = []
pid = 1

# Main 3 models × all conditions
for split, cat, var, mdl, cond in itertools.product(
        SPLITS, CATEGORIES, VARIANTS, MODELS, CONDITIONS):
    base_ref = HARM_REF[cond][var] if split == "harmful" else SAFE_REF[cond][var]
    base_lat = LAT[cond] * MODEL_LAT[mdl]
    for _ in range(ROWS_PER_COMBO):
        refused     = 1 if random.random() < base_ref else 0
        judge_score = round(max(0.0, min(5.0, random.gauss(base_ref * 5, 0.6))), 2)
        latency     = max(200, int(random.gauss(base_lat, base_lat * 0.15)))
        rows.append([f"P{pid:05d}", split, cat, var, mdl, cond,
                     refused, judge_score, latency, COMMIT])
        pid += 1

# llama-guard-3-1b: appears only in condition=baseline (mac4 baseline pipeline)
for split, cat, var in itertools.product(SPLITS, CATEGORIES, VARIANTS):
    base_ref = HARM_REF["baseline"][var] if split == "harmful" else SAFE_REF["baseline"][var]
    base_lat = LAT["baseline"] * MODEL_LAT[GUARD_MODEL]
    for _ in range(ROWS_PER_COMBO):
        refused     = 1 if random.random() < base_ref else 0
        judge_score = round(max(0.0, min(5.0, random.gauss(base_ref * 5, 0.6))), 2)
        latency     = max(100, int(random.gauss(base_lat, base_lat * 0.15)))
        rows.append([f"P{pid:05d}", split, cat, var, GUARD_MODEL, "baseline",
                     refused, judge_score, latency, COMMIT])
        pid += 1

out = "dashboard/sample/results_sample.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["prompt_id", "split", "category", "variant", "model",
                "condition", "refused", "judge_score", "latency_ms", "commit"])
    w.writerows(rows)

# Quick sanity
models_found = sorted({r[4] for r in rows})
print(f"Wrote {len(rows)} rows → {out}")
print(f"Models in CSV: {models_found}")
