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
# fallback translator (ungated, 2.5 GB). HF_HUB_DISABLE_XET=1 avoids the Xet "error decoding response body"; rerun if the connection drops, it resumes:
HF_HUB_DISABLE_XET=1 python -c "from huggingface_hub import snapshot_download as s; s('facebook/nllb-200-distilled-600M', allow_patterns=['pytorch_model.bin','*.json','*.model'])"
mkdir -p logs
# CFG = mac1_qwen | mac2_llama | mac3_gemma
python -m pipeline.extract_direction --config configs/CFG.yaml            # reads data_tools/output/direction.jsonl
caffeinate -dims python -m pipeline.run --config configs/CFG.yaml --prompts data_tools/output/pilot.jsonl --conditions none,steer_always,steer_gated > logs/CFG_pilot.log 2>&1
# after hf login, if judge_score came out blank:
python -m pipeline.run --config configs/CFG.yaml --prompts data_tools/output/pilot.jsonl --conditions none,steer_always,steer_gated --rescore
```
Options: `--limit N` (first N prompt_ids, all variants), `--layer L --alpha A --tau T` (override config/defaults).
Sweep: `--layers 10,14,18 --alphas 4,8,12 --conditions steer_gated` -> results/macN/sweep_<model>_<cond>_L<L>_a<A>.csv (same schema).
Defaults when config has null: layer = best Cohen's-d separation in the middle third; alpha = norm of the harmful-harmless mean difference at that layer; tau = mean + 2 sd of English HARMLESS projections (the English midpoint was too high: Kannada harmful prompts project far below English harmful ones). See results/macN/<model>_direction.json.

Done:
- requirements.txt (Python 3.12), configs/mac{1,2,3}_*.yaml, pipeline/{data,model,extract_direction,steer,score,run}.py, CLAUDE.md/AGENTS.md "Python 3.12" line.
- MILESTONE: full loop on Qwen passed: 10 English prompts (5 harmful, 5 harmless) + kn/kn_latn/kn_mix of one harmful prompt, all 3 conditions, resume verified. CSVs in results/mac1/smoke/ (NOT real results; kept out of results/mac1/*.csv on purpose). ~75-90 tok/s on M5, batch 8.
- Smoke numbers (32 direction prompts, layer 23/36, alpha 34.5, tau 12.4): none = 5/5 English harmful refused, 0/5 harmless refused, 0/3 Kannada variants refused. steer_always = 3/3 Kannada refused, but 4/5 harmless wrongly refused. steer_gated = 3/3 Kannada refused, 0/5 harmless refused, English untouched.
- Projection at layer 23: English harmful ~42, English harmless 3-10, Kannada harmful ~15. Supports the "weak activation" hypothesis; motivated the tau change above.
- mac1 .venv rebuilt on Python 3.12.16 from requirements.txt; smoke loop re-run on it, same refusals as before, ~85 tok/s.
- P2: Qwen direction extracted from direction.jsonl (64 harmful + 64 harmless English): layer 23 of 36 (best separation in the middle third 12-23, Cohen's d 7.55), alpha 35.4, tau 15.9. results/mac1/Qwen2.5-3B-Instruct_direction.json. Separation keeps rising after layer 23 (about 10 at 26 and 35), so the layer sweep should include values beyond the middle third.
- TIP: models already downloaded -> prefix runs with HF_HUB_OFFLINE=1 to skip HF network checks (they timed out here). NEEDS THE PIPELINE FROM a later commit than 549b5b5: transformers 4.57.3 calls the Hub when a tokenizer is loaded by repo id even offline; pipeline now loads the local cached snapshot when HF_HUB_OFFLINE=1. Verified offline: Qwen generate + NLLB translate.
- Scorer translator: IndicTrans2 if accessible, ELSE facebook/nllb-200-distilled-600M (ungated). The log line "[score] translator: ..." says which one ran. mac1 uses NLLB (IndicTrans2 still gated).
Doing:
- Waiting for data_tools/output/pilot.jsonl, then --conditions none.
Blocked:
- mac1 logged in as shared account oberoii284 (read token), but HF still answers 403 'not in the authorized list' for ai4bharat/indictrans2-indic-en-1B AND meta-llama/Llama-Guard-3-1B. That account's access requests must be approved (check huggingface.co/settings/gated-repos). Until then: judge_score blank, no translation; refused (phrase check) still works. Fix later with --rescore.
- data_tools/output/direction.jsonl + pilot.jsonl not on mac1 yet (AirDrop).
Next:
- Pilot: extract_direction on direction.jsonl, then --conditions none on pilot.jsonl.
