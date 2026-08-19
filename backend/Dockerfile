# EBADS allocation engine image (docs/01-architecture.md §5, docs/11-development-setup.md §3).
FROM python:3.12-slim

# Predictable Python runtime: no .pyc files, unbuffered stdout for live container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (declared in pyproject.toml) so Docker layer caching is not
# invalidated by ordinary source edits. The "." dependency is the engine package itself.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy the application source, Alembic config, ops scripts, and the facility dataset.
# scripts/ and data/ live under backend/ so `python -m scripts.seed_facilities --source
# data/ga_facilities.csv` works from WORKDIR /app inside the container. [IMPL: docs/10
# shows scripts/ at the repo root conceptually; nesting it here keeps the engine image
# self-contained.]
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
COPY data ./data
COPY config ./config

EXPOSE 8000

# Apply migrations, (idempotently) seed the facility registry, then the first
# system_administrator (a no-op unless SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD are set — see
# scripts/create_system_admin.py; this is how platforms with no shell/exec access, like
# Render's free tier, get a first admin account at all), then serve. Baked into the image so
# hosted platforms need no fragile start-command override (Render's Docker Command field
# mis-tokenizes quoted sh -c chains). Binds all interfaces; honors the platform's $PORT,
# defaulting to 8000 for local compose.
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed_facilities --source data/ga_facilities.csv && python -m scripts.create_system_admin && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
