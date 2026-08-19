"""FastAPI application factory (docs/01-architecture.md §2, docs/10-project-structure.md).

``create_app`` wires the engine together: it mounts the health router at the root and the
facility / allocation / simulation routers (Phases 1, 3, 4) under the ``/api/v1`` prefix.
Building the app in a factory keeps it constructible from tests without import-time side
effects.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Imported for its side effect: loading the module runs validate_parameters(), so a
# malformed study configuration prevents the engine from starting at all (docs/09 §12).
from app import parameters as _parameters  # noqa: F401
from app.api.routes import (
    allocations,
    audit,
    auth,
    facilities,
    health,
    registrations,
    simulation,
    users,
)
from app.config import get_settings
from app.db.session import get_engine

# Base path for all versioned resource endpoints (docs/04-api-spec.md §1).
API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: dispose the DB engine's connection pool on shutdown."""
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application.

    Swagger UI is served at ``/docs`` and the OpenAPI schema at ``/openapi.json``
    (docs/04-api-spec.md §7).
    """
    app = FastAPI(
        title="EBADS Allocation Engine",
        version="0.1.0",
        summary="Emergency Bed Allocation and Dispatch System — allocation engine.",
        lifespan=_lifespan,
    )
    # CORS so the browser (web) build of the mobile client can call the engine. Native apps
    # are unaffected; this only matters for the web target (docs/05). [IMPL]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Health probes and login/registration submission stay unauthenticated (liveness must
    # not depend on credentials; FR16 registration confers no privilege). Every other
    # router enforces auth per-route via app/security/dependencies.py::require_permission
    # — there is no router-level blanket dependency any more (docs/01 §4: the RBAC
    # decision depends on which resource/action/scope the specific route needs, which a
    # single router-wide dependency cannot express).
    app.include_router(health.router)
    app.include_router(auth.router, prefix=API_V1_PREFIX)
    app.include_router(registrations.router, prefix=API_V1_PREFIX)
    app.include_router(users.router, prefix=API_V1_PREFIX)
    app.include_router(audit.router, prefix=API_V1_PREFIX)
    app.include_router(facilities.router, prefix=API_V1_PREFIX)
    app.include_router(allocations.router, prefix=API_V1_PREFIX)
    app.include_router(simulation.router, prefix=API_V1_PREFIX)
    return app


app = create_app()
