# 09 — Parameters (Single Source of Truth)

> Every numeric constant in EBADS lives here and is read from **one config module** (`backend/app/parameters.py`). Logic code must never hardcode these values. All values are from the thesis unless tagged `[IMPL]` (an implementation default not specified in the thesis — confirm with the researcher before evaluation runs).

## 1. Enumerations

```
Urgency  = { critical, urgent, standard }
Tier     = { tertiary, secondary, primary }
BedType  = { general, icu, maternity_specialist }
Status   = { pending, allocated, escalated }
```

## 2. Urgency-based travel-time radius R(u) — thesis Table 3.2

| Urgency | R(u) (minutes) |
|---------|----------------|
| critical | 30 |
| urgent | 60 |
| standard | 90 |

## 3. Capability-match matrix ĉ[urgency][tier] — thesis Table 3.3

| Urgency \ Tier | tertiary | secondary | primary |
|----------------|----------|-----------|---------|
| critical | 1.0 | 0.6 | 0.2 |
| urgent | 0.8 | 1.0 | 0.5 |
| standard | 0.5 | 0.8 | 1.0 |

## 4. Algorithm 2 — fixed weights (w_t, w_b, w_c) — thesis §3.5.5

```
w_t = 0.40   # travel time
w_b = 0.35   # bed scarcity
w_c = 0.25   # capability mismatch
# constraint: w_t + w_b + w_c = 1.0
```

## 5. Algorithm 3 — urgency-adaptive weight vectors — thesis Table 3.5

| Urgency | w_t | w_b | w_c | (sum) |
|---------|-----|-----|-----|-------|
| critical | 0.50 | 0.15 | 0.35 | 1.00 |
| urgent | 0.40 | 0.30 | 0.30 | 1.00 |
| standard | 0.30 | 0.50 | 0.20 | 1.00 |

Each row must sum to 1.0 (assert on load).

## 6. Normalization — thesis §3.5.2

- Method: min–max across the **current** candidate set Hₑ, per criterion.
- Tie rule: if `x_max == x_min` for a criterion, every normalised value = **0.5**.

## 7. Travel-time service — thesis §3.5.7

| Parameter | Value | Note |
|-----------|-------|------|
| Primary source | Google Maps Distance Matrix API | road, traffic-aware |
| Fallback | Haversine great-circle distance | on API unavailability |
| Fallback speed factor | 30 km/h | urban |
| Flag | `is_estimated_travel_time = true` when fallback used | always returned |

## 8. Simulation parameters — thesis Table 3.8 (as revised)

| Parameter | Value | Basis |
|-----------|-------|-------|
| Facilities in simulation | 24 public emergency-receiving facilities across the three tiers (Greater Accra) | GHS regional facility list |
| Emergency event rate | 1 event per 3–7 minutes (uniform random) | stress-test rate informed by NAS utilisation (Zakariah et al., 2024) |
| Urgency distribution | critical 20% / urgent 35% / standard 45% | modelling assumption (triage acuity patterns) |
| Bed-type distribution | general 40% / icu 30% / maternity_specialist 30% | GHS facility data |
| Occupancy scenario A | 75% | lower bound of documented range |
| Occupancy scenario B | 90% | mid range |
| Occupancy scenario C | 100% | documented peak |
| Runs per configuration per scenario | 30 | researcher-defined |
| Events per run | 100 (⇒ 3,000 events per configuration per scenario) | researcher-defined |
| Algorithm configurations | greedy, weighted, urgency_adaptive | researcher-defined |

### 8.1 Simulation constants not enumerated in the thesis `[IMPL]`

These are required to implement the virtual clock and bed lifecycle (thesis §3.12.1 describes them qualitatively). Defaults below are placeholders — **confirm with the researcher and record the chosen values before any evaluation run**, then treat them as fixed for the whole study.

| Parameter | Default `[IMPL]` | Meaning |
|-----------|------------------|---------|
| `COORDINATION_OVERHEAD_MIN` | 5 | fixed dispatch-handling overhead added to travel time in ATBP |
| `LOS_DISTRIBUTION` | exponential | length-of-stay distribution shape |
| `LOS_MEAN_MIN.general` | 2880 (48 h) | mean LOS, general beds |
| `LOS_MEAN_MIN.icu` | 5760 (96 h) | mean LOS, ICU beds |
| `LOS_MEAN_MIN.maternity_specialist` | 2160 (36 h) | mean LOS, maternity/specialist |
| `PATIENT_LOCATION_SAMPLING` | uniform over Greater Accra bounding box | source of synthetic patient coordinates |
| `GA_BBOX` | lat [5.45, 5.95], lon [-0.45, 0.25] | Greater Accra bounding box for sampling + distance matrix grid |
| `RANDOM_SEED` | 20260617 | global seed; every run records its seed |

## 9. Statistical analysis — thesis §3.12.4, §3.13.2

| Parameter | Value |
|-----------|-------|
| Significance level α | 0.05 |
| Primary test | paired t-test (per-run metric means, n=30) |
| Normality check | Shapiro–Wilk |
| Non-normal fallback | Wilcoxon signed-rank |
| Effect size | Cohen's d (paired) |
| Pairing basis | same seeded facility state + same random seed across compared configurations |

## 10. Sensitivity analysis configurations — thesis §3.13.3

- **Weights: 4 configurations.** Config 1 = default (§5 above). `[IMPL]` Configs 2–4 are systematic variants (e.g. flatter and steeper urgency gradients); record the exact four vectors here before running. All must sum to 1.0 per urgency.
- **Radii: 3 configurations.** Config 1 = default (30/60/90). `[IMPL]` Configs 2–3 are tighter and looser bands; record exact values.
- **Capability matrix: 2 configurations.** Config 1 = default (§3). Config 2 = steeper critical gradient **1.0 / 0.4 / 0.1** for critical patients (thesis §3.5.3 names this variant); other rows as agreed.

> The exact sensitivity vectors must be filled in here (not in code) and reviewed before the evaluation run, so the sensitivity study is reproducible and auditable.

## 11. Mobile / sync — thesis §3.9–3.10

| Parameter | Value |
|-----------|-------|
| Background sync interval (default) | 15 minutes |
| Cache contents | facility profiles + last-known bed counts only |
| Offline mode | read-only; no algorithm execution |

## 12. Validation rules to assert on config load

1. Each Algorithm 3 weight row sums to 1.0 (±1e-9).
2. Algorithm 2 weights sum to 1.0.
3. Capability matrix values ∈ [0, 1].
4. R(critical) ≤ R(urgent) ≤ R(standard).
5. Occupancy scenarios are exactly {0.75, 0.90, 1.00}.
6. Urgency and bed-type distributions each sum to 1.0.
