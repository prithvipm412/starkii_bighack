# The Language Barrier guard (`guard/`)

A deployable 3-layer safety guard for Indian-language chatbots, built from the study's measured components.
Everything runs locally on Apple Silicon (MPS), offline (`HF_HUB_OFFLINE=1`).
It uses two models: NLLB-200-distilled-600M (kn→en translation) and Llama-Guard-3-1B.
Verdicts are JSON and never contain the input or reply text.

## Layers
| # | layer | what it does | where |
|---|---|---|---|
| 1 | **input** | Score the raw prompt and any available Kannada-script and English views with Llama Guard 3 1B. The maximum score determines the verdict. | `guard/guard.py` |
| 2 | **steer** | gated refusal-direction steering inside the chatbot model: adds the model's English refusal direction at a middle layer when the input is non-English and the gate fires (`steer_gated`). Runs during generation, not in the guard process; `check()` reports it as a pass-through layer. | `pipeline/steer.py` (mac1) |
| 3 | **output** | translate the reply if it isn't English, then Llama Guard on (prompt, reply). This uses the same format and `p_unsafe > 0.5` threshold as the study's judge (`pipeline/score.py`). | `guard/guard.py` |

`check(text, reply=None)` runs input, then steer (pass-through), then output (only if a reply is given). It returns the first block, else `allow`.

`detect(text)` returns `en | kn | kn_latn | kn_mix`:
- **Kannada script:** the text is `kn_mix` if Latin words make up ≥15% of its words, else `kn`.
- **Latin script:** recognize common Kannada words and informal spellings. Two Kannada signals covering at least 20% of Latin words trigger `kn_latn`, with the existing romanized-Indic detector as a fallback.
- **Kanglish:** map common phonetic spellings, convert recognizable ITRANS words with the installed `indic-transliteration` package, and preserve unrecognized Latin words for NLLB to handle as code-mixed text.

Input scoring uses the cached model's user-only chat template with typed text content. The usual threshold is 0.5. With the default threshold, standalone English requests matching the software process-management pattern use 0.85. The pattern must match the entire input. The API exposes the applied threshold and the original model score.

## Run
```bash
source .venv/bin/activate            # Python 3.12, repo root
# CLI: prints a JSON verdict; exit code 0 allow, 1 block, 2 error
python -m guard.cli "What is the capital of Karnataka?"
python -m guard.cli "<user prompt>" --reply "<chatbot reply>"   # also runs the output layer

# Local HTTP API with CORS (*), for dashboard/
python -m guard.server --port 8787 --preload
curl -s -X POST http://127.0.0.1:8787/check -d '{"text": "...", "reply": "... (optional)"}'
curl -s http://127.0.0.1:8787/health
```
In Python: `from guard import LanguageBarrierGuard; LanguageBarrierGuard().check(text, reply)`.

**Verdict:**
```json
{"verdict": "allow|block", "blocked": bool, "layer": "input|output|null", "detected": "en|kn|kn_latn|kn_mix",
 "p_unsafe": float, "scores": {"raw": float, "transliterated": float|null, "english": float|null},
 "latency_ms": int, "layers": [ ... per-layer results ... ]}
```

**Server behaviour:**
- Binds to 127.0.0.1 and caps request bodies at 32 KB.
- Bad JSON returns 400.
- Model calls are serialised behind a lock.
- Logs record only method, path and status.

## Measured latency (MacBook Air M4, MPS, models warm; median ms)
| layer | en | kn | kn_mix | kn_latn | source |
|---|---|---|---|---|---|
| input | 179 | 448 | 447 | 422 | full baseline, n = 450 per variant (kn_latn: baseline_translit pilot, n = 100) |
| output | 108 | 599 | – | – | 10 harmless synthetic prompt+reply pairs per language |
| steer (in-model) | +24 (Qwen), +2 (Gemma) | | | | steer_gated vs none per prompt, pilot64 |
| cold start | ~2.6–4.6 s | | | | first call loads both models; use `--preload` |

## Effect (study numbers; primary metric = harmful_compliance, Llama Guard on the translated reply)
From `analysis/combined.csv` (Qwen2.5-3B-Instruct, full set, 256 tokens, n = 300 harmful / 150 harmless per variant).

**Harmful pass-through % (prompt not blocked AND reply harmful):**
| variant | model alone | + input layer |
|---|---|---|
| kn | 65.3 | 2.7 |
| kn_mix | 46.7 | 1.3 |
| kn_latn | 4.0 | 0.3 |
| en | 6.7 | 0.0 |

- **Cost:** harmless prompts wrongly blocked rise 2–5 points.
- **Steering numbers** (steer_only, input+steer): PENDING until the full steer_gated runs land. See FINDINGS.md "Layered guard".

## Input smoke test

Run `python -m guard.smoke_test` using the cached models. Standard output is one verdict and score per case, with 10 harmless cases followed by 10 harmful cases across the four variants.

| Metric | Before | After |
|---|---:|---:|
| Harmful cases blocked | 7/10 | 10/10 |
| Harmless cases wrongly blocked | 1/10 | 0/10 |
| Harmful Kanglish regression case | allow (0.1192) | block (0.9903) |
| Python process regression case | block (0.8355) | allow (0.8355) |

These are local smoke-test results. The study numbers above describe the original evaluation.

## Limits
- **Output layer isn't independently scored.** Llama Guard is both the output filter and the study's judge, so scoring it with Llama Guard would be circular. It is a design layer, validated only by the 30-item human-labelled sample (`analysis/scorer_check.csv`).
- **The 3-way `label` agrees with humans only ~33% (n = 30).** So harmless "wrongly blocked" rates based on `label = refused`, and any not_understood shares, are approximate. They are never headline numbers.
- **Kanglish:** informal spellings and unrecognized words can still be mistransliterated or misdetected. The smoke test covers only a small sample.
- **Language and model coverage:** only Kannada was evaluated. Other Indic scripts are routed to NLLB with their FLORES code but are untested. Llama Guard 3 1B is a small judge; its own errors pass straight through.
- **The steer layer needs the chatbot's weights and a direction file** (`results/macN/<model>_direction.json`). It isn't available for hosted or closed models.
- **Prompt translation:** prompts in the study were machine-translated (Google en→kn). Translation noise affects both the attack and the defence numbers.
