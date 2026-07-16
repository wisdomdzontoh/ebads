"""Hypothesis testing over the per-run metrics (docs/08-evaluation.md §2-3, RB-7).

Implements the exact statistical procedure from docs/08 §3 for each comparison in the H1/H2/H3
table (docs/08 §2, thesis Table 3.9):

1. take the paired per-run metric means for two configurations (paired by run index — same
   seed, same seeded facility state, docs/07 §7);
2. **normality**: Shapiro–Wilk on the paired differences;
3. **test**: paired t-test if normal, else Wilcoxon signed-rank;
4. **effect size**: paired Cohen's d;
5. report test, statistic, df, p-value, Cohen's d, and the signed mean difference.

The hypotheses are directional but **not** predetermined: a comparison whose result is
non-significant, or significant in the *opposite* direction, is reported honestly
(``supported = false``). Undefined metrics — e.g. ATBP at 100 % occupancy when every event
escalates — yield an ``insufficient_data`` row rather than a fabricated number (docs/08 §7).

CLI (RB-7)::

    python -m app.analysis.statistics --input per_run_metrics.parquet --out hypothesis_tests.csv
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from app.parameters import SIGNIFICANCE_ALPHA, AlgorithmName

# Metric column names as they appear in the runner's per-run dataset (docs/07 §8).
ATBP = "atbp"
FRR = "frr"
CM_CRITICAL = "cm_critical"

# Minimum paired sample size for a meaningful normality test (Shapiro–Wilk needs n >= 3).
_MIN_SAMPLES = 3


@dataclass(frozen=True)
class Comparison:
    """One hypothesis comparison: config A vs config B on a metric, in a direction (docs/08 §2)."""

    hypothesis: str
    metric: str
    config_a: str  # the treatment configuration
    config_b: str  # the baseline configuration
    direction: str  # expected direction of A relative to B: "lower" | "higher"
    scenarios: tuple[float, ...]
    description: str


# The H1/H2/H3 comparisons exactly as specified in docs/08 §2 (thesis Table 3.9).
_ALL_SCENARIOS = (0.75, 0.90, 1.00)
DEFAULT_COMPARISONS: tuple[Comparison, ...] = (
    Comparison(
        "H1", ATBP, AlgorithmName.WEIGHTED, AlgorithmName.GREEDY, "lower", _ALL_SCENARIOS,
        "Weighted yields lower ATBP than Greedy",
    ),
    Comparison(
        "H2", ATBP, AlgorithmName.URGENCY_ADAPTIVE, AlgorithmName.WEIGHTED, "lower", _ALL_SCENARIOS,
        "Urgency-Adaptive yields lower ATBP than Weighted",
    ),
    Comparison(
        "H2", CM_CRITICAL, AlgorithmName.URGENCY_ADAPTIVE, AlgorithmName.WEIGHTED, "higher",
        _ALL_SCENARIOS, "Urgency-Adaptive yields higher critical capability-match than Weighted",
    ),
    Comparison(
        "H3", FRR, AlgorithmName.WEIGHTED, AlgorithmName.GREEDY, "lower", (1.00,),
        "Weighted yields lower FRR than Greedy at 100% occupancy",
    ),
    Comparison(
        "H3", FRR, AlgorithmName.URGENCY_ADAPTIVE, AlgorithmName.GREEDY, "lower", (1.00,),
        "Urgency-Adaptive yields lower FRR than Greedy at 100% occupancy",
    ),
)


def _paired_series(
    frame: pd.DataFrame, occupancy: float, metric: str, config_a: str, config_b: str
) -> tuple[np.ndarray, np.ndarray]:
    """Return the run-index-aligned (a, b) metric vectors for one scenario, NaNs dropped."""
    scenario = frame[np.isclose(frame["occupancy"], occupancy)]
    a = scenario[scenario["algorithm"] == config_a].set_index("run_index")[metric]
    b = scenario[scenario["algorithm"] == config_b].set_index("run_index")[metric]
    paired = pd.DataFrame({"a": a, "b": b}).dropna()  # inner-align on run index, drop undefined
    return paired["a"].to_numpy(dtype=float), paired["b"].to_numpy(dtype=float)


def _cohens_d_paired(differences: np.ndarray) -> float:
    """Paired Cohen's d = mean(diff) / sample-std(diff); 0.0 when there is no spread."""
    spread = float(np.std(differences, ddof=1)) if len(differences) > 1 else 0.0
    return float(np.mean(differences)) / spread if spread > 0 else 0.0


def _direction(mean_diff: float) -> str:
    """Observed direction of A relative to B from the signed mean difference."""
    if mean_diff < 0:
        return "lower"
    if mean_diff > 0:
        return "higher"
    return "equal"


def _evaluate(
    comparison: Comparison, occupancy: float, alpha: float, a: np.ndarray, b: np.ndarray
) -> dict[str, object]:
    """Run the normality → test → effect-size procedure for one (comparison, scenario)."""
    base: dict[str, object] = {
        "hypothesis": comparison.hypothesis,
        "metric": comparison.metric,
        "comparison": f"{comparison.config_a} vs {comparison.config_b}",
        "occupancy": occupancy,
        "n": len(a),
        "direction_expected": comparison.direction,
        "description": comparison.description,
    }
    differences = a - b
    mean_diff = float(np.mean(differences)) if len(differences) else float("nan")

    # Not enough data, or no variation at all (e.g. every FRR = 1.0): no test is defined.
    if len(a) < _MIN_SAMPLES:
        return {**base, **_undefined("insufficient_data", mean_diff, comparison)}
    if float(np.ptp(differences)) == 0.0:
        return {**base, **_no_variation(mean_diff, comparison)}

    normal = bool(stats.shapiro(differences).pvalue > alpha)
    if normal:
        result = stats.ttest_rel(a, b)
        test, statistic, df = "paired_t", float(result.statistic), len(a) - 1
    else:
        result = stats.wilcoxon(a, b)
        test, statistic, df = "wilcoxon", float(result.statistic), None
    p_value = float(result.pvalue)
    observed = _direction(mean_diff)
    significant = p_value < alpha
    return {
        **base,
        "test": test,
        "statistic": statistic,
        "df": df,
        "p_value": p_value,
        "cohens_d": _cohens_d_paired(differences),
        "mean_diff": mean_diff,
        "direction_observed": observed,
        "significant": significant,
        "supported": bool(significant and observed == comparison.direction),
        "note": "",
    }


def _undefined(note: str, mean_diff: float, comparison: Comparison) -> dict[str, object]:
    """Row body for a comparison that could not be tested (too few / undefined samples)."""
    return {
        "test": "none",
        "statistic": float("nan"),
        "df": None,
        "p_value": float("nan"),
        "cohens_d": float("nan"),
        "mean_diff": mean_diff,
        "direction_observed": _direction(mean_diff) if mean_diff == mean_diff else "undefined",
        "significant": False,
        "supported": False,
        "note": note,
    }


def _no_variation(mean_diff: float, comparison: Comparison) -> dict[str, object]:
    """Row body when the paired differences are all identical (no testable variation)."""
    return {**_undefined("no_variation", mean_diff, comparison), "p_value": 1.0}


def analyze(
    frame: pd.DataFrame,
    comparisons: Sequence[Comparison] = DEFAULT_COMPARISONS,
    alpha: float = SIGNIFICANCE_ALPHA,
) -> pd.DataFrame:
    """Run every (comparison × scenario) and return the hypothesis-test table (docs/08 §3)."""
    rows: list[dict[str, object]] = []
    for comparison in comparisons:
        for occupancy in comparison.scenarios:
            a, b = _paired_series(
                frame, occupancy, comparison.metric, comparison.config_a, comparison.config_b
            )
            rows.append(_evaluate(comparison, occupancy, alpha, a, b))
    return pd.DataFrame(rows)


def main() -> None:
    """CLI entry point: read the per-run metrics and write the hypothesis-test table (RB-7)."""
    parser = argparse.ArgumentParser(description="Run the EBADS H1/H2/H3 hypothesis tests.")
    parser.add_argument("--input", required=True, type=Path, help="Per-run metrics Parquet.")
    parser.add_argument("--out", required=True, type=Path, help="Output CSV path.")
    args = parser.parse_args()

    frame = pd.read_parquet(args.input)
    results = analyze(frame)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out, index=False)
    supported = int(results["supported"].sum())
    print(f"Wrote {len(results)} comparison rows ({supported} supported) -> {args.out}")


if __name__ == "__main__":
    main()
