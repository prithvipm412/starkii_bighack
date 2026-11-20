#!/usr/bin/env python3
"""
Generates dashboard/sample/results_sample.csv
⚠️  SAMPLE DATA — not real experimental results.
Schema: prompt_id,split,category,variant,model,condition,refused,judge_score,latency_ms,commit

Real models (from AGENTS.md):
  mac1: Qwen/Qwen2.5-3B-Instruct
  mac2: meta-llama/Llama-3.2-3B-Instruct
  mac3: google/gemma-2-2b-it
  mac4 baseline judge: meta-llama/Llama-Guard-3-1B  (condition=baseline only)

Categories come from the prompt schema — listed here for sample generation only;
the dashboard reads them dynamically from whatever CSVs are loaded.
"""
import csv, random, itertools

random.seed(42)

CATEGORIES = [
    "violence", "hate_speech", "self_harm", "illegal_weapons",
    "misinformation", "adult_content", "privacy", "cybercrime",
]
VARIANTS   = ["en", "kn", "kn_latn", "kn_mix"]
# Real model IDs — match AGENTS.md exactly
MODELS     = [
    "Qwen/Qwen2.5-3B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "google/gemma-2-2b-it",
]
# mac4 Llama Guard only appears in the baseline condition
GUARD_MODEL = "meta-llama/Llama-Guard-3-1B"
CONDITIONS  = ["none", "baseline", "steer_always", "steer_gated"]
SPLITS      = ["harmful", "harmless"]

# Base refusal rates: harmful/harmless × condition × variant
# Tells the story: en has the highest refusal; kn/kn_latn/kn_mix lower → "the gap"
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
# Latency ms per condition (guard adds overhead on baseline)
LAT = {"none": 820, "baseline": 1100, "steer_always": 950, "steer_gated": 1050}
# Small model multiplier (all similar size ~2-3B, slight spread)
MODEL_LAT = {
    "Qwen/Qwen2.5-3B-Instruct":       1.00,
    "meta-llama/Llama-3.2-3B-Instruct": 1.05,
    "google/gemma-2-2b-it":            0.90,
    GUARD_MODEL:                        0.60,  # 1B, only classifies
}

ROWS_PER_COMBO = 20   # prompts per (split, category, variant, model, condition)
COMMIT = "a1b2c3d"

rows = []
pid = 1

for split, cat, var, mdl, cond in itertools.product(SPLITS, CATEGORIES, VARIANTS, MODELS, CONDITIONS):
    base_ref = HARM_REF[cond][var] if split == "harmful" else SAFE_REF[cond][var]
    base_lat = LAT[cond] * MODEL_LAT[mdl]
    for _ in range(ROWS_PER_COMBO):
        refused     = 1 if random.random() < base_ref else 0
        judge_score = round(max(0, min(5, random.gauss(base_ref * 5, 0.6))), 2)
        latency     = max(200, int(random.gauss(base_lat, base_lat * 0.15)))
        rows.append([f"P{pid:05d}", split, cat, var, mdl, cond,
                     refused, judge_score, latency, COMMIT])
        pid += 1

# Llama Guard rows exist only for condition=baseline (mac4 baseline pipeline)
for split, cat, var in itertools.product(SPLITS, CATEGORIES, VARIANTS):
    base_ref = HARM_REF["baseline"][var] if split == "harmful" else SAFE_REF["baseline"][var]
    base_lat = LAT["baseline"] * MODEL_LAT[GUARD_MODEL]
    for _ in range(ROWS_PER_COMBO):
        refused     = 1 if random.random() < base_ref else 0
        judge_score = round(max(0, min(5, random.gauss(base_ref * 5, 0.6))), 2)
        latency     = max(100, int(random.gauss(base_lat, base_lat * 0.15)))
        rows.append([f"P{pid:05d}", split, cat, var, GUARD_MODEL, "baseline",
                     refused, judge_score, latency, COMMIT])
        pid += 1

out = "dashboard/sample/results_sample.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["prompt_id","split","category","variant","model","condition",
                "refused","judge_score","latency_ms","commit"])
    w.writerows(rows)
print(f"Wrote {len(rows)} rows → {out}")
