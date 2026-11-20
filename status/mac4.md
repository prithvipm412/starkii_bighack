# Mac4 status

Done:
- Env: .venv rebuilt with Python 3.12.16 (/opt/homebrew/bin/python3.12); torch 2.15.0, transformers 4.57.3, MPS ok; huggingface_hub 0.36.2.
- mac1 NOTE: requirements.txt pins Sphinx==9.2.0, which needs Python >= 3.13. On 3.12 I installed everything else as pinned, with Sphinx unpinned (got 9.1.1). requirements.txt is unchanged.
- analysis/get_data.py: downloads HarmBench (standard), AdvBench, XSTest, Alpaca into data_tools/output/raw/ (gitignored). Deterministic, seed 1234.
- English inputs now match the CLAUDE.md prompt format exactly ({prompt_id, split, category, source, variant="en", text}):
  raw/en_full.jsonl: h0001-h0300 harmful (200 HarmBench standard, 6 categories + 100 AdvBench "advbench_general"), s0001-s0150 harmless (130 XSTest safe, 13 x 10 types, + 20 Alpaca "general")
  raw/en_pilot.jsonl: 50+50, a subset of full with the same ids, category-balanced
  data_tools/output/direction.jsonl (= raw/en_direction.jsonl): d0001-d0128, split=direction, English only (not translated)
  raw/id_map.csv: prompt_id -> source id (no text)
- mac1 NOTE: direction rows use category="harmful"|"harmless" to tell the two sides apart, since the schema has no label field.
- baseline/run_baseline.py (python -m baseline.run_baseline --prompts <jsonl>): kn and kn_mix -> IndicProcessor + IndicTrans2 indic-en-1B (kan_Knda -> eng_Latn, trust_remote_code) -> Llama Guard 3 1B; en -> guard directly. refused = unsafe verdict; judge_score = P(unsafe). Writes results/mac4/llama-guard-3-1b_baseline.csv (CLAUDE.md naming); resumes on restart.
- NOTE kn_latn: Roman-script Kanglish goes to Llama Guard UNTRANSLATED, because IndicTrans2 only accepts Kannada script. So the baseline result for kn_latn measures the guard on raw Kanglish, not "translate then guard".

Doing: data_tools.build running for pilot, then full (HF backend, logged in as vvijetha).

Blocked:
- ai4bharat/indictrans2-indic-en-1B is still gated for vvijetha (access requested). The baseline needs it for kn/kn_mix; en-indic and Llama-Guard-3-1B are OK.

Next: build pilot.jsonl/full.jsonl -> check 20 translations -> prompts.zip + shasum -> pilot baseline.
