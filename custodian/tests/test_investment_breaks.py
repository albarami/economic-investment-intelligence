"""One assertion for each condition the first suites left uncaught."""

from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.investment_build import (
    _PAGES as SPEC_PATH,
)
from eii_custodian.publicdata.investment_build import (
    _bounds,
    _fetch_page,
    _pages,
    _period_failure,
    _receipt,
    _spec_bounds,
    _string_list,
    _string_map,
    audit_snapshot,
    load_source_spec,
)
from eii_custodian.publicdata.investment_contracts import (
    PAGE_FIELDS,
    Bounds,
    DashboardShape,
    InvestmentFailure,
    KindRule,
    SourceEnvelope,
    lookup,
    parse_int,
    period_is_future,
    retrieval_year,
)
from eii_custodian.publicdata.investment_parse import (
    dashboard_envelope as with_method,
)
from eii_custodian.publicdata.investment_parse import (
    parse_fdi,
)

_FIXTURE_PATH = Path(__file__).with_name("investment_fixtures.py")
_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "investment_fixtures", _FIXTURE_PATH
)
assert _FIXTURE_SPEC is not None and _FIXTURE_SPEC.loader is not None
_fixtures = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(_fixtures)
DASHBOARD_URL = _fixtures.DASHBOARD_URL
TERMS_URL = _fixtures.TERMS_URL
dashboard_page = _fixtures.dashboard_page
invented_record = _fixtures.invented_record

RETRIEVED = "2026-11-14T08:00:00Z"


def test_unreadable_page_and_split_caveat_phrase() -> None:
    """A page that is not UTF-8 fails, and a phrase split by a tag is absent."""
    shape = _shape()
    refused = parse_fdi(b"\xff", shape, _fdi_envelope())
    assert isinstance(refused, InvestmentFailure)
    assert refused.check == "unreadable"
    nested = dashboard_page().replace(
        b"estimates of publicly announced projects",
        b"estimates of <span>publicly</span> announced projects",
    )
    marked = parse_fdi(nested, shape, _fdi_envelope())
    assert isinstance(marked, InvestmentFailure)
    assert marked.check == "missing_caveat"


def test_shape_and_capex_and_period_messages_name_the_value() -> None:
    """A wrong shape, a one-sided capex and a stated period keep their own values."""
    shape = _shape()
    assert isinstance(shape, DashboardShape)
    wrong = replace(shape, shape_id="fdi-other-v1")
    mismatch = parse_fdi(dashboard_page(), wrong, _fdi_envelope())
    assert isinstance(mismatch, InvestmentFailure)
    assert mismatch.observed == "fdi-other-v1"
    one_sided = dashboard_page((invented_record(capex=("n", "1"), capex_currency=""),))
    capex = parse_fdi(one_sided, shape, _fdi_envelope())
    assert isinstance(capex, InvestmentFailure)
    assert capex.check == "capex_currency"


def test_integer_lookup_and_period_edges() -> None:
    """Leading zeros, an empty crosswalk key and a future year each stay closed."""
    assert parse_int("0") == 0
    assert parse_int("00") is None
    assert lookup({"invented": "kept"}, "invented") == "kept"
    assert lookup({"": "hit"}, "") is None
    assert lookup({"invented": "kept"}, None) is None
    assert retrieval_year("202") is None
    assert retrieval_year(RETRIEVED) == 2026
    assert period_is_future("2027", RETRIEVED) is True
    assert period_is_future("abcd", RETRIEVED) is False
    assert period_is_future("2027", "bad") is False
    assert period_is_future("100", "0099-01-01") is False
    envelope = _fdi_envelope()
    assert replace(envelope, method="", method_version="1").missing() == "method"
    assert replace(envelope, method="named", method_version="").missing() == "method"


def test_spec_rejects_each_broken_bound_and_page_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-string page slot and each bound type refuse the specification."""
    document = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    missing = copy.deepcopy(document)
    del missing["sources"]["fdi_projects"]
    _point(monkeypatch, tmp_path, missing)
    refused = load_source_spec("fdi_projects", url=DASHBOARD_URL)
    assert isinstance(refused, InvestmentFailure)
    assert refused.check == "unconfirmed"
    rules = {
        kind: KindRule(kind, "block", {}, "", 2, 0, 0)
        for kind in ("sector", "opportunity", "incentive", "setup", "law")
    }
    pages = [
        {"kind": kind, "url": f"https://agency.invalid/{kind}"}
        for kind in ("sector", "opportunity", "incentive", "setup", "law")
    ]
    pages[0]["url"] = 1
    listed = _pages(pages, "https://agency.invalid/", rules)
    assert isinstance(listed, InvestmentFailure)
    assert listed.observed == "unreadable"
    pages[0]["url"] = "https://agency.invalid/sector"
    pages[0]["kind"] = 1
    shaped = _pages(pages, "https://agency.invalid/", rules)
    assert isinstance(shaped, InvestmentFailure)
    row = copy.deepcopy(document["sources"]["fdi_projects"])
    assert _string_list([*PAGE_FIELDS, 1]) is None
    row["mapping"] = {**row["mapping"], "company": "firm_name"}
    direct = _dashboard_from(tmp_path, row)
    assert isinstance(direct, InvestmentFailure)
    assert direct.check == "confirmation_fields"
    assert direct.expected == "mapped fields"
    row["mapping"] = document["sources"]["fdi_projects"]["mapping"]
    row["further_fields"] = ["company"]
    nullable = _dashboard_from(tmp_path, row)
    assert isinstance(nullable, InvestmentFailure)
    assert nullable.expected == "further fields"
    row["further_fields"] = document["sources"]["fdi_projects"]["further_fields"]
    row["cache_only"] = ["company"]
    cached = _dashboard_from(tmp_path, row)
    assert isinstance(cached, InvestmentFailure)
    assert cached.expected == "cache-only fields"
    bounds = copy.deepcopy(document["sources"]["fdi_projects"])
    for name, value in (
        ("row_count_min", True),
        ("row_count_max", True),
        ("row_count_min", "1"),
        ("row_count_max", "1"),
        ("period_field", 1),
        ("period_last", 1),
        ("confirmed", "yes"),
    ):
        planted = copy.deepcopy(bounds)
        planted[name] = value
        outcome = _spec_bounds(planted, "fdi_projects", DASHBOARD_URL)
        assert isinstance(outcome, InvestmentFailure)
        assert outcome.check == "unconfirmed"


def test_fetch_sidecar_and_entry_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fault, a sidecar and an entry bound each beat the fallback."""
    entry = next(item for item in load_registry() if item.source_id == "investqa_pages")
    fault = AttemptFailure(
        6,
        "https://evil.example/planted",
        "blocked_host",
        "allow-listed host",
        "https://evil.example/planted",
    )
    monkeypatch.setattr(
        "eii_custodian.publicdata.investment_build.read_bounded",
        lambda _transport, _sleep, _url: (
            Response("https://evil.example/planted", b"x", ()),
            fault,
        ),
    )
    fetched = _fetch_page(
        entry,
        tmp_path,
        fault.url,
        lambda _url: Response("", b"", ()),
        lambda _seconds: None,
        lambda: RETRIEVED,
        "terms",
    )
    assert isinstance(fetched, InvestmentFailure)
    assert fetched.code == 6
    assert fetched.check == "blocked_host"
    assert fetched.expected == "allow-listed host"
    assert fetched.observed == fault.url
    monkeypatch.setattr(
        "eii_custodian.publicdata.investment_build.read_bounded",
        lambda _transport, _sleep, url: (Response(url, b"invented page", ()), None),
    )
    stored = _fetch_page(
        entry,
        tmp_path,
        "https://agency.invalid/sectors/invented-textiles",
        lambda _url: Response("", b"", ()),
        lambda _seconds: None,
        lambda: RETRIEVED,
        "terms-hash",
    )
    assert not isinstance(stored, InvestmentFailure)
    digest = sha256_hex(b"invented page")
    side = tmp_path / entry.key / f"{digest}.meta.json"
    assert side.is_file()
    side.write_text(
        json.dumps({"retrieved_utc": 1, "terms_sha256": "terms-hash"}), encoding="utf-8"
    )
    again = _fetch_page(
        entry,
        tmp_path,
        "https://agency.invalid/sectors/invented-textiles",
        lambda _url: Response("", b"", ()),
        lambda _seconds: None,
        lambda: RETRIEVED,
        "terms-hash",
    )
    assert not isinstance(again, InvestmentFailure)
    assert again[1] == RETRIEVED
    empty_terms = tmp_path / entry.key / "empty-terms.meta.json"
    # _receipt keys the sidecar by the digest argument, not a fixed name.
    (tmp_path / entry.key / "blank.meta.json").write_text(
        json.dumps({"terms_sha256": "", "retrieved_utc": RETRIEVED}),
        encoding="utf-8",
    )
    terms = _receipt(tmp_path, entry.key, "blank", entry.source_id, entry.url)
    assert isinstance(terms, InvestmentFailure)
    assert terms.check == "missing_terms"
    (tmp_path / entry.key / "blank-time.meta.json").write_text(
        json.dumps({"terms_sha256": "terms-hash", "retrieved_utc": ""}),
        encoding="utf-8",
    )
    timed = _receipt(tmp_path, entry.key, "blank-time", entry.source_id, entry.url)
    assert isinstance(timed, InvestmentFailure)
    assert timed.check == "missing_lineage"
    del empty_terms
    spec = load_source_spec("fdi_projects", url=DASHBOARD_URL)
    assert not isinstance(spec, InvestmentFailure)
    fdi = next(item for item in load_registry() if item.source_id == "fdi_projects")
    chosen = _bounds(replace(fdi, row_count_min=2, row_count_max=9), spec)
    assert chosen.row_count_min == 2
    assert chosen.row_count_max == 9
    filled = _bounds(replace(fdi, period_field="", period_last=""), spec)
    assert filled.period_field == "announced"
    assert filled.period_last == "2026"
    skipped = _period_failure(
        ({"announced": None},),
        Bounds(1, 5, "announced", "", True),
        _fdi_envelope(),
    )
    assert skipped is None


def test_manifest_page_type_and_string_maps(tmp_path: Path) -> None:
    """A non-string page hash and a non-string crosswalk value are refused."""
    source = tmp_path / "fdi_projects"
    (source / "manifests").mkdir(parents=True)
    (source / "loadable.json").write_text(
        json.dumps({"manifest_sha256": "abc"}), encoding="utf-8"
    )
    (source / "manifests" / "abc.json").write_text(
        json.dumps(
            {"pages": [{"sha256": 1, "url": "https://agency.invalid/invented"}]}
        ),
        encoding="utf-8",
    )
    audited = audit_snapshot(tmp_path, "fdi_projects")
    assert isinstance(audited, InvestmentFailure)
    assert audited.observed == "unreadable"
    assert _string_map({"invented_textiles": "invented-key"}) == {
        "invented_textiles": "invented-key"
    }
    assert _string_map({"invented_textiles": 5}) == {}
    assert _string_map(["invented"]) == {}


def _dashboard_from(root: Path, row: dict[str, object]) -> InvestmentFailure | object:
    document = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    planted = copy.deepcopy(document)
    planted["sources"]["fdi_projects"] = row
    path = root / "pages.yaml"
    path.write_text(yaml.safe_dump(planted), encoding="utf-8")
    import eii_custodian.publicdata.investment_build as build

    original = build._PAGES
    build._PAGES = path
    try:
        return load_source_spec("fdi_projects", url=DASHBOARD_URL)
    finally:
        build._PAGES = original


def _point(monkeypatch: pytest.MonkeyPatch, root: Path, document: object) -> None:
    path = root / "pages.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    import eii_custodian.publicdata.investment_build as build

    monkeypatch.setattr(build, "_PAGES", path)


def _shape() -> object:
    spec = load_source_spec("fdi_projects", url=DASHBOARD_URL)
    assert not isinstance(spec, InvestmentFailure)
    assert spec.dashboard is not None
    return spec.dashboard


def _fdi_envelope() -> SourceEnvelope:
    bare = SourceEnvelope(
        source_id="fdi_projects",
        publisher="Invented publisher",
        page_url=DASHBOARD_URL,
        licence_id="invented-terms",
        licence_basis="terms",
        decision_record="0017",
        terms_sha256="abc",
        terms_url=TERMS_URL,
        retrieved_utc=RETRIEVED,
        page_sha256="def",
        method="",
        method_version="",
    )
    return with_method(bare)
