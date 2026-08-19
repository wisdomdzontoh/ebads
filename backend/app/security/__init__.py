"""Authentication and RBAC (docs/01-architecture.md §4, docs/09-parameters.md §10).

``passwords`` and ``jwt`` are self-contained utilities. ``dependencies`` is the single
enforcement point: every protected route attaches ``get_current_user`` and/or
``require_permission(...)`` from here, and no route handler performs its own permission
check (the hard rule in docs/AGENTS.md §3).
"""

from __future__ import annotations
