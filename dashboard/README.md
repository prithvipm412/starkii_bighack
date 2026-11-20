# THE LANGUAGE BARRIER — Results Dashboard

> **Tagline**: Do small AI models stop refusing harmful requests when you switch to Kannada or Kanglish?  
> **Core Question**: Can a gated refusal steer close the gap without over-refusing harmless questions?

---

## Open the Dashboard

Run from the **repository root** (not from inside `dashboard/`):

```bash
python3 -m http.server 8000
```

Then open: **<http://localhost:8000/dashboard/>**

This serves the whole repository root so that relative paths to `../results/mac*/` resolve cleanly in the browser. Zero Node.js or build steps required.

---

## Architecture & Layout

### 1. Sticky Top Navigation (`#top-nav`)
- **Brand & Sections**: `THE LANGUAGE BARRIER` | `Overview` | `Results` | `Gate tuning` | `Method`
- **Active Scrollspy**: Highlights the current section on scroll with smooth scrolling (`scroll-behavior: smooth`).
- **Data Source Control**: Toggle between **Full (real)** [default] and **Show sample data**. The orange `SAMPLE DATA` badge is strictly shown only in sample mode.

### 2. Homepage & Hero (`#overview`)
- **Animated Background**: Full-viewport `<canvas>` featuring 35 floating elements in luminous light yellow tones (`#D9B44A` / `#E5C86C`) (outline padlocks, keys, shields, and neutral multilingual words: *"no"*, *"refuse"*, *"safe"*, *"guardrail"*, *"language"*, *"beda"*, *"illa"*, *"ಬೇಡ"*, *"ಇಲ್ಲ"*, *"ಭಾಷೆ"*).
- **Subtle Dynamics**: Slow drift, gentle rotation, soft opacity fade (`0.36` to `0.56`), mouse parallax tracking, and a clear zone behind hero copy. Pauses when the tab is hidden and respects `prefers-reduced-motion`.
- **Live Stat Cards**: Dynamically calculated from loaded CSVs:
  - **Largest Safety Gap**: English vs lowest Kannada refusal rate drop across models.
  - **Llama Guard Baseline**: English vs Kanglish moderation flag rate.
  - **Gemma Gated Steering**: Harmful refusal recovery vs harmless wrong-refusal rate.
- **How It Works Strip**: 3-step pipeline (`Translate prompts → Measure refusal → Steer with a gate`).
- **Action Buttons**: Smooth-scroll shortcuts to `View results` and `Gate tuning`.

### 3. Results Dashboard (`#results`)
- **Filters & Metrics**: Real-time filtering by Model, Variant, Category, and Metric toggle (`refused` | `harmful_compliance`).
- **Kannada Safety Gap Tiles**: English refusal minus the lowest among Kannada variants (`kn`, `kn_latn`, `kn_mix`) for undefended models and Llama Guard baseline.
- **View 1 — The Gap**: Harmful refusal rate by variant with **95% Wilson confidence intervals** and sample count $n$ under every bar, plus `llama-guard-3-1b (baseline)`.
- **View 2 — Steering Evaluation**: Harmful safety recovery (↑) vs Harmless over-refusal check (↓) across conditions (`none`, `steer_always`, `steer_gated`, `baseline`).
- **View 2.5 — Response Classification Breakdown**: Stacked bar breakdown (`refused`, `not_understood`, `complied`) active when `label` column is present.
- **View 3 — Cost**: Median generation latency (ms) per condition.
- **View 4 — Where It Still Fails**: Category $\times$ variant matrix where `steer_gated` has the lowest refusal rate.

### 4. Gate Tuning (`#gate-tuning`)
- **View 2.6 — Pareto Trade-off Curve**: Reads parameter sweeps (`results/mac*/sweep_*_a<A>_t<T>.csv`) and plots Harmful Kannada refusal (↑) vs Harmless wrong-refusal (↓) per $(\alpha, \tau)$ setting with tabular data.

### 5. Method (`#method`)
- Experimental methodology covering prompt generation across 4 variants (`en`, `kn`, `kn_latn`, `kn_mix`), English contrastive refusal direction extraction, activation gating, and Llama Guard baseline moderation.

---

## Statistical & Safety Rigor

- **Offline-First Typography**: Clean system font stacks for body and serif headings (no font CDN requests, ensuring full reliability on venue Wi-Fi). Tabular figures (`tabular-nums`) on all numbers and rates.
- **Strictly Numbers Only**: Never displays prompt text or model replies anywhere.
- **Wilson Score Intervals**: 95% Wilson confidence intervals rendered as 1px error bars on all proportion estimates.
- **Subfolder Isolation**: Automatically ignores nested directories (e.g., `smoke/`, `pilot64/`).

---

## Files Owned (`dashboard/` only)

```
dashboard/
  index.html                 ← Complete single-page dashboard & homepage
  README.md                  ← Documentation and setup instructions
  sample/
    results_sample.csv       ← Synthetic sample data for testing distributions
    sweep_*.csv              ← Synthetic sweep CSVs for testing gate tuning
    generate_sample.py       ← Sample data generation script
```
