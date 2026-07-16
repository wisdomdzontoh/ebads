"""Environment-backed runtime settings (docs/11-development-setup.md §2).

These are *deployment/infrastructure* values that legitimately change between
environments (database URL, API key, maps key, log level) — distinct from the
researcher-defined study constants, which live in ``parameters.py`` and must never be
overridden per-environment. Keeping the two apart is deliberate: it prevents a
deployment tweak from silently changing a thesis-defined number.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration loaded from the environment / ``infra/.env``.

    Field names map to the upper-cased environment variables documented in
    ``infra/.env.example``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Async SQLAlchemy URL for PostgreSQL 16. The default targets the docker-compose
    # `db` service; override locally when running the engine outside Docker.
    database_url: str = ""

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
