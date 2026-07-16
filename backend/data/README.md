# Facility dataset — `ga_facilities.csv`

> ⚠️ **BEST-EFFORT SYNTHETIC DATA — FOR RESEARCHER REVIEW BEFORE ANY EVALUATION RUN.**

This file is the single place the facility set is defined for the study
([docs/11 §5](../../docs/11-development-setup.md)). It currently holds **24** Greater Accra
public emergency-receiving facilities spread across the three capability tiers
(4 tertiary / 10 secondary / 10 primary).

## Provenance & status of each column

| Column | Status |
|--------|--------|
| `name` | Real, well-known Greater Accra public facilities. |
| `latitude`, `longitude` | **Approximate** decimal coordinates, all inside the GA bounding box (`GA_BBOX` in [parameters.py](../app/parameters.py)). Verify against an authoritative source before publishing results. |
| `tier` | **Best-effort** classification; confirm each facility's true capability tier with the GHS Greater Accra facility list. |
| `supported_bed_types`, `capacity_*` | **Synthetic / plausible** — not official bed returns. These drive simulation capacity seeding and must be reviewed/replaced with GHS data before the evaluation grid is run. |
| `contact_phone` | **Placeholder** numbers; not verified. |

## What must happen before evaluation

Per [docs/PRD.md §9](../../docs/PRD.md) and [docs/AGENTS.md](../../docs/AGENTS.md), study
inputs are a research responsibility. Replace the approximate coordinates, tiers, and
capacities with values traceable to the GHS regional facility list (or another citable
public source), then treat this file as fixed for the whole study.

## Format

`supported_bed_types` is a `|`-separated subset of `{general, icu, maternity_specialist}`.
A `capacity_*` column is `0` for any bed type the facility does not support. The seed script
sets live availability equal to capacity on load (simulation seeds occupancy separately).

Reload with: `python -m scripts.seed_facilities --source data/ga_facilities.csv`
(idempotent — upserts by name).
