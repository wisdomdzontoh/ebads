"""Evaluation & analysis package (docs/08-evaluation.md).

Turns the simulation's per-run metrics into thesis results: ``statistics`` runs the H1/H2/H3
hypothesis tests, ``sensitivity`` re-runs the grid under parameter variants and tabulates
which findings are robust, and ``report`` produces the figures and the reproducibility
manifest. None of these predetermine outcomes — a non-significant or negative result is a
valid finding and is reported in full (docs/08 header, §7).
"""
