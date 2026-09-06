"""Scenario test runner (FR23, docs/07-scenario-testing.md).

Replays a fixed, version-controlled case set through the live allocation engine
(``domain/allocation/service.py``) against each matching strategy in turn, under
depleting bed state — the reported evaluation instrument (docs/07 §2). There is no
stochastic sampling anywhere in this package (NFR6, docs/07 §3): the case set, the starting
bed state, and the tie-break (``domain/allocation/scoring.py``'s ``score, travel_time,
facility_id``) are all deterministic by construction, so two runs of the same case set
under the same parameters produce byte-identical measure output.

This package is distinct from — and not built on — ``app/simulation``/``app/analysis``,
the discrete-event simulation subsystem those packages' own docstrings now mark as
exploratory and superseded by this one for reported results.

Modules: ``case_set`` (load the fixed case list), ``runner`` (populate the registry, replay
one case set per strategy under depletion, the contention-mode burst, and the CLI),
``measures`` (thesis Table 3.10, overall and per urgency tier), ``report`` (the
cross-strategy comparison table and the §3.8.4 robustness re-run).
"""

from __future__ import annotations
