"""Remaining fetch seams: invented measures, periods, terms and tender calls."""

from dataclasses import replace
from datetime import UTC
from pathlib import Path

import pytest
from custodian.tests.test_fetch_kinds_survivors import wrong
from custodian.tests.test_fetch_kinds_survivors_2 import portal, refusal, transport
from custodian.tests.test_publicdata_behaviour import (
    FILE_URL,
    PORTAL,
    _entry,
    _ok,
    _portal_meta,
    _sleep,
)

from eii_custodian.publicdata.additions import property_venues
from eii_custodian.publicdata.fetch import kinds
from eii_custodian.publicdata.singles import tenders


@pytest.mark.parametrize(
    "rows", [["invented"], [{"SYN_VALUE": "unparsed"}], [{"SYN_VALUE": "1.5"}]]
)
def test_measure_refusal(rows, monkeypatch):
    monkeypatch.setattr(
        property_venues,
        "missing_forms_for",
        lambda key: ("SYN_VALUE", frozenset({"-"})),
    )
    result = kinds.prepare(
        portal(), transport(_portal_meta("Planted publisher"), rows), _sleep
    )
    refusal(result, PORTAL, "measure_unparsed", "SYN_VALUE", "measure_unparsed")


@pytest.mark.parametrize("rows", [[{"SYN_VALUE": "-"}], [{"SYN_VALUE": "2"}]])
def test_measure_accepts_reviewed_forms(rows, monkeypatch):
    monkeypatch.setattr(
        property_venues,
        "missing_forms_for",
        lambda key: ("SYN_VALUE", frozenset({"-"})),
    )
    assert (
        kinds.prepare(
            portal(), transport(_portal_meta("Planted publisher"), rows), _sleep
        ).failure
        is None
    )


@pytest.mark.parametrize(
    "source,rule,rows,expected",
    [
        ("trade_ext", "", [{}], ("", "", True, "")),
        (
            "invented",
            "sit=row;form=year_text;field=to_be_confirmed",
            [{}],
            ("", "", True, ""),
        ),
        (
            "invented",
            "sit=row;form=year_text;field=year",
            [{"year": "2021"}, {"year": "2019"}],
            ("2019", "2021", True, ""),
        ),
        (
            "trade_ext",
            "sit=row;form=year_text;field=year",
            [{"year": "2021"}, {"year": "2019"}],
            ("2019", "2021", True, ""),
        ),
        (
            "trade_ext",
            "sit=row;form=published_label;field=year",
            [],
            ("", "", True, "distinct labels 0"),
        ),
    ],
)
def test_observed_period_contract(source, rule, rows, expected):
    result = kinds.prepare(
        portal(source_id=source, period_field=rule),
        transport(_portal_meta("Planted publisher"), rows),
        _sleep,
    )
    assert result.failure is None
    assert (
        result.period_first,
        result.period_last,
        result.periods_observed,
        result.coverage_note,
    ) == expected


@pytest.mark.parametrize(
    "body,count", [(b'[{"invented": 2}]', 1), (b'{"results": [{"invented": 2}]}', 1)]
)
def test_json_file_record(body, count):
    row = replace(_entry(), row_count_min=1, row_count_max=1)
    result = kinds.prepare(row, lambda url: _ok(url, body), _sleep)
    assert result == kinds.Prepared(
        body,
        FILE_URL,
        "download.openstreetmap.fr",
        "Planted publisher",
        "",
        count,
        "",
        None,
    )


@pytest.mark.parametrize("failed", [False, True])
def test_terms_page_record(failed):
    row = replace(_entry(), kind="terms_page")
    from eii_custodian.publicdata.fetch.transport import TransportFault

    def read(url):
        if failed:
            raise TransportFault("blocked_host", url)
        return _ok(url, b"invented page")

    result = kinds.prepare(row, read, _sleep)
    if failed:
        refusal(result, FILE_URL, "blocked_host", "allow-listed host", FILE_URL)
    else:
        assert result == kinds.Prepared(
            b"invented page",
            FILE_URL,
            "download.openstreetmap.fr",
            "Planted publisher",
            "",
            None,
            "",
            None,
        )


@pytest.mark.parametrize(
    "route,stage",
    [
        ("portal_dataset", 0),
        ("portal_dataset", 1),
        ("https_file", 0),
        ("terms_page", 0),
        ("paged_layer", 0),
        ("paged_layer", 1),
        ("read_terms", 0),
    ],
)
def test_missing_response_seams(route, stage, monkeypatch):
    # _reader normally refuses a malformed transport result before _call returns;
    # inject the lower call seam to cover each explicit absent-response branch.
    row = replace(_entry(), kind=route, layer=0, terms_url=FILE_URL)
    calls = 0

    def call(entry, url, reader):
        nonlocal calls
        calls += 1
        if calls == stage + 1:
            return None, None
        return _ok(url, b'{"count": 1}'), None

    monkeypatch.setattr(kinds, "_call", call)
    if route == "read_terms":
        assert kinds.read_terms_page(
            row, lambda url: pytest.fail(url), _sleep
        ) == kinds.TermsPage("", None)
    else:
        refusal(
            kinds.prepare(row, lambda url: pytest.fail(url), _sleep),
            FILE_URL,
            "check_failed",
            "passed check",
            "check failed",
        )


def test_zero_attempt_setting_checks_missing_fault(monkeypatch):
    monkeypatch.setattr(kinds, "ATTEMPT_LIMIT", 0)
    with pytest.raises(AssertionError):
        kinds.read_bounded(lambda url: pytest.fail(url), _sleep, FILE_URL)


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("cached", [False, True])
def test_tender_handoff(fail, cached, tmp_path, monkeypatch):
    row = replace(
        _entry(),
        kind="paged_cards",
        fetch_host="invented.invalid",
        chain_intermediate_sha256="a" * 64,
    )
    chain = Path("invented-chain.pem")
    monkeypatch.setattr(tenders, "CHAIN_PATH", chain)
    seam = object()

    def https(entry, *, chain_file=None):
        assert entry is row
        # tender_https intentionally resolves None and an omitted argument to
        # CHAIN_PATH; the wrapper must preserve that effective value.
        assert (chain if chain_file is None else chain_file) == chain
        return seam

    calls = []

    def fetch(
        transport, *, chain_file, chain_sha256, sleep, clock, host="default", cache=None
    ):
        assert transport is seam
        assert chain_file == chain
        assert chain_sha256 == "a" * 64
        assert sleep is _sleep
        assert clock().tzinfo is UTC
        assert host == "invented.invalid"
        assert cache == (tmp_path / "planted" if cached else None)
        calls.append("called")
        if fail:
            raise tenders.TenderError("invented_refusal")
        return wrong(None)

    monkeypatch.setattr(tenders, "tender_https", https)
    monkeypatch.setattr(tenders, "fetch_tenders", fetch)
    result = kinds.prepare(
        row, lambda url: pytest.fail(url), _sleep, tmp_path if cached else None
    )
    assert calls == ["called"]
    if fail:
        refusal(
            result, FILE_URL, "invented_refusal", "invented_refusal", "invented_refusal"
        )
    else:
        assert result == kinds.Prepared(
            b"", FILE_URL, "invented.invalid", "Planted publisher", "", None, "", None
        )


@pytest.mark.parametrize(
    "meta,check,expected,observed",
    [
        (
            {"metas": {"default": {"publisher": 7}}},
            "publisher_missing",
            "Planted publisher",
            "",
        ),
        (
            _portal_meta("Planted publisher", licence="different"),
            "licence_mismatch",
            "text:invented-licence url:",
            "text:different url:https://creativecommons.org/licenses/by/4.0/",
        ),
    ],
)
def test_portal_metadata_coercion_and_other_licence(meta, check, expected, observed):
    result = kinds.prepare(
        portal(licence_id="invented-licence"), transport(meta, []), _sleep
    )
    refusal(
        result,
        "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/planted-slug",
        check,
        expected,
        observed,
    )


def test_other_licence_and_whitespace_publisher():
    row = portal(publisher="  Planted\tPublisher  ", licence_id="invented-licence")
    result = kinds.prepare(
        row,
        transport(_portal_meta("Planted Publisher", licence="invented-licence"), []),
        _sleep,
    )
    assert result.failure is None
    assert result.publisher == "Planted Publisher"


def test_portal_nontext_licence_and_modified():
    meta = {
        "metas": {
            "default": {"publisher": "Planted publisher", "license": 7, "modified": 3}
        }
    }
    result = kinds.prepare(
        portal(licence_basis="owner_decision"), transport(meta, []), _sleep
    )
    assert result.failure is None
    assert result.portal_licence == ""
    assert result.source_modified == ""
