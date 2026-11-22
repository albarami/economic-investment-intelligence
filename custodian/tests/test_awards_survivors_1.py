"""Invented award intake and immutable publication contract plants (S2-T29)."""

import csv
import io
import json
from dataclasses import replace

import pytest
from custodian.tests.test_s2_t29_awards import STAMP, profile, proof_row, row

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import AwardError
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot


@pytest.mark.parametrize("value", [None, [], "SYN other"])
def test_profile_top_level_reason(value):
    with pytest.raises(AwardError, match=r"^schema_missing$"):
        awards._profile(value)


@pytest.mark.parametrize(
    "plant",
    [
        "type_kind",
        "type_count",
        "type_container",
        "mapped_column",
        "report_url",
        "empty_column",
        "duplicate",
        "columns_type",
        "format",
        "extra",
        "missing",
        "numeric_column",
        "row_negative",
        "row_boolean",
        "date_negative",
    ],
)
def test_profile_independent_requirements(plant):
    schema = profile()
    if plant == "type_kind":
        schema["types"][0] = "SYN unknown"
    elif plant == "type_count":
        schema["types"].pop()
    elif plant == "type_container":
        schema["types"] = tuple(schema["types"])
    elif plant == "mapped_column":
        schema["company"] = "SYN missing"
    elif plant == "report_url":
        schema["columns"][-1] = "SYN proof"
    elif plant == "empty_column":
        schema["columns"].append("")
        schema["types"].append("string")
    elif plant == "duplicate":
        schema["columns"].append("report_url")
        schema["types"].append("string")
    elif plant == "columns_type":
        schema["columns"] = tuple(schema["columns"])
    elif plant == "format":
        schema["format"] = "SYN other"
    elif plant == "extra":
        schema["SYN extra"] = "SYN"
    elif plant == "missing":
        schema.pop("sheet")
    elif plant == "numeric_column":
        schema["columns"].append(7)
        schema["types"].append("string")
    elif plant == "row_negative":
        schema["row_count"] = -1
    elif plant == "row_boolean":
        schema["row_count"] = True
    else:
        schema["dated_rows"] = -1
    with pytest.raises(AwardError, match=r"^schema_missing$"):
        awards._profile(schema)


def test_profile_zero_counts_and_proof_mapping_allowed():
    schema = dict(
        profile(), row_count=0, dated_rows=0, proof_columns={"company": "SYN column"}
    )
    assert awards._profile(schema) == schema


def intake(tmp_path, body):
    folder = tmp_path / "intake" / awards.SOURCE
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SYN.csv"
    path.write_bytes(body)
    return path


def csv_body(records):
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=profile()["columns"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return text.getvalue().encode()


def test_xlsx_error_translation():
    with pytest.raises(AwardError, match=r"^schema_missing$"):
        awards._xlsx(b"SYN not OOXML", "SYN sheet")


@pytest.mark.parametrize("plant", ["file", "source", "intake"])
def test_symlink_intake_refused(tmp_path, plant):
    body = csv_body([row()])
    path = intake(tmp_path, body)
    original = {"file": path, "source": path.parent, "intake": path.parent.parent}[
        plant
    ]
    moved = original.with_name("SYN-moved")
    original.rename(moved)
    original.symlink_to(moved.name, target_is_directory=plant != "file")
    with pytest.raises(AwardError, match=r"^intake_path_refused$"):
        awards.ingest_awards(tmp_path, path, sha256_hex(body), profile(), STAMP)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("missing", "intake_missing"),
        ("hash", "snapshot_hash_mismatch"),
        ("decode", "schema_missing"),
        ("empty", "schema_missing"),
        ("header", "schema_missing"),
        ("short", "schema_missing"),
        ("long", "schema_missing"),
    ],
)
def test_intake_closed_refusals(tmp_path, plant, reason):
    body = csv_body([row()])
    if plant == "decode":
        body = b"\xff"
    elif plant == "empty":
        body = b""
    elif plant == "header":
        body = body.replace(b"syn_company", b"SYN wrong")
    elif plant in {"short", "long"}:
        body = (
            ",".join(profile()["columns"])
            + "\n"
            + ("SYN,\n" if plant == "short" else "SYN,SYN,SYN,SYN,SYN,SYN\n")
        ).encode()
    path = intake(tmp_path, body)
    if plant == "missing":
        path.unlink()
    with pytest.raises(AwardError, match=f"^{reason}$"):
        awards.ingest_awards(
            tmp_path,
            path,
            "SYN wrong" if plant == "hash" else sha256_hex(body),
            profile(),
            STAMP,
        )


def test_intake_counts_and_every_row_field(tmp_path):
    records = [
        dict(row(i), syn_date=date)
        for i, date in enumerate(
            ["", "  ", "bad", "31/02/2024", "04/02/2024", "03/02/2024"]
        )
    ]
    body = csv_body(records)
    path = intake(tmp_path, body)
    batch = awards.ingest_awards(tmp_path, path, sha256_hex(body), profile(), STAMP)
    dates = [None, None, None, None, "2024-02-04", "2024-02-03"]
    assert batch.rows == tuple(
        {
            "original": r,
            "parsed": dict(r, syn_date=None if r["syn_date"] == "" else r["syn_date"]),
            "normalised_date": date,
            "report_url": r["report_url"],
            "retrieved_utc": STAMP,
        }
        for r, date in zip(records, dates, strict=True)
    )
    assert batch.summary == {
        "row_count": 6,
        "dated_rows": 2,
        "unparsed_dates": 2,
        "blank_dates": 2,
        "date_first": "2024-02-03",
        "date_last": "2024-02-04",
        "completeness": "unknown",
        "stored_date_cells": 0,
        "unparsed_date_rows": [4, 5],
        "date_reading_assumption": "stored_day_month_swapped",
    }
    assert (batch.sha256, batch.body, batch.extension) == (
        sha256_hex(body),
        body,
        "csv",
    )


def batch():
    body = b"SYN immutable intake"
    return awards.AwardBatch(
        (
            {
                "original": row(),
                "parsed": row(),
                "normalised_date": "2024-02-03",
                "report_url": row()["report_url"],
                "retrieved_utc": STAMP,
            },
        ),
        {
            "date_first": "2024-02-03",
            "date_last": "2024-02-04",
            "row_count": 1,
            "completeness": "unknown",
        },
        sha256_hex(body),
        body,
        "csv",
    )


def award_entry():
    return next(e for e in load_registry() if e.source_id == awards.SOURCE)


@pytest.mark.parametrize("plant", ["source", "commit"])
def test_publish_entry_guards(tmp_path, plant):
    entry = replace(
        award_entry(),
        **{
            "source": {"source_id": "SYN other"},
            "commit": {"commit_allowed": True},
        }[plant],
    )
    with pytest.raises(AwardError, match=r"^receipt_missing$"):
        awards.publish_awards(
            entry, tmp_path, batch(), profile(), STAMP, 73, lambda _: proof_row(), []
        )


@pytest.mark.parametrize("value", ["", "pending"])
def test_publish_entry_pending_basis_is_published_as_written(tmp_path, value):
    """Ruling L-1001: a blank or pending basis of use is a record, never a
    refusal; the snapshot is published and the sidecar keeps the basis as
    written (ruling L-1025 item a)."""
    entry = replace(award_entry(), licence_basis=value)
    result = awards.publish_awards(
        entry,
        tmp_path,
        batch(),
        profile(),
        STAMP,
        73,
        lambda _: proof_row(),
        [{"registration": "SYN-reg", "name": "SYN Company"}],
    )
    assert result.sidecar["licence_basis"] == value


def test_publish_preserves_full_lineage_and_canonical_body(tmp_path):
    entry = award_entry()
    source = batch()
    inputs = [
        {
            "key": "biz_register",
            "identity": "SYN identity",
            "sha256": "SYN hash",
            "retrieved_utc": STAMP,
        }
    ]
    registers = [{"registration": "SYN-reg", "name": "SYN Company"}]
    result = awards.publish_awards(
        entry,
        tmp_path,
        source,
        profile(),
        STAMP,
        73,
        lambda _: proof_row(),
        registers,
        inputs,
    )
    raw = read_snapshot(tmp_path / entry.key / "raw", source.sha256)
    for snapshot in (raw, result):
        side = snapshot.sidecar
        for key, expected in {
            "fetch_url": entry.url,
            "fetch_host": entry.fetch_host,
            "publisher": entry.publisher,
            "source_modified": "2026-11-03",
            "row_count": 1,
            "terms_sha256": None,
            "as_of": "2024-02-03",
            "period_first": "2024-02-03",
            "period_last": "2024-02-04",
            "summary": source.summary,
            "method": "awards.ingest_awards@v2",
            "original_scrape_date": "2026-11-03",
            "registration_inputs": inputs,
            "registration_match": {
                "matched": 1,
                "unmatched": 0,
                "rows": [{"original": row(), "reason": "matched"}],
            },
        }.items():
            assert side[key] == expected, key
    expected = {
        "rows": source.rows,
        "as_of": "2024-02-03",
        "period_first": "2024-02-03",
        "period_last": "2024-02-04",
        "summary": source.summary,
        "raw_identity": raw.sha256,
        "source_sha256": source.sha256,
        "provenance": "Public",
        "method": "awards.ingest_awards@v2",
        "label": "owner scrape of public award reports, retrieved 2026-11-03",
    }
    assert result.body == json.dumps(expected, sort_keys=True).encode()
    assert result.sha256 == sha256_hex(result.body)


def test_invalid_workbook_closed_reason():
    with pytest.raises(AwardError, match=r"^schema_missing$"):
        awards._xlsx(b"SYN invalid workbook", "SYN sheet")
