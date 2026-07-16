"""Database package.

Importing this package selects a psycopg-compatible asyncio event loop on Windows.
psycopg's async support cannot run on the Proactor loop (Python's Windows default,
which lacks ``add_reader``), so the selector loop is chosen here — before any DB entry
point (Alembic's env.py, the seed script, the test harness) calls ``asyncio.run``.
Deployments run on Linux and are unaffected.
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
