# EBADS — Emergency Bed Allocation and Dispatch System

An algorithm-driven decision-support system that matches emergency patients to hospital
facilities across Ghana's referral network. BSc Computer Science final-project prototype;
the full design and source of truth live in [`docs/`](./docs/README.md).

## Repository layout

```
ebads/
  backend/   FastAPI allocation engine + simulation + analysis
  mobile/    React Native + Expo dispatcher app (Phase 6)
  infra/     docker-compose, env templates
  docs/      implementation specification (source of truth)
  scripts/   dev/ops helper scripts
  artifacts/ generated sim/ + eval/ outputs (gitignored)
```

## Build status

Implemented per the phased [roadmap](./docs/15-roadmap.md):

- [x] **Phase 0 — Foundations:** parameters module (single source of truth) with
      load-time validation, config, async DB layer, health/readiness endpoints,
      Alembic, Docker Compose, CI scaffold.
- [x] **Phase 1 — Facility registry + data model:** `facility` + `bed_count` entities and
      migration, Facility Registry Service, `/api/v1/facilities` CRUD + `PATCH .../beds`,
      seed script + 24-facility Greater Accra dataset.
- [x] **Phase 2 — Bed data source abstraction (Bridge):** `BedDataSource` interface, the
      built `SimulationDataSource` (isolated per-session bed state), and three specified
      EMR/FHIR stubs; `simulation_session` + `simulation_bed_state` entities.
- [x] **Phase 3 — Allocation engine + algorithms:** hard filter, min–max normalization,
      capability lookup, travel-time service (Google + Haversine fallback), Algorithms
      1/2/3 + dynamic selector, `POST /allocations` with audit persistence + escalation;
      deterministic algorithm vectors.
- [x] **Phase 4 — Simulation engine:** deterministic discrete-event simulation reusing the
      allocation engine — seeded event generation, occupancy seeding, virtual-clock bed
      lifecycle (allocate/release), `simulation_allocation_event` records, ATBP/FRR/MCEE/CM
      metrics, precomputed distance matrix (`MatrixTravelTimeService`), `/simulation/...`
      endpoints (create/run/step/results), and the batch grid runner (RB-4/5/6).
- [x] **Phase 5 — Evaluation pipeline:** H1/H2/H3 hypothesis tests (Shapiro→paired-t/Wilcoxon,
      Cohen's d), sensitivity analysis over weight/radius/capability variants
      (`config/sensitivity.yaml`), evaluation report (figures + `study_manifest.json`), and
      grid reproduction from a manifest (RB-7/8/9/10).
- [ ] Phase 6 — Mobile app
- [ ] Phase 7 — Hardening & docs

## Quick start

```bash
docker compose -f infra/docker-compose.yml up --build -d
docker compose -f infra/docker-compose.yml exec engine alembic upgrade head
curl -s localhost:8000/readyz        # {"status":"ready"}
```

See [docs/11-development-setup.md](./docs/11-development-setup.md) for the full setup and
[docs/13-runbooks.md](./docs/13-runbooks.md) for operational runbooks.
