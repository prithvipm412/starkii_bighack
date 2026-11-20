#!/usr/bin/env python3
"""
Generates dashboard/sample/results_sample.csv and sample sweep files.
⚠️  SAMPLE DATA — not real experimental results.

Schema:
  prompt_id,split,category,variant,model,condition,refused,judge_score,latency_ms,commit,label,harmful_compliance
"""
import csv, random, itertools, os

random.seed(42)

CATEGORIES = [
    "violence", "hate_speech", "self_harm", "illegal_weapons",
    "misinformation", "adult_content", "privacy", "cybercrime",
]
VARIANTS   = ["en", "kn", "kn_latn", "kn_mix"]

MODELS = [
    "qwen2.5-3b-instruct",
    "llama-3.2-3b-instruct",
    "gemma-2-2b-it",
]
GUARD_MODEL = "llama-guard-3-1b"

CONDITIONS = ["none", "baseline", "steer_always", "steer_gated"]
SPLITS     = ["harmful", "harmless"]

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

LAT = {"none": 820, "baseline": 1100, "steer_always": 950, "steer_gated": 1050}
MODEL_LAT = {
    "qwen2.5-3b-instruct":  1.00,
    "llama-3.2-3b-instruct": 1.05,
    "gemma-2-2b-it":          0.90,
    GUARD_MODEL:              0.60,
}

ROWS_PER_COMBO = 20
COMMIT = "a1b2c3d"

def assign_label_and_compliance(split, variant, refused):
    if refused == 1:
        # In Kanglish / code-mix, some refusals are "not understood"
        if variant in ["kn_latn", "kn_mix"] and random.random() < 0.45:
            label = "not_understood"
        else:
            label = "refused"
        harmful_compliance = 0
    else:
        label = "complied"
        harmful_compliance = 1 if split == "harmful" else 0
    return label, harmful_compliance

rows = []
pid = 1

for split, cat, var, mdl, cond in itertools.product(
        SPLITS, CATEGORIES, VARIANTS, MODELS, CONDITIONS):
    base_ref = HARM_REF[cond][var] if split == "harmful" else SAFE_REF[cond][var]
    base_lat = LAT[cond] * MODEL_LAT[mdl]
    for _ in range(ROWS_PER_COMBO):
        refused     = 1 if random.random() < base_ref else 0
        judge_score = round(max(0.0, min(1.0, random.gauss(base_ref, 0.15))), 4)
        latency     = max(200, int(random.gauss(base_lat, base_lat * 0.15)))
        lbl, comp   = assign_label_and_compliance(split, var, refused)
        rows.append([f"P{pid:05d}", split, cat, var, mdl, cond,
                     refused, judge_score, latency, COMMIT, lbl, comp])
        pid += 1

# Llama Guard rows for baseline
for split, cat, var in itertools.product(SPLITS, CATEGORIES, VARIANTS):
    base_ref = HARM_REF["baseline"][var] if split == "harmful" else SAFE_REF["baseline"][var]
    base_lat = LAT["baseline"] * MODEL_LAT[GUARD_MODEL]
    for _ in range(ROWS_PER_COMBO):
        refused     = 1 if random.random() < base_ref else 0
        judge_score = round(max(0.0, min(1.0, random.gauss(base_ref, 0.15))), 4)
        latency     = max(100, int(random.gauss(base_lat, base_lat * 0.15)))
        lbl, comp   = assign_label_and_compliance(split, var, refused)
        rows.append([f"P{pid:05d}", split, cat, var, GUARD_MODEL, "baseline",
                     refused, judge_score, latency, COMMIT, lbl, comp])
        pid += 1

sample_dir = os.path.dirname(__file__)
out = os.path.join(sample_dir, "results_sample.csv")
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["prompt_id", "split", "category", "variant", "model",
                "condition", "refused", "judge_score", "latency_ms", "commit",
                "label", "harmful_compliance"])
    w.writerows(rows)

print(f"Wrote {len(rows)} rows → {out}")

# Generate sample sweep files
sweep_configs = [
    # (model, alpha, tau, harmful_kn_target, harmless_wrong_target)
    ("qwen2.5-3b-instruct", 10.0, 5.0, 0.55, 0.03),
    ("qwen2.5-3b-instruct", 20.0, 10.0, 0.72, 0.06),
    ("qwen2.5-3b-instruct", 35.4, 15.9, 0.85, 0.10),
    ("qwen2.5-3b-instruct", 50.0, 20.0, 0.94, 0.22),
    ("gemma-2-2b-it", 50.0, -20.0, 0.58, 0.04),
    ("gemma-2-2b-it", 100.0, -16.0, 0.75, 0.07),
    ("gemma-2-2b-it", 176.0, -13.6, 0.87, 0.12),
    ("gemma-2-2b-it", 220.0, -10.0, 0.95, 0.25),
]

for mdl, alpha, tau, harm_kn_p, safe_p in sweep_configs:
    sw_rows = []
    sw_pid = 1
    fname = f"sweep_{mdl}_steer_gated_a{alpha}_t{tau}.csv"
    fpath = os.path.join(sample_dir, fname)
    for split, var in itertools.product(SPLITS, VARIANTS):
        if split == "harmful":
            p = 0.92 if var == "en" else harm_kn_p
        else:
            p = safe_p
        for _ in range(25):
            refused = 1 if random.random() < p else 0
            lbl, comp = assign_label_and_compliance(split, var, refused)
            sw_rows.append([f"SP{sw_pid:04d}", split, "general", var, mdl, "steer_gated",
                            refused, round(p, 2), 900, "sw1234", lbl, comp])
            sw_pid += 1
    with open(fpath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["prompt_id", "split", "category", "variant", "model",
                    "condition", "refused", "judge_score", "latency_ms", "commit",
                    "label", "harmful_compliance"])
        w.writerows(sw_rows)
    print(f"Generated sample sweep file: {fname}")
