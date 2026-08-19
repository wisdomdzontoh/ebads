# 09 — Parameters (Single Source of Truth)

> Every numeric constant lives here and is read from **one config module** (`backend/app/parameters.py`). Logic code must never hardcode these values. Values are from the thesis unless tagged `[IMPL]`.

## 1. Enumerations

```
Urgency  = { critical, urgent, standard }
Tier     = { tertiary, secondary, primary }
BedType  = { general, icu, maternity, specialist }
Strategy = { nearest_facility, fixed_weight, urgency_adaptive }
Status   = { pending, confirmed, arrived, expired, refused, escalated }
Role     = { system_administrator, facility_administrator, facility_staff, dispatcher }
```

## 2. Urgency-based travel-time radius R(u) — thesis Table 3.6

| Urgency | R(u) (minutes) |
|---------|----------------|
| critical | 30 |
| urgent | 60 |
| standard | 90 |

Assert: `R(critical) ≤ R(urgent) ≤ R(standard)`.

## 3. Bed types supported by tier — thesis Table 3.7

| Tier | Bed types |
|------|-----------|
| tertiary | general, maternity, icu, specialist |
| secondary | general, maternity, icu |
| primary | general, maternity |

## 4. Capability-match matrix ĉ[urgency][tier] — thesis Table 3.8

| Urgency \ Tier | tertiary | secondary | primary |
|----------------|----------|-----------|---------|
| critical | 1.0 | 0.6 | 0.2 |
| urgent | 0.8 | 1.0 | 0.5 |
| standard | 0.5 | 0.8 | 1.0 |

All values ∈ [0,1]. `ĉ` is **not** min–max normalised; it is looked up directly.

## 5. Fixed-weight strategy — thesis §3.7.4

```
w_t = 0.40   # travel time
w_b = 0.30   # bed scarcity
w_c = 0.30   # capability mismatch
```
Identical for all urgencies. Sum = 1.0.

> **Corrected.** An earlier document set recorded 0.40 / 0.35 / 0.25. Chapter Three is authoritative.

## 6. Urgency-adaptive strategy — thesis Table 3.9

| Urgency | w_t | w_b | w_c | sum |
|---------|-----|-----|-----|-----|
| critical | 0.50 | 0.10 | 0.40 | 1.00 |
| urgent | 0.40 | 0.25 | 0.35 | 1.00 |
| standard | 0.25 | 0.50 | 0.25 | 1.00 |

Each row must sum to 1.0 (±1e-9), asserted on load.

> **Corrected.** An earlier set recorded critical 0.50/0.15/0.35 and standard 0.30/0.50/0.20. Chapter Three is authoritative.

## 7. Normalisation — thesis §3.7.2

- Min–max across the **current** candidate set Hₑ, per criterion (travel time, bed count).
- Tie rule: if `x_max == x_min`, every normalised value = **0.5**.

## 8. Travel-time service

| Parameter | Value | Note |
|-----------|-------|------|
| Primary source | Google Maps Distance Matrix API | road, traffic-aware |
| Fallback | Haversine great-circle | on API unavailability |
| Fallback speed factor `[IMPL]` | 30 km/h | urban |
| Flag | `is_estimated_travel_time = true` when fallback used | always returned |

## 9. Reservation and notification — thesis §3.6.6

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `RESERVATION_GRACE_MIN` `[IMPL]` | 15 | minutes added to ETA before a reservation expires |
| `SWEEPER_INTERVAL_SEC` `[IMPL]` | 60 | how often the expiry sweeper runs |
| `SMS_CHANNEL` | sms | notification channel to the receiving facility |
| `SMS_RETRY_ATTEMPTS` `[IMPL]` | 2 | gateway retries before recording delivery failure |

Reservation lifetime is `now + eta_minutes + RESERVATION_GRACE_MIN`. A **fixed** timeout is explicitly rejected: journeys in this network differ by an order of magnitude, so a timeout generous enough for a 90-minute transfer would hold a bed far too long after a short urban one (thesis §3.6.6).

## 10. Authentication and access control — thesis §3.6.5

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `ACCESS_TOKEN_TTL_MIN` `[IMPL]` | 30 | access token lifetime |
| `REFRESH_TOKEN_TTL_DAYS` `[IMPL]` | 7 | refresh token lifetime |
| `PASSWORD_HASH` `[IMPL]` | argon2id | password hashing algorithm |
| `MIN_PASSWORD_LENGTH` `[IMPL]` | 12 | |

Role permission matrix is data, seeded by migration — see [02 §2.2](./02-data-model.md).

## 11. Scenario testing — thesis §3.8

| Parameter | Value | Basis |
|-----------|-------|-------|
| Facility set | Greater Accra public emergency-receiving facilities | GHS regional facility list |
| Case set size `[IMPL]` | 120 cases | researcher-defined; fixed and version-controlled |
| Urgency distribution `[IMPL]` | critical 20% / urgent 35% / standard 45% | triage acuity assumption |
| Bed-type distribution `[IMPL]` | general 40% / icu 30% / maternity 20% / specialist 10% | GHS facility data |
| Starting occupancy `[IMPL]` | 85% | mid-range of documented occupancy |
| Depletion | each allocation decrements availability; no release during the run | makes the test a test of policy, not of lookups |

> Case origins, urgencies and bed types are **fixed in `scenario/cases.json`** and version-controlled. There is no random sampling and no seed: the test is deterministic by construction.

## 12. Robustness check — thesis §3.8.4

One alternative weight set, with the contrast between urgency tiers deliberately reduced:

| Urgency | w_t | w_b | w_c |
|---------|-----|-----|-----|
| critical | 0.40 | 0.20 | 0.40 |
| urgent | 0.35 | 0.30 | 0.35 |
| standard | 0.30 | 0.40 | 0.30 |

Purpose is confined: establish whether any observed difference between fixed-weight and urgency-adaptive survives a change in the *degree* of urgency conditioning.

## 13. Mobile / sync — thesis §3.6.4

| Parameter | Value |
|-----------|-------|
| Background sync interval | 15 minutes |
| Cache contents | facility profiles + last-known bed counts only |
| Offline mode | read-only; no scoring executes on the device |

## 14. Validation rules asserted on config load

1. Each urgency-adaptive weight row sums to 1.0 (±1e-9).
2. Fixed weights sum to 1.0.
3. Capability matrix values ∈ [0,1].
4. `R(critical) ≤ R(urgent) ≤ R(standard)`.
5. Urgency and bed-type distributions each sum to 1.0.
6. `RESERVATION_GRACE_MIN > 0`.
7. Every bed type in the case set is supported by at least one tier.
