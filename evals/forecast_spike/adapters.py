"""Fail-closed offline challenger admission; no model imports or downloads."""

import re
import tomllib
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class Asset:
    name: str
    sha256: str


@dataclass(frozen=True)
class ModelPin:
    candidate: str
    repository: str
    revision: str
    package: str
    package_version: str
    files: tuple[Asset, ...]
    documentation: str
    median_documented: bool
    training_boundary: date | None
    boundary_source: str
    boundary_uncertainty: str
    boundary_reliable: bool


@dataclass(frozen=True)
class CPU:
    device: str = "cpu"
    seed: int = 27
    threads: int = 1
    workers: int = 1


@dataclass(frozen=True)
class Admission:
    status: str
    reasons: tuple[str, ...]


def readiness(
    pin: ModelPin, root: Path, lock: Path, cpu: CPU | None = None
) -> Admission:
    cpu = CPU() if cpu is None else cpu
    reasons = []
    identities = {
        "chronos_2": ("amazon/chronos-2", "chronos-forecasting"),
        "timesfm_2_5": ("google/timesfm-2.5-200m-pytorch", "timesfm"),
    }
    if identities.get(pin.candidate) != (pin.repository, pin.package):
        reasons.append("model_identity")
    if re.fullmatch(r"[a-f0-9]{40}", pin.revision) is None:
        reasons.append("revision_unpinned")
    if not pin.documentation:
        reasons.append("documentation_unconfirmed")
    if not pin.median_documented:
        reasons.append("median_undocumented")
    if not pin.boundary_source or not pin.boundary_uncertainty:
        reasons.append("training_boundary_record")
    if cpu.device != "cpu":
        reasons.append("cpu_only")
    if (
        type(cpu.seed) is not int
        or type(cpu.threads) is not int
        or type(cpu.workers) is not int
        or cpu.threads < 1
        or cpu.workers < 1
    ):
        reasons.append("cpu_configuration")
    try:
        packages = tomllib.loads(lock.read_text())["package"]
        locked = {row["name"]: row["version"] for row in packages}
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        locked = {}
    if (
        not pin.package_version
        or locked.get(pin.package) != pin.package_version
        or "torch" not in locked
    ):
        reasons.append("dependency_not_locked")
    if not root.is_dir() or not pin.files:
        reasons.append("weights_missing")
    seen = set()
    for asset in pin.files:
        name = Path(asset.name)
        if (
            not asset.name
            or name.is_absolute()
            or ".." in name.parts
            or asset.name in seen
            or root.is_symlink()
            or re.fullmatch(r"[a-f0-9]{64}", asset.sha256) is None
            or any(
                (root / Path(*name.parts[:i])).is_symlink()
                for i in range(1, len(name.parts) + 1)
            )
        ):
            reasons.append("asset_path")
            continue
        seen.add(asset.name)
        path = root / name
        if not path.is_file():
            reasons.append("weights_missing")
        elif sha256(path.read_bytes()).hexdigest() != asset.sha256:
            reasons.append("weights_hash_mismatch")
    # Official API documentation cannot be read in this no-network build and no
    # model package is locked. Never turn a metadata fixture into inference.
    reasons.append("inference_api_unconfirmed")
    return Admission("blocked", tuple(dict.fromkeys(reasons)))


def stratum(pin: ModelPin, target_end: date, provenance: str) -> str:
    if provenance in ("generated", "invented"):
        return "generated"
    if provenance != "public":
        raise ValueError("provenance")
    if (
        pin.boundary_reliable
        and pin.training_boundary is not None
        and pin.boundary_source
        and pin.boundary_uncertainty
        and target_end > pin.training_boundary
    ):
        return "post_cutoff"
    return "overlapping_or_unknown"


def eligibility(pin: ModelPin, targets: tuple[date, ...], provenance: str) -> Admission:
    if len(set(targets)) != len(targets) or tuple(sorted(targets)) != targets:
        raise ValueError("target_membership")
    strata = tuple(stratum(pin, target, provenance) for target in targets)
    if not targets or len(targets) < 12:
        return Admission("insufficient", ("minimum_evaluated_targets",))
    if all(s == "generated" for s in strata):
        return Admission(
            "eligible_generated_only", ("go_live_refit_and_backtest_required",)
        )
    if all(s == "post_cutoff" for s in strata):
        return Admission("eligible", ())
    return Admission("blocked", ("overlapping_or_unknown_descriptive_only",))


@dataclass(frozen=True)
class ProcessOutput:
    process: int
    workers: int
    output: bytes


def determinism(
    samples: tuple[ProcessOutput, ...], workers: tuple[int, ...]
) -> Admission:
    if (
        not workers
        or len(set(workers)) != len(workers)
        or any(type(w) is not int or w < 1 for w in workers)
        or set(s.workers for s in samples) != set(workers)
        or any(sum(s.workers == w for s in samples) < 2 for w in workers)
        or len({s.process for s in samples}) != len(samples)
    ):
        return Admission("blocked", ("fresh_process_evidence_missing",))
    if not samples or any(not s.output for s in samples):
        return Admission("blocked", ("empty_output",))
    if len({s.output for s in samples}) != 1:
        return Admission("fail", ("output_bytes_differ",))
    return Admission("pass", ())
