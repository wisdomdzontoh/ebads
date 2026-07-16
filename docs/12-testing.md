# 12 — Testing

> Tests are how we keep the implementation honest against the thesis. The most important tests are **deterministic algorithm vectors**: hand-computable inputs with expected outputs that lock the math to [03-algorithms.md](./03-algorithms.md) and [09-parameters.md](./09-parameters.md).

## 1. Test pyramid
| Layer | Scope | Tooling |
|-------|-------|---------|
| Unit | hard filter, normalization, capability lookup, each algorithm, selector, metrics, stats | pytest |
| Vectors | deterministic end-to-end algorithm cases with expected `h*` | pytest (data-driven) |
| Integration | API endpoints against a real test DB; data-source Bridge | pytest + httpx + test postgres |
| Simulation | virtual clock, occupancy seeding, reproducibility under seed | pytest |
| Mobile | services (api/cache/sync), offline-mode boundary | Jest + React Native Testing Library |

## 2. Deterministic algorithm vectors (the core safety net)

Stored as data files in `backend/tests/vectors/` and executed by one parametrized test. Each vector fixes the candidate set (travel times, bed counts, tiers), the request (urgency, bed type), and the **expected** normalised values, score per candidate, and selected facility — computed by hand from the formulas.

Example vector (`urgency_adaptive_critical_icu.json`):
```json
{
  "request": { "urgency": "critical", "required_bed_type": "icu" },
  "candidates": [
    { "id": "A", "tier": "tertiary",  "travel_min": 10, "beds": 1 },
    { "id": "B", "tier": "secondary", "travel_min": 20, "beds": 5 },
    { "id": "C", "tier": "tertiary",  "travel_min": 30, "beds": 2 }
  ],
  "expected": {
    "passes_hard_filter": ["A", "B", "C"],
    "t_hat": { "A": 0.0, "B": 0.5, "C": 1.0 },
    "b_hat": { "A": 0.0, "B": 1.0, "C": 0.25 },
    "c_hat": { "A": 1.0, "B": 0.6, "C": 1.0 },
    "weights": { "w_t": 0.50, "w_b": 0.15, "w_c": 0.35 },
    "score": { "A": 0.150, "B": 0.640, "C": 0.6375 },
    "selected": "A"
  }
}
```
> Worked check for A: `0.50·0.0 + 0.15·(1−0.0) + 0.35·(1−1.0) = 0.15`. The test recomputes from the implementation and asserts equality to `expected` within 1e-9, and asserts `selected == argmin`.

Required vector coverage (minimum):
- Each algorithm × each urgency.
- Hard-filter exclusions (bed=0 excluded; travel>R(u) excluded).
- Escalation (empty H_f) returning the two correct fallbacks.
- Normalization tie rule (all equal → 0.5).
- Tie-break order (equal scores → shorter travel → facility id).
- The rejected scalar `M(u)` regression guard: a test asserting Algo 3 selection **differs** from Algo 2 on at least one urgency where weights differ (proves urgency actually changes selection, not just scales it).

## 3. Selector tests
- urgency present → urgency_adaptive; urgency null/invalid → weighted; simulation session → session's configured algorithm; greedy only inside simulation.

## 4. Bed Data Source (Bridge) tests
- `SimulationDataSource` decrements session bed state on allocation and never touches `bed_count`/`facility`.
- Interface conformance test that any `BedDataSource` implements `get_available_beds`.

## 5. Simulation tests
- **Reproducibility**: same seed → identical per-event outcomes (assert event-by-event equality).
- Occupancy seeding: available = round(capacity·(1−occupancy)); at 100% initial availability = 0.
- Bed release: an allocated bed returns to the pool at `arrival + los`.
- Metrics: ATBP excludes escalated events; FRR counts escalations; MCEE/CM computed over the right denominators.
- Isolation: a run leaves `bed_count`/`facility` unchanged.

## 6. Statistics tests
- Known fixtures with hand/SciPy-verified outputs for paired t-test, Shapiro–Wilk branch → Wilcoxon, and Cohen's d.
- Pairing uses matched seed indices across configurations.

## 7. Integration tests
- `POST /allocations` happy path → 200 allocated with all audit fields persisted.
- `POST /allocations` → escalation shape when no candidate.
- Maps-API failure path → recommendation with `is_estimated_travel_time=true` (mock the travel service).
- Full simulation session create → run → results.

## 8. Mobile tests
- `connectivity` switches Dispatch ↔ Offline correctly.
- Offline mode renders cached data and the banner, and **does not** call `/allocations`.
- No scoring/filtering logic exists client-side (guard test / lint rule).

## 9. Coverage + CI
- Target ≥ 85% on `backend/app/domain` and `backend/app/simulation` (the logic that must match the thesis); overall ≥ 75% `[IMPL]`.
- CI runs: lint → unit+vectors → integration (ephemeral postgres) → mobile unit. A failing vector blocks merge.

## 10. What a test must never do
- Never assert on wall-clock timing as a correctness metric.
- Never hardcode a parameter value that also lives in `parameters.py` — import it, so a parameter change is caught in one place.
- Never weaken a vector's expected value to make a failing implementation pass; fix the implementation or escalate a thesis discrepancy.
