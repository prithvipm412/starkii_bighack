# The Language Barrier guard (`guard/`)

A deployable 3-layer safety guard for Indian-language chatbots, built from the study's measured components.
Everything runs locally on Apple Silicon (MPS), offline (`HF_HUB_OFFLINE=1`).
It uses two models: NLLB-200-distilled-600M (kn→en translation) and Llama-Guard-3-1B.
Verdicts are JSON and never contain the input or reply text.

## Layers
| # | layer | what it does | where |
|---|---|---|---|
| 1 | **input** | `detect()` the language, then translate to English (Kannada script → NLLB `kan_Knda→eng_Latn`; Kanglish → ITRANS-to-Kannada transliteration → NLLB), then Llama Guard 3 1B on the prompt. `blocked` = verdict `unsafe`. | `guard/guard.py` |
| 2 | **steer** | gated refusal-direction steering inside the chatbot model: adds the model's English refusal direction at a middle layer when the input is non-English and the gate fires (`steer_gated`). Runs during generation, not in the guard process; `check()` reports it as a pass-through layer. | `pipeline/steer.py` (mac1) |
| 3 | **output** | translate the reply if it isn't English, then Llama Guard on (prompt, reply). This uses the same format and `p_unsafe > 0.5` threshold as the study's judge (`pipeline/score.py`). | `guard/guard.py` |

`check(text, reply=None)` runs input, then steer (pass-through), then output (only if a reply is given). It returns the first block, else `allow`.

`detect(text)` returns `en | kn | kn_latn | kn_mix`:
- **Kannada script:** the text is `kn_mix` if Latin words make up ≥15% of its words, else `kn`.
- **No Indic script:** mac1's romanized-Indic heuristic from `pipeline/data.py` (Kanglish word list, Kannada suffixes, ITRANS capitals) gives `kn_latn`; otherwise `en`.
- **Accuracy on the 1800-row study set:** en 449/450, kn_latn 437/450. All 900 kn / kn_mix rows are routed to translation; kn vs kn_mix is split ~50/50, which doesn't matter because both take the same path.

The input layer reuses `baseline/run_baseline.py`'s Translator and Guard classes exactly. On 40 pilot rows (20 harmful + 20 harmless, all 4 variants), it gives the **same block decision and the same `p_unsafe` (|Δ| = 0.0000) as `results/mac4/llama-guard-3-1b_baseline*.csv`**.

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
 "p_unsafe": float, "latency_ms": int, "layers": [ ... per-layer results ... ]}
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

## Limits
- **Output layer isn't independently scored.** Llama Guard is both the output filter and the study's judge, so scoring it with Llama Guard would be circular. It is a design layer, validated only by the 30-item human-labelled sample (`analysis/scorer_check.csv`).
- **The 3-way `label` agrees with humans only ~33% (n = 30).** So harmless "wrongly blocked" rates based on `label = refused`, and any not_understood shares, are approximate. They are never headline numbers.
- **Kanglish:**
  - The study's kn_latn is a mechanical ITRANS transliteration, which this guard reverses near-exactly (80/100 pilot prompts round-trip identically).
  - Real informal Kanglish (ad-hoc spellings) will transliterate worse, so expect lower recall than measured.
  - 13 of 450 study kn_latn prompts are detected as `en` and checked untranslated.
- **Language and model coverage:** only Kannada was evaluated. Other Indic scripts are routed to NLLB with their FLORES code but are untested. Llama Guard 3 1B is a small judge; its own errors pass straight through.
- **The steer layer needs the chatbot's weights and a direction file** (`results/macN/<model>_direction.json`). It isn't available for hosted or closed models.
- **Prompt translation:** prompts in the study were machine-translated (Google en→kn). Translation noise affects both the attack and the defence numbers.
