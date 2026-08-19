# 03 — Scoring and Ranking

> Source of truth: thesis §3.7. All constants from [09-parameters.md](./09-parameters.md). **Never hardcode a number in this logic.**
>
> Terminology: the three variants are **allocation strategies**, not "algorithms". The procedure they share is **scoring and ranking**. "Algorithm" is reserved for the theoretical sense used in thesis §2.4 (online assignment, competitive analysis).

## 0. Notation

For an emergency `e` at location `p`, urgency `u`, required bed type `β`:

- `H` = facility registry; `Hₑ` = candidate set after the hard filter
- `t(p,h)` = road travel time in minutes
- `beds(h,β)` = available beds of type β at h, via `BedDataSource`
- `R(u)` = maximum travel-time radius for urgency u
- `t̂, b̂, ĉ` = normalised travel time, normalised bed count, capability match

## 1. Pipeline (identical for every strategy)

```
1. spatial_retrieve(p, R(u))       -> facilities within radius        [PostGIS ST_DWithin + GIST]
2. hard_filter(candidates, β)      -> Hₑ
3. if Hₑ empty: escalate(e)        -> structured escalation, STOP
4. travel_times(p, Hₑ)             -> t(p,h)                          [Travel-time Service]
5. bed_counts(Hₑ, β)               -> beds(h,β)                       [BedDataSource]
6. normalise(Hₑ)                   -> t̂, b̂ ; lookup ĉ
7. score + rank ascending          -> ordered candidate list
8. reserve(top-ranked)             -> CAS; on conflict take next      [04 §5]
9. return recommendation(h*, strategy, weights, breakdown, candidates_evaluated)
```

Steps 1–7 are **pure**: no I/O beyond the two fetches, no clock, no mutation. Step 8 is the only stateful operation. This separation is what makes the contribution unit-testable.

## 2. Spatial retrieval (thesis §3.7.5, FR3)

```sql
SELECT * FROM facility
WHERE ST_DWithin(location, ST_MakePoint(:lon,:lat)::geography, :radius_metres);
-- index: CREATE INDEX idx_facility_location ON facility USING GIST (location);
```

`radius_metres` derives from `R(u)` at the configured urban speed factor. A sequential scan is a defect, not a performance detail: FR3 and NFR2 require the index, and the query plan is asserted in test.

## 3. Hard filter (thesis §3.7.1)

```
Hₑ = { h ∈ H : β ∈ B(tier(h))  ∧  beds(h,β) ≥ 1  ∧  t(p,h) ≤ R(u) }
```

The tier condition is **not** redundant with bed availability: a polyclinic operates no ICU, so an ICU request must never treat primary facilities as candidates even if a bed row exists.

Empty `Hₑ` → **escalation**, never a relaxed constraint and never a null:

```
escalation = {
  status: "escalated",
  nearest_within_radius:      argmin t(p,h) over { h : t(p,h) ≤ R(u), β ∈ B(tier(h)) }   # ignore beds
  nearest_available_outside:  argmin t(p,h) over { h : beds(h,β) ≥ 1, t(p,h) > R(u) }
  requires_manual_decision: true
}
```
Either field may be null; both null is valid.

## 4. Normalisation (thesis §3.7.2)

Min–max across the **current** `Hₑ`, per criterion `x ∈ {travel_time, bed_count}`:

```
x̂ = (x − x_min) / (x_max − x_min)
if x_max == x_min:  x̂ = 0.5          # tie rule
```

Normalisation is **per request**, not global: the comparison that matters is among the candidates actually available to this patient.

`ĉ` is looked up from the capability matrix `ĉ[u][tier(h)]`, already in [0,1].

## 5. Strategy 1 — Nearest-facility (baseline)

```
h* = argmin t(p,h),   h ∈ Hₑ
```
**Not deployed.** Evaluation baseline only, representing the best case of current practice once real-time bed visibility is assumed. `strategy_used = nearest_facility`, `weight_vector = null`.

## 6. Strategy 2 — Fixed-weight scoring

Lower is better on every term:

```
Score₂(h) = w_t·t̂(h) + w_b·(1−b̂(h)) + w_c·(1−ĉ(h))
h* = argmin Score₂(h),   h ∈ Hₑ
```
Weights `(0.40, 0.30, 0.30)`, identical for all urgencies ([09 §5](./09-parameters.md)). `strategy_used = fixed_weight`.

Serves as the **control** in the evaluation: it has multi-criteria scoring but no urgency conditioning, so the difference between Strategy 2 and Strategy 3 isolates the contribution.

## 7. Strategy 3 — Urgency-adaptive scoring (deployed default)

Same functional form; the weight vector is a function of urgency:

```
Score₃(h,u) = w_t(u)·t̂(h) + w_b(u)·(1−b̂(h)) + w_c(u)·(1−ĉ(h))
h* = argmin Score₃(h,u),   h ∈ Hₑ
```
Vectors from [09 §6](./09-parameters.md). `strategy_used = urgency_adaptive`, `weight_vector = w(u)`.

**Do not regress to a scalar formulation.** An earlier design `Score₃ = M(u)·Score₂` was rejected: multiplying every candidate's score by the same positive constant cannot change the argmin, so it cannot change the selected facility for an individually-processed request. Urgency **must** enter through the weight vector. A regression guard test enforces this ([12 §2](./12-testing.md)).

### Known subtlety — state this correctly if asked

`ĉ` depends on urgency in **both** Strategy 2 and Strategy 3, because the capability matrix is indexed by acuity. So Strategy 2 is not fully urgency-blind. The precise distinction: **Strategy 2 lets urgency change one criterion's value; Strategy 3 additionally lets urgency change how much each criterion matters.** Do not overstate this in code comments or the thesis.

## 8. Strategy selection

```python
def select_strategy(request, config) -> Strategy:
    if config.forced_strategy:                 # scenario testing only
        return config.forced_strategy
    if request.urgency in VALID_URGENCIES:
        return Strategy.URGENCY_ADAPTIVE       # deployed default
    return Strategy.FIXED_WEIGHT               # safe fallback: urgency missing/invalid
```
`nearest_facility` is never selected in live operation — only by explicit configuration in a scenario run.

## 9. Reference skeleton

```python
# backend/app/domain/allocation/scoring.py
# PURE. No DB session, no HTTP client, no datetime.now().

@dataclass(frozen=True)
class Candidate:
    facility_id: UUID
    tier: Tier
    travel_min: float
    free_beds: int

@dataclass(frozen=True)
class Ranked:
    facility_id: UUID
    score: float
    breakdown: dict[str, float]   # t_hat, b_hat, c_hat, weighted contributions — FR12, FR13

def rank(candidates: list[Candidate], urgency: Urgency,
         strategy: Strategy, params: Parameters) -> list[Ranked]:
    ...
```

**Tie-breaking** `[IMPL]` — not specified in the thesis. Deterministic order: (1) lowest score, (2) shortest travel time, (3) facility id ascending. Identical in scenario and live paths, so results are reproducible.

## 10. Determinism

Given the same `Hₑ`, travel times, bed counts and parameters, every strategy returns the **same** ordering every time. No floating-point ordering ambiguity — apply the tie-break in §9. Enforced by the deterministic vectors in [12 §2](./12-testing.md).

## 11. Hungarian algorithm — considered and rejected (thesis §2.4.1)

Optimal for batch assignment (Kuhn 1955; Munkres 1957) but **not implemented**. Emergency dispatch is an *online* problem: patients arrive one at a time and each must be placed immediately and irrevocably. Assembling a batch would add the very delay the system removes. Documented so the solution space is visibly considered. **Do not add it.**

## 12. TOPSIS and AHP — considered and rejected (thesis §2.5.4)

TOPSIS ranks by relative closeness to an ideal alternative and penalises being far from ideal on any single criterion, which a weighted sum permits to be compensated. Rejected on **transparency**, not correctness: a relative distance in normalised criterion space is materially harder to explain to a clinician than a weighted sum of three named quantities, and interpretability is a stated requirement (NFR4). The compensation concern is partly met by the hard filter, which removes clinically inadmissible candidates before any scoring. AHP was rejected because it requires expert pairwise judgements that were not available. **Do not implement either.**
