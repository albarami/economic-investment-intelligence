"""Archive existing tender-reader output, without another fetch."""

import json
from pathlib import Path

import pytest
from custodian.tests.singles_entries import tender_entry

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_tenders import archive_pages
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.singles.tenders import (
    LIST_PATHS,
    ListReading,
    _write_pages,
)


def test_tender_archive_contains_every_list_language_and_named_page(
    tmp_path: Path,
) -> None:
    entry = tender_entry()
    stored = []
    readings = []
    for list_name, _ in LIST_PATHS:
        for language in ("en", "ar"):
            stored.append((list_name, language, 1, b"<html>SYN-page</html>"))
            readings.append(
                ListReading(
                    list_name,
                    language,
                    1,
                    1,
                    "2026-11-18T00:00:00Z",
                    "2026-11-18T00:00:00Z",
                )
            )
    _write_pages(tmp_path / entry.key, stored, readings)
    identity = archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")
    selected = read_snapshot(tmp_path / entry.key, identity)
    payload = json.loads(selected.body)
    assert payload["method"] == "assembly-tender-pages.v1"
    assert len(payload["pages"]) == len(LIST_PATHS) * 2
    assert {p["language"] for p in payload["pages"]} == {"en", "ar"}
    assert selected.sidecar["sha256"] == identity
    (tmp_path / entry.key / "available/en/1.html").unlink()
    # Already published immutable bytes remain readable; capture itself refuses
    # a missing file instead of substituting yesterday's assembled envelope.
    assert read_snapshot(tmp_path / entry.key, identity).sha256 == identity
    with pytest.raises(AssemblyError, match="assembly_tender_pages_incomplete"):
        archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")


@pytest.mark.parametrize("remaining", [0, 1])
def test_incremental_archive_verifies_the_stop_against_pages_and_workbook(
    tmp_path, monkeypatch, remaining
):
    from custodian.tests.test_awards_incremental import intake, pages, workbook
    from custodian.tests.test_tenders import _Fake, _run

    from eii_custodian.publicdata.fetch import awards
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    body = workbook()
    _, schema = intake(tmp_path, body)
    monkeypatch.setattr(awards, "load_declaration", lambda _: {"profile": schema})
    entry = tender_entry()
    fake = _Fake(pages([["04/02/2024"] * 20, *([["02/02/2024"]] if remaining else [])]))
    _run(
        fake,
        tmp_path,
        lists=("awarded",),
        award_cutoff="2024-02-04",
        workbook_sha256=sha256_hex(body),
        cache=tmp_path / entry.key,
    )
    for list_name, _ in LIST_PATHS:
        if list_name == "awarded":
            continue
        for language in ("en", "ar"):
            _write_pages(
                tmp_path / entry.key,
                [(list_name, language, 1, b"SYN")],
                [ListReading(list_name, language, 1, 1, "SYN", "SYN")],
            )
    identity = archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")
    result = read_snapshot(tmp_path / entry.key, identity)
    payload = json.loads(result.body)
    reading = next(r for r in payload["readings"] if r["list_name"] == "awarded")
    assert reading["stop_page"] == 1 and reading["pages_read"] == 1 + remaining
    assert reading["continuity_pages"] == remaining
    assert reading["last_page_read"] == reading["first_stated_last"] == 1 + remaining
    assert reading["award_cutoff"] == "2024-02-04"
    path = tmp_path / entry.key / "awarded/en.receipt.json"
    receipt = json.loads(path.read_bytes())
    receipt["award_cutoff"] = "2024-02-03"
    path.write_text(json.dumps(receipt))
    with pytest.raises(AssemblyError, match="assembly_tender_pages_incomplete"):
        archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize(
    "plant",
    [
        "clean",
        "newer_first_margin",
        "newer_second_margin",
        "order",
        "short_margin",
        "extra_margin",
        "wrong_last",
        "wrong_continuity",
        "wrong_stop",
        "missing_continuity",
        "missing_last",
        "missing_margin_page",
    ],
)
def test_archive_rechecks_continuity_pages_and_receipt(
    tmp_path, monkeypatch, language, plant
):
    from custodian.tests.test_awards_incremental import intake, pages, workbook
    from custodian.tests.test_tenders import _Fake, _run

    from eii_custodian.publicdata.fetch import awards
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    body = workbook()
    _, schema = intake(tmp_path, body)
    monkeypatch.setattr(awards, "load_declaration", lambda _: {"profile": schema})
    entry = tender_entry()
    date_pages = [
        ["04/02/2024"] * 20,
        ["03/02/2024"] * 20,
        ["02/02/2024"] * 20,
        ["01/02/2024"],
    ]
    _run(
        _Fake(pages(date_pages)),
        tmp_path,
        lists=("awarded",),
        award_cutoff="2024-02-04",
        workbook_sha256=sha256_hex(body),
        cache=tmp_path / entry.key,
    )
    for list_name, _ in LIST_PATHS:
        if list_name != "awarded":
            for lang in ("en", "ar"):
                _write_pages(
                    tmp_path / entry.key,
                    [(list_name, lang, 1, b"SYN")],
                    [ListReading(list_name, lang, 1, 1, "SYN", "SYN")],
                )
    prefix = tmp_path / entry.key / "awarded"
    path = prefix / (language + ".receipt.json")
    receipt = json.loads(path.read_bytes())
    if plant in {"newer_first_margin", "newer_second_margin", "order"}:
        number = 3 if plant == "newer_second_margin" else 2
        changed = [*date_pages]
        changed[number - 1] = (
            ["05/02/2024"] * 20
            if plant != "order"
            else ["02/02/2024", "03/02/2024"] + ["02/02/2024"] * 18
        )
        fixture = pages(changed)
        (prefix / language / f"{number}.html").write_bytes(
            fixture[
                (
                    "https://monaqasat.mof.gov.qa/TendersOnlineServices/AwardedTenders/"
                    + str(number),
                    language,
                )
            ]
        )
    elif plant in {"short_margin", "extra_margin"}:
        count = 2 if plant == "short_margin" else 4
        receipt.update(
            pages_read=count, last_page_read=count, continuity_pages=count - 1
        )
        if count == 4:
            fixture = pages(date_pages)
            (prefix / language / "4.html").write_bytes(
                fixture[
                    (
                        "https://monaqasat.mof.gov.qa/TendersOnlineServices/AwardedTenders/4",
                        language,
                    )
                ]
            )
    elif plant == "wrong_last":
        receipt["last_page_read"] = 2
    elif plant == "wrong_continuity":
        receipt["continuity_pages"] = 1
    elif plant == "wrong_stop":
        receipt["stop_page"] = 2
    elif plant == "missing_continuity":
        receipt.pop("continuity_pages", None)
    elif plant == "missing_last":
        receipt.pop("last_page_read", None)
    elif plant == "missing_margin_page":
        (prefix / language / "2.html").unlink(missing_ok=True)
    path.write_text(json.dumps(receipt))
    if plant != "clean":
        with pytest.raises(AssemblyError, match=r"^assembly_tender_pages_incomplete$"):
            archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")
        return
    identity = archive_pages(tmp_path, entry, "2026-11-18T00:00:00Z")
    payload = json.loads(read_snapshot(tmp_path / entry.key, identity).body)
    awarded = [r for r in payload["readings"] if r["list_name"] == "awarded"]
    assert len(awarded) == 2
    assert all(
        r["stop_page"] == 1
        and r["pages_read"] == 3
        and r["last_page_read"] == 3
        and r["continuity_pages"] == 2
        for r in awarded
    )
    assert {
        (p["language"], p["number"])
        for p in payload["pages"]
        if p["list_name"] == "awarded"
    } == {(lang, number) for lang in ("en", "ar") for number in (1, 2, 3)}
