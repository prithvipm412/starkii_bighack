# Mac2 status

Done:
- Phase 1 prompt variant tools added under `data_tools/` and pushed; a mocked 20-prompt structural check passed (80 output rows, four variants per `prompt_id`). Ready for mac4 to use after dependencies and input JSONL are available.
Doing:
 - Waiting for the pilot JSONL and a local model environment for the real 20-prompt run.
Blocked:
 - No Python dependencies are installed (`torch`, `transformers`, `IndicTransToolkit`, `indic-transliteration`), and the 1B model has not been downloaded, so live translation cannot yet run on this checkout. `AGENTS.md` and `requirements.txt` have now arrived from mac1; the documented JSONL schema uses `text`, `prompt_id`, `split`, `category`, `source`, and `variant`.
Next:
 - Install the shared requirements; run `python -m data_tools.build --in <english.jsonl> --out data_tools/output/<name>.jsonl --language Kannada`; then run `python -m data_tools.check` on the generated file.

The input follows the prompt schema in `AGENTS.md`; all original fields are preserved, `text` is replaced per variant, and all four rows retain the same `prompt_id`. Code-mix masks and restores common technical terms and identifiers around translation; `--mix-latin` selects Latin transliteration for that variant. Output files are ignored by git.
