"""S2-P63: the production writer of the S2-T09 pin pair, all inputs invented.

The ``method_pins`` phase persists the pin artifact and the recorded
generation configuration as one pair from producer inputs bound to the build.
The gather_audit consumer stays the only gate; no live value, public snapshot
or review document is read by the writer or these tests.
"""

from __future__ import annotations

import json
import re
import tempfile
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
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

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


# S2-P63 round 3 (ruling L-1494): while the S2-T08 part B inputs are not
# bound, the phase never stops the live build. It writes no pair, records its
# closed pending reason for the build report, and the gate refuses the pending
# build after reports.
def test_phase_pends_unbound_generation_configuration(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_generation_config = None
    assert build.method_pins() == {}
    _no_credited_output(build)
    assert build.pin_pending_reason == "pin_inputs_missing"


def test_phase_pends_missing_producer_rows(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_rows = ()
    assert build.method_pins() == {}
    _no_credited_output(build)
    assert build.pin_pending_reason == "pin_inputs_missing"


def test_phase_pends_a_configuration_that_is_no_mapping(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_generation_config = [{"SYN": "not a recorded mapping"}]
    assert build.method_pins() == {}
    _no_credited_output(build)
    assert build.pin_pending_reason == "pin_inputs_missing"


# The bound pair of the boundness boundary: the only shape that still writes.
def test_bound_inputs_still_write_the_pair_with_no_pending_reason(
    tmp_path: Path,
) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    output = build.method_pins()
    assert set(output) == set(PHASE_OUTPUTS)
    assert build.pin_pending_reason == ""
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "recorded"
    assert "details" not in s2_t09


# The writer's own closed refusal for direct callers stays: the phase decides
# pending, the writer never accepts an unbound input.
def test_writer_refuses_unbound_inputs_directly(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_method_pins import write_pin_pair

    _paths, _record, artifact, config = case(tmp_path / "case-root")
    with pytest.raises(AssemblyError, match=r"^pin_inputs_missing$"):
        write_pin_pair(tmp_path / "cache", None, producer_rows(artifact["pins"]))
    with pytest.raises(AssemblyError, match=r"^pin_inputs_missing$"):
        write_pin_pair(tmp_path / "cache", config, ())
    assert not (tmp_path / "cache").exists()


@hypothesis_settings(deadline=None, max_examples=40)
@given(
    config=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.text(max_size=4),
        st.lists(st.integers(), max_size=3),
    ),
    rows=st.lists(
        st.dictionaries(st.text(max_size=3), st.text(max_size=3)), max_size=2
    ),
)
def test_property_an_unbound_configuration_never_writes_a_pair(config, rows):
    # Oracle written from the plan's words, never from the module's code:
    # without a recorded mapping configuration no pair is written, whatever
    # producer rows are bound, and the closed pending reason is recorded.
    with tempfile.TemporaryDirectory() as folder:
        build, *_ = _staged_phase_build(Path(folder))
        build.pin_generation_config = config
        build.pin_rows = tuple(rows)
        assert build.method_pins() == {}
        _no_credited_output(build)
        assert build.pin_pending_reason == "pin_inputs_missing"


def _pending_run_build(
    tmp_path: Path, *, stale_pair: bool = False
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """A gather-rooted Production whose head phases are invented stubs.

    The real ``method_pins``, ``final_audit``, ``draw`` and ``reports``
    adapters run in their production order through ``Production.run``; every
    earlier phase is replaced by a stub that writes only its declared invented
    outputs, and one stub registers an invented 25-row table so the figure
    draw has its review universe. The pin inputs stay unbound: the pending
    state of ruling L-1494, entered the way the live build enters it.
    """
    build, record, artifact, config = stage_method_pin_gather_build(
        tmp_path, stage_outputs=False
    )
    if stale_pair:
        for name in PHASE_OUTPUTS:
            write_record(build.cache, name, {"SYN": "stale earlier run"})
    for item in INVENTORY:
        if item.name in {"method_pins", "final_audit", "draw", "reports"}:
            continue

        def stub(item=item):
            output: dict[str, str] = {}
            for name in item.outputs:
                output.update(write_record(build.cache, name, {"SYN": item.name}))
            return output

        setattr(build, item.name, stub)
    key, sidecar = next(iter(build.receipts.items()))

    def gis_property_singles() -> dict[str, str]:
        # run() clears the bound receipts; the stub rebinds the invented
        # receipt of the fixture before any table or audit reads it.
        build.receipts[key] = sidecar
        build.table(
            "pub_invented",
            [{"period": "2026", "value": str(i), "cell": i} for i in range(25)],
            (key,),
        )
        return build.record(
            "gis_property_singles",
            {"tables": build.tables, "source_tables": build.source_tables},
        )

    build.gis_property_singles = gis_property_singles
    return build, record, artifact, config


def _s2_t09_row(cache: Path, name: str) -> dict[str, Any]:
    rows = json.loads((cache / name).read_text(encoding="utf-8"))
    return next(item for item in rows if item["task"] == "S2-T09")


def test_pending_pin_state_build_reaches_reports_and_records_its_reason(
    tmp_path: Path,
) -> None:
    build, *_ = _pending_run_build(tmp_path)
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        build.run()
    # The run continued past the pending phase to the report writer.
    for name in (
        "assembly/final_audit.json",
        "assembly/draw_values.json",
        "assembly/s2_t08_completeness.json",
        "assembly/s2_t08_terms.json",
        "assembly/s2_t08_coverage.json",
        "assembly/s2_t08_oi03.json",
        "assembly/s2_t08_confirmations.json",
        "assembly/s2_t08_investment.json",
        "assembly/s2_t08_draw.json",
    ):
        assert (build.cache / name).is_file(), name
    row = _s2_t09_row(build.cache, "assembly/s2_t08_confirmations.json")
    assert row["state"] == "pending"
    assert row["details"] == {"pending_reason": "pin_inputs_missing"}
    _no_credited_output(build)


def test_require_complete_refuses_the_pending_pin_state(tmp_path: Path) -> None:
    build, *_ = _staged_phase_build(tmp_path)
    build.pin_generation_config = None
    assert build.method_pins() == {}
    build.final_audit()
    row = next(
        item for item in build.audit["confirmations"] if item["task"] == "S2-T09"
    )
    assert row["state"] == "pending"
    assert row["details"] == {"pending_reason": "pin_inputs_missing"}
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        require_complete(otherwise_complete_audit_with_s2_t09(row))


def test_pending_pin_state_never_credits_a_stale_pair_of_an_earlier_run(
    tmp_path: Path,
) -> None:
    build, *_ = _pending_run_build(tmp_path, stale_pair=True)
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        build.run()
    # The new run removed the stale pair before any source read, the pending
    # phase wrote nothing over it, and the report credits no pin output.
    _no_credited_output(build)
    row = _s2_t09_row(build.cache, "assembly/s2_t08_confirmations.json")
    assert row["state"] == "pending"
    assert row["details"] == {"pending_reason": "pin_inputs_missing"}


def test_a_later_bound_run_leaves_no_stale_pending_reason(tmp_path: Path) -> None:
    build, _record, artifact, config = _pending_run_build(tmp_path)
    with pytest.raises(AssemblyError, match=r"^assembly_gate_pending$"):
        build.run()
    build.pin_generation_config = config
    build.pin_rows = producer_rows(artifact["pins"])
    try:
        build.run()
    except AssemblyError as exc:
        # Other gates may still be pending on invented inputs; no pin reason
        # may survive the bound run.
        assert str(exc) == "assembly_gate_pending"
    assert set(PHASE_OUTPUTS) <= set(build.files)
    assert (build.cache / PIN_ARTIFACT).is_file()
    row = next(
        item for item in build.audit["confirmations"] if item["task"] == "S2-T09"
    )
    assert row["state"] == "recorded"
    assert "details" not in row


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


# S2-P63 round 3 (ruling L-1494): the unbound-input case no longer refuses at
# the phase; the pending build runs on and the run's own gate refuses, and the
# command reports that closed reason, never the generic assembly_build_refused.
@pytest.mark.parametrize(
    "planted,reason",
    [
        ("pending_inputs", "assembly_gate_pending"),
        ("failed_second_write", "pin_output_pair_unwritten"),
    ],
)
def test_build_public_reports_the_phase_s_own_closed_pin_refusals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: str, reason: str
) -> None:
    from custodian.tests.test_source_completeness import entry

    from eii_custodian.publicdata.fetch.build import run_build

    if planted == "pending_inputs":

        def run(build: Production) -> dict[str, str]:
            # The live command binds no pin input: the phase stays pending,
            # writes no pair, and the run's own gate refuses after reports.
            assert build.method_pins() == {}
            assert not (build.cache / PIN_ARTIFACT).exists()
            require_complete(build.audit)

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
