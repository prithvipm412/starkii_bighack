# The Language Barrier: slide outline (8 slides)
Team Stark Industry Interns · The Big Hack 2.0 · PS R2. Numbers are from `analysis/FINDINGS.md` (full set, 256 tokens, n = 300 harmful / 150 harmless per cell unless marked pilot, n = 50). ASR = attack success rate = % of harmful prompts whose reply Llama Guard 3 1B judges unsafe. No prompt text or model replies on any slide.

## 1. The problem: safety stops at the language barrier
- Small open chat models are safety-tuned mostly in English; Indian-language chatbots are built on them.
- Same harmful request, 4 styles: English, Kannada script, Kanglish (Latin letters), Kannada-English code-mix.
- Question: how much safety is lost, why, and what fixes it offline on a laptop?

## 2. Setup
- 3 models: Qwen2.5-3B, Llama-3.2-3B, Gemma-2-2B; local on Apple Silicon, greedy, 256 new tokens.
- 450 prompts (300 harmful: HarmBench + AdvBench; 150 harmless: XSTest + Alpaca) × 4 styles = 1,800 per model and condition.
- Judge: reply → NLLB to English → Llama Guard 3 1B. Primary metric ASR; secondary = harmless prompts wrongly blocked.

## 3. The gap is 6–20×
- ASR, Kannada script vs English: Llama 62.0% vs 10.7% (5.8×), Qwen 65.3% vs 6.7% (9.7×), Gemma 40.0% vs 2.0% (20×).
- Code-mix: Llama 57.3%, Qwen 46.7%, Gemma 27.3% (5.4×, 7.0×, 13.7× English).
- Kanglish: Llama 34.3%, Gemma 18.3%; Qwen 4.0% mostly because it doesn't understand Kanglish (82% of harmful replies labelled not_understood by the phrase label, which is approximate).

## 4. Why: the internal harm signal fades
- The refusal direction (English harmful − harmless activations) separates English prompts almost perfectly: AUROC 0.993 Llama, 0.971 Qwen, 0.976 Gemma.
- In Kannada script: 0.646 Llama, 0.633 Qwen, 0.816 Gemma; Kanglish on Llama: 0.498 (chance).
- Qwen layer 23 projections: English harmful 40.6, Kannada harmful 17.2, Kannada harmless 15.5. The model barely "sees" harm in Kannada.

## 5. Fix 1: gated steering (helps, over-refuses, backfires on Llama)
- Qwen: Kannada ASR 65.3 → 28.3, code-mix 46.7 → 17.0; English unchanged (6.7 → 6.3).
- Cost: harmless Kannada wrongly blocked 4.0 → 45.3, code-mix 12.0 → 72.7. Gemma: ASR 40.0 → 27.7, harmless 11.3 → 26.0.
- Llama (pilot, n = 50): ASR rises, Kannada 58 → 78. Always-on steering refuses ~100% of everything (Qwen English harmless 24 → 100%).

## 6. Fix 2: translate-then-guard (works)
- NLLB translate the prompt (Kanglish: back-transliterate first), then Llama Guard 3 1B: ASR under 4% in every cell (max 3.7%, Gemma Kannada).
- Cost: +2.0 to +7.3 points harmless wrongly blocked; latency 179 ms (English) to 448 ms (Kannada, incl. translation).
- Back-transliteration is essential: harmful Kanglish flagged 39.7% raw vs 90.7% back-transliterated. Guard + steering: ASR 0–2.7%.

## 7. Failure analysis
- No steering setting met our pre-written rule (lowest ASR with harmless refusal ≤ +10 pts over none). Closest: Qwen L26 α35.4, ASR 8% but harmless Kannada +30 pts.
- Root cause: harmful and harmless Kannada prompts overlap on the English direction, so no gate threshold separates them; steering turns "don't understand" into refusal.
- Truncation checked: 64 vs 256 tokens flips only 6 of 150 Qwen refusal decisions. What still beats every layer: 0–3.7% of harmful prompts per cell (IDs in `analysis/missed.csv`).

## 8. Limits and takeaways
- Limits: prompts machine-translated (Google); 1B judge after machine translation, ASR not hand-checked; phrase label agrees with humans 33% (n = 30); Kanglish is ITRANS (80/100 round-trip exactly), so its guard numbers are an upper bound.
- Takeaway: English-only safety tuning leaves a 6–20× gap; the model's own refusal signal is too weak in Kannada to gate on.
- Ship: translate-then-guard as the input layer (`guard/`, offline, ~0.45 s per prompt); steering only as an optional extra once it is calibrated on Kannada.
