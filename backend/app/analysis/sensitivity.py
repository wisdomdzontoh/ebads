"""Sensitivity analysis (docs/08-evaluation.md §4, docs/09 §10, RB-8).

Re-runs the **main grid** under parameter variants (weight/radius/capability configurations)
and tabulates which hypotheses survive which variants. A hypothesis that holds under the
default *and every* variant is reported as **robust**; one that holds only under the default is
**conditional** (docs/08 §4).

The exact variant vectors are researcher-defined and live in ``config/sensitivity.yaml`` (not
in code), so the sensitivity study is auditable and reproducible (docs/09 §10). Each variant's
overrides are merged onto the ``parameters.py`` defaults via
:func:`app.domain.allocation.study_parameters.from_overrides`, which validates them.

CLI (RB-8)::

    python -m app.analysis.sensitivity --study-id 2026-06-17 \
      --variants config/sensitivity.yaml --out artifacts/eval/2026-06-17/sensitivity_results.csv
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.statistics import analyze
from app.db.session import get_engine
from app.domain.allocation.study_parameters import StudyParameters, from_overrides
from app.simulation.runner import (
    RUN_MANIFEST_NAME,
    GridConfig,
    grid_config_from_manifest,
    run_grid,
)

_BASELINE_FAMILY = "baseline"


@dataclass(frozen=True)
class Variant:
    """One sensitivity configuration: a name, a family, and the overrides it applies."""

    name: str
    family: str
    weight_config: dict[str, Any] | None
    radius_config: dict[str, Any] | None
    capability_config: dict[str, Any] | None

    def parameters(self) -> StudyParameters:
        """Build the validated :class:`StudyParameters` for this variant."""
        return from_overrides(self.radius_config, self.capability_config, self.weight_config)


def load_variants(path: Path) -> list[Variant]:
    """Parse the sensitivity-variant YAML (docs/09 §10) into :class:`Variant` objects."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    variants: list[Variant] = []
    for entry in document["variants"]:
        variants.append(
            Variant(
                name=entry["name"],
                family=entry.get("family", "unspecified"),
                weight_config=entry.get("weights"),
                radius_config=entry.get("radius"),
                capability_config=entry.get("capability"),
            )
        )
    return variants


def _hypothesis_holds(rows: pd.DataFrame) -> bool:
    """A hypothesis holds in a variant iff it has ≥1 testable row and all are supported."""
    testable = rows[rows["test"] != "none"]
    if len(testable) == 0:
        return False  # nothing testable (e.g. every metric undefined) — cannot confirm it holds
    return bool(testable["supported"].all())


def _classify(holds_by_variant: dict[str, bool], default_name: str) -> str:
    """Robust (holds everywhere), conditional (default only), or unsupported (not in default)."""
    if not holds_by_variant.get(default_name, False):
        return "unsupported"
    return "robust" if all(holds_by_variant.values()) else "conditional"


def summarise(details: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    """Pivot the per-variant results into a hypothesis-survival table (docs/08 §4)."""
    default = next((v for v in variants if v.family == _BASELINE_FAMILY), variants[0])
    ordered_names = [variant.name for variant in variants]
    rows: list[dict[str, object]] = []
    for hypothesis in sorted(details["hypothesis"].unique()):
        holds_by_variant = {
            name: _hypothesis_holds(
                details[(details["hypothesis"] == hypothesis) & (details["variant"] == name)]
            )
            for name in ordered_names
        }
        rows.append(
            {
                "hypothesis": hypothesis,
                **holds_by_variant,
                "classification": _classify(holds_by_variant, default.name),
            }
        )
    return pd.DataFrame(rows)


async def run_sensitivity(
    variants: Sequence[Variant],
    grid_config: GridConfig,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run each variant's grid, test the hypotheses, and return (summary, details) frames."""
    detail_frames: list[pd.DataFrame] = []
    for variant in variants:
        per_run, _ = await run_grid(
            grid_config, sessionmaker=sessionmaker, study_parameters=variant.parameters()
        )
        tests = analyze(per_run)
        tests.insert(0, "variant", variant.name)
        tests.insert(1, "family", variant.family)
        detail_frames.append(tests)
    details = pd.concat(detail_frames, ignore_index=True)
    return summarise(details, variants), details


async def _main(study_id: str, sim_dir: Path, variants_path: Path, out_path: Path) -> None:
    """RB-8 body: locate the study's grid manifest, run all variants, write the survival table."""
    manifest_path = sim_dir / study_id / RUN_MANIFEST_NAME
    grid_config = grid_config_from_manifest(manifest_path, out_dir=sim_dir)
    variants = load_variants(variants_path)
    summary, details = await run_sensitivity(variants, grid_config)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False)
    details.to_csv(out_path.with_name("sensitivity_details.csv"), index=False)
    await get_engine().dispose()
    print(f"Wrote sensitivity survival table ({len(summary)} hypotheses) -> {out_path}")


def main() -> None:
    """CLI entry point for the sensitivity analysis (RB-8)."""
    parser = argparse.ArgumentParser(description="Run the EBADS sensitivity analysis.")
    parser.add_argument("--study-id", required=True, help="Study whose grid manifest to reuse.")
    parser.add_argument(
        "--sim-dir", type=Path, default=Path("artifacts/sim"), help="Where the grid manifest lives."
    )
    parser.add_argument("--variants", required=True, type=Path, help="Sensitivity variants YAML.")
    parser.add_argument("--out", required=True, type=Path, help="Output survival-table CSV.")
    args = parser.parse_args()
    asyncio.run(_main(args.study_id, args.sim_dir, args.variants, args.out))


if __name__ == "__main__":
    main()
