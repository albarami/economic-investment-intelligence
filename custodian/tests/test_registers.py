"""S2-T49: invented schema-shaped CSVs only; never read ambient register inputs."""

from __future__ import annotations

import csv
import io
import json
import socket
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import h3
from eii_custodian.publicdata.fetch.kinds import prepare
from eii_custodian.publicdata.fetch.registry import load_registry, nightly_blocked
from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import SCHEMAS, RegisterError
from eii_custodian.publicdata.registers.intake import from_environment
from eii_custodian.publicdata.registers.parse import parse
from eii_custodian.publicdata.registers.provenance import Capture, Frame, receipt_for
from eii_custodian.publicdata.registers.validate import (
    scan_artefact,
    scan_content,
    validate_release,
)
from eii_custodian.publicdata.review.cache_fixture import read_parquet


def csv_bytes(role, rows):
    stream = io.StringIO(newline="")
    headers = list(SCHEMAS[role])
    if role == "establishments":
        headers += ["nationality_group", "nationality_group_ar"]
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


# Published row keys are twenty lowercase hexadecimal characters, digits
# included (the lead's source shape); the released identity spells each digit
# as a letter under decision 0104 item 1, written out here by hand.
ROW_HEX_FIXTURE = "a0b1c2d3e4f5a6b7c8d9"
ROW_IDENTITY_FIXTURE = "ROW-agbhcidjekflambncodp"
FC_ROW_HEX_FIXTURE = "b0c1d2e3f4a5b6c7d8e9"


def row_identity_oracle(key):
    """An independent spelling of decision 0104 item 1 for test expectations."""
    letters = dict(zip("0123456789", "ghijklmnop", strict=True))
    return "ROW-" + "".join(letters.get(character, character) for character in key)


def commerce(**updates):
    row = dict.fromkeys(SCHEMAS["establishments"], "")
    row.update(
        row_key=ROW_HEX_FIXTURE,
        name_ar="SYN invented Arabic name",
        name_en="SYN Invented Commerce",
        classification="SYN classification",
        registration_issue_date="2026-11-03",
        registration_expiry_date="2027-11-03",
        licence_status="Active",
        licence_issue_date="2026-11-03",
        licence_expiry_date="2027-11-03",
        municipality="SYN municipality",
        zone="3",
        lon="1.25",
        lat="2.25",
        registration_number="54321",
        licence_number="97003",
        tax_registered="no",
        establishment_nationality="SYN establishment nationality",
        establishment_nationality_ar="SYN establishment nationality",
        street_number="3",
        building_number="3",
        classification_ar="SYN classification",
        licence_status_ar="SYN status",
        municipality_ar="SYN municipality",
        nationality_group="SYN input-only group",
        nationality_group_ar="SYN input-only group",
        block_en="3",
        block_ar="3",
        points_at_location="1",
    )
    row.update(updates)
    return row


def fc(number="65432", **updates):
    row = dict(
        row_key=FC_ROW_HEX_FIXTURE,
        qfc_number=number,
        name_en="SYN Invented Centre",
        name_ar="",
        registered_address="SYN invented published address",
        licence_status="SYN open status",
        register_order="1",
    )
    row.update(updates)
    return row


def geocode(number="65432", **updates):
    row = dict(
        row_key=FC_ROW_HEX_FIXTURE,
        qfc_number=number,
        building_name="SYN unconfirmed derived building",
        matched_place="SYN derived match",
        match_quality="SYN open quality",
        lon="",
        lat="",
    )
    row.update(updates)
    return row


def inputs(source="biz_register", rows=None):
    if source == "biz_register":
        return {"establishments": csv_bytes("establishments", rows or [commerce()])}
    return {
        "companies": csv_bytes("companies", rows or [fc()]),
        "geocoded": csv_bytes("geocoded", [geocode()]),
        "events": csv_bytes("events", []),
    }


def capture(source="biz_register", period="2026-11", files=None):
    files = inputs(source) if files is None else files
    receipt = receipt_for(
        source,
        period,
        files,
        publisher="SYN invented publisher",
        dataset="SYN register capture",
        retrieved_utc=period + "-20T00:00:00Z",
        licence_id="pending",
        licence_basis="owner_decision",
        terms_words="terms to be read",
        terms_read_on="pending",
        basis_note="decision 0026; local use",
    )
    return Capture(source, period, files, receipt)


@pytest.fixture
def frame():
    return Frame(frozenset({h3.str_to_int(h3.latlng_to_cell(2.25, 1.25, 8))}))


def test_both_card_shapes_preserve_public_fields_and_frame(frame):
    biz = parse("biz_register", inputs(), frame)
    centre = parse("fc_register", inputs("fc_register"), frame)
    assert biz[0]["registered_cell"] in frame.cells
    assert biz[0]["registration_issue_date"] == "2026-11-03"
    assert biz[0]["name_en"] == commerce()["name_en"]
    assert centre[0]["registration_number"] == "65432"
    assert centre[0]["registered_cell"] is None
    assert centre[0]["registered_address"] == fc()["registered_address"]
    assert centre[0]["registration_issue_date"] is None
    assert "building_name" not in centre[0]
    for column in (
        "row_key",
        "nationality_group",
        "nationality_group_ar",
        "points_at_location",
    ):
        assert column not in biz[0]


@pytest.mark.parametrize(
    "column", ["extra", "person_name", "wage", "residence_address"]
)
def test_extra_and_person_columns_are_refused(frame, column):
    body = inputs()["establishments"].decode().splitlines()
    body[0] += "," + column
    body[1] += ",SYN secret sentinel"
    with pytest.raises(RegisterError, match=r"^input_schema$"):
        parse(
            "biz_register", {"establishments": ("\n".join(body) + "\n").encode()}, frame
        )


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("registration_number", "SYN-F-key", "registration_format"),
        ("registration_number", "9" * 8, "registration_format"),
        ("row_key", "Z" * 20, "row_key_format"),
        ("registration_issue_date", "2026-02-30", "malformed_date"),
        ("registration_expiry_date", "03-11-2027", "malformed_date"),
        ("lon", "NaN", "coordinate_format"),
        ("lon", "181", "coordinate_format"),
        ("branches", "SYN guessed branch", "unconfirmed_branch_structure"),
        ("tax_registered", "Maybe", "tax_registered_format"),
        ("zone", "SYN zone", "integer_format"),
    ],
)
def test_declared_formats_have_planted_violations(frame, column, value, reason):
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        parse("biz_register", inputs(rows=[commerce(**{column: value})]), frame)


@pytest.mark.parametrize(
    "number", ["54321", "543210", "543210/1", "54321/12", "543210/123"]
)
def test_declared_registration_shapes_and_open_categories(frame, number):
    row = commerce(registration_number=number, legal_form="SYN unlisted form")
    assert (
        parse("biz_register", inputs(rows=[row]), frame)[0]["registration_number"]
        == number
    )


def test_duplicate_registration_and_row_key_refused(frame):
    for rows, reason in [
        ([commerce(), commerce(registration_number="97005")], "duplicate_row_key"),
    ]:
        with pytest.raises(RegisterError, match="^" + reason + "$"):
            parse("biz_register", inputs(rows=rows), frame)


def test_empty_frame_and_missing_coordinates_never_relocate(frame):
    assert (
        parse("biz_register", inputs(), Frame(frozenset()))[0]["registered_cell"]
        is None
    )
    centre = inputs("fc_register")
    centre["geocoded"] = csv_bytes("geocoded", [geocode(lon="1.25")])
    with pytest.raises(RegisterError, match=r"^coordinate_pair$"):
        parse("fc_register", centre, frame)


@pytest.mark.parametrize(
    "plant",
    [
        "missing_companion",
        "unmatched_key",
        "wrong_row_key",
        "duplicate_geocode",
        "bad_notice",
        "unknown_event_company",
    ],
)
def test_fc_companion_joins_and_malformed_notices(frame, plant):
    files = inputs("fc_register")
    if plant == "missing_companion":
        del files["geocoded"]
    elif plant == "unmatched_key":
        files["geocoded"] = csv_bytes("geocoded", [geocode("65433")])
    elif plant == "wrong_row_key":
        files["geocoded"] = csv_bytes("geocoded", [geocode(row_key="c" * 20)])
    elif plant == "duplicate_geocode":
        files["geocoded"] = csv_bytes("geocoded", [geocode(), geocode()])
    else:
        files["events"] = csv_bytes(
            "events",
            [
                dict(
                    qfc_number="65433" if plant == "unknown_event_company" else "65432",
                    event="SYN event",
                    notice_expiration_date="29-ABC-123"
                    if plant == "bad_notice"
                    else "",
                )
            ],
        )
    reason = {
        "missing_companion": "input_schema",
        "unmatched_key": "companion_keys",
        "wrong_row_key": "companion_row_key",
        "duplicate_geocode": "duplicate_registration_key",
        "bad_notice": "malformed_date",
        "unknown_event_company": "companion_keys",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        parse("fc_register", files, frame)


@pytest.mark.parametrize(
    "plant",
    [
        "hash",
        "bytes",
        "source",
        "key",
        "kind",
        "period",
        "publisher",
        "retrieval",
        "extra",
        "missing_role",
    ],
)
def test_receipt_chain_is_complete_and_key_scoped(tmp_path, frame, plant):
    item = capture()
    side = dict(item.receipt)
    if plant in {"hash", "bytes"}:
        side["files"] = {k: dict(v) for k, v in side["files"].items()}
        side["files"]["establishments"]["sha256" if plant == "hash" else "bytes"] = (
            "a" * 64 if plant == "hash" else 0
        )
    else:
        field, value = {
            "source": ("source_id", "fc_register"),
            "key": ("key", "fc_register"),
            "kind": ("kind", "public_page"),
            "period": ("period", "2026-12"),
            "publisher": ("publisher", ""),
            "retrieval": ("retrieved_utc", "2026-02-30T00:00:00Z"),
            "extra": ("person_name", "SYN sentinel"),
            "missing_role": ("files", {}),
        }[plant]
        side[field] = value
    reason = {
        "hash": "receipt_hash_mismatch",
        "bytes": "receipt_hash_mismatch",
        "source": "receipt_binding",
        "key": "receipt_binding",
        "kind": "receipt_binding",
        "period": "receipt_binding",
        "publisher": "receipt_metadata",
        "retrieval": "receipt_retrieval",
        "extra": "receipt_schema",
        "missing_role": "receipt_files",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        build(
            tmp_path,
            "public_only",
            frame,
            (replace(item, receipt=side), capture("fc_register")),
            (),
        )
    assert not (tmp_path / "current").exists()


@pytest.mark.parametrize("files", [{}, {"establishments": "not bytes"}])
def test_capture_file_set_and_body_plants_refused(tmp_path, frame, files):
    item = replace(capture(), files=files)
    with pytest.raises(RegisterError, match=r"^receipt_files$"):
        build(
            tmp_path,
            "public_only",
            frame,
            (item, capture("fc_register")),
            (),
        )
    assert not (tmp_path / "current").exists()


def test_history_keeps_exited_company_and_earlier_location(tmp_path, frame):
    earlier = capture(period="2026-11")
    moved = capture(period="2026-12", files=inputs(rows=[commerce(lon="15.25")]))
    current = capture(
        period="2027-01", files=inputs(rows=[commerce(registration_number="97005")])
    )
    result = build(
        tmp_path,
        "public_only",
        frame,
        (current, capture("fc_register", "2027-01")),
        (earlier, moved),
    )
    rows = result.tables["pub_register_snapshot"]
    assert rows[0]["registration_number"] == "54321"
    assert rows[0]["registered_cell"] in frame.cells
    assert rows[1]["registered_cell"] is None
    assert "54321" not in {
        r["registration_number"] for r in result.tables["pub_register_company"]
    }
    assert result.coverage["fc_register"] == ()
    assert (
        result.snapshot_reason("fc_register", "2026-11", "2026-12")
        == "snapshot_not_kept"
    )
    assert result.snapshot_reason("biz_register", "2026-11", "2026-12") is None
    assert set(rows[0]) == {
        "registration_number",
        "period",
        "source_id",
        "registered_cell",
    }


@pytest.mark.parametrize(
    "plant",
    [
        "cross_source",
        "cross_source_history",
        "duplicate_month",
        "bad_month",
        "release_kind",
    ],
)
def test_ambiguous_keys_and_periods_refused(tmp_path, frame, plant):
    company = capture()
    centre = capture("fc_register")
    snapshots = ()
    kind = "public_only"
    if plant == "cross_source":
        files = inputs("fc_register", [fc("54321")])
        files["geocoded"] = csv_bytes("geocoded", [geocode("54321")])
        centre = capture("fc_register", files=files)
    elif plant == "cross_source_history":
        company = capture(period="2026-12")
        centre = capture("fc_register", "2026-12")
        snapshots = (
            capture(
                period="2026-11",
                files=inputs(rows=[commerce(registration_number="65432")]),
            ),
        )
    elif plant == "duplicate_month":
        snapshots = (capture(), capture())
    elif plant == "bad_month":
        snapshots = (replace(capture(), period="2026-13"),)
    else:
        kind = "unknown"
    reason = {
        "cross_source": "ambiguous_cross_source_key",
        "cross_source_history": "ambiguous_cross_source_key",
        "duplicate_month": "duplicate_snapshot_month",
        "bad_month": "snapshot_month",
        "release_kind": "release_kind",
    }[plant]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        build(tmp_path, kind, frame, (company, centre), snapshots)


def test_both_release_kinds_consume_equal_validated_tables(tmp_path, frame):
    results = [
        build(
            tmp_path / kind,
            kind,
            frame,
            (capture(), capture("fc_register")),
            (capture(),),
        )
        for kind in ("public_only", "protected")
    ]
    assert results[0].tables == results[1].tables
    assert results[0].manifest["tables"] == results[1].manifest["tables"]
    assert results[0].manifest["frame_sha256"] == frame.sha256
    for result in results:
        report = json.dumps(result.manifest)
        assert "SYN Invented Commerce" not in report
        assert "54321" not in report


@pytest.mark.parametrize(
    "table", ["register_company_list", "pub_register_company", "pub_register_snapshot"]
)
def test_identifier_allowed_in_each_key_only(tmp_path, frame, table):
    result = build(
        tmp_path,
        "public_only",
        frame,
        (capture(), capture("fc_register")),
        (capture(),),
    )
    tables = dict(result.tables)
    tables["register_company_list"] = [
        dict(
            registration_number="54321",
            period="2026-11",
            employee_count=3,
            suppression_reason_code=None,
        )
    ]
    validate_release(tables, frame)
    bad = {key: [dict(row) for row in rows] for key, rows in tables.items()}
    bad[table][0]["person_name"] = "SYN forbidden person"
    with pytest.raises(RegisterError, match=r"^release_schema$"):
        validate_release(bad, frame)


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("pub_place", "registration_number", "54321"),
        # Decision 0123: a withheld duplicate still meets an unkeyed row.
        ("pub_place", "name_en", "SYN copied 97003"),
        ("unknown_table", "name", "SYN anything"),
        ("pub_register_company", "name_en", "SYN-E-hidden"),
        ("pub_register_company", "name_en", "9" * 8),
        ("pub_register_company", "name_en", "9" * 11),
        ("pub_register_company", "registered_cell", 3),
        ("pub_register_company", "wage", 5),
        ("pub_register_company", "residence", "SYN invented address"),
    ],
)
def test_release_schema_and_identifier_egress_plants(
    tmp_path, frame, table, column, value
):
    result = build(
        tmp_path,
        "public_only",
        frame,
        (capture(), capture("fc_register")),
        (capture(),),
    )
    tables = {key: [dict(row) for row in rows] for key, rows in result.tables.items()}
    if table not in tables:
        tables[table] = [{column: value}]
    else:
        tables[table][0][column] = value
    reason = {
        ("pub_place", "registration_number"): "release_identifier_column",
        ("pub_place", "name_en"): "registration_egress",
        ("unknown_table", "name"): "release_table",
        ("pub_register_company", "name_en"): "identifier_prefix"
        if isinstance(value, str) and value.startswith("SYN-E-")
        else "identifier_digit_run",
        ("pub_register_company", "registered_cell"): "release_cell",
        ("pub_register_company", "wage"): "release_schema",
        ("pub_register_company", "residence"): "release_schema",
    }[table, column]
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        validate_release(tables, frame, withheld_registrations=frozenset({"97003"}))


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        pytest.param(["97003"], "registration_egress", id="key_in_list"),
        pytest.param({"k": "97003"}, "registration_egress", id="key_in_mapping"),
        pytest.param(b"97003", "registration_egress", id="key_as_bytes"),
        pytest.param({"97003": None}, "registration_egress", id="mapping_key"),
        pytest.param({"k": ([b"97003"],)}, "registration_egress", id="nested_bytes"),
        pytest.param(["SYN-E-7F3K2Q"], "identifier_prefix", id="prefix_in_list"),
        pytest.param(Decimal("1.5"), "artefact_type", id="decimal"),
        pytest.param(date(2026, 11, 1), "artefact_type", id="date"),
        pytest.param({"k": [Decimal("1.5")]}, "artefact_type", id="nested_decimal"),
        pytest.param(b"\xff", "artefact_encoding", id="invalid_bytes"),
    ],
)
def test_release_value_artefact_plants(tmp_path, frame, value, reason):
    """Decision 0123: a withheld key meets every unkeyed row and shape."""
    result = build(
        tmp_path, "public_only", frame, (capture(), capture("fc_register")), ()
    )
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        validate_release(
            {**result.tables, "source_registry": [{"value": value}]},
            frame,
            withheld_registrations=frozenset({"97003"}),
        )


@pytest.mark.parametrize(
    "value",
    [["54321"], {"k": "54321"}, b"54321", {"54321": None}, {"k": ([b"54321"],)}],
    ids=["key_in_list", "key_in_mapping", "key_as_bytes", "mapping_key", "nested"],
)
def test_release_value_released_key_publishes(tmp_path, frame, value):
    result = build(
        tmp_path, "public_only", frame, (capture(), capture("fc_register")), ()
    )
    tables = {**result.tables, "pub_place": [{"name_en": "SYN copied 54321"}]}
    validate_release({**tables, "source_registry": [{"value": value}]}, frame)


# Decision 0119 item 6: two named digest columns; `fact_lineage` has no
# `sha256` column, so a digest-shaped string there is scanned (see
# test_registers_digest_fields.py).
@pytest.mark.parametrize("table", ["source_registry", "pub_price_ext"])
@pytest.mark.parametrize(
    "digest",
    [
        pytest.param("a" * 28 + "1" * 8 + "b" * 28, id="eight_digit_run"),
        pytest.param("a" * 29 + "54321" + "b" * 30, id="registration_token"),
    ],
)
def test_release_value_sha256_exemption(tmp_path, frame, table, digest):
    assert len(digest) == 64
    result = build(
        tmp_path, "public_only", frame, (capture(), capture("fc_register")), ()
    )
    validate_release({**result.tables, table: [{"sha256": digest}]}, frame)


def test_release_value_nested_typed_public_values_pass(tmp_path, frame):
    result = build(
        tmp_path, "public_only", frame, (capture(), capture("fc_register")), ()
    )
    validate_release(
        {
            **result.tables,
            "source_registry": [
                {"value": {"k": [None, True, False, 54320, (10**7, 2.65431)]}}
            ],
        },
        frame,
    )


@pytest.mark.parametrize(
    "channel", ["log", "model_payload", "manifest", "report", "ledger", "web_bundle"]
)
def test_no_identifier_in_non_table_artefact(channel):
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_artefact({channel: "SYN copied 54321"}, frozenset({"54321"}))


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (b"SYN Invented Commerce", "register_content_egress"),
        ({"body": [b"SYN Invented Commerce"]}, "register_content_egress"),
        (b"\xff", "artefact_encoding"),
    ],
)
def test_content_bytes_are_decoded_or_refused(value, reason):
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        scan_content(value, frozenset({"SYN Invented Commerce"}))


def test_content_bytes_without_card_text_pass():
    scan_content(b"SYN unrelated metadata", frozenset({"SYN Invented Commerce"}))


def test_numeric_public_values_are_not_identifier_strings(tmp_path, frame):
    capital = 10**7
    item = capture(
        files=inputs(rows=[commerce(capital_qar=str(capital), lat="2.65431")])
    )
    result = build(tmp_path, "public_only", frame, (item, capture("fc_register")), ())
    card = result.tables["pub_register_company"][0]
    assert type(card["capital_qar"]) is int and card["capital_qar"] == capital
    assert type(card["lat"]) is float and card["lat"] == 2.65431
    assert type(card["lon"]) is float and card["lon"] == 1.25
    validate_release(
        {
            **result.tables,
            "pub_place": [{"count": 54320, "lat": 2.65431, "capital": capital}],
            "register_company_list": [
                dict(
                    registration_number="54321",
                    period="2026-11",
                    employee_count=65431,
                    suppression_reason_code=None,
                )
            ],
        },
        frame,
    )
    assert (
        list(
            read_parquet(
                (tmp_path / "current/tables/pub_register_company.parquet").read_bytes()
            )
        )
        == result.tables["pub_register_company"]
    )
    # The artefact contract is unchanged, including its numeric branch.
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_artefact({"count": 54321}, frozenset({"54321"}))


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("capital_qar", "3", "release_type"),
        ("capital_qar", True, "release_type"),
        ("capital_qar", -1, "integer_format"),
        ("capital_qar", 2**63, "integer_format"),
        ("lon", "1.25", "release_type"),
        ("lat", True, "release_type"),
        ("lat", float("nan"), "coordinate_format"),
        ("lon", float("inf"), "coordinate_format"),
        ("lat", 91.0, "coordinate_format"),
        ("lon", -181.0, "coordinate_format"),
    ],
)
def test_typed_numeric_card_loader_plants(frame, column, value, reason):
    cards = parse("biz_register", inputs(), frame)
    cards[0][column] = value
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        validate_release(
            {"pub_register_company": cards, "pub_register_snapshot": []}, frame
        )


def test_numeric_capital_storage_range_and_small_coordinate(frame):
    cards = parse(
        "biz_register",
        inputs(rows=[commerce(capital_qar=str(2**63 - 1), lat="0.0000000001")]),
        frame,
    )
    validate_release(
        {"pub_register_company": cards, "pub_register_snapshot": []}, frame
    )
    assert cards[0]["capital_qar"] == 2**63 - 1
    with pytest.raises(RegisterError, match=r"^integer_format$"):
        parse("biz_register", inputs(rows=[commerce(capital_qar=str(2**63))]), frame)


@pytest.mark.parametrize(
    ("source", "column", "value", "reason"),
    [
        # Decision 0123: an own licence refuses; another company's licence
        # and released keys publish (None).
        ("biz_register", "name_en", "97003", "registration_egress"),
        (
            "fc_register",
            "registered_address",
            "Office 97003, SYN tower",
            None,
        ),
        ("biz_register", "name_en", "65432", None),
        ("fc_register", "registered_address", "Office 54321, SYN tower", None),
        (
            "fc_register",
            "registered_address",
            "Office " + "9" * 8,
            "identifier_digit_run",
        ),
        (
            "fc_register",
            "registered_address",
            "Office " + "9" * 11,
            "identifier_digit_run",
        ),
    ],
)
def test_every_string_card_column_keeps_dat11_scan(
    tmp_path, frame, source, column, value, reason
):
    company, centre = capture(), capture("fc_register")
    if source == "biz_register":
        company = capture(files=inputs(rows=[commerce(**{column: value})]))
    else:
        centre = capture(
            "fc_register", files=inputs("fc_register", [fc(**{column: value})])
        )
    if reason is None:
        build(tmp_path, "public_only", frame, (company, centre), ())
        assert (tmp_path / "current" / "manifest.json").exists()
        return
    with pytest.raises(RegisterError, match="^" + reason + "$"):
        build(tmp_path, "public_only", frame, (company, centre), ())
    assert not (tmp_path / "current").exists()


@pytest.mark.parametrize("source", ["biz_register", "fc_register"])
def test_current_capture_can_predate_snapshot_keeper(tmp_path, frame, source):
    current = tuple(
        capture(name, "2026-10" if name == source else "2026-11")
        for name in ("biz_register", "fc_register")
    )
    result = build(tmp_path, "public_only", frame, current, ())
    assert len(result.tables["pub_register_company"]) == 2
    assert result.coverage == {"biz_register": (), "fc_register": ()}


@pytest.mark.parametrize("later_source", ["biz_register", "fc_register"])
@pytest.mark.parametrize("reverse", [False, True])
def test_snapshot_uses_own_sources_current_month(
    tmp_path, frame, later_source, reverse
):
    current = tuple(
        capture(name, "2026-12" if name == later_source else "2026-11")
        for name in ("biz_register", "fc_register")
    )
    if reverse:
        current = current[::-1]
    result = build(
        tmp_path / "valid",
        "public_only",
        frame,
        current,
        (capture(later_source, "2026-12"),),
    )
    assert result.coverage[later_source] == ("2026-12",)
    earlier_source = "fc_register" if later_source == "biz_register" else "biz_register"
    with pytest.raises(RegisterError, match=r"^snapshot_after_current$"):
        build(
            tmp_path / "invalid",
            "public_only",
            frame,
            current,
            (capture(earlier_source, "2026-12"),),
        )


@pytest.mark.parametrize("source", ["biz_register", "fc_register"])
def test_empty_snapshot_before_keeper_floor_refuses(tmp_path, frame, source):
    files = {role: csv_bytes(role, []) for role in inputs(source)}
    with pytest.raises(RegisterError, match=r"^snapshot_month$"):
        build(
            tmp_path,
            "public_only",
            frame,
            (capture(), capture("fc_register")),
            (capture(source, "2026-10", files),),
        )


def test_failures_and_repr_hide_source_values(tmp_path, frame, capsys):
    item = capture(
        files=inputs(rows=[commerce(registration_number="SYN private sentinel")])
    )
    with pytest.raises(RegisterError, match=r"^registration_format$") as caught:
        build(tmp_path, "public_only", frame, (item, capture("fc_register")), ())
    assert "sentinel" not in str(caught.value)
    assert "sentinel" not in repr(item)
    assert capsys.readouterr() == ("", "")
    assert not list(tmp_path.rglob("*.csv"))


def test_no_network_or_ambient_setting_read(tmp_path, frame, monkeypatch):
    monkeypatch.setattr(
        socket, "socket", lambda *a, **k: pytest.fail("network invocation")
    )
    monkeypatch.setenv("EII_REGISTER_FILE", "SYN forbidden ambient path")
    build(tmp_path, "public_only", frame, (capture(), capture("fc_register")), ())
    with pytest.raises(RegisterError, match=r"^register_setting_missing$"):
        from_environment({})


def test_registry_file_declarations_and_dispatch_are_closed():
    entries = load_registry()
    local = [entry for entry in entries if entry.kind == "register_file"]
    assert {entry.key for entry in local} == {"biz_register", "fc_register/file"}
    page = next(entry for entry in entries if entry.key == "fc_register")
    assert (
        page.kind == "public_page"
        and page.skip_reason == "fc_activation_review_pending"
    )
    for entry in local:
        assert not entry.nightly_live_fetch and not entry.commit_allowed
        assert (entry.url, entry.fetch_host, entry.landing_url) == ("", "", "")
        prepared = prepare(
            entry,
            lambda *a: pytest.fail("transport invoked"),
            lambda *a: pytest.fail("sleep invoked"),
        )
        assert prepared.failure.check == "lead_shell_file_input"
    # A shared source id never becomes enabled by whichever row appears last.
    assert nightly_blocked(
        (replace(page, nightly_live_fetch=True), *local), ("fc_register",)
    ) == ("fc_register",)


def test_stale_two_table_wording_is_gone():
    root = Path(__file__).resolve().parents[2]
    for file, requirement in [
        ("docs/03_DATA_CONTRACTS.md", "DAT-11"),
        ("docs/12_TESTING_AND_QUALITY.md", "TST-142"),
    ]:
        row = next(
            line
            for line in (root / file).read_text().splitlines()
            if line.startswith("| " + requirement + " |")
        )
        assert "`pub_register_snapshot`" in row
        assert "two key columns" not in row


@pytest.mark.parametrize("column", ["nationality_group", "nationality_group_ar"])
def test_input_only_nationality_is_header_checked_and_dropped(frame, column):
    from eii_custodian.publicdata.registers.parse import InputAudit, _rows

    assert (
        column
        not in _rows(inputs()["establishments"], "establishments", InputAudit())[0]
    )
    assert column not in parse("biz_register", inputs(), frame)[0]
    body = inputs()["establishments"].decode().splitlines()
    header = body[0].split(",")
    index = header.index(column)
    # Missing or renamed source headers must still refuse.
    for replacement in (None, "SYN_unconfirmed_column"):
        rows = [line.split(",") for line in body]
        for row in rows:
            if replacement is None:
                row.pop(index)
        if replacement is not None:
            rows[0][index] = replacement
        altered = ("\n".join(",".join(row) for row in rows) + "\n").encode()
        with pytest.raises(RegisterError, match=r"^input_schema$"):
            parse("biz_register", {"establishments": altered}, frame)


def test_capture_receipt_not_a_mapping_refused(tmp_path, frame):
    item = replace(capture(), receipt=5)
    with pytest.raises(RegisterError, match=r"^receipt_schema$"):
        build(
            tmp_path,
            "public_only",
            frame,
            (item, capture("fc_register")),
            (),
        )
    assert not (tmp_path / "current").exists()


def test_capture_receipt_missing_key_refused(tmp_path, frame):
    item = capture()
    side = {name: value for name, value in item.receipt.items() if name != "version"}
    with pytest.raises(RegisterError, match=r"^receipt_schema$"):
        build(
            tmp_path,
            "public_only",
            frame,
            (replace(item, receipt=side), capture("fc_register")),
            (),
        )
    assert not (tmp_path / "current").exists()
