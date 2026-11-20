# Mac3 status

Done:
- Pulled `origin/main`. Confirmed arm64 and an existing virtual environment with Python 3.9.6.

Doing:
- Phase 0–1 setup for `google/gemma-2-2b-it`.

Blocked:
- Mac1 has yet to push `requirements.txt`. Dependency installation, model download, and MPS verification are pending.
- The pilot also needs the pipeline modules, `configs/mac3_gemma.yaml`, and `data_tools/output/pilot.jsonl`. The full run and sweep await Mac1's instructions.

Next:
- Install the shared requirements, download Gemma, and verify that it loads on MPS.
