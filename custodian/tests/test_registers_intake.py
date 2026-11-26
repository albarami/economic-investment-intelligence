"""Invented sibling-file intake, atomic publication and schema-only registry plants."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pytest
import yaml
from custodian.tests.test_registers import capture, commerce, csv_bytes, geocode, inputs

import h3
from eii_custodian.publicdata.additions import storage
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import (
    RegistryError,
    load_registry,
    read_yaml,
    registry_path,
)
from eii_custodian.publicdata.registers.__main__ import main
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import SCHEMAS, RegisterError
from eii_custodian.publicdata.registers.intake import from_environment, read_file
from eii_custodian.publicdata.registers.parse import parse
from eii_custodian.publicdata.registers.provenance import Frame, digest
from eii_custodian.publicdata.registers.validate import (
    RELEASE_TABLES,
    scan_artefact,
    validate_release,
)
from eii_custodian.publicdata.review.cache_fixture import read_parquet


def write_inputs(tmp_path, history=True, *, periods=None, snapshot_period="2026-11"):
    env = {}
    indexes = []
    for source, setting, name in [
        ("biz_register", "EII_REGISTER_FILE", "establishments.csv"),
        ("fc_register", "EII_FC_REGISTER_FILE", "qfc_companies.csv"),
    ]:
        directory = tmp_path / source
        directory.mkdir()
        primary = directory / name
        env[setting] = str(primary)
        item = capture(source, (periods or {}).get(source, "2026-12"))
        names = (
            {"establishments": name}
            if source == "biz_register"
            else {
                "companies": name,
                "geocoded": "qfc_companies_geocoded.csv",
                "events": "qfc_events.csv",
            }
        )
        for role, body in item.files.items():
            (directory / names[role]).write_bytes(body)
        index = {
            "version": "register_siblings_v1",
            "current": {"receipt": item.receipt, "files": names},
            "snapshots": [],
        }
        if history:
            older = capture(source, snapshot_period)
            old_names = {
                role: snapshot_period + "." + role + ".csv" for role in older.files
            }
            for role, body in older.files.items():
                (directory / old_names[role]).write_bytes(body)
            index["snapshots"].append({"receipt": older.receipt, "files": old_names})
        side = primary.with_name(primary.name + ".register.json")
        side.write_text(json.dumps(index))
        indexes.append((side, index))
    return env, indexes


def frame_value():
    return Frame(frozenset({h3.str_to_int(h3.latlng_to_cell(2.25, 1.25, 8))}))


def index_pins(indexes):
    return {
        index["current"]["receipt"]["source_id"]: digest(side.read_bytes())
        for side, index in indexes
    }


def test_unpinned_index_is_not_a_trusted_snapshot_selection(tmp_path):
    env, _ = write_inputs(tmp_path)
    with pytest.raises(RegisterError, match=r"^register_index_pin_missing$"):
        from_environment(env)


def test_explicit_older_pin_no_latest_substitution(tmp_path):
    env, indexes = write_inputs(tmp_path)
    current, history = from_environment(env, index_hashes=index_pins(indexes))
    assert {item.period for item in current} == {"2026-12"}
    assert {item.period for item in history} == {"2026-11"}
    assert {item.receipt["key"] for item in current} == {
        "biz_register",
        "fc_register/file",
    }
    assert all(item.receipt["kind"] == "register_file" for item in current)
    assert not list(tmp_path.rglob("*cache*"))


def test_intake_current_months_are_independent_and_may_predate_keeper(tmp_path):
    periods = {"biz_register": "2026-10", "fc_register": "2026-09"}
    env, indexes = write_inputs(tmp_path, history=False, periods=periods)
    current, history = from_environment(env, index_hashes=index_pins(indexes))
    assert {item.source_id: item.period for item in current} == periods
    assert history == ()


def test_intake_refuses_snapshot_before_keeper_floor(tmp_path):
    env, indexes = write_inputs(tmp_path, snapshot_period="2026-10")
    with pytest.raises(RegisterError, match=r"^snapshot_month$"):
        from_environment(env, index_hashes=index_pins(indexes))


@pytest.mark.parametrize(
    "plant",
    [
        "traversal",
        "absolute",
        "latest",
        "month",
        "extra",
        "duplicate_month",
        "tamper",
        "missing",
        "symlink",
    ],
)
def test_sibling_selection_integrity_plants(tmp_path, plant):
    env, indexes = write_inputs(tmp_path)
    original_pins = index_pins(indexes)
    side, index = indexes[0]
    if plant == "tamper":
        Path(env["EII_REGISTER_FILE"]).write_bytes(b"SYN tampered file")
    elif plant == "missing":
        side.unlink()
    elif plant == "symlink":
        primary = Path(env["EII_REGISTER_FILE"])
        target = primary.with_name("invented.csv")
        primary.rename(target)
        primary.symlink_to(target.name)
    else:
        if plant in {"traversal", "absolute", "latest", "month"}:
            index["snapshots"][0]["files"]["establishments"] = {
                "traversal": "../invented.csv",
                "absolute": str(tmp_path / "invented.csv"),
                "latest": "establishments.csv",
                "month": "2026-12.establishments.csv",
            }[plant]
        elif plant == "extra":
            index["private_path"] = "SYN sentinel"
        else:
            index["snapshots"].append(index["snapshots"][0])
        side.write_text(json.dumps(index))
    reason = {
        "traversal": "register_sibling_selection",
        "absolute": "register_sibling_selection",
        "latest": "register_sibling_selection",
        "month": "register_sibling_selection",
        "extra": "register_index_schema",
        "duplicate_month": "duplicate_snapshot_month",
        "tamper": "receipt_hash_mismatch",
        "missing": "register_file_unreadable",
        "symlink": "register_path",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        from_environment(
            env,
            index_hashes=original_pins if plant == "missing" else index_pins(indexes),
        )


def test_overwritten_index_and_receipt_cannot_repin_history(tmp_path):
    env, indexes = write_inputs(tmp_path)
    pins = index_pins(indexes)
    side, index = indexes[0]
    index["snapshots"] = []
    side.write_text(json.dumps(index))
    with pytest.raises(RegisterError, match=r"^register_index_hash_mismatch$"):
        from_environment(env, index_hashes=pins)


def test_changed_file_during_read_and_byte_bound(tmp_path, monkeypatch):
    path = tmp_path / "invented.csv"
    path.write_bytes(b"SYN invented")
    with pytest.raises(RegisterError, match=r"^register_file_bound$"):
        read_file(path, 1)
    real_fstat = os.fstat
    calls = 0

    def changed(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            path.write_bytes(b"SYN changed body")
        return real_fstat(fd)

    monkeypatch.setattr(os, "fstat", changed)
    with pytest.raises(RegisterError, match=r"^register_file_changed$"):
        read_file(path, 1024)


def test_reserved_path_is_rejected_before_open(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "open", lambda *a, **k: pytest.fail("forbidden read"))
    for part in (".private", "vault", "public_cache", ".env"):
        with pytest.raises(RegisterError, match=r"^register_path$"):
            read_file(tmp_path / part / "invented.csv", 1024)


def test_atomic_failure_preserves_entire_previous_set(tmp_path, monkeypatch):
    frame = frame_value()
    current = (capture(), capture("fc_register"))
    build(tmp_path, "public_only", frame, current, ())
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in (tmp_path / "current").rglob("*")
        if p.is_file()
    }
    real_write = storage.write_parquet

    def failing(path, columns, rows):
        if path.stem == "pub_register_snapshot":
            raise OSError("SYN private output sentinel")
        return real_write(path, columns, rows)

    monkeypatch.setattr(storage, "write_parquet", failing)
    with pytest.raises(RegisterError, match=r"^register_publish_failed$"):
        build(tmp_path, "protected", frame, current, ())
    after = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in (tmp_path / "current").rglob("*")
        if p.is_file()
    }
    assert before == after
    assert not (tmp_path / ".staging").exists()


@pytest.mark.parametrize(
    "plant",
    [
        "wrong_type",
        "duplicate",
        "unknown_source",
        "bad_date",
        "wrong_frame_cell",
        "list_missing_company",
        "list_bad_count",
    ],
)
def test_loader_contract_plants(tmp_path, plant):
    frame = frame_value()
    built = build(
        tmp_path, "public_only", frame, (capture(), capture("fc_register")), ()
    )
    tables = {key: [dict(row) for row in rows] for key, rows in built.tables.items()}
    card = tables["pub_register_company"][0]
    if plant == "wrong_type":
        card["name_en"] = 3
    elif plant == "duplicate":
        tables["pub_register_company"].append(dict(card))
    elif plant == "unknown_source":
        card["source_id"] = "SYN other source"
    elif plant == "bad_date":
        card["registration_issue_date"] = "2026-02-30"
    elif plant == "wrong_frame_cell":
        other = h3.str_to_int(h3.latlng_to_cell(3.25, 1.25, 8))
        frame = Frame(frame.cells | {other})
        card["registered_cell"] = other
    else:
        tables["register_company_list"] = [
            dict(
                registration_number="97005"
                if plant == "list_missing_company"
                else "54321",
                period="2026-11",
                employee_count=-1 if plant == "list_bad_count" else 3,
                suppression_reason_code=None,
            )
        ]
    reason = {
        "wrong_type": "release_type",
        "duplicate": "release_duplicate_key",
        "unknown_source": "release_source",
        "bad_date": "malformed_date",
        "wrong_frame_cell": "release_cell_mismatch",
        "list_missing_company": "list_company_missing",
        "list_bad_count": "release_count",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        validate_release(tables, frame)


@pytest.mark.parametrize(
    "plant",
    [
        "url",
        "fetch_host",
        "landing_url",
        "nightly_live_fetch",
        "commit_allowed",
        "source_id",
        "key",
        "refetch",
    ],
)
def test_file_registry_shape_cannot_become_a_transport(tmp_path, plant):
    doc = read_yaml(registry_path())
    row = next(dict(row) for row in doc["sources"] if row["key"] == "fc_register/file")
    row[plant] = {
        "url": "https://example.invalid/invented",
        "fetch_host": "example.invalid",
        "landing_url": "https://example.invalid/invented",
        "nightly_live_fetch": True,
        "commit_allowed": True,
        "source_id": "SYN source",
        "key": "SYN key",
        "refetch": {
            "value": "weekly",
            "family": "registers",
            "evidence": "SYN evidence",
        },
    }[plant]
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match=r"^register file declaration$"):
        load_registry(path)


def test_registry_headers_are_exact_metadata_contracts():
    for entry in load_registry():
        if entry.kind == "register_file":
            role = (
                "establishments" if entry.source_id == "biz_register" else "companies"
            )
            assert entry.columns == tuple((name, "string") for name in SCHEMAS[role])


def test_table_catalogue_drift_and_every_other_table_identifier_plant(tmp_path):
    root = Path(__file__).resolve().parents[2]
    pack = (
        (root / "docs/03_DATA_CONTRACTS.md")
        .read_text()
        .split("### 7.2 Table catalogue\n", 1)[1]
        .split("### 7.3 Columns\n", 1)[0]
    )
    names = frozenset(re.findall(r"^\| `([a-z0-9_]+)` \|", pack, re.MULTILINE))
    assert names == RELEASE_TABLES
    built = build(
        tmp_path, "public_only", frame_value(), (capture(), capture("fc_register")), ()
    )
    for table in names - {
        "pub_register_company",
        "pub_register_snapshot",
        "register_company_list",
    }:
        # Decision 0123: the text plant holds a withheld 97003, an input-only
        # key; the released key 54321 in the same column publishes.
        for column, value, reason in (
            ("registration_number", "54321", "release_identifier_column"),
            ("invented_text", "97003", "registration_egress"),
        ):
            with pytest.raises(RegisterError, match="^" + reason + "$"):
                validate_release(
                    {**built.tables, table: [{column: value}]},
                    frame_value(),
                    withheld_registrations=frozenset({"97003"}),
                )
        released = {**built.tables, table: [{"invented_text": "54321"}]}
        validate_release(
            released, frame_value(), withheld_registrations=frozenset({"97003"})
        )


def test_build_dispatch_never_opens_a_register_file_or_transport(tmp_path, monkeypatch):
    entries = tuple(entry for entry in load_registry() if entry.kind == "register_file")
    monkeypatch.setenv("EII_REGISTER_FILE", "SYN forbidden ambient path")
    outcome = run_build(
        entries,
        lambda *a: pytest.fail("transport invoked"),
        tmp_path,
        lambda: "2026-11-20T00:00:00Z",
        lambda *a: pytest.fail("sleep invoked"),
        environ={},
        _fetch_only=True,
    )
    assert outcome.failure is None
    assert all("lead_shell_file_input" in line for line in outcome.lines)
    assert not list(tmp_path.rglob("*.csv"))


def test_lead_cli_invented_end_to_end_only(tmp_path, monkeypatch, capsys):
    env, indexes = write_inputs(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    frame = tmp_path / "frame.json"
    body = json.dumps(sorted(frame_value().cells)).encode()
    frame.write_bytes(body)
    pins = index_pins(indexes)
    args = [
        "--frame-cells",
        str(frame),
        "--frame-sha256",
        digest(body),
        "--biz-index-sha256",
        pins["biz_register"],
        "--fc-index-sha256",
        pins["fc_register"],
        "--output",
        str(tmp_path / "release"),
        "--release-kind",
        "public_only",
    ]
    assert main(args) == 0
    assert capsys.readouterr() == ("register_inputs_validated\n", "")
    args[3] = "a" * 64
    assert main(args) == 1
    assert capsys.readouterr() == ("", "frame_hash_mismatch\n")


def test_empty_snapshot_is_kept_not_missing(tmp_path):
    frame = frame_value()
    empty = capture(files={"establishments": csv_bytes("establishments", [])})
    result = build(
        tmp_path, "public_only", frame, (capture(), capture("fc_register")), (empty,)
    )
    assert result.tables["pub_register_snapshot"] == []
    assert result.coverage["biz_register"] == ("2026-11",)


def test_fc_location_and_full_notice_are_preserved(tmp_path):
    files = inputs("fc_register")
    files["geocoded"] = csv_bytes("geocoded", [geocode(lon="1.25", lat="2.25")])
    files["events"] = csv_bytes(
        "events",
        [
            dict(
                qfc_number="65432",
                event="SYN notice",
                notice_expiration_date="2026-11-25",
            )
        ],
    )
    result = build(
        tmp_path,
        "public_only",
        frame_value(),
        (capture(), capture("fc_register", files=files)),
        (),
    )
    card = next(
        row
        for row in result.tables["pub_register_company"]
        if row["source_id"] == "fc_register"
    )
    assert card["registered_cell"] in frame_value().cells
    assert card["notice_expiration_date"] == "2026-11-25"
    assert card["event"] == "SYN notice"


def test_frames_refuse_stored_parent_and_child():
    fine = h3.latlng_to_cell(2.25, 1.25, 9)
    with pytest.raises(RegisterError, match=r"^frame_schema$"):
        Frame(
            frozenset({h3.str_to_int(fine), h3.str_to_int(h3.cell_to_parent(fine, 8))})
        )


def test_raw_bundle_bytes_and_unserializable_artefact_refuse():
    for value, reason in (
        (b"SYN copied 54321", "registration_egress"),
        (object(), "artefact_type"),
    ):
        with pytest.raises(RegisterError, match="^" + reason + "$"):
            scan_artefact(value, frozenset({"54321"}))


def test_card_name_cannot_be_copied_to_metadata(tmp_path):
    item = capture()
    side = {**item.receipt, "dataset": "SYN Invented Commerce"}
    from dataclasses import replace

    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        build(
            tmp_path,
            "public_only",
            frame_value(),
            (replace(item, receipt=side), capture("fc_register")),
            (),
        )


@pytest.mark.parametrize(
    "publisher",
    [
        "",
        "pending",
        "Lead receipt required for invented publisher",
        "lead receipt required for invented publisher",
        "  LEAD RECEIPT REQUIRED for invented publisher  ",
    ],
)
def test_placeholder_publisher_cannot_claim_completed_lineage(tmp_path, publisher):
    from dataclasses import replace

    item = capture()
    with pytest.raises(RegisterError, match=r"^receipt_metadata$"):
        build(
            tmp_path,
            "public_only",
            frame_value(),
            (
                replace(item, receipt={**item.receipt, "publisher": publisher}),
                capture("fc_register"),
            ),
            (),
        )


@pytest.mark.parametrize("basis", ["pending", "owner_decision"])
def test_prohibitive_or_pending_terms_remain_records(tmp_path, basis):
    from dataclasses import replace

    item = capture()
    side = {
        **item.receipt,
        "licence_basis": basis,
        "terms_words": "SYN prohibitive terms; use forbidden",
        "terms_read_on": "2026-11-19",
    }
    built = build(
        tmp_path,
        "public_only",
        frame_value(),
        (replace(item, receipt=side), capture("fc_register")),
        (),
    )
    receipt = next(
        entry["receipt"]
        for entry in built.manifest["receipts"]
        if entry["receipt"]["source_id"] == "biz_register"
    )
    assert receipt["licence_basis"] == basis
    assert receipt["terms_words"] == side["terms_words"]


@pytest.mark.parametrize(
    "plant",
    [
        "duplicate_header",
        "missing_column",
        "extra_cell",
        "invalid_utf8",
        "broken_quote",
        "required_empty",
        "bad_year",
        "bad_latitude",
    ],
)
def test_csv_boundary_and_lexeme_plants(plant):
    body = inputs()["establishments"]
    if plant in {"required_empty", "bad_year", "bad_latitude"}:
        changes = {
            "required_empty": {"classification": ""},
            "bad_year": {"tax_classification_year": "26"},
            "bad_latitude": {"lat": "91"},
        }[plant]
        body = inputs(rows=[commerce(**changes)])["establishments"]
    elif plant == "invalid_utf8":
        body += b"\xff"
    elif plant == "broken_quote":
        body += b'"SYN unclosed'
    else:
        lines = body.decode().splitlines()
        if plant == "duplicate_header":
            header = lines[0].split(",")
            header[1] = header[0]
            lines[0] = ",".join(header)
        elif plant == "missing_column":
            lines[0] = lines[0].rsplit(",", 1)[0]
        else:
            lines[1] += ",SYN extra"
        body = ("\n".join(lines) + "\n").encode()
    reason = {
        "duplicate_header": "input_schema",
        "missing_column": "input_schema",
        "extra_cell": "input_schema",
        "invalid_utf8": "input_csv",
        "broken_quote": "input_csv",
        "required_empty": "required_text",
        "bad_year": "integer_format",
        "bad_latitude": "coordinate_format",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        parse("biz_register", {"establishments": body}, frame_value())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("licence_basis", "SYN invented basis"),
        ("terms_read_on", "2026-02-30"),
        ("terms_read_on", "yesterday"),
        ("retrieved_utc", "2026-12-01T00:00:00Z"),
        ("retrieved_utc", "2026-11-20T00:00:00+01:00"),
        ("files", []),
    ],
)
def test_remaining_receipt_format_plants(tmp_path, field, value):
    from dataclasses import replace

    item = capture()
    reason = {
        "licence_basis": "receipt_metadata",
        "terms_read_on": "receipt_terms_date",
        "retrieved_utc": "receipt_month_mismatch"
        if isinstance(value, str) and value.endswith("Z")
        else "receipt_retrieval",
        "files": "receipt_files",
    }[field]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        build(
            tmp_path,
            "public_only",
            frame_value(),
            (
                replace(item, receipt={**item.receipt, field: value}),
                capture("fc_register"),
            ),
            (),
        )


@pytest.mark.parametrize(
    "plant",
    [
        "missing_current",
        "duplicate_current",
        "future_snapshot",
        "too_early_snapshot",
        "source_field",
        "missing_table",
    ],
)
def test_build_and_source_applicability_plants(tmp_path, plant):
    current = (capture(), capture("fc_register"))
    snapshots = ()
    if plant == "missing_current":
        current = (capture(),)
    elif plant == "duplicate_current":
        current = (capture(), capture())
    elif plant == "future_snapshot":
        snapshots = (capture(period="2026-12"),)
    elif plant == "too_early_snapshot":
        snapshots = (capture(period="2026-10"),)
    else:
        built = build(tmp_path, "public_only", frame_value(), current, snapshots)
        tables = {
            key: [dict(row) for row in rows] for key, rows in built.tables.items()
        }
        if plant == "source_field":
            centre = next(
                row
                for row in tables["pub_register_company"]
                if row["source_id"] == "fc_register"
            )
            centre["establishment_nationality"] = "SYN invented attribute"
        else:
            del tables["pub_register_snapshot"]
        reason = (
            "release_source_field"
            if plant == "source_field"
            else "release_tables_missing"
        )
        with pytest.raises(RegisterError, match="^" + reason + "$"):
            validate_release(tables, frame_value())
        return
    reason = {
        "missing_current": "current_sources",
        "duplicate_current": "current_sources",
        "future_snapshot": "snapshot_after_current",
        "too_early_snapshot": "snapshot_month",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        build(tmp_path, "public_only", frame_value(), current, snapshots)


@pytest.mark.parametrize("prefix", ["SYN-E-", "SYN-L-", "SYN-G-", "SYN-P-", "SYN-F-"])
def test_every_retired_identifier_prefix_is_refused(tmp_path, prefix):
    item = capture(files=inputs(rows=[commerce(name_en=prefix + "invented")]))
    with pytest.raises(RegisterError, match=r"^identifier_prefix$"):
        build(
            tmp_path, "public_only", frame_value(), (item, capture("fc_register")), ()
        )


@pytest.mark.parametrize(
    ("count", "reason", "valid"),
    [
        (None, "CARRIED_FORWARD", True),
        (None, None, False),
        (3, "CARRIED_FORWARD", False),
        (True, None, False),
    ],
)
def test_company_count_nullability_is_preserved(tmp_path, count, reason, valid):
    built = build(
        tmp_path, "public_only", frame_value(), (capture(), capture("fc_register")), ()
    )
    tables = {
        **built.tables,
        "register_company_list": [
            dict(
                registration_number="54321",
                period="2026-11",
                employee_count=count,
                suppression_reason_code=reason,
            )
        ],
    }
    if valid:
        validate_release(tables, frame_value())
    else:
        with pytest.raises(RegisterError, match=r"^release_count$"):
            validate_release(tables, frame_value())


@pytest.mark.parametrize("plant", ["source_type", "period_type"])
def test_release_wrong_container_types_have_fixed_refusals(tmp_path, plant):
    built = build(
        tmp_path,
        "public_only",
        frame_value(),
        (capture(), capture("fc_register")),
        (capture(),),
    )
    tables = {key: [dict(row) for row in rows] for key, rows in built.tables.items()}
    if plant == "source_type":
        tables["pub_register_company"][0]["source_id"] = []
    else:
        tables["pub_register_snapshot"][0]["period"] = []
    reason = "release_source" if plant == "source_type" else "snapshot_month"
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        validate_release(tables, frame_value())


def test_protected_list_reference_period_predates_public_snapshot_keeper(tmp_path):
    built = build(
        tmp_path, "public_only", frame_value(), (capture(), capture("fc_register")), ()
    )
    tables = {
        **built.tables,
        "register_company_list": [
            dict(
                registration_number="54321",
                period="2025-12",
                employee_count=3,
                suppression_reason_code=None,
            )
        ],
    }
    validate_release(tables, frame_value())
    assert (
        built.snapshot_reason("biz_register", "2025-11", "2025-12")
        == "snapshot_not_kept"
    )


def test_published_parquet_roundtrip_hashes_and_file_receipt_mode(
    tmp_path, monkeypatch
):
    # The existing reader uses tempfile; keep its files in this test's documented
    # workspace temp root as well as the builder's own output.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = build(
        tmp_path / "release",
        "public_only",
        frame_value(),
        (capture(), capture("fc_register")),
        (capture(),),
    )
    for table in built.manifest["tables"]:
        body = (
            tmp_path / "release/current/tables" / (table["name"] + ".parquet")
        ).read_bytes()
        assert digest(body) == table["sha256"]
        assert list(read_parquet(body)) == built.tables[table["name"]]
    entry = next(entry for entry in load_registry() if entry.key == "fc_register/file")
    side = sidecar_for(
        entry,
        digest="a" * 64,
        nbytes=3,
        fetch_url="",
        fetch_host="",
        retrieved_utc="2026-11-20T00:00:00Z",
        publisher="SYN publisher",
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    assert side["fetch_mode"] == "file_input"
    assert side["key"] == "fc_register/file"
    assert side["kind"] == "register_file"
