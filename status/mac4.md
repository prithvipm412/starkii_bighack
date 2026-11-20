# Mac4 status

Done:
- Full Llama Guard baseline: 1800/1800 rows. Harmful flagged: en 96.3, kn 90.3, kn_mix 92.3, kn_latn (untranslated) 39.7 (n=300). Harmless flagged 1.3-7.3 (n=150).
- baseline_translit (kn_latn -> ITRANS->Kannada -> NLLB -> Guard), pilot: harmful kn_latn 42 -> 90%, harmless 2 -> 10%. results/mac4/llama-guard-3-1b_baseline_translit.csv.
- scorer_check.csv on mac3's 30 Gemma hand labels: label agrees with humans 33.3% (kn 30, kn_latn 30, kn_mix 40); binary refused 56.7%. Pipeline catches 1/14 human not_understood; on kn_latn humans agree with the pipeline's not_understood 1/3. Scorer validation section added to FINDINGS.
- GOTCHA: `git pull --autostash` while a run is appending to a tracked CSV swaps the file and silently loses rows. Fixed by writing long runs to logs/*_work.csv and copying when done. An "auto-push" job (not mine) also does this on mac4.
- FINDINGS.md updated with rescored Qwen (pilot64) and Gemma (mac3 rescore 3170860). The gap holds on harmful_compliance: Qwen en 2% -> kn 76%, kn_mix 52%; Gemma 0 -> 44 / 16. kn_latn is mostly not_understood (Qwen 72%, Gemma 64%). steer_gated over-refusal on harmless is REAL refusal (label refused +20..+80 pts), not not_understood. Llama-3.2 PENDING.
- Baseline translator = NLLB-200-distilled-600M kn->en (local, offline; same settings as pipeline/score.py). Pilot baseline complete (400 rows): harmful flagged en 49/50, kn 45/50, kn_mix 46/50, kn_latn (untranslated) 21/50; harmless flagged en 6, kn 4, kn_mix 3, kn_latn 1 /50. Median latency: en 177 ms, kn 424, kn_mix 404, kn_latn 113.
- summarize.py v2: adds run (main | pilot64 ...), scope (all | pilot ids only), harmful_compliance %, and label breakdown (refused / not_understood / complied %) per split.
- analysis/FINDINGS.md draft (numbers only, pilot): gap per model (Qwen, Gemma), Llama Guard en/kn_latn, projections, gated vs always, failure analysis. PENDING: Llama-3.2, Guard kn/kn_mix, full set, handlabels, translation check.
- analysis/scorer_check.py -> analysis/scorer_check.csv (once handlabels exist). Per model x variant (+ALL): n, accuracy of pipeline `refused` vs human, refused rates, confusion (pipeline refused/not x human refused / not_understood / complied_other), unmatched. Tested on synthetic labels.
  HANDLABELS FORMAT (mac1-3, results/macN/handlabels.csv, no text): prompt_id,variant,condition,human_label with human_label = refused | complied | not_understood. The old prompt_id,condition,human_refused format also works (variant defaults to en).
- analysis/summarize.py -> analysis/summary.csv: per model x condition x variant, harmful refusal % / harmless wrong-refusal % / harmful_compliance % (when the column exists), each with n, k and 95% Wilson CI, plus median latency. Skips sweep_* files and subfolders.
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

Doing: -

Blocked:
- 20-prompt translation check needs a human.

Next: baseline_translit on the full set; per-category failure analysis (analysis/failure.py); Llama-3.2 numbers when mac2 pushes; more hand labels (en, Qwen, Llama).
