"""Environment-backed runtime settings (docs/11-development-setup.md §2).

These are *deployment/infrastructure* values that legitimately change between
environments (database URL, API key, maps key, log level) — distinct from the
researcher-defined study constants, which live in ``parameters.py`` and must never be
overridden per-environment. Keeping the two apart is deliberate: it prevents a
deployment tweak from silently changing a thesis-defined number.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Coerce any common Postgres URL onto the async psycopg (v3) dialect.

    Accepts the URL exactly as a hosting provider hands it out: ``postgres://``
    (Heroku-era), plain ``postgresql://`` (Neon/Render), or a URL written for the
    previous asyncpg driver. libpq query options such as ``sslmode`` and
    ``channel_binding`` pass through to psycopg untouched; only asyncpg's ``ssl=``
    spelling is renamed to ``sslmode=``. Also used by the integration-test harness
    so ``TEST_DATABASE_URL`` follows the same contract as ``DATABASE_URL``.
    """
    value = re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql+psycopg://", value.strip())
    return re.sub(r"([?&])ssl=", r"\1sslmode=", value)


class Settings(BaseSettings):
    """Process configuration loaded from the environment / ``infra/.env``.

    Field names map to the upper-cased environment variables documented in
    ``infra/.env.example``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Async SQLAlchemy URL for PostgreSQL 16. The default targets the docker-compose
    # `db` service; override locally when running the engine outside Docker. Providers'
    # connection strings (Neon, Render, Heroku) can be pasted verbatim — the validator
    # below normalizes the scheme and SSL parameter to what the psycopg driver expects.
    database_url: str = "postgresql+psycopg://ebads:ebads@db:5432/ebads"

    # Static API key for the prototype's X-API-Key auth (docs/04-api-spec.md §1). [IMPL]
    # Blank disables the check (unit/integration tests, bare local dev); the deployed stack
    # sets API_KEY in infra/.env, so /api/v1 is enforced there (app/api/security.py).
    api_key: str = ""

    # Optional Google Distance Matrix key; blank => Haversine fallback (docs/09 §7).
    google_maps_api_key: str = ""

    # Precomputed simulation distance matrix (docs/07 §3, RB-4). When this file exists the
    # simulation API serves travel times from it; otherwise it builds an in-memory Haversine
    # matrix from the registered facilities on first use. Build a study matrix with RB-4.
    distance_matrix_path: str = "artifacts/distance_matrix.parquet"

    # Allowed CORS origins for the browser (web) build of the mobile client. Comma-separated,
    # or "*" for any origin (the prototype default — native apps are unaffected by CORS). [IMPL]
    cors_allow_origins: str = "*"

    log_level: str = "info"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Providers' connection strings work pasted verbatim (see normalize_database_url)."""
        return normalize_database_url(value)

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse ``cors_allow_origins`` into the list FastAPI's CORS middleware expects."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so the environment is read once; FastAPI dependencies and the DB session
    factory share the same instance.
    """
    return Settings()
