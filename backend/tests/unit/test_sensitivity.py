"""Sensitivity variant parsing + survival-table logic (docs/08 §4, docs/09 §10).

Unit-level: the shipped variants file parses into the default + steeper-critical capability
configurations, and the hypothesis-survival classification (robust / conditional /
unsupported) is computed correctly from a synthetic per-variant results table.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.analysis.sensitivity import Variant, load_variants, summarise
from app.parameters import Tier, Urgency

_SHIPPED_VARIANTS = Path("config/sensitivity.yaml")


def test_ships_default_and_capability_variants() -> None:
    """The active variants are the default and the doc-specified steeper-critical capability."""
    variants = load_variants(_SHIPPED_VARIANTS)
    names = [variant.name for variant in variants]
    assert names == ["default", "capability_steep_critical"]
    assert variants[0].family == "baseline"


def test_capability_variant_builds_steeper_critical_matrix() -> None:
    """The capability variant carries the 1.0 / 0.4 / 0.1 critical gradient (docs/09 §10)."""
    variants = load_variants(_SHIPPED_VARIANTS)
    params = variants[1].parameters()
    critical = params.capability_matrix[Urgency.CRITICAL]
    assert (critical[Tier.TERTIARY], critical[Tier.SECONDARY], critical[Tier.PRIMARY]) == (
        1.0,
        0.4,
        0.1,
    )


def _detail_row(variant: str, hypothesis: str, test: str, supported: bool) -> dict[str, object]:
    return {"variant": variant, "hypothesis": hypothesis, "test": test, "supported": supported}


def test_survival_classification() -> None:
    """Robust = holds everywhere; conditional = default only; unsupported = not in default."""
    variants = [
        Variant("default", "baseline", None, None, None),
        Variant("variant2", "capability", None, None, None),
    ]
    details = pd.DataFrame(
        [
            # H1 holds under default but fails under variant2 -> conditional.
            _detail_row("default", "H1", "paired_t", True),
            _detail_row("variant2", "H1", "paired_t", False),
            # H2 holds under both -> robust.
            _detail_row("default", "H2", "paired_t", True),
            _detail_row("variant2", "H2", "paired_t", True),
            # H3 is untestable everywhere (e.g. FRR all 1.0) -> not held in default -> unsupported.
            _detail_row("default", "H3", "none", False),
            _detail_row("variant2", "H3", "none", False),
        ]
    )
    summary = summarise(details, variants).set_index("hypothesis")
    assert summary.loc["H1", "classification"] == "conditional"
    assert summary.loc["H2", "classification"] == "robust"
    assert summary.loc["H3", "classification"] == "unsupported"
    assert bool(summary.loc["H1", "default"]) is True
    assert bool(summary.loc["H1", "variant2"]) is False
