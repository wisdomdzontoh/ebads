"""Evaluation & analysis package (docs/08-evaluation.md — see the discrepancy this predates).

**Exploratory, not the reported evaluation instrument.** This package turns ``app/simulation``'s
per-run metrics into inferential statistics (H1/H2/H3 hypothesis tests, a sensitivity sweep
over parameter variants) — the discrete-event-simulation methodology the thesis moved away
from at §3.8. The current, reported methodology is descriptive comparison over
``app/scenario``'s deterministic case-set replay (docs/07 §1, §8): thesis Table 3.10's
measures, and one confined robustness check under a single alternative weight table — not a
hypothesis test and not a parameter sweep. No figure in the thesis results is sourced from
this package.

It remains in the repository, unmodified beyond this note, because it is part of the same
1,750-line exploratory subsystem as ``app/simulation`` and removing it this close to
submission is unnecessary risk — not because it is still in use. ``statistics`` runs the
H1/H2/H3 hypothesis tests, ``sensitivity`` re-runs the grid under parameter variants and
tabulates which findings are robust, and ``report`` produces the figures and the
reproducibility manifest.
"""
