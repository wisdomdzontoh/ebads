# 11 — Development Setup

> Goal: a reproducible local environment. The prototype's deployment target is Docker Compose for the engine + DB; the mobile app runs via Expo. Constants in [09-parameters.md](./09-parameters.md).

## 1. Prerequisites
- Docker + Docker Compose
- Python 3.12+ (for running backend tooling outside Docker)
- Node 20+ and Expo CLI (`npx expo`)
- A Google Maps API key (Distance Matrix) — optional; without it, the engine and simulation use the Haversine fallback.

## 2. Environment variables (`infra/.env`, never committed)
```
# engine
DATABASE_URL=postgresql+asyncpg://ebads:ebads@db:5432/ebads
API_KEY=dev-only-key
GOOGLE_MAPS_API_KEY=            # optional; blank => Haversine fallback
LOG_LEVEL=info

# simulation defaults (mirror 09-parameters.md §8.1; confirm before evaluation)
RANDOM_SEED=20260617
COORDINATION_OVERHEAD_MIN=5
```
A committed `infra/.env.example` documents every variable with placeholder values.

## 3. Bring up the engine + database
```
docker compose -f infra/docker-compose.yml up --build
# engine on http://localhost:8000  (Swagger at /docs)
```
`docker-compose.yml` defines two services: `engine` (FastAPI/uvicorn) and `db` (postgres:16). The engine waits for `readyz` (DB reachable) before serving.

## 4. Migrations
```
docker compose exec engine alembic upgrade head     # apply schema
docker compose exec engine alembic revision --autogenerate -m "describe change"   # new migration
```

## 5. Seed facilities (idempotent)
```
docker compose exec engine python -m scripts.seed_facilities --source data/ga_facilities.csv
```
- `data/ga_facilities.csv` holds the 24 Greater Accra public emergency-receiving facilities (name, lat, lon, tier, supported bed types, capacity per type, phone), drawn from the GHS regional facility list ([09 §8](./09-parameters.md)).
- The seed script upserts by name; re-running does not duplicate.
- **This CSV must be populated before any simulation/evaluation run.** It is the single place the facility set is defined for the study.

## 6. Build the distance matrix (once per study)
```
docker compose exec engine python -m app.simulation.distance_matrix build \
  --facilities data/ga_facilities.csv --out artifacts/distance_matrix.parquet
```
Uses the maps API if `GOOGLE_MAPS_API_KEY` is set, else Haversine @ 30 km/h. Records which was used + a content hash.

## 7. Run the backend tests
```
docker compose exec engine pytest -q                 # all
docker compose exec engine pytest tests/unit -q      # fast unit + vectors
```
See [12-testing.md](./12-testing.md).

## 8. Mobile app
```
cd mobile
npm install
npx expo start            # then run on device/emulator via Expo Go or a dev build
```
Set the engine base URL + API key in the Settings screen (defaults read from `app.json` extra config for development).

## 9. Local dev without Docker (optional)
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# start a local postgres yourself, set DATABASE_URL, then:
uvicorn app.main:app --reload
```

## 10. Definition of "environment is healthy"
- `GET /healthz` → 200, `GET /readyz` → 200.
- `alembic upgrade head` is clean.
- `pytest tests/unit` passes (including algorithm vectors).
- Seed script loads 24 facilities; `GET /api/v1/facilities` returns them.
- A one-event `POST /api/v1/allocations` returns a valid recommendation or escalation.
