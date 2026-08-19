# AGENTS.md — Rules for AI Agents

> Read this before writing any code in this repo. It says where truth lives, what you may not do, and the protocol for a task.

## 1. Source of truth (in order)

1. **Thesis Chapters 1–3** — the research design. You may not change thesis-defined behaviour.
2. **[`09-parameters.md`](./09-parameters.md)** + `backend/app/parameters.py` — every numeric constant.
3. **The scope docs** in this folder ([index](./README.md)).

Higher wins on conflict. If the thesis itself seems wrong or ambiguous, **stop and ask** (§5). Never silently invent a resolution.

## 2. Vocabulary — get this right

- The three variants are **allocation strategies**: `nearest_facility`, `fixed_weight`, `urgency_adaptive`. Do not call them "Algorithm 1/2/3" in code, comments, identifiers or docs.
- The procedure is **scoring and ranking**.
- "Algorithm" is reserved for the theoretical sense in thesis §2.4 — online assignment, competitive analysis, the Hungarian method.

## 3. Hard rules (violations are auto-reject)

- **No magic numbers.** Import from `parameters.py`. Missing constant → add it there first and mirror in [09](./09-parameters.md), tagged `[IMPL]` if not from the thesis.
- **No invented features, endpoints, fields or parameters.** Build only what a doc describes.
- **No scoring logic in any client.** Mobile and portal render engine responses.
- **No silent failure.** Maps down → Haversine + `is_estimated_travel_time=true`. Empty `Hₑ` → structured escalation, not null, not 5xx.
- **Never bypass the compare-and-set.** A bed is committed only through `reserve(..., expect_version)`. A plain `UPDATE available = available - 1` is a correctness defect, not a shortcut.
- **Never update `bed_state.available` without incrementing `version`** in the same statement.
- **No endpoint-level permission checks.** Authorization lives in middleware, once. Adding an inline check is a defect even when it is correct.
- **Do not implement:** the Hungarian algorithm; the scalar `M(u)` urgency formulation; TOPSIS; AHP. All four are explicitly rejected ([03 §7, §11, §12](./03-scoring-and-ranking.md)).
- **Do not build discrete-event simulation.** No virtual clock, no length-of-stay sampling, no random seed, no run grid. The project uses deterministic scenario testing ([07](./07-scenario-testing.md)).
- **Do not compute p-values, t-tests or Cohen's d** over the case set. The cases are a fixture, not a sample ([08 §3](./08-evaluation.md)).
- **Do not change a test's expected value** to make a wrong implementation pass. Fix the code, or escalate a genuine thesis discrepancy.
- **Determinism.** Same inputs + parameters → same output. Apply the documented tie-break ([03 §9](./03-scoring-and-ranking.md)).

## 4. Task protocol

1. **Plan** — name the one doc section the task implements; list files, parameters and tests.
2. **Implement** — the smallest change that fully satisfies that section. Keep allocation steps as separate functions: `spatial_retrieve`, `hard_filter`, `normalise`, `score`, `rank`, `reserve`. Never one mega-function.
3. **Test** — extend unit tests; for scoring work, add a deterministic vector with **hand-computed** expected values.
4. **Verify** — `ruff`/`mypy` clean; relevant tests pass; run the smallest runbook exercising your change ([13](./13-runbooks.md)).
5. **Report** — PR names the doc section, parameters touched and proving tests. Run the anti-slop checklist ([14 §5](./14-coding-standards.md)).

## 5. When unsure — escalate, do not guess

```
DISCREPANCY / QUESTION
- Where: <doc section or thesis §>
- What is ambiguous or missing:
- Options considered:
- Blocking? yes/no
- If blocking and a choice is unavoidable: chosen default (tagged [IMPL]), why, and where documented
```

The thesis and docs are corrected first; code follows.

## 6. Purity boundary — the one that matters most

`backend/app/domain/allocation/scoring.py` must remain **pure**: no database session, no HTTP client, no `datetime.now()`, no logging of state, no globals. It takes candidates, urgency, strategy and parameters, and returns a ranking.

If you find yourself needing I/O inside it, you are solving the problem in the wrong layer. Move the I/O to the caller. This purity is what makes the contribution testable in milliseconds without a database, and it is the file the researcher and supervisor will read most closely.

## 7. Quick map

| You need to… | Go to |
|---|---|
| change a formula | [`03`](./03-scoring-and-ranking.md) → `domain/allocation/` |
| change a constant | [`09`](./09-parameters.md) → `app/parameters.py` |
| add or change an endpoint | [`04`](./04-api-spec.md) → `app/api/` |
| touch bed sourcing | [`01 §5`](./01-architecture.md) → `domain/beds/` |
| touch reservation or expiry | [`01 §7`](./01-architecture.md) → `domain/reservation/` |
| touch auth or permissions | [`01 §4`](./01-architecture.md) → `app/security/` |
| change the evaluation | [`07`](./07-scenario-testing.md), [`08`](./08-evaluation.md) → `app/scenario/`, `app/analysis/` |
| change the app | [`05`](./05-mobile-app.md) → `mobile/app/` |
| run something | [`13`](./13-runbooks.md) |

## 8. The one-sentence test

Before committing: *"Can I point to the exact thesis or doc section, and the parameter, that justifies every line I wrote?"* If not, delete it or escalate.
