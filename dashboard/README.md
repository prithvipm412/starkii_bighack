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

## Views (Judge View)

| Section | Name | Description |
|---|---|---|
| **Tiles** | Kannada Gap Tiles | Per model: English refusal rate minus the lowest of `kn`, `kn_latn`, `kn_mix` in percentage points (for `condition=none`, harmful split). |
| **View 1** | The Gap (Headline Chart) | Harmful-prompt refusal rate by variant (`en`, `kn`, `kn_latn`, `kn_mix`), grouped by model (`condition=none`). Shows sample count `n` under each bar and **95% Wilson confidence interval** error bars. |
| **View 2** | Steering & Over-Refusal | **Harmful split**: refusal rate across conditions (`none` vs `steer_always` vs `steer_gated` vs `baseline`) to measure safety recovery (↑).<br>**Harmless split**: false refusal rate across conditions to verify benign queries are not over-refused (↓). Both feature 95% Wilson CIs. |
| **View 3** | Cost | Median latency (ms) per condition across models. |
| **View 4** | Where It Fails | Category × variant matrix where `steer_gated` has the lowest refusal rate across conditions. |

Header strip: project name, hypothesis, **Pilot (sample) / Full (real CSVs)** toggle,
orange **SAMPLE DATA** badge (visible only when sample data is active).

Status bar: per-model row counts + last-updated timestamp.

---

## Statistical Rigor

- **95% Wilson Score Confidence Intervals**: Rendered as thin error bars on all proportion estimates to account for small pilot sample sizes ($n$).
- **Strictly Numbers Only**: Never displays harmful prompt text or model replies in the dashboard.

---

## Real Models (from AGENTS.md)

| Mac  | Model (column in CSVs) |
|------|------------------------|
| mac1 | `qwen2.5-3b-instruct` |
| mac2 | `llama-3.2-3b-instruct` |
| mac3 | `gemma-2-2b-it` |
| mac4 | `llama-guard-3-1b` (baseline condition only) |

---

## Switching to Real Pilot CSVs

1. Drop CSVs directly into `results/mac1/`, `results/mac2/`, `results/mac3/`, or `results/mac4/`.
   Subfolders (e.g. `results/mac1/smoke/` for smoke tests) are strictly ignored.
2. Ensure the exact header matches:
   ```
   prompt_id,split,category,variant,model,condition,refused,judge_score,latency_ms,commit
   ```
   Other CSVs (`handlabels.csv`, `translation_check.csv`, etc.) are safely ignored.
3. In the dashboard header, click **Full (real CSVs)**. The orange **SAMPLE DATA** badge will disappear.

---

## Files Owned (`dashboard/` only)

```
dashboard/
  index.html                 ← single-page static dashboard (Chart.js + PapaParse + Wilson error bars)
  README.md                  ← documentation and run instructions
  sample/
    results_sample.csv       ← generated sample data with realistic refusal distributions
    generate_sample.py       ← sample generator script
```
