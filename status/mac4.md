# Mac4 status

Done:
- analysis/get_data.py: downloads HarmBench (standard), AdvBench, XSTest, Alpaca into data_tools/output/raw/ (gitignored). Deterministic, seed 1234.
- English inputs now match the CLAUDE.md prompt format exactly ({prompt_id, split, category, source, variant="en", text}):
  raw/en_full.jsonl: h0001-h0300 harmful (200 HarmBench standard, 6 categories + 100 AdvBench "advbench_general"), s0001-s0150 harmless (130 XSTest safe, 13 x 10 types, + 20 Alpaca "general")
  raw/en_pilot.jsonl: 50+50, a subset of full with the same ids, category-balanced
  data_tools/output/direction.jsonl (= raw/en_direction.jsonl): d0001-d0128, split=direction, English only (not translated)
  raw/id_map.csv: prompt_id -> source id (no text)
- mac1 NOTE: direction rows use category="harmful"|"harmless" to tell the two sides apart, since the schema has no label field.
- baseline/run_baseline.py (python -m baseline.run_baseline --prompts <jsonl>): kn/kn_mix -> IndicTrans2 indic-en; kn_latn -> ITRANS->Kannada script first (inverse of mac2's transliterate) -> Llama Guard 3 1B. refused = unsafe verdict; judge_score = P(unsafe); writes results/mac4/llama-guard-3-1b_baseline.csv (CLAUDE.md naming); resumes on restart. Uses the variant label to choose preprocessing, which gives the baseline an advantage worth stating on the slides.

Doing: building the Kannada pilot/full with data_tools.build.
Blocked:
- No HF login on mac4. ai4bharat/indictrans2-en-indic-1B, indictrans2-indic-en-1B and meta-llama/Llama-Guard-3-1B are all gated. Needs the licenses accepted and hf auth login.
Next: build pilot.jsonl/full.jsonl -> check 20 translations -> prompts.zip + shasum -> pilot baseline.
