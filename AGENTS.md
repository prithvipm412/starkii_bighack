# Big Hack 2.0 — R2 "Jailbreaks speak Kannada too" (team Stark Industry Interns)
Shared rules for every agent (Claude Code reads CLAUDE.md, Codex reads AGENTS.md — same content).

## Research
Hypothesis: Small open models refuse harmful requests less in Kannada script, Kanglish (Kannada in Latin letters) and Kannada-English code-mixed text than in English. Adding the model's own English-derived "refusal direction" at a middle layer, only when the input already weakly activates it, closes the gap with little extra refusal of harmless requests.
Compare: none (no defence) vs baseline (translate to English -> Llama Guard 3 1B) vs steer_always vs steer_gated.
Report: refusal rate on harmful, wrong-refusal rate on harmless, latency, where each method fails.

## Track rules
- Never commit or publish model replies or harmful prompt text. Only scores go in git.
- Prompt files live in data_tools/output/ (gitignored) and move between Macs by AirDrop.
- Open-weight models run locally only.

## Macs and folders (never edit another Mac's folders)
- mac1 (M5) Claude Code: pipeline/, configs/, requirements.txt, results/mac1/, status/mac1.md — Qwen/Qwen2.5-3B-Instruct
- mac2 (M5) Codex: data_tools/, results/mac2/, status/mac2.md — meta-llama/Llama-3.2-3B-Instruct
- mac3 (M5) Codex: results/mac3/, status/mac3.md — google/gemma-2-2b-it; Antigravity owns dashboard/
- mac4 (M4) Claude Code: baseline/, analysis/, results/mac4/, status/mac4.md — IndicTrans2 + meta-llama/Llama-Guard-3-1B
Only mac1 edits pipeline/. Pipeline bug? Write it under Blocked in your status file.

## Prompt file format (JSONL, one prompt per line)
{"prompt_id": "h0001", "split": "harmful|harmless|direction", "category": "...", "source": "...", "variant": "en|kn|kn_latn|kn_mix", "text": "..."}
"direction" = separate English prompts used only to compute the refusal direction (never evaluated). All 4 variants of a prompt share the same prompt_id.

## Results format (CSV: results/macN/<model>_<condition>.csv)
prompt_id,split,category,variant,model,condition,refused,judge_score,latency_ms,commit
refused is 0/1; commit = git rev-parse --short HEAD.

## Pipeline commands (mac1 builds; everyone runs)
python -m pipeline.extract_direction --config configs/<cfg>.yaml
python -m pipeline.run --config configs/<cfg>.yaml --prompts data_tools/output/<file>.jsonl --conditions none,steer_always,steer_gated
Greedy decoding, seed 0, max 64 new tokens, save after every batch, resume on restart, raw replies only in outputs/ (gitignored), score locally.

## Git routine
git pull --rebase ; git add <your folders only> ; git commit -m "macN: <what>" ; git push
Update status/macN.md (Done / Doing / Blocked / Next) and push at least every 2 hours.

## Long runs
caffeinate -dims python -m pipeline.run ... > logs/<name>.log 2>&1   (plugged in, lid open)

## Timeline (IST)
P0 setup 3:45-4:15 | P1 build 4:15-6:00 | P2 pilot 6:00-7:30 | P3 steering + dashboard + slides 7:30-8:30 | code freeze 8:30 | judging 9:00 pm | P4 full runs 9:30-12:30 | P5 sweeps + failure analysis 12:30-5:00 | P6 final 5:00 -> submission
