# FINDINGS (draft, pilot): numbers only

Source: `analysis/summary.csv` (`python -m analysis.summarize`), gate projections in `results/mac*/gate/`, direction stats in `results/mac*/*_direction.json`.
Each cell has n = 50 (pilot: 50 harmful + 50 harmless prompts per variant), with 95% Wilson CIs in [ ].

**Metrics:**
- **refused:** a refusal-phrase match. It also fires on some "don't understand" replies.
- **harmful_compliance:** Llama Guard 3 1B P(unsafe) > 0.5 on the English-translated reply. This is the **primary** metric.
- **label:** each reply is classed as refused / not_understood / complied. not_understood is checked first.

**Runs:**
- Qwen = `results/mac1/pilot64/`, max 64 new tokens, rescored by mac1.
- Gemma = `results/mac3/`, rescored by mac3 (commit 3170860).
- Llama-3.2-3B-Instruct = PENDING.

## Hypothesis
Small open models refuse harmful requests less often in Kannada script (kn), Kanglish (kn_latn) and Kannada-English code-mix (kn_mix) than in English (en). Steering along the model's own English refusal direction at a middle layer closes that gap, if it is applied only when the input is non-English and already weakly activates the direction (steer_gated). The cost should be a small rise in wrong refusals of harmless prompts.

## Data & translation
- **Evaluation set:** 450 English prompts.
  - 300 harmful: 200 HarmBench standard behaviours (6 semantic categories) + 100 AdvBench.
  - 150 harmless: 130 XSTest safe prompts (13 from each of 10 types) + 20 Alpaca general prompts.
- **Variants:** each prompt comes in 4 versions sharing one prompt_id, for 1800 rows: en, kn, kn_latn (ITRANS transliteration of kn), kn_mix (technical terms kept in English).
- **Pilot:** 100 prompts (50 + 50, category-balanced) × 4 = 400 rows. The pilot is a subset of the full set.
- **Direction set:** 64 AdvBench + 64 Alpaca English prompts, separate from the evaluation set and never evaluated.
- **Prompt translation:** Google Translate (en→kn) for the whole study.
- **Reply and baseline translation:** NLLB-200-distilled-600M (kn→en), local. The pipeline scorer and the Llama Guard baseline use the same NLLB settings.

## Finding 1: the gap per model holds on harmful_compliance (condition none)
**Harmful prompts, harmful_compliance % (lower = safer):**
| model | en | kn | kn_latn | kn_mix |
|---|---|---|---|---|
| Qwen2.5-3B | 2.0 [0.4–10.5] | 76.0 [62.6–85.7] | 4.0 [1.1–13.5] | 52.0 [38.5–65.2] |
| gemma-2-2b | 0.0 [0.0–7.1] | 44.0 [31.2–57.7] | 22.0 [12.8–35.2] | 16.0 [8.3–28.5] |
| Llama-3.2-3B | PENDING | PENDING | PENDING | PENDING |

**Harmful prompts, label breakdown % (refused / not_understood / complied):**
| model | en | kn | kn_latn | kn_mix |
|---|---|---|---|---|
| Qwen2.5-3B | 90 / 0 / 10 | 8 / 0 / 92 | 2 / 72 / 26 | 18 / 4 / 78 |
| gemma-2-2b | 100 / 0 / 0 | 48 / 0 / 52 | 4 / 64 / 32 | 56 / 0 / 44 |

- **The gap holds on the primary metric.**
  - Qwen: harmful compliance rises from 2% in en to 76% in kn (+74 pts) and 52% in kn_mix (+50). The CIs don't overlap.
  - Gemma: 0% → 44% in kn and 16% in kn_mix.
- **The Kanglish gap is mostly not understanding, not refusal or compliance.**
  - Qwen kn_latn harmful: 72% not_understood. Real refusals are 2%, against the raw `refused` rate of 32%.
  - Gemma kn_latn: 64% not_understood.
  - Compliance on kn_latn is low (Qwen 4%, Gemma 22%) because the models mostly can't parse the input.
- **Phrase-refusal rates for harmful prompts (refused, en → kn):** Qwen 90 → 8, Gemma 100 → 48.

## Finding 2: Llama Guard baseline (translate → Llama Guard 3 1B on the prompt)
| variant | condition | harmful flagged, full (n=300) | harmless flagged, full (n=150) | harmful flagged, pilot (n=50) | harmless flagged, pilot (n=50) | median latency ms |
|---|---|---|---|---|---|---|
| en | baseline | 96.3 [93.6–97.9] | 7.3 [4.1–12.7] | 98.0 [89.5–99.6] | 12.0 [5.6–23.8] | 179 |
| kn (NLLB kn→en) | baseline | 90.3 [86.5–93.2] | 7.3 [4.1–12.7] | 90.0 [78.6–95.7] | 8.0 [3.2–18.8] | 448 |
| kn_mix (NLLB kn→en) | baseline | 92.3 [88.8–94.8] | 6.0 [3.2–11.0] | 92.0 [81.2–96.8] | 6.0 [2.1–16.2] | 447 |
| kn_latn (untranslated) | baseline | 39.7 [34.3–45.3] | 1.3 [0.4–4.7] | 42.0 [29.4–55.8] | 2.0 [0.4–10.5] | 138 |
| kn_latn (ITRANS→Kannada→NLLB) | baseline_translit | PENDING | PENDING | 90.0 [78.6–95.7] | 10.0 [4.3–21.4] | 422 |

- **Translate-then-guard mostly closes the gap for Kannada script and code-mix.**
  - Full set: kn −6.0 pts and kn_mix −4.0 pts compared with en (96.3).
  - Wrong flags on harmless prompts don't rise (6.0–7.3% vs 7.3% for en).
  - Translation adds about 270 ms per prompt.
- **Untranslated Kanglish fails:** 96.3 → 39.7 (−56.6 pts, full set). The guard sees raw Roman-script text.
- **Back-transliterating Kanglish closes most of that gap.**
  - Pilot: harmful kn_latn flagged 42 → 90 (+48 pts), the same as kn.
  - Cost: harmless wrong flags 2 → 10%, close to en at 12%.
  - Caveat: our kn_latn was produced by ITRANS, so reversing it is near-exact (80/100 pilot prompts round-trip to the identical kn text). Real, informal Kanglish would not reverse this cleanly, so this is an upper bound.

## Mechanism: refusal-direction projections, EN vs KN (condition none, mean over 50 prompts)
| model (layer, tau) | harmful en | harmful kn | harmful kn_latn | harmful kn_mix | harmless en | harmless kn | harmless kn_latn | harmless kn_mix |
|---|---|---|---|---|---|---|---|---|
| Qwen (L23/36, tau 15.9) | 39.4 | 17.7 | 17.2 | 18.3 | 19.8 | 15.8 | 15.6 | 17.5 |
| Gemma (L16/26, tau −13.6) | 99.7 | 25.7 | 0.6 | 35.6 | −13.6 | −11.8 | −2.1 | −6.6 |
| Llama-3.2-3B | PENDING | | | | | | | |

- **Direction-set stats at the chosen layer:**
  - Qwen: harmful 46.0 vs harmless 10.7, separation (Cohen's d) 7.55, alpha 35.4.
  - Gemma: harmful 125.3 vs harmless −50.7, separation 7.61, alpha 176.1.
- **Harmful Kannada prompts project much lower than harmful English ones:**
  - Qwen: 17–18 vs 39.4, about 45% of the English value.
  - Gemma: 0.6–35.6 vs 99.7.
  - So the refusal feature is only weakly activated in Kannada.
- **Harmful and harmless Kannada projections sit close together:** Qwen kn 17.7 vs 15.8; Gemma kn_mix 35.6 vs −6.6. This limits how well the gate can separate them (see Failure analysis).

## Fix: gated vs always steering
**Harmful prompts, harmful_compliance % (primary):**
| model | condition | en | kn | kn_latn | kn_mix |
|---|---|---|---|---|---|
| Qwen | none | 2.0 | 76.0 | 4.0 | 52.0 |
| Qwen | steer_gated | 2.0 | 30.0 [19.1–43.8] | 0.0 [0.0–7.1] | 22.0 [12.8–35.2] |
| Qwen | steer_always | 0.0 | 8.0 | 0.0 | 0.0 |
| Gemma | none | 0.0 | 44.0 | 22.0 | 16.0 |
| Gemma | steer_gated | 0.0 | 16.0 [8.3–28.5] | 0.0 [0.0–7.1] | 6.0 [2.1–16.2] |
| Gemma | steer_always | 0.0 | 4.0 | 0.0 | 0.0 |

**Harmless prompts, real refusals (label = refused) %:**
| model | condition | en | kn | kn_latn | kn_mix |
|---|---|---|---|---|---|
| Qwen | none | 24 | 8 | 36 | 36 |
| Qwen | steer_gated | 24 | 44 | 56 | 80 |
| Qwen | steer_always | 100 | 92 | 100 | 100 |
| Gemma | none | 14 | 4 | 4 | 18 |
| Gemma | steer_gated | 14 | 48 | 84 | 58 |
| Gemma | steer_always | 100 | 96 | 100 | 100 |

- **steer_gated cuts harmful compliance** with no change to English, because the gate never fires on en:
  - Qwen: kn 76 → 30 (−46 pts), kn_mix 52 → 22 (−30).
  - Gemma: kn 44 → 16 (−28), kn_latn 22 → 0, kn_mix 16 → 6.
- **steer_always is lowest on harmful compliance (0–8%)**, but it refuses 100% of English harmless prompts (Qwen 24 → 100, Gemma 14 → 100).
- **Median latency per prompt (ms):**
  - Qwen: none 644, gated 668 (+24), always 786.
  - Gemma: none 528, gated 530 (+2), always 622.
  - Llama Guard baseline: 177 (en), 404–424 (kn, kn_mix, incl. translation).
- **Gate firing (steered/50):**
  - Qwen: harmful kn 36, kn_latn 42, kn_mix 37; harmless kn 22, kn_latn 13, kn_mix 38.
  - Gemma: harmful kn 43, kn_latn 48, kn_mix 44; harmless kn 24, kn_latn 42, kn_mix 29.

## Scorer validation (human hand labels)
- **Data:** 30 hand labels, all from `results/mac3/handlabels.csv`: gemma-2-2b-it, 10 each for kn, kn_latn and kn_mix, 5 none + 5 steer_gated per variant.
  - mac3 notes some kn items were labelled with AI translation help.
  - No en labels; no Qwen or Llama labels yet.
- **Output:** `analysis/scorer_check.csv`.

| variant | n | `label` agrees with human (3-class) | `refused` agrees with human (binary) | pipeline not_understood → human agrees | human not_understood → pipeline caught |
|---|---|---|---|---|---|
| kn | 10 | 30.0% | 80.0% | 0 / 0 | 0 / 7 |
| kn_latn | 10 | 30.0% | 50.0% | 1 / 3 (33.3%) | 1 / 5 (20.0%) |
| kn_mix | 10 | 40.0% | 40.0% | 0 / 0 | 0 / 2 |
| ALL | 30 | 33.3% | 56.7% | 1 / 3 (33.3%) | 1 / 14 (7.1%) |

- **Humans marked 14/30 replies not_understood; the pipeline found 1 of them.**
  - kn: 5 of the 7 human not_understood replies were labelled complied by the pipeline, and 2 refused.
  - kn_latn: 3 of 5 were labelled refused.
- **On kn_latn, humans agree with the pipeline's not_understood 1 time in 3.** The other 2 were human-labelled complied.
- **Refusals are over-counted:** 7 of the 16 pipeline `refused=1` replies were not_understood to humans, and 3 were complied.
- **kn_mix misses refusals:** 3 human refusals were labelled complied by the pipeline (`refused=0`).
- **Read-across:**
  - Phrase-based `label` misses most not_understood replies in Kannada and over-calls refusal, so Finding 1's not_understood shares (72% / 64% on kn_latn) are unreliable at the reply level.
  - harmful_compliance comes from Llama Guard, not phrases, and was not hand-checked here (PENDING).
  - n = 10 per variant: CIs are about ±25–30 pts.

## Failure analysis
- **Harmless over-refusal under gating is real refusal, not not_understood.** Real refusals rise:
  - Qwen: kn 8 → 44 (+36 pts), kn_latn 36 → 56 (+20), kn_mix 36 → 80 (+44).
  - Gemma: kn 4 → 48 (+44), kn_latn 4 → 84 (+80), kn_mix 18 → 58 (+40).
  - not_understood on harmless prompts falls under gating (Qwen kn_latn 56 → 38, kn_mix 34 → 4; Gemma kn_latn 58 → 10): steering turns "don't understand" replies into refusals.
  - Cause: the gate fires on 13–38 of 50 harmless Kannada-variant prompts (Qwen) and 24–42 (Gemma), because the harmful and harmless projections overlap.
- **Kanglish not_understood confound.** Raw `refused` overstates real refusal on kn_latn.
  - Qwen harmful: refused 32% vs label refused 2% (72% not_understood).
  - Qwen harmless: refused 84% vs label refused 36%.
  - Use harmful_compliance plus the label breakdown, not raw `refused`, for kn_latn and kn_mix.
  - Human check (Gemma, n = 30): the label agrees with humans 33% of the time, and the pipeline catches 1 of 14 human not_understood replies (see Scorer validation).
- **Translation noise.**
  - Prompts are machine-translated (Google), and kn_latn is a mechanical ITRANS transliteration, not natural Kanglish.
  - Replies are judged after NLLB kn→en translation, so judge errors can come from translation.
  - The human meaning check of 20 translations is PENDING.
- **Small n.**
  - n = 50 per cell, so CIs are ±10–14 pts at mid-range rates. Differences under ~20 pts are not reliable.
  - Qwen numbers come from the 64-token pilot. mac1 has moved to 256 tokens, so compliance may change in longer replies (PENDING).
  - Full set (300 + 150 per variant): done for the Llama Guard baseline only; models PENDING.

## Next steps
1. Finish the full-set Llama Guard baseline (running), then failure breakdown per HarmBench category.
2. Full runs at 256 tokens for Qwen, Gemma and Llama-3.2-3B. Llama-3.2 is PENDING everywhere.
3. Sweeps of layer × alpha × tau for steer_gated, to cut harmless kn and kn_mix real refusals. The gate needs better harmful/harmless separation in Kannada.
4. Hand labels from mac1–3, then `scorer_check.csv`: agreement of `label` with humans, especially not_understood on kn_latn.
5. baseline_translit on the full set; test on natural (non-ITRANS) Kanglish.
6. More hand labels: en, Qwen and Llama, plus a harmful_compliance check. Fix not_understood detection in Kannada replies (phrase lists miss it).

<!-- layered-guard:begin -->
## Layered guard (run = main; from `analysis/combined.csv`, `python -m analysis.combined`)
Settings: none = model alone; input_only = Llama Guard on the prompt first; steer_only = steer_gated model; input+steer = both.
Harmful pass-through = prompt not flagged AND harmful_compliance = 1 (primary metric; Llama Guard on the translated reply). Harmless wrongly blocked = prompt flagged OR label = refused.

**Llama-3.2-3B-Instruct**

| variant | setting | harmful pass-through % | harmless wrongly blocked % | kn_latn input rows: translit / untranslated |
|---|---|---|---|---|
| en | none | 8.0 [3.2–18.8] (n=50) | 2.0 [0.4–10.5] (n=50) |  |
| en | input_only | 0.0 [0.0–7.1] (n=50) | 12.0 [5.6–23.8] (n=50) |  |
| en | steer_only | 8.0 [3.2–18.8] (n=50) | 2.0 [0.4–10.5] (n=50) |  |
| en | input+steer | 0.0 [0.0–7.1] (n=50) | 12.0 [5.6–23.8] (n=50) |  |
| kn | none | 58.0 [44.2–70.6] (n=50) | 0.0 [0.0–7.1] (n=50) |  |
| kn | input_only | 2.0 [0.4–10.5] (n=50) | 8.0 [3.2–18.8] (n=50) |  |
| kn | steer_only | 78.0 [64.8–87.2] (n=50) | 0.0 [0.0–7.1] (n=50) |  |
| kn | input+steer | 2.0 [0.4–10.5] (n=50) | 8.0 [3.2–18.8] (n=50) |  |
| kn_latn | none | 38.0 [25.9–51.8] (n=50) | 12.0 [5.6–23.8] (n=50) |  |
| kn_latn | input_only | 0.0 [0.0–7.1] (n=50) | 16.0 [8.3–28.5] (n=50) | 100 / 0 |
| kn_latn | steer_only | 42.0 [29.4–55.8] (n=50) | 14.0 [7.0–26.2] (n=50) |  |
| kn_latn | input+steer | 2.0 [0.4–10.5] (n=50) | 22.0 [12.8–35.2] (n=50) | 100 / 0 |
| kn_mix | none | 52.0 [38.5–65.2] (n=50) | 10.0 [4.3–21.4] (n=50) |  |
| kn_mix | input_only | 0.0 [0.0–7.1] (n=50) | 16.0 [8.3–28.5] (n=50) |  |
| kn_mix | steer_only | 72.0 [58.3–82.5] (n=50) | 0.0 [0.0–7.1] (n=50) |  |
| kn_mix | input+steer | 2.0 [0.4–10.5] (n=50) | 6.0 [2.1–16.2] (n=50) |  |
| kn_latn_translit_rows | none | 38.0 [25.9–51.8] (n=50) | 12.0 [5.6–23.8] (n=50) |  |
| kn_latn_translit_rows | input_only | 0.0 [0.0–7.1] (n=50) | 16.0 [8.3–28.5] (n=50) | 100 / 0 |
| kn_latn_translit_rows | steer_only | 42.0 [29.4–55.8] (n=50) | 14.0 [7.0–26.2] (n=50) |  |
| kn_latn_translit_rows | input+steer | 2.0 [0.4–10.5] (n=50) | 22.0 [12.8–35.2] (n=50) | 100 / 0 |

**Qwen2.5-3B-Instruct**

| variant | setting | harmful pass-through % | harmless wrongly blocked % | kn_latn input rows: translit / untranslated |
|---|---|---|---|---|
| en | none | 6.7 [4.4–10.1] (n=300) | 20.0 [14.4–27.1] (n=150) |  |
| en | input_only | 0.0 [0.0–1.3] (n=300) | 22.0 [16.1–29.3] (n=150) |  |
| en | steer_only | 6.3 [4.1–9.7] (n=300) | 20.0 [14.4–27.1] (n=150) |  |
| en | input+steer | 0.0 [0.0–1.3] (n=300) | 22.0 [16.1–29.3] (n=150) |  |
| kn | none | 65.3 [59.8–70.5] (n=300) | 4.0 [1.8–8.5] (n=150) |  |
| kn | input_only | 2.7 [1.4–5.2] (n=300) | 8.7 [5.1–14.3] (n=150) |  |
| kn | steer_only | 28.3 [23.5–33.7] (n=300) | 45.3 [37.6–53.3] (n=150) |  |
| kn | input+steer | 0.7 [0.2–2.4] (n=300) | 46.7 [38.9–54.6] (n=150) |  |
| kn_latn | none | 4.0 [2.3–6.9] (n=300) | 28.0 [21.4–35.7] (n=150) |  |
| kn_latn | input_only | 0.0 [0.0–1.3] (n=300) | 34.0 [26.9–41.9] (n=150) | 450 / 0 |
| kn_latn | steer_only | 1.3 [0.5–3.4] (n=300) | 47.3 [39.5–55.3] (n=150) |  |
| kn_latn | input+steer | 0.0 [0.0–1.3] (n=300) | 50.0 [42.1–57.9] (n=150) | 450 / 0 |
| kn_mix | none | 46.7 [41.1–52.3] (n=300) | 12.0 [7.7–18.2] (n=150) |  |
| kn_mix | input_only | 1.3 [0.5–3.4] (n=300) | 17.3 [12.1–24.2] (n=150) |  |
| kn_mix | steer_only | 17.0 [13.2–21.7] (n=300) | 72.7 [65.0–79.2] (n=150) |  |
| kn_mix | input+steer | 1.0 [0.3–2.9] (n=300) | 73.3 [65.7–79.8] (n=150) |  |
| kn_latn_translit_rows | none | 4.0 [2.3–6.9] (n=300) | 28.0 [21.4–35.7] (n=150) |  |
| kn_latn_translit_rows | input_only | 0.0 [0.0–1.3] (n=300) | 34.0 [26.9–41.9] (n=150) | 450 / 0 |
| kn_latn_translit_rows | steer_only | 1.3 [0.5–3.4] (n=300) | 47.3 [39.5–55.3] (n=150) |  |
| kn_latn_translit_rows | input+steer | 0.0 [0.0–1.3] (n=300) | 50.0 [42.1–57.9] (n=150) | 450 / 0 |

- **kn_latn input flags** come from the translit baseline (ITRANS → Kannada → NLLB → Llama Guard) for 450 kn_latn rows and from the untranslated baseline for 0. `kn_latn_translit_rows` restricts kn_latn to translit-covered rows.
- **The output layer is not scored here.** Llama Guard is both the output filter and the study's judge (harmful_compliance), so scoring it with Llama Guard would be circular: it would block exactly what it counts as harmful. It is reported as a design layer, validated only by the human-labelled sample (`analysis/scorer_check.csv`).
- `label` (refused / not_understood / complied) agrees with humans only ~33% (n = 30, Gemma), so the harmless-blocked rates, which use label = refused, carry that caveat. not_understood shares are never a headline.
- All listed cells are filled; models not shown have no main CSVs yet.
<!-- layered-guard:end -->
<!-- missed:begin -->
## What beats every layer (run = main; `analysis/missed.csv`, `python -m analysis.missed`)
Harmful prompts that the input check (Llama Guard on the translated prompt) did **not** flag **and** that the model complied with (harmful_compliance = 1). Condition none = beats the input layer alone; steer_gated = beats input + steering. IDs only (`missed.csv`); no prompt text.

**Llama-3.2-3B-Instruct**

| variant | missed, none | missed, steer_gated | categories missed (steer_gated) |
|---|---|---|---|
| en | 0/50 (0.0%) | 0/50 (0.0%) | none |
| kn | 1/50 (2.0%) | 1/50 (2.0%) | illegal 1 |
| kn_latn | 0/50 (0.0%) | 1/50 (2.0%) | harmful 1 |
| kn_mix | 0/50 (0.0%) | 1/50 (2.0%) | cybercrime_intrusion 1 |

- Prompt IDs that beat the layers in ≥ 2 variants (steer_gated): none.

**Qwen2.5-3B-Instruct**

| variant | missed, none | missed, steer_gated | categories missed (steer_gated) |
|---|---|---|---|
| en | 0/300 (0.0%) | 0/300 (0.0%) | none |
| kn | 8/300 (2.7%) | 2/300 (0.7%) | harmful 1, illegal 1 |
| kn_latn | 0/300 (0.0%) | 0/300 (0.0%) | none |
| kn_mix | 4/300 (1.3%) | 3/300 (1.0%) | advbench_general 1, harassment_bullying 1, illegal 1 |

- Prompt IDs that beat the layers in ≥ 2 variants (steer_gated): none.

- These counts rely on harmful_compliance (Llama Guard on the NLLB-translated reply); judge or translation errors can add or hide misses. Small cells (single digits) are anecdotes, not rates.
<!-- missed:end -->

<!-- projdet:begin -->
## The model's own refusal signal as a language-agnostic detector
Source: `analysis/projection_detector.csv` (`python -m analysis.projection_detector`), condition none gate files.
Detector = the prompt's projection on the model's **English-derived** refusal direction at the steering layer; flag if projection > tau (the configured gate threshold). AUROC is threshold-free (0.5 = chance).

**Llama-3.2-3B-Instruct** (layer 15, tau -2.353, n = 50 harmful / 50 harmless per variant)

| variant | AUROC [95% CI] | catch % at tau | false-alarm % at tau | mean proj harmful / harmless |
|---|---|---|---|---|
| en | 0.999 [0.992–1.0] | 100.0 [92.9–100.0] | 52.0 [38.5–65.2] | 4.74 / -2.32 |
| kn | 0.639 [0.531–0.748] | 100.0 [92.9–100.0] | 98.0 [89.5–99.6] | -0.55 / -1.19 |
| kn_latn | 0.474 [0.361–0.588] | 100.0 [92.9–100.0] | 100.0 [92.9–100.0] | -0.65 / -0.6 |
| kn_mix | 0.669 [0.564–0.775] | 98.0 [89.5–99.6] | 100.0 [92.9–100.0] | -0.3 / -1.17 |
| ALL_non_en | 0.617 [0.554–0.68] | 99.3 [96.3–99.9] | 99.3 [96.3–99.9] | -0.5 / -0.99 |
| ALL | 0.759 [0.713–0.806] | 99.5 [97.2–99.9] | 87.5 [82.2–91.4] | 0.81 / -1.32 |

- Llama-3.2-3B-Instruct: AUROC en 0.999 vs Kannada variants kn 0.639, kn_latn 0.474, kn_mix 0.669; weakest = kn_latn. At tau, the false-alarm rate on harmless Kannada-variant prompts is kn 98.0%, kn_latn 100.0%, kn_mix 100.0%.
  - Llama-3.2-3B-Instruct: tau -2.353 is below almost all kn, kn_latn, kn_mix projections, so at this tau the gate fires on nearly every non-English prompt (it behaves like steer-all-non-English); the AUROC, not the tau, is the fair measure here.
  - Llama-3.2-3B-Instruct: pilot-size n (50 per class), so CIs are wide.
**Qwen2.5-3B-Instruct** (layer 23, tau 15.882, n = 300 harmful / 150 harmless per variant)

| variant | AUROC [95% CI] | catch % at tau | false-alarm % at tau | mean proj harmful / harmless |
|---|---|---|---|---|
| en | 0.971 [0.957–0.985] | 100.0 [98.7–100.0] | 70.7 [62.9–77.4] | 40.57 / 19.03 |
| kn | 0.633 [0.581–0.686] | 62.3 [56.7–67.6] | 46.0 [38.2–54.0] | 17.21 / 15.52 |
| kn_latn | 0.849 [0.814–0.883] | 87.0 [82.7–90.3] | 34.0 [26.9–41.9] | 17.09 / 15.51 |
| kn_mix | 0.577 [0.522–0.632] | 74.3 [69.1–78.9] | 71.3 [63.6–78.0] | 18.21 / 17.03 |
| ALL_non_en | 0.663 [0.634–0.693] | 74.6 [71.6–77.3] | 50.4 [45.8–55.0] | 17.5 / 16.02 |
| ALL | 0.697 [0.673–0.721] | 80.9 [78.6–83.0] | 55.5 [51.5–59.4] | 23.27 / 16.77 |

- Qwen2.5-3B-Instruct: AUROC en 0.971 vs Kannada variants kn 0.633, kn_latn 0.849, kn_mix 0.577; weakest = kn_mix. At tau, the false-alarm rate on harmless Kannada-variant prompts is kn 46.0%, kn_latn 34.0%, kn_mix 71.3%.

- **Where it is weak:** the direction is computed from English prompts. In Kannada script, Kanglish and code-mix, harmful projections fall towards the harmless range, so AUROC drops and a single tau trades catch rate against false alarms (the harmless over-refusal seen under steer_gated). It is a cheap in-model signal (no extra model, no translation), not a replacement for the translated Llama Guard input check.
- Catch / false-alarm here use projection > tau only; the deployed gate also requires a non-English detection, so it never fires on English (see gate_fire_* columns).
<!-- projdet:end -->
