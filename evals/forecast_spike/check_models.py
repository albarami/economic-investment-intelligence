"""Offline blocked-model report; never fetches, imports or executes a model."""

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from .adapters import CPU, ModelPin, readiness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weights-root", type=Path, default=Path("evals/forecast_spike/weights")
    )
    parser.add_argument(
        "--fixture-temp-root",
        type=Path,
        help="explicit existing fixture directory strictly below the system temporary root; excludes data and .private",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    message = (
        "weights root must be in the repository, excluding data and .private, "
        "or strictly below --fixture-temp-root, an existing directory strictly "
        "below the system temporary root; data and .private are excluded in both cases"
    )
    # Refuse lexical forbidden components before resolving or inspecting them.
    paths: tuple[Path, ...] = (args.weights_root,)
    if args.fixture_temp_root is not None:
        paths += (args.fixture_temp_root,)
    if any(p in ("data", ".private") for path in paths for p in path.parts):
        parser.error(message)
    weights = args.weights_root.resolve()
    if any(p in ("data", ".private") for p in weights.parts):
        parser.error(message)
    fixture = None
    if args.fixture_temp_root is not None:
        fixture = args.fixture_temp_root.resolve()
        temporary = Path(tempfile.gettempdir()).resolve()
        if (
            fixture == temporary
            or not fixture.is_relative_to(temporary)
            or any(p in ("data", ".private") for p in fixture.parts)
            or not fixture.is_dir()
            or weights == fixture
            or not weights.is_relative_to(fixture)
        ):
            parser.error(message)
    if not weights.is_relative_to(root) and fixture is None:
        parser.error(message)
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
