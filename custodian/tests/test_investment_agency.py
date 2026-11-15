"""Heading-led agency pages. Furniture is dropped and each refusal names itself."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.investment_contracts import (
    InvestmentFailure,
    KindRule,
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
SECTOR_URL = _fixtures.SECTOR_URL
agency_plant = _fixtures.agency_plant
incentive_page = _fixtures.incentive_page
law_page = _fixtures.law_page
opportunity_page = _fixtures.opportunity_page
sector_page = _fixtures.sector_page
setup_page = _fixtures.setup_page

FURNITURE = frozenset({"pattern-lg-1", "pattern-dual", "whatsHappening"})
RETRIEVED = "2026-11-14T08:00:00Z"
SECTOR = KindRule("sector", "sector_block", {}, "", 2, 3, 0)
OPPORTUNITY = KindRule("opportunity", "", {3: "opportunity"}, "", 3, 5, 0)
INCENTIVE = KindRule("incentive", "", {4: "incentive_parameter"}, "setup_step", 4, 4, 0)
SETUP = KindRule("setup", "", {2: "setup_step", 3: "setup_step"}, "", 2, 5, 0)
LAW = KindRule("law", "law_block", {}, "", 0, 0, 1)


def test_sector_page_reads_heading_blocks_and_drops_furniture() -> None:
    """Content outside sections is kept; footer, furniture and the first title are not."""
    rows = parse_agency(
        sector_page(),
        rule=SECTOR,
        furniture=FURNITURE,
        minimum_blocks=SECTOR.minimum_blocks,
        minimum_paragraphs=SECTOR.minimum_paragraphs,
        envelope=_envelope(SECTOR_URL),
    )
    assert not isinstance(rows, InvestmentFailure), getattr(rows, "check", "")
    page = rows[0]
    assert page["record_type"] == "sector"
    assert page["record_key"] == "/sectors/invented-textiles"
    assert page["title"] == "Invented textiles"
    assert page["page_url"] == SECTOR_URL
    headings = [row["heading"] for row in rows[1:]]
    assert headings == [
        "Invented weaving",
        "Invented second block",
        "Invented third block",
        "Invented lower",
    ]
    assert all(row["record_type"] == "sector_block" for row in rows[1:])
    first = rows[1]
    assert json.loads(str(first["text_items"])) == [
        "Invented & loom",
        "Invented listed paragraph",
        "Invented bare item",
        "Invented share 12.5 percent",
    ]
    links = json.loads(str(first["links"]))
    assert links[0]["url"] == "https://agency.invalid/files/invented.pdf"
    assert links[0]["document"] is True
    assert links[0]["outside"] is False
    assert links[1]["url"] == "https://statute.invalid/invented"
    assert links[1]["document"] is False
    assert links[1]["outside"] is True
    assert rows[4]["parent_ordinal"] == 3
    assert rows[4]["level"] == 3
    blob = json.dumps(rows)
    assert "Invented footer" not in blob
    assert "Invented call" not in blob
    assert "Invented news" not in blob
    assert "Invented first title" not in blob


@pytest.mark.parametrize(
    ("problem", "kind", "rule", "check"),
    [
        ("no_main", "sector", SECTOR, "no_main"),
        ("no_title", "sector", SECTOR, "no_title"),
        ("empty_heading", "sector", SECTOR, "empty_heading"),
        ("short_sector", "sector", SECTOR, "leading_level"),
        ("short_opportunity", "opportunity", OPPORTUNITY, "leading_level"),
        ("short_incentive", "incentive", INCENTIVE, "leading_level"),
        ("short_setup", "setup", SETUP, "leading_level"),
        ("law_without_paragraph", "law", LAW, "paragraph"),
        ("table", "sector", SECTOR, "unsupported_shape"),
        ("cut_after_minimum", "sector", SECTOR, "truncated"),
        ("cut_in_paragraph", "sector", SECTOR, "truncated"),
        ("no_main_close", "sector", SECTOR, "truncated"),
        ("open_paragraph", "sector", SECTOR, "truncated"),
        ("no_html_end", "sector", SECTOR, "truncated"),
        ("second_main", "sector", SECTOR, "truncated"),
    ],
)
def test_each_agency_plant_names_its_reason(
    problem: str, kind: str, rule: KindRule, check: str
) -> None:
    """One planted page fails by its own reason."""
    del kind
    result = parse_agency(
        agency_plant(problem),
        rule=rule,
        furniture=FURNITURE,
        minimum_blocks=rule.minimum_blocks,
        minimum_paragraphs=rule.minimum_paragraphs,
        envelope=_envelope("https://agency.invalid/planted/invented"),
    )
    assert getattr(result, "check", "") == check


def test_empty_page_path_is_refused() -> None:
    """A page address with no path fails key_shape."""
    result = parse_agency(
        sector_page(),
        rule=SECTOR,
        furniture=FURNITURE,
        minimum_blocks=SECTOR.minimum_blocks,
        minimum_paragraphs=SECTOR.minimum_paragraphs,
        envelope=_envelope("https://agency.invalid/"),
    )
    assert getattr(result, "check", "") == "key_shape"


def test_trailing_slash_does_not_change_the_page_key() -> None:
    """A trailing slash is not part of the page key."""
    rows = _read(sector_page(), SECTOR, SECTOR_URL + "/")
    assert rows[0]["record_key"] == "/sectors/invented-textiles"
    assert rows[1]["record_key"] == "/sectors/invented-textiles:1"


def test_request_form_in_the_content_is_not_a_record() -> None:
    """A dialog form inside the content is skipped, text and link included."""
    pages = (
        (sector_page(), SECTOR, SECTOR_URL),
        (
            opportunity_page(),
            OPPORTUNITY,
            "https://agency.invalid/opportunities/invented-loom",
        ),
    )
    for body, rule, url in pages:
        assert b"form class='request-form'" in body
        assert b"Invented request link" in body
        if url == SECTOR_URL:
            assert b"<form><p>Invented plain label</p>" in body
        rows = parse_agency(
            body,
            rule=rule,
            furniture=FURNITURE,
            minimum_blocks=rule.minimum_blocks,
            minimum_paragraphs=rule.minimum_paragraphs,
            envelope=_envelope(url),
        )
        assert not isinstance(rows, InvestmentFailure), getattr(rows, "check", "")
        blob = json.dumps(rows)
        assert "Invented request label" not in blob
        assert "Invented request link" not in blob
        assert "Invented request button" not in blob
        assert "invented-request" not in blob
        assert "Invented plain label" not in blob
        assert "invented-plain" not in blob


def test_opportunity_incentive_setup_and_law_kinds() -> None:
    """Each page kind names the records the criterion asks for."""
    halls = _read(
        opportunity_page(),
        OPPORTUNITY,
        "https://agency.invalid/opportunities/invented-loom",
    )
    assert halls[0]["record_type"] == "opportunity"
    assert [row["record_type"] for row in halls[1:]] == [
        "block",
        "opportunity",
        "opportunity",
        "opportunity",
        "opportunity",
        "opportunity",
    ]
    package = _read(
        incentive_page(),
        INCENTIVE,
        "https://agency.invalid/incentives/invented-rent-ease",
    )
    assert package[0]["record_type"] == "incentive"
    assert [row["record_type"] for row in package[1:]] == [
        "incentive_parameter",
        "incentive_parameter",
        "incentive_parameter",
        "incentive_parameter",
        "setup_step",
    ]
    steps = _read(setup_page(), SETUP, "https://agency.invalid/setup/invented-steps")
    assert steps[0]["record_type"] == "setup"
    assert [row["record_type"] for row in steps[1:]] == ["setup_step"] * 6
    assert steps[-1]["parent_ordinal"] == 5
    statute = _read(law_page(), LAW, "https://agency.invalid/laws/invented-statute")
    assert statute[0]["record_type"] == "law"
    assert statute[0]["title"] == "Invented statute"
    assert statute[1]["record_type"] == "law_block"
    links = json.loads(str(statute[1]["links"]))
    assert links[0]["document"] is True
    assert links[1]["outside"] is True
    waived = parse_agency(
        law_page(paragraph=False),
        rule=LAW,
        furniture=FURNITURE,
        minimum_blocks=0,
        minimum_paragraphs=0,
        envelope=_envelope("https://agency.invalid/laws/invented-index"),
    )
    assert not isinstance(waived, InvestmentFailure), getattr(waived, "check", "")
    assert waived[0]["record_type"] == "law"


def _read(body: bytes, rule: KindRule, url: str) -> tuple[dict[str, object], ...]:
    rows = parse_agency(
        body,
        rule=rule,
        furniture=FURNITURE,
        minimum_blocks=rule.minimum_blocks,
        minimum_paragraphs=rule.minimum_paragraphs,
        envelope=_envelope(url),
    )
    assert not isinstance(rows, InvestmentFailure), getattr(rows, "check", "")
    return rows


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
