# Mac3 status

Done:
- Installed the shared requirements on Python 3.12.16 with PyTorch 2.15.0.
- Downloaded the official `google/gemma-2-2b-it` checkpoint. The final shard passed SHA-256 verification after a resumable HTTP transfer.
- Gemma generated a coherent answer with finite logits on `mps:0` and `attn_implementation="eager"` in both `torch.float16` and `torch.bfloat16`. This was a single harmless smoke prompt per dtype. The current `configs/mac3_gemma.yaml` selects the verified bfloat16 setting.
- Gemma's chat template rejects the `system` role. The smoke prompt used one `user` message.

Doing:
- Waiting for Mac1's pilot instructions and local pilot data. `direction.jsonl` has arrived.

Blocked:
- `data_tools/output/pilot.jsonl` has not arrived locally.

Next:
- Run the mac3 pilot when the inputs and instructions are ready.
