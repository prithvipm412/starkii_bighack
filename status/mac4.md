# Mac4 status

Done:
- analysis/get_data.py: downloads HarmBench (standard), AdvBench, XSTest, Alpaca into data_tools/output/raw/ (gitignored); deterministic (seed 1234).
- English splits in data_tools/output/raw/: en_full.jsonl (300 harmful + 150 harmless), en_pilot.jsonl (50+50, subset of full, category-balanced), en_direction.jsonl (64+64, disjoint from eval).
- Format (no PLAN.md/prompt format found, so I chose this one; mac2 please match or tell me):
  {"prompt_id","split","label":"harmful|harmless","category","source","lang":"en","text"}
  ids: hb_<BehaviorID>, adv_<row>, xs_<id>, alp_<idx>.
- Harmful = 200 HarmBench standard (6 semantic cats) + 100 AdvBench ("advbench_general"). Harmless = 130 XSTest safe (13 x 10 types) + 20 Alpaca ("general"). Direction = AdvBench 64 + Alpaca 64.

Doing: waiting on mac2 data_tools.build to make pilot/full/direction.jsonl (Kannada).
Blocked: -
Next: translation check (20), prompts.zip + shasum, baseline/run_baseline.py (needs HF token for gated Llama-Guard-3-1B; venv is empty, Python 3.14).
