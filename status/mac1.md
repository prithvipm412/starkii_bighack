# Mac1 status

NOTES FOR EVERYONE (READ FIRST):
- PYTHON 3.12. REQUIREMENTS.TXT IS PINNED AND TESTED ON 3.12.13 (CLEAN INSTALL + IMPORTS + MPS).
- RESULTS FILE NAME = <MODEL_ID BASENAME>_<CONDITION>.CSV, E.G. results/mac1/Qwen2.5-3B-Instruct_none.csv. "model" COLUMN = FULL HF ID.
- judge_score = Llama Guard 3 1B P(unsafe) of the (English-translated) reply, 0..1. refused = multilingual refusal-phrase match (en / kn / Kanglish / hi ...). latency_ms = generation time per prompt (batch time / 8), scoring not included.
- EXTRA FILES (NOT IN THE RESULTS SCHEMA, NO TEXT): results/macN/gate/<model>_<condition>.csv = prompt_id,split,variant,condition,layer,alpha,tau,projection,steered,detected_non_en. Loaders that glob results/macN/*.csv do not see them.
- run.py RESUMES BY (prompt_id, variant). Kill it any time and rerun the same command.
- If Llama Guard / IndicTrans2 can't load (gated), judge_score is left blank; after `hf auth login` rerun the same command with `--rescore` (no regeneration).

## Commands for every Mac (repo root, .venv on 3.12)
```
git pull --rebase
uv venv -p 3.12 .venv && uv pip install -r requirements.txt     # or python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
source .venv/bin/activate
hf auth login        # Llama / Gemma / Llama Guard / IndicTrans2 are gated: accept each licence on huggingface.co first
mkdir -p logs
# CFG = mac1_qwen | mac2_llama | mac3_gemma
python -m pipeline.extract_direction --config configs/CFG.yaml            # reads data_tools/output/direction.jsonl
caffeinate -dims python -m pipeline.run --config configs/CFG.yaml --prompts data_tools/output/pilot.jsonl --conditions none,steer_always,steer_gated > logs/CFG_pilot.log 2>&1
# after hf login, if judge_score came out blank:
python -m pipeline.run --config configs/CFG.yaml --prompts data_tools/output/pilot.jsonl --conditions none,steer_always,steer_gated --rescore
```
Options: `--limit N` (first N prompt_ids, all variants), `--layer L --alpha A --tau T` (override config/defaults).
Sweep: `--layers 10,14,18 --alphas 4,8,12 --conditions steer_gated` -> results/macN/sweep_<model>_<cond>_L<L>_a<A>.csv (same schema).
Defaults when config has null: layer = best Cohen's-d separation in the middle third; alpha = norm of the harmful-harmless mean difference at that layer; tau = midpoint of English harmful/harmless projections. See results/macN/<model>_direction.json.

Done:
- requirements.txt (Python 3.12), configs/mac{1,2,3}_*.yaml, pipeline/{data,model,extract_direction,steer,score,run}.py, CLAUDE.md/AGENTS.md "Python 3.12" line.
Doing:
- Smoke test on Qwen (10 English prompts + kn/kn_latn/kn_mix of one prompt).
Blocked:
- No HF login on mac1: Llama Guard 3 1B and IndicTrans2 are gated, so judge_score is blank until `hf auth login`.
Next:
- Pilot: extract_direction on direction.jsonl, then --conditions none on pilot.jsonl.
