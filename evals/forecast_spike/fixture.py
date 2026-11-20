"""Invented fixture command only; lead must authorise it before direct use."""

import argparse
import json
import multiprocessing
import os
import resource
import socket
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from .backtest import Run, run
from .contract import AUTOS, Family, Registration, SeriesSpec


def _network_forbidden(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("fixture_network_forbidden")


def fixture_job(spec: SeriesSpec) -> Run:
    """Only arithmetic fixtures run here; this is not an inference sandbox."""
    registration = Registration((spec,))
    values = tuple(Decimal(10 + 2 * i + i % 3) for i in range(len(spec.periods)))
    with (
        patch.object(socket, "socket", side_effect=_network_forbidden),
        patch.object(socket, "getaddrinfo", side_effect=_network_forbidden),
    ):
        return run(
            registration,
            {spec.key: values},
            {key: lambda prefix, _season: prefix[-1] for key in AUTOS},
            expected_registration_sha256=registration.sha256,
        )


def fixture_specs(document: dict[str, object]) -> tuple[SeriesSpec, ...]:
    # The file is an application-owned fixture declaration, never user input.
    # Exact equality prevents a changed threshold being silently ignored.
    fixed: dict[str, object] = {
        "version": "s6-t27-prefix-mase-v1",
        "fixture_only": True,
        "seed": 27,
        "horizon": 1,
        "minimum": 12,
        "levels": {"year": [4, 5], "quarter": [4, 5], "month": [9, 10]},
        "adapter_kind": "invented_prefix_stubs",
        "generator_version": "invented-trend-cycle-v1",
        "scope": "invented_generated_fixtures_only_no_public_or_release_acceptance",
        "training_strata": ["generated", "post_cutoff", "overlapping_or_unknown"],
        "zero_scale": "separate_mae_no_family_mase_pass",
        "aggregation": "equal_series_weight_paired_targets",
        "selection": "matured_inner_errors_fixed_order_ties",
    }
    if (
        set(document) != set(fixed) | {"candidates", "series"}
        or any(document.get(key) != value for key, value in fixed.items())
        or document.get("fixture_only") is not True
        or any(
            type(document.get(key)) is not int for key in ("seed", "horizon", "minimum")
        )
    ):
        raise ValueError("fixture_contract")
    rows = document["series"]
    if not isinstance(rows, list):
        raise ValueError("fixture_series")
    specs = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"key", "frequency", "length", "first_target"}
            or type(row["key"]) is not str
            or not row["key"].startswith("syn-")
            or type(row["frequency"]) is not str
            or type(row["length"]) is not int
            or type(row["first_target"]) is not int
        ):
            raise ValueError("fixture_series")
        family = Family(
            "invented-trend-cycle-v1",
            row["frequency"],
            "count",
            "count",
            "none",
            "none",
            "none",
            "generated",
        )
        specs.append(
            SeriesSpec(
                row["key"],
                family,
                tuple(range(row["length"])),
                tuple(range(row["first_target"], row["length"])),
                "syn-geography",
                "syn-category",
                "invented-fixture-v1",
            )
        )
    registration = Registration(tuple(specs))
    if document.get("candidates") != list(registration.candidates):
        raise ValueError("fixture_candidates")
    registration.validate()
    return tuple(specs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    raw = Path(__file__).with_name("preregistration.json").read_bytes()
    specs = fixture_specs(json.loads(raw))
    started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        results = tuple(pool.map(fixture_job, specs))
    registration = Registration(specs)
    joint = run(
        registration,
        {
            spec.key: tuple(
                Decimal(10 + 2 * i + i % 3) for i in range(len(spec.periods))
            )
            for spec in specs
        },
        {key: lambda prefix, _season: prefix[-1] for key in AUTOS},
        expected_registration_sha256=registration.sha256,
    )
    print(
        json.dumps(
            {
                "fixture_only": True,
                "model_inference": "blocked",
                "preregistration_file_sha256": sha256(raw).hexdigest(),
                "registration_sha256": registration.sha256,
                "runs": [asdict(result) for result in results],
                "family_summaries": [asdict(summary) for summary in joint.summaries],
            },
            default=str,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    print(
        json.dumps(
            {
                "process": os.getpid(),
                "device": "cpu",
                "threads": 1,
                "workers": args.workers,
                "seed": 27,
                "batch_seconds": time.perf_counter() - started,
                "peak_memory_kib": resource.getrusage(
                    resource.RUSAGE_CHILDREN
                ).ru_maxrss,
                "memory_scope": "largest_worker_peak_not_aggregate",
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
