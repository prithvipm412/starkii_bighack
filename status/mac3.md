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

Doing:
- Waiting for Mac1's Gemma-specific tau sweep command. Human labeling is in progress locally.

Blocked:


Next:
- Run the published tau sweep, then select the full-run settings after confirming Mac1's token limit.
