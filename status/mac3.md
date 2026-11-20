# Mac3 status

Done:
- Installed the shared requirements on Python 3.12.16 with PyTorch 2.15.0.
- Downloaded the official `google/gemma-2-2b-it` checkpoint. The final shard passed SHA-256 verification after a resumable HTTP transfer.
- Gemma generated a coherent answer with finite logits on `mps:0` and `attn_implementation="eager"` in both `torch.float16` and `torch.bfloat16`. This was a single harmless smoke prompt per dtype. The current `configs/mac3_gemma.yaml` selects the verified bfloat16 setting.
- Gemma's chat template rejects the `system` role. The smoke prompt used one `user` message.

- Removed two temporary download folders and the incomplete Gemma cache shard. The completed checkpoint remains cached.
- Extracted the Gemma direction on MPS with bf16 from 64 harmful and 64 harmless English rows. Chosen layer **16**, alpha **176.0623**, tau **-13.6028**, Cohen's d **7.61**. Metadata is in `results/mac3/gemma-2-2b-it_direction.json`.
- Finished the 400-row, 100-prompt-ID pilot in order: `none`, `steer_gated`, `steer_always`. Verified each result and gate CSV covers all 400 prompt/variant pairs.
- First 20 baseline rows averaged 95.2 rows/min. Generation took 214 s for `none`, 214 s for `steer_gated`, and 252 s for `steer_always`.
- Phrase-based refusal counts (harmful / harmless, each out of 200): `none` 105 / 36, `steer_gated` 183 / 106, `steer_always` 198 / 198. The gate activated on 230 of 400 rows.
- Added 20 manual refusal labels for English replies, with 10 harmful and 10 harmless examples across all three conditions. `handlabels.csv` contains only prompt IDs, conditions, and binary labels.


## Gemma pilot alpha sweep

Layer 16, tau −13.6028, `steer_gated`. Harmful columns are refusal rates. Harmless columns are wrong-refusal rates. This uses the pre-fix phrase scorer, which can count confusion as refusal.

| Alpha | harmful en | harmful kn | harmful kn_latn | harmful kn_mix | harmless en | harmless kn | harmless kn_latn | harmless kn_mix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 44 | 100% (50/50) | 76% (38/50) | 78% (39/50) | 86% (43/50) | 14% (7/50) | 28% (14/50) | 76% (38/50) | 40% (20/50) |
| 88 | 100% (50/50) | 86% (43/50) | 96% (48/50) | 88% (44/50) | 14% (7/50) | 44% (22/50) | 90% (45/50) | 54% (27/50) |
| 132 | 100% (50/50) | 86% (43/50) | 96% (48/50) | 86% (43/50) | 14% (7/50) | 46% (23/50) | 92% (46/50) | 58% (29/50) |

## Pilot rescored with Llama Guard 3 1B

Rescored all 2,400 saved replies using Mac1's three-way scorer and cached Llama Guard 3 1B. All rows have judge scores. The table counts only `label=refused` and excludes `not_understood`.

| Setting | harmful en | harmful kn | harmful kn_latn | harmful kn_mix | harmless en | harmless kn | harmless kn_latn | harmless kn_mix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | 100% (50/50) | 48% (24/50) | 4% (2/50) | 56% (28/50) | 14% (7/50) | 4% (2/50) | 4% (2/50) | 18% (9/50) |
| steer_gated | 100% (50/50) | 82% (41/50) | 96% (48/50) | 88% (44/50) | 14% (7/50) | 48% (24/50) | 84% (42/50) | 58% (29/50) |
| steer_always | 100% (50/50) | 96% (48/50) | 100% (50/50) | 100% (50/50) | 100% (50/50) | 96% (48/50) | 100% (50/50) | 100% (50/50) |
| alpha 44 | 100% (50/50) | 76% (38/50) | 26% (13/50) | 86% (43/50) | 14% (7/50) | 28% (14/50) | 30% (15/50) | 40% (20/50) |
| alpha 88 | 100% (50/50) | 86% (43/50) | 70% (35/50) | 88% (44/50) | 14% (7/50) | 44% (22/50) | 68% (34/50) | 54% (27/50) |
| alpha 132 | 100% (50/50) | 86% (43/50) | 94% (47/50) | 86% (43/50) | 14% (7/50) | 46% (23/50) | 84% (42/50) | 58% (29/50) |

## Human label agreement

All 30 labels came from the human reviewer. Some Kannada-script items were labeled with AI translation help. The sample includes 15 `none` and 15 alpha-44 `steer_gated` replies from the 64-token pilot, including five harmless `kn_latn` replies selected because the phrase scorer flagged them. These agreement rates describe that sample.

Mac4's scorer checker matched all 30 rows to the archived 64-token `none` CSV and the alpha-44 sweep CSV. Binary agreement compares `refused` against whether the human chose refusal. Three-way agreement requires an exact match among `refused`, `not_understood`, and `complied`.

| Variant | Binary `refused` agreement | Three-way `label` agreement |
| --- | ---: | ---: |
| kn | 8/10 (80.0%) | 3/10 (30.0%) |
| kn_latn | 5/10 (50.0%) | 3/10 (30.0%) |
| kn_mix | 5/10 (50.0%) | 5/10 (50.0%) |
| ALL | 18/30 (60.0%) | 11/30 (36.7%) |

## Gate firing from stored pilot projections

Layer 16. A row fires when it is detected as non-English and its stored projection exceeds tau. Cells show harmful / harmless firing rates (50 rows each). These are projection estimates from the 64-token pilot, separate from the 256-token generation sweep.

| Tau | en | kn | kn_latn | kn_mix |
| ---: | --- | --- | --- | --- |
| -20 | 0% / 0% | 92% / 60% | 98% / 90% | 90% / 72% |
| -13.6 | 0% / 0% | 86% / 48% | 96% / 84% | 88% / 58% |
| -10 | 0% / 0% | 78% / 40% | 86% / 76% | 84% / 50% |
| -5 | 0% / 0% | 72% / 32% | 72% / 58% | 78% / 40% |
| 0 | 0% / 0% | 66% / 30% | 52% / 22% | 68% / 36% |
| 5 | 0% / 0% | 64% / 22% | 30% / 10% | 66% / 24% |
| 10 | 0% / 0% | 58% / 12% | 14% / 6% | 60% / 20% |

## 256-token Gemma pilot tau sweep

Layer 16, alpha 44, 400 rows per tau and 50 per split/variant cell. Refusal uses `label=refused`. Harmful compliance is the share of harmful replies flagged by Llama Guard after translation.

| Tau | Variant | Harmful refusal | Harmless wrong-refusal | Harmful compliance |
| ---: | --- | ---: | ---: | ---: |
| -13.6 | en | 100% (50/50) | 14% (7/50) | 4% (2/50) |
| -13.6 | kn | 76% (38/50) | 40% (20/50) | 20% (10/50) |
| -13.6 | kn_latn | 20% (10/50) | 20% (10/50) | 10% (5/50) |
| -13.6 | kn_mix | 86% (43/50) | 42% (21/50) | 16% (8/50) |
| -5 | en | 100% (50/50) | 14% (7/50) | 4% (2/50) |
| -5 | kn | 68% (34/50) | 28% (14/50) | 26% (13/50) |
| -5 | kn_latn | 18% (9/50) | 16% (8/50) | 8% (4/50) |
| -5 | kn_mix | 78% (39/50) | 34% (17/50) | 18% (9/50) |
| 0 | en | 100% (50/50) | 14% (7/50) | 4% (2/50) |
| 0 | kn | 64% (32/50) | 24% (12/50) | 30% (15/50) |
| 0 | kn_latn | 18% (9/50) | 12% (6/50) | 14% (7/50) |
| 0 | kn_mix | 70% (35/50) | 34% (17/50) | 18% (9/50) |

### Setting selection and translate-then-guard comparison

No tested tau satisfies the +10-point harmless real-refusal ceiling for both `kn` and `kn_mix` against the available 64-token `none` reference. The provisional ceilings are 14% and 28%. Tau 0 comes closest with 24% and 34%, and tau −13.6 has the lowest pooled harmful compliance (18%) among the tested taus.

| Setting | Harmful outcome kn | Harmless refusal kn | Harmful outcome kn_mix | Harmless refusal kn_mix |
| --- | ---: | ---: | ---: | ---: |
| Gemma none (64 tokens) | 44% (22/50) | 4% (2/50) | 16% (8/50) | 18% (9/50) |
| Gemma alpha 44, tau -13.6 (256 tokens) | 20% (10/50) | 40% (20/50) | 16% (8/50) | 42% (21/50) |
| Gemma alpha 44, tau -5 (256 tokens) | 26% (13/50) | 28% (14/50) | 18% (9/50) | 34% (17/50) |
| Gemma alpha 44, tau 0 (256 tokens) | 30% (15/50) | 24% (12/50) | 18% (9/50) | 34% (17/50) |
| NLLB → Llama Guard baseline | 10% (5/50) | 8% (4/50) | 8% (4/50) | 6% (3/50) |

For Gemma, harmful outcome means the generated reply was judged unsafe. For the NLLB → Llama Guard baseline, it means a harmful input was not flagged, as the baseline screens inputs and generates no reply. Its harmless column is the rate of benign inputs flagged. Baseline rows were matched to the same pilot prompt IDs and variants.

## Full-run gate firing by threshold

Computed from 1,800 unique layer-16 Gemma prompt/variant pairs. The full `none` and `steer_gated` gate CSVs agree on every stored projection and detected-language flag. Cells show harmful / harmless firing, with 300 harmful and 150 harmless prompts per variant. A row fires when its projection is strictly above tau and the existing detector marks it non-English. The detector marked one harmful `en` row non-English.

| Tau | en | kn | kn_latn | kn_mix |
| ---: | ---: | ---: | ---: | ---: |
| -20 | 0.3% / 0.0% | 93.3% / 54.7% | 99.0% / 90.7% | 93.3% / 67.3% |
| -13.6 | 0.3% / 0.0% | 86.7% / 44.0% | 95.3% / 86.0% | 88.3% / 47.3% |
| -10 | 0.3% / 0.0% | 79.7% / 39.3% | 89.7% / 76.7% | 85.7% / 42.0% |
| -8 | 0.3% / 0.0% | 78.7% / 35.3% | 86.7% / 68.0% | 84.0% / 39.3% |
| -6 | 0.3% / 0.0% | 76.3% / 34.0% | 82.3% / 62.0% | 81.7% / 36.7% |
| -5 | 0.3% / 0.0% | 75.7% / 34.0% | 79.3% / 57.3% | 80.7% / 35.3% |
| -4 | 0.3% / 0.0% | 74.7% / 33.3% | 76.3% / 46.0% | 79.3% / 34.7% |
| -3 | 0.3% / 0.0% | 74.3% / 33.3% | 70.7% / 40.7% | 77.7% / 34.7% |
| -2 | 0.3% / 0.0% | 72.0% / 31.3% | 66.7% / 34.7% | 76.0% / 33.3% |
| 0 | 0.3% / 0.0% | 70.7% / 30.7% | 56.3% / 27.3% | 73.7% / 31.3% |
| 2 | 0.3% / 0.0% | 68.3% / 27.3% | 46.7% / 19.3% | 72.3% / 30.0% |
| 5 | 0.3% / 0.0% | 64.7% / 24.7% | 31.3% / 13.3% | 69.3% / 23.3% |
| 10 | 0.3% / 0.0% | 58.0% / 16.0% | 15.7% / 5.3% | 65.0% / 20.0% |

**Proposal for Mac1.** At layer 16 and alpha 44, try tau **−4** for `kn_latn` and keep tau **0** for the other variants. Using 75% harmful firing as a working target, −4 retains 229/300 (76.3%) and fires on 69/150 harmless prompts (46.0%). Relative to the original −13.6 threshold, harmless firing drops 40.0 points while harmful firing drops 19.0 points. Relative to the current full-run tau 0, −4 raises harmful firing by 20.0 points and harmless firing by 18.7 points. Stricter thresholds than 0 cut harmless firing further and drive harmful firing below 56.3%. The stored projections do not show a threshold that both cuts harmless firing below the current full-run rate and retains high harmful firing.

The pipeline accepts one scalar `--tau` per run. `--taus` sweeps scalar settings across separate runs. Mac1 would need a variant-keyed threshold override with the scalar fallback and the effective threshold logged per row. The 400-row pilot was not generated because per-variant thresholds are unsupported.

Doing:

Blocked:
- The full gated run needs a setting that meets the selection rule. The current comparison uses different generation caps. A 256-token `none` reference would allow a matched-cap check.

Next:
- Resolve the full-run setting against the confirmed 256-token cap in Mac1's config.
