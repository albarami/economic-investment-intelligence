"""Invented intake and proof links only; no workbook value from a source."""

import hashlib
from dataclasses import replace

import pytest

STAMP = "2024-02-03T00:00:00Z"
URL = "https://www.data.gov.qa/syn-proof/"


def profile():
    return {
        "format": "csv",
        "columns": ["syn_company", "syn_reg", "syn_value", "syn_date", "report_url"],
        "company": "syn_company",
        "registration": "syn_reg",
        "value": "syn_value",
        "date": "syn_date",
        "sheet": "",
        "types": ["string"] * 5,
    }


def row(index=0):
    return {
        "syn_company": "SYN Company",
        "syn_reg": "SYN-reg",
        "syn_value": "12.50",
        "syn_date": "03/02/2024",
        "report_url": URL + str(index),
    }


def test_awards_intake_dates_blanks(tmp_path):
    from eii_custodian.publicdata.fetch.awards import ingest_awards

    folder = tmp_path / "intake" / "awards_owner_scrape"
    folder.mkdir(parents=True)
    path = folder / "syn.csv"
    body = (
        ",".join(profile()["columns"])
        + "\nSYN Company,SYN-reg,12.50,03/02/2024,"
        + URL
        + "a\n"
        "SYN Other,SYN-other,,invalid,\nSYN Blank,SYN-blank,,,\n"
    ).encode()
    path.write_bytes(body)
    batch = ingest_awards(
        tmp_path, path, hashlib.sha256(body).hexdigest(), profile(), STAMP
    )
    assert batch.rows[0]["normalised_date"] == "2024-02-03"
    assert batch.rows[0]["normalised_date"] != "2024-03-02"
    assert batch.rows[1]["original"]["syn_value"] == ""
    assert batch.summary == {
        "row_count": 3,
        "dated_rows": 1,
        "unparsed_dates": 1,
        "blank_dates": 1,
        "date_first": "2024-02-03",
        "date_last": "2024-02-03",
        "completeness": "unknown",
    }
    assert batch.rows[0]["retrieved_utc"] == STAMP


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("escape", "intake_path_refused"),
        ("hash", "snapshot_hash_mismatch"),
        ("profile", "awards_profile_pending"),
        ("date", "snapshot_date_missing"),
    ],
)
def test_awards_intake_refusals(tmp_path, plant, reason):
    from eii_custodian.publicdata.fetch.awards import ingest_awards

    folder = tmp_path / "intake" / "awards_owner_scrape"
    folder.mkdir(parents=True)
    path = folder / "syn.csv"
    path.write_bytes(b"SYN-intake")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if plant == "escape":
        path = tmp_path / "syn.csv"
    with pytest.raises(ValueError, match=reason):
        ingest_awards(
            tmp_path,
            path,
            "SYN-wrong" if plant == "hash" else digest,
            "[LEAD: evidence 3]" if plant == "profile" else profile(),
            "" if plant == "date" else STAMP,
        )


@pytest.mark.parametrize("count", [0, 2, 30, 39])
def test_awards_seeded_proof_sample(count):
    from eii_custodian.publicdata.fetch.award_checks import check_awards

    rows = [row(index) for index in range(count)]
    rows += [dict(row(), report_url="")]
    if count:
        rows.append(row())
    calls = []
    by_url = {item["report_url"]: item for item in rows}

    def proof(url):
        calls.append(url)
        return by_url[url]

    result = check_awards(rows, profile(), 73, proof)
    selected = tuple(calls)
    assert len(calls) == min(count, 30) and len(set(calls)) == len(calls)
    assert result["distinct_frame_count"] == count
    assert result["selected_count"] == min(count, 30)
    assert result["incomplete"] == (count < 30)
    assert result["match_rate"] == ("1" if count else None)
    assert result["seed"] == 73
    calls.clear()
    assert check_awards(rows, profile(), 73, proof) == result
    assert tuple(calls) == selected


def test_awards_rate_mismatch_and_failed_fetch():
    from eii_custodian.publicdata.fetch.award_checks import check_awards

    rows = [row(i) for i in range(4)]

    def proof(url):
        index = int(url.rsplit("/", 1)[1])
        if index == 0:
            raise OSError("SYN-private-error")
        return dict(row(index), syn_value="13" if index == 1 else "12.50")

    result = check_awards(rows, profile(), 73, proof)
    assert result["matched"] == 2
    assert result["mismatched"] == 1
    assert result["failed_fetches"] == 1
    assert result["match_rate"] == "0.5"
    assert result["incomplete"] is True
    assert "SYN-private-error" not in str(result)


def test_awards_register_match():
    from eii_custodian.publicdata.fetch.award_checks import match_register

    rows = [
        row(),
        dict(row(), syn_company="SYN Companx"),
        dict(row(), syn_reg="SYN-absent"),
    ]
    matched = match_register(
        rows, profile(), [{"registration": "SYN-reg", "name": "  SYN company! "}]
    )
    assert matched["matched"] == 1 and matched["unmatched"] == 2
    assert len(matched["rows"]) == 3
    assert matched["rows"][1]["reason"] == "name_mismatch"
    assert matched["rows"][2]["reason"] == "registration_unmatched"


@pytest.mark.parametrize("plant", ["missing", "misplaced"])
def test_awards_check_registry_receipt(plant):
    from eii_custodian.publicdata.fetch.award_checks import validate_check_receipt

    receipt = {"source_id": "awards_owner_scrape"}
    if plant == "misplaced":
        receipt["summary"] = {"match_rate": "1"}
    with pytest.raises(ValueError, match="award_check_metadata_missing"):
        validate_check_receipt(receipt)


def test_awards_weekly_append(tmp_path):
    from eii_custodian.publicdata.fetch.award_checks import validate_check_receipt
    from eii_custodian.publicdata.fetch.awards import AwardBatch, publish_awards
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    entry = next(e for e in load_registry() if e.source_id == "awards_owner_scrape")
    body = b"SYN-intake"
    records = (
        {
            "original": row(),
            "normalised_date": "2024-02-03",
            "report_url": row()["report_url"],
            "retrieved_utc": STAMP,
        },
    )
    batch = AwardBatch(
        records,
        {"completeness": "unknown"},
        hashlib.sha256(body).hexdigest(),
        body,
        "csv",
    )
    first = publish_awards(
        entry, tmp_path, batch, profile(), STAMP, 73, lambda _: row(), []
    )
    validate_check_receipt(first.sidecar)
    other = replace(
        batch, body=b"SYN-second", sha256=hashlib.sha256(b"SYN-second").hexdigest()
    )
    second = publish_awards(
        entry,
        tmp_path,
        other,
        profile(),
        "2024-02-10T00:00:00Z",
        73,
        lambda _: row(),
        [],
    )
    assert first.sha256 != second.sha256
    assert read_snapshot(tmp_path / entry.key, first.sha256).body == first.body
    assert second.sidecar["award_check"]["seed"] == 73
    assert first.sidecar["original_scrape_date"] == "2026-11-03"


def test_workbook_profile_and_sparse_blanks(tmp_path):
    from zipfile import ZipFile

    from eii_custodian.publicdata.fetch.awards import ingest_awards

    folder = tmp_path / "intake" / "awards_owner_scrape"
    folder.mkdir(parents=True)
    path = folder / "syn.xlsx"
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    cols = profile()["columns"]

    def cells(values):
        return "".join(
            f'<c r="{chr(65 + i)}1" t="inlineStr"><is><t>{value}</t></is></c>'
            for i, value in enumerate(values)
        )

    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="SYN-sheet" r:id="syn"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="syn" Target="worksheets/syn.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/syn.xml",
            f'<worksheet xmlns="{ns}"><sheetData><row>{cells(cols)}</row><row>{cells(["SYN-company", "SYN-reg"])}</row></sheetData></worksheet>',
        )
    batch = ingest_awards(
        tmp_path,
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        dict(profile(), format="xlsx", sheet="SYN-sheet"),
        STAMP,
    )
    assert batch.rows[0]["original"]["syn_value"] == ""
    assert batch.summary["blank_dates"] == 1


def test_awards_normal_command_intake(tmp_path, monkeypatch):
    import json

    from commands import build_public
    from eii_custodian.publicdata.fetch import awards
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot
    from eii_custodian.publicdata.fetch.transport import Response

    entry = next(e for e in load_registry() if e.source_id == "awards_owner_scrape")
    schema = profile()
    columns = [[c, "string"] for c in schema["columns"]]
    link = row()["report_url"]
    entry = replace(entry, url=link, fetch_host="www.data.gov.qa", skip_reason="")
    declaration = {
        "url": link,
        "reviewed_urls": [link],
        "table_id": "syn",
        "columns": columns,
        "profile": schema,
    }
    monkeypatch.setattr(build_public, "load_registry", lambda: (entry,))
    monkeypatch.setattr(awards, "load_declaration", lambda source: declaration)
    cache = tmp_path / "data/public_cache"
    folder = cache / "intake/awards_owner_scrape"
    folder.mkdir(parents=True)
    body = (
        ",".join(schema["columns"])
        + "\n"
        + ",".join(row()[c] for c in schema["columns"])
        + "\n"
    ).encode()
    (folder / "syn.csv").write_bytes(body)
    (folder / "intake.json").write_text(
        json.dumps(
            {
                "file": "syn.csv",
                "sha256": hashlib.sha256(body).hexdigest(),
                "seed": 73,
                "register_selections": [],
            }
        )
    )
    proof = (
        '<table id="syn"><tr>'
        + "".join(f"<th>{c}</th>" for c in schema["columns"])
        + "</tr><tr>"
        + "".join(f"<td>{row()[c]}</td>" for c in schema["columns"])
        + "</tr></table>"
    ).encode()
    assert (
        build_public.run(
            tmp_path,
            {},
            [],
            transport=lambda url: Response(url, proof, ()),
            sleep=lambda _: None,
        )
        == 0
    )
    index = next((cache / entry.key / "index").glob("*.json"))
    result = read_snapshot(cache / entry.key, index.stem)
    assert result.sidecar["award_check"]["matched"] == 1
    assert result.sidecar["award_check"]["incomplete"] is True


def test_register_match_requires_archived_inputs(tmp_path):
    import json

    from eii_custodian.publicdata.fetch.awards import read_registers
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    body = json.dumps([{"syn_reg": "SYN-reg", "syn_name": "SYN Company"}]).encode()
    snapshot = publish_snapshot(
        tmp_path / "biz_register",
        "json",
        body,
        {
            "source_id": "biz_register",
            "key": "biz_register",
            "retrieved_utc": STAMP,
            "publisher": "SYN-publisher",
            "licence_basis": "owner_decision",
        },
    )
    selection = [
        {
            "key": "biz_register",
            "identity": snapshot.sha256,
            "format": "json_records",
            "registration_column": "syn_reg",
            "name_column": "syn_name",
        }
    ]
    rows, lineage = read_registers(tmp_path, selection)
    assert rows == [{"registration": "SYN-reg", "name": "SYN Company"}]
    assert lineage[0]["sha256"] == snapshot.sha256
    snapshot.path.write_bytes(b"SYN-tamper")
    with pytest.raises(ValueError, match="snapshot_hash_mismatch"):
        read_registers(tmp_path, selection)


def test_aggregate_profile_counts_never_replace_measured_counts(tmp_path):
    from eii_custodian.publicdata.fetch.awards import ingest_awards

    folder = tmp_path / "intake/awards_owner_scrape"
    folder.mkdir(parents=True)
    source = folder / "syn.csv"
    schema = dict(
        profile(),
        row_count=99,
        dated_rows=98,
        types=["string", "string", "number", "string", "string"],
    )
    body = (
        ",".join(schema["columns"])
        + "\n"
        + ",".join(row()[c] for c in schema["columns"])
        + "\n"
    ).encode()
    source.write_bytes(body)
    result = ingest_awards(
        tmp_path, source, hashlib.sha256(body).hexdigest(), schema, STAMP
    )
    assert result.summary["row_count"] == 1
    assert result.summary["dated_rows"] == 1
    assert result.rows[0]["original"]["syn_value"] == "12.50"
