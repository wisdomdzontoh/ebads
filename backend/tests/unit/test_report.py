"""Evaluation report assembly (docs/08 §6, RB-9).

Drives ``generate_report`` over a synthetic per-run dataset and asserts the deliverables are
produced: the per-scenario figures, the hypothesis-test table, and the ``study_manifest.json``
reproducibility record (grid block, parameter snapshot, distance-matrix hash, timestamp).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.analysis.report import generate_report, parameter_snapshot

_MATRIX_HASH = "abc123def456"


def _synthetic_per_run() -> pd.DataFrame:
    """A small but complete per-run dataset over 3 algorithms x 2 occupancies x 5 runs."""
    rng = np.random.default_rng(0)
    rows: list[dict[str, object]] = []
    for algorithm in ("greedy", "weighted", "urgency_adaptive"):
        for occupancy in (0.75, 0.90):
            for run_index in range(5):
                rows.append(
                    {
                        "algorithm": algorithm,
                        "occupancy": occupancy,
                        "run_index": run_index,
                        "seed": 1000 + run_index,
                        "distance_matrix_sha256": _MATRIX_HASH,
                        "atbp": float(rng.normal(30, 2)),
                        "frr": float(rng.uniform(0, 0.2)),
                        "mcee": float(rng.uniform(5, 15)),
                        "cm": float(rng.uniform(0.5, 1.0)),
                        "cm_critical": float(rng.uniform(0.4, 1.0)),
                    }
                )
    return pd.DataFrame(rows)


def _write_study(tmp_path: Path, study_id: str) -> Path:
    """Write the synthetic grid outputs + a run manifest under a sim dir; return the sim dir."""
    sim_dir = tmp_path / "sim"
    study_dir = sim_dir / study_id
    study_dir.mkdir(parents=True)
    _synthetic_per_run().to_parquet(study_dir / "per_run_metrics.parquet", index=False)
    manifest = {
        "study_id": study_id,
        "grid": {
            "base_seed": 20260617,
            "algorithms": ["greedy", "weighted", "urgency_adaptive"],
            "occupancies": [0.75, 0.90],
            "runs": 5,
            "events": 100,
            "distance_matrix": "artifacts/distance_matrix.parquet",
            "distance_matrix_sha256": _MATRIX_HASH,
        },
        "generated_at": "2026-07-02T00:00:00+00:00",
    }
    (study_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return sim_dir


def test_generate_report_writes_all_deliverables(tmp_path: Path) -> None:
    """RB-9: figures, hypothesis_tests.csv, and study_manifest.json are all produced."""
    study_id = "study-2026"
    sim_dir = _write_study(tmp_path, study_id)
    eval_dir = generate_report(study_id, sim_dir, tmp_path / "eval")

    assert (eval_dir / "hypothesis_tests.csv").exists()
    figures = list((eval_dir / "figures").glob("*.png"))
    assert {figure.name for figure in figures} == {
        "atbp.png",
        "frr.png",
        "mcee.png",
        "cm.png",
        "cm_critical.png",
    }

    manifest = json.loads((eval_dir / "study_manifest.json").read_text(encoding="utf-8"))
    assert manifest["study_id"] == study_id
    assert manifest["distance_matrix_sha256"] == _MATRIX_HASH
    assert manifest["grid"]["base_seed"] == 20260617
    assert set(manifest["figures"]) == {figure.name for figure in figures}
    assert "generated_at" in manifest
    # The parameter snapshot is embedded and complete enough to reproduce the study.
    assert manifest["parameters"]["random_seed"] == parameter_snapshot()["random_seed"]
    assert "capability_matrix" in manifest["parameters"]


def test_manifest_parameter_snapshot_is_json_serialisable() -> None:
    """The parameter snapshot round-trips through JSON (no enum/Decimal leaks)."""
    snapshot = parameter_snapshot()
    restored = json.loads(json.dumps(snapshot))
    assert restored["radius_minutes"]["critical"] == 30
    assert restored["algorithm_2_weights"]["w_t"] == 0.40
