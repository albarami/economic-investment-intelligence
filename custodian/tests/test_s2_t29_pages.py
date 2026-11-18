"""Synthetic table pages exercise the dated archive and evidence holds."""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_publicdata_behaviour import _entry

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response

URL = "https://www.data.gov.qa/syn-page"
STAMP = "2024-02-03T00:00:00Z"
BODY = b'<table id="syn"><tr><th>syn_name</th><th>syn_count</th></tr><tr><td>SYN-item</td><td>7</td></tr></table>'


def page_entry():
    return replace(
        _entry(),
        key="events_visit_qatar",
        source_id="events_visit_qatar",
        kind="public_page",
        url=URL,
        fetch_host="www.data.gov.qa",
        columns=(("syn_name", "string"), ("syn_count", "integer")),
        row_count_min=None,
        row_count_max=None,
        commit_allowed=False,
        period_first="",
        period_last="",
        period_field="",
        terms_url="",
        extension="html",
    )


def review(entry=None):
    row = entry or page_entry()
    return {
        "url": URL,
        "reviewed_urls": [URL],
        "table_id": "syn",
        "columns": [[name, kind] for name, kind in row.columns],
        "as_of": "2024-02-03",
        "period": "2024",
        "bounds_basis": "unconfirmed",
        "pin": "[LEAD: evidence 2]",
        "profile": "[LEAD: evidence 3]",
    }


def test_registry_sources_and_receipts():
    from eii_custodian.publicdata.fetch.page_records import (
        SOURCES,
        load_declaration,
    )

    rows = {e.source_id: e for e in load_registry()}
    for source in SOURCES:
        assert source in rows
        row = rows[source]
        assert not row.commit_allowed and row.licence_basis == "owner_decision"
        assert row.row_count_min is None and row.row_count_max is None
        declaration = load_declaration(source)
        assert declaration["version"] == 2 and declaration["evidence"]
        assert declaration["max_bytes"] is None
        assert declaration["hold"] is not None or declaration["kind"] == "refusal"


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("basis", "receipt_missing"),
        ("commit", "commit_refused"),
        ("columns", "schema_missing"),
        ("date", "snapshot_date_missing"),
        ("offhost", "blocked_host"),
        ("bounds", "bounds_unconfirmed"),
        ("types", "schema_missing"),
        ("count", "row_count"),
    ],
)
def test_page_guards_before_publication(tmp_path, plant, reason):
    from eii_custodian.publicdata.fetch.page_records import PageError, fetch_page

    row, declaration, body = page_entry(), review(), BODY
    if plant == "basis":
        row = replace(row, licence_basis="")
    if plant == "commit":
        row = replace(row, commit_allowed=True)
    if plant == "columns":
        body = BODY.replace(b"syn_name", b"syn_changed")
    if plant == "date":
        declaration["as_of"] = ""
    if plant == "offhost":
        declaration["url"] = "https://example.invalid/syn-page"
    if plant == "bounds":
        row = replace(row, row_count_min=1, row_count_max=1)
    if plant == "types":
        body = BODY.replace(b">7<", b">SYN-wrong<")
    if plant == "count":
        row = replace(row, row_count_min=2, row_count_max=2)
        declaration["bounds_basis"] = "observed"
    with pytest.raises(PageError, match=reason):
        fetch_page(
            row,
            lambda url: Response(url, body, ()),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=declaration,
        )
    assert not list(tmp_path.rglob("index/*.json"))


def test_page_snapshot_selected_history(tmp_path):
    from eii_custodian.publicdata.fetch.page_records import fetch_page, selected_page
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    row = page_entry()
    first = fetch_page(
        row,
        lambda url: Response(url, BODY, ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=review(),
    )
    second = fetch_page(
        row,
        lambda url: Response(url, BODY.replace(b">7<", b">9<"), ()),
        tmp_path,
        lambda: "2024-02-04T00:00:00Z",
        lambda _: None,
        declaration=review(),
    )
    assert first.sha256 != second.sha256
    with pytest.raises(ValueError, match="snapshot_selection_invalid"):
        selected_page(tmp_path, row)
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: first.sha256}))
    selected = selected_page(tmp_path, row)
    payload = json.loads(selected.body)
    assert payload["rows"][0]["syn_count"] == 7
    assert payload["as_of"] == "2024-02-03"
    raw = read_snapshot(tmp_path / row.key / "raw", payload["raw_identity"])
    assert payload["page_sha256"] == raw.sha256
    raw.path.write_bytes(b"SYN-tamper")
    with pytest.raises(SnapshotError, match="snapshot_hash_mismatch"):
        selected_page(tmp_path, row)


@pytest.mark.parametrize(
    "source,claim",
    [
        ("events_visit_qatar", "complete_events"),
        ("events_qncc", "close_N4"),
        ("schools_private_directory", "capacity"),
        ("schools_private_directory", "enrolment"),
        ("schools_private_directory", "catchment"),
        ("schools_private_directory", "press_seats"),
        ("suppliers_tawteen", "inferred_certification"),
        ("manateq_tariffs", "close_N6"),
        ("awards_owner_scrape", "turnover"),
        ("awards_owner_scrape", "sales"),
        ("awards_owner_scrape", "official_table"),
        ("awards_owner_scrape", "all_state_awards"),
    ],
)
def test_snapshot_claim_limits(source, claim):
    from eii_custodian.publicdata.fetch.page_records import validate_claim

    with pytest.raises(ValueError, match="unsupported_source_claim"):
        validate_claim(source, claim)


def test_public_split_uses():
    from eii_custodian.publicdata.additions.split_policy import UseRequest
    from eii_custodian.publicdata.fetch.page_records import validate_use

    base = UseRequest(
        "syn_table",
        (("insurance_tables", ("nationality",)),),
        "public_display",
        "source",
        "source",
        "public",
    )
    validate_use(base)
    for target in ("worker", "residence", "company"):
        for field in ("join_to", "segments"):
            with pytest.raises(ValueError):
                validate_use(replace(base, **{field: target}))
    for field in ("apportions", "combines_protected", "person_key"):
        with pytest.raises(ValueError):
            validate_use(replace(base, **{field: True}))


def test_gis_hold_and_premature_removal(tmp_path):
    import yaml

    from eii_custodian.publicdata.fetch.registry import RegistryError, registry_path

    document = yaml.safe_load(registry_path().read_text())
    for key in ("gis_boundaries", "gis_imagery_history"):
        row = next(r for r in document["sources"] if r["key"] == key)
        assert row["skip_reason"] == "schema_unconfirmed"
        assert row["url"].startswith("https://services.gisqatar.org.qa/")
        row["skip_reason"] = ""
        path = tmp_path / "syn-registry.yaml"
        path.write_text(yaml.safe_dump(document))
        with pytest.raises(RegistryError, match="paged_layer requires layer"):
            load_registry(path)
        row["skip_reason"] = "schema_unconfirmed"
        path.write_text(yaml.safe_dump(document))
        assert load_registry(path)


def test_new_source_cadences():
    from eii_custodian.publicdata.fetch.cadence import parse_cadence

    pairs = {
        "events_visit_qatar": ("event_pages", "daily"),
        "events_qncc": ("event_pages", "daily"),
        "suppliers_tawteen": ("supplier_credentials", "weekly"),
        "monaqasat_classified": ("supplier_credentials", "weekly"),
        "awards_owner_scrape": ("award_reports", "weekly"),
    }
    entries = {e.key: e for e in load_registry()}
    for source, (family, cadence) in pairs.items():
        assert (entries[source].refetch.family, entries[source].refetch.value) == (
            family,
            cadence,
        )
        with pytest.raises(ValueError, match="cadence_family_assignment"):
            parse_cadence(
                {"value": cadence, "family": family, "evidence": "SYN-review"},
                source_id="SYN-other",
            )
        with pytest.raises(ValueError, match="cadence_family_assignment"):
            parse_cadence(
                {"value": "none", "reason": "frequency_unconfirmed"}, source_id=source
            )


def test_build_public_page_dispatch(tmp_path, monkeypatch):
    from commands import build_public
    from eii_custodian.publicdata.fetch import page_records

    row = page_entry()
    monkeypatch.setattr(build_public, "load_registry", lambda: (row,))
    monkeypatch.setattr(page_records, "load_declaration", lambda source: review(row))
    assert (
        build_public.run(
            tmp_path,
            {},
            [],
            transport=lambda url: Response(url, BODY, ()),
            sleep=lambda _: None,
        )
        == 1
    )
    cache = tmp_path / "data/public_cache"
    assert "snapshot_selection_invalid" in (cache / "build-log.json").read_text()
    assert list((cache / row.key / "index").glob("*.json"))


def test_missing_page_receipt(tmp_path):
    from eii_custodian.publicdata.fetch.page_records import parse_page_snapshot
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    raw = publish_snapshot(
        tmp_path,
        "html",
        BODY,
        {
            "source_id": "events_visit_qatar",
            "key": "events_visit_qatar",
            "retrieved_utc": STAMP,
        },
    )
    with pytest.raises(ValueError, match="receipt_missing"):
        parse_page_snapshot(raw, page_entry(), review())


@pytest.mark.parametrize(
    "column", ["capacity", "enrolment", "catchment", "press_seats"]
)
def test_school_forbidden_columns_on_real_parser(tmp_path, column):
    from eii_custodian.publicdata.fetch.page_records import parse_body

    row = replace(
        page_entry(),
        source_id="schools_private_directory",
        columns=((column, "integer"),),
    )
    body = f'<table id="syn"><tr><th>{column}</th></tr><tr><td>7</td></tr></table>'.encode()
    with pytest.raises(ValueError, match="unsupported_source_claim"):
        parse_body(body, row, review(row))


def test_page_kind_cannot_bypass_context(tmp_path):
    from eii_custodian.publicdata.fetch.kinds import prepare

    row = page_entry()

    def forbidden(url):
        pytest.fail("page bypassed reviewed dispatch")

    prepared = prepare(row, forbidden, lambda _: None, cache=tmp_path)
    assert prepared.failure.check == "build_context_required"


def test_page_cache_symlink_refused(tmp_path):
    from eii_custodian.publicdata.fetch.page_records import fetch_page

    cache = tmp_path / "syn-cache"
    cache.mkdir()
    other = tmp_path / "syn-other"
    other.mkdir()
    (cache / page_entry().key).symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="cache_path_refused"):
        fetch_page(
            page_entry(),
            lambda url: Response(url, BODY, ()),
            cache,
            lambda: STAMP,
            lambda _: None,
            declaration=review(),
        )
    assert not list(other.iterdir())


def test_page_terms_archived_with_receipt(tmp_path):
    from eii_custodian.publicdata.fetch.page_records import fetch_page
    from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256

    terms_url = "https://www.data.gov.qa/syn-terms"
    terms = b"<p>SYN-terms</p>"
    row = replace(page_entry(), terms_url=terms_url)
    calls = []

    def transport(url):
        calls.append(url)
        return Response(url, terms if url == terms_url else BODY, ())

    result = fetch_page(
        row, transport, tmp_path, lambda: STAMP, lambda _: None, declaration=review()
    )
    assert result.sidecar["terms_sha256"] == terms_text_sha256(terms)
    assert calls == [URL, terms_url]
    assert list((tmp_path / row.key / "terms" / "index").glob("*.json"))


@pytest.mark.parametrize("field", ["as_of", "period"])
def test_partial_declaration_keeps_evidence_hold(tmp_path, field):
    import yaml

    from eii_custodian.publicdata.fetch.page_records import PageError, load_declaration

    declaration = review()
    declaration[field] = "[LEAD: evidence 1]"
    path = tmp_path / "review.yaml"
    path.write_text(yaml.safe_dump({"sources": {page_entry().source_id: declaration}}))
    with pytest.raises(PageError, match=r"^page_evidence_pending$"):
        load_declaration(page_entry().source_id, path)
