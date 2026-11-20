"""Absent weights are blocked; fixture admission never certifies a model."""

import json
import socket
import sys
import tempfile
from dataclasses import replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.forecast_spike.adapters import (
    CPU,
    Admission,
    Asset,
    ModelPin,
    ProcessOutput,
    determinism,
    eligibility,
    readiness,
    stratum,
)
from evals.forecast_spike.check_models import main as check_models


def pin(candidate: str = "chronos_2") -> ModelPin:
    is_chronos = candidate == "chronos_2"
    return ModelPin(
        candidate,
        "amazon/chronos-2" if is_chronos else "google/timesfm-2.5-200m-pytorch",
        "a" * 40,
        "chronos-forecasting" if is_chronos else "timesfm",
        "0.0.0",
        (Asset("syn-weights.bin", sha256(b"invented-weights").hexdigest()),),
        "https://example.invalid/invented-median-contract",
        True,
        date(2020, 1, 1),
        "https://example.invalid/invented-boundary",
        "invented fixture only",
        True,
    )


def files(tmp_path: Path, model: ModelPin) -> tuple[Path, Path]:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "syn-weights.bin").write_bytes(b"invented-weights")
    lock = tmp_path / "uv.lock"
    lock.write_text(
        f'[[package]]\nname = "{model.package}"\nversion = "0.0.0"\n[[package]]\nname = "torch"\nversion = "0.0.0+cpu"\n'
    )
    return assets, lock


@pytest.mark.parametrize("candidate", ["chronos_2", "timesfm_2_5"])
def test_missing_weights_and_dependencies_are_blocked(
    tmp_path: Path, candidate: str
) -> None:
    model = pin(candidate)
    lock = tmp_path / "uv.lock"
    lock.write_text("package = []\n")
    with patch.object(
        socket, "socket", side_effect=AssertionError("network forbidden")
    ):
        result = readiness(model, tmp_path / "absent", lock)
    assert result.status == "blocked"
    assert "weights_missing" in result.reasons
    assert "dependency_not_locked" in result.reasons
    assert "inference_api_unconfirmed" in result.reasons


@pytest.mark.parametrize(
    "change,reason",
    [
        ("hash", "weights_hash_mismatch"),
        ("revision", "revision_unpinned"),
        ("median", "median_undocumented"),
        ("documentation", "documentation_unconfirmed"),
        ("device", "cpu_only"),
        ("workers", "cpu_configuration"),
        ("threads", "cpu_configuration"),
        ("package", "dependency_not_locked"),
        ("path", "asset_path"),
        ("duplicate", "asset_path"),
        ("repository", "model_identity"),
        ("boundary", "training_boundary_record"),
        ("empty_files", "weights_missing"),
    ],
)
def test_admission_plants_refuse(tmp_path: Path, change: str, reason: str) -> None:
    model = pin()
    root, lock = files(tmp_path, model)
    cpu = CPU()
    if change == "hash":
        (root / "syn-weights.bin").write_bytes(b"tamper")
    elif change == "revision":
        model = replace(model, revision="main")
    elif change == "median":
        model = replace(model, median_documented=False)
    elif change == "documentation":
        model = replace(model, documentation="")
    elif change == "device":
        cpu = replace(cpu, device="cuda")
    elif change == "workers":
        cpu = replace(cpu, workers=0)
    elif change == "threads":
        cpu = replace(cpu, threads=0)
    elif change == "package":
        model = replace(model, package_version="0.0.1")
    elif change == "path":
        model = replace(model, files=(Asset("../outside.bin", "a" * 64),))
    elif change == "duplicate":
        model = replace(model, files=model.files * 2)
    elif change == "repository":
        model = replace(model, repository="unknown/model")
    elif change == "boundary":
        model = replace(model, boundary_source="", boundary_uncertainty="")
    elif change == "empty_files":
        model = replace(model, files=())
    result = readiness(model, root, lock, cpu)
    assert result.status == "blocked"
    assert reason in result.reasons


def test_asset_symlink_refuses_before_read(tmp_path: Path) -> None:
    model = pin()
    root, lock = files(tmp_path, model)
    (root / "syn-weights.bin").unlink()
    (root / "syn-weights.bin").symlink_to("../unread")
    result = readiness(model, root, lock)
    assert "asset_path" in result.reasons


def test_verified_fixture_is_still_not_implemented_model_inference(
    tmp_path: Path,
) -> None:
    model = pin()
    root, lock = files(tmp_path, model)
    assert readiness(model, root, lock) == Admission(
        "blocked", ("inference_api_unconfirmed",)
    )


def test_f4_training_strata_and_unknown_boundary() -> None:
    model = pin()
    assert stratum(model, date(2021, 1, 1), "public") == "post_cutoff"
    assert stratum(model, date(2020, 1, 1), "public") == "overlapping_or_unknown"
    assert stratum(model, date(2019, 1, 1), "generated") == "generated"
    unknown = replace(model, training_boundary=None, boundary_reliable=False)
    assert stratum(unknown, date(2021, 1, 1), "public") == "overlapping_or_unknown"
    assert (
        stratum(replace(model, boundary_reliable=False), date(2021, 1, 1), "public")
        == "overlapping_or_unknown"
    )


def test_unknown_overlap_cannot_establish_public_comparison() -> None:
    model = replace(pin(), training_boundary=None, boundary_reliable=False)
    targets = tuple(date(2021 + i, 1, 1) for i in range(12))
    assert eligibility(model, targets, "public").status == "blocked"
    assert eligibility(pin(), targets[:11], "public").status == "insufficient"
    assert eligibility(pin(), targets, "public").status == "eligible"
    assert eligibility(model, targets, "generated").status == "eligible_generated_only"
    assert eligibility(model, (), "generated").status == "insufficient"


@pytest.mark.parametrize(
    "plant", ["empty", "same_process", "missing_workers", "changed_output"]
)
def test_fresh_process_determinism_plants_cannot_pass(plant: str) -> None:
    samples: tuple[ProcessOutput, ...] = (
        ProcessOutput(1, 1, b"same"),
        ProcessOutput(2, 1, b"same"),
        ProcessOutput(3, 2, b"same"),
        ProcessOutput(4, 2, b"same"),
    )
    if plant == "empty":
        samples = ()
    elif plant == "same_process":
        samples = (samples[0], samples[0], samples[2], samples[3])
    elif plant == "missing_workers":
        samples = samples[:2]
    else:
        samples = (*samples[:3], replace(samples[3], output=b"changed"))
    assert determinism(samples, (1, 2)).status != "pass"


def test_complete_byte_identical_process_evidence() -> None:
    samples = tuple(ProcessOutput(i + 1, 1 if i < 2 else 2, b"same") for i in range(4))
    assert determinism(samples, (1, 2)).status == "pass"


@pytest.mark.parametrize("candidate", ["chronos_2", "timesfm_2_5"])
def test_actual_lock_has_no_challenger_dependencies(
    tmp_path: Path, candidate: str
) -> None:
    model = pin(candidate)
    lock = Path(__file__).resolve().parents[2] / "uv.lock"
    result = readiness(model, tmp_path / "unavailable-weights", lock)
    assert result.status == "blocked"
    assert "dependency_not_locked" in result.reasons
    assert "weights_missing" in result.reasons


def test_offline_model_command_returns_nonzero_blocked_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with patch.object(
        socket, "socket", side_effect=AssertionError("network forbidden")
    ):
        code = check_models(
            [
                "--weights-root",
                str(tmp_path / "absent"),
                "--fixture-temp-root",
                str(tmp_path),
            ]
        )
    assert code == 2
    result = json.loads(capsys.readouterr().out)
    assert list(result["models"]) == ["chronos_2", "timesfm_2_5"]
    assert all(row["status"] == "blocked" for row in result["models"].values())
    assert result["production_promotion"] is False


@pytest.mark.parametrize(
    "kind",
    [
        "outside",
        "data",
        "private",
        "fixture_data",
        "fixture_private",
        "wrong_fixture",
        "broad_fixture",
    ],
)
def test_weights_root_guard_plants(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = Path(__file__).resolve().parents[2]
    weights = {
        "outside": root.parent / "syn-unapproved-weights",
        "data": root / "data/syn-unread",
        "private": root / ".private/syn-unread",
    }.get(kind, tmp_path / "absent")
    args = ["--weights-root", str(weights)]
    if kind == "fixture_data":
        args = [
            "--weights-root",
            str(tmp_path / "data/syn-unread"),
            "--fixture-temp-root",
            str(tmp_path),
        ]
    elif kind == "fixture_private":
        args = [
            "--weights-root",
            str(tmp_path / ".private/syn-unread"),
            "--fixture-temp-root",
            str(tmp_path),
        ]
    elif kind == "wrong_fixture":
        args += ["--fixture-temp-root", str(tmp_path / "absent-root")]
    elif kind == "broad_fixture":
        args += ["--fixture-temp-root", tempfile.gettempdir()]
    with patch(
        "evals.forecast_spike.check_models.readiness",
        side_effect=AssertionError("must refuse before reading"),
    ):
        with pytest.raises(SystemExit) as exc:
            check_models(args)
    assert exc.value.code == 2
    assert (
        "weights root must be in the repository, excluding data and .private, "
        "or strictly below --fixture-temp-root, an existing directory strictly "
        "below the system temporary root; data and .private are excluded in both cases"
        in capsys.readouterr().err
    )


def test_weights_default_experiment_path_is_accepted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check_models([]) == 2
    assert all(
        row["status"] == "blocked"
        for row in json.loads(capsys.readouterr().out)["models"].values()
    )
