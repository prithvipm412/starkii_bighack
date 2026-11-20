# Mac4 status

Done:
- Pilot baseline (partial, 200/400 rows) in results/mac4/llama-guard-3-1b_baseline.csv. Guard flag rate: harmful en 49/50 (98%), harmful kn_latn untranslated 21/50 (42%); harmless en 6/50 (12% wrong refusals), harmless kn_latn 1/50 (2%). Median latency 114 ms.
- TRANSLATION = GOOGLE TRANSLATE for the whole study (IndicTrans2 download ~118 KB/s, not viable). analysis/build_google.py: kn = Google en->kn; kn_latn = mac2 transliterate (ITRANS); kn_mix = mac2 TERM_PATTERN masked + Google + restored. Same schema/4 variants as data_tools.build.
- prompts_full.zip (data_tools/output/full.jsonl): 1800 rows = 450 prompts (300 harmful + 150 harmless) x 4 variants, 0 failed; pilot rows identical to full. shasum 576bdafc3def979d8f900b9fe3fd47dd8adcfa3a
- prompts_pilot_v2.zip (FULL pilot, data_tools/output/pilot.jsonl): 400 rows = 100 prompts (50 harmful + 50 harmless) x 4 variants, 0 failed. shasum f7be0bf20c32cbe5bc25d8af4d859e4af346c459 (supersedes the mini pilot)
- prompts_pilot.zip (MINI pilot, data_tools/output/pilot.jsonl): 160 rows = 40 prompts (20 harmful + 20 harmless, 18 categories) x 4 variants. shasum d143f595aa4d97a73550e3b82dbcf88447f2f678
- prompts_direction.zip (data_tools/output/direction.jsonl, 128 English rows d0001-d0128): shasum 644d06b86e70c12e6ebf79182a3be076a09fef82
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

Doing: pilot baseline for kn and kn_mix (200 rows). Waiting on the kn->en translator decision (Google vs IndicTrans2 indic-en, ~1.4 GB still to download).

Blocked: -

Next: build pilot.jsonl/full.jsonl -> check 20 translations -> prompts.zip + shasum -> pilot baseline.
