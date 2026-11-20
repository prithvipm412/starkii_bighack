# Mac3 status

Done:
- Installed the shared requirements on Python 3.12.16 with PyTorch 2.15.0.
- Downloaded the official `google/gemma-2-2b-it` checkpoint. The final shard passed SHA-256 verification after a resumable HTTP transfer.
- Gemma generated a coherent answer with finite logits on `mps:0` and `attn_implementation="eager"` in both `torch.float16` and `torch.bfloat16`. This was a single harmless smoke prompt per dtype. The current `configs/mac3_gemma.yaml` selects the verified bfloat16 setting.
- Gemma's chat template rejects the `system` role. The smoke prompt used one `user` message.

- Removed two temporary download folders and the incomplete Gemma cache shard. The completed checkpoint remains cached.
- Extracted the Gemma direction on MPS with bf16 from 64 harmful and 64 harmless English rows. Chosen layer **16**, alpha **176.0623**, tau **-13.6028**, Cohen's d **7.61**. Metadata is in `results/mac3/gemma-2-2b-it_direction.json`.

Doing:
- Waiting for `data_tools/output/pilot.jsonl` (checking every 30 seconds).

Blocked:

Next:
- Run the Gemma pilot with `--conditions none` and `HF_HUB_ETAG_TIMEOUT=10`, with `HF_HUB_OFFLINE` unset.
