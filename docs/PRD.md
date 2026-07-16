# EBADS — Product Requirements Document (PRD)

> Source of truth: thesis Chapters 1–3. This PRD restates *what must be built and why*; it does not add features. Anything beyond the thesis is tagged `[IMPL]`.

## 1. Problem

Emergency patients in Ghana are repeatedly turned away from facilities reporting no available bed ("No Bed Syndrome"), with documented fatal cases (Yevoo et al., 2023; Citi Newsroom, 2018). The cause is not bed scarcity alone (~0.7 beds/1,000; referral hospitals at 120–150% capacity — Ghana News Agency, 2026) but a **coordination failure**: at the moment of an emergency, no party knows which reachable facility has an appropriate free bed. Existing communication tools (e.g. WhatsApp referral systems) cut messaging time but leave the matching problem unsolved — median referral-to-arrival ~5 hours, <25% of urgent cases within the WHO 2-hour window (Owen et al., 2022).

## 2. What EBADS is

An algorithm-driven decision-support system that, given an emergency (patient location, urgency, required bed type), recommends the best reachable facility with an appropriate available bed — adapting the recommendation to patient urgency. It is a **single-dispatcher decision-support tool**, not an autonomous controller and not a replacement for clinical judgement.

## 3. Objectives (traceable to thesis §1.3)

| ID | Objective | Primary deliverable |
|----|-----------|---------------------|
| O1 | Establish requirements from the literature and Ghana's referral context | This documentation set, grounded in Chapters 1–2 |
| O2 | Design an allocation engine with a vendor-agnostic data-source abstraction | Backend engine + Bridge data-source layer ([01](./01-architecture.md)) |
| O3 | Develop and evaluate three matching algorithms via multi-occupancy simulation with formal hypothesis testing | Algorithms ([03](./03-algorithms.md)) + simulation ([07](./07-simulation.md)) + evaluation ([08](./08-evaluation.md)) |
| O4 | Develop a cross-platform mobile app with an online dispatcher interface and an offline informational mode | Mobile app ([05](./05-mobile-app.md)) |
| O5 | Assess robustness (sensitivity analysis) and clinical meaningfulness (contextual baseline comparison) of the results | Sensitivity + baseline ([08](./08-evaluation.md)) |

## 4. In scope

- Allocation engine: facility registry, bed-data-source abstraction (Bridge), emergency request + allocation service, notification service, dynamic algorithm selector.
- Three algorithms: Greedy Nearest-Facility (baseline), Weighted Multi-Criteria Scoring (fixed weights), Urgency-Adaptive Weighted Scoring (deployed default).
- Discrete-event simulation: automatic + interactive modes, three occupancy scenarios (75/90/100%), virtual clock, precomputed distance matrix.
- Evaluation: three hypotheses, paired statistical tests, sensitivity analysis, contextual baseline comparison.
- Mobile app: Dispatch, Facility Map, Simulation, Settings screens; offline informational (read-only) mode.

## 5. Out of scope / non-goals (thesis §1.7–1.8)

- **No offline matching.** Offline mode is read-only display of cached data; no algorithm runs on the device. (Production resolution noted, not built: a single shared algorithm module callable from both runtimes.)
- **No live EMR/hospital integration in the prototype.** Only `SimulationDataSource` is implemented; the other three data sources are specified at the interface level.
- **No true cross-patient bed contention** (no reclaiming a bed already assigned to one patient for a later higher-urgency arrival).
- **No human-subjects research.** No interviews, no patient data; evaluation is simulation-only on synthetic + public data (see [PRD §9](#9-ethics--data)).
- **No multi-region / rural generalisation claims.** Calibrated to Greater Accra urban conditions.
- **Not production-hardened.** Full authentication, encryption-at-rest, and rate limiting are specified but not fully implemented in the prototype.

## 6. Users

- **Primary:** a National Ambulance Service (NAS) dispatcher operating under time pressure (single-dispatcher model).
- **Secondary `[IMPL]`:** a facility administrator registering facilities and bed capacities via the API/admin surface.

## 7. Success criteria (the hypotheses — thesis §3.12.4)

The system is considered successful if the simulation can **test** these hypotheses with statistical rigour (significance is a research finding, not a build pass/fail). See [08-evaluation.md](./08-evaluation.md).

- **H1** — Weighted (Algo 2) yields significantly lower ATBP than Greedy (Algo 1) across all three occupancy scenarios.
- **H2** — Urgency-Adaptive (Algo 3) yields significantly lower ATBP **and** higher capability-match for critical patients than Algo 2 in mixed-urgency scenarios.
- **H3** — Both Algo 2 and Algo 3 yield significantly lower FRR than Algo 1 at 100% occupancy.

**Engineering definition of done** (distinct from research findings): all three algorithms implemented and unit-tested against deterministic vectors; the simulation runs 30×100 events per configuration per scenario reproducibly under a fixed seed; the statistical pipeline outputs test statistic, df, p-value, and Cohen's d per comparison; the mobile app performs online dispatch and offline informational mode end-to-end.

## 8. Constraints

- **Connectivity is intermittent** at the point of care → offline informational mode + background sync; engine never fails silently on maps-API unavailability (Haversine fallback, flagged).
- **No historical training data** → transparent researcher-defined weights, not machine-learned; all such values centralised in [09-parameters.md](./09-parameters.md) and sensitivity-tested.
- **National EMR is in transition** (LHIMS suspended 2025 → GHIMS successor; Ofori-Adjei, 2025) → vendor-agnostic data-source abstraction; the engine targets whichever national platform is current without changing matching logic.
- **PostgreSQL without PostGIS** — decimal lat/long is sufficient; all spatial work is done by the maps service or the Haversine fallback.

## 9. Ethics & data

The project involves **no human participants** and **no patient data**. All bed/facility data are either drawn from public Ghana Health Service (GHS) facility data or synthetically generated. No ethics-board approval for human subjects is required for the prototype. Should the system later be evaluated with NAS dispatchers or clinical staff, institutional ethics approval would be sought first, and procedures consistent with Ghana's Data Protection Act, 2012 (Act 843) would apply. All results, including any that do not support the hypotheses, are reported in full.

## 10. Glossary

| Term | Meaning |
|------|---------|
| ATBP | Average Time-to-Bed-Placement (virtual-clock minutes) |
| FRR | Facility Rejection Rate (proportion of events with no candidate) |
| MCEE | Mean Candidates Evaluated per Emergency |
| CM | Capability match of placement (mean ĉ) |
| Hₑ / H_f | Filtered candidate set after the hard filter |
| R(u) | Maximum travel-time radius for urgency `u` |
| ĉ / b̂ / t̂ | Normalised capability match / bed count / travel time |
| Tier | Facility capability level: primary, secondary, tertiary |
| Urgency | Patient acuity: critical, urgent, standard |
