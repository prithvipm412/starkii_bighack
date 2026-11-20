# Mac2 status

Done:
- Changed `configs/mac2_llama.yaml` to use `unsloth/Llama-3.2-3B-Instruct` in commit `df184d1`.

Doing:
- Preparing the Llama direction extraction and pilot.

Blocked:
- `data_tools/output/pilot.jsonl`, `full.jsonl`, and `direction.jsonl` are not present in this checkout. The output directory contains only the local harmless test fixture and its variants.

Next:
- Once the prompt files are available, run direction extraction, the three-condition pilot, push `results/mac2/` and the per-condition × variant rate table, then start the full `none` run in the background.
