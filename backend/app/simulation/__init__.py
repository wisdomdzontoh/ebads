"""Discrete-event simulation package (docs/07-scenario-testing.md — see the banner).

**Exploratory, not the reported evaluation instrument.** This package predates the §3.8
methodology change to scenario-based testing on real facility data: it generates *synthetic*
emergency events with a stochastic arrival process and a seeded random-number generator,
which the current thesis methodology deliberately does not use (docs/07 §1 — the fidelity of
a modelled arrival process to genuine emergency demand cannot be established, so no
conclusion should rest on it). ``app/scenario/`` — the fixed-case-set replay against real
facility data under depleting bed state — is the reported evaluation instrument (FR23). No
figure in the thesis results is sourced from this package.

It remains in the repository, unmodified beyond this note, because it is 1,750 lines with
its own passing test suite and removing it this close to submission is unnecessary risk —
not because it is still in use. See ``events`` (synthetic event generation), ``distance_matrix``
(precomputed travel times), ``engine`` (the event loop), ``metrics`` (ATBP/FRR/MCEE/CM),
``service`` (session lifecycle), and ``runner`` (the batch grid).
"""
