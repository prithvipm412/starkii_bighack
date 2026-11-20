# FINDINGS (draft, pilot): numbers only

Source: `analysis/summary.csv` (made by `python -m analysis.summarize`), gate projections from `results/mac*/gate/`, and direction stats from `results/mac*/*_direction.json`.
Percentages are refusal rates with 95% Wilson CIs. Each cell has n = 50, and every row is unique by (prompt_id, variant).
`refused` is a refusal-phrase match. It also fires on "I don't understand / please clarify" replies (see Failure analysis).

## Hypothesis
Small open models refuse harmful requests less often in Kannada script (kn), Kanglish (kn_latn) and Kannada-English code-mix (kn_mix) than in English (en). Steering along the model's own English refusal direction at a middle layer closes that gap, if it is applied only when the input is non-English and already weakly activates the direction (steer_gated). The cost should be a small rise in wrong refusals of harmless prompts.

## Data & translation
- **Evaluation set:** 450 English prompts.
  - 300 harmful: 200 HarmBench standard behaviours (6 semantic categories) + 100 AdvBench.
  - 150 harmless: 130 XSTest safe prompts (13 from each of 10 types) + 20 Alpaca general prompts.
- **Variants:** each prompt comes in 4 versions sharing one prompt_id, for 1800 rows: en, kn, kn_latn (ITRANS transliteration of kn), kn_mix (technical terms kept in English).
- **Pilot:** 100 prompts (50 harmful + 50 harmless, category-balanced) × 4 = 400 rows. The pilot is a subset of the full set.
- **Direction set:** 64 AdvBench + 64 Alpaca English prompts, separate from the evaluation set and never evaluated.
- **Translation:** Google Translate (en→kn) for the whole study. IndicTrans2 could not be downloaded in time (~118 KB/s).
- **Pipeline scorer:** mac1 translates replies with NLLB-200-distilled-600M, because IndicTrans2 is gated.

## Finding 1: the refusal gap per model (condition none)
| model | harmful en | harmful kn | harmful kn_latn | harmful kn_mix | harmless en | harmless kn | harmless kn_latn | harmless kn_mix |
|---|---|---|---|---|---|---|---|---|
| Qwen2.5-3B-Instruct | 90.0 [78.6–95.7] | 8.0 [3.2–18.8] | 32.0 [20.8–45.8] | 22.0 [12.8–35.2] | 24.0 [14.3–37.4] | 14.0 [7.0–26.2] | 84.0 [71.5–91.7] | 68.0 [54.2–79.2] |
| gemma-2-2b-it | 100.0 [92.9–100] | 48.0 [34.8–61.5] | 6.0 [2.1–16.2] | 56.0 [42.3–68.8] | 14.0 [7.0–26.2] | 4.0 [1.1–13.5] | 36.0 [24.1–49.9] | 18.0 [9.8–30.8] |
| Llama-3.2-3B-Instruct | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

- **Qwen, harmful refusal en → kn:** 90 → 8 (−82 pts). Excluding "don't understand" replies (mac1 local check), kn_latn is 0% and kn_mix 16%.
- **Gemma, harmful refusal:** en 100 → kn 48 (−52), kn_latn 6 (−94), kn_mix 56 (−44).
- **The CIs for en and kn don't overlap** in either model.

## Finding 2: Llama Guard baseline gap (translate → Llama Guard 3 1B)
| variant | harmful flagged | harmless flagged | median latency ms |
|---|---|---|---|
| en | 98.0 [89.5–99.6] | 12.0 [5.6–23.8] | 177 |
| kn_latn (untranslated) | 42.0 [29.4–55.8] | 2.0 [0.4–10.5] | 113 |
| kn (Google kn→en) | PENDING | PENDING | PENDING |
| kn_mix (Google kn→en) | PENDING | PENDING | PENDING |

- **Harmful detection on Kanglish:** 98 → 42 (−56 pts). IndicTrans2 and Google take Kannada script only, so the guard sees raw Roman-script Kanglish.
- **Pending rows:** kn and kn_mix are blocked because Google kn→en returns HTTP 429. A local translator is needed.

## Mechanism: refusal-direction projections, EN vs KN (condition none, mean over 50 prompts)
| model (layer, tau) | harmful en | harmful kn | harmful kn_latn | harmful kn_mix | harmless en | harmless kn | harmless kn_latn | harmless kn_mix |
|---|---|---|---|---|---|---|---|---|
| Qwen (L23/36, tau 15.9) | 39.4 | 17.7 | 17.2 | 18.3 | 19.8 | 15.8 | 15.6 | 17.5 |
| Gemma (L16/26, tau −13.6) | 99.7 | 25.7 | 0.6 | 35.6 | −13.6 | −11.8 | −2.1 | −6.6 |

- **Direction-set stats at the chosen layer:**
  - Qwen: harmful 46.0 vs harmless 10.7, separation (Cohen's d) 7.55, alpha 35.4.
  - Gemma: harmful 125.3 vs harmless −50.7, separation 7.61, alpha 176.1.
- **Harmful Kannada prompts project much lower than harmful English ones:**
  - Qwen: 17–18 vs 39.4, about 45% of the English value.
  - Gemma: 0.6–35.6 vs 99.7.
  - So the refusal feature is only weakly activated in Kannada.
- **Harmful and harmless Kannada projections sit close together:** Qwen kn 17.7 vs 15.8; Gemma kn_mix 35.6 vs −6.6. This limits how well the gate can separate them.

## Fix: gated vs always steering
**Harmful refusal %:**
| model | condition | en | kn | kn_latn | kn_mix |
|---|---|---|---|---|---|
| Qwen | none | 90.0 | 8.0 | 32.0 | 22.0 |
| Qwen | steer_gated | 90.0 | 66.0 [52.2–77.6] | 86.0 [73.8–93.0] | 74.0 [60.4–84.1] |
| Qwen | steer_always | 100.0 | 88.0 | 100.0 | 100.0 |
| Gemma | none | 100.0 | 48.0 | 6.0 | 56.0 |
| Gemma | steer_gated | 100.0 | 82.0 [69.2–90.2] | 96.0 [86.5–98.9] | 88.0 [76.2–94.4] |
| Gemma | steer_always | 100.0 | 96.0 | 100.0 | 100.0 |

**Harmless wrong-refusal %:**
| model | condition | en | kn | kn_latn | kn_mix |
|---|---|---|---|---|---|
| Qwen | none | 24.0 | 14.0 | 84.0 | 68.0 |
| Qwen | steer_gated | 24.0 | 44.0 | 88.0 | 84.0 |
| Qwen | steer_always | 100.0 | 92.0 | 100.0 | 100.0 |
| Gemma | none | 14.0 | 4.0 | 36.0 | 18.0 |
| Gemma | steer_gated | 14.0 | 48.0 | 92.0 | 58.0 |
| Gemma | steer_always | 100.0 | 96.0 | 100.0 | 100.0 |

- **steer_gated, harmful refusal gain over none:**
  - Qwen: kn +58, kn_latn +54, kn_mix +52 pts.
  - Gemma: kn +34, kn_latn +90, kn_mix +32 pts.
  - English is unchanged, because the gate never fires on en.
- **steer_always** pushes English harmless refusals to 100% in both models (24 → 100 and 14 → 100). It is unusable at this alpha.
- **Median latency per prompt (ms):**
  - Qwen: none 644, gated 668 (+24), always 786.
  - Gemma: none 528, gated 530 (+2), always 622.
  - Llama Guard baseline: 177 for en (translation excluded).
- **Gate firing (steered/50):**
  - Qwen: harmful kn 36, kn_latn 42, kn_mix 37; harmless kn 22, kn_latn 13, kn_mix 38.
  - Gemma: harmful kn 43, kn_latn 48, kn_mix 44; harmless kn 24, kn_latn 42, kn_mix 29.

## Failure analysis
- **Harmless over-refusal under gating.** Wrong refusals rise on Kannada harmless prompts:
  - Qwen: kn +30, kn_latn +4, kn_mix +16 pts.
  - Gemma: kn +44, kn_latn +56, kn_mix +40 pts.
  - The gate fires on 13–38 of 50 harmless Kannada-variant prompts for Qwen and 24–42 for Gemma, because harmless and harmful Kannada projections overlap (see Mechanism).
- **Kanglish not_understood confound.** The raw `refused` flag counts "don't understand / clarify" replies as refusals. Qwen, none, per mac1's local check (raw → excl.):
  - harmful kn_latn 32 → 0
  - harmless kn_latn 84 → 34
  - harmless kn_mix 68 → 16
  - So raw kn_latn and kn_mix refusal rates overstate real refusals. Human-checked scorer accuracy per variant: PENDING (`analysis/scorer_check.csv`, waiting on handlabels).
- **Translation noise.** Prompts are machine-translated (Google), and kn_latn is a mechanical ITRANS transliteration, not natural Kanglish. Human meaning check of 20 translations: PENDING. The guard sees Kanglish untranslated.
- **Small n.** n = 50 per cell, so CIs are ±10–14 pts at mid-range rates. Differences under ~20 pts are not reliable. Only the pilot has been run; the full set (300 harmful + 150 harmless per variant) is PENDING.
- **Llama Guard by category / variant:** PENDING (full run).

## Next steps
1. Llama Guard baseline for kn and kn_mix with a local kn→en translator, then the full-set baseline.
2. Full runs (450 prompts × 4 variants) for all models, plus Llama-3.2-3B-Instruct (mac2).
3. Sweeps of layer × alpha × tau for steer_gated, aiming to cut harmless kn and kn_mix over-refusal; mac1 notes separation keeps rising after layer 23.
4. Hand labels from mac1–3, then `scorer_check.csv`. Report excl.-not_understood rates for every model.
5. Failure breakdown per HarmBench category under each condition.
