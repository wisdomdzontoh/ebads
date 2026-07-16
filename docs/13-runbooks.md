# 13 — Runbooks

> Step-by-step operational procedures. Each runbook is self-contained and ends with a verifiable success check.

## RB-1 — Start the engine locally
```
docker compose -f infra/docker-compose.yml up --build -d
docker compose exec engine alembic upgrade head
curl -s localhost:8000/readyz        # expect {"status":"ready"}
```
**Success:** `/healthz` and `/readyz` return 200; `/docs` loads.

## RB-2 — Load the facility set
```
docker compose exec engine python -m scripts.seed_facilities --source data/ga_facilities.csv
curl -s localhost:8000/api/v1/facilities | jq 'length'   # expect 24
```
**Success:** 24 facilities present, each with tier, supported bed types, capacity, phone.
**If <24:** the CSV is incomplete — populate it from the GHS Greater Accra list before proceeding ([11 §5](./11-development-setup.md)).

## RB-3 — Submit a single allocation (smoke test)
```
curl -s localhost:8000/api/v1/allocations -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' -d '{
  "patient_lat":5.6037,"patient_lon":-0.1870,"urgency":"critical","required_bed_type":"icu"
}' | jq
```
**Success:** `status` is `allocated` (with facility, algorithm_used=`urgency_adaptive`, weight_vector, candidates_evaluated) or `escalated` (with two fallbacks + requires_manual_decision).

## RB-4 — Build the distance matrix (once per study)
```
docker compose exec engine python -m app.simulation.distance_matrix build \
  --facilities data/ga_facilities.csv --out artifacts/distance_matrix.parquet
```
**Success:** matrix file written; `study` log records source (maps vs Haversine) and content hash.

## RB-5 — Run one simulation session (interactive sanity)
```
SID=$(curl -s localhost:8000/api/v1/simulation/sessions -H "X-API-Key:$API_KEY" -H 'Content-Type: application/json' \
  -d '{"algorithm_config":"urgency_adaptive","occupancy_scenario":0.90,"events_planned":100,"random_seed":20260617}' | jq -r .id)
curl -s -X POST localhost:8000/api/v1/simulation/sessions/$SID/step -H "X-API-Key:$API_KEY" | jq
```
**Success:** a decision trace with candidates, normalised values, scores, and a selection.

## RB-6 — Run the full evaluation grid
```
docker compose exec engine python -m app.simulation.runner \
  --study-id 2026-06-17 --seed 20260617 \
  --algorithms greedy weighted urgency_adaptive \
  --occupancies 0.75 0.90 1.00 --runs 30 --events 100 \
  --distance-matrix artifacts/distance_matrix.parquet
```
Produces `artifacts/sim/2026-06-17/per_run_metrics.parquet` + per-event records.
**Success:** 3 algorithms × 3 occupancies × 30 runs = 270 runs recorded; each with ATBP/FRR/MCEE/CM.

## RB-7 — Run hypothesis tests
```
docker compose exec engine python -m app.analysis.statistics \
  --input artifacts/sim/2026-06-17/per_run_metrics.parquet \
  --out artifacts/eval/2026-06-17/hypothesis_tests.csv
```
**Success:** one row per comparison per scenario (test, statistic, df, p, Cohen's d, mean diff) for H1/H2/H3.

## RB-8 — Run sensitivity analysis
```
docker compose exec engine python -m app.analysis.sensitivity \
  --study-id 2026-06-17 --variants config/sensitivity.yaml \
  --out artifacts/eval/2026-06-17/sensitivity_results.csv
```
- `config/sensitivity.yaml` holds the 4 weight, 3 radius, 2 capability configurations from [09 §10](./09-parameters.md).
**Success:** table showing which hypotheses hold under each variant (robust vs conditional).

## RB-9 — Generate the evaluation report + figures
```
docker compose exec engine python -m app.analysis.report --study-id 2026-06-17
```
**Success:** `artifacts/eval/2026-06-17/` contains figures, the two CSVs, and `study_manifest.json` (seeds, parameter snapshot, distance-matrix hash, code commit).

## RB-10 — Reproduce a study from a manifest
```
docker compose exec engine python -m app.simulation.runner --from-manifest artifacts/eval/2026-06-17/study_manifest.json
```
**Success:** regenerated `per_run_metrics.parquet` is identical (same hash) to the original.

## Troubleshooting
| Symptom | Likely cause | Action |
|---------|--------------|--------|
| All allocations escalate | occupancy=100% with no LOS releases yet, or beds not seeded | check `simulation_bed_state`; verify seeding + LOS config |
| Travel times all `is_estimated=true` | no/invalid maps key | set `GOOGLE_MAPS_API_KEY` or accept Haversine (record it) |
| Non-reproducible runs | seed not threaded into RNG, or live maps used in sim | ensure distance matrix is used in sim; thread seed everywhere |
| `readyz` failing | DB not up / migrations not applied | `alembic upgrade head`; check `db` container |
| Algo 3 == Algo 2 selections everywhere | regressed to scalar `M(u)` | restore weight-vector formulation ([03 §6](./03-algorithms.md)) |
