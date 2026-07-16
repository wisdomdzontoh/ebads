# EBADS — Implementation Documentation

**EBADS** (Emergency Bed Allocation and Dispatch System) is an algorithm-driven system that matches emergency patients to hospital facilities across Ghana's referral network, designed and specified in the BSc thesis *"An Algorithm-Driven Emergency Bed Allocation and Dispatch System for Ghana's Hospital Referral Network"* (Chapters 1–3).

This folder is the **implementation specification**. It translates the thesis design into a build-ready spec for engineers and AI coding agents. Every functional rule, formula, and parameter here is traceable to the thesis. Anything not in the thesis is marked `[IMPL]` (an implementation decision) so it is never confused with a research requirement.

## How to read this (suggested order)

| # | File | Scope |
|---|------|-------|
| — | [`PRD.md`](./PRD.md) | Product requirements: problem, objectives, scope, non-goals, success criteria |
| 01 | [`01-architecture.md`](./01-architecture.md) | System components, service layers, Bridge pattern, data flow, deployment |
| 02 | [`02-data-model.md`](./02-data-model.md) | Entities, schema, relationships, migrations |
| 03 | [`03-algorithms.md`](./03-algorithms.md) | Hard filter, normalization, capability matrix, the three algorithms, selection policy |
| 04 | [`04-api-spec.md`](./04-api-spec.md) | REST endpoints, request/response schemas, escalation, errors |
| 05 | [`05-mobile-app.md`](./05-mobile-app.md) | React Native app: screens, offline mode, sync |
| 06 | [`06-user-flows.md`](./06-user-flows.md) | User journeys and sequence diagrams |
| 07 | [`07-simulation.md`](./07-simulation.md) | Discrete-event simulation, virtual clock, scenarios, distance matrix |
| 08 | [`08-evaluation.md`](./08-evaluation.md) | Hypotheses, metrics, statistical plan, sensitivity analysis |
| 09 | [`09-parameters.md`](./09-parameters.md) | **Single source of truth** for every numeric parameter |
| 10 | [`10-project-structure.md`](./10-project-structure.md) | Monorepo layout and naming conventions |
| 11 | [`11-development-setup.md`](./11-development-setup.md) | Environment, Docker, local run, seeding |
| 12 | [`12-testing.md`](./12-testing.md) | Test strategy and deterministic algorithm test vectors |
| 13 | [`13-runbooks.md`](./13-runbooks.md) | Operational procedures |
| 14 | [`14-coding-standards.md`](./14-coding-standards.md) | Conventions and definition of done |
| 15 | [`15-roadmap.md`](./15-roadmap.md) | Phased build plan with acceptance criteria |
| — | [`AGENTS.md`](./AGENTS.md) | Rules for AI agents working in this repo |

## Source-of-truth hierarchy

When two documents appear to conflict, resolve in this order:

1. **The thesis (Chapters 1–3)** — the research design. Functional behaviour cannot deviate from it.
2. **[`09-parameters.md`](./09-parameters.md)** — every numeric constant. Code reads these values from one config module; no magic numbers in logic.
3. **[`PRD.md`](./PRD.md)** and the scope docs — everything else.

If a change to thesis-defined behaviour is ever needed, it is escalated to the researcher and the thesis is updated **first**; the code follows.

## One-paragraph system summary

A server-side **allocation engine** (FastAPI) holds all matching logic. It maintains a facility registry and bed-availability state, and for each emergency request it applies a hard filter, runs the selected matching algorithm, obtains travel times from an external maps service, and returns a ranked recommendation (or a structured escalation). A **cross-platform mobile app** (React Native + Expo) is the dispatcher client: online it submits requests and shows recommendations; offline it shows a read-only cache of facilities — it never runs matching itself. The system is evaluated entirely by **discrete-event simulation** on synthetic and public data; there are no human participants.
