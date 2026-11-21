"""Investment build: injected transport, cache, drift, bounds and publication."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from check_tree import DATA_PROBES
from eii_custodian.publicdata.fetch.cadence import Cadence
from eii_custodian.publicdata.fetch.registry import FIELDS, Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.investment_build import (
    PageSpec,
    audit_snapshot,
    load_source_spec,
    require_page_families,
    select_release,
    validate_investment,
)
from eii_custodian.publicdata.investment_contracts import (
    Bounds,
    Confirmation,
    InvestmentFailure,
    SourceEnvelope,
    accept_project_slot,
    bare_digit_run,
)
from eii_custodian.publicdata.investment_parse import parse_fdi

_FIXTURE_PATH = Path(__file__).with_name("investment_fixtures.py")
_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "investment_fixtures", _FIXTURE_PATH
)
assert _FIXTURE_SPEC is not None and _FIXTURE_SPEC.loader is not None
_fixtures = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(_fixtures)
DASHBOARD_URL = _fixtures.DASHBOARD_URL
LANDING_URL = _fixtures.LANDING_URL
INCENTIVE_URL = _fixtures.INCENTIVE_URL
LAW_URL = _fixtures.LAW_URL
OPPORTUNITY_URL = _fixtures.OPPORTUNITY_URL
ORIGIN = _fixtures.ORIGIN
SECTOR_URL = _fixtures.SECTOR_URL
SETUP_URL = _fixtures.SETUP_URL
PHRASES = _fixtures.PHRASES
PROSE = _fixtures.PROSE
TERMS_BODY = _fixtures.TERMS_BODY
TERMS_URL = _fixtures.TERMS_URL
agency_bodies = _fixtures.agency_bodies
agency_plant = _fixtures.agency_plant
dashboard_page = _fixtures.dashboard_page
invented_record = _fixtures.invented_record
made_dashboard = _fixtures.made_dashboard

RETRIEVED = "2026-11-14T08:00:00Z"


def test_dashboard_loads_every_mapped_field_on_successive_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two builds of the same invented page keep every field and one raw body."""
    assert ORIGIN == "invented"
    page = made_dashboard(prose=PROSE)
    code = _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: page.body})
    assert code == 0
    _pointer, manifest, table = _batch(tmp_path, "fdi_projects")
    assert table["row_count"] == 1
    row = table["rows"][0]
    assert row["company"] == "Invented Loom Works"
    assert row["source_country"] == "Inventedland"
    assert row["sector"] == "Invented textiles"
    assert row["sub_sector"] == "Invented weaving"
    assert row["business_function"] == "Invented making"
    assert row["project_type"] == "Invented new site"
    assert row["capex_value"] == "12.5"
    assert row["capex_unit"] == "Mn USD"
    assert row["jobs"] == "40"
    assert row["announced"] == "2024-06-15"
    assert row["location_text"] == "Invented Bay"
    assert row["project_id"] == 1001
    assert row["project_month"] == 5
    assert row["lat"] == "10.123456789012"
    assert table["empty_coordinate_count"] == 0
    assert row["source_country_iso3"] is None
    assert row["municipality_code"] is None
    assert row["place_key"] is None
    assert "latitude" not in row
    assert row["caveat_keys"] == ["fdi_estimates"]
    assert row["provenance"] == "public"
    assert row["publisher"] == "National investment promotion agency"
    assert row["page_url"] == DASHBOARD_URL
    assert row["retrieved_utc"] == RETRIEVED
    assert isinstance(row["terms_sha256"], str) and row["terms_sha256"]
    assert row["licence_basis"] == "owner_decision"
    assert row["decision_record"] == "0017"
    assert row["project_key"] == _independent_key(page.tokens[0])
    rendered = json.dumps(table)
    assert PROSE not in rendered
    assert "cache-only-loom" not in rendered
    upstream = tmp_path / "data" / "public_cache" / "fdi_projects" / "upstream"
    assert not upstream.exists()
    log = _log(tmp_path)
    assert any(line == "fdi_projects empty_coordinates=0" for line in log["lines"])
    again = _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: page.body})
    assert again == 0
    bodies = list((tmp_path / "data" / "public_cache" / "fdi_projects").glob("*.html"))
    assert len(bodies) == 1
    assert manifest["snapshot_identity"] == "page_sha256"
    assert manifest["release_selected"] is False
    assert manifest["live_page_compared"] is True


def test_nullable_precision_and_duplicate_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty optional fields stay null and source precision is kept.

    A duplicate refresh fails by source name. The earlier pointer stays: a failed
    build is not reported as a refresh of the old batch, and that batch is not
    deleted (PUB-10).
    """
    sparse = invented_record(
        project_id=1002,
        investing_company_name="Invented Cedar Press",
        jobs="",
        project_date="",
        project_year="",
        project_month=None,
        capex=("n", "0"),
        capex_currency="",
    )
    page = dashboard_page((invented_record(), sparse))
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: page}) == 0
    _pointer, _manifest, table = _batch(tmp_path, "fdi_projects")
    second = table["rows"][1]
    assert second["company"] == "Invented Cedar Press"
    assert second["jobs"] is None
    assert second["announced"] is None
    assert second["capex_value"] is None
    assert second["capex_unit"] is None
    precise = dashboard_page(
        (
            invented_record(
                capex=("n", "12.5"), investing_company_name="Invented Reed Mill"
            ),
        )
    )
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: precise}) == 0
    _pointer, _manifest, precise_table = _batch(tmp_path, "fdi_projects")
    assert precise_table["rows"][0]["capex_value"] == "12.5"
    kept = (
        tmp_path / "data" / "public_cache" / "fdi_projects" / "loadable.json"
    ).read_bytes()
    cloned = dashboard_page((invented_record(), invented_record()))
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: cloned}) != 0
    assert (
        tmp_path / "data" / "public_cache" / "fdi_projects" / "loadable.json"
    ).read_bytes() == kept
    log = _log(tmp_path)
    assert any(
        line.startswith("FAIL fdi_projects") and "duplicate_project" in line
        for line in log["lines"]
    )
    assert not any(str(line).startswith("PASS fdi_projects") for line in log["lines"])


_SHARED_SECTOR = "https://agency.invalid/sectors/financial-services"
_SHARED_INCENTIVE = "https://agency.invalid/incentives/financial-services"
_SAME_PATH = "https://other.invalid/sectors/financial-services"


def test_shared_last_segment_publishes_one_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sector page and an incentive page can share a final segment."""
    bodies = _agency_transport_bodies()
    bodies[_SHARED_SECTOR] = bodies[SECTOR_URL]
    bodies[_SHARED_INCENTIVE] = bodies[INCENTIVE_URL]
    pages = _family_pages(_SHARED_SECTOR, _SHARED_INCENTIVE)
    assert _run(tmp_path, monkeypatch, _agency_entry(), bodies, pages=pages) == 0
    _pointer, _manifest, table = _batch(tmp_path, "investqa_pages")
    page_keys = {
        str(row["page_key"])
        for row in table["rows"]
        if row["record_type"] in {"sector", "incentive"}
    }
    assert page_keys == {
        "/sectors/financial-services",
        "/incentives/financial-services",
    }
    blocks = [
        str(row["record_key"])
        for row in table["rows"]
        if row["record_type"] not in {"sector", "incentive"}
        and str(row["page_key"]) in page_keys
    ]
    assert blocks
    assert len(blocks) == len(set(blocks))
    assert all(
        key.startswith("/sectors/financial-services:")
        or key.startswith("/incentives/financial-services:")
        for key in blocks
    )


def test_same_page_path_is_still_a_duplicate_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two pages with one whole path still fail duplicate_key and publish nothing."""
    bodies = _agency_transport_bodies()
    bodies[_SHARED_SECTOR] = bodies[SECTOR_URL]
    bodies[_SAME_PATH] = bodies[INCENTIVE_URL]
    pages = _family_pages(_SHARED_SECTOR, _SAME_PATH)
    assert _run(tmp_path, monkeypatch, _agency_entry(), bodies, pages=pages) != 0
    assert not (
        tmp_path / "data" / "public_cache" / "investqa_pages" / "loadable.json"
    ).exists()
    log = _log(tmp_path)
    assert any(
        line.startswith("FAIL investqa_pages") and "duplicate_key" in line
        for line in log["lines"]
    )


def test_agency_batch_folder_prints_counts_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A folder of addressed pages builds one batch and prints counts only."""
    from eii_custodian.publicdata.investment_counts import main

    folder = _page_folder(tmp_path / "batch")
    code = main(["investment_counts", "agency-batch", str(folder)])
    captured = capsys.readouterr()
    assert code == 0, captured.out
    assert "Invented" not in captured.out
    assert captured.out.splitlines()[1] == "pages 5"
    assert captured.out.startswith("records ")


def test_agency_batch_same_path_names_duplicate_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two saved pages with one path fail the batch and print no record text."""
    from eii_custodian.publicdata.investment_counts import main

    folder = _page_folder(tmp_path / "same")
    (folder / "sector-again.html").write_bytes((folder / "sector.html").read_bytes())
    with (folder / "addresses.txt").open("a", encoding="utf-8") as handle:
        handle.write(
            "sector https://other.invalid/sectors/invented-textiles sector-again.html\n"
        )
    code = main(["investment_counts", "agency-batch", str(folder)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == "fail duplicate_key\n"
    assert "Invented" not in captured.out


def test_agency_batch_names_usage_and_an_unknown_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing list, a short line, or an unknown kind is named and publishes nothing."""
    from eii_custodian.publicdata.investment_counts import main

    missing = tmp_path / "missing"
    missing.mkdir()
    assert main(["investment_counts", "agency-batch", str(missing)]) == 2
    assert capsys.readouterr().err == "fail usage\n"
    folder = tmp_path / "short"
    folder.mkdir()
    (folder / "addresses.txt").write_text("sector only\n", encoding="utf-8")
    assert main(["investment_counts", "agency-batch", str(folder)]) == 2
    assert capsys.readouterr().err == "fail usage\n"
    (folder / "addresses.txt").write_text(
        "invented-kind https://agency.invalid/sectors/invented-textiles sector.html\n",
        encoding="utf-8",
    )
    assert main(["investment_counts", "agency-batch", str(folder)]) == 1
    assert capsys.readouterr().out == "fail missing_page\n"
    one = tmp_path / "one"
    one.mkdir()
    (one / "sector.html").write_bytes(_fixtures.agency_bodies()[SECTOR_URL])
    (one / "addresses.txt").write_text(
        f"sector {SECTOR_URL} sector.html\n", encoding="utf-8"
    )
    assert main(["investment_counts", "agency-batch", str(one)]) == 1
    assert capsys.readouterr().out == "fail missing_page\n"
    cut = _page_folder(tmp_path / "cut")
    (cut / "sector.html").write_bytes(agency_plant("cut_after_minimum"))
    assert main(["investment_counts", "agency-batch", str(cut)]) == 1
    assert capsys.readouterr().out == "fail truncated\n"


def test_removing_either_caveat_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each required estimate note is mandatory."""
    for phrase in PHRASES:
        root = tmp_path / str(PHRASES.index(phrase))
        code = _run(
            root,
            monkeypatch,
            _fdi_entry(),
            {DASHBOARD_URL: dashboard_page(drop_phrase=phrase)},
        )
        assert code != 0
        log = _log(root)
        assert any("missing_caveat" in line for line in log["lines"])
        assert not (
            root / "data" / "public_cache" / "fdi_projects" / "loadable.json"
        ).exists()


def test_agency_pages_load_six_record_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sector, opportunity, package, parameter, set-up step and law keep their page."""
    code = _run(tmp_path, monkeypatch, _agency_entry(), _agency_transport_bodies())
    assert code == 0
    _pointer, manifest, table = _batch(tmp_path, "investqa_pages")
    kinds = {row["record_type"] for row in table["rows"]}
    assert {
        "sector",
        "opportunity",
        "incentive",
        "incentive_parameter",
        "setup_step",
        "law",
    } <= kinds
    law = next(row for row in table["rows"] if row["record_type"] == "law")
    assert str(law["page_url"]).endswith("/invented-statute")
    block = next(row for row in table["rows"] if row["record_type"] == "law_block")
    assert "invented.pdf" in str(block["links"])
    assert manifest["snapshot_identity"] == "aggregate_manifest"
    assert len(manifest["pages"]) == 6
    assert all(page["sha256"] and page["retrieved_utc"] for page in manifest["pages"])


def test_agency_plants_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each broken page shape publishes nothing from the source."""
    plants = (
        ("no_main", SECTOR_URL),
        ("no_title", SECTOR_URL),
        ("empty_heading", SECTOR_URL),
        ("short_sector", SECTOR_URL),
        ("short_opportunity", OPPORTUNITY_URL),
        ("short_incentive", INCENTIVE_URL),
        ("short_setup", SETUP_URL),
        ("law_without_paragraph", LAW_URL),
        ("table", SECTOR_URL),
    )
    for problem, url in plants:
        folder = tmp_path / problem
        bodies = _agency_transport_bodies()
        bodies[url] = agency_plant(problem)
        assert _run(folder, monkeypatch, _agency_entry(), bodies) != 0
        assert not (
            folder / "data" / "public_cache" / "investqa_pages" / "loadable.json"
        ).exists()


def test_changed_page_is_kept_and_terms_stay_admitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed page keeps both bodies, and changed terms do not switch the source off."""
    first = dashboard_page()
    second = dashboard_page(
        (invented_record(investing_company_name="Invented Reed Mill"),)
    )
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: first}) == 0
    assert (
        _run(
            tmp_path,
            monkeypatch,
            _fdi_entry(),
            {DASHBOARD_URL: second},
            terms=b"Invented terms, revised.",
        )
        == 0
    )
    bodies = list((tmp_path / "data" / "public_cache" / "fdi_projects").glob("*.html"))
    assert len(bodies) == 2
    log = _log(tmp_path)
    assert any(line.startswith("TERMS fdi_projects") for line in log["lines"])
    assert not any(line.startswith("OWNER ") for line in log["lines"])
    assert (
        tmp_path / "data" / "public_cache" / "fdi_projects" / "loadable.json"
    ).is_file()


def test_a_missing_terms_reading_is_pending_and_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling L-1001: an unread terms page is recorded as pending and publishes."""

    def transport(url: str) -> Response:
        if url == _fdi_entry().terms_url:
            raise TransportFault("unreachable", url)
        if url == DASHBOARD_URL:
            return Response(final_url=url, body=dashboard_page(), hops=())
        if url == _fdi_entry().url:
            return Response(
                final_url=url, body=b"<html>Invented landing.</html>", hops=()
            )
        raise AssertionError(url)

    assert _execute(tmp_path, monkeypatch, _fdi_entry(), transport) == 0
    _pointer, _manifest, table = _batch(tmp_path, "fdi_projects")
    assert table["rows"]
    # The pending reading is recorded truthfully: no hash, nothing invented.
    assert all(row["terms_sha256"] == "" for row in table["rows"])
    log = _log(tmp_path)
    assert any(line.startswith("TERMS fdi_projects") for line in log["lines"])


def test_drift_plants_publish_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retyped field, an extra field and a late bad row publish nothing."""
    retyped = tmp_path / "retyped"
    page = dashboard_page((invented_record(jobs="many"),))
    assert _run(retyped, monkeypatch, _fdi_entry(), {DASHBOARD_URL: page}) != 0
    extra = tmp_path / "extra"
    page = dashboard_page((invented_record(secret_score="1"),))
    assert _run(extra, monkeypatch, _fdi_entry(), {DASHBOARD_URL: page}) != 0
    late = tmp_path / "late"
    page = dashboard_page(
        (
            invented_record(),
            invented_record(
                investing_company_name="Invented Reed Mill", project_date="2024-06-1"
            ),
        )
    )
    assert _run(late, monkeypatch, _fdi_entry(), {DASHBOARD_URL: page}) != 0
    for folder in (retyped, extra, late):
        assert not (
            folder / "data" / "public_cache" / "fdi_projects" / "loadable.json"
        ).exists()


def test_bounds_lineage_confirmation_and_public_only() -> None:
    """Bounds, lineage, confirmation flags and foreign slots are refused."""
    spec = load_source_spec("fdi_projects", url=DASHBOARD_URL)
    assert isinstance(spec, type(spec)) and not isinstance(spec, InvestmentFailure)
    assert spec.confirmation.live_page_compared is True
    envelope = _envelope()
    row = {
        "project_key": "fdi_aaaaaaaaaaaaaaaa",
        "caveat_keys": ["fdi_estimates"],
        "provenance": "public",
        "join_key": "",
        "announced": "2024-06",
        "publisher": envelope.publisher,
        "page_url": envelope.page_url,
        "licence_id": envelope.licence_id,
        "licence_basis": envelope.licence_basis,
        "decision_record": envelope.decision_record,
        "terms_sha256": envelope.terms_sha256,
        "retrieved_utc": envelope.retrieved_utc,
        "page_sha256": envelope.page_sha256,
    }
    tight = Bounds(2, 2, "announced", "2000", True)
    refused = validate_investment((row,), tight, spec.confirmation, envelope)
    assert getattr(refused, "check", "") == "row_count"
    stale = Bounds(1, 2, "announced", "2025", True)
    refused = validate_investment((row,), stale, spec.confirmation, envelope)
    assert getattr(refused, "check", "") == "period_last"
    unconfirmed = Bounds(1, 2, "announced", "2000", False)
    refused = validate_investment((row,), unconfirmed, spec.confirmation, envelope)
    assert getattr(refused, "check", "") == "unconfirmed"
    for name in ("publisher", "retrieved_utc", "page_sha256"):
        broken = dict(row)
        broken[name] = ""
        refused = validate_investment(
            (broken,),
            Bounds(1, 2, "announced", "2000", True),
            spec.confirmation,
            envelope,
        )
        assert getattr(refused, "check", "") == "missing_lineage"
    # Ruling L-1001: a pending terms reading, in the row or the envelope,
    # never refuses the batch; the empty value is the recorded pending state.
    pending_row = dict(row)
    pending_row["terms_sha256"] = ""
    accepted = validate_investment(
        (pending_row,),
        Bounds(1, 2, "announced", "2000", True),
        spec.confirmation,
        envelope,
    )
    assert not hasattr(accepted, "check")
    pending_envelope = replace(envelope, terms_sha256="", terms_url="")
    accepted = validate_investment(
        (row,),
        Bounds(1, 2, "announced", "2000", True),
        spec.confirmation,
        pending_envelope,
    )
    assert not hasattr(accepted, "check")
    broken = dict(row)
    broken["page_url"] = ""
    refused = validate_investment(
        (broken,),
        Bounds(1, 2, "announced", "2000", True),
        spec.confirmation,
        pending_envelope,
    )
    assert getattr(refused, "check", "") == "missing_lineage"
    gap = Confirmation(False, True, True, False)
    refused = validate_investment(
        (row,), Bounds(1, 2, "announced", "2000", True), gap, envelope
    )
    assert getattr(refused, "check", "") == "confirmation_inventory"
    bare = dict(row)
    bare["caveat_keys"] = []
    refused = validate_investment(
        (bare,), Bounds(1, 2, "announced", "2000", True), spec.confirmation, envelope
    )
    assert getattr(refused, "check", "") == "missing_caveat"
    assert accept_project_slot("synthetic", "") is not None
    assert accept_project_slot("simulated", "") is not None
    assert accept_project_slot("public", "attached-record") is not None
    assert accept_project_slot("public", "") is None
    assert require_page_families(("sector",), envelope) is not None
    entries = [item for item in load_registry() if item.source_id == "investqa_pages"]
    assert len(entries) == 1
    assert entries[0].skip_reason == ""
    assert entries[0].row_count_min == 20
    assert entries[0].row_count_max == 5000
    agency = load_source_spec("investqa_pages", url=LANDING_URL)
    assert not isinstance(agency, InvestmentFailure)
    assert agency.bounds.confirmed is True
    assert agency.confirmation.live_page_compared is True
    assert {page.kind for page in agency.pages} == {
        "sector",
        "opportunity",
        "incentive",
        "setup",
        "law",
    }
    assert "manifest" not in FIELDS


def test_publication_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Interrupt, hash mismatch, a missing file and an unreviewed release are refused."""
    import eii_custodian.publicdata.investment_build as publication

    def boom(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("interrupted")

    monkeypatch.setattr(publication, "_replace", boom)
    assert (
        _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: dashboard_page()})
        != 0
    )
    cache = tmp_path / "data" / "public_cache" / "fdi_projects"
    assert not (cache / "loadable.json").exists()
    assert list(cache.rglob("*.partial")) == []
    monkeypatch.undo()
    stored = tmp_path / "stored"
    assert (
        _run(stored, monkeypatch, _fdi_entry(), {DASHBOARD_URL: dashboard_page()}) == 0
    )
    cache = stored / "data" / "public_cache" / "fdi_projects"
    html = next(cache.glob("*.html"))
    html.write_bytes(b"invented-corrupt")
    mismatch = audit_snapshot(cache.parent, "fdi_projects")
    assert mismatch is not None
    assert mismatch.check == "hash_mismatch"
    html.unlink()
    missing = audit_snapshot(cache.parent, "fdi_projects")
    assert missing is not None
    assert missing.check == "missing_artifact"
    pointer = {"source_id": "fdi_projects", "release_selected": False}
    refused = select_release(pointer, reviewed=False)
    assert refused is not None
    assert refused.check == "unreviewed_release"


def test_audit_snapshot_rejects_replaced_manifest_before_page_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A same-name manifest substitution fails its pointer checksum first."""
    stored = tmp_path / "stored"
    assert (
        _run(stored, monkeypatch, _fdi_entry(), {DASHBOARD_URL: dashboard_page()}) == 0
    )
    cache = stored / "data" / "public_cache" / "fdi_projects"
    pointer, manifest, _table = _batch(stored, "fdi_projects")
    manifest_path = cache / "manifests" / f"{pointer['manifest_sha256']}.json"
    manifest_path.write_text('{"pages": []}\n', encoding="utf-8")
    raw_page = cache / f"{manifest['pages'][0]['sha256']}.html"
    raw_page.unlink()

    refused = audit_snapshot(cache.parent, "fdi_projects")
    assert isinstance(refused, InvestmentFailure)
    assert refused.check == "hash_mismatch"
    assert refused.expected == pointer["manifest_sha256"]
    assert refused.observed == "mismatch"


def test_audit_snapshot_rejects_correctly_named_empty_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty page coverage is invalid even when the replacement filename matches."""
    stored = tmp_path / "stored"
    assert (
        _run(stored, monkeypatch, _fdi_entry(), {DASHBOARD_URL: dashboard_page()}) == 0
    )
    cache = stored / "data" / "public_cache" / "fdi_projects"
    pointer = json.loads((cache / "loadable.json").read_text(encoding="utf-8"))
    body = b'{"pages": []}\n'
    digest = hashlib.sha256(body).hexdigest()
    (cache / "manifests" / f"{digest}.json").write_bytes(body)
    pointer["manifest_sha256"] = digest
    (cache / "loadable.json").write_text(json.dumps(pointer), encoding="utf-8")

    refused = audit_snapshot(cache.parent, "fdi_projects")
    assert isinstance(refused, InvestmentFailure)
    assert refused.check == "missing_artifact"
    assert refused.expected == "pages"
    assert refused.observed == "empty"


def test_fixtures_reject_realistic_identifiers_and_tracked_cache() -> None:
    """Invented fixtures have no bare digit run, and the tree guard names the cache."""
    text = dashboard_page().decode("utf-8")
    assert "Invented" in text
    assert bare_digit_run(text) is False
    assert bare_digit_run("Invented " + ("1" * 8) + " Works") is True
    assert bare_digit_run("Invented " + ("1" * 11) + " Works") is True
    assert "data/public_cache/x" in DATA_PROBES
    assert "data/vault/x" in DATA_PROBES
    import inspect

    import eii_custodian.publicdata.investment_parse as parser

    assert "dataset" not in inspect.signature(parser.parse_fdi).parameters
    assert "transport" not in inspect.signature(parser.parse_agency).parameters
    source = Path(parser.__file__).read_text(encoding="utf-8")
    assert "data/vault" not in source


def test_decimal_overflow_truncated_page_and_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An oversized decimal, a cut-off page and an unlisted redirect fail closed."""
    huge = "1" * 17
    for field in ("capex", "jobs"):
        folder = tmp_path / field
        assert (
            _run(
                folder,
                monkeypatch,
                _fdi_entry(),
                {
                    DASHBOARD_URL: dashboard_page(
                        (invented_record(**{field: ("n", huge)}),)
                    )
                },
            )
            != 0
        )
        assert not (
            folder / "data" / "public_cache" / "fdi_projects" / "loadable.json"
        ).exists()
        log = _log(folder)
        assert any(
            line.startswith("FAIL fdi_projects") and "unrepresentable" in line
            for line in log["lines"]
        )
    largest = ("9" * 16) + ".99"
    fitted = tmp_path / "fitted"
    assert (
        _run(
            fitted,
            monkeypatch,
            _fdi_entry(),
            {
                DASHBOARD_URL: dashboard_page(
                    (invented_record(capex=("n", largest), jobs=("n", largest)),)
                )
            },
        )
        == 0
    )
    _pointer, _manifest, table = _batch(fitted, "fdi_projects")
    assert table["rows"][0]["capex_value"] == largest
    assert table["rows"][0]["jobs"] == largest
    huge_old = "1" + ("0" * 18)
    legacy = tmp_path / "legacy"
    assert (
        _run(
            legacy,
            monkeypatch,
            _fdi_entry(),
            {DASHBOARD_URL: dashboard_page((invented_record(capex=("n", huge_old)),))},
        )
        != 0
    )
    cut = tmp_path / "cut"
    truncated = dashboard_page()[:80]
    assert _run(cut, monkeypatch, _fdi_entry(), {DASHBOARD_URL: truncated}) != 0
    from eii_custodian.publicdata.fetch.kinds import read_bounded

    def transport(url: str) -> Response:
        return Response(
            final_url=url, body=b"invented", hops=("https://evil.example/planted",)
        )

    live = next(
        item.url for item in load_registry() if item.source_id == "fdi_projects"
    )
    response, failure = read_bounded(transport, lambda _seconds: None, live)
    assert response is None
    assert failure is not None
    assert failure.check == "blocked_host"


@pytest.mark.parametrize("source_id", ["fdi_projects", "investqa_pages"])
@pytest.mark.parametrize("refusal", ["parser", "validation", "interrupted"])
def test_refused_refresh_keeps_the_earlier_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    refusal: str,
) -> None:
    """A refused refresh leaves the earlier pointer and artefacts byte-identical."""
    if source_id == "fdi_projects":
        entry = _fdi_entry()
        good: dict[str, bytes] = {DASHBOARD_URL: dashboard_page()}
    else:
        entry = _agency_entry()
        good = _agency_transport_bodies()
    assert _run(tmp_path, monkeypatch, entry, good) == 0
    before = _published(tmp_path, source_id)
    bodies, pages = _refused_bodies(source_id, refusal, good)
    if source_id == "fdi_projects" and refusal == "validation":
        from dataclasses import replace

        entry = replace(entry, row_count_max=0)
    if refusal == "interrupted":
        import eii_custodian.publicdata.investment_build as publication

        def boom(source: Path, destination: Path) -> None:
            del source, destination
            raise OSError("interrupted")

        monkeypatch.setattr(publication, "_replace", boom)
    assert _run(tmp_path, monkeypatch, entry, bodies, pages=pages) != 0
    after = _published(tmp_path, source_id)
    for name, body in before.items():
        assert after[name] == body
    assert _batch_names(before) == _batch_names(after)
    log = _log(tmp_path)
    assert any(str(line).startswith(f"FAIL {source_id}") for line in log["lines"])
    assert not any(str(line).startswith(f"PASS {source_id}") for line in log["lines"])
    if source_id == "fdi_projects" and refusal == "validation":
        assert any("row_count" in str(line) for line in log["lines"])


def test_failed_audit_leaves_the_earlier_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A candidate is audited before the pointer is replaced."""
    import eii_custodian.publicdata.investment_build as publication

    assert (
        _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: dashboard_page()})
        == 0
    )
    before = _published(tmp_path, "fdi_projects")

    def refuse_audit(
        cache: Path, source_id: str, manifest: object
    ) -> InvestmentFailure:
        del cache, manifest
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", "page", "missing"
        )

    monkeypatch.setattr(publication, "_audit_pages", refuse_audit)
    assert (
        _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: dashboard_page()})
        != 0
    )
    assert _published(tmp_path, "fdi_projects") == before
    changed = dashboard_page(
        (invented_record(investing_company_name="Invented Reed Mill"),)
    )
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: changed}) != 0
    after = _published(tmp_path, "fdi_projects")
    assert after["loadable.json"] == before["loadable.json"]
    for name, body in before.items():
        assert after[name] == body
    log = _log(tmp_path)
    assert any("missing_artifact" in str(line) for line in log["lines"])
    assert not any(str(line).startswith("PASS fdi_projects") for line in log["lines"])


def test_yaml_reader_is_the_registry_and_adds_no_suppression(tmp_path: Path) -> None:
    """The package has one YAML reader, and this task adds no type suppression."""
    from eii_custodian.publicdata.fetch.registry import RegistryError, read_yaml

    root = repository_root(Path(__file__).parent)
    build = (
        root / "custodian/src/eii_custodian/publicdata/investment_build.py"
    ).read_text(encoding="utf-8")
    fixtures = _FIXTURE_PATH.read_text(encoding="utf-8")
    registry = (
        root / "custodian/src/eii_custodian/publicdata/fetch/registry.py"
    ).read_text(encoding="utf-8")
    assert "type: ignore" not in build
    assert "type: ignore" not in fixtures
    assert "import yaml" not in build
    assert registry.count("type: ignore") == 0
    broken = tmp_path / "broken.yaml"
    broken.write_text("[\n", encoding="utf-8")
    with pytest.raises(RegistryError):
        read_yaml(broken)


def test_parser_accepts_null_date_without_padding() -> None:
    """A blank date stays null, and a padded partial date is refused."""
    spec = load_source_spec("fdi_projects", url=DASHBOARD_URL)
    assert spec.dashboard is not None
    envelope = _envelope()
    blank = dashboard_page(
        (invented_record(project_date="", project_year="", project_month=None),)
    )
    parsed = parse_fdi(blank, spec.dashboard, envelope)
    assert not isinstance(parsed, InvestmentFailure)
    rows, empty = parsed
    assert rows[0]["announced"] is None
    assert empty == 0
    padded = dashboard_page((invented_record(project_date="2023-02-29"),))
    refused = parse_fdi(padded, spec.dashboard, envelope)
    assert getattr(refused, "check", "") == "announced"


def test_parsed_revision_archive_survives_failed_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every parsed batch has an immutable receipt that a failed refresh cannot remove."""
    first = dashboard_page()
    second = dashboard_page(
        (invented_record(investing_company_name="Invented Reed Mill"),)
    )
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: first}) == 0
    first_pointer, first_manifest, first_table = _batch(tmp_path, "fdi_projects")
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: second}) == 0
    second_pointer, second_manifest, second_table = _batch(tmp_path, "fdi_projects")
    cache = tmp_path / "data" / "public_cache" / "fdi_projects"
    evidence = cache / "evidence"
    first_identity = first_manifest["table_snapshot_identity"]
    second_identity = second_manifest["table_snapshot_identity"]
    assert first_identity != second_identity
    assert json.loads(read_snapshot(evidence, first_identity).body) == first_table
    assert json.loads(read_snapshot(evidence, second_identity).body) == second_table
    assert (
        first_pointer["evidence_manifest_identity"]
        != second_pointer["evidence_manifest_identity"]
    )
    retained_before = {
        path.relative_to(evidence): path.read_bytes()
        for path in evidence.rglob("*")
        if path.is_file()
    }

    refused_entry = replace(_fdi_entry(), row_count_max=0)
    third = dashboard_page(
        (invented_record(investing_company_name="Invented Cedar Press"),)
    )
    assert _run(tmp_path, monkeypatch, refused_entry, {DASHBOARD_URL: third}) != 0
    assert _batch(tmp_path, "fdi_projects")[0] == second_pointer
    for relative, body in retained_before.items():
        assert (evidence / relative).read_bytes() == body


def test_equal_byte_agency_recheck_uses_archived_retrieval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An equal-byte recheck never replaces the original source retrieval time."""
    import eii_custodian.publicdata.investment_build as publication
    from eii_custodian.publicdata.fetch.allowlist import HostDecision, approve

    def allow(url: str) -> HostDecision:
        decision = approve(url)
        if decision.ok or decision.host.endswith(".invalid"):
            return HostDecision(True, decision.host, "https", "")
        return decision

    monkeypatch.setattr("eii_custodian.publicdata.fetch.kinds.approve", allow)
    entry = _agency_entry()
    body = agency_bodies()[SECTOR_URL]

    def transport(url: str) -> Response:
        return Response(final_url=url, body=body, hops=())

    first = publication._fetch_page(
        entry,
        tmp_path,
        SECTOR_URL,
        transport,
        lambda _seconds: None,
        lambda: "2026-11-14T08:00:00Z",
        "ab" * 32,
    )
    second = publication._fetch_page(
        entry,
        tmp_path,
        SECTOR_URL,
        transport,
        lambda _seconds: None,
        lambda: "2026-11-15T08:00:00Z",
        "ab" * 32,
    )
    assert not isinstance(first, InvestmentFailure)
    assert not isinstance(second, InvestmentFailure)
    assert first[1] == "2026-11-14T08:00:00Z"
    assert second[1] == "2026-11-14T08:00:00Z"
    assert second[2] == body


def test_fail_fast_archives_failed_and_unattempted_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shared build retains attempt evidence after its first fetch failure."""
    import commands.build_public as build_public
    from eii_custodian.publicdata.fetch.allowlist import HostDecision, approve

    first = _fdi_entry()
    second = replace(first, key="fdi_projects_later")

    def allow(url: str) -> HostDecision:
        decision = approve(url)
        if decision.ok or decision.host.endswith(".invalid"):
            return HostDecision(True, decision.host, "https", "")
        return decision

    def transport(url: str) -> Response:
        raise TransportFault("invented unavailable", url)

    monkeypatch.setattr(build_public, "load_registry", lambda: (first, second))
    monkeypatch.setattr(build_public, "utc_now", lambda: RETRIEVED)
    monkeypatch.setattr("eii_custodian.publicdata.fetch.build.approve", allow)
    monkeypatch.setattr("eii_custodian.publicdata.fetch.kinds.approve", allow)
    assert (
        build_public.run(tmp_path, {}, (), transport=transport, sleep=lambda _: None)
        != 0
    )
    cache = tmp_path / "data" / "public_cache"
    for key in (first.key, second.key):
        directory = cache / "audit" / key / "evidence"
        indexes = tuple((directory / "index").glob("*.json"))
        assert len(indexes) == 1
        identity = indexes[0].stem
        audit = json.loads(read_snapshot(directory, identity).body)
        states = {(row["key"], row["evidence_status"]) for row in audit["entries"]}
        assert (first.key, "failed") in states
        assert (second.key, "unattempted") in states
    log = _log(tmp_path)
    assert any(
        line
        == f"EVIDENCE {second.key} unattempted reason=not_attempted_after_fail_fast"
        for line in log["lines"]
    )


def _independent_key(tokens: dict[str, str]) -> str:
    parts = [
        json.dumps(name, ensure_ascii=True) + ":" + tokens[name]
        for name in sorted(tokens)
    ]
    encoded = "{" + ",".join(parts) + "}"
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return "fdi_" + digest[:16]


def _run(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: Entry,
    bodies: dict[str, bytes],
    terms: bytes = TERMS_BODY,
    pages: tuple[PageSpec, ...] | None = None,
) -> int:
    def transport(url: str) -> Response:
        if url == entry.terms_url:
            return Response(final_url=url, body=terms, hops=())
        if url in bodies:
            return Response(final_url=url, body=bodies[url], hops=())
        if url == entry.url:
            return Response(
                final_url=url, body=b"<html>Invented landing.</html>", hops=()
            )
        raise AssertionError(url)

    return _execute(root, monkeypatch, entry, transport, pages)


def _execute(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: Entry,
    transport: object,
    pages: tuple[PageSpec, ...] | None = None,
) -> int:
    from dataclasses import replace

    import commands.build_public as build_public
    import eii_custodian.publicdata.investment_build as publication
    from eii_custodian.publicdata.fetch.allowlist import HostDecision, approve
    from eii_custodian.publicdata.investment_build import PageSpec, load_source_spec

    def allow(url: str) -> HostDecision:
        decision = approve(url)
        if decision.ok or decision.host.endswith(".invalid"):
            return HostDecision(True, decision.host, "https", "")
        return decision

    def loading(source_id: str, *, url: str) -> object:
        spec = load_source_spec(source_id, url=url)
        if source_id != "investqa_pages" or isinstance(spec, InvestmentFailure):
            return spec
        chosen = (
            pages
            if pages is not None
            else (
                PageSpec("sector", _fixtures.SECTOR_URL, 3, 0),
                PageSpec("opportunity", _fixtures.OPPORTUNITY_URL, 5, 0),
                PageSpec("incentive", _fixtures.INCENTIVE_URL, 4, 0),
                PageSpec("setup", _fixtures.SETUP_URL, 5, 0),
                PageSpec("law", _fixtures.LAW_URL, 0, 1),
            )
        )
        return replace(
            spec,
            bounds=replace(spec.bounds, row_count_min=1, row_count_max=5000),
            pages=chosen,
        )

    monkeypatch.setattr(build_public, "load_registry", lambda: (entry,))
    monkeypatch.setattr(build_public, "utc_now", lambda: RETRIEVED)
    monkeypatch.setattr("eii_custodian.publicdata.fetch.build.approve", allow)
    monkeypatch.setattr("eii_custodian.publicdata.fetch.kinds.approve", allow)
    monkeypatch.setattr(publication, "load_source_spec", loading)
    # These are source-publication fixtures. The production command now also
    # requires the complete reviewed assembly; exercise its existing fetch seam
    # directly here, retaining every publication and refusal assertion below.
    from custodian.tests.support.fetch_build import run_build

    from commands import exits
    from eii_custodian.publicdata.fetch.report import log_line

    cache = root / "data/public_cache"
    outcome = run_build(
        (entry,),
        transport,
        cache,
        lambda: RETRIEVED,
        lambda _seconds: None,
    )
    for line in outcome.lines:
        print(line)
    print(log_line("data/public_cache/build-log.json"))
    if outcome.failure is not None:
        return exits.finish(
            outcome.failure.code, "build-public", outcome.failure.detail
        )
    return 0


def _family_pages(sector: str, incentive: str) -> tuple[PageSpec, ...]:
    return (
        PageSpec("sector", sector, 3, 0),
        PageSpec("opportunity", OPPORTUNITY_URL, 5, 0),
        PageSpec("incentive", incentive, 4, 0),
        PageSpec("setup", SETUP_URL, 5, 0),
        PageSpec("law", LAW_URL, 0, 1),
    )


def _refused_bodies(
    source_id: str, refusal: str, good: dict[str, bytes]
) -> tuple[dict[str, bytes], tuple[PageSpec, ...] | None]:
    if source_id == "fdi_projects":
        if refusal == "parser":
            return {DASHBOARD_URL: dashboard_page()[:80]}, None
        if refusal == "validation":
            return dict(good), None
        return dict(good), None
    bodies = dict(good)
    if refusal == "parser":
        bodies[SECTOR_URL] = agency_plant("cut_after_minimum")
        return bodies, None
    if refusal == "validation":
        bodies[_SHARED_SECTOR] = bodies[SECTOR_URL]
        bodies[_SAME_PATH] = bodies[INCENTIVE_URL]
        return bodies, _family_pages(_SHARED_SECTOR, _SAME_PATH)
    return bodies, None


def _published(root: Path, source_id: str) -> dict[str, bytes]:
    cache = root / "data" / "public_cache" / source_id
    found: dict[str, bytes] = {}
    for path in sorted(cache.rglob("*")):
        if path.is_file() and not path.name.endswith(".partial"):
            found[str(path.relative_to(cache))] = path.read_bytes()
    return found


def _batch_names(found: dict[str, bytes]) -> set[str]:
    return {
        name
        for name in found
        if name == "loadable.json" or name.startswith(("manifests/", "staging/"))
    }


def _page_folder(folder: Path) -> Path:
    folder.mkdir()
    bodies = agency_bodies()
    listed = (
        ("sector", SECTOR_URL, "sector.html"),
        ("opportunity", OPPORTUNITY_URL, "opportunity.html"),
        ("incentive", INCENTIVE_URL, "incentive.html"),
        ("setup", SETUP_URL, "setup.html"),
        ("law", LAW_URL, "law.html"),
    )
    lines = [f"{kind} {url} {name}" for kind, url, name in listed]
    for _kind, url, name in listed:
        (folder / name).write_bytes(bodies[url])
    (folder / "addresses.txt").write_text("\n".join(lines) + "\n\n", encoding="utf-8")
    return folder


def _agency_transport_bodies() -> dict[str, bytes]:
    bodies = agency_bodies()
    bodies[LANDING_URL] = b"<html>Invented landing.</html>"
    return bodies


def _batch(
    root: Path, source_id: str
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    cache = root / "data" / "public_cache" / source_id
    pointer = json.loads((cache / "loadable.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (cache / "manifests" / f"{pointer['manifest_sha256']}.json").read_text(
            encoding="utf-8"
        )
    )
    table = json.loads(
        (cache / "staging" / f"{manifest['table_sha256']}.json").read_text(
            encoding="utf-8"
        )
    )
    return pointer, manifest, table


def _log(root: Path) -> dict[str, object]:
    loaded = json.loads(
        (root / "data" / "public_cache" / "build-log.json").read_text(encoding="utf-8")
    )
    assert isinstance(loaded, dict)
    return loaded


def _fdi_entry() -> Entry:
    return _base(
        "fdi_projects",
        DASHBOARD_URL,
        "dashboard.invalid",
        ("fdi_projects",),
        ("fdi_estimates",),
        1,
        5000,
        "announced",
    )


def _agency_entry() -> Entry:
    return _base(
        "investqa_pages",
        LANDING_URL,
        "agency.invalid",
        ("pub_investqa_record", "pub_investqa_page"),
        (),
        6,
        500,
        "period",
    )


def _base(
    source_id: str,
    url: str,
    host: str,
    tables: tuple[str, ...],
    caveats: tuple[str, ...],
    low: int,
    high: int,
    period_field: str,
) -> Entry:
    return Entry(
        refetch=Cadence("none", "frequency_unconfirmed", ""),
        key=source_id,
        source_id=source_id,
        slug="",
        kind="terms_page",
        title_en="Invented investment source",
        publisher="National investment promotion agency",
        licence_id="publisher-terms",
        licence_basis="owner_decision",
        decision_record="0017",
        fetch_host=host,
        url=url,
        terms_url=TERMS_URL,
        nightly_live_fetch=True,
        public_splits=(),
        commit_allowed=False,
        release_tables=tables,
        caveat_keys=caveats,
        columns=(),
        row_count_min=low,
        row_count_max=high,
        period_first="2000",
        period_last="2000",
        period_field=period_field,
        reconciliation="none",
        skip_reason="",
        extension="html",
        landing_url=url,
        terms_words="Invented terms words",
        terms_read_on="2026-01-15",
        terms_watch=True,
        basis_note="Owner decision recorded for this planted row.",
    )


def _envelope() -> SourceEnvelope:
    return SourceEnvelope(
        source_id="fdi_projects",
        publisher="National investment promotion agency",
        page_url=DASHBOARD_URL,
        licence_id="publisher-terms",
        licence_basis="owner_decision",
        decision_record="0017",
        terms_sha256="ab" * 32,
        terms_url=TERMS_URL,
        retrieved_utc=RETRIEVED,
        page_sha256="cd" * 32,
        method="eii_custodian.publicdata.investment_parse.parse_fdi",
        method_version="1",
    )


def _quotation_row(body=None, language="en", **changes):
    from eii_custodian.publicdata.investment_agency import extract_page

    if body is None:
        body = _fixtures.quotation_page(language)
    values = dict(
        page_url=f"https://agency.invalid/{language}/invented-page",
        page_language=language,
        sequence=1,
        retrieved_on="2026-11-14",
        page_sha256=hashlib.sha256(body).hexdigest(),
        manifest_sha256=hashlib.sha256(body).hexdigest(),
        charset="",
        furniture=frozenset({"cookie"}),
    )
    values.update(changes)
    return extract_page(body, **values)


@pytest.mark.parametrize("language", ["en", "ar"])
def test_page_text_determinism_and_bilingual_roundtrip(language):
    body = _fixtures.quotation_page(language)
    first = _quotation_row(body, language)
    assert not isinstance(first, InvestmentFailure), first
    second = _quotation_row(body, language)
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=True)) == first
    assert first["page_text"].encode() == second["page_text"].encode()
    assert first["extractor"] == "investqa_page_text@1"
    assert first["page_key"] == "en_invented_page"
    assert set(first) == {
        "page_key",
        "page_language",
        "sequence",
        "page_title",
        "page_url",
        "retrieved_on",
        "page_sha256",
        "extractor",
        "page_text",
        "source_id",
    }
    lead = "Invented café" if language == "en" else "نص مخترع ١٢"
    assert first["page_text"] == (
        f"Invented title\n{lead} link tail.\nFirst inline last.\nSecond."
    )
    reordered = body.replace(
        b"<div>First <span>inline</span> last.</div><p>Second.</p>",
        b"<p>Second.</p><div>First <span>inline</span> last.</div>",
    )
    changed = _quotation_row(reordered, language)
    assert not isinstance(changed, InvestmentFailure)
    assert changed["page_text"] != first["page_text"]


@pytest.mark.parametrize(
    "plant,check",
    [
        ("eight", "page_identifier_shape"),
        ("eleven", "page_identifier_shape"),
        ("arabic_eight", "page_identifier_shape"),
        ("mixed_eight", "page_identifier_shape"),
        ("contact", "page_contact_shape"),
        ("telephone", "page_contact_shape"),
        ("telephone_plain", "page_contact_shape"),
        ("synthetic", "page_release_token"),
        ("canary", "page_release_token"),
    ],
)
def test_page_text_refusals_are_named(plant, check):
    tokens = {
        "eight": "7" * 8,
        "eleven": "7" * 11,
        "arabic_eight": chr(0x661) * 8,
        "mixed_eight": "7" * 4 + chr(0x6F1) * 4,
        "contact": "invented" + "@" + "example.invalid",
        "telephone": "+" + "7" * 3 + " " + "7" * 3 + " " + "7" * 4,
        "telephone_plain": "7" * 10,
        "synthetic": "SYN-" + "P-invented",
        "canary": "CANARY" + "_invented",
    }
    result = _quotation_row(
        _fixtures.quotation_page(extra=f"<div>{tokens[plant]}</div>")
    )
    assert isinstance(result, InvestmentFailure)
    assert result.check == check
    assert result.observed == "refused"  # Never echo the offending token.


@pytest.mark.parametrize(
    "changes,check",
    [
        ({"page_sha256": "ab" * 32}, "page_hash_mismatch"),
        ({"manifest_sha256": "ab" * 32}, "page_hash_mismatch"),
        ({"page_language": "ar"}, "page_language"),
        ({"extractor": "investqa_page_text@old"}, "page_extractor_version"),
    ],
)
def test_page_text_hash_language_and_version_refusals(changes, check):
    result = _quotation_row(**changes)
    assert isinstance(result, InvestmentFailure)
    assert result.check == check


@pytest.mark.parametrize(
    "plant,check",
    [
        ("text", "page_text_mismatch"),
        ("duplicate", "page_duplicate_key"),
        ("missing", "page_rows_missing"),
        ("version", "page_extractor_version"),
        ("language", "page_language"),
        ("extra_column", "page_columns"),
    ],
)
def test_page_release_reextracts_and_refuses_candidate(plant, check):
    from eii_custodian.publicdata.investment_build import validate_page_rows

    body = _fixtures.quotation_page()
    row = _quotation_row(body)
    assert not isinstance(row, InvestmentFailure)
    candidates = [dict(row)]
    if plant == "text":
        candidates[0]["page_text"] += " edited"
    elif plant == "duplicate":
        candidates.append(dict(row))
    elif plant == "missing":
        candidates.clear()
    elif plant == "version":
        candidates[0]["extractor"] = "investqa_page_text@old"
    elif plant == "language":
        candidates[0]["page_language"] = "ar"
    else:
        candidates[0]["invented"] = "extra"
    failure = validate_page_rows(candidates, [row])
    assert isinstance(failure, InvestmentFailure)
    assert failure.check == check


def test_page_rows_contribute_source_only_public_totals():
    from eii_custodian.publicdata.investment_build import page_public_totals

    rows = [_quotation_row(language=language) for language in ("en", "ar")]
    entries = page_public_totals(rows)
    assert len(entries) == len(rows)
    for row, entry in zip(rows, entries, strict=True):
        key = json.dumps(
            {name: row[name] for name in ("page_key", "page_language")},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        assert entry["public_total_id"] == "row:pub_investqa_page:" + key
        assert entry["status"] == "not_applicable"
        assert entry["reason"] == "source_only"
        assert entry["source_id"] == row["source_id"]
        assert entry["selectors"] == {
            "page_key": row["page_key"],
            "page_language": row["page_language"],
        }


@pytest.mark.parametrize(
    "plant,check",
    [
        ("encoding", "page_decode"),
        ("bad_encoding", "page_decode"),
        ("language", "page_language"),
        ("truncated", "page_truncated"),
        ("region", "page_truncated"),
        ("sequence", "page_sequence"),
    ],
)
def test_page_extractor_refuses_incomplete_source(plant, check):
    body = _fixtures.quotation_page()
    changes = {}
    if plant == "encoding":
        body = body.replace(b'<meta charset="utf-8">', b"")
    elif plant == "bad_encoding":
        body = body.replace(b"utf-8", b"invented-encoding")
    elif plant == "language":
        body = body.replace(b'lang="en"', b"")
    elif plant == "truncated":
        body = body.replace(b"</main>", b"")
    elif plant == "region":
        body = body.replace(b"<main>", b"<article>").replace(b"</main>", b"</article>")
    else:
        changes["sequence"] = True
    result = _quotation_row(body, **changes)
    assert isinstance(result, InvestmentFailure)
    assert result.check == check


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_page_encoding_bom_precedes_receipt_and_meta(encoding):
    body = _fixtures.quotation_page().decode().encode(encoding)
    result = _quotation_row(body, charset="invented-encoding")
    expected = _quotation_row()
    assert not isinstance(result, InvestmentFailure)
    assert result["page_text"] == expected["page_text"]


def test_page_receipt_charset_precedes_meta():
    body = _fixtures.quotation_page().replace(b"utf-8", b"invented-encoding")
    result = _quotation_row(body, charset="utf-8")
    assert not isinstance(result, InvestmentFailure)
    assert result["page_text"] == _quotation_row()["page_text"]


def test_agency_registry_declares_page_release_beside_unchanged_records():
    from eii_custodian.publicdata.investment_contracts import SCHEMA_AGENCY

    entry = next(row for row in load_registry() if row.source_id == "investqa_pages")
    assert entry.release_tables == ("pub_investqa_record", "pub_investqa_page")
    assert SCHEMA_AGENCY == "pub_investqa_record.v1"
    assert entry.commit_allowed is False
    assert entry.refetch.value == "daily"
