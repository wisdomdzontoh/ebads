# 08 — Evaluation

> Source of truth: thesis §3.8.3–3.8.4. **Replaces the previous hypothesis-testing and sensitivity-analysis plan.** No paired t-tests over 30 runs, no Shapiro–Wilk, no Cohen's d, no 270-run grid. Those depended on stochastic simulation, which the project no longer performs.

## 1. Unit of analysis

One value per **strategy × urgency tier × measure**, computed over the fixed case set ([07](./07-scenario-testing.md)). There is no distribution of run means, because there is only one deterministic run per configuration.

This is the honest consequence of deterministic testing and it must be reflected in how results are reported: **descriptive comparison and paired per-case differences, not inferential statistics over runs.**

## 2. Expectations (thesis §3.8.3)

Stated in advance so results confirm or contradict them rather than being interpreted after the fact.

| ID | Expectation | Primary measure |
|----|-------------|-----------------|
| **E1** | The urgency-adaptive strategy places a higher proportion of critical cases at tertiary facilities than the nearest-facility strategy, at the cost of some additional travel time for those cases | critical-at-tertiary; travel time (critical) |
| **E2** | The urgency-adaptive strategy performs no worse than the fixed-weight strategy on standard-urgency cases | all measures, standard tier |
| **E3** | The nearest-facility strategy produces the shortest mean travel time overall and the lowest capability match | travel time (all); capability match (all) |

**E3 concedes in advance that the baseline wins on one measure.** This is deliberate. The claim of this study is not that urgency-adaptive allocation is faster — it will not always be — but that a modest increase in travel time for critical patients purchases a substantial improvement in the clinical appropriateness of their placement, and that this is a trade worth making. Stating the expected direction of every result in advance is what allows that argument to be assessed rather than asserted.

**E2 is a non-inferiority condition.** A policy that improves outcomes for the most acute by displacing the least acute is a redistribution, not an improvement. The evaluation must be capable of detecting that outcome and reporting it as such.

## 3. Comparison procedure

For each pair of strategies and each measure:

1. Report the value per urgency tier and overall, with the difference and its direction.
2. Where a difference is claimed, support it with a **paired per-case comparison**: every strategy sees the identical case, so per-case differences are directly meaningful. Report the number of cases where each strategy did better, and the median per-case difference.
3. Report the number of cases where the strategies chose **different facilities** — if that number is small, no measure difference can be large, and this is worth knowing before interpreting anything else.

`backend/app/analysis/compare.py` consumes `measures.csv` + `decisions.jsonl` and emits the comparison table.

**Do not compute p-values over the case set.** The cases are a fixed fixture, not a random sample from a population, so a significance test would answer a question nobody asked. If a reviewer requests inferential statistics, the correct response is to explain the design, not to manufacture a test.

## 4. Robustness check

Re-run the complete case set under the alternative weight set ([09 §12](./09-parameters.md)) and reproduce the comparison table.

Reported as one of two outcomes:

- **Robust** — the direction of the fixed-weight vs urgency-adaptive difference is unchanged under the alternative weights.
- **Conditional** — the difference holds only under the primary weights, and is reported as a finding about that specific weighting rather than about urgency-adaptive allocation in general.

`backend/app/analysis/robustness.py`.

## 5. Contextual baseline

Present the scenario travel times alongside the documented manual referral figures for Greater Accra — median referral-to-arrival ≈ 5 hours, fewer than 25% of urgent cases within the WHO 2-hour window (Owen et al. 2022).

**Contextual, not experimental.** The manual figures were not generated under the same conditions and describe end-to-end referral rather than travel alone. The comparison judges whether the *magnitude* of any improvement is clinically meaningful. It is never a claim of statistical superiority over the manual process, and any wording implying otherwise is a defect.

## 6. Outputs

Under `artifacts/eval/<study_id>/`:

| File | Contents |
|------|----------|
| `comparison.csv` | strategy × measure × urgency tier, with pairwise differences |
| `per_case.csv` | one row per case per strategy: chosen facility, score, travel time, ĉ |
| `divergence.csv` | cases where strategies chose different facilities, with both scores |
| `robustness.csv` | comparison table under the alternative weight set, with robust/conditional verdict |
| `figures/` | travel time by strategy and tier; capability match by strategy and tier; critical-at-tertiary |
| `manifest.json` | parameter snapshot, case-set hash, facility-CSV hash, code commit, timestamps |

## 7. Reporting rules

- Report **all three strategies** on **all measures** across **all urgency tiers**. No selective reporting.
- Report results that contradict E1, E2 or E3 without suppression. A contradicted expectation is a finding.
- Every reported number must be reproducible from `manifest.json` and the version-controlled fixtures.
- The evaluation output maps 1:1 onto thesis Chapter Four sections.
- Where the two scoring strategies chose the same facility for most cases, say so prominently — it bounds every other claim in the chapter.
