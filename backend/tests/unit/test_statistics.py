"""Hypothesis-test procedure (docs/08-evaluation.md §3, docs/12 §6).

Verifies the branch logic (normal → paired t; non-normal → Wilcoxon), agreement with SciPy on
the same inputs, a hand-computed paired Cohen's d, the honest handling of undefined metrics
(no data / no variation), and that a directional hypothesis is only "supported" when the
result is both significant *and* in the predicted direction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from app.analysis.statistics import (
    Comparison,
    _cohens_d_paired,
    analyze,
)
from app.parameters import AlgorithmName


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _paired_frame(metric: str, occupancy: float, a_values: list[float], b_values: list[float]):
    """Build a per-run frame with config_a='weighted', config_b='greedy' at one occupancy."""
    rows: list[dict[str, object]] = []
    for run_index, (a, b) in enumerate(zip(a_values, b_values, strict=True)):
        rows.append(
            {"algorithm": "weighted", "occupancy": occupancy, "run_index": run_index, metric: a}
        )
        rows.append(
            {"algorithm": "greedy", "occupancy": occupancy, "run_index": run_index, metric: b}
        )
    return _frame(rows)


_H1_ONLY = (
    Comparison(
        "H1", "atbp", AlgorithmName.WEIGHTED, AlgorithmName.GREEDY, "lower", (0.75,),
        "Weighted lower ATBP than Greedy",
    ),
)


def test_cohens_d_matches_hand_computation() -> None:
    """Paired Cohen's d = mean(diff) / sample-std(diff)."""
    diffs = np.array([-2.0, -4.0, -6.0, -8.0])
    expected = float(np.mean(diffs)) / float(np.std(diffs, ddof=1))
    assert abs(_cohens_d_paired(diffs) - expected) < 1e-12


def _normal_pair(mean_diff: float, seed: int = 0, n: int = 20) -> tuple[list[float], list[float]]:
    """Deterministic paired vectors whose differences (a-b) are ~normal with the given mean."""
    rng = np.random.default_rng(seed)
    diffs = rng.normal(mean_diff, 1.2, n)
    b = rng.normal(15.0, 2.0, n)
    a = b + diffs
    return list(a), list(b)


def test_normal_differences_use_paired_t_and_match_scipy() -> None:
    """Normal paired differences select the t-test and match scipy.ttest_rel exactly."""
    a, b = _normal_pair(mean_diff=-4.0)
    result = analyze(_paired_frame("atbp", 0.75, a, b), _H1_ONLY).iloc[0]

    reference = stats.ttest_rel(np.array(a), np.array(b))
    assert result["test"] == "paired_t"
    assert result["df"] == len(a) - 1
    assert abs(result["statistic"] - float(reference.statistic)) < 1e-9
    assert abs(result["p_value"] - float(reference.pvalue)) < 1e-9
    # Weighted (a) is lower than Greedy (b), significantly, in the predicted direction.
    assert result["direction_observed"] == "lower"
    assert bool(result["significant"])
    assert bool(result["supported"])


def test_non_normal_differences_use_wilcoxon() -> None:
    """Heavily skewed paired differences fail Shapiro and fall back to Wilcoxon (docs/08 §3)."""
    # One huge outlier difference makes the differences clearly non-normal.
    a = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    b = [1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 100.0]
    result = analyze(_paired_frame("atbp", 0.75, a, b), _H1_ONLY).iloc[0]
    assert result["test"] == "wilcoxon"
    assert result["df"] is None


def test_wrong_direction_is_significant_but_not_supported() -> None:
    """A significant result in the opposite direction is reported, not counted as support."""
    # 'weighted' comes out HIGHER than 'greedy' — opposite of the H1 prediction ("lower").
    a, b = _normal_pair(mean_diff=+8.0)
    result = analyze(_paired_frame("atbp", 0.75, a, b), _H1_ONLY).iloc[0]
    assert bool(result["significant"])
    assert result["direction_observed"] == "higher"
    assert not bool(result["supported"])


def test_all_equal_metric_is_no_variation() -> None:
    """When both configs are identical every run (e.g. FRR=1.0 at 100%), no test is defined."""
    a = [1.0] * 6
    b = [1.0] * 6
    result = analyze(_paired_frame("atbp", 0.75, a, b), _H1_ONLY).iloc[0]
    assert result["test"] == "none"
    assert result["note"] == "no_variation"
    assert not bool(result["supported"])


def test_all_nan_metric_is_insufficient_data() -> None:
    """An undefined metric (all NaN, e.g. ATBP when every event escalates) is not fabricated."""
    a = [float("nan")] * 6
    b = [float("nan")] * 6
    result = analyze(_paired_frame("atbp", 0.75, a, b), _H1_ONLY).iloc[0]
    assert result["n"] == 0
    assert result["test"] == "none"
    assert result["note"] == "insufficient_data"


def test_default_comparisons_cover_the_hypothesis_table() -> None:
    """The default comparison set matches the H1/H2/H3 rows of docs/08 §2 (11 rows total)."""
    # Full synthetic grid so analyze() produces one row per (comparison × scenario).
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(0)
    for algorithm in ("greedy", "weighted", "urgency_adaptive"):
        for occupancy in (0.75, 0.90, 1.00):
            for run_index in range(30):
                rows.append(
                    {
                        "algorithm": algorithm,
                        "occupancy": occupancy,
                        "run_index": run_index,
                        "atbp": float(rng.normal(30, 2)),
                        "frr": float(rng.uniform(0, 0.2)),
                        "cm_critical": float(rng.uniform(0.4, 1.0)),
                    }
                )
    results = analyze(_frame(rows))
    # H1: 3 scenarios; H2: 2 metrics × 3 scenarios = 6; H3: 2 comparisons × 1 scenario = 2 => 11.
    assert len(results) == 11
    assert set(results["hypothesis"]) == {"H1", "H2", "H3"}
