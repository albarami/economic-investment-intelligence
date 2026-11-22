"""S2-T49/S2-T08: the register_tables assembly phase consumes a staged bundle.

Every fixture is invented and staged inside pytest's tmp_path; no ambient
register setting, private path or real file is read. The writer path
(registers.intake + registers.build) is unchanged; the lead stages its
published ``current/`` output as ``register_bundle/`` plus ``register_bundle_pin.json``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_registers import capture, commerce, inputs
from hypothesis import given
from hypothesis import strategies as st

import h3
from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_reports import draw_tables
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.bundle import (
    BUNDLE,
    PIN,
    Bundle,
    load_bundle,
)
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.provenance import Frame, digest


@pytest.fixture
def frame():
    return Frame(frozenset({h3.str_to_int(h3.latlng_to_cell(2.25, 1.25, 8))}))


def _frame_result(frame):
    return FrameResult(
        {"grid_cell": [{"cell": cell} for cell in frame.cells]}, [], {}, {}
    )


def _stage(
    cache: Path,
    stage: Path,
    frame,
    snapshots=(),
    current_period="2026-11",
    biz_files=None,
    release_kind="public_only",
) -> None:
    """Build an invented bundle and stage it exactly as the lead would."""
    build(
        stage,
        release_kind,
        frame,
        (
            capture(period=current_period, files=biz_files),
            capture("fc_register", period=current_period),
        ),
        snapshots,
    )
    shutil.copytree(stage / "current", cache / BUNDLE)
    manifest_sha = digest((cache / BUNDLE / "manifest.json").read_bytes())
    (cache / PIN).write_text(
        json.dumps(
            {"version": "register_bundle_pin_v1", "manifest_sha256": manifest_sha}
        )
    )


def _production(tmp_path: Path, frame, snapshots=(), **stage_kwargs):
    state = context(tmp_path)
    state.frame_result = _frame_result(frame)
    _stage(tmp_path, tmp_path / "stage", frame, snapshots, **stage_kwargs)
    return state


def _rewrite_manifest(tmp_path: Path, mutate) -> None:
    manifest_path = tmp_path / BUNDLE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mutate(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    pin = json.loads((tmp_path / PIN).read_text())
    pin["manifest_sha256"] = digest(manifest_path.read_bytes())
    (tmp_path / PIN).write_text(json.dumps(pin))


def _rebuild_rows(tmp_path: Path, frame, name: str):
    result = build(
        tmp_path / "rebuild",
        "public_only",
        frame,
        (capture(), capture("fc_register")),
        (),
    )
    return [dict(row) for row in result.tables[name]]


def test_phase_is_registered_after_frame(tmp_path: Path, frame) -> None:
    from eii_custodian.publicdata.assembly import PHASES
    from eii_custodian.publicdata.assembly_inventory import (
        INVENTORY,
        validate_inventory,
    )

    assert PHASES[PHASES.index("frame") + 1] == "register_tables"
    state = context(tmp_path)
    assert "register_tables" in state.adapters()
    validate_inventory(state.adapters())
    item = next(i for i in INVENTORY if i.name == "register_tables")
    assert item.outputs == ("assembly/register_tables.json",)


def test_production_phase_populates_both_tables_and_phase_evidence(
    tmp_path: Path, frame
) -> None:
    snapshots = (capture(period="2026-11"),)
    state = _production(tmp_path, frame, snapshots)
    state.register_tables()
    company = state.tables["pub_register_company"]
    assert {row["source_id"] for row in company} == {
        "biz_register",
        "fc_register",
    }
    snapshot_rows = state.tables["pub_register_snapshot"]
    assert [row["period"] for row in snapshot_rows] == ["2026-11"]
    assert state.table_sources["pub_register_company"] == {
        "biz_register",
        "fc_register/file",
    }
    assert state.receipts["biz_register"]["source_id"] == "biz_register"
    assert state.receipts["fc_register/file"]["kind"] == "register_file"
    record = json.loads((tmp_path / "assembly/register_tables.json").read_text())
    assert BUNDLE + "/manifest.json" in state.files
    assert PIN in state.files
    assert record["row_sources"]["pub_register_company"] == [
        "biz_register",
        "fc_register/file",
    ]
    assert record["snapshot_coverage"]["biz_register"] == ["2026-11"]
    assert len(record["receipts"]) == 3


def test_phase_tables_survive_draw_and_completeness_binding(
    tmp_path: Path, frame
) -> None:
    snapshots = (capture(period="2026-11"),)
    biz = inputs("biz_register", [commerce(capital_qar="1000")])
    state = _production(tmp_path, frame, snapshots, biz_files=biz)
    state.register_tables()
    readers = draw_tables(state)
    assert {
        "pub_register_company",
        "pub_register_snapshot",
    } <= set(readers)
    figures = readers["pub_register_company"]()
    assert figures
    assert all(f.kind == "money" for f in figures)
    assert all(
        f.filter.startswith("snapshot=" + state.receipts["biz_register"]["sha256"])
        for f in figures
    )
    from eii_custodian.publicdata.completeness import Pack, check
    from eii_custodian.publicdata.fetch.registry import load_registry

    rows = [
        e
        for e in load_registry()
        if e.source_id in {"biz_register", "fc_register"} and e.kind == "register_file"
    ]
    record = check(
        entries=rows,
        pack=Pack({}, frozenset()),
        inventory={},
        catalogue={"pub_register_company", "pub_register_snapshot"},
        receipts=state.receipts,
        outputs=state.source_tables,
        absences={},
        cached_source_ids=(),
    )
    assert not [row for row in record if row["state"] == "failed"]
    assert {row["id"] for row in record if row["state"] == "in use"} == {
        "biz_register",
        "fc_register/file",
    }


def test_completeness_refuses_register_row_without_valid_receipt(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.completeness import Pack, check
    from eii_custodian.publicdata.fetch.registry import load_registry

    rows = [
        e
        for e in load_registry()
        if e.source_id in {"biz_register", "fc_register"} and e.kind == "register_file"
    ]
    record = check(
        entries=rows,
        pack=Pack({}, frozenset()),
        inventory={},
        catalogue={"pub_register_company", "pub_register_snapshot"},
        receipts={},
        outputs={},
        absences={},
        cached_source_ids=(),
    )
    failed = {row["id"]: row["state"] for row in record}
    assert failed["biz_register"] == "failed"
    assert failed["fc_register/file"] == "failed"


def test_completeness_refuses_invalid_register_receipt(tmp_path: Path) -> None:
    from eii_custodian.publicdata.completeness import Pack, check
    from eii_custodian.publicdata.fetch.registry import load_registry

    rows = [
        e
        for e in load_registry()
        if e.source_id in {"biz_register", "fc_register"} and e.kind == "register_file"
    ]
    receipts = {
        row.key: {
            "version": "register_input_v1",
            "kind": "register_file",
            "key": row.key,
            "source_id": row.source_id,
            "period": "2026-11",
            "publisher": "SYN invented publisher",
            "dataset": "SYN register capture",
            "retrieved_utc": "2026-11-20T00:00:00Z",
            "licence_id": "pending",
            "licence_basis": "owner_decision",
            "sha256": "0" * 64,
        }
        for row in rows
    }
    receipts["biz_register"]["version"] = "unknown_v0"
    outputs = {
        row.key: ["pub_register_company", "pub_register_snapshot"] for row in rows
    }
    record = check(
        entries=rows,
        pack=Pack({}, frozenset()),
        inventory={},
        catalogue={"pub_register_company", "pub_register_snapshot"},
        receipts=receipts,
        outputs=outputs,
        absences={},
        cached_source_ids=(),
    )
    by_id = {row["id"]: row["state"] for row in record}
    assert by_id["biz_register"] == "failed"
    assert by_id["fc_register/file"] == "in use"


def test_missing_bundle_is_refused(tmp_path: Path, frame) -> None:
    state = context(tmp_path)
    state.frame_result = _frame_result(frame)
    with pytest.raises(RegisterError, match=r"^register_bundle_missing$"):
        state.register_tables()


def test_missing_pin_is_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    (tmp_path / PIN).unlink()
    with pytest.raises(RegisterError, match=r"^register_bundle_missing$"):
        state.register_tables()


def test_wrong_pin_refuses(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    pin = json.loads((tmp_path / PIN).read_text())
    pin["manifest_sha256"] = "0" * 64
    (tmp_path / PIN).write_text(json.dumps(pin))
    with pytest.raises(RegisterError, match=r"^register_bundle_pin$"):
        state.register_tables()


def test_extra_pin_key_refuses(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    pin = json.loads((tmp_path / PIN).read_text())
    pin["extra"] = "x"
    (tmp_path / PIN).write_text(json.dumps(pin))
    with pytest.raises(RegisterError, match=r"^register_bundle_pin$"):
        state.register_tables()


def test_manifest_key_set_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: m.pop("method"))
    with pytest.raises(RegisterError, match=r"^register_bundle_manifest$"):
        state.register_tables()


def _fix_receipt_sha(manifest) -> None:
    for item in manifest["receipts"]:
        item["receipt_sha256"] = digest(
            json.dumps(item["receipt"], sort_keys=True, separators=(",", ":")).encode()
        )


def test_manifest_binding_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: m.__setitem__("method", "x"))
    with pytest.raises(RegisterError, match=r"^register_bundle_manifest$"):
        state.register_tables()


def test_receipt_use_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: m["receipts"][0].__setitem__("use", "latest"))
    with pytest.raises(RegisterError, match=r"^register_bundle_receipt$"):
        state.register_tables()


def _alter_receipt(manifest, field, value) -> None:
    for item in manifest["receipts"]:
        if item["use"] == "current" and item["receipt"]["source_id"] == "biz_register":
            item["receipt"][field] = value
    _fix_receipt_sha(manifest)


def test_receipt_schema_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: _alter_receipt(m, "junk", "x"))
    with pytest.raises(RegisterError, match=r"^receipt_schema$"):
        state.register_tables()


def test_receipt_binding_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: _alter_receipt(m, "kind", "x"))
    with pytest.raises(RegisterError, match=r"^receipt_binding$"):
        state.register_tables()


def test_receipt_metadata_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: _alter_receipt(m, "publisher", ""))
    with pytest.raises(RegisterError, match=r"^receipt_metadata$"):
        state.register_tables()


def test_receipt_licence_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: _alter_receipt(m, "licence_basis", "bogus"))
    with pytest.raises(RegisterError, match=r"^receipt_metadata$"):
        state.register_tables()


def test_receipt_retrieval_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(
        tmp_path, lambda m: _alter_receipt(m, "retrieved_utc", "not-a-date")
    )
    with pytest.raises(RegisterError, match=r"^receipt_retrieval$"):
        state.register_tables()


def test_receipt_files_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)

    def alter(manifest):
        for item in manifest["receipts"]:
            if (
                item["use"] == "current"
                and item["receipt"]["source_id"] == "biz_register"
            ):
                item["receipt"]["files"] = {}
        _fix_receipt_sha(manifest)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^receipt_files$"):
        state.register_tables()


def test_receipt_file_binding_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)

    def alter(manifest):
        for item in manifest["receipts"]:
            if (
                item["use"] == "current"
                and item["receipt"]["source_id"] == "biz_register"
            ):
                item["receipt"]["files"] = {
                    "establishments": {"sha256": "nothex", "bytes": 1}
                }
        _fix_receipt_sha(manifest)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^receipt_files$"):
        state.register_tables()


def test_pre_floor_month_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame, (capture(period="2026-11"),))

    def alter(manifest):
        manifest["snapshot_coverage"]["biz_register"] = ["2026-10"]
        for item in manifest["receipts"]:
            if item["use"] == "snapshot":
                item["receipt"]["period"] = "2026-10"
                item["receipt"]["retrieved_utc"] = "2026-10-20T00:00:00Z"
        _fix_receipt_sha(manifest)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^snapshot_month$"):
        state.register_tables()


def test_duplicate_month_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame, (capture(period="2026-11"),))

    def alter(manifest):
        manifest["receipts"].append(manifest["receipts"][-1])

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^duplicate_snapshot_month$"):
        state.register_tables()


def test_after_current_month_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame, (capture(period="2026-11"),))

    def alter(manifest):
        manifest["snapshot_coverage"]["biz_register"] = ["2026-12"]
        for item in manifest["receipts"]:
            if item["use"] == "snapshot":
                item["receipt"]["period"] = "2026-12"
                item["receipt"]["retrieved_utc"] = "2026-11-20T00:00:00Z"
        _fix_receipt_sha(manifest)

    _rewrite_manifest(tmp_path, alter)
    # The receipt's own period/retrieval mismatch is the first closed refusal.
    with pytest.raises(RegisterError, match=r"^receipt_month_mismatch$"):
        state.register_tables()


def test_after_current_period_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame, (capture(period="2026-11"),))

    def alter(manifest):
        manifest["snapshot_coverage"]["biz_register"] = ["2026-12"]
        for item in manifest["receipts"]:
            if item["use"] == "snapshot":
                item["receipt"]["period"] = "2026-12"
                item["receipt"]["retrieved_utc"] = "2026-12-20T00:00:00Z"
        _fix_receipt_sha(manifest)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^snapshot_after_current$"):
        state.register_tables()


def test_row_count_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)

    def alter(manifest):
        manifest["tables"][0]["rows"] += 1

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^register_bundle_table$"):
        state.register_tables()


def test_row_period_not_kept_refused(tmp_path: Path, frame) -> None:
    from eii_custodian.publicdata.additions.storage import write_parquet
    from eii_custodian.publicdata.registers.contracts import (
        SNAPSHOT_COLUMNS,
        column_type,
    )

    state = _production(tmp_path, frame, (capture(period="2026-11"),))
    rows = _rebuild_rows(tmp_path, frame, "pub_register_snapshot")
    if not rows:
        built = build(
            tmp_path / "rebuild",
            "public_only",
            frame,
            (capture(period="2026-12"), capture("fc_register", period="2026-12")),
            (capture(period="2026-11"),),
        )
        rows = [dict(row) for row in built.tables["pub_register_snapshot"]]
    for row in rows:
        row["period"] = "2026-12"
    sha = write_parquet(
        tmp_path / BUNDLE / "tables/pub_register_snapshot.parquet",
        [(name, column_type(name)) for name in SNAPSHOT_COLUMNS],
        [tuple(row.get(name) for name in SNAPSHOT_COLUMNS) for row in rows],
    )

    def alter(manifest):
        for item in manifest["tables"]:
            if item["name"] == "pub_register_snapshot":
                item["sha256"] = sha
                item["rows"] = len(rows)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^register_bundle_period$"):
        state.register_tables()


def test_manifest_frame_mismatch_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    _rewrite_manifest(tmp_path, lambda m: m.__setitem__("frame_sha256", "0" * 64))
    with pytest.raises(RegisterError, match=r"^frame_hash_mismatch$"):
        state.register_tables()


def test_run_frame_mismatch_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    other = h3.str_to_int(h3.latlng_to_cell(2.3, 1.3, 8))
    state.frame_result = FrameResult({"grid_cell": [{"cell": other}]}, [], {}, {})
    with pytest.raises(RegisterError, match=r"^frame_hash_mismatch$"):
        state.register_tables()


def test_manifest_source_missing_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)

    def drop(manifest):
        manifest["receipts"] = [
            item
            for item in manifest["receipts"]
            if not (
                item["use"] == "current"
                and item["receipt"]["source_id"] == "fc_register"
            )
        ]

    _rewrite_manifest(tmp_path, drop)
    with pytest.raises(RegisterError, match=r"^register_bundle_source$"):
        state.register_tables()


def test_manifest_table_set_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)

    def rename(manifest):
        for item in manifest["tables"]:
            if item["name"] == "pub_register_snapshot":
                item["name"] = "other_table"

    _rewrite_manifest(tmp_path, rename)
    with pytest.raises(RegisterError, match=r"^register_bundle_table$"):
        state.register_tables()


def test_substituted_table_bytes_refused(tmp_path: Path, frame) -> None:
    from eii_custodian.publicdata.additions.storage import write_parquet
    from eii_custodian.publicdata.registers.contracts import (
        CARD_COLUMNS,
        column_type,
    )

    state = _production(tmp_path, frame)
    # Substituted bytes keep the same schema and row count but hash differently.
    rows = _rebuild_rows(tmp_path, frame, "pub_register_company")
    write_parquet(
        tmp_path / BUNDLE / "tables/pub_register_company.parquet",
        [(name, column_type(name)) for name in CARD_COLUMNS],
        [tuple(row.get(name) for name in CARD_COLUMNS) for row in reversed(rows)],
    )
    with pytest.raises(RegisterError, match=r"^register_bundle_table$"):
        state.register_tables()


def test_foreign_table_file_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)
    (tmp_path / BUNDLE / "tables/extra.parquet").write_bytes(b"x")
    with pytest.raises(RegisterError, match=r"^register_bundle_table$"):
        state.register_tables()


def test_altered_receipt_digest_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame)

    def alter(manifest):
        manifest["receipts"][0]["receipt_sha256"] = "0" * 64

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^register_bundle_receipt$"):
        state.register_tables()


def test_wrong_period_refused(tmp_path: Path, frame) -> None:
    state = _production(tmp_path, frame, (capture(period="2026-11"),))

    def alter(manifest):
        manifest["snapshot_coverage"]["biz_register"] = ["2026-11", "2026-12"]

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^register_bundle_period$"):
        state.register_tables()


@given(
    st.sets(st.from_regex(r"202[6-9]-(0[1-9]|1[0-2])", fullmatch=True)),
    st.from_regex(r"202[6-9]-(0[1-9]|1[0-2])", fullmatch=True),
    st.from_regex(r"202[6-9]-(0[1-9]|1[0-2])", fullmatch=True),
)
def test_snapshot_reason_is_closed_over_the_month_domain(
    kept: set, earlier: str, later: str
) -> None:
    """No coverage answer other than kept-both or snapshot_not_kept exists."""
    bundle = Bundle(
        tables={},
        manifest={},
        manifest_sha256="0" * 64,
        table_sha256={},
        coverage={"biz_register": tuple(sorted(kept))},
        receipts=(),
        current={},
    )
    answer = bundle.snapshot_reason("biz_register", earlier, later)
    if earlier in kept and later in kept:
        assert answer is None
    else:
        assert answer == "snapshot_not_kept"


def test_missing_earlier_month_reports_snapshot_not_kept(tmp_path: Path, frame) -> None:
    snapshots = (capture(period="2026-11"), capture(period="2027-01"))
    state = _production(tmp_path, frame, snapshots, current_period="2027-02")
    bundle = load_bundle(
        tmp_path / BUNDLE,
        tmp_path / PIN,
        frozenset(frame.cells),
    )
    assert bundle.snapshot_reason("biz_register", "2026-11", "2027-01") is None
    assert (
        bundle.snapshot_reason("biz_register", "2026-11", "2026-12")
        == "snapshot_not_kept"
    )
    state.register_tables()
    record = json.loads((tmp_path / "assembly/register_tables.json").read_text())
    assert record["snapshot_coverage"]["biz_register"] == ["2026-11", "2027-01"]


def test_person_column_plant_refused(tmp_path: Path, frame) -> None:
    from eii_custodian.publicdata.additions.storage import write_parquet
    from eii_custodian.publicdata.registers.contracts import (
        CARD_COLUMNS,
        column_type,
    )

    state = _production(tmp_path, frame)
    rows = _rebuild_rows(tmp_path, frame, "pub_register_company")
    columns = [*list(CARD_COLUMNS), "person_name"]
    for row in rows:
        row["person_name"] = "SYN forbidden person"
    sha = write_parquet(
        tmp_path / BUNDLE / "tables/pub_register_company.parquet",
        [(name, column_type(name)) for name in columns],
        [tuple(row.get(name) for name in columns) for row in rows],
    )

    def alter(manifest):
        for item in manifest["tables"]:
            if item["name"] == "pub_register_company":
                item["sha256"] = sha
                item["rows"] = len(rows)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^release_schema$"):
        state.register_tables()
    assert "pub_register_company" not in state.tables


def test_identifier_egress_plant_refused(tmp_path: Path, frame) -> None:
    from eii_custodian.publicdata.additions.storage import write_parquet
    from eii_custodian.publicdata.registers.contracts import (
        CARD_COLUMNS,
        column_type,
    )

    state = _production(tmp_path, frame)
    rows = _rebuild_rows(tmp_path, frame, "pub_register_company")
    for row in rows:
        if row["source_id"] == "biz_register":
            row["licence_number"] = "65432"
    sha = write_parquet(
        tmp_path / BUNDLE / "tables/pub_register_company.parquet",
        [(name, column_type(name)) for name in CARD_COLUMNS],
        [tuple(row.get(name) for name in CARD_COLUMNS) for row in rows],
    )

    def alter(manifest):
        for item in manifest["tables"]:
            if item["name"] == "pub_register_company":
                item["sha256"] = sha
                item["rows"] = len(rows)

    _rewrite_manifest(tmp_path, alter)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        state.register_tables()


def test_raw_private_path_is_never_read(tmp_path: Path, frame) -> None:
    """A planted private path cannot be opened through the boundary."""
    from eii_custodian.publicdata.registers.bundle import _read

    secret = tmp_path / "private.env"
    secret.write_text("a=1")
    with pytest.raises(RegisterError, match=r"^register_bundle_missing$"):
        _read(tmp_path / "missing", 4, "register_bundle_missing")
    state = _production(tmp_path, frame)
    state.register_tables()
    assert all("private" not in path for path in state.files)


def test_unreadable_leaf_file_refused(tmp_path: Path) -> None:
    """An existing but unreadable staged file is refused, not leaked."""
    import os

    from eii_custodian.publicdata.registers.bundle import _read

    blocked = tmp_path / "blocked.json"
    blocked.write_text("{}")
    os.chmod(blocked, 0)
    try:
        with pytest.raises(RegisterError, match=r"^register_bundle_missing$"):
            _read(blocked, 1024, "x")
    finally:
        os.chmod(blocked, 0o600)


def test_symlinked_leaf_file_refused(tmp_path: Path) -> None:
    """A symlinked staged file is refused at the leaf, not only at the root."""
    from eii_custodian.publicdata.registers.bundle import _read

    target = tmp_path / "real.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(RegisterError, match=r"^register_bundle_missing$"):
        _read(link, 1024, "x")


def test_frame_incomplete_refuses_before_bundle_read(tmp_path: Path) -> None:
    state = context(tmp_path)
    with pytest.raises(AssemblyError, match="assembly_frame_incomplete"):
        state.register_tables()


def test_public_only_and_protected_release_kinds_are_equivalent(
    tmp_path: Path, frame
) -> None:
    for kind in ("public_only", "protected"):
        cache = tmp_path / kind
        cache.mkdir()
        _stage(cache, tmp_path / ("stage" + kind), frame, release_kind=kind)
        state = context(cache)
        state.frame_result = _frame_result(frame)
        state.register_tables()
        assert state.tables["pub_register_company"]


def test_symlinked_bundle_refuses(tmp_path: Path, frame) -> None:
    import os

    state = _production(tmp_path, frame)
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.rmtree(tmp_path / BUNDLE)
    os.symlink(outside, tmp_path / BUNDLE, target_is_directory=True)
    with pytest.raises(AssemblyError, match="assembly_path_invalid"):
        state.register_tables()
