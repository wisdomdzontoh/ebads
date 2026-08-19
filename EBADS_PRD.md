# Product Requirements Document

**Project:** Design and Implementation of an Urgency-Adaptive Emergency Bed Allocation System
**Author:** Wisdom — BSc Computer Science, Ghana Communication Technology University
**Supervisor:** Dr. Kelvin
**Version:** 1.0
**Status:** Ready for implementation

> Every requirement below traces to a requirement in Chapter Three. Requirement IDs match the thesis exactly, so the build and the document cannot drift apart.

---

## 1. Overview

### 1.1 Problem

Emergency patients in Ghana are moved between hospitals in search of an available bed. Published evidence puts the median interval from referral to arrival in Greater Accra at roughly five hours, with fewer than a quarter of urgent cases placed within the two-hour window. Instant messaging reduced the time to *reach* a colleague without reducing the time to *placement* — establishing that the bottleneck is selecting a destination, not communication speed.

National bed-visibility infrastructure is now being deployed. It makes availability observable; it does not rank candidates, condition selection on patient acuity, or arbitrate two dispatchers claiming the same bed.

### 1.2 Solution

An allocation system that retrieves candidate facilities by spatial query, filters them by clinical admissibility, scores and ranks them under a weight vector conditioned on patient urgency, commits the selection through an atomic reservation, and notifies the receiving facility by SMS with an estimated time of arrival.

### 1.3 Goals

| # | Goal |
|---|---|
| G1 | Return a ranked, explicable facility recommendation for an emergency request |
| G2 | Condition the ranking on patient urgency, not on fixed criteria |
| G3 | Guarantee that no bed is ever committed to two patients |
| G4 | Remain independent of any single facility EMR |
| G5 | Prepare the receiving facility before the patient arrives |
| G6 | Produce reproducible evidence comparing three allocation strategies |

### 1.4 Non-goals

Do not build these.

- Clinical triage. Urgency is an input supplied by the dispatcher, never inferred.
- Ambulance siting, fleet management or vehicle routing.
- Machine learning of any kind. Interpretability is a stated requirement.
- Live connection to any facility EMR. The adapter interface is specified and a reference adapter implemented; connecting a real EMR is a deployment activity requiring institutional access.
- Patient medical records. The system stores none.
- Payment, billing or insurance.

### 1.5 Success criteria

| # | Criterion |
|---|---|
| S1 | A concurrency test shows zero double-allocation under 500 simultaneous claims on one bed |
| S2 | Recommendation returned within 2 seconds against the full Greater Accra registry |
| S3 | Candidate retrieval does not degrade linearly with registry size (index in use, verified by query plan) |
| S4 | Every recommendation reconstructable from recorded criteria, weights and scores |
| S5 | An unconfirmed reservation expires at ETA + grace and the bed returns to availability |
| S6 | Scenario test set runs to completion against all three strategies with recorded measures |
| S7 | A second adapter implementation can be registered without change to allocation code |

---

## 2. Roles and permissions

| Role | Permitted | Denied |
|---|---|---|
| **System Administrator** | Approve/reject facility registration requests; provision dispatcher accounts; configure weight vectors, radii, capability matrix, grace period; read audit log | Update bed availability for any facility |
| **Facility Administrator** | Manage user accounts within own facility; configure EMR adapter for own facility; edit own facility profile; update own bed availability | Read or modify any other facility's data |
| **Facility Staff** | Update bed availability for own facility; acknowledge incoming allocations | Manage accounts; alter configuration; read other facilities' data |
| **Dispatcher** | Submit emergency requests; receive recommendations; confirm patient arrival; view own request history | Write bed state for any facility; manage accounts |

**Separation of duties.** The party requesting a bed is never the party who declares one available, and the party configuring the scoring parameters is never the party who supplies the data those parameters act on. Both directions are enforced, and both are testable.

**Provisioning principle.** No self-service path grants any privilege. Registration creates a *request*; only approval creates an account.

---

## 3. Architecture

```
┌──────────────────┐   ┌────────────────────────┐
│ Dispatcher app   │   │ Facility admin portal  │
│ (React Native)   │   │ (React web)            │
└────────┬─────────┘   └───────────┬────────────┘
         │  HTTPS / JSON            │
         └────────────┬─────────────┘
              ┌───────▼────────┐
              │   API layer    │  chi router
              ├────────────────┤
              │ Security layer │  JWT auth, RBAC middleware, audit
              ├────────────────┤
              │ Allocation     │  filter → normalise → score → rank
              ├────────────────┤
              │ Coordination   │  CAS reservation, ETA, expiry sweeper, SMS
              ├────────────────┤
              │ Data access    │  BedDataSource adapter interface
              └───────┬────────┘
          ┌───────────┼────────────┐
   ┌──────▼─────┐          ┌───────▼──────┐
   │ PostgreSQL │          │ SMS gateway  │
   │ + PostGIS  │          │ (pluggable)  │
   └────────────┘          └──────────────┘
```

**Layer rule:** the allocation layer is a pure computation over a candidate set. It performs no I/O, holds no connection, and reads no clock. Everything stateful lives in coordination or below. This is what makes the contribution unit-testable.

---

## 4. Functional requirements

Each carries an acceptance test. Write the test with the code, not after.

### Registry and data access

**FR1** — Maintain a facility registry recording name, GHS code, capability tier, location and contact.
*Accept:* Greater Accra facilities load from GHS data; each has a valid tier and coordinates.

**FR2** — Obtain bed availability through an adapter interface such that a concrete source can be substituted without change to allocation logic.
*Accept:* Two adapters (reference GHS-data adapter, manual-entry adapter) both satisfy the interface; swapping requires no change to allocation code. Satisfies S7.

**FR3** — Retrieve candidates within an urgency-dependent radius using a spatial index, not a linear scan.
*Accept:* `EXPLAIN` on the retrieval query shows index usage, not a sequential scan.

**FR4** — Exclude candidates whose tier does not support the required bed type, or with no available bed of that type.
*Accept:* An ICU request returns no primary-tier facility. A facility with zero free beds never appears.

### Scoring and ranking

**FR5** — Normalise each criterion across the candidate set for the current request.
*Accept:* Min–max applied per request; identical values across candidates yield 0.5, no division by zero.

**FR6** — Support three selectable strategies: nearest-facility, fixed-weight, urgency-adaptive.
*Accept:* Strategy chosen by configuration; identical request under each yields the documented ranking.

**FR7** — Select the weight vector as a function of urgency under the urgency-adaptive strategy.
*Accept:* Same candidate set, urgency changed critical→standard, produces a different ranking.

### Reservation and concurrency

**FR8** — Commit only through atomic compare-and-set against the recorded bed-state version.
*Accept:* 500 concurrent claims on one bed yield exactly one success. Repeat 20×, zero violations. Satisfies S1.

**FR9** — On reservation failure, proceed to the next-ranked candidate without recomputing the candidate set.
*Accept:* Forced version conflict produces a second attempt against candidate #2, with no repeat spatial query (assert query count).

**FR10** — Expire unconfirmed reservations at ETA + configurable grace, returning the bed to availability.
*Accept:* Reservation with ETA+grace in the past is released by the sweeper within one cycle. Satisfies S5.

**FR11** — Return a structured escalation naming the nearest facility outside the radius and the nearest without an available bed, where no candidate is admissible.
*Accept:* Impossible request returns 200 with an escalation body, never an error or a silent empty result.

**FR12** — Record every allocation decision with candidate count, scores and selected facility.
*Accept:* Recomputing the score from the logged inputs reproduces the logged ranking exactly. Satisfies S4.

### Interface

**FR13** — Present the recommended facility with the reasons for its selection.
*Accept:* Response includes per-criterion normalised values, weights applied and final score for the top three.

**FR14** — Provide an offline informational mode showing last-known registry and bed data, timestamped, computing no recommendation.
*Accept:* With the network disabled, the app shows facilities with retrieval timestamps and no recommendation.

### Security

**FR15** — Authenticate every user; authorize every action against the role's permissions.
*Accept:* Unauthenticated request → 401. Authenticated but unpermitted → 403.

**FR16** — Create no account except by administrator approval; registration confers no privilege.
*Accept:* A pending registration cannot authenticate. Approval creates the facility and its first admin.

**FR17** — Prevent any account reading or modifying another facility's data, except System Administrator.
*Accept:* Facility A's admin requesting Facility B's bed state → 403. Test both read and write.

**FR18** — Prevent any dispatcher writing bed availability.
*Accept:* Dispatcher token on any bed-update endpoint → 403.

### Notification

**FR19** — Transmit SMS to the receiving facility on reservation confirmation, carrying urgency, bed type, ETA and reservation reference.
*Accept:* Confirmation produces exactly one gateway call with all four fields; the message is recorded.

**FR20** — Record facility acknowledgement where given, without making departure conditional on it.
*Accept:* Allocation reaches confirmed state with no acknowledgement. Acknowledgement, when it arrives, is stored with its timestamp.

### Portal and evaluation

**FR21** — Provide a facility administration portal for registration, adapter configuration, manual bed maintenance and user management.
*Accept:* Each function performable end-to-end by a Facility Administrator, and blocked for Facility Staff.

**FR22** — Convert reservation to admission on recorded arrival, permanently decrementing the bed.
*Accept:* Arrival confirmation decrements `available_beds` and closes the reservation.

**FR23** — Replay an identical case set against each strategy under depleting bed state, recording the specified measures.
*Accept:* Two runs of the same case set under the same strategy produce byte-identical measure output. Satisfies S6.

---

## 5. Non-functional requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR1 | Recommendation within 2 s under the modelled registry | Timed benchmark over the case set |
| NFR2 | Retrieval does not degrade linearly with registry size | Query plan + timing at 100 / 500 / 2000 facilities |
| NFR3 | No bed allocated to two patients under any interleaving | Concurrency test (FR8) |
| NFR4 | Every recommendation explicable from recorded data | Replay test (FR12) |
| NFR5 | Data-source failure degrades to informational, never silent misrouting | Adapter kill test |
| NFR6 | Scenario runs reproducible from recorded configuration | Byte-identical repeat run |
| NFR7 | No patient-identifying clinical data stored | Schema review; no name, ID or diagnosis columns |
| NFR8 | Every create/modify/approve attributable to an authenticated account | Audit log inspection |
| NFR9 | Connecting a facility EMR requires no allocation-logic change | Second adapter added without touching `internal/allocation` |

---

## 6. Data model

Tables follow the ER schema in Chapter Three (Figure 3.8).

| Table | Key columns | Notes |
|---|---|---|
| `user_account` | user_id PK, email, password_hash, role_id FK, facility_id FK (nullable), status, created_by FK | facility_id null for System Administrator and Dispatcher |
| `role` | role_id PK, name | Four rows, seeded |
| `permission` | permission_id PK, role_id FK, resource, action | Checked by middleware |
| `facility_request` | request_id PK, facility_name, ghs_code, contact, tier, status, reviewed_by FK | No privilege until approved |
| `facility` | facility_id PK, name, tier, location `geography(Point,4326)`, region, ghs_code | GIST index on location |
| `bed_state` | (facility_id, bed_type) PK, total_beds, available_beds, **version**, updated_at | version drives compare-and-set |
| `emr_adapter` | adapter_id PK, facility_id FK, adapter_type, endpoint, last_sync_at, status | |
| `emergency_request` | request_id PK, urgency, bed_type_required, origin `geography(Point,4326)`, dispatcher_id FK, created_at | No patient identifiers |
| `allocation` | allocation_id PK, request_id FK, facility_id FK, strategy_used, score, eta_minutes, status | status: pending, confirmed, arrived, expired, refused |
| `reservation` | reservation_id PK, allocation_id FK, bed_type, expires_at, acknowledged_at, confirmed | expires_at = now + eta + grace |
| `notification` | notification_id PK, allocation_id FK, channel, recipient_msisdn, sent_at, delivery_status | |
| `decision_log` | log_id PK, allocation_id FK, candidate_count, candidates_json, weights_json, rejected_reason | Enables FR12 replay |
| `audit_log` | log_id PK, user_id FK, action, entity, detail, logged_at | NFR8 |

**Spatial index:**
```sql
CREATE INDEX idx_facility_location ON facility USING GIST (location);
-- retrieval
SELECT * FROM facility
WHERE ST_DWithin(location, ST_MakePoint($lng,$lat)::geography, $radius_metres);
```

---

## 7. The adapter interface

This is the interoperability contract. Nothing above it may know which implementation is in use.

```go
// internal/datasource/adapter.go
type BedState struct {
    FacilityID    string
    BedType       string
    TotalBeds     int
    AvailableBeds int
    Version       int64
    UpdatedAt     time.Time
}

type BedDataSource interface {
    // Name identifies the adapter in configuration and logs.
    Name() string
    // Fetch returns current bed state for one facility.
    Fetch(ctx context.Context, facilityID string) ([]BedState, error)
    // Reserve attempts an atomic decrement; returns ErrVersionConflict on mismatch.
    Reserve(ctx context.Context, facilityID, bedType string, expectVersion int64) error
    // Release returns a reserved bed to availability.
    Release(ctx context.Context, facilityID, bedType string) error
    // Health reports whether the source is currently reachable.
    Health(ctx context.Context) error
}
```

Two implementations at delivery: `ManualAdapter` (portal-entered data, the default) and `GHSDataAdapter` (reference adapter over Ghana Health Service facility data). A third implementing this interface connects a real EMR without touching allocation code — this is what NFR9 and S7 verify.

---

## 8. Scoring and ranking

### Radii and tiers

| Urgency | Radius R(u) | | Tier | Bed types supported |
|---|---|---|---|---|
| Critical | 30 min | | Tertiary | General, maternity, ICU, specialist |
| Urgent | 60 min | | Secondary | General, maternity, ICU |
| Standard | 90 min | | Primary | General, maternity |

### Hard filter

```
H_e = { h ∈ H : β ∈ B(tier(h)) ∧ beds(h,β) ≥ 1 ∧ t(p,h) ≤ R(u) }
```
Empty `H_e` → structured escalation. Never relax a constraint silently.

### Normalisation

`x̂ = (x − x_min) / (x_max − x_min)`, per request, across `H_e`. All values equal → 0.5.

### Capability-match matrix

| Urgency | Tertiary | Secondary | Primary |
|---|---|---|---|
| Critical | 1.0 | 0.6 | 0.2 |
| Urgent | 0.8 | 1.0 | 0.5 |
| Standard | 0.5 | 0.8 | 1.0 |

### Weight vectors

| Urgency | w_t | w_b | w_c |
|---|---|---|---|
| Critical | 0.50 | 0.10 | 0.40 |
| Urgent | 0.40 | 0.25 | 0.35 |
| Standard | 0.25 | 0.50 | 0.25 |

Fixed-weight strategy uses 0.40 / 0.30 / 0.30 for all urgencies.

### The three strategies

```
Nearest-facility:   h* = argmin t(p,h)
Fixed-weight:       Score(h)   = 0.40·t̂ + 0.30·(1−b̂) + 0.30·(1−ĉ)
Urgency-adaptive:   Score(h,u) = w_t(u)·t̂ + w_b(u)·(1−b̂) + w_c(u)·(1−ĉ)
```
Lower is better. Rank ascending.

### Required package shape

```go
// internal/allocation/score.go — PURE. No I/O, no clock, no DB.
type Candidate struct {
    FacilityID  string
    TravelMin   float64
    FreeBeds    int
    Tier        Tier
}

type Ranked struct {
    FacilityID string
    Score      float64
    Breakdown  map[string]float64 // per-criterion contributions, for FR13 and FR12
}

func Rank(cands []Candidate, urgency Urgency, s Strategy, cfg Config) []Ranked
```

**Build this package and its table-driven tests before anything else.** It is the contribution; everything else is plumbing. It must be testable with `go test` in milliseconds, with no database running.

---

## 9. Reservation protocol

```
1. ranked ← Rank(candidates, urgency, strategy, config)
2. for each candidate in ranked:
3.     err ← source.Reserve(facilityID, bedType, expectVersion)
4.     if err == ErrVersionConflict: continue        // someone took it; next candidate
5.     if err != nil: record degradation; continue
6.     create allocation (status=pending)
7.     eta ← travelTime(origin, facility)
8.     create reservation (expires_at = now + eta + grace)
9.     send SMS (urgency, bedType, eta, reference)
10.    return recommendation with breakdown
11. no candidate succeeded → structured escalation
```

**Expiry sweeper** runs on a timer, independent of any request: releases reservations past `expires_at`, restores availability, marks the allocation expired, writes the audit entry.

**Reads are advisory; the compare-and-set is authoritative.** A stale read costs a wasted attempt. It can never cause double allocation.

---

## 10. API contracts

```
POST /api/auth/login                    → { access_token, refresh_token, role, facility_id }
POST /api/auth/refresh

POST /api/requests                      Dispatcher
  { urgency, bed_type, origin: {lat,lng} }
  200 { allocation_id, facility: {...}, eta_minutes, breakdown: [...] }
  200 { escalation: { nearest_outside_radius, nearest_without_bed, reason } }

POST /api/allocations/{id}/arrive       Dispatcher
POST /api/allocations/{id}/acknowledge  Facility Staff
POST /api/allocations/{id}/refuse       Facility Staff

GET  /api/facilities                    all roles (scoped)
PUT  /api/facilities/{id}/beds          Facility Admin/Staff, own facility only
POST /api/facilities/{id}/adapter       Facility Admin, own facility only

POST /api/registrations                 public — creates a REQUEST, no account
GET  /api/registrations                 System Admin
POST /api/registrations/{id}/approve    System Admin
POST /api/users                         System Admin (dispatchers) | Facility Admin (own facility)

GET  /api/config                        System Admin
PUT  /api/config                        System Admin — weights, radii, grace period
```

Every endpoint passes through auth then RBAC middleware. **No endpoint performs its own permission check** — centralised enforcement is what makes FR17 and FR18 testable.

---

## 11. Technology stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | **Go 1.22** + `chi` router | You are comfortable in it; strong stdlib HTTP; single deployable binary |
| Database | **PostgreSQL 16 + PostGIS** | `ST_DWithin` with a GIST index satisfies FR3 directly — no hand-rolled spatial structure |
| Migrations | `golang-migrate` | Reproducible schema; needed for NFR6 |
| Auth | JWT access + refresh; **argon2id** password hashing | Standard, defensible; argon2id is current best practice |
| Web portal | **React + TypeScript + Vite** | You have TypeScript experience |
| Mobile | **React Native (Expo) + TypeScript** | Same language as the portal; one skill covers both clients |
| SMS | Pluggable `SMSGateway` interface; Ghanaian provider (Hubtel / Arkesel / mNotify) plus a `LogGateway` for testing | Verify provider pricing and API before committing |
| Container | Docker Compose | Postgres + API + portal reproducibly |
| Charts | Go test runner emits CSV; Python (pandas, matplotlib) for thesis figures | Offline analysis; no runtime cost |

**Why PostGIS rather than implementing a k-d tree.** Chapter Two justifies spatial indexing by reference to k-d trees and R-trees. PostGIS's GIST index is an R-tree variant, so using it *is* implementing the reviewed design, not avoiding it — and you can cite Guttman (1984) honestly. Hand-rolling the structure would consume a week and add no marks.

---

## 12. Repository structure

```
ebads/
├── docker-compose.yml
├── go.mod
├── cmd/
│   ├── api/main.go                 # HTTP server
│   ├── sweeper/main.go             # reservation expiry worker
│   └── scenario/main.go            # test runner (FR23)
├── internal/
│   ├── allocation/
│   │   ├── score.go                # PURE: Rank(). No I/O.
│   │   ├── score_test.go           # table-driven — write first
│   │   ├── filter.go               # hard filter
│   │   └── normalise.go
│   ├── reservation/
│   │   ├── manager.go              # CAS loop, fall-through
│   │   └── sweeper.go              # expiry
│   ├── datasource/
│   │   ├── adapter.go              # BedDataSource interface
│   │   ├── manual.go
│   │   └── ghsdata.go
│   ├── auth/
│   │   ├── jwt.go  password.go
│   │   └── rbac.go                 # middleware; single enforcement point
│   ├── notify/
│   │   ├── gateway.go              # SMSGateway interface
│   │   ├── provider.go  log.go
│   ├── store/                      # repositories, migrations
│   ├── api/                        # handlers, routing
│   └── config/
├── migrations/
├── web/                            # React admin portal
├── mobile/                         # React Native dispatcher app
├── scenario/
│   ├── cases.json                  # the fixed case set
│   └── facilities.csv              # GHS registry data
├── test/
│   ├── concurrency_test.go         # FR8
│   └── rbac_test.go                # FR17, FR18
└── results/
    └── run-YYYYMMDD/ {config, measures.csv, decisions.jsonl}
```

---

## 13. Build order

Five increments, matching Chapter Three. **Do not start an increment before the previous one's acceptance tests pass.**

| # | Increment | Days | Deliverable | Gate |
|---|---|---|---|---|
| I0 | Skeleton | 2 | Compose, Postgres+PostGIS, migrations, health endpoint | `docker compose up` works |
| I1 | Registry, auth, RBAC | 6 | Facility registry, four roles, JWT, middleware, registration→approval flow, audit log | FR1, FR15–FR18, NFR8 |
| I2 | Adapter and bed state | 5 | `BedDataSource` interface, manual + GHS adapters, portal bed maintenance | FR2, FR21, NFR9, S7 |
| I3 | **Retrieval, filtering, scoring** | 6 | PostGIS retrieval, hard filter, normalisation, three strategies | FR3–FR7, FR13, NFR2 |
| I4 | Reservation, ETA, SMS, expiry | 6 | CAS loop, fall-through, sweeper, SMS gateway, arrival/refusal | FR8–FR12, FR19, FR20, FR22, S1, S5 |
| I5 | Scenario runner and reporting | 5 | Case set, replay under depletion, CSV output, charts | FR23, S6 |

**≈ 30 working days.**

**Critical path is I3 and I4.** I3 is the academic contribution; I4 carries all the correctness risk. Protect both.

**If time runs short, cut in this order:**
1. Mobile app → a minimal single-screen client, or demonstrate via the portal
2. Real SMS provider → `LogGateway`, documented as a simulated gateway
3. Portal polish → function over appearance

**Never cut:** the scoring package, the concurrency test, or the scenario runner. Those three are your thesis.

---

## 14. Test plan

| Level | What | Tool |
|---|---|---|
| Unit | `Rank()` — each strategy, tie-breaking, single-candidate, identical-value normalisation | `go test`, table-driven |
| Unit | Hard filter — tier/bed-type/radius exclusion | `go test` |
| Unit | Capability matrix and weight selection by urgency | `go test` |
| Integration | 500 concurrent claims on one bed → exactly one success, ×20 | `go test` + goroutines |
| Integration | Version conflict → falls through to candidate #2, no re-query | `go test` + query counter |
| Integration | RBAC matrix — every role × every endpoint | `go test`, table-driven |
| Integration | Cross-facility access denied (read and write) | `go test` |
| Integration | Sweeper releases expired reservation within one cycle | `go test` + clock injection |
| Integration | Second adapter registered, allocation code untouched | `go test` + `git diff` evidence |
| System | Scenario set × three strategies, repeat run byte-identical | `cmd/scenario` |

---

## 15. Scenario test design

**Facility data:** Greater Accra registry from GHS data — name, tier, coordinates, supported bed types.

**Case set** (`scenario/cases.json`), fixed and version-controlled. Each case: `{origin_lat, origin_lng, urgency, bed_type}`. Construct to span:
- Dense urban origins (Circle, Osu, Madina) and peripheral (Kasoa fringe, Prampram)
- All three urgency tiers, in realistic proportion
- Bed types with wide availability (general) and narrow (ICU, specialist)
- At least a few cases with **no** admissible candidate, to exercise escalation

**Protocol:** identical starting bed state per strategy; identical case order; each success depletes availability. No randomness anywhere.

**Measures per strategy:** travel time to placement; escalation rate; facility attempts per case; mean capability match; proportion of critical cases at tertiary facilities; placement success rate. Report disaggregated by urgency tier — an aggregate mean hides the effect under test.

**Robustness check:** one re-run under a reduced-contrast weight set (e.g. critical 0.40/0.20/0.40, standard 0.30/0.40/0.30) to establish whether any fixed-weight vs urgency-adaptive difference survives a change in the degree of urgency conditioning.

---

## 16. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scope too large for the schedule | **High** | High | Cut in the stated order; protect I3–I5 absolutely |
| GHS facility data incomplete or lacking coordinates | Medium | Medium | Geocode manually for the Greater Accra subset; document the source and any gaps |
| SMS provider integration blocked (account, cost, KYC) | Medium | Low | `LogGateway` behind the same interface; document as simulated |
| Travel time estimation crude | High | Medium | Use straight-line distance × road factor; state it in limitations, already conceded in Chapter One |
| Concurrency bug found late | Low | High | Write the concurrency test in I4 *before* the manager, not after |
| Three strategies show no meaningful difference | Medium | **Low** | This is a reportable finding; Chapter Three states expectations in advance |

---

## 17. Traceability

| Objective (Ch. 1) | Requirements | Increment |
|---|---|---|
| O1 — engine with adapter, RBAC, spatial index, atomic reservation | FR1–FR4, FR8–FR10, FR15–FR18 | I1, I2, I3, I4 |
| O2 — three strategies, complexity, online behaviour | FR5–FR7, FR12, FR13 | I3 |
| O3 — evaluate by scenario testing on GHS data | FR23 | I5 |
| O4 — dispatcher app, portal, SMS notification | FR14, FR19–FR22 | I2, I4 |

---

## 18. Definition of done

- All 23 functional requirements have passing acceptance tests
- All 9 non-functional requirements verified, with evidence recorded
- Scenario set run against all three strategies; measures archived with configuration
- Robustness check completed under the alternative weight set
- Chapter Four written from the recorded implementation and results
- Repository reproducible from `docker compose up` plus a documented seed command

---

## 19. Writing Chapter Four alongside the build

Do not wait until the end.

| After | Draft this section of Chapter Four |
|---|---|
| I0–I1 | Tools and technologies; database schema as built; authentication and access control implementation |
| I2 | Adapter interface; interoperability discussion |
| I3 | Scoring and ranking implementation; the worked example; complexity in practice |
| I4 | Reservation protocol; concurrency test evidence; notification |
| I5 | Results, measures, charts, robustness check, discussion against expectations E1–E3 |

Only the results section genuinely requires the finished system. Chapter Five follows from Chapter Four's findings and is written last.
