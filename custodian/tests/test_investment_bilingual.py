"""Offline bilingual acquisition and exact archived quotation guards."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from custodian.tests import test_investment_build as b

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.investment_contracts import InvestmentFailure


def bilingual():
    import eii_custodian.publicdata.investment_build as build

    pages = []
    bodies = b._agency_transport_bodies()
    for language in ("en", "ar"):
        for kind, url, blocks, paragraphs in (
            ("sector", b.SECTOR_URL, 3, 0),
            ("opportunity", b.OPPORTUNITY_URL, 5, 0),
            ("incentive", b.INCENTIVE_URL, 4, 0),
            ("setup", b.SETUP_URL, 5, 0),
            ("law", b.LAW_URL, 0, 1),
        ):
            address = url.replace("agency.invalid/", f"agency.invalid/{language}/")
            body = bodies[url].replace(
                b'<html lang="en">', f'<html lang="{language}">'.encode()
            )
            introduction = (
                "Invented  introduction;\n unchanged."
                if language == "en"
                else "مقدمة  مخترعة؛\n دون تغيير."
            )
            body = body.replace(
                b"<main>",
                (
                    "<main><p>"
                    + introduction
                    + "</p><ul><li>"
                    + introduction
                    + "</li></ul>"
                ).encode(),
            )
            if language == "ar":
                body = body.replace(b"Invented", "مخترع".encode())
            bodies[address] = body
            pages.append(build.PageSpec(kind, address, blocks, paragraphs, language))
    return tuple(pages), bodies


def test_bilingual_normal_seam_exact_quotations(tmp_path: Path, monkeypatch):
    import eii_custodian.publicdata.investment_quotation as q

    def no_network(*args, **kwargs):
        raise AssertionError("network_attempt")

    monkeypatch.setattr(socket, "create_connection", no_network)
    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    pointer, manifest, table = b._batch(tmp_path, "investqa_pages")
    cache = tmp_path / "data/public_cache"
    for order, page in enumerate(pages, 1):
        quotation = q.read_quotation(
            cache, pointer["evidence_manifest_identity"], order
        )
        assert not isinstance(quotation, InvestmentFailure), quotation
        assert quotation.body == bodies[page.url]
        assert quotation.language == page.language
        assert quotation.retrieved_utc == b.RETRIEVED
        assert quotation.page_sha256 == sha256_hex(bodies[page.url])
        assert quotation.order == order
        assert q.validate_quotation(quotation, bodies[page.url]) is None
    assert manifest["parser_version"] == "2"
    assert {row["language"] for row in table["rows"]} == {"ar", "en"}
    assert table["schema_version"] == "pub_investqa_record.v1"


@pytest.mark.parametrize(
    "plant",
    [
        "introduction",
        "list",
        "whitespace",
        "punctuation",
        "translation",
        "substitution",
    ],
)
def test_quotation_plants(tmp_path: Path, monkeypatch, plant):
    import eii_custodian.publicdata.investment_quotation as q

    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    pointer, _, _ = b._batch(tmp_path, "investqa_pages")
    quotation = q.read_quotation(
        tmp_path / "data/public_cache", pointer["evidence_manifest_identity"], 1
    )
    assert not isinstance(quotation, InvestmentFailure)
    body = quotation.body
    if plant == "introduction":
        start, end = body.index(b"<p>"), body.index(b"</p>") + 4
        altered = body[:start] + body[end:]
    elif plant == "list":
        start, end = body.index(b"<ul>"), body.index(b"</ul>") + 5
        altered = body[:start] + body[end:]
    elif plant == "whitespace":
        altered = body.replace(b"  introduction", b" introduction")
    elif plant == "punctuation":
        altered = body.replace(b"introduction;", b"introduction,")
    elif plant == "translation":
        altered = bodies[pages[5].url]
    else:
        altered = bodies[pages[1].url]
    assert q.validate_quotation(quotation, altered).check == "quotation_mismatch"
    assert q.validate_quotation(quotation, body) is None


def test_wrong_language_keeps_previous_batch(tmp_path: Path, monkeypatch):
    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    before = b._published(tmp_path, "investqa_pages")
    bodies[pages[5].url] = bodies[pages[5].url].replace(b'lang="ar"', b'lang="en"')
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 1
    assert any("page_language" in line for line in b._log(tmp_path)["lines"])
    after = b._published(tmp_path, "investqa_pages")
    for name in b._batch_names(before):
        assert before[name] == after[name]


@pytest.mark.parametrize(
    "field", ["sha256", "retrieved_utc", "language", "order", "kind"]
)
def test_missing_page_evidence_refuses_atomic_batch(tmp_path: Path, monkeypatch, field):
    import eii_custodian.publicdata.investment_build as build

    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    before = b._published(tmp_path, "investqa_pages")
    commit = build._commit_batch

    def plant(cache, entry, spec, envelope, document, listed, terms, retrieved):
        changed = [dict(page) for page in listed]
        changed[1].pop(field)
        return commit(
            cache, entry, spec, envelope, document, tuple(changed), terms, retrieved
        )

    monkeypatch.setattr(build, "_commit_batch", plant)
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 1
    assert any("page_evidence" in line for line in b._log(tmp_path)["lines"])
    after = b._published(tmp_path, "investqa_pages")
    for name in b._batch_names(before):
        assert before[name] == after[name]


def test_parser_versions_do_not_restamp_other_families(tmp_path: Path):
    from custodian.tests.test_investment_evidence_survivors import candidate

    from eii_custodian.publicdata import investment_evidence
    from eii_custodian.publicdata.investment_contracts import PARSER_VERSION
    from eii_custodian.publicdata.investment_evidence import _snapshot_envelope
    from eii_custodian.publicdata.investment_parse import (
        agency_envelope,
        dashboard_envelope,
    )

    assert dashboard_envelope(b._envelope()).method_version == "1"
    assert agency_envelope(b._envelope()).method_version == "2"
    assert PARSER_VERSION == "1"
    milestone = candidate(tmp_path)
    envelope = _snapshot_envelope(
        milestone.snapshot, investment_evidence._MILESTONE_METHOD, PARSER_VERSION
    )
    assert envelope.method == investment_evidence._MILESTONE_METHOD
    assert envelope.method_version == "1"


def test_inventory_v2_requires_explicit_language():
    from custodian.tests.test_investment_agency import SECTOR

    from eii_custodian.publicdata.investment_build import _pages

    for language in (None, "translated", ""):
        item = {"kind": "sector", "url": b.SECTOR_URL, "language": language}
        result = _pages([item], b.LANDING_URL, {"sector": SECTOR})
        assert getattr(result, "check", "") == "page_language"


def test_missing_arabic_confirmation_is_pending():
    import eii_custodian.publicdata.gate_report as g

    flags = dict.fromkeys(g.INVESTMENT_FLAGS, True)
    document = {
        "sources": {
            key: {"confirmation": flags} for key in ("fdi_projects", "investqa_pages")
        }
    }
    result = g.investment_evidence(document, "invented-review")
    assert result.checks["investqa_pages:arabic_evidence"] is False
    document["sources"]["investqa_pages"].update(
        {
            "language_confirmation": {
                "ar": {**flags, "read_on": "2026-11-19", "reference": "invented-review"}
            },
            "pages": [
                {"kind": kind, "language": "ar"}
                for kind in ("sector", "opportunity", "incentive", "setup", "law")
            ],
        }
    )
    assert (
        g.investment_evidence(document, "invented-review").checks[
            "investqa_pages:arabic_evidence"
        ]
        is True
    )


def test_each_language_requires_all_families(tmp_path: Path, monkeypatch):
    pages, bodies = bilingual()
    partial = tuple(
        page for page in pages if not (page.language == "ar" and page.kind == "law")
    )
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=partial) == 1
    assert any("missing_page" in line for line in b._log(tmp_path)["lines"])


@pytest.mark.parametrize("digits", [8, 11])
def test_intro_identifiers_cannot_hide_outside_blocks(
    tmp_path: Path, monkeypatch, digits
):
    pages, bodies = bilingual()
    bodies[pages[0].url] = bodies[pages[0].url].replace(
        b"Invented  introduction", b"Invented " + b"1" * digits
    )
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 1
    assert any("identifier_shape" in line for line in b._log(tmp_path)["lines"])


@pytest.mark.parametrize("plant", ["truncated", "shape"])
def test_arabic_shape_and_truncation_keep_previous_batch(
    tmp_path: Path, monkeypatch, plant
):
    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    before = b._published(tmp_path, "investqa_pages")
    if plant == "truncated":
        bodies[pages[5].url] = bodies[pages[5].url].replace(b"</html>", b"")
        check = "truncated"
    else:
        bodies[pages[5].url] = bodies[pages[5].url].replace(
            b"<main>", b"<main><table></table>"
        )
        check = "unsupported_shape"
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 1
    assert any(check in line for line in b._log(tmp_path)["lines"])
    after = b._published(tmp_path, "investqa_pages")
    for name in b._batch_names(before):
        assert after[name] == before[name]


def test_network_attempt_is_an_explicit_failure(tmp_path: Path, monkeypatch):
    pages, bodies = bilingual()

    def refuse(*args, **kwargs):
        raise AssertionError("network_attempt")

    def transport(url):
        socket.create_connection(("invented.invalid", 443))
        body = b.TERMS_BODY if url == b.TERMS_URL else bodies[url]
        return b.Response(final_url=url, body=body, hops=())

    monkeypatch.setattr(socket, "create_connection", refuse)
    with pytest.raises(AssertionError, match="network_attempt"):
        b._execute(tmp_path, monkeypatch, b._agency_entry(), transport, pages)
    assert not b._batch_names(b._published(tmp_path, "investqa_pages"))


def test_fetched_content_commit_is_refused(tmp_path: Path):
    from check_tree import Checker, data_untracked

    checker = object.__new__(Checker)
    checker.root = tmp_path
    checker.tracked = {"data/public_cache/invented.html"}
    failures = []
    data_untracked(checker, failures)
    assert any("data-untracked" in failure for failure in failures)
    checker.tracked = set()
    clean = []
    data_untracked(checker, clean)
    assert clean == []


def test_registry_contract_and_release_boundaries():
    from custodian.tests.repository_root import repository_root

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.investment_build import load_source_spec

    for entry in load_registry():
        if entry.source_id not in {"fdi_projects", "investqa_pages"}:
            continue
        spec = load_source_spec(entry.source_id, url=entry.url)
        assert spec.bounds.row_count_min == entry.row_count_min
        assert spec.bounds.row_count_max == entry.row_count_max
        assert entry.commit_allowed is False
        assert entry.nightly_live_fetch is True
        assert entry.licence_basis == "owner_decision"
    contract = (
        repository_root(Path(__file__)) / "docs/03_DATA_CONTRACTS.md"
    ).read_text()
    agency_row = next(
        line
        for line in contract.splitlines()
        if line.startswith("| `pub_investqa_record` | The reader")
    )
    assert "no paragraph column" in agency_row
    assert "full_page" not in agency_row
    assert "never a page's paragraphs" in contract


def test_count_command_uses_inventory_language(tmp_path: Path, monkeypatch, capsys):
    from dataclasses import replace

    from eii_custodian.publicdata import investment_counts as counts
    from eii_custodian.publicdata.investment_build import load_source_spec

    pages, bodies = bilingual()
    spec = load_source_spec("investqa_pages", url=b.LANDING_URL)
    monkeypatch.setattr(
        counts, "load_source_spec", lambda *args, **kwargs: replace(spec, pages=pages)
    )
    page = pages[5]
    path = tmp_path / "invented.html"
    path.write_bytes(bodies[page.url].replace(b'lang="ar"', b'lang="en"'))
    assert counts.main(["counts", "agency", str(path), page.url, page.kind]) == 1
    assert capsys.readouterr().out == "fail page_language\n"
    path.write_bytes(bodies[page.url])
    assert counts.main(["counts", "agency", str(path), page.url, page.kind]) == 0
    assert capsys.readouterr().out.startswith("records ")


@pytest.mark.parametrize("field,value", [("language", []), ("order", 1.0)])
def test_malformed_page_evidence_is_a_named_refusal(
    tmp_path: Path, monkeypatch, field, value
):
    import eii_custodian.publicdata.investment_quotation as q

    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    _, manifest, _ = b._batch(tmp_path, "investqa_pages")
    page = dict(manifest["pages"][1])
    page[field] = value
    result = q.page_evidence(tmp_path / "data/public_cache/investqa_pages", page, 1)
    assert getattr(result, "check", "") == "page_evidence"


def test_arabic_evidence_requires_a_calendar_date():
    import eii_custodian.publicdata.gate_report as g

    flags = dict.fromkeys(g.INVESTMENT_FLAGS, True)
    agency = {
        "language_confirmation": {
            "ar": {**flags, "read_on": "2026-99-99", "reference": "invented-review"}
        },
        "pages": [
            {"language": "ar", "kind": kind}
            for kind in ("sector", "opportunity", "incentive", "setup", "law")
        ],
    }
    result = g.investment_evidence(
        {"sources": {"investqa_pages": agency}}, "invented-review"
    )
    assert result.checks["investqa_pages:arabic_evidence"] is False


def test_page_evidence_refusal_names_its_source_url(tmp_path: Path, monkeypatch):
    import eii_custodian.publicdata.investment_quotation as q

    pages, bodies = bilingual()
    assert b._run(tmp_path, monkeypatch, b._agency_entry(), bodies, pages=pages) == 0
    _, manifest, _ = b._batch(tmp_path, "investqa_pages")
    page = dict(manifest["pages"][1])
    page.pop("retrieved_utc")
    failure = q.page_evidence(tmp_path / "data/public_cache/investqa_pages", page, 1)
    assert failure.source_id == "investqa_pages"
    assert failure.url == pages[0].url
    assert failure.check == "page_evidence"
