# Mac2 status

Done:
- Phase 1 prompt variant tools added under `data_tools/` (English, native script, Latin transliteration, code-mixed).
Doing:
 - Waiting for mac4's prompt schema confirmation and local model dependencies for the real 20-prompt run.
Blocked:
 - This checkout has no `HANDOFF.md`, `PLAN.md`, or `TASKS.md`; `AGENTS.md` does not include the promised prompt schema. No Python dependencies are installed (`torch`, `transformers`, `IndicTransToolkit`, `indic-transliteration`), and the 1B model has not been downloaded, so live translation cannot yet run on this checkout.
Next:
 - Install `torch`, `transformers`, `IndicTransToolkit`, and `indic-transliteration`; run `python -m data_tools.build --in <english.jsonl> --out data_tools/output/<name>.jsonl --language Kannada`; then run `python -m data_tools.check` on the generated file.

Assumption: each JSONL line is an object with `prompt_id`, optional `split`, and one string field named `prompt`, `prompt_text`, `text`, `question`, `instruction`, or `input`. All original fields are preserved; the chosen prompt field is replaced for each variant. Code-mix uses IndicTrans2 entity protection and keeps retained English names/identifiers; `--mix-latin` selects Latin transliteration for that variant. Output files are ignored by git.
