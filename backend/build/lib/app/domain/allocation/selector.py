"""Dynamic algorithm selector (docs/03-algorithms.md §8, thesis §3.6).

Chooses which algorithm runs for a request:
  - inside a simulation session → that session's configured algorithm (greedy is reachable
    only here — it is never deployed live);
  - live with a valid urgency → Algorithm 3 (urgency-adaptive), the deployed default;
  - live with missing/invalid urgency → Algorithm 2 (weighted), the safe fallback.
"""

from __future__ import annotations

from app.parameters import AlgorithmName, Urgency

VALID_URGENCIES: frozenset[Urgency] = frozenset(Urgency)


def select_algorithm(
    session_algorithm: AlgorithmName | None,
    urgency: Urgency | None,
) -> AlgorithmName:
    """Return the algorithm to run (docs/03 §8).

    Args:
        session_algorithm: the simulation session's ``algorithm_config`` if this request
            belongs to a simulation session, else ``None`` for a live request.
        urgency: the request urgency, or ``None`` if missing/invalid.
    """
    if session_algorithm is not None:
        return session_algorithm
    if urgency in VALID_URGENCIES:
        return AlgorithmName.URGENCY_ADAPTIVE
    return AlgorithmName.WEIGHTED
