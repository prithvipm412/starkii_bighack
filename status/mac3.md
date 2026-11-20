# Mac3 status

Done:
- Installed the shared requirements on Python 3.12.16. Verified PyTorch 2.15.0 can allocate a tensor on MPS.
- Confirmed access to the official `google/gemma-2-2b-it` checkpoint.

Doing:
- Resuming the final Gemma weight shard over HTTP after the Xet transfer returned a response-decoding error.

Blocked:
- Pilot inputs `data_tools/output/direction.jsonl` and `data_tools/output/pilot.jsonl` have not arrived locally.

Next:
- Verify Gemma on MPS with eager attention, starting with float16 and retrying with bfloat16 if needed. Gemma's chat template requires a user-only test message because it rejects the system role.
