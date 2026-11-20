"""The reviewed Arabic page list and the shared kind rules on invented pages.

OI-181 offline part: the inventory's ``ar`` entries mirror the confirmed
``en`` list through the site's own language path segment, each language
covers every page family, and the same kind rules parse and refuse the
invented Arabic pages of the same shape. The live comparison through the
normal seam is the lead's later run: every ``language_confirmation.ar``
flag stands false until it.
"""

from __future__ import annotations

import copy
import importlib.util
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.registry import read_yaml
from eii_custodian.publicdata.gate_report import INVESTMENT_FLAGS, investment_evidence
from eii_custodian.publicdata.investment_build import (
    PageSpec,
    SourceSpec,
    _pages,
    load_source_spec,
    require_page_families,
)
from eii_custodian.publicdata.investment_contracts import (
    InvestmentFailure,
    SourceEnvelope,
)
from eii_custodian.publicdata.investment_parse import agency_envelope, parse_agency

_FIXTURE_PATH = Path(__file__).with_name("investment_fixtures.py")
_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "investment_fixtures", _FIXTURE_PATH
)
assert _FIXTURE_SPEC is not None and _FIXTURE_SPEC.loader is not None
_fixtures = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(_fixtures)
LANDING_URL = _fixtures.LANDING_URL
SECTOR_URL = _fixtures.SECTOR_URL
OPPORTUNITY_URL = _fixtures.OPPORTUNITY_URL
INCENTIVE_URL = _fixtures.INCENTIVE_URL
SETUP_URL = _fixtures.SETUP_URL
LAW_URL = _fixtures.LAW_URL
agency_plant = _fixtures.agency_plant
incentive_page = _fixtures.incentive_page
law_page = _fixtures.law_page
opportunity_page = _fixtures.opportunity_page
sector_page = _fixtures.sector_page
setup_page = _fixtures.setup_page

RETRIEVED = "2026-11-14T08:00:00Z"
KIND_PAGES = (
    ("sector", sector_page, SECTOR_URL, ["sector"] + ["sector_block"] * 4),
    (
        "opportunity",
        opportunity_page,
        OPPORTUNITY_URL,
        ["opportunity", "block"] + ["opportunity"] * 5,
    ),
    (
        "incentive",
        incentive_page,
        INCENTIVE_URL,
        ["incentive"] + ["incentive_parameter"] * 4 + ["setup_step"],
    ),
    ("setup", setup_page, SETUP_URL, ["setup"] + ["setup_step"] * 6),
    ("law", law_page, LAW_URL, ["law", "law_block"]),
)


def _spec() -> SourceSpec:
    spec = load_source_spec("investqa_pages", url=LANDING_URL)
    assert not isinstance(spec, InvestmentFailure)
    return spec


def _arabic(body: bytes) -> bytes:
    """The same invented page in Arabic: the lang mark and invented text."""
    # INVENTED: every heading and text node is an invented token, never page data.
    return body.replace(b'<html lang="en">', b'<html lang="ar">').replace(
        b"Invented", "مخترع".encode()
    )


def _arabic_url(url: str) -> str:
    return url.replace("agency.invalid/", "agency.invalid/ar/")


def _envelope(url: str) -> SourceEnvelope:
    return agency_envelope(
        SourceEnvelope(
            source_id="investqa_pages",
            publisher="National investment promotion agency",
            page_url=url,
            licence_id="publisher-terms",
            licence_basis="owner_decision",
            decision_record="0017",
            terms_sha256="ab" * 32,
            terms_url="https://terms.invalid/terms",
            retrieved_utc=RETRIEVED,
            page_sha256="cd" * 32,
            method="",
            method_version="",
        )
    )


def test_arabic_list_mirrors_the_confirmed_english_pages() -> None:
    """Every English page has one Arabic twin by the language segment, and no more."""
    spec = _spec()
    english = [page for page in spec.pages if page.language == "en"]
    arabic = [page for page in spec.pages if page.language == "ar"]
    assert english
    assert len(arabic) == len(english)
    by_url: dict[str, PageSpec] = {}
    for page in arabic:
        assert "/ar/" in page.url
        assert page.url not in by_url
        by_url[page.url] = page
    for page in english:
        twin_url = page.url.replace("/en/", "/ar/", 1)
        assert twin_url != page.url
        twin = by_url.pop(twin_url, None)
        assert twin is not None, page.url
        assert twin.kind == page.kind
        assert twin.minimum_blocks == page.minimum_blocks
        assert twin.minimum_paragraphs == page.minimum_paragraphs
    assert by_url == {}


@pytest.mark.parametrize("language", ["en", "ar"])
def test_each_language_covers_every_page_family(language: str) -> None:
    """The publish rule of one page of each family holds per language."""
    spec = _spec()
    kinds = tuple(page.kind for page in spec.pages if page.language == language)
    assert require_page_families(kinds, _envelope(LANDING_URL)) is None


def test_arabic_evidence_flags_stay_pending_until_the_live_read() -> None:
    """The live comparison is the lead's later run; no flag is ticked offline."""
    root = repository_root(Path(__file__))
    document = read_yaml(root / "custodian" / "publicdata" / "investment_pages.yaml")
    agency = document["sources"]["investqa_pages"]
    arabic = agency["language_confirmation"]["ar"]
    for flag in INVESTMENT_FLAGS:
        assert arabic[flag] is False
    assert arabic["read_on"] is None
    assert arabic["reference"] is None
    result = investment_evidence(document, "invented-review")
    assert result.checks["investqa_pages:arabic_evidence"] is False


@pytest.mark.parametrize(
    ("kind", "page", "url", "expected"), KIND_PAGES, ids=[row[0] for row in KIND_PAGES]
)
def test_each_kind_rule_parses_the_arabic_page(
    kind: str, page: Callable[[], bytes], url: str, expected: list[str]
) -> None:
    """The reviewed rule of each family reads its invented Arabic page."""
    spec = _spec()
    rule = spec.kind_rules[kind]
    arabic_url = _arabic_url(url)
    rows = parse_agency(
        _arabic(page()),
        rule=rule,
        furniture=spec.furniture,
        minimum_blocks=rule.minimum_blocks,
        minimum_paragraphs=rule.minimum_paragraphs,
        envelope=_envelope(arabic_url),
        language="ar",
    )
    assert not isinstance(rows, InvestmentFailure), getattr(rows, "check", "")
    assert [row["record_type"] for row in rows] == expected
    assert all(row["language"] == "ar" for row in rows)
    assert rows[0]["page_key"] == urlsplit(arabic_url).path


@pytest.mark.parametrize(
    ("problem", "kind", "check"),
    [
        ("short_sector", "sector", "leading_level"),
        ("short_opportunity", "opportunity", "leading_level"),
        ("short_incentive", "incentive", "leading_level"),
        ("short_setup", "setup", "leading_level"),
        ("law_without_paragraph", "law", "paragraph"),
        ("table", "sector", "unsupported_shape"),
        ("no_title", "sector", "no_title"),
        ("empty_heading", "sector", "empty_heading"),
    ],
)
def test_arabic_plants_name_their_refusal(problem: str, kind: str, check: str) -> None:
    """Each planted Arabic page fails by its own reason."""
    spec = _spec()
    rule = spec.kind_rules[kind]
    result = parse_agency(
        _arabic(agency_plant(problem)),
        rule=rule,
        furniture=spec.furniture,
        minimum_blocks=rule.minimum_blocks,
        minimum_paragraphs=rule.minimum_paragraphs,
        envelope=_envelope(_arabic_url(SECTOR_URL)),
        language="ar",
    )
    assert getattr(result, "check", "") == check


def test_arabic_page_stating_english_or_cut_is_refused() -> None:
    """An Arabic entry that serves an English page or a cut page fails by name."""
    spec = _spec()
    rule = spec.kind_rules["sector"]
    envelope = _envelope(_arabic_url(SECTOR_URL))
    stated_english = parse_agency(
        sector_page(),
        rule=rule,
        furniture=spec.furniture,
        minimum_blocks=rule.minimum_blocks,
        minimum_paragraphs=rule.minimum_paragraphs,
        envelope=envelope,
        language="ar",
    )
    assert getattr(stated_english, "check", "") == "page_language"
    body = _arabic(sector_page())
    cut = parse_agency(
        body[:-30],
        rule=rule,
        furniture=spec.furniture,
        minimum_blocks=rule.minimum_blocks,
        minimum_paragraphs=rule.minimum_paragraphs,
        envelope=envelope,
        language="ar",
    )
    assert getattr(cut, "check", "") == "truncated"


def test_a_listed_page_url_in_the_other_language_is_refused() -> None:
    """A list entry whose URL language segment differs from its language is refused."""
    spec = _spec()
    for language, segment in (("ar", "en"), ("en", "ar")):
        item = {
            "kind": "sector",
            "url": f"https://agency.invalid/{segment}/invented",
            "language": language,
        }
        result = _pages([item], LANDING_URL, spec.kind_rules)
        assert getattr(result, "check", "") == "page_language"
    bare = {
        "kind": "sector",
        "url": "https://agency.invalid/sectors/invented-textiles",
        "language": "ar",
    }
    found = _pages([bare], LANDING_URL, spec.kind_rules)
    assert not isinstance(found, InvestmentFailure)
    assert found[0].language == "ar"


def test_a_malformed_listed_page_url_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A list entry whose URL cannot be split is refused by name, not a crash."""
    import eii_custodian.publicdata.investment_build as build

    root = repository_root(Path(__file__))
    document = read_yaml(root / "custodian" / "publicdata" / "investment_pages.yaml")
    planted = copy.deepcopy(document)
    planted["sources"]["investqa_pages"]["pages"].append(
        {
            "kind": "sector",
            "url": "https://[agency.invalid/ar/invented",
            "language": "ar",
        }
    )
    path = tmp_path / "pages.yaml"
    path.write_text(yaml.safe_dump(planted), encoding="utf-8")
    monkeypatch.setattr(build, "_PAGES", path)
    result = load_source_spec("investqa_pages", url=LANDING_URL)
    assert isinstance(result, InvestmentFailure)
    assert result.check == "missing_page"
    assert result.expected == "valid page URL"
    assert result.observed == "unreadable"
