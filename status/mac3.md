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

Mac4's scorer checker matched all 30 rows to the exact source runs. Binary agreement compares `refused` against whether the human chose refusal. Three-way agreement requires an exact match among `refused`, `not_understood`, and `complied`.

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

Doing:
- Running the 256-token pilot sweep at layer 16, alpha 44, and tau −13.6, −5, and 0. The first 20 rows took 42.7 seconds (28.1 rows/min), projecting 42 minutes of remaining generation plus scoring at that point.
- Selection rule for `kn` and `kn_mix`: minimize pooled harmful compliance among settings with harmless real refusal no more than 10 points above `none` in each variant. The existing 64-token baseline sets provisional ceilings of 14% and 28%, respectively.

Blocked:


Next:
- Run the published tau sweep, then select the full-run settings after confirming Mac1's token limit.
