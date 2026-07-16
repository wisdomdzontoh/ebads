"""Evaluation report: figures + hypothesis table + reproducibility manifest (docs/08 §6, RB-9).

Assembles the ``artifacts/eval/<study_id>/`` deliverables from a completed grid: per-scenario
metric figures for thesis Chapter 4, the ``hypothesis_tests.csv`` table, and
``study_manifest.json`` — the full reproducibility record (grid config, parameter snapshot,
distance-matrix hash, code commit, timestamps, docs/08 §6-7). Every reported number is
traceable back to this manifest plus the recorded seeds.

CLI (RB-9)::

    python -m app.analysis.report --study-id 2026-06-17
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

from app.analysis.statistics import analyze
from app.parameters import (
    ALGORITHM_2_WEIGHTS,
    ALGORITHM_3_WEIGHTS,
    BED_TYPE_DISTRIBUTION,
    CAPABILITY_MATRIX,
    COORDINATION_OVERHEAD_MIN,
    DISTANCE_MATRIX_GRID_SIZE,
    EVENTS_PER_RUN,
    GA_BBOX,
    LOS_DISTRIBUTION,
    LOS_MEAN_MINUTES,
    OCCUPANCY_SCENARIOS,
    RADIUS_MINUTES,
    RANDOM_SEED,
    RUNS_PER_CONFIGURATION,
    SIGNIFICANCE_ALPHA,
    URGENCY_DISTRIBUTION,
)
from app.simulation.runner import RUN_MANIFEST_NAME

matplotlib.use("Agg", force=True)  # headless: render to files, never a display
import matplotlib.pyplot as plt  # noqa: E402  (backend must be selected before pyplot use)

# The metrics plotted per scenario (docs/08 §6). ATBP/CM may be undefined (NaN) at 100%.
_PLOTTED_METRICS = ("atbp", "frr", "mcee", "cm", "cm_critical")


def parameter_snapshot() -> dict[str, object]:
    """A JSON-serialisable snapshot of every study constant (docs/08 §6 reproducibility)."""
    return {
        "radius_minutes": {u.value: v for u, v in RADIUS_MINUTES.items()},
        "capability_matrix": {
            u.value: {t.value: v for t, v in row.items()} for u, row in CAPABILITY_MATRIX.items()
        },
        "algorithm_2_weights": ALGORITHM_2_WEIGHTS.model_dump(),
        "algorithm_3_weights": {u.value: w.model_dump() for u, w in ALGORITHM_3_WEIGHTS.items()},
        "urgency_distribution": {u.value: v for u, v in URGENCY_DISTRIBUTION.items()},
        "bed_type_distribution": {b.value: v for b, v in BED_TYPE_DISTRIBUTION.items()},
        "occupancy_scenarios": list(OCCUPANCY_SCENARIOS),
        "runs_per_configuration": RUNS_PER_CONFIGURATION,
        "events_per_run": EVENTS_PER_RUN,
        "coordination_overhead_min": COORDINATION_OVERHEAD_MIN,
        "los_distribution": LOS_DISTRIBUTION,
        "los_mean_minutes": {b.value: v for b, v in LOS_MEAN_MINUTES.items()},
        "ga_bbox": list(GA_BBOX),
        "distance_matrix_grid_size": list(DISTANCE_MATRIX_GRID_SIZE),
        "random_seed": RANDOM_SEED,
        "significance_alpha": SIGNIFICANCE_ALPHA,
    }


def _code_commit() -> str | None:
    """Return the current git commit hash, or ``None`` if not in a git checkout (best-effort)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _mean_std(agg: pd.DataFrame, occupancy: float, algorithm: str) -> tuple[float, float]:
    """Look up (mean, std) for one (occupancy, algorithm) cell, NaN if absent/undefined."""
    cell = agg[(agg["occupancy"] == occupancy) & (agg["algorithm"] == algorithm)]
    if len(cell) == 0:
        return float("nan"), float("nan")
    return float(cell["mean"].iloc[0]), float(cell["std"].iloc[0])


def _plot_metric(per_run: pd.DataFrame, metric: str, path: Path) -> None:
    """Grouped bar chart of one metric (mean ± std) across algorithms, per occupancy scenario."""
    agg = per_run.groupby(["occupancy", "algorithm"])[metric].agg(["mean", "std"]).reset_index()
    occupancies = sorted(per_run["occupancy"].unique())
    algorithms = sorted(per_run["algorithm"].unique())
    positions = np.arange(len(occupancies))
    width = 0.8 / max(len(algorithms), 1)

    figure, axis = plt.subplots(figsize=(7, 4))
    for index, algorithm in enumerate(algorithms):
        stats = [_mean_std(agg, occupancy, algorithm) for occupancy in occupancies]
        means = [mean for mean, _ in stats]
        errors = [0.0 if std != std else std for _, std in stats]  # NaN std -> no error bar
        axis.bar(positions + index * width, means, width, yerr=errors, capsize=3, label=algorithm)

    axis.set_xticks(positions + width * (len(algorithms) - 1) / 2)
    axis.set_xticklabels([f"{occupancy:.0%}" for occupancy in occupancies])
    axis.set_xlabel("Occupancy scenario")
    axis.set_ylabel(metric.upper())
    axis.set_title(f"{metric.upper()} by algorithm and occupancy")
    axis.legend(title="algorithm")
    figure.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(figure)


def _plot_all(per_run: pd.DataFrame, figures_dir: Path) -> list[str]:
    """Render every per-scenario metric figure and return their filenames (docs/08 §6)."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    filenames: list[str] = []
    for metric in _PLOTTED_METRICS:
        if metric in per_run.columns:
            filename = f"{metric}.png"
            _plot_metric(per_run, metric, figures_dir / filename)
            filenames.append(filename)
    return filenames


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON file if it exists, else ``None`` (the run manifest is optional here)."""
    if not path.exists():
        return None
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def build_study_manifest(
    study_id: str,
    per_run: pd.DataFrame,
    run_manifest: dict[str, Any] | None,
    figures: list[str],
    tables: list[str],
) -> dict[str, object]:
    """Assemble the full reproducibility manifest (docs/08 §6)."""
    if run_manifest is not None:
        grid: dict[str, Any] = run_manifest["grid"]
        matrix_hash = str(grid["distance_matrix_sha256"])
    else:
        grid = _grid_from_per_run(per_run)
        matrix_hash = str(per_run["distance_matrix_sha256"].iloc[0])
    return {
        "study_id": study_id,
        "grid": grid,
        "distance_matrix_sha256": matrix_hash,
        "parameters": parameter_snapshot(),
        "code_commit": _code_commit(),
        "figures": figures,
        "tables": tables,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _grid_from_per_run(per_run: pd.DataFrame) -> dict[str, Any]:
    """Best-effort grid block when no run manifest is present (derived from the dataset)."""
    return {
        "algorithms": sorted(per_run["algorithm"].unique()),
        "occupancies": sorted(per_run["occupancy"].unique()),
        "runs": int(per_run["run_index"].max()) + 1,
    }


def generate_report(study_id: str, sim_dir: Path, out_dir: Path) -> Path:
    """Produce figures, the hypothesis table, and the manifest for a study; return the eval dir."""
    per_run = pd.read_parquet(sim_dir / study_id / "per_run_metrics.parquet")
    eval_dir = out_dir / study_id
    eval_dir.mkdir(parents=True, exist_ok=True)

    analyze(per_run).to_csv(eval_dir / "hypothesis_tests.csv", index=False)
    figures = _plot_all(per_run, eval_dir / "figures")
    tables = [
        name
        for name in ("hypothesis_tests.csv", "sensitivity_results.csv")
        if (eval_dir / name).exists()
    ]
    run_manifest = _read_json(sim_dir / study_id / RUN_MANIFEST_NAME)
    manifest = build_study_manifest(study_id, per_run, run_manifest, figures, tables)
    (eval_dir / "study_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return eval_dir


def main() -> None:
    """CLI entry point for the evaluation report (RB-9)."""
    parser = argparse.ArgumentParser(description="Generate the EBADS evaluation report.")
    parser.add_argument("--study-id", required=True, help="Study to report on.")
    parser.add_argument(
        "--sim-dir", type=Path, default=Path("artifacts/sim"), help="Grid outputs location."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("artifacts/eval"), help="Evaluation output root."
    )
    args = parser.parse_args()
    eval_dir = generate_report(args.study_id, args.sim_dir, args.out_dir)
    print(f"Wrote evaluation report -> {eval_dir}")


if __name__ == "__main__":
    main()
