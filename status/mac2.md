# Mac2 status

Done:
- Set `model_id: unsloth/Llama-3.2-3B-Instruct` in config commit `df184d1`.
- Extracted Llama refusal direction from 128 prompts; direction artifact is in `results/mac2/`.

Doing:
- Pilot generation for `none,steer_gated,steer_always`; local MPS unavailable, so the model is running on CPU. Replies are saved locally under ignored `outputs/`.

Blocked:
- None. HF cache is available; HF offline mode is enabled because this environment cannot resolve Hugging Face.

Next:
- Finish pilot, rerun with `--rescore` for cached Llama Guard judge scores, calculate the harmful/harmless refusal rate table per condition × variant, push `results/mac2/` and this status, then start the full `none` run in the background.
