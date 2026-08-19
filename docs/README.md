# EBADS — Implementation Documentation

**EBADS** matches emergency patients to hospital beds across Ghana's referral network. Specified in the BSc thesis *"Design and Implementation of an Urgency-Adaptive Emergency Bed Allocation System"* (Chapters 1–3).

This folder is the **implementation specification**. Every rule, formula and parameter traces to the thesis. Anything not in the thesis is marked `[IMPL]` so it is never confused with a research requirement.

## Reading order

| # | File | Scope |
|---|------|-------|
| — | [`PRD.md`](./PRD.md) | Problem, objectives, scope, non-goals, success criteria |
| 01 | [`01-architecture.md`](./01-architecture.md) | Components, layers, adapter interface, data flow, deployment |
| 02 | [`02-data-model.md`](./02-data-model.md) | Entities, schema, invariants, migrations |
| 03 | [`03-scoring-and-ranking.md`](./03-scoring-and-ranking.md) | Hard filter, normalisation, capability matrix, the three strategies |
| 04 | [`04-api-spec.md`](./04-api-spec.md) | REST endpoints, auth, RBAC, escalation, errors |
| 05 | [`05-mobile-app.md`](./05-mobile-app.md) | Dispatcher app: screens, offline mode, sync |
| 06 | [`06-user-flows.md`](./06-user-flows.md) | Journeys and sequence diagrams |
| 07 | [`07-scenario-testing.md`](./07-scenario-testing.md) | Case set, depletion protocol, measures |
| 08 | [`08-evaluation.md`](./08-evaluation.md) | Expectations, comparison, robustness check |
| 09 | [`09-parameters.md`](./09-parameters.md) | **Single source of truth** for every numeric constant |
| 10 | [`10-project-structure.md`](./10-project-structure.md) | Monorepo layout, naming |
| 11 | [`11-development-setup.md`](./11-development-setup.md) | Environment, Docker, seeding |
| 12 | [`12-testing.md`](./12-testing.md) | Test strategy, deterministic vectors, concurrency and RBAC tests |
| 13 | [`13-runbooks.md`](./13-runbooks.md) | Operational procedures |
| 14 | [`14-coding-standards.md`](./14-coding-standards.md) | Conventions, definition of done |
| 15 | [`15-roadmap.md`](./15-roadmap.md) | Five increments with acceptance criteria |
| — | [`AGENTS.md`](./AGENTS.md) | Rules for AI agents working in this repo |

## Source-of-truth hierarchy

1. **Thesis Chapters 1–3** — the research design. Functional behaviour cannot deviate.
2. **[`09-parameters.md`](./09-parameters.md)** — every numeric constant. No magic numbers in logic.
3. **[`PRD.md`](./PRD.md)** and the scope docs.

If thesis-defined behaviour must change, escalate to the researcher; the thesis is updated **first**, code follows.

## One-paragraph system summary

A server-side **allocation engine** (FastAPI) holds all scoring and ranking logic. For each emergency request it authenticates the dispatcher, retrieves facilities within an urgency-dependent radius using a spatial index, applies a hard filter for capability tier and bed availability, normalises three criteria across the surviving candidates, scores and ranks them under a weight vector selected by patient urgency, and commits the top-ranked facility through an **atomic compare-and-set reservation**. On success it notifies the receiving facility **by SMS** with an estimated time of arrival; the reservation expires at ETA plus a configurable grace period if no arrival is recorded. A **dispatcher mobile app** (React Native + Expo) submits requests and renders recommendations, falling back to a read-only informational mode offline. A **facility administration portal** (React) lets facilities register, connect an EMR adapter or maintain bed data manually, and manage their own users. Bed availability is obtained through a **vendor-agnostic adapter interface**, so connecting a real EMR requires a new implementation and no change to allocation logic. Evaluation is by **scenario-based testing** on Ghana Health Service facility data.

## What changed from the previous document set

| Area | Previously | Now |
|---|---|---|
| Terminology | "Algorithm 1/2/3" | **Allocation strategies**; the procedure is scoring and ranking |
| Evaluation | Discrete-event simulation, 270-run grid, H1–H3, full sensitivity analysis | **Scenario-based testing** on GHS data, expectations E1–E3, one robustness check |
| Concurrency | Absent | **Compare-and-set reservation**, fall-through, ETA-based expiry |
| Auth | Static API key, "out of scope" | **Full authentication and RBAC**, four roles, approval-based provisioning |
| Notification | SMS stubbed | **SMS with ETA** on reservation confirmation |
| Facility surface | API only | **Facility administration web portal** |
| Spatial | Decimal lat/long, no index | **PostGIS + GIST index** (thesis §2.6, FR3) |
