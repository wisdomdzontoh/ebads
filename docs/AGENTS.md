# AGENTS.md — Rules for AI Agents

> Read this before writing any code in this repo. It tells you where truth lives, what you may not do, and the exact protocol for a task. Following it is how we keep output grounded and free of slop.

## 1. Source of truth (in order)
1. **Thesis Chapters 1–3** — the research design. You may not change thesis-defined behaviour.
2. **[`docs/09-parameters.md`](./09-parameters.md)** + `backend/app/parameters.py` — every numeric constant.
3. **The scope docs** in `docs/` ([README index](./README.md)).

If two sources conflict, the higher one wins. If the thesis itself seems wrong or ambiguous, **stop and ask** (see §5). Never silently invent a resolution.

## 2. Before you start a task
- Identify the **one doc section** the task implements. State it in your plan.
- Read [`03-algorithms.md`](./03-algorithms.md) and [`09-parameters.md`](./09-parameters.md) if the task touches matching, scoring, simulation, or evaluation.
- Check whether a deterministic vector already covers the behaviour ([`12-testing.md`](./12-testing.md)).

## 3. Hard rules (violations are auto-reject)
- **No magic numbers.** Import from `parameters.py`. If a needed constant is missing there, add it there first (and mirror in [09](./09-parameters.md)), tagged `[IMPL]` if not from the thesis.
- **No invented features, endpoints, fields, or parameters.** Build only what a doc describes.
- **No matching logic in the mobile client.** The client renders engine responses.
- **No silent failure.** Maps down → Haversine + `is_estimated_travel_time=true`. Empty `H_f` → structured escalation.
- **Do not implement the Hungarian algorithm or the scalar `M(u)` urgency formulation.** Both are explicitly rejected ([03 §6–7](./03-algorithms.md)).
- **Do not change a test's expected value to make a wrong implementation pass.** Fix the code, or escalate a genuine thesis discrepancy.
- **Determinism:** thread the seed everywhere; apply the documented tie-break ([03 §9](./03-algorithms.md)).

## 4. Task protocol
1. **Plan**: name the doc section, list files you will touch, list parameters involved, list tests you will add/update.
2. **Implement**: smallest change that fully satisfies the section. Keep allocation steps as separate functions.
3. **Test**: add/extend unit tests; for algorithm work, add or update a deterministic vector with hand-computed expected values.
4. **Verify**: `ruff`/`mypy` (or `tsc`/eslint) clean; relevant tests pass; run the smallest runbook that exercises your change ([13-runbooks.md](./13-runbooks.md)).
5. **Report**: in the PR, state the doc section implemented, parameters touched, and tests that prove it. Run the anti-slop checklist ([14 §5](./14-coding-standards.md)).

## 5. When you are unsure (escalation)
Do **not** guess. Produce a short note:
```
DISCREPANCY / QUESTION
- Where: <doc section or thesis §>
- What is ambiguous/missing: ...
- Options considered: ...
- Blocking? yes/no. If blocking and a choice is unavoidable to proceed:
  - chosen default (tagged [IMPL]) and why, + where you documented it
```
Surface it for the researcher. The thesis/docs are corrected first; code follows.

## 6. Definition of done (agent)
- Implements exactly the named section — no more, no less.
- Constants from `parameters.py`; no magic numbers.
- Tests pass and assert documented expected values (vectors for algorithms).
- Lint/type-check clean.
- PR names the doc section + proving tests.
- Anti-slop checklist clean.

## 7. Quick map of where things are
| You need to… | Go to |
|--------------|-------|
| change a formula | [`03-algorithms.md`](./03-algorithms.md) → `backend/app/domain/allocation/` |
| change a constant | [`09-parameters.md`](./09-parameters.md) → `backend/app/parameters.py` |
| add/change an endpoint | [`04-api-spec.md`](./04-api-spec.md) → `backend/app/api/` |
| touch bed sourcing | [`01 §3.2`](./01-architecture.md) → `backend/app/domain/beds/` |
| change the simulation | [`07-simulation.md`](./07-simulation.md) → `backend/app/simulation/` |
| change stats/sensitivity | [`08-evaluation.md`](./08-evaluation.md) → `backend/app/analysis/` |
| change the app | [`05-mobile-app.md`](./05-mobile-app.md) → `mobile/app/` |
| run something | [`13-runbooks.md`](./13-runbooks.md) |

## 8. The one-sentence test
Before committing, ask: *"Can I point to the exact thesis/doc section and parameter that justifies every line I wrote?"* If not, delete it or escalate.
