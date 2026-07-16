# 10 — Project Structure

> A monorepo with two deployables (backend engine, mobile app) and shared docs. Layout is fixed so agents and humans find things in the same place every time.

## 1. Top level
```
ebads/
  backend/        # FastAPI allocation engine + simulation + analysis
  mobile/         # React Native + Expo dispatcher app
  infra/          # docker-compose, env templates
  docs/           # this documentation set (source of truth)
  scripts/        # dev/ops helper scripts
  artifacts/      # generated: sim/ eval/ (gitignored)
  README.md
```

## 2. Backend
```
backend/
  app/
    main.py                  # FastAPI app factory, router mount, health
    config.py                # env-backed Settings (pydantic-settings)
    parameters.py            # researcher-defined constants (mirrors 09-parameters.md)
    db/
      base.py                # declarative base
      session.py             # async engine/session
      models/                # SQLAlchemy models (one file per entity)
      migrations/            # Alembic versions
    domain/
      facilities/            # Facility Registry Service
      beds/                  # Bed Data Source Abstraction (Bridge)
        base.py              #   BedDataSource interface
        simulation_source.py #   built
        facility_management_source.py
        national_emr_source.py
        hl7_fhir_source.py
      allocation/            # Emergency Request & Allocation Service
        hard_filter.py
        normalization.py
        capability.py
        algorithms/
          base.py
          greedy.py
          weighted.py
          urgency_adaptive.py
        selector.py
        service.py
      travel/                # travel-time service (Google + Haversine fallback)
      notifications/         # push + stubbed SMS
    api/
      routes/                # facilities.py, allocations.py, simulation.py, health.py
      schemas/               # Pydantic request/response models
      errors.py
    simulation/
      engine.py              # virtual clock + event loop
      scenarios.py           # occupancy seeding
      distance_matrix.py     # precompute + lookup
      metrics.py             # ATBP/FRR/MCEE/CM
      runner.py              # batch grid
    analysis/
      statistics.py          # t-test / shapiro / wilcoxon / cohen d
      sensitivity.py
      report.py              # tables + figures + manifest
  tests/
    unit/
    integration/
    fixtures/
    vectors/                 # deterministic algorithm test vectors (see 12-testing.md)
  pyproject.toml
  alembic.ini
  Dockerfile
```

## 3. Mobile
```
mobile/
  app/
    screens/        DispatchScreen.tsx FacilityMapScreen.tsx SimulationScreen.tsx SettingsScreen.tsx
    components/
    services/       api.ts cache.ts sync.ts connectivity.ts notifications.ts
    state/
    navigation/
  app.json
  package.json
  tsconfig.json
```

## 4. Naming conventions
- **Python**: `snake_case` modules/functions, `PascalCase` classes; one entity per model file; service classes end in `Service`; data sources end in `Source`.
- **TypeScript**: `PascalCase` components/screens, `camelCase` functions/vars; one screen per file.
- **Files map to concepts in the docs**: e.g. `urgency_adaptive.py` ↔ Algorithm 3 in [03-algorithms.md](./03-algorithms.md).
- **Tests** mirror source paths: `tests/unit/allocation/test_urgency_adaptive.py`.

## 5. Where things live (so nothing is invented twice)
| Concern | Single location |
|---------|-----------------|
| Numeric constants | `backend/app/parameters.py` (mirrors [09](./09-parameters.md)) |
| Matching logic | `backend/app/domain/allocation/` |
| Bed sourcing | `backend/app/domain/beds/` |
| Simulation | `backend/app/simulation/` |
| Stats/sensitivity | `backend/app/analysis/` |
| API contracts | `backend/app/api/schemas/` (mirrors [04](./04-api-spec.md)) |
| Client logic | `mobile/app/services/` (rendering only) |

## 6. Gitignore essentials
`artifacts/`, `.env`, `*.parquet`, `*.npz`, Expo build output, `__pycache__/`, `node_modules/`.
