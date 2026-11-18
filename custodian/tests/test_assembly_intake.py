"""Invented local intake; profile evidence is never a released table."""

import hashlib
import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_intake import write_intake_evidence


def _input(cache: Path, *, digest: str | None = None) -> dict:
    folder = cache / "intake/awards_owner_scrape"
    folder.mkdir(parents=True)
    body = b"firm,registration,amount,date,report_url\nEXAMPLE-A,SYN-A,10,02/03/2026,https://example.invalid/a\nEXAMPLE-B,SYN-B,20,wrong,https://example.invalid/b\nEXAMPLE-C,SYN-C,30,,https://example.invalid/c\n"
    (folder / "invented.csv").write_bytes(body)
    manifest = {
        "file": "invented.csv",
        "sha256": digest or hashlib.sha256(body).hexdigest(),
        "seed": 17,
        "register_selections": {},
    }
    (folder / "intake.json").write_text(json.dumps(manifest))
    return {
        "sources": {
            "awards_owner_scrape": {
                "max_bytes": len(body),
                "profile": {
                    "format": "csv",
                    "columns": ["firm", "registration", "amount", "date", "report_url"],
                    "company": "firm",
                    "registration": "registration",
                    "value": "amount",
                    "date": "date",
                    "sheet": "",
                    "types": ["string", "string", "integer", "string", "string"],
                },
            }
        },
        "accident_spans": {2026: [10, 100]},
    }


def test_profile_records_counts_hash_mapping_seed_and_no_rows(tmp_path: Path) -> None:
    document = _input(tmp_path)
    result = write_intake_evidence(tmp_path, document, 17, "2026-11-18T00:00:00Z")
    assert set(result) == {"assembly/intake_evidence.json"}
    record = json.loads((tmp_path / "assembly/intake_evidence.json").read_text())
    awards = record["awards"]
    assert awards["state"] == "profiled"
    assert awards["summary"] == {
        "row_count": 3,
        "dated_rows": 1,
        "unparsed_dates": 1,
        "blank_dates": 1,
        "date_first": "2026-03-02",
        "date_last": "2026-03-02",
        "completeness": "unknown",
    }
    assert (
        awards["profile"]["columns"]
        == document["sources"]["awards_owner_scrape"]["profile"]["columns"]
    )
    assert awards["seed"] == 17
    assert (
        awards["sha256"]
        == json.loads(
            (tmp_path / "intake/awards_owner_scrape/intake.json").read_text()
        )["sha256"]
    )
    assert record["accident"] == {"state": "accepted", "spans": {"2026": [10, 100]}}
    assert "EXAMPLE-A" not in (tmp_path / "assembly/intake_evidence.json").read_text()
    assert not (tmp_path / "awards_owner_scrape").exists()


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("max_bytes", None, "acquisition_bound_unconfirmed"),
        ("profile", "pending", "awards_profile_pending"),
    ],
)
def test_pending_profile_or_bound_is_evidence_before_fetch(
    tmp_path: Path, field: str, value: object, reason: str
) -> None:
    document = _input(tmp_path)
    document["sources"]["awards_owner_scrape"][field] = value
    if field == "profile":
        document["sources"]["awards_owner_scrape"]["max_bytes"] = None
    write_intake_evidence(tmp_path, document, 17, "2026-11-18T00:00:00Z")
    record = json.loads((tmp_path / "assembly/intake_evidence.json").read_text())
    assert record["awards"] == {"state": "pending", "reason": reason}


@pytest.mark.parametrize("change", ["digest", "seed", "escape", "overbound"])
def test_intake_guards_refuse_without_publishing_profile(
    tmp_path: Path, change: str
) -> None:
    document = _input(tmp_path, digest="0" * 64 if change == "digest" else None)
    path = tmp_path / "intake/awards_owner_scrape/intake.json"
    manifest = json.loads(path.read_text())
    if change == "seed":
        manifest["seed"] = 18
    if change == "escape":
        manifest["file"] = "../invented.csv"
    if change == "overbound":
        document["sources"]["awards_owner_scrape"]["max_bytes"] = 1
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssemblyError):
        write_intake_evidence(tmp_path, document, 17, "2026-11-18T00:00:00Z")
    assert not (tmp_path / "assembly/intake_evidence.json").exists()


@pytest.mark.parametrize(
    "spans", ["pending", {}, {2026: [0, 1]}, {True: [1, 2]}, {2026: [2, 1]}]
)
def test_unaccepted_accident_spans_never_activate_release(
    tmp_path: Path, spans: object
) -> None:
    write_intake_evidence(
        tmp_path, {"sources": {}, "accident_spans": spans}, 17, "2026-11-18T00:00:00Z"
    )
    record = json.loads((tmp_path / "assembly/intake_evidence.json").read_text())
    assert record["accident"] == {
        "state": "pending",
        "reason": "partition_byte_bound_unconfirmed",
    }


def test_pending_mapping_can_still_profile_original_columns_and_lexical_types(
    tmp_path: Path,
) -> None:
    document = _input(tmp_path)
    document["sources"]["awards_owner_scrape"]["profile"] = "pending"
    write_intake_evidence(tmp_path, document, 17, "2026-11-18T00:00:00Z")
    record = json.loads((tmp_path / "assembly/intake_evidence.json").read_text())[
        "awards"
    ]
    assert record["state"] == "profiled"
    assert record["mapping_state"] == "pending"
    assert record["observed_profile"]["original_columns"] == [
        "firm",
        "registration",
        "amount",
        "date",
        "report_url",
    ]
    assert record["observed_profile"]["inferred_types"] == [
        "string",
        "string",
        "integer",
        "string",
        "string",
    ]
    assert record["summary"]["row_count"] == 3
    assert record["summary"]["dated_rows"] is None
    assert record["summary"]["date_mapping_state"] == "pending"
    assert "EXAMPLE-A" not in json.dumps(record)
