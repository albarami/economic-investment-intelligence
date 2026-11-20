"""Offline blocked-model report; never fetches, imports or executes a model."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .adapters import CPU, ModelPin, readiness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weights-root", type=Path, default=Path("evals/forecast_spike/weights")
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    weights = args.weights_root.resolve()
    if not weights.is_relative_to(root) or any(
        p in ("data", ".private") for p in weights.relative_to(root).parts
    ):
        parser.error(
            "weights_root_must_be_inside_experiment_or_fixture_temporary_folder"
        )
    models = {}
    for candidate, repository, package in (
        ("chronos_2", "amazon/chronos-2", "chronos-forecasting"),
        ("timesfm_2_5", "google/timesfm-2.5-200m-pytorch", "timesfm"),
    ):
        # Deliberately unresolved: no offline source supplied a model revision,
        # package version, file hash or documented median/training boundary.
        pin = ModelPin(
            candidate,
            repository,
            "",
            package,
            "",
            (),
            "",
            False,
            None,
            "unconfirmed",
            "official pages not read",
            False,
        )
        models[candidate] = asdict(
            readiness(pin, weights / candidate, root / "uv.lock")
        )
    print(
        json.dumps(
            {"models": models, "cpu": asdict(CPU()), "production_promotion": False},
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
