# 08 — Evaluation

> Source of truth: thesis §3.12.4, §3.13. Constants in [09-parameters.md §9–10](./09-parameters.md). This describes how the simulation output becomes the thesis results. It does **not** predetermine outcomes: a non-significant or negative result is a valid finding and is reported in full.

## 1. Unit of analysis
Per-run metric means (n = 30 per configuration per occupancy scenario), produced by the batch runner ([07-simulation.md §7](./07-simulation.md)).

## 2. Hypotheses (thesis Table 3.9)

| ID | Statement | Primary metric | Comparison |
|----|-----------|----------------|------------|
| H1 | Weighted (Algo 2) yields significantly lower ATBP than Greedy (Algo 1) | ATBP | Algo 1 vs 2, all three scenarios |
| H2 | Urgency-Adaptive (Algo 3) yields significantly lower ATBP **and** higher capability-match for critical patients than Algo 2 | ATBP; CM (critical) | Algo 2 vs 3, mixed-urgency runs, all scenarios |
| H3 | Both Algo 2 and Algo 3 yield significantly lower FRR than Algo 1 at 100% occupancy | FRR | Algo 1 vs 2, and Algo 1 vs 3, Scenario C |

These are directional but **not predetermined**. If H1 fails under some occupancy, that is reported. Because Algo 3 prioritises critical patients, it may place standard patients slightly worse; the analysis reports the effect on **every** urgency tier, characterising the trade-off rather than only the critical-patient benefit.

## 3. Statistical procedure (thesis §3.13.2)

For each comparison:
1. Compute the 30 paired per-run means for each configuration.
2. **Normality**: Shapiro–Wilk on the paired differences.
3. **Test**: paired t-test if normal; otherwise Wilcoxon signed-rank.
4. **Effect size**: Cohen's d (paired).
5. Report: test name, statistic, df (t-test), p-value, Cohen's d, and the mean difference with direction. Significant at **α = 0.05**.

Pairing is valid because compared configurations share the same seeded facility state and seed at each run index ([07-simulation.md §7](./07-simulation.md)).

`backend/app/analysis/statistics.py` implements this; it consumes the runner's per-run dataset and emits a results table (one row per comparison per scenario).

## 4. Sensitivity analysis (thesis §3.13.3)

Re-run the **main grid** under parameter variants to test robustness:

| Family | Configurations | Source |
|--------|----------------|--------|
| Weights | 4 (default + 3 variants) | [09 §10](./09-parameters.md) |
| Radii | 3 (default + 2 variants) | [09 §10](./09-parameters.md) |
| Capability matrix | 2 (default + steeper critical 1.0/0.4/0.1) | [09 §10](./09-parameters.md) |

For each variant, recompute the hypothesis tests. A result that holds under the default **and all variants** is reported as robust; a result that holds only under the default is reported as a **conditional** finding. `backend/app/analysis/sensitivity.py` drives this and tabulates which hypotheses survive which variants.

## 5. Contextual baseline comparison (thesis §3.13.4)

Present simulated ATBP alongside the documented manual referral times for Greater Accra — median referral-to-arrival ≈ 5 hours, <25% of urgent cases within the WHO 2-hour window (Owen et al., 2022). This is **contextual, not experimental**: the manual figures were not generated under the same conditions, so the comparison judges whether the *magnitude* of any improvement is clinically meaningful — never a claim of statistical superiority over the manual process.

## 6. Outputs (what the evaluation produces)

Under `artifacts/eval/<study_id>/`:
- `per_run_metrics.parquet` — n=30 per configuration per scenario (ATBP, FRR, MCEE, CM, CM-critical).
- `hypothesis_tests.csv` — one row per comparison per scenario (test, statistic, df, p, Cohen's d, mean diff).
- `sensitivity_results.csv` — hypothesis survival across all variant configurations.
- `figures/` — per-scenario metric plots (Algo 1/2/3) for the thesis Chapter 4.
- `study_manifest.json` — seeds, parameter snapshot, distance-matrix hash, code commit, timestamps (full reproducibility record).

## 7. Reporting rules
- Report all three algorithms on all metrics, all scenarios, all urgency tiers.
- Report negative/null results without suppression (thesis ethics commitment).
- Every reported number is reproducible from `study_manifest.json` + the recorded seeds.
- The evaluation report maps 1:1 onto thesis Chapter 4 sections.
