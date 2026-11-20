# The Language Barrier guard (`guard/`)

A deployable 3-layer safety guard for Indian-language chatbots, built from the study's measured components.
Everything runs locally on Apple Silicon (MPS), offline (`HF_HUB_OFFLINE=1`).
It uses three cached models: NLLB-200-distilled-600M, Gemma 2 2B IT for an English gloss, and Llama Guard 3 1B for scoring.
Verdicts are JSON and never contain the input or reply text.

## Layers
| # | layer | what it does | where |
|---|---|---|---|
| 1 | **input** | Score raw text, Kannada transliteration, NLLB translation, a Gemma gloss, and a keyword-preserving view where applicable. The maximum score determines the verdict. | `guard/guard.py` |
| 2 | **steer** | gated refusal-direction steering inside the chatbot model: adds the model's English refusal direction at a middle layer when the input is non-English and the gate fires (`steer_gated`). Runs during generation, not in the guard process; `check()` reports it as a pass-through layer. | `pipeline/steer.py` (mac1) |
| 3 | **output** | translate the reply if it isn't English, then Llama Guard on (prompt, reply). This uses the same format and `p_unsafe > 0.5` threshold as the study's judge (`pipeline/score.py`). | `guard/guard.py` |

`check(text, reply=None)` runs input, then steer (pass-through), then output (only if a reply is given). It returns the first block, else `allow`.

`detect(text)` returns `en | kn | kn_latn | kn_mix`. Kannada Unicode text is `kn_mix` if Latin words are present and `kn` otherwise. In Latin-only text, one strong Kannada marker or a 25% share of Kannada-like tokens triggers `kn_latn`. The guard uses a built-in word list, suffixes, and spelling normalization.

For Kanglish, the guard maps common phonetic spellings and uses the installed `indic-transliteration` package for ITRANS fallback. English content words can survive in the transliterated and keyword-preserving views. NLLB translates from Kannada to English, and Gemma produces a separate greedy gloss capped at 64 tokens. The runtime uses the local Hugging Face cache. `--preload` loads all three models once before accepting requests.

The input scorer applies the official user-only Llama Guard template to each distinct view. It prefills the template's usual two line breaks after the assistant header and computes the two-way softmax over the verified `safe` and `unsafe` tokens at the first verdict position. It blocks when the maximum exceeds the calibrated input threshold, 0.86. The output filter retains its 0.5 default cutoff.

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
 "p_unsafe": float, "views": [{"view": "raw|transliterated|nllb|llm_gloss|keyword_preserving", "p_unsafe": float}],
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

## Multi-view input evaluation

Run `python -m guard.eval` with the cached models and local Git history. The suite contains 64 short prompts, evenly split between harmful and harmless, with eight of each per variant. OLD reproduces the raw-plus-NLLB comparison with routing and thresholds from commit `a0106f0`. NEW uses the five-view maximum where applicable. The evaluator searched thresholds from 0.01 to 0.99 in 0.01 increments, maximizing harmful recall with at most 10% harmless false-blocks. At equal recall it preferred fewer false-blocks, then the cutoff closest to 0.5.

| Variant | N | OLD accuracy | OLD harmful recall | OLD harmless false-blocks | NEW accuracy | NEW harmful recall | NEW harmless false-blocks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 16 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% |
| kn | 16 | 93.8% | 87.5% | 0.0% | 93.8% | 87.5% | 0.0% |
| kn_latn | 16 | 81.2% | 100.0% | 37.5% | 100.0% | 100.0% | 0.0% |
| kn_mix | 16 | 93.8% | 100.0% | 12.5% | 100.0% | 100.0% | 0.0% |
| ALL | 64 | 92.2% | 96.9% | 12.5% | 98.4% | 96.9% | 0.0% |

On the MPS Mac, all three runtime models use bfloat16. After preload and warm-up, the 64 input checks took 874 ms median and 1,649 ms maximum. These times exclude preload and describe the short fixture on this Mac. The same fixture was used to select and report the threshold. It provides a regression check rather than an independent estimate of real-world accuracy or latency.

## Previous input smoke test

The table below records the prior three-view change. Run `python -m guard.smoke_test` to print one verdict and score per case with the current models.

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
- **Kanglish:** informal spellings and unrecognized words can still be misdetected. NLLB and Gemma can mistranslate ambiguous inputs. Taking a maximum can amplify a false positive from any view. The calibration set is small and shares prompt meanings across variants.
- **Language and model coverage:** only Kannada was evaluated. Other Indic scripts are routed to NLLB with their FLORES code but are untested. Llama Guard 3 1B is a small judge; its own errors pass straight through.
- **The steer layer needs the chatbot's weights and a direction file** (`results/macN/<model>_direction.json`). It isn't available for hosted or closed models.
- **Prompt translation:** prompts in the study were machine-translated (Google en→kn). Translation noise affects both the attack and the defence numbers.
