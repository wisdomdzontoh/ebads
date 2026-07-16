# 03 — Algorithms

> Source of truth: thesis §3.5–3.6. All constants come from [09-parameters.md](./09-parameters.md). Do not hardcode numbers in this logic.

## 0. Notation

For an emergency `e` at patient location `p` with urgency `u` and required bed type `β`:

- `H` = full facility set; `H_f` = filtered candidate set.
- `t(p, h)` = road travel time from `p` to facility `h` (minutes).
- `beds(h, β)` = available beds of type `β` at `h` (via `BedDataSource`).
- `R(u)` = max travel-time radius for urgency `u` (Table 3.2).
- `t̂, b̂, ĉ` = normalised travel time, normalised available-bed count, capability-match score.

## 1. Pipeline (every algorithm)

```
1. hard_filter(e)              -> H_f
2. if H_f empty: escalate(e)   -> structured escalation, STOP
3. fetch travel times t(p,h) for all h in H_f   (Travel-time Service)
4. fetch beds(h, β) for all h in H_f             (BedDataSource)
5. normalize criteria across H_f
6. score + argmin per the selected algorithm
7. return recommendation(h*, algorithm, weights, reason, candidates_evaluated)
```

## 2. Hard filter (thesis §3.5.1)

```
H_f = { h in H : beds(h, β) >= 1  AND  t(p, h) <= R(u) }
```

If `H_f` is empty → **escalation** (do not route to an unreachable facility):

```
escalation = {
  status: "escalated",
  nearest_within_radius:        argmin t(p,h) over { h in H : t(p,h) <= R(u) }            (ignore beds),
  nearest_available_outside:    argmin t(p,h) over { h in H : beds(h,β) >= 1, t(p,h) > R(u) },
  requires_manual_decision: true
}
```
Either of the two nearest fields may be null if no such facility exists; both null is valid (return escalation with both null).

## 3. Normalization (thesis §3.5.2)

Min–max across the **current** `H_f`, per criterion `x ∈ {travel_time, bed_count}`:

```
x̂ = (x - x_min) / (x_max - x_min)
if x_max == x_min:  x̂ = 0.5    # tie rule
```

`ĉ` is **not** min–max normalised; it is looked up directly from the capability matrix `ĉ[u][tier(h)]` (Table 3.3), already in [0,1].

## 4. Algorithm 1 — Greedy Nearest-Facility (baseline; thesis §3.5.4)

```
h* = argmin t(p, h),   h in H_f
```
Not deployed. Simulation baseline only. `algorithm_used = greedy`, `weight_vector = null`.

## 5. Algorithm 2 — Weighted Multi-Criteria Scoring (fixed weights; thesis §3.5.5)

Lower score is better on every term (travel time, bed scarcity = `1-b̂`, capability mismatch = `1-ĉ`):

```
Score2(h) = w_t · t̂(h) + w_b · (1 - b̂(h)) + w_c · (1 - ĉ(h))
h* = argmin Score2(h),   h in H_f
```
Weights `(w_t, w_b, w_c) = (0.40, 0.35, 0.25)`, identical for all urgencies. `algorithm_used = weighted`.

## 6. Algorithm 3 — Urgency-Adaptive Weighted Scoring (deployed default; thesis §3.5.6)

Same three criteria, but weights are a function of urgency `u`:

```
Score3(h, e) = w_t(u) · t̂(h) + w_b(u) · (1 - b̂(h)) + w_c(u) · (1 - ĉ(h))
h* = argmin Score3(h, e),   h in H_f
```
Weight vectors `w(u)` from Table 3.5 (critical 0.50/0.15/0.35; urgent 0.40/0.30/0.30; standard 0.30/0.50/0.20). `algorithm_used = urgency_adaptive`, `weight_vector = w(u)`.

**Design note (do not regress to this):** an earlier scalar formulation `Score3 = M(u) · Score2` was rejected because multiplying every candidate's score by the same positive constant does not change the argmin, so it cannot change the selected facility for an individually-processed request. Urgency **must** be encoded in the weight vector, not as a scalar multiplier.

## 7. Hungarian algorithm — considered and rejected (thesis §3.5.4)

Optimal for batch assignment (Kuhn 1955; Munkres 1957) but **not implemented**: emergency dispatch is an *online* problem (patients arrive one at a time, each placed immediately and irrevocably). Batching to assemble a full assignment would add the very delay the system removes. Documented here so the solution space is visibly considered; do not add it.

## 8. Selection policy (Dynamic Selector; thesis §3.6)

```
def select_algorithm(request):
    if request.simulation_session_id and session.algorithm_config == greedy:
        return GREEDY            # baseline, simulation only
    if request.simulation_session_id:
        return session.algorithm_config   # weighted or urgency_adaptive
    if request.urgency in VALID_URGENCIES:
        return URGENCY_ADAPTIVE  # deployed default
    return WEIGHTED              # safe fallback when urgency missing/invalid
```

## 9. Reference implementation skeleton (Python, async)

```python
# backend/app/domain/allocation/algorithms/base.py
class MatchingAlgorithm(Protocol):
    name: AlgorithmName
    def score(self, candidate: Candidate, ctx: ScoringContext) -> float: ...

def argmin_candidate(candidates: list[Candidate], score_fn) -> Candidate:
    # ties: lowest score, then shortest travel time, then facility_id (stable, deterministic)
    return min(candidates, key=lambda c: (score_fn(c), c.travel_time_min, str(c.facility_id)))
```

`[IMPL]` **Tie-breaking** is not specified in the thesis. Use a deterministic order: (1) lowest score, (2) shortest travel time, (3) facility id. This must be identical in simulation and live paths and documented here so results are reproducible.

## 10. Determinism requirements
- Given the same `H_f`, travel times, bed counts, and parameters, every algorithm returns the **same** `h*` every time.
- No floating-point ordering ambiguity: apply the tie-break in §9.
- These properties are enforced by the deterministic test vectors in [12-testing.md](./12-testing.md).
