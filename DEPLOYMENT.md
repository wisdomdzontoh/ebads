# Deploying the EBADS Engine (Free Tier)

This guide deploys the EBADS allocation engine (FastAPI + PostgreSQL) to **free** managed
services, step by step, and then points the mobile app at it:

| Piece | Service | Why |
|---|---|---|
| Engine (FastAPI, Docker) | **Render** (free web service) | Builds the existing `backend/Dockerfile` straight from GitHub; free HTTPS URL; no card required. |
| Database (PostgreSQL 16) | **Neon** (free tier) | Durable free Postgres (Render's own free Postgres **expires after 30 days**, Neon's does not); no card required. |

The result is a public HTTPS URL like `https://ebads-engine.onrender.com/api/v1` that the
mobile app connects to from anywhere — no LAN IP, no cleartext traffic.

> **Time required:** ~20 minutes. **Cost:** $0.

---

## 0. Prerequisites

- A [GitHub](https://github.com) account.
- A [Render](https://render.com) account (sign up with GitHub — free, no card).
- A [Neon](https://neon.tech) account (sign up with GitHub — free, no card).
- Git installed locally.

---

## 1. Push the project to GitHub

Render deploys from a GitHub repository. The project is not a git repo yet, so from the
project root (`F:\final-project\ebads`):

```powershell
git init
git add .
git commit -m "EBADS: engine + mobile app"
```

> **Check first:** `infra/.env` and `mobile/.env` hold secrets and must NOT be committed.
> Confirm they are ignored before committing: `git status` must not list them. If it does,
> add them to `.gitignore` first.

Create an empty repository on GitHub (e.g. `ebads`), then:

```powershell
git remote add origin https://github.com/<your-username>/ebads.git
git branch -M main
git push -u origin main
```

The repo can be **private** — Render and Neon both work with private repos.

---

## 2. Create the free Postgres database (Neon)

1. Go to [console.neon.tech](https://console.neon.tech) → **New Project**.
2. Name: `ebads` · Postgres version: **16** · Region: pick the closest to your Render region
   (e.g. both in Frankfurt or both in US East — keeps latency low).
3. After creation, open **Dashboard → Connection Details** and copy the connection string.
   It looks like:

   ```
   postgresql://neondb_owner:AbC123xyz@ep-cool-name-a1b2c3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

4. **Use it as-is — this is your `DATABASE_URL`.** No conversion needed: the engine
   normalizes the scheme onto its async psycopg driver at startup (`app/config.py`), and
   psycopg understands Neon's `sslmode` / `channel_binding` options natively.

Keep this value handy for step 3.

---

## 3. Deploy the engine on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New → Web Service**.
2. **Connect your GitHub repo** (`ebads`). Authorize Render if asked.
3. Configure the service:

   | Setting | Value |
   |---|---|
   | Name | `ebads-engine` (becomes `https://ebads-engine.onrender.com`) |
   | Region | Closest to your Neon region |
   | Branch | `main` |
   | **Root Directory** | `backend` ← important: the Dockerfile lives here |
   | Runtime / Language | **Docker** (Render auto-detects `backend/Dockerfile`) |
   | Instance Type | **Free** |

4. **Environment variables** (Add Environment Variable, one per row):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string from step 2, pasted verbatim |
   | `JWT_SECRET_KEY` | a strong random key — generate one: `openssl rand -hex 32` (Git Bash) |
   | `CORS_ALLOW_ORIGINS` | `*` (fine for the prototype; restrict later if you host the web build) |
   | `LOG_LEVEL` | `info` |

   > `JWT_SECRET_KEY` signs every access/refresh token (docs/01 §4). Leaving it blank
   > doesn't disable auth (unlike the old `API_KEY` scheme this replaced) — every
   > authenticated request fails with a 500 until it's set. There is no `API_KEY` variable
   > any more; remove it from the environment if it's still set from an earlier deploy.

5. **Docker Command** (Settings → Docker Command): **leave it empty.** The image's own
   start command already runs the migrations, seeds the facility registry (idempotent —
   safe to re-run), and starts the API on Render's `$PORT` (see `backend/Dockerfile`).
   Do not wrap a command in `sh -c "…"` here — Render mis-tokenizes the quotes and the
   deploy exits with status 127.

6. **Health Check Path** (Settings → Health Checks): `/healthz`

7. Click **Deploy Web Service** and watch the logs. First build takes a few minutes. You
   should see the Alembic migrations run to the latest revision, the seed summary
   (24 facilities), then `Uvicorn running on 0.0.0.0:…`.

8. **Bootstrap the first account.** No HTTP endpoint can create one (every `/users` route
   needs an existing system_administrator caller — that's deliberate, FR16). From a shell
   with the deployed `DATABASE_URL` exported, run once:
   ```bash
   cd backend
   DATABASE_URL=<the Neon connection string> python -m scripts.create_system_admin \
     --email you@example.com --password '<a strong password>'
   ```
   This is the one out-of-band exception — every account after this one is created through
   the API by an already-authenticated admin.

---

## 4. Verify the deployment

From any terminal (replace the URL and credentials with yours):

```bash
# Liveness — no auth required
curl https://ebads-engine.onrender.com/healthz
# → {"status":"ok"}

# Readiness — checks the database connection
curl https://ebads-engine.onrender.com/readyz
# → {"status":"ready"}

# Auth is enforced: no token → 401
curl -i https://ebads-engine.onrender.com/api/v1/facilities
# → HTTP/1.1 401 Unauthorized

# Log in as the account from step 8, then use its access token → 200
TOKEN=$(curl -s -X POST https://ebads-engine.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"<your password>"}' | python -c \
  'import json,sys; print(json.load(sys.stdin)["access_token"])')
curl -H "Authorization: Bearer $TOKEN" https://ebads-engine.onrender.com/api/v1/facilities
```

If all five behave as shown, the engine is live.

---

## 5. Point the mobile app at it

**Currently broken, not yet a config step.** The deployed dispatcher app's Settings screen
still has only a base-URL + static "API key" field — the connection test and every API
call it makes use the retired `X-API-Key` header, which the engine no longer accepts as of
the auth/RBAC work. Pointing the app at a freshly deployed engine will fail the connection
test and every subsequent call with 401s. The app needs a real login screen (email +
password → `/auth/login`, storing the returned access/refresh tokens) before this section
can be restored — tracked as follow-up work, not done in this pass.

Because the URL is HTTPS, the Android cleartext-traffic exception in `app.json`
(`usesCleartextTraffic: true`) is no longer needed for this engine — it can be removed once
you stop using plain-HTTP LAN engines.

---

## 6. Free-tier behaviour you should know about

| Behaviour | What you'll see | What to do |
|---|---|---|
| **Render free services sleep** after 15 min without traffic | The first request after idle takes **~50–60 s** (cold start). The app's connection test times out at 10 s, so the *first* "Save & test" after a long idle may report a network failure. | Tap **Test connection** again after ~1 minute — the service is waking, not broken. |
| Keep-warm (optional) | — | A free monitor ([cron-job.org](https://cron-job.org) or [UptimeRobot](https://uptimerobot.com)) pinging `https://…/healthz` every 10 min keeps it awake. One always-on service fits in Render's 750 free instance-hours/month (a 31-day month is 744 h). |
| **Neon autosuspends** after ~5 min idle | First DB query after idle adds ~1 s. | Nothing — it's transparent. |
| Free instance = 512 MB RAM, shared CPU | Allocations and small simulation runs are fine; very large simulation grids belong on your dev machine (RB-6 runner), not this instance. | Use the deployed engine for dispatch/demo, the local stack for studies. |

---

## 7. Updating the deployment

- **Code changes:** `git push` to `main` → Render auto-builds and redeploys (migrations +
  seed run automatically via the Docker Command).
- **Rotate the signing key:** Render → Environment → edit `JWT_SECRET_KEY` → Save (service
  restarts). Every previously issued access/refresh token is invalidated — every account
  must log in again.
- **Logs:** Render → your service → **Logs** (live tail; allocation requests, migrations,
  seed output all appear here).
- **Database console:** Neon → **SQL Editor** to inspect `facility`, `bed_count`,
  `emergency_request` tables directly.

---

## Alternatives considered

| Service | Verdict |
|---|---|
| **Render free Postgres** | Works, but the free database **expires after 30 days** — Neon doesn't. |
| **Koyeb** | Also has a free Docker web service; fine fallback if Render changes its free tier. Same env vars + start command apply. |
| **Railway** | Trial credit only — not durably free. |
| **Fly.io** | Requires a credit card. |
| **PythonAnywhere / Vercel** | Poor fit for a long-lived async FastAPI + asyncpg pool. |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails: `pyproject.toml not found` | Root Directory not set | Set **Root Directory = `backend`** in the service settings. |
| Deploy exits with status 127: `sh: 1: alembic upgrade head && …: not found` | A quoted `sh -c "…"` chain in Render's Docker Command field | Clear the field (step 3.5) — the image runs migrations + seed + API by itself. |
| Logs: password / SSL errors on startup | `DATABASE_URL` mangled | Re-paste the Neon connection string exactly as Neon shows it (step 2.4) — no manual edits needed. |
| `/readyz` returns 503 | Engine up, DB unreachable | Neon project paused/deleted, or wrong host in `DATABASE_URL`. Test the URL in Neon's SQL editor. |
| `POST /auth/login` returns 401 | Wrong email/password, account suspended, or `JWT_SECRET_KEY` unset (500, not 401 — check logs) | Re-check credentials; confirm `JWT_SECRET_KEY` is set in step 4. |
| App connection test fails only on the *first* try after idle | Render cold start | Wait ~1 min, test again (see §6). |
| Migration fails: `extension "postgis" is not available` | Neon project predates PostGIS being enabled | Neon supports PostGIS natively — run `CREATE EXTENSION IF NOT EXISTS postgis;` once in Neon's SQL Editor if the migration's own `CREATE EXTENSION` is blocked by role permissions, then re-deploy. |
