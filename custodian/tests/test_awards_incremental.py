"""Invented workbook dates and newest-first tender pages; no live inputs."""

import io
import json
from datetime import date
from zipfile import ZipFile

import pytest
from custodian.tests.test_s2_t29_awards import STAMP, profile
from custodian.tests.test_tenders import (
    _AR_CARD,
    HOST,
    _awarded,
    _Fake,
    _list_card,
    _page,
    _run,
)

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.report import fail_line
from eii_custodian.publicdata.singles.tenders import TenderError


def workbook(*, iso=False):
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    header = "".join(
        f'<c r="{chr(65 + i)}1" t="inlineStr"><is><t>{c}</t></is></c>'
        for i, c in enumerate(profile()["columns"])
    )
    serial = (date(2024, 3, 2) - date(1899, 12, 30)).days
    stored = (
        '<c r="D2" t="d"><v>2024-03-02T00:00:00</v></c>'
        if iso
        else f'<c r="D2" s="1"><v>{serial}</v></c>'
    )
    stream = io.BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
            '<sheet name="SYN-sheet " r:id="syn"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="syn" Target="worksheets/syn.xml"/></Relationships>',
        )
        z.writestr(
            "xl/styles.xml",
            f'<styleSheet xmlns="{ns}"><cellXfs><xf numFmtId="0"/>'
            '<xf numFmtId="14"/></cellXfs></styleSheet>',
        )
        z.writestr(
            "xl/worksheets/syn.xml",
            f'<worksheet xmlns="{ns}"><sheetData><row r="1">{header}</row>'
            f'<row r="2">{stored}</row>'
            '<row r="3"><c r="D3" t="inlineStr"><is><t>31/02/2024</t></is></c></row>'
            '<row r="4"><c r="A4" t="inlineStr"><is><t>SYN blank</t></is></c></row>'
            '<row r="5"><c r="C5"><v>7.50</v></c><c r="D5" t="inlineStr">'
            "<is><t>04/02/2024</t></is></c></row></sheetData></worksheet>",
        )
    return stream.getvalue()


def intake(tmp_path, body, *, schema=None):
    folder = tmp_path / "intake/awards_owner_scrape"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SYN.xlsx"
    path.write_bytes(body)
    (folder / "intake.json").write_text(
        json.dumps(
            dict(
                file=path.name, sha256=sha256_hex(body), seed=73, register_selections=[]
            )
        )
    )
    return path, schema or dict(profile(), format="xlsx", sheet="SYN-sheet ")


@pytest.mark.parametrize("iso", [False, True])
def test_stored_date_is_swapped_and_bad_and_blank_dates_remain_visible(tmp_path, iso):
    body = workbook(iso=iso)
    path, schema = intake(tmp_path, body)
    result = awards.ingest_awards(tmp_path, path, sha256_hex(body), schema, STAMP)
    assert result.rows[0]["normalised_date"] == "2024-02-03"
    assert result.summary["stored_date_cells"] == 1
    assert result.summary["date_reading_assumption"] == "stored_day_month_swapped"
    assert result.summary["unparsed_dates"] == 1
    assert result.summary["unparsed_date_rows"] == [3]
    assert result.summary["blank_dates"] == 1
    assert result.rows[2]["normalised_date"] is None
    assert result.rows[0]["original"]["syn_value"] == ""
    assert result.rows[0]["parsed"]["syn_value"] is None
    assert result.rows[3]["original"]["syn_value"] == "7.50"
    assert result.summary["date_last"] == "2024-02-04"


def pages(date_pages, list_name="awarded"):
    from eii_custodian.publicdata.singles.tenders import LIST_PATHS

    path = "/TendersOnlineServices/" + dict(LIST_PATHS)[list_name]
    result = {}
    for language in ("en", "ar"):
        for number, dates in enumerate(date_pages, 1):
            cards = "".join(
                _awarded(
                    internal=number * 100 + i,
                    title="SYN tender",
                    award=when,
                    labels=_AR_CARD if language == "ar" else None,
                    notice="",
                )
                for i, when in enumerate(dates)
            )
            result[(HOST + path + "/" + str(number), language)] = _page(
                cards,
                lang=language,
                path=path,
                last_page=len(date_pages),
                current=number,
            ).encode()
    return result


@pytest.mark.parametrize(
    "date_pages,stop",
    [
        ([["03/02/2024"] * 20, ["02/02/2024"]], 1),
        ([["04/02/2024"] * 10 + ["03/02/2024"] * 10, ["02/02/2024"]], 2),
    ],
)
def test_cutoff_stop_page_and_mixed_page(tmp_path, date_pages, stop):
    fake = _Fake(pages(date_pages))
    result, _ = _run(
        fake,
        tmp_path,
        lists=("awarded",),
        award_cutoff="2024-02-03",
        cache=tmp_path / "pages",
    )
    last = min(stop + 2, len(date_pages))
    assert len(fake.calls) == last * 2
    for reading in result.readings:
        assert reading.pages_read == last
        assert reading.stop_page == stop
        assert reading.award_cutoff == "2024-02-03"
    receipt = json.loads((tmp_path / "pages/awarded/en.receipt.json").read_bytes())
    assert receipt["award_cutoff"] == "2024-02-03"
    assert receipt["pages_read"] == last and receipt["stop_page"] == stop


@pytest.mark.parametrize(
    "date_pages",
    [
        [["05/02/2024"] * 20, ["06/02/2024"]],
        [["05/02/2024"] * 19 + ["06/02/2024"], ["02/02/2024"]],
    ],
)
def test_newer_date_after_older_refuses(tmp_path, date_pages):
    fake = _Fake(pages(date_pages))
    with pytest.raises(TenderError, match=r"^award_order_invalid$"):
        _run(fake, tmp_path, lists=("awarded",), award_cutoff="2024-02-03")


def test_cutoff_comes_from_verified_intake_and_hash_refusal_is_recorded(
    tmp_path, monkeypatch
):
    body = workbook()
    path, schema = intake(tmp_path, body)
    monkeypatch.setattr(awards, "load_declaration", lambda _: {"profile": schema})
    result = awards.intake_cutoff(tmp_path, STAMP)
    assert result == ("2024-02-04", "", sha256_hex(body))
    path.write_bytes(b"SYN changed")
    assert awards.intake_cutoff(tmp_path, STAMP) == (
        None,
        "snapshot_hash_mismatch",
        None,
    )


def test_missing_intake_has_a_closed_reason(tmp_path):
    assert awards.intake_cutoff(tmp_path, STAMP) == (None, "intake_missing", None)


def test_refused_report_url_never_supplies_a_cutoff(tmp_path, monkeypatch):
    from dataclasses import replace

    body = workbook()
    path, schema = intake(tmp_path, body)
    original = awards.ingest_awards

    def ingested(*args, **kwargs):
        batch = original(*args, **kwargs)
        return replace(
            batch,
            rows=(dict(batch.rows[0], report_url="https://www.data.gov.qa/SYN-other"),),
        )

    monkeypatch.setattr(awards, "ingest_awards", ingested)
    monkeypatch.setattr(
        awards,
        "load_declaration",
        lambda _: {"profile": schema, "url": HOST, "reviewed_urls": []},
    )
    assert path.exists()
    assert awards.intake_cutoff(tmp_path, STAMP) == (None, "blocked_host", None)


def test_incremental_read_removes_stale_mutable_pages(tmp_path):
    cache = tmp_path / "pages"
    stale = cache / "awarded/en/4.html"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"SYN previous read")
    fake = _Fake(pages([["03/02/2024"] * 20, ["02/02/2024"]]))
    _run(fake, tmp_path, lists=("awarded",), award_cutoff="2024-02-03", cache=cache)
    assert not stale.exists()


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("extra", "intake_missing"),
        ("file_type", "intake_missing"),
        ("sha_type", "intake_missing"),
        ("seed", "award_seed_pending"),
        ("escape", "intake_path_refused"),
        ("bound", "metadata_bytes"),
    ],
)
def test_intake_manifest_and_byte_guards(tmp_path, plant, reason):
    from eii_custodian.publicdata.fetch.certificate_pins import PinError

    body = workbook()
    path, schema = intake(tmp_path, body)
    manifest_path = path.parent / "intake.json"
    manifest = json.loads(manifest_path.read_bytes())
    declaration = {"profile": schema}
    if plant == "extra":
        manifest["SYN-extra"] = "SYN"
    elif plant == "file_type":
        manifest["file"] = None
    elif plant == "sha_type":
        manifest["sha256"] = None
    elif plant == "seed":
        manifest["seed"] = True
    elif plant == "escape":
        manifest["file"] = "../SYN.xlsx"
    elif plant == "bound":
        declaration["max_bytes"] = len(body) - 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((awards.AwardError, PinError), match=f"^{reason}$"):
        awards.read_intake(tmp_path, declaration, STAMP)


def test_missing_award_date_cannot_establish_a_stop(tmp_path):
    fake = _Fake(pages([[""]]))
    with pytest.raises(TenderError, match=r"^award_date_missing$"):
        _run(fake, tmp_path, lists=("awarded",), award_cutoff="2024-02-03")


@pytest.mark.parametrize("cutoff", ["SYN-invalid", "2024-2-03"])
def test_invalid_cutoff_refuses_before_request(tmp_path, cutoff):
    with pytest.raises(TenderError, match=r"^award_cutoff_invalid$"):
        _run(
            lambda _: pytest.fail("invalid cut-off requested transport"),
            tmp_path,
            lists=("awarded",),
            award_cutoff=cutoff,
        )


@pytest.mark.parametrize("serial", ["-1", "NaN", "Infinity", "60", "999999999999"])
def test_invalid_spreadsheet_date_storage_refuses(serial):
    from eii_custodian.publicdata.fetch.page_workbook import _serial_date

    with pytest.raises(ValueError, match=r"^schema_missing$"):
        _serial_date(serial, False)


def test_spreadsheet_epochs_and_fractional_times_do_not_change_the_date():
    from eii_custodian.publicdata.fetch.page_workbook import _serial_date

    assert _serial_date("1.5", False) == "1900-01-01"
    assert _serial_date("61", False) == "1900-03-01"
    assert _serial_date("0.5", True) == "1904-01-01"


def test_closed_failure_has_no_fabricated_comparison():
    assert fail_line("tenders_pub", HOST, "company_size awarded", "", "") == (
        "FAIL tenders_pub " + HOST + " company_size awarded"
    )


@pytest.mark.parametrize(
    "plant", ["valid", "pem_hash", "der_hash", "review", "other_host", "other_source"]
)
def test_shared_tender_chain_keeps_both_pins_and_host_review(
    tmp_path, monkeypatch, plant
):
    import ssl
    from dataclasses import replace

    from custodian.tests.test_tenders import _chain

    from eii_custodian.publicdata.fetch.certificate_pins import (
        PinError,
        load_pin,
        verified_context,
    )
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.singles import tenders

    chain, digest = _chain(tmp_path)
    der = ssl.PEM_cert_to_DER_cert(chain.read_text())
    entry = next(e for e in load_registry() if e.source_id == "tenders_pub")
    monkeypatch.setattr(tenders, "CHAIN_PATH", chain)
    from eii_custodian.publicdata.fetch import registry

    monkeypatch.setattr(
        registry,
        "load_registry",
        lambda: (replace(entry, chain_intermediate_sha256=digest),),
    )
    config = dict(
        host=tenders.TENDER_HOST,
        sha256=sha256_hex(der),
        file="tenders_pub.intermediate.pem",
        security_review="APPROVED",
    )
    reason = "certificate_chain_incomplete"
    if plant == "pem_hash":
        chain.write_text(chain.read_text() + "\n")
    elif plant == "der_hash":
        config["sha256"] = "0" * 64
    elif plant == "review":
        config["security_review"] = "PENDING"
        reason = "certificate_review_pending"
    elif plant == "other_host":
        config["host"] = "www.edu.gov.qa"
        reason = "certificate_host_mismatch"
    if plant == "valid":
        pin = load_pin(tmp_path, awards.SOURCE, config)
        assert pin.der == der and pin.host == tenders.TENDER_HOST
        context = verified_context(pin.host, pin)
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
        assert context.get_ciphers()[-1]["name"] == tenders.TENDER_SUITE
    else:
        with pytest.raises(PinError, match=f"^{reason}$"):
            load_pin(
                tmp_path,
                "SYN-other" if plant == "other_source" else awards.SOURCE,
                config,
            )


@pytest.mark.parametrize("plant", ["valid", "host", "path", "query", "fragment"])
def test_only_intake_delivered_award_report_urls_extend_scope(plant):
    link = HOST + "/TendersOnlineServices/TenderCompaniesDetails/SYN-report"
    if plant == "host":
        link = link.replace("monaqasat.mof.gov.qa", "www.data.gov.qa")
    elif plant == "path":
        link = HOST + "/TendersOnlineServices/TenderDetails/SYN-report"
    elif plant == "query":
        link += "?SYN=other"
    elif plant == "fragment":
        link += "#SYN"
    batch = awards.AwardBatch((dict(report_url=link),), {}, "SYN", b"", "xlsx")
    dec = dict(profile=dict(format="xlsx"), reviewed_urls=[])
    if plant == "valid":
        assert awards._proof_urls(batch, dec, "monaqasat.mof.gov.qa") == (link,)
    else:
        with pytest.raises(awards.AwardError, match=r"^blocked_host$"):
            awards._proof_urls(batch, dec, "monaqasat.mof.gov.qa")


@pytest.mark.parametrize(
    "list_name",
    ["available", "closed", "technically_opened", "financially_opened", "cancelled"],
)
def test_cutoff_never_shortens_other_five_lists(tmp_path, list_name):
    from eii_custodian.publicdata.singles.tenders import LIST_PATHS

    path = "/TendersOnlineServices/" + dict(LIST_PATHS)[list_name]
    fixture = {}
    for language in ("en", "ar"):
        for number, count in ((1, 20), (2, 1)):
            cards = "".join(
                _list_card(list_name, language, number * 100 + i) for i in range(count)
            )
            fixture[(HOST + path + "/" + str(number), language)] = _page(
                cards, lang=language, path=path, last_page=2, current=number
            ).encode()
    fake = _Fake(fixture)
    result, _ = _run(fake, tmp_path, lists=(list_name,), award_cutoff="2024-02-03")
    assert len(fake.calls) == 4
    assert all(
        r.pages_read == 2 and r.stop_page is None and r.award_cutoff is None
        for r in result.readings
    )


def test_missing_intake_keeps_full_awarded_fetch_and_records_reason(tmp_path):
    cutoff, reason, digest = awards.intake_cutoff(tmp_path, STAMP)
    fake = _Fake(pages([["02/02/2024"] * 20, ["01/02/2024"]]))
    result, _ = _run(
        fake,
        tmp_path,
        lists=("awarded",),
        award_cutoff=cutoff,
        cutoff_reason=reason,
        workbook_sha256=digest,
    )
    assert len(fake.calls) == 4
    assert all(
        r.pages_read == 2
        and r.stop_page is None
        and r.cutoff_reason == "intake_missing"
        for r in result.readings
    )


def test_intake_refusal_does_not_prevent_fetch_but_still_refuses_assembly(
    tmp_path, monkeypatch
):
    from custodian.tests.test_production_adapters import context

    from eii_custodian.publicdata import assembly_adapters
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.fetch.build import BuildOutcome
    from eii_custodian.publicdata.fetch.registry import load_registry

    entry = next(e for e in load_registry() if e.source_id == awards.SOURCE)
    build = context(tmp_path, (entry,))
    monkeypatch.setattr(
        assembly_adapters,
        "read_yaml",
        lambda _: {
            "sources": {
                "awards_owner_scrape": {"max_bytes": 4096, "profile": profile()}
            }
        },
    )
    calls = []
    build.fetcher = lambda: calls.append("fetch") or BuildOutcome((), None)
    output = build.intake_evidence()
    assert "assembly/intake_evidence.json" in output
    evidence = json.loads((tmp_path / "assembly/intake_evidence.json").read_bytes())
    assert evidence["awards"] == {
        "state": "refused",
        "reason": "assembly_input_refused",
    }
    with pytest.raises(AssemblyError, match=r"^assembly_input_refused$"):
        build.fetch_archive()
    assert calls == ["fetch"]


def test_activated_workbook_profile_reaches_proof_and_normal_tender_dispatch(
    tmp_path, monkeypatch
):
    from custodian.tests.test_s2_t29_live_awards import report
    from custodian.tests.test_s2_t29_transport import pin

    from eii_custodian.publicdata.fetch import kinds, page_requests
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.singles import tenders

    dec = awards.load_declaration(awards.SOURCE)
    schema = dec["profile"]
    rows = {
        e.source_id: e
        for e in load_registry()
        if e.source_id in {awards.SOURCE, "tenders_pub"}
    }
    link = HOST + "/TendersOnlineServices/TenderCompaniesDetails/SYN-proof"
    values = {
        "award_date": "03/02/2024",
        "report_url": link,
        "Company name": "SYN Company",
        "Commercial Registration Number": "SYN-reg",
        "Approved Value": "12.50",
        "Approved Value Number": "12.5",
    }
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    stream = io.BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="Awarded Contracts " r:id="syn"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="syn" Target="worksheets/syn.xml"/></Relationships>',
        )
        xml_rows = []
        for number, cells in (
            (1, schema["columns"]),
            (2, [values.get(c, "") for c in schema["columns"]]),
        ):
            # the real sheet stores 'Approved Value Number' (H) as formula cells
            # with cached values; every other cell is plain text
            cells_xml = "".join(
                f'<c r="H{number}"><f>VALUE(G{number})</f><v>{value}</v></c>'
                if number > 1 and column == "Approved Value Number"
                else f'<c r="{chr(65 + i)}{number}" t="inlineStr"><is><t>{value}</t></is></c>'
                for i, (column, value) in enumerate(
                    zip(schema["columns"], cells, strict=True)
                )
            )
            xml_rows.append(f'<row r="{number}">{cells_xml}</row>')
        z.writestr(
            "xl/worksheets/syn.xml",
            f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>',
        )
    body = stream.getvalue()
    with ZipFile(io.BytesIO(body)) as z:
        assert b"<f>VALUE(G2)</f><v>12.5</v>" in z.read("xl/worksheets/syn.xml")
    intake(tmp_path, body)
    proof_dec, proof_body = report()
    for old, new in zip(
        proof_dec["shape"]["headers"], dec["shape"]["headers"], strict=True
    ):
        proof_body = proof_body.replace(old.encode(), new.encode())
    proof_body = proof_body.replace(b"SYN first", b"SYN Company").replace(
        b"1,007.00", b"12.50"
    )
    monkeypatch.setattr(awards, "load_pin", lambda *args: pin())
    calls = []

    def send(url):
        page_requests.check_target(url)
        calls.append(url)
        return Response(url, proof_body, ())

    result = awards.fetch_awards(
        rows[awards.SOURCE], send, tmp_path, lambda: STAMP, lambda _: None
    )
    assert calls == [link]
    assert result.sidecar["award_check"]["matched"] == 1
    assert result.sidecar["summary"]["row_count"] == 1
    assert result.sidecar["summary"]["date_last"] == "2024-02-03"
    assert json.loads(result.body)["rows"][0]["original"] == {
        c: values.get(c, "") for c in schema["columns"]
    }
    seen = []
    monkeypatch.setattr(tenders, "tender_https", lambda *args, **kwargs: send)

    def fetch(*args, **kwargs):
        seen.append(kwargs)

    monkeypatch.setattr(tenders, "fetch_tenders", fetch)
    assert (
        kinds.prepare(rows["tenders_pub"], send, lambda _: None, cache=tmp_path).failure
        is None
    )
    assert seen[0]["award_cutoff"] == "2024-02-03"
    assert seen[0]["workbook_sha256"] == sha256_hex(body)
    assert seen[0]["cutoff_reason"] == ""


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("margin", [1, 2])
def test_newer_award_after_wholly_covered_page_refuses(tmp_path, language, margin):
    date_pages = [["03/02/2024"] * 20, ["02/02/2024"] * 20, ["01/02/2024"]]
    fixture = pages(date_pages)
    date_pages[margin] = ["01/02/2024", "04/02/2024"] + ["01/02/2024"] * (
        18 if margin == 1 else 0
    )
    planted = pages(date_pages)
    fixture.update({key: value for key, value in planted.items() if key[1] == language})
    fake = _Fake(fixture)
    with pytest.raises(TenderError, match=r"^award_after_stop$"):
        _run(fake, tmp_path, lists=("awarded",), award_cutoff="2024-02-03")
    assert any(call.url.endswith("/" + str(1 + margin)) for call in fake.calls)


@pytest.mark.parametrize("stop", [1, 2])
@pytest.mark.parametrize("margin", [0, 1, 2, 3])
def test_continuity_margin_is_exact_and_records_early_list_end(tmp_path, stop, margin):
    date_pages = [["04/02/2024"] * 10 + ["03/02/2024"] * 10] if stop == 2 else []
    date_pages += [["03/02/2024"] * 20]
    date_pages += [
        [f"{2 if number == 0 else 1:02}/02/2024"] * 20 for number in range(margin)
    ]
    date_pages[-1] = date_pages[-1][:1]
    fake = _Fake(pages(date_pages))
    cache = tmp_path / "pages"
    result, _ = _run(
        fake, tmp_path, lists=("awarded",), award_cutoff="2024-02-03", cache=cache
    )
    expected_margin = min(margin, 2)
    last = stop + expected_margin
    assert len(fake.calls) == last * 2
    for reading in result.readings:
        assert reading.stop_page == stop
        assert reading.pages_read == last
        assert reading.last_page_read == last
        assert reading.continuity_pages == expected_margin
        receipt = json.loads(
            (cache / "awarded" / (reading.language + ".receipt.json")).read_bytes()
        )
        assert receipt["stop_page"] == stop
        assert receipt["pages_read"] == last
        assert receipt["last_page_read"] == last
        assert receipt["continuity_pages"] == expected_margin
        assert receipt["first_stated_last"] == stop + margin
        assert (reading.last_page_read == reading.first_stated_last) == (margin <= 2)


@pytest.mark.parametrize("margin", [1, 2])
def test_order_check_still_applies_below_cutoff_on_margin_pages(tmp_path, margin):
    date_pages = [["03/02/2024"] * 20, ["01/02/2024"] * 20, ["01/02/2024"]]
    date_pages[margin] = ["02/02/2024", "03/02/2024"] + ["01/02/2024"] * (
        18 if margin == 1 else 0
    )
    with pytest.raises(TenderError, match=r"^award_order_invalid$"):
        _run(
            _Fake(pages(date_pages)),
            tmp_path,
            lists=("awarded",),
            award_cutoff="2024-02-03",
        )


@pytest.mark.parametrize(
    "expected,observed", [("", ""), ("SYN expected", "SYN observed")]
)
def test_failure_without_address_has_single_spacing(expected, observed):
    suffix = f" expected={expected} observed={observed}" if expected else ""
    assert fail_line(
        "awards_owner_scrape", "", "intake_missing", expected, observed
    ) == ("FAIL awards_owner_scrape intake_missing" + suffix)
