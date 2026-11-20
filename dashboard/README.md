# Bhasha Kavach — Results Dashboard

## Open it

Run from the **repo root** (not from inside `dashboard/`):

```bash
python3 -m http.server 8000
```

Then open: **<http://localhost:8000/dashboard/>**

This serves the whole repository root, ensuring `../results/mac*/` relative paths resolve correctly.
No Node.js or build steps required.

---

## Views

| Section | Name | Description |
|---|---|---|
| **Tiles** | Kannada Gap Tiles | Per model: English refusal rate minus the lowest of `kn`, `kn_latn`, `kn_mix` in percentage points (for undefended condition and Llama Guard baseline). |
| **View 1** | The Gap (Headline Chart) | Harmful-prompt refusal rate by variant (`en`, `kn`, `kn_latn`, `kn_mix`), grouped by model (`condition=none`), plus the **Llama Guard baseline** (`condition=baseline`) as its own bar group. Shows sample count `n` under each bar and **95% Wilson confidence intervals**. |
| **View 2** | Steering & Over-Refusal | **Harmful split**: refusal rate across defense conditions (`none` vs `steer_always` vs `steer_gated` vs `baseline`) to measure safety recovery (↑).<br>**Harmless split**: false refusal rate across conditions to verify benign queries are not over-refused (↓). |
| **View 2.5** | Response Breakdown | Stacked bars per variant showing classification: `refused` (safe refusal), `not_understood` (clarification/language barrier), and `complied` (jailbreak). Automatically enables when `label` column is present in CSVs. |
| **View 2.6** | Gate Tuning (Sweep Curve) | Reads `results/mac*/sweep_*.csv` (`_a<A>_t<T>`) and plots the Pareto trade-off curve per model: Harmful Kannada refusal (↑ Safety target) vs Harmless wrong-refusal (↓ Over-refusal penalty). |
| **View 3** | Cost | Median generation latency (ms) per condition across models. |
| **View 4** | Where It Fails | Category × variant matrix where `steer_gated` has the lowest refusal rate across conditions. |

Header strip: project name, hypothesis, **Full (real CSVs) [default] / Show sample data** toggle.
The orange **SAMPLE DATA** badge is visible only when sample data is explicitly selected and never in real mode.

Filters bar: Model, Variant, Category filters, and **Metric toggle** (`refused` | `harmful_compliance`).

---

## Statistical Rigor

- **95% Wilson Score Confidence Intervals**: Rendered as thin error bars on all proportion estimates to account for small pilot sample sizes ($n$).
- **Strictly Numbers Only**: Never displays harmful prompt text or model replies in the dashboard.

---

## Real Models (from AGENTS.md)

| Mac  | Model (column in CSVs) |
|------|------------------------|
| mac1 | `Qwen/Qwen2.5-3B-Instruct` |
| mac2 | `meta-llama/Llama-3.2-3B-Instruct` |
| mac3 | `google/gemma-2-2b-it` |
| mac4 | `llama-guard-3-1b` (baseline condition only) |

---

## Data Loading & Sweep Handling

1. Real CSVs are read directly from `results/mac1/`, `results/mac2/`, `results/mac3/`, and `results/mac4/`.
   Subfolders (e.g. `results/mac1/smoke/`) are strictly ignored.
2. Core schema columns:
   ```
   prompt_id,split,category,variant,model,condition,refused,judge_score,latency_ms,commit
   ```
   Optional new columns `label` and `harmful_compliance` are automatically recognized when present.
3. Parameter sweeps matching `results/mac*/sweep_*_a<A>_t<T>.csv` are automatically loaded into the **Gate Tuning** view.

---

## Files Owned (`dashboard/` only)

```
dashboard/
  index.html                 ← single-page static dashboard (Chart.js + PapaParse + Wilson error bars)
  README.md                  ← documentation and run instructions
  sample/
    results_sample.csv       ← generated sample data with realistic refusal distributions
    sweep_*.csv              ← sample parameter sweep CSVs for testing trade-off curves
    generate_sample.py       ← sample generator script
```
