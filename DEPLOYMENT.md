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

4. **Convert it for the engine** (SQLAlchemy + asyncpg). Two changes:
   - scheme `postgresql://` → `postgresql+asyncpg://`
   - query string `?sslmode=require&channel_binding=require` → `?ssl=require`
     (asyncpg uses `ssl`, not `sslmode`)

   Result — this is your `DATABASE_URL`:

   ```
   postgresql+asyncpg://neondb_owner:AbC123xyz@ep-cool-name-a1b2c3.eu-central-1.aws.neon.tech/neondb?ssl=require
   ```

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
   | `DATABASE_URL` | the `postgresql+asyncpg://…?ssl=require` URL from step 2 |
   | `API_KEY` | a strong random key — generate one: `openssl rand -hex 32` (Git Bash) |
   | `CORS_ALLOW_ORIGINS` | `*` (fine for the prototype; restrict later if you host the web build) |
   | `LOG_LEVEL` | `info` |

   > `API_KEY` is what the mobile app must send as `X-API-Key`. Leaving it blank would
   > disable auth on a public URL — don't.

5. **Docker Command** (Settings → Docker Command, or "Advanced" during creation). Override it
   so every deploy runs migrations, seeds the facility registry (idempotent — safe to re-run),
   and then starts the API on Render's port:

   ```
   sh -c "alembic upgrade head && python -m scripts.seed_facilities --source data/ga_facilities.csv && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
   ```

6. **Health Check Path** (Settings → Health Checks): `/healthz`

7. Click **Deploy Web Service** and watch the logs. First build takes a few minutes. You
   should see the Alembic migrations (`0001` → `0004`), the seed summary (24 facilities),
   then `Uvicorn running on 0.0.0.0:…`.

---

## 4. Verify the deployment

From any terminal (replace the URL and key with yours):

```bash
# Liveness — no auth required
curl https://ebads-engine.onrender.com/healthz
# → {"status":"ok"}

# Readiness — checks the database connection
curl https://ebads-engine.onrender.com/readyz
# → {"status":"ready"}

# Auth is enforced: no key → 401
curl -i https://ebads-engine.onrender.com/api/v1/facilities
# → HTTP/1.1 401 Unauthorized

# With the key → 24 facilities
curl -H "X-API-Key: <your API_KEY>" https://ebads-engine.onrender.com/api/v1/facilities
```

If all four behave as shown, the engine is live.

---

## 5. Point the mobile app at it

In the app: **Settings → Connection**

- **API base URL:** `https://ebads-engine.onrender.com/api/v1`
- **API key:** the exact `API_KEY` value from step 3
- Tap **Save & test connection** → you should see **“Connected · Engine verified · 24
  facilities”**. The facility cache then syncs automatically.

(New installs can do the same thing in the onboarding **“Connect to the Engine”** step.)

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
- **Rotate the API key:** Render → Environment → edit `API_KEY` → Save (service restarts).
  Then update the key in the app's Settings and re-test.
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
| Logs: `InvalidPasswordError` / SSL errors on startup | `DATABASE_URL` not converted | Re-check step 2.4: scheme `postgresql+asyncpg://`, query `?ssl=require`, nothing else. |
| `/readyz` returns 503 | Engine up, DB unreachable | Neon project paused/deleted, or wrong host in `DATABASE_URL`. Test the URL in Neon's SQL editor. |
| App says "engine rejected the API key" | Key mismatch | The app must send the *exact* `API_KEY` value — no extra spaces. Re-paste both sides. |
| App connection test fails only on the *first* try after idle | Render cold start | Wait ~1 min, test again (see §6). |
