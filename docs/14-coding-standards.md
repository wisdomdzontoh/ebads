# 14 — Coding Standards & Definition of Done

> These rules exist to keep the codebase precise and to prevent "AI slop" — plausible-looking code that drifts from the thesis, invents behaviour, or pads files. They are enforced in review and CI.

## 1. Non-negotiables
1. **No magic numbers.** Every constant comes from `parameters.py` ([09](./09-parameters.md)). If you typed a number into logic, it is a bug.
2. **No invented behaviour.** If it is not in the thesis or a doc, do not build it. If you think something is missing, raise it (see [AGENTS.md](./AGENTS.md)), do not improvise.
3. **Matching logic is server-only.** No scoring/filtering/ranking in the mobile client. Ever.
4. **The engine never fails silently.** Maps unavailable → Haversine + flag, not an error. Empty `H_f` → structured escalation, not a null.
5. **Determinism.** Same inputs + parameters → same output. Apply the documented tie-break.

## 2. Python (backend)
- Python 3.12, full type hints, `mypy` clean. Async I/O (SQLAlchemy async, httpx).
- Functions do one thing; allocation steps (`hard_filter`, `normalize`, `score`, `select`) are separate, individually testable units — not one mega-function.
- Pydantic v2 models for all API I/O; no untyped dicts across boundaries.
- Docstrings state **what** and cite the doc/section they implement, e.g. `"""Algorithm 3 — urgency-adaptive scoring (03-algorithms.md §6)."""`. No restating the obvious line-by-line.
- Errors are explicit and typed; no bare `except`.
- Formatting: `ruff` + `ruff format`. Imports sorted. Lines ≤ 100 cols.

## 3. TypeScript (mobile)
- Strict TS (`strict: true`). No `any` without a written reason.
- Components render; side effects in `services/`. No business logic in components.
- One screen per file; shared UI in `components/`.

## 4. Comments & docs
- Comment **why**, not what. The code says what.
- Every non-thesis decision carries an `# [IMPL]` marker referencing where it is documented.
- No aspirational comments ("TODO: make robust", "handle edge cases later") without a tracked issue id.

## 5. Anti-slop checklist (reviewer blocks the PR if any is true)
- [ ] A number appears in logic that should be in `parameters.py`.
- [ ] A feature/endpoint/field exists that no doc describes.
- [ ] A function is long and does several unrelated things.
- [ ] Client contains matching logic.
- [ ] A test's expected value was changed to match a wrong implementation.
- [ ] Vague names (`data`, `process`, `handle`, `manager`) where a precise domain noun exists (`candidate`, `bed_count`, `allocation`).
- [ ] Dead code, commented-out blocks, or unused scaffolding left behind.
- [ ] Docstrings/READMEs padded with marketing adjectives ("robust", "seamless", "powerful").
- [ ] A formula deviates from [03-algorithms.md](./03-algorithms.md) without a thesis update.

## 6. Commits & PRs
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
- One logical change per PR; PR description links the doc section(s) it implements.
- PR template asks: *Which doc/thesis section does this implement? Which parameters did it touch? Which tests prove it?*

## 7. Definition of Done (per unit of work)
A change is done when:
1. It implements exactly what the referenced doc/section says — no more, no less.
2. Constants are read from `parameters.py`.
3. Unit tests (and vectors, for algorithm work) pass and assert against documented expected values.
4. `mypy`/`ruff` (or `tsc`/eslint) clean.
5. The PR names the doc section and the tests that prove it.
6. No item on the anti-slop checklist is true.

## 8. Discrepancy protocol
If the thesis is ambiguous or appears wrong: **stop**, write the question, and escalate to the researcher. Do not silently choose. If a choice is unavoidable to proceed, mark it `[IMPL]`, document it in the relevant doc, and flag it for review. The thesis is corrected first; code follows.
