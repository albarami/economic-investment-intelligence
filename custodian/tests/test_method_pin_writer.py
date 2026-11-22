"""S2-P63: the production writer of the S2-T09 pin pair, all inputs invented.

The ``method_pins`` phase persists the pin artifact and the recorded
generation configuration as one pair from producer inputs bound to the build.
The gather_audit consumer stays the only gate; no live value, public snapshot
or review document is read by the writer or these tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.method_card_pin_fixtures import (
    PINS,
    case,
    digest,
    methods_document,
    pending,
    producer_rows,
)
from custodian.tests.method_pin_gather_fixtures import (
    gathered_s2_t09_confirmation,
    otherwise_complete_audit_with_s2_t09,
    stage_method_pin_gather_build,
)
from custodian.tests.test_production_adapters import context

from eii_custodian.publicdata.assembly import PHASES, AssemblyError
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.assembly_inventory import INVENTORY
from eii_custodian.publicdata.assembly_io import bound_files, write_record
from eii_custodian.publicdata.assembly_reports import require_complete
from eii_custodian.publicdata.method_card_validation import completion_evidence

PIN_ARTIFACT = "assembly/s2_t09_pin_artifact.json"
PIN_CONFIG = "assembly/s2_t09_pin_generation_config.json"
PIN_MANIFEST = "assembly/method_pins.json"
PHASE_OUTPUTS = (PIN_MANIFEST, PIN_ARTIFACT, PIN_CONFIG)

# Decision 0094: only these five result pins may stay pending at the S2 gate.
DEFERRED_TO_S7 = (
    "c6.expected_clq",
    "c6.expected_p",
    "c6.expected_q",
    "c7.shared_b_given_a",
    "c7.shared_a_given_b",
)
OI_283_REASON = "OI-283: computed by a later slice task, decision 0094"


def _staged_phase_build(
    tmp_path: Path, *, mutate: Any = None
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """A gather-rooted Production whose method_pins phase can run on inputs."""
    build, record, artifact, config = stage_method_pin_gather_build(
        tmp_path, mutate=mutate, stage_outputs=False
    )
    build.pin_generation_config = config
    build.pin_rows = producer_rows(artifact["pins"])
    return build, record, artifact, config


def _completion_paths(build: Any) -> tuple[Path, Path, Path, Path]:
    return (
        build.review / "s2_t09_source_checks.yaml",
        build.cache / PIN_ARTIFACT,
        build.cache / PIN_CONFIG,
        build.root / "docs/07_ECONOMIC_METHODS.md",
    )


def _no_credited_output(build: Any) -> None:
    assert not any(name in build.files for name in PHASE_OUTPUTS)
    assert not any((build.cache / name).exists() for name in PHASE_OUTPUTS)


def test_method_pins_phase_writes_pair_binds_hashes_and_evidence(
    tmp_path: Path,
) -> None:
    """The actual Production phase; red on the missing phase, green after."""
    build, record, artifact, config = _staged_phase_build(tmp_path)
    assert record["pins"] and artifact["pins"]
    output = build.method_pins()
    assert set(output) == set(PHASE_OUTPUTS)
    assert set(build.files) >= set(PHASE_OUTPUTS)
    for name in PHASE_OUTPUTS:
        assert build.files[name] == output[name]
    bound_files(build.cache, build.files)
    assert json.loads((build.cache / PIN_ARTIFACT).read_text(encoding="utf-8")) == (
        artifact
    )
    assert json.loads((build.cache / PIN_CONFIG).read_text(encoding="utf-8")) == config
    manifest = json.loads((build.cache / PIN_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["method"] == "public-assembly.method_pins"
    assert manifest["outputs"] == sorted((PIN_ARTIFACT, PIN_CONFIG))
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "recorded"
    require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


def test_method_pins_is_declared_after_busyness_and_before_final_audit() -> None:
    assert (
        PHASES.index("busyness")
        < PHASES.index("method_pins")
        < PHASES.index("final_audit")
    )
    item = next(item for item in INVENTORY if item.name == "method_pins")
    assert item.outputs == PHASE_OUTPUTS
    assert item.inputs
    final_audit = next(item for item in INVENTORY if item.name == "final_audit")
    assert "method_pins" in final_audit.inputs


def test_new_run_removes_stale_pin_outputs_before_any_source_read(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.fetch.build import BuildOutcome, FetchFailure

    for name in PHASE_OUTPUTS:
        write_record(tmp_path, name, {"SYN": "stale earlier run"})
    build = context(tmp_path)

    def refuse():
        assert not any((tmp_path / name).exists() for name in PHASE_OUTPUTS)
        return BuildOutcome((), FetchFailure(6, "invented", "", "unreachable", "", ""))

    build.fetcher = refuse
    with pytest.raises(AssemblyError, match=r"^assembly_fetch_refused$"):
        build.run()
    assert not any((tmp_path / name).exists() for name in PHASE_OUTPUTS)


def test_phase_refuses_missing_generation_configuration(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_generation_config = None
    with pytest.raises(AssemblyError, match=r"^pin_inputs_missing$"):
        build.method_pins()
    _no_credited_output(build)


def test_phase_refuses_missing_producer_rows(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_rows = ()
    with pytest.raises(AssemblyError, match=r"^pin_inputs_missing$"):
        build.method_pins()
    _no_credited_output(build)


def test_phase_refuses_missing_producer_row(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_rows = build.pin_rows[:-1]
    with pytest.raises(ValueError, match=r"^pin_missing_or_duplicate$"):
        build.method_pins()
    _no_credited_output(build)


def test_phase_refuses_missing_configuration_pin(tmp_path: Path) -> None:
    build, _, _, config = _staged_phase_build(tmp_path)
    del config["pins"]["wilson.period"]
    with pytest.raises(ValueError, match=r"^pin_artifact_missing$"):
        build.method_pins()
    _no_credited_output(build)


def test_phase_refuses_unknown_pin_row(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_rows = [
        *build.pin_rows,
        {"pin_id": "invented.extra", "values": {}, "source_lineage": []},
    ]
    with pytest.raises(ValueError, match=r"^pin_artifact_duplicate_or_unknown$"):
        build.method_pins()
    _no_credited_output(build)


def test_phase_refuses_failed_second_write_and_leaves_no_half_pair(
    tmp_path: Path,
) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    # The artifact write succeeds; the configuration write cannot start.
    (build.cache / PIN_CONFIG).mkdir(parents=True)
    with pytest.raises(AssemblyError, match=r"^pin_output_pair_unwritten$"):
        build.method_pins()
    assert not (build.cache / PIN_ARTIFACT).exists()
    assert PIN_ARTIFACT not in build.files


# S2-P63 round 2 (review RV1 F1, RV2): only the configuration output is a
# symlink to a file outside the cache. The refused second write must leave no
# half pair under any refusal: the new artifact is removed, the symlink itself
# is removed without following it, and its target survives.
def test_phase_refuses_symlinked_configuration_output_and_leaves_no_half_pair(
    tmp_path: Path,
) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    outside = tmp_path / "outside-the-cache.json"
    outside.write_text("SYN body outside the cache", encoding="utf-8")
    (build.cache / PIN_CONFIG).symlink_to(outside)
    with pytest.raises(AssemblyError, match=r"^pin_output_pair_unwritten$"):
        build.method_pins()
    _no_credited_output(build)
    assert not (build.cache / PIN_ARTIFACT).exists()
    assert not (build.cache / PIN_CONFIG).is_symlink()
    assert not (build.cache / PIN_CONFIG).exists()
    assert outside.read_text(encoding="utf-8") == "SYN body outside the cache"


# S2-P63 round 2 (review RV1 F1): the widened pair guard also covers the
# serialization refusals of either write. One input changed: one recorded
# setting carries a value the canonical JSON writer must refuse.
def test_phase_refuses_unserializable_setting_and_leaves_no_half_pair(
    tmp_path: Path,
) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_generation_config["pins"]["wilson.period"]["nan_setting"] = float("nan")
    with pytest.raises(AssemblyError, match=r"^pin_output_pair_unwritten$"):
        build.method_pins()
    _no_credited_output(build)


# S2-P63 round 2 (review RV1 F2): the command's assembly outcome carries the
# phase's own closed refusals, never the generic assembly_build_refused.
@pytest.mark.parametrize(
    "planted,reason",
    [
        ("unbound_inputs", "pin_inputs_missing"),
        ("failed_second_write", "pin_output_pair_unwritten"),
    ],
)
def test_build_public_reports_the_phase_s_own_closed_pin_refusals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: str, reason: str
) -> None:
    from custodian.tests.test_source_completeness import entry

    from eii_custodian.publicdata.fetch.build import run_build

    if planted == "unbound_inputs":

        def run(build: Production) -> dict[str, str]:
            # The live command binds no pin input: the phase refuses closed.
            return build.method_pins()

    else:
        # Bound, schema-valid inputs; only the second write of the pair fails.
        _paths, _record, artifact, config = case(tmp_path / "case-root")
        (tmp_path / PIN_CONFIG).mkdir(parents=True)

        def run(build: Production) -> dict[str, str]:
            build.pin_generation_config = config
            build.pin_rows = producer_rows(artifact["pins"])
            return build.method_pins()

    monkeypatch.setattr(Production, "run", run)
    outcome = run_build(
        (entry(),),
        lambda url: pytest.fail("network called"),
        tmp_path,
        lambda: "2026-11-22T00:00:00Z",
        lambda seconds: None,
        seed=36,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == reason
    assert any(reason in line for line in outcome.lines)
    assert not any("assembly_build_refused" in line for line in outcome.lines)


def test_consumer_refuses_changed_receipt_hash_of_written_pair(
    tmp_path: Path,
) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.method_pins()
    key = next(iter(build.receipts))
    build.receipts[key] = {**build.receipts[key], "sha256": digest(b"other body")}
    with pytest.raises(ValueError, match=r"^pin_lineage_receipt_mismatch$"):
        completion_evidence(
            *_completion_paths(build),
            gate="S2",
            registry=build.entries,
            receipts=build.receipts,
        )
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "pending"
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


def test_consumer_refuses_mismatched_configuration_settings(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_generation_config["pins"]["wilson.period"]["fixture_setting"] = (
        "invented-other"
    )
    build.method_pins()
    with pytest.raises(ValueError, match=r"^pin_settings_hash_mismatch$"):
        completion_evidence(
            *_completion_paths(build),
            gate="S2",
            registry=build.entries,
            receipts=build.receipts,
        )
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "pending"
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))


def _pend_deferred(paths, record, artifact, config):
    """The five decision-0094 result pins stay pending everywhere, not stand-ins."""
    for row in record["pins"]:
        if row["pin_id"] in DEFERRED_TO_S7:
            pending(row)
            row["unpinned_reason"] = OI_283_REASON
    for produced in artifact["pins"]:
        if produced["pin_id"] in DEFERRED_TO_S7:
            produced["values"] = {}
            produced["source_lineage"] = []
    paths[3].write_text(methods_document(record["pins"]), encoding="utf-8")


def test_deferred_pending_pair_reaches_s2_and_is_refused_at_s7(
    tmp_path: Path,
) -> None:
    build, *_ = _staged_phase_build(tmp_path, mutate=_pend_deferred)
    build.method_pins()
    written = json.loads((build.cache / PIN_ARTIFACT).read_text(encoding="utf-8"))
    pending_rows = [row for row in written["pins"] if row["pin_id"] in DEFERRED_TO_S7]
    assert len(pending_rows) == len(DEFERRED_TO_S7)
    assert all(
        row["values"] == {} and row["source_lineage"] == [] for row in pending_rows
    )
    assert set(
        completion_evidence(
            *_completion_paths(build),
            gate="S2",
            registry=build.entries,
            receipts=build.receipts,
        )
    ) == set(PINS)
    refusal = "S7:unpinned:" + ",".join(sorted(DEFERRED_TO_S7))
    with pytest.raises(ValueError, match=r"^" + re.escape(refusal) + "$"):
        completion_evidence(
            *_completion_paths(build),
            gate="S7",
            registry=build.entries,
            receipts=build.receipts,
        )
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "recorded"
    require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))
