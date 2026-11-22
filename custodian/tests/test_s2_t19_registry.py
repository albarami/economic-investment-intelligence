"""Closed S2-T19 source list: PUB-105, PUB-108 and live rulings LR-G/P/T."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root
from custodian.tests.support.fetch_build import run_build

from eii_custodian.publicdata.fetch.allowlist import ALLOWED_HOSTS, approve
from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import (
    COLLECTED_FAMILIES,
    RegistryError,
    load_registry,
)
from eii_custodian.publicdata.fetch.snapshots import checked_times, read_snapshot
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.singles.families import family_table_name

REPO = repository_root(Path(__file__))
EXPECTED = frozenset(
    {
        "bank_credit_act/local-banks-credit-by-economic-activity",
        "dcool_capacity/design-cooling-capacity-by-status-municipality-and-sector-tr",
        "trade_ext/qatar-export-statistics-2019-2024",
        "trade_ext/qatar-imports-2014-2018",
        "trade_ext/imports-by-nature-of-items-and-year",
        "trade_ext/imports-by-utilization-of-items-and-year",
        "survey_ext/hotels-and-restaurants-statistics-production-value-by-type-of-revenue-and-main-economic-activity",
        "survey_ext/hotels-and-restaurants-statistics-transformational-revenues-by-revenue-item-and-main-activity",
        "survey_ext/hotels-and-restaurants-statistics-transformational-revenues-by-revenue-item-and-main-activity0",
        "survey_ext/production-value-hotels-and-restaurants-type-of-revenue-and-main-economic-activity-less-10-employees",
        "survey_ext/production-value-of-hotels-and-restaurants-type-revenue-economic-activity-10-employees-and-more",
        "survey_ext/revenues-hotels-restaurants-current-activity-by-revenue-item-and-main-activity-10-employees-and-more",
        "survey_ext/revenues-of-current-activity-by-revenue-item-and-main-activity-hotels-and-restaurants",
        "survey_ext/transformational-revenues-by-revenue-item-and-main-activity-establishments-with-10-employees-or-more",
        "price_ext/producer-price-index-ppi",
        "price_ext/producer-price-index-ppi-by-activity-monthly",
        "price_ext/machinery-and-equipment-price-index-mepi",
        "hotel_ext/number-of-hotels-by-hotel-class",
        "hotel_ext/number-of-hotel-rooms-by-hotel-class",
        "hotel_ext/number-of-hotel-beds-by-hotel-class",
        "hotel_ext/number-of-hotels-rooms-and-beds-by-hotel-type",
        "hotel_ext/number-of-hotel-guests-and-nights-of-stay-by-month",
        "hotel_ext/number-of-hotel-guests-and-nights-of-stay-by-nationality",
        "talent_ext/education-statistics-number-of-graduates-of-private-colleges-and-universities-by-educational",
        "talent_ext/education-statistics-number-of-graduates-of-public-colleges-and-universities-by-academic-degree",
        "talent_ext/education-statistics-number-of-graduates-of-public-colleges-and-universities-by-educational",
        "talent_ext/education-statistics-number-of-graduates-on-scholarships-abroad-by-field-of-study-and-gender",
        "talent_ext/total-students-on-scholarships-at-home-and-abroad-by-degree-and-gender",
        "talent_ext/trainees-at-the-private-training-centers-by-field-of-training-gender-nationality-and-age-groups",
        "talent_ext/trainees-at-the-private-training-centers-by-employment-status-gender-nationality-and-field-of",
        "jobseekers/qatari-unemployed-15-by-gender-and-willingness-to-work-quarterly",
        "jobseekers/qatari-unemployed-15-not-willing-to-work-by-reason-quarterly",
        "jobseekers/qatari-unemployed-15-with-secondary-education-and-training-quarterly",
        "jobseekers/unemployed-qataris-15-years-and-above-by-gender-and-whether-offered-work-in-private-sector",
        "jobseekers/unemployed-qataris-15-years-and-above-by-gender-and-willingness-to-work-in-private-sector",
        "jobseekers/unemployed-qataris-15-years-and-above-with-secondary-education-who-attended-training-programs-by",
        "jobseekers/unemployed-qataris-less-than-secondary-by-gender-and-readiness-to-train-for-craft-work0",
        "jobseekers/unemployed-qataris-not-willing-to-work-in-the-private-sector-by-gender-and-reasons",
        "jobseekers/unemployed-qataris-with-secondary-education-and-training-courses-refusing-work-in-private-sector-by",
        "utilities_ext/total-electricity-consumption-by-sectors",
        "utilities_ext/total-water-consumption-by-sectors",
        "utilities_ext/sectoral-electricity-consumption-mwh",
        "utilities_ext/operational-peak-district-cooling-load",
        "coverage_ext/electricity-network-coverage",
        "coverage_ext/electricity-network-coverage-by-municipality",
        "coverage_ext/water-supply-coverage",
        "coverage_ext/water-supply-coverage-by-municipality",
        "coverage_ext/proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender",
        "coverage_ext/proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender-and-municipality",
        "coverage_ext/sdg-9-c-1-proportion-of-population-covered-by-a-mobile-network-by-technology",
        "fdi_stats/foreign-direct-investment",
        "fdi_stats/sdg-17-3-1-foreign-direct-investment-inflows",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-daayen-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-khor-and-al-thakhira",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-rayyan-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-shahhaniya-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-shamal-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-al-wakrah-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-doha-municipality",
        "completions_ext/building-completion-certificates-issued-by-type-of-certificate-and-month-umm-slal-municipality0",
        "gis_land_price",
        "gis_rail",
        "gis_phcc",
        "gis_landmarks",
        "gis_locator",
        "gis_zoning",
        "gis_address",
        "gis_parcels",
        "gis_poi_comm",
        "gis_boundaries",
        "gis_context",
        "gis_imagery_history",
        "tenders_pub",
    }
)


def test_all_s2_t19_sources_are_registered():
    entries = load_registry(REPO / "custodian/publicdata/sources.yaml")
    actual = {entry.key for entry in entries}
    assert EXPECTED <= actual, f"missing S2-T19 rows: {sorted(EXPECTED - actual)}"


def test_older_imports_keep_counts_with_evidenced_text_years():
    entries = {entry.key: entry for entry in load_registry()}
    entry = entries["trade_ext/qatar-imports-2014-2018"]
    assert (entry.row_count_min, entry.row_count_max) == (644486, 644486)
    assert (entry.period_field, entry.period_first, entry.period_last) == (
        "sit=row;form=year_text;field=year",
        "2014",
        "2018",
    )


def test_absent_layer_needs_no_invented_id(tmp_path):

    document = yaml.safe_load((REPO / "custodian/publicdata/sources.yaml").read_text())
    row = next(r for r in document["sources"] if r["kind"] == "paged_layer")
    row.pop("layer")
    row["skip_reason"] = "direct_url_unconfirmed"
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    assert load_registry(path)[0].layer is None


def test_live_layer_still_requires_id(tmp_path):

    document = yaml.safe_load((REPO / "custodian/publicdata/sources.yaml").read_text())
    row = next(r for r in document["sources"] if r["kind"] == "paged_layer")
    row.pop("layer")
    row["skip_reason"] = ""
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match="paged_layer requires layer"):
        load_registry(path)


def _block():

    text = (REPO / "custodian/publicdata/sources.yaml").read_text()
    assert "# BEGIN S2-T19 sources" in text, "missing S2-T19 rows block"
    block = text.split("# BEGIN S2-T19 sources\n", 1)[1].split(
        "# END S2-T19 sources", 1
    )[0]
    return yaml.safe_load(block)


def test_exact_block_and_metadata():

    rows = _block()
    assert {row["key"] for row in rows} == EXPECTED
    assert len(rows) == len(EXPECTED)
    entries = {
        e.key: e for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
    }
    for row in rows:
        entry = entries[row["key"]]
        assert entry.publisher and entry.title_en
        assert entry.terms_words and entry.terms_read_on
        assert entry.skip_reason in {"", "schema_unconfirmed"}
        assert not entry.commit_allowed
        if entry.key in {"gis_boundaries", "gis_imagery_history"}:
            assert approve(entry.url).ok and entry.layer is None
            assert entry.skip_reason == "schema_unconfirmed"
        else:
            assert approve(entry.url).ok
            assert entry.skip_reason == ""
        if entry.source_id.startswith("gis_") or entry.source_id == "tenders_pub":
            assert entry.licence_basis == "owner_decision"
            assert entry.decision_record == "0026"
        else:
            assert entry.columns and entry.row_count_min == entry.row_count_max
            assert entry.licence_basis == (
                "portal_terms"
                if entry.slug == "producer-price-index-ppi"
                else "dataset"
            )
            if entry.source_id in COLLECTED_FAMILIES:
                assert entry.release_tables == (family_table_name(entry.source_id),)
            elif entry.source_id not in {"bank_credit_act", "dcool_capacity"}:
                assert entry.release_tables == ()
        assert entry.terms_read_on == (
            "2026-11-14" if entry.source_id == "tenders_pub" else "2026-11-15"
        )


def test_exact_hosts_and_pack_list():

    baseline = {
        "www.data.gov.qa",
        "www.data.qa",
        "services7.arcgis.com",
        "data.humdata.org",
        "s3.us-east-1.amazonaws.com",
        "www.geoboundaries.org",
        "github.com",
        "raw.githubusercontent.com",
        "stac.overturemaps.org",
        "overturemaps-us-west-2.s3.us-west-2.amazonaws.com",
        "download.openstreetmap.fr",
        "unstats.un.org",
        "data.worldpop.org",
        "web.archive.org",
        "fdiprojects.invest.qa",
        "www.invest.qa",
        "data.source.coop",
        "archive-api.open-meteo.com",
        "ladsweb.modaps.eosdis.nasa.gov",
        "ndownloader.figshare.com",
        "download.geoservice.dlr.de",
        "44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com",
        "besttime.app",
        "www.cepii.fr",
    }
    added = {
        "eservices.qfc.qa",
        "www.qfc.qa",
        "services.gisqatar.org.qa",
        "monaqasat.mof.gov.qa",
        "www.qcb.gov.qa",
        "visitqatar.com",
        "www.qncc.qa",
        "manateq.qa",
        "www.edu.gov.qa",
        "myschool.edu.gov.qa",
        "myschools.edu.gov.qa",
        # S2-P53-cit: reviewed citation page and terms hosts.
        "dezzzme.wordpress.com",
        "en.wikiarquitectura.com",
        "en.wikipedia.org",
        "foundation.wikimedia.org",
        "inside.fifa.com",
        "megatalls.com",
        "nabkmastclimber.com",
        "qm.org.qa",
        "skyscraperpage.com",
        "stadiumdb.com",
        "www.businessdestinations.com",
        "www.scraperbase.com",
        "www.skyscrapercenter.com",
        "www.thenationalnews.com",
        "www.wernersobek.com",
    }
    assert ALLOWED_HOSTS == baseline | added
    pub03 = next(
        line
        for line in (REPO / "docs/04_PUBLIC_DATA_PACK.md").read_text().splitlines()
        if line.startswith("| PUB-03 |")
    )
    for host in added:
        assert f"`{host}`" in pub03


def test_tender_kind_and_pin_load(tmp_path):

    document = yaml.safe_load((REPO / "custodian/publicdata/sources.yaml").read_text())
    row = next(
        item for item in document["sources"] if item["source_id"] == "tenders_pub"
    ).copy()
    row.update(chain_intermediate_sha256="a" * 64)
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    assert load_registry(path)[0].chain_intermediate_sha256 == "a" * 64


def test_tender_bad_pin_refused(tmp_path):

    document = yaml.safe_load((REPO / "custodian/publicdata/sources.yaml").read_text())
    row = document["sources"][0].copy()
    row.update(kind="paged_cards", chain_intermediate_sha256="invented-bad-pin")
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(
        RegistryError, match="chain_intermediate_sha256 is not a SHA-256"
    ):
        load_registry(path)


FAMILIES = frozenset(
    {
        "trade_ext",
        "survey_ext",
        "price_ext",
        "hotel_ext",
        "talent_ext",
        "jobseekers",
        "utilities_ext",
        "coverage_ext",
        "fdi_stats",
        "completions_ext",
    }
)


def _period_column(period_field: str) -> str:
    """The published column a period rule names. A bare field is that column."""
    if "form=" not in period_field:
        return period_field
    from eii_custodian.publicdata.additions.common import parse_period_rule

    return parse_period_rule(period_field).field


def _fixture_entry():

    original = next(
        e
        for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
        if e.source_id == "trade_ext"
    )
    return replace(
        original,
        key="trade_ext/invented",
        slug="invented",
        publisher="Invented publisher",
        url="https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/invented/exports/json",
        columns=(("year", "string"), ("value", "number")),
        row_count_min=2,
        row_count_max=2,
        period_first="2020-01-01",
        period_last="2021-01-01",
        period_field="sit=row;form=date;field=year",
        terms_url="",
    )


def _transport(entry, records):

    def transport(url):
        payload = (
            records
            if url == entry.url
            else {
                "metas": {
                    "default": {
                        "publisher": entry.publisher,
                        "license": entry.licence_id,
                        "modified": "2030-01-01",
                    }
                }
            }
        )
        if url != entry.url and entry.licence_id == "CC-BY-4.0":
            payload["metas"]["default"].update(
                license="CC BY",
                license_url="https://creativecommons.org/licenses/by/4.0/",
            )
        return Response(final_url=url, body=json.dumps(payload).encode(), hops=())

    return transport


def test_family_sex_column_without_declaration_stores_nothing(tmp_path):

    entry = _fixture_entry()
    records = [
        {"year": "2020-01-01", "value": 1, "sex": "invented"},
        {"year": "2021-01-01", "value": 2, "sex": "invented"},
    ]
    failure = fetch_entry(
        entry,
        _transport(entry, records),
        tmp_path,
        lambda: "2026-11-15T00:00:00Z",
        lambda _: None,
    )
    assert failure is not None, "undeclared Public sex split reached cache"
    assert failure.check == "public_split_undeclared"
    assert list(tmp_path.iterdir()) == []


def test_family_receipt_uses_observed_period_not_modified_date(tmp_path):

    entry = _fixture_entry()
    records = [{"year": "2022-01-01", "value": 1}, {"year": "2023-01-01", "value": 2}]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert (receipt["period_first"], receipt["period_last"]) == (
        "2022-01-01",
        "2023-01-01",
    )
    assert receipt["source_modified"] == "2030-01-01"


def test_each_family_cache_and_receipt_preserve_published_shape(tmp_path):
    """Invented values in the B2-declared shapes; no publisher response is copied."""

    from eii_custodian.publicdata.additions.common import parse_period_rule

    for original in load_registry(REPO / "custodian/publicdata/sources.yaml"):
        if original.source_id not in FAMILIES:
            continue
        record = {
            name: {
                "string": "invented",
                "number": 2.5,
                "integer": 2,
                "object": {"invented": "shape"},
            }[kind]
            for name, kind in original.columns
        }
        # Small invented counts replace catalogue counts only in this fixture.
        entry = replace(
            original,
            publisher="Invented publisher",
            row_count_min=1,
            row_count_max=1,
            period_first="",
            period_last="",
            terms_url="",
        )
        column = _period_column(entry.period_field)
        published = (
            "form=" in entry.period_field
            and parse_period_rule(entry.period_field).form == "published_label"
        )
        # S2-T08 part B mismatch 2 and S2-P38's separately evidenced imports
        # export: annual-text fixtures carry a four-digit year.
        annual = (
            "form=" in entry.period_field
            and parse_period_rule(entry.period_field).form == "year_text"
        )
        label = "2020" if annual else "2020-01-01"
        if column:
            record[column] = label
        records = [record]
        assert (
            fetch_entry(
                entry,
                _transport(entry, records),
                tmp_path,
                lambda: "2026-11-15T00:00:00Z",
                lambda _: None,
            )
            is None
        )
        directory = tmp_path / entry.key
        sidecar = next(directory.glob("*.meta.json"))
        receipt = json.loads(sidecar.read_text())
        body = directory / (receipt["sha256"] + ".json")
        assert json.loads(body.read_text()) == records
        assert receipt["sha256"] == hashlib.sha256(body.read_bytes()).hexdigest()
        assert receipt["retrieved_utc"] == "2026-11-15T00:00:00Z"
        assert receipt["release_tables"] == [family_table_name(original.source_id)]
        assert receipt["public_splits"] == list(entry.public_splits)
        assert receipt["terms_words"] == entry.terms_words
        assert receipt["terms_read_on"] == entry.terms_read_on
        if published:
            # M1: published_label computes no bound. The receipt counts labels.
            assert receipt["period_first"] is None
            assert receipt["period_last"] is None
            assert receipt["coverage_note"] == "distinct labels 1"
        else:
            assert receipt["period_first"] == (label if column else None)
            assert receipt["period_last"] == receipt["period_first"]
        assert receipt["bytes"] == len(body.read_bytes())
        assert receipt["switched_off"] is False
    assert not list(tmp_path.rglob("*.parquet"))


def test_missing_basis_loads_as_pending(tmp_path):
    """Ruling L-1001: a row without the licence_basis key loads as pending."""

    row = _block()[0].copy()
    del row["licence_basis"]
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    entries = load_registry(path)
    assert entries[0].licence_basis == "pending"


def test_absent_prohibitive_and_unread_terms_stay_in_use(tmp_path):

    for i, words in enumerate(
        (
            "terms to be read",
            "Invented page states no reuse terms.",
            "Invented page prohibits reuse without permission.",
        )
    ):
        entry = replace(
            _fixture_entry(),
            terms_words=words,
            licence_basis="owner_decision",
            decision_record="0026",
            licence_id="",
        )
        records = [
            {"year": "2020-01-01", "value": 1},
            {"year": "2021-01-01", "value": 2},
        ]
        cache = tmp_path / str(i)
        assert (
            fetch_entry(
                entry,
                _transport(entry, records),
                cache,
                lambda: "2026-11-15T00:00:00Z",
                lambda _: None,
            )
            is None
        )
        receipt = json.loads(next(cache.rglob("*.meta.json")).read_text())
        assert receipt["terms_words"] == words
        assert receipt["terms_read_on"] == "2026-11-15"
        assert receipt["switched_off"] is False
        assert receipt["row_count"] == 2


def test_off_list_request_and_short_family_file_store_nothing(tmp_path):

    entry = _fixture_entry()

    def never(_url):
        raise AssertionError("off-list transport called")

    failure = fetch_entry(
        replace(entry, url="https://invented.invalid/data"),
        never,
        tmp_path,
        lambda: "unused",
        lambda _: None,
    )
    assert failure.check == "blocked_host"
    records = [{"year": "2021-01-01", "value": 1}]
    failure = fetch_entry(
        entry, _transport(entry, records), tmp_path, lambda: "unused", lambda _: None
    )
    assert failure.check == "row_count"
    assert list(tmp_path.iterdir()) == []


def test_existing_fetch_kinds_have_hashed_receipts(tmp_path):

    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    for kind in ("paged_layer", "https_file", "terms_page"):
        entry = replace(
            _fixture_entry(),
            kind=kind,
            key="invented-" + kind,
            source_id="invented",
            layer=0 if kind == "paged_layer" else None,
            columns=(),
            row_count_min=None,
            row_count_max=None,
            period_field="",
            period_first="",
            period_last="",
        )

        def transport(url):
            payload = (
                {"count": 1}
                if "returnCountOnly" in url
                else {"features": [{"attributes": {"invented": "value"}}]}
            )
            return Response(final_url=url, body=json.dumps(payload).encode(), hops=())

        assert (
            fetch_entry(
                entry,
                transport,
                fixture_cache,
                lambda: "2026-11-15T00:00:00Z",
                lambda _: None,
            )
            is None
        )
        receipt = json.loads(
            next((fixture_cache / entry.key).glob("*.meta.json")).read_text()
        )
        body = fixture_cache / entry.key / (receipt["sha256"] + ".json")
        assert receipt["sha256"] == hashlib.sha256(body.read_bytes()).hexdigest()
        assert receipt["retrieved_utc"] == "2026-11-15T00:00:00Z"
    citation = replace(entry, kind="citation_only", key="invented-citation")

    def never(_url):
        raise AssertionError("citation called transport")

    assert (
        run_build(
            [citation],
            never,
            fixture_cache,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        ).failure
        is None
    )
    receipt = json.loads((fixture_cache / citation.key / "citation.json").read_text())
    assert receipt["sha256"] == "CITATION_ONLY"
    assert receipt["retrieved_utc"] == "2026-11-15T00:00:00Z"


def test_split_tokens_and_declared_splits(tmp_path):

    for field, dimension in (
        ("gender", "sex"),
        ("qataris_female", "sex"),
        ("nationality", "nationality"),
        ("non_qataris", "nationality"),
    ):
        entry = _fixture_entry()
        # Isolate the tested missing dimension where a wide field contains both.
        other = ("nationality",) if dimension == "sex" else ("sex",)
        entry = replace(entry, public_splits=other)
        records = [
            {"year": "2020-01-01", "value": 1, field: "invented"},
            {"year": "2021-01-01", "value": 2, field: "invented"},
        ]
        cache = tmp_path / field
        failure = fetch_entry(
            entry,
            _transport(entry, records),
            cache,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        assert failure.check == "public_split_undeclared"
        assert not cache.exists()
        entry = replace(entry, public_splits=("sex", "nationality"))
        assert (
            fetch_entry(
                entry,
                _transport(entry, records),
                cache,
                lambda: "2026-11-15T00:00:00Z",
                lambda _: None,
            )
            is None
        )


def test_confirmation_matches_registered_not_fetched_states():

    path = REPO / "custodian/publicdata/review/s2_t19_confirmation.yaml"
    assert path.is_file(), "S2-T19 confirmation record missing"
    document = json.loads(path.read_text())
    assert set(document) == {"task", "review_ref", "sources"}
    assert document["task"] == "S2-T19" and document["review_ref"]
    entries = {
        e.key: e for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
    }
    sources = document["sources"]
    assert {row["key"] for row in sources} == EXPECTED
    assert len(sources) == len(EXPECTED)
    fields = {
        "key",
        "outcome",
        "review_ref",
        "terms_words",
        "terms_read_on",
        "licence_basis",
        "skip_reason",
        "retrieved_utc",
        "sha256",
        "note",
    }
    for row in sources:
        assert set(row) == fields
        entry = entries[row["key"]]
        assert row["outcome"] == (
            "absent" if entry.skip_reason else "registered_not_fetched"
        )
        assert row["retrieved_utc"] is None and row["sha256"] is None
        for field in ("terms_words", "terms_read_on", "licence_basis", "skip_reason"):
            if field == "skip_reason" and entry.key in {
                "gis_boundaries",
                "gis_imagery_history",
            }:
                # Preserve the earlier confirmation as history; S2-T29 only confirms URLs.
                assert row[field] == "direct_url_unconfirmed"
                assert entry.skip_reason == "schema_unconfirmed" and entry.layer is None
            else:
                assert row[field] == getattr(entry, field)
        assert row["review_ref"] and row["note"]


def test_contract_revisions_and_terms_are_documented():
    doc = (REPO / "docs/03_DATA_CONTRACTS.md").read_text()
    assert "`source_layer`" in doc
    assert "`buying_entity_ar`" in doc
    assert "`text_cleaned`" in doc
    assert "`STARTDATE`" in doc and "`ENDDATE`" in doc
    pack = (REPO / "docs/04_PUBLIC_DATA_PACK.md").read_text()
    assert (
        "registered in S2-T19; first call by the task that has numbers to resolve"
        in pack
    )
    for entry in load_registry(REPO / "custodian/publicdata/sources.yaml"):
        if entry.key in EXPECTED and entry.terms_words != "terms to be read":
            assert entry.terms_words in pack


# Schema and count observations: lead portal reading 2026-11-15; B2 / LR-P1 to LR-P13.
PORTAL_DECLARATIONS = {
    "building-completion-certificates-issued-by-type-of-certificate-and-month": (
        "National Planning Council",
        72,
        "year:string month:string lshhr:string certificate_type:string nw_lshhd:string count:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-al-daayen-municipality": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-al-khor-and-al-thakhira": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-al-rayyan-municipality": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-al-shahhaniya-municipality": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-al-shamal-municipality": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-al-wakrah-municipality": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-doha-municipality": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "building-completion-certificates-issued-by-type-of-certificate-and-month-umm-slal-municipality0": (
        "National Planning Council",
        120,
        "year:string month:string lshhr:string type_of_certificate:string nw_lshhd:string number:integer",
    ),
    "design-cooling-capacity-by-status-municipality-and-sector-tr": (
        "National Planning Council",
        69,
        "year:string project_status:string municipality:string other:integer industrial:integer real_estate_development:integer sport:integer culture:string health:integer transport:integer education:integer hotels:integer commercial:integer district_cooling_service_supply:integer lbldy:string hl_lmshry:string geo_point:object geo_shape:object",
    ),
    "education-statistics-number-of-graduates-of-private-colleges-and-universities-by-educational": (
        "National Planning Council",
        56,
        "academic_year:string educational_institution:string educational_institution_arabic:string qataris_male:number qataris_female:number non_qataris_male:number non_qataris_female:number",
    ),
    "education-statistics-number-of-graduates-of-public-colleges-and-universities-by-academic-degree": (
        "National Planning Council",
        635,
        "academic_year:string academic_degree:string academic_degree_ar:string academic_program:string academic_program_ar:string educational_institution:string educational_institution_ar:string qataris_males:integer qataris_females:integer non_qataris_males:integer non_qataris_females:integer",
    ),
    "education-statistics-number-of-graduates-of-public-colleges-and-universities-by-educational": (
        "National Planning Council",
        550,
        "year:string college:string college_ar:string field_of_specialization:string field_of_specialization_ar:string qataris:string non_qataris:string",
    ),
    "education-statistics-number-of-graduates-on-scholarships-abroad-by-field-of-study-and-gender": (
        "National Planning Council",
        568,
        "year:string field_of_study:string field_of_study_ar:string gender:string lnw:string number_of_graduates:integer",
    ),
    "electricity-network-coverage": (
        "KAHRAMAA",
        7,
        "year:string electricity_network_coverage:number",
    ),
    "electricity-network-coverage-by-municipality": (
        "KAHRAMAA",
        56,
        "year:string municipality:string lbldy:string value:number",
    ),
    "foreign-direct-investment": (
        "National Planning Council",
        6,
        "period:string indicator:string lbyn:string value:number",
    ),
    "hotels-and-restaurants-statistics-production-value-by-type-of-revenue-and-main-economic-activity": (
        "National Planning Council",
        40,
        "year:string activity_code:integer main_economic_activity:string lnsht_lqtsdy_lry_ysy:string type_of_revenue:string nw_lyrdt:string production_value_value_in_1_000_qr:integer",
    ),
    "hotels-and-restaurants-statistics-transformational-revenues-by-revenue-item-and-main-activity": (
        "National Planning Council",
        126,
        "year:string main_activity:string lnsht_lry_ysy:string revenue_item:string bnwd_lyrdt_l_khr:string transformational_revenues_value_in_1_000_qr:integer",
    ),
    "hotels-and-restaurants-statistics-transformational-revenues-by-revenue-item-and-main-activity0": (
        "National Planning Council",
        162,
        "year:string revenue_item:string bnd_lyrdt:string main_activity:string lnsht_lry_ysy:string transformational_revenues_value_in_1_000_qr:number",
    ),
    "imports-by-nature-of-items-and-year": (
        "National Planning Council",
        30,
        "year:string nature_of_items:string tby_lmwd:string value:number",
    ),
    "imports-by-utilization-of-items-and-year": (
        "National Planning Council",
        30,
        "year:string utilization_of_items:string stkhdm_lmwd:string value:number",
    ),
    "local-banks-credit-by-economic-activity": (
        "National Planning Council",
        88,
        "year:string economic_activity:string lnsht_lqtsdy:string value:number",
    ),
    # S2-T08 part B source review, mismatch 6: the publisher's long form
    # replaced the wide LR-P7 reading.
    "machinery-and-equipment-price-index-mepi": (
        "National Planning Council",
        100,
        "year:string half_year:string nsf_lsn:string group_code:string group:string lmjmw:string weight:number index_value:number",
    ),
    "number-of-hotel-beds-by-hotel-class": (
        "National Planning Council",
        5,
        "year:string five_star:integer four_star:integer three_star:integer two_one_star:integer",
    ),
    "number-of-hotel-guests-and-nights-of-stay-by-month": (
        "National Planning Council",
        120,
        "month:string month_ar:string year:string sn:string value:number",
    ),
    "number-of-hotel-guests-and-nights-of-stay-by-nationality": (
        "National Planning Council",
        5,
        "year:string arab_nationalities_guests:integer arab_nationalities_nights:integer foreign_nationalities_guest:number foreign_nationalities_nights:integer",
    ),
    "number-of-hotel-rooms-by-hotel-class": (
        "National Planning Council",
        5,
        "year:string five_star:integer four_star:integer three_star:integer two_one_star:integer",
    ),
    "number-of-hotels-by-hotel-class": (
        "National Planning Council",
        5,
        "year:string five_star:integer four_star:integer three_star:integer two_one_star:integer",
    ),
    "number-of-hotels-rooms-and-beds-by-hotel-type": (
        "National Planning Council",
        32,
        "year:string hotel_class:string fy_lfndq:string number_of_hotels:integer number_of_rooms:integer number_of_beds:integer",
    ),
    "operational-peak-district-cooling-load": (
        "KAHRAMAA",
        6,
        "year:string district_cooling_plant_peak_cooling_load_in_tons_of_refrigeration:integer district_cooling_plant_installed_cooling_capacity_in_tons_of_refrigeration:integer",
    ),
    "producer-price-index-ppi": (
        "National Planning Council",
        1292,
        "year:string month:string lshhr:string basket_code:string item:string lbnd:string value:number",
    ),
    "producer-price-index-ppi-by-activity-monthly": (
        "National Planning Council",
        1224,
        "year:string month:string lshhr:string basket_code:string item:string lbnd:string ppi_index:number",
    ),
    "production-value-hotels-and-restaurants-type-of-revenue-and-main-economic-activity-less-10-employees": (
        "National Planning Council",
        40,
        "year:string activity_code:integer main_economic_activity:string lnsht_lqtsdy_lry_ysy:string type_of_revenue:string nw_lyrdt:string production_value_value_in_1_000_qr:integer",
    ),
    "production-value-of-hotels-and-restaurants-type-revenue-economic-activity-10-employees-and-more": (
        "National Planning Council",
        40,
        "year:string activity_code:integer main_economic_activity:string lnsht_lqtsdy_lry_ysy:string type_of_revenue:string nw_lyrdt:string production_value_value_in_1_000_qatari_riyals:integer",
    ),
    "proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender": (
        "Communications Regulatory Authority",
        24,
        "year:string gender:string ljns:string category:string lfy:string value:number",
    ),
    "proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender-and-municipality": (
        "Communications Regulatory Authority",
        192,
        "year:string municipality:string lbldy:string gender:string ljns:string category:string lfy:string value:number",
    ),
    "qatar-export-statistics-2019-2024": (
        "National Planning Council",
        142720,
        "year:string quarter:string month:integer hs4:integer ltfsyl:string details:string dwl_lmqsd:string country_of_destination:string quantity:integer weight_kg:integer value_qr:integer",
    ),
    "qatar-imports-2014-2018": (
        "National Planning Council",
        644486,
        "year:string quarter:string month:integer hs8:integer ltfsyl:string details:string dwl_lmnsh:string country_of_origin:string quantity:integer weight_kg:integer value_qr:number",
    ),
    "qatari-unemployed-15-by-gender-and-willingness-to-work-quarterly": (
        "National Planning Council",
        128,
        "year:string quarter:string willingness_to_work:string lrgb_ll_ml:string gender:string ljns:string number:integer",
    ),
    "qatari-unemployed-15-not-willing-to-work-by-reason-quarterly": (
        "National Planning Council",
        121,
        "year:string quarter:string reason:string sbb_dm_lrgb:string number:integer",
    ),
    "qatari-unemployed-15-with-secondary-education-and-training-quarterly": (
        "National Planning Council",
        158,
        "year:string quarter:string type_of_training:string nw_ltdryb:string gender:string ljns:string number:integer",
    ),
    "revenues-hotels-restaurants-current-activity-by-revenue-item-and-main-activity-10-employees-and-more": (
        "National Planning Council",
        50,
        "year_lsn:string revenue_item:string main_activity:string revenues_from_current_activity_value_in_1_000_qr_yrdt_lnsht_ljry_lqym_b_lf_ryl_qtry:number lnsht_lry_ysy:string bnd_lyrdt:string",
    ),
    "revenues-of-current-activity-by-revenue-item-and-main-activity-hotels-and-restaurants": (
        "National Planning Council",
        90,
        "year:string main_activity:string lnsht_lry_ysy:string revenue_item:string bnd_lyrdt:string revenues_from_current_activity_value_in_1_000_qr:integer",
    ),
    "sdg-17-3-1-foreign-direct-investment-inflows": (
        "National Planning Council",
        35,
        "year:string amount:number",
    ),
    "sdg-9-c-1-proportion-of-population-covered-by-a-mobile-network-by-technology": (
        "National Planning Council",
        24,
        "year:string technology:string ltknwlwjy:string percentage:string",
    ),
    "sectoral-electricity-consumption-mwh": (
        "KAHRAMAA",
        2,
        "year:string bulk_industrial:integer domestic:integer auxiliary:integer transmission_and_distribution_losses:integer total_injected_generation:integer total_electricity_generation:integer",
    ),
    "total-electricity-consumption-by-sectors": (
        "KAHRAMAA",
        576,
        "year:string month:string lshhr:string sector:string lqt:string value:integer",
    ),
    "total-students-on-scholarships-at-home-and-abroad-by-degree-and-gender": (
        "National Planning Council",
        80,
        "year:string type_of_scholarship:string nw_lmnh:string scientific_degree:string ldrj_l_lmy:string gender:string lnw:string number_of_students:integer",
    ),
    "total-water-consumption-by-sectors": (
        "KAHRAMAA",
        648,
        "year:string month:string lshhr:string sector:string lqt:string value:integer",
    ),
    "trainees-at-the-private-training-centers-by-employment-status-gender-nationality-and-field-of": (
        "National Planning Council",
        120,
        "year:string field_of_training_ar:string field_of_training:string nationality_ar:string nationality:string employment_status_ar:string employment_status:string gender_ar:string gender:string value:integer",
    ),
    "trainees-at-the-private-training-centers-by-field-of-training-gender-nationality-and-age-groups": (
        "National Planning Council",
        240,
        "year:string age_group:string lfy_l_mry:string nationality:string nationality_ar:string field_of_training:string field_of_training_ar:string gender:string lnw:string number_of_trainees:integer",
    ),
    "transformational-revenues-by-revenue-item-and-main-activity-establishments-with-10-employees-or-more": (
        "National Planning Council",
        162,
        "year:string revenue_item:string bnwd_lyrdt_l_khr:string main_activity:string lnsht_lry_ysy:string transformational_revenues_value_in_1_000_qr:integer",
    ),
    "unemployed-qataris-15-years-and-above-by-gender-and-whether-offered-work-in-private-sector": (
        "National Planning Council",
        28,
        "year:string gender:string ljns:string offered_work_in_private_sector:string l_rd_ll_ml_fy_lqt_lkhs:string value:integer",
    ),
    "unemployed-qataris-15-years-and-above-by-gender-and-willingness-to-work-in-private-sector": (
        "National Planning Council",
        32,
        "year:string gender:string ljns:string willingness_to_work_in_private_sector:string lrgb_ll_ml_fy_lqt_lkhs:string number:number",
    ),
    "unemployed-qataris-15-years-and-above-with-secondary-education-who-attended-training-programs-by": (
        "National Planning Council",
        46,
        "year:string type_of_training:string nw_ldwr:string gender:string lnw:string number:integer",
    ),
    "unemployed-qataris-less-than-secondary-by-gender-and-readiness-to-train-for-craft-work0": (
        "National Planning Council",
        24,
        "year:string readiness_to_train_for_craft_work:string md_lst_dd_lltdryb_fy_lmjl_lhrfy:string gender:string lnw:string number:integer",
    ),
    "unemployed-qataris-not-willing-to-work-in-the-private-sector-by-gender-and-reasons": (
        "National Planning Council",
        54,
        "year:string reason:string lsbb:string gender:string lnw:string number:integer",
    ),
    "unemployed-qataris-with-secondary-education-and-training-courses-refusing-work-in-private-sector-by": (
        "National Planning Council",
        84,
        "year:string gender:string ljns:string reason:string lsbb:string number_of_repetitions:integer",
    ),
    "water-supply-coverage": (
        "KAHRAMAA",
        21,
        "year:string coverage_type:string nw_ltgty:string supply_coverage:number",
    ),
    "water-supply-coverage-by-municipality": (
        "KAHRAMAA",
        56,
        "year:string municipality:string lbldy:string water_supply_coverage:number",
    ),
}


def test_portal_declarations_match_lead_reading():
    for entry in load_registry(REPO / "custodian/publicdata/sources.yaml"):
        if entry.key not in EXPECTED or not entry.slug:
            continue
        publisher, count, schema = PORTAL_DECLARATIONS[entry.slug]
        assert entry.publisher == publisher
        assert entry.row_count_min == entry.row_count_max == count
        assert entry.columns == tuple(tuple(item.split(":")) for item in schema.split())


def test_all_family_split_guards_and_measure_non_split(tmp_path):
    original = _fixture_entry()
    for family in FAMILIES:
        for token, dimension in (
            ("sex", "sex"),
            ("gender", "sex"),
            ("male", "sex"),
            ("female", "sex"),
            ("males", "sex"),
            ("females", "sex"),
            ("nationality", "nationality"),
            ("nationalities", "nationality"),
            ("qataris", "nationality"),
        ):
            entry = replace(original, source_id=family)
            records = [
                {"year": "2020-01-01", "value": 1, "SYN_" + token.upper(): "invented"},
                {"year": "2021-01-01", "value": 2, "SYN_" + token.upper(): "invented"},
            ]
            transport = _transport(entry, records)
            failure = fetch_entry(
                entry, transport, tmp_path, lambda: "unused", lambda _: None
            )
            assert failure is not None and failure.check == "public_split_undeclared"
            assert list(tmp_path.iterdir()) == []
            entry = replace(entry, public_splits=(dimension,))
            cache = tmp_path / (family + token)
            assert (
                fetch_entry(
                    entry,
                    transport,
                    cache,
                    lambda: "2026-11-15T00:00:00Z",
                    lambda _: None,
                )
                is None
            )
            # Remove this invented receipt so the next refusal proves no output.
            for file in cache.rglob("*"):
                if file.is_file():
                    file.unlink()
            for folder in sorted(cache.rglob("*"), reverse=True):
                folder.rmdir()
            cache.rmdir()
    entry = replace(
        original,
        columns=(
            *original.columns,
            ("production_value_value_in_1_000_qatari_riyals", "integer"),
        ),
    )
    records = [
        {
            "year": "2020-01-01",
            "value": 1,
            "production_value_value_in_1_000_qatari_riyals": 1,
        },
        {
            "year": "2021-01-01",
            "value": 2,
            "production_value_value_in_1_000_qatari_riyals": 2,
        },
    ]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )


def test_public_splits_match_b2_categories():
    for entry in load_registry(REPO / "custodian/publicdata/sources.yaml"):
        if entry.key not in EXPECTED:
            continue
        expected = set()
        if entry.source_id == "jobseekers":
            expected.add("nationality")
            if (
                entry.slug
                != "qatari-unemployed-15-not-willing-to-work-by-reason-quarterly"
            ):
                expected.add("sex")
        if entry.source_id == "talent_ext":
            if entry.slug not in {
                "education-statistics-number-of-graduates-on-scholarships-abroad-by-field-of-study-and-gender",
                "total-students-on-scholarships-at-home-and-abroad-by-degree-and-gender",
            }:
                expected.add("nationality")
            if (
                entry.slug
                != "education-statistics-number-of-graduates-of-public-colleges-and-universities-by-educational"
            ):
                expected.add("sex")
        if (
            entry.source_id == "hotel_ext"
            and entry.slug == "number-of-hotel-guests-and-nights-of-stay-by-nationality"
        ):
            expected.add("nationality")
        if entry.source_id == "coverage_ext" and entry.slug in {
            "proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender",
            "proportion-of-mobile-network-coverage-at-least-2g-and-at-least-3g-by-gender-and-municipality",
        }:
            expected.add("sex")
        assert set(entry.public_splits) == expected
        assert len(entry.public_splits) == len(expected)


@pytest.mark.parametrize("pin", ["a" * 63, "a" * 65, "g" * 64, "A" * 64, 7])
def test_chain_pin_rejects_bad_length_alphabet_and_type(tmp_path, pin):
    row = _block()[-1].copy()
    row["chain_intermediate_sha256"] = pin
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match="chain_intermediate_sha256 is not"):
        load_registry(path)


def test_chain_pin_round_trips_a_computed_digest(tmp_path):
    row = _block()[-1].copy()
    digest = hashlib.sha256(b"invented intermediate certificate fixture").hexdigest()
    row["chain_intermediate_sha256"] = digest
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    assert load_registry(path)[0].chain_intermediate_sha256 == digest


def test_absent_layer_can_explicitly_be_null(tmp_path):
    row = next(row for row in _block() if row["key"] == "gis_boundaries")
    row["layer"] = None
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    assert load_registry(path)[0].layer is None


def test_survey_period_field_is_declared_even_before_bounds_are_read():
    """M2: survey rows declare published_label. Their bounds stay unread."""
    from eii_custodian.publicdata.additions.common import parse_period_rule

    for entry in load_registry(REPO / "custodian/publicdata/sources.yaml"):
        if entry.source_id == "survey_ext":
            rule = parse_period_rule(entry.period_field)
            assert rule.form == "published_label"
            assert rule.field in {"year", "year_lsn"}
            assert (rule.field, "string") in entry.columns
            assert entry.period_first == entry.period_last == ""


def test_a_paged_layer_omits_its_layer_only_for_a_technical_reason(tmp_path):
    """J17(a): a plant with any other skip reason cannot omit the layer."""
    row = next(row for row in _block() if row["key"] == "gis_boundaries")
    row.pop("layer", None)
    row["skip_reason"] = "invented_gap"
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match="paged_layer requires layer"):
        load_registry(path)


def test_missing_family_period_label_names_the_source_and_the_field(tmp_path):
    """J14: a missing or null label is a named refusal. The refusal carries no value."""
    entry = replace(_fixture_entry(), period_first="", period_last="")
    records = [{"year": "", "value": 1}, {"year": "", "value": 2}]
    failure = fetch_entry(
        entry,
        _transport(entry, records),
        tmp_path,
        lambda: "2026-11-15T00:00:00Z",
        lambda _: None,
    )
    assert failure is not None
    text = " ".join((failure.check, failure.expected, failure.observed))
    assert entry.source_id in text
    # K6: the refusal names the column. The registry field is now the declared form.
    assert "year" in text
    assert "invented" not in text


def test_unparsed_family_labels_leave_null_bounds_and_a_distinct_count(tmp_path):
    """J14: bounds are stated only when every label parses; otherwise the count."""
    entry = replace(
        _fixture_entry(), source_id="hotel_ext", period_first="", period_last=""
    )
    records = [{"year": "2020 Guests", "value": 1}, {"year": "2021 Nights", "value": 2}]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert (receipt["period_first"], receipt["period_last"]) == (None, None)
    from eii_custodian.publicdata.fetch.kinds import family_period_bounds

    _first, _last, note = family_period_bounds(entry, records)
    assert note == "distinct labels 2"
    assert "Guests" not in note


def test_unsplit_text_period_labels_reach_receipts_unchanged(tmp_path):
    entry = replace(
        _fixture_entry(), source_id="hotel_ext", period_first="", period_last=""
    )
    records = [{"year": "2020 Guests", "value": 1}, {"year": "2021 Nights", "value": 2}]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    # J14: unsplit labels are not bounds. The previous assertion expected the labels.
    assert (receipt["period_first"], receipt["period_last"]) == (None, None)


def test_no_period_field_cannot_inherit_stale_registry_bounds(tmp_path):
    entry = replace(
        _fixture_entry(), period_field="", period_first="2020", period_last="2021"
    )
    records = [{"year": "invented", "value": 1}, {"year": "invented", "value": 2}]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert receipt["period_first"] is None and receipt["period_last"] is None


def test_build_orchestration_collects_families_without_tables(tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    original = _fixture_entry()
    entries = tuple(
        replace(
            original,
            source_id=family,
            key=family + "/invented",
            release_tables=(family_table_name(family),),
        )
        for family in sorted(FAMILIES)
    )
    records = [{"year": "2020-01-01", "value": 1}, {"year": "2021-01-01", "value": 2}]
    outcome = run_build(
        entries,
        _transport(original, records),
        fixture_cache,
        lambda: "2026-11-15T00:00:00Z",
        lambda _: None,
    )
    assert outcome.failure is None
    indexes = sorted(fixture_cache.glob("**/index/*.json"))
    snapshots = [read_snapshot(path.parent.parent, path.stem) for path in indexes]
    receipts = [snapshot.receipt_path for snapshot in snapshots]
    assert len(receipts) == len(FAMILIES)
    for index, snapshot in zip(indexes, snapshots, strict=True):
        directory = index.parent.parent
        check = dict(snapshot.sidecar, identity=index.stem)
        check_bytes = (
            json.dumps(check, sort_keys=True, ensure_ascii=True) + "\n"
        ).encode()
        check_path = (
            directory / "checks" / (hashlib.sha256(check_bytes).hexdigest() + ".json")
        )
        body_alias = directory / snapshot.path.name
        receipt_alias = directory / snapshot.receipt_path.name
        assert {path for path in directory.rglob("*") if path.is_file()} == {
            snapshot.path,
            snapshot.receipt_path,
            index,
            check_path,
            body_alias,
            receipt_alias,
        }
        assert check_path.read_bytes() == check_bytes
        assert body_alias.samefile(snapshot.path)
        assert receipt_alias.samefile(snapshot.receipt_path)
        assert checked_times(directory) == (snapshot.sidecar["retrieved_utc"],)
    assert {json.loads(p.read_text())["source_id"] for p in receipts} == FAMILIES
    assert all(
        json.loads(p.read_text())["release_tables"]
        == [family_table_name(json.loads(p.read_text())["source_id"])]
        for p in receipts
    )
    assert not list(tmp_path.rglob("*.parquet"))


@pytest.mark.parametrize("records", [None, [1, 2]])
def test_legacy_untyped_portal_response_keeps_existing_fetch_behavior(
    tmp_path, records
):
    entry = replace(
        _fixture_entry(),
        source_id="invented-legacy",
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_field="",
        period_first="",
        period_last="",
    )
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )


def test_distinct_label_count_is_written_on_the_receipt(tmp_path):
    """J14: when bounds are null, the receipt's coverage note counts distinct labels."""
    row = next(item for item in _block() if item["source_id"] == "trade_ext")
    registry = tmp_path / "registry.yaml"
    registry.write_text(yaml.safe_dump({"sources": [row]}))
    entry = replace(
        load_registry(registry)[0],
        source_id="hotel_ext",
        key="hotel_ext/invented",
        slug="invented",
        publisher="Invented publisher",
        url="https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/invented/exports/json",
        columns=(("year", "string"), ("value", "number")),
        row_count_min=2,
        row_count_max=2,
        period_first="",
        period_last="",
        terms_url="",
    )
    records = [{"year": "2020 Guests", "value": 1}, {"year": "2021 Nights", "value": 2}]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert receipt.get("coverage_note") == "distinct labels 2"


def test_family_row_without_a_period_form_is_refused(tmp_path):
    """A planted family row that names a period field and no form is refused."""
    row = next(item for item in _block() if item["source_id"] == "trade_ext").copy()
    row["key"] = "trade_ext/planted-no-form"
    row["slug"] = "planted-no-form"
    row["period_field"] = "year"
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match="trade_ext") as caught:
        load_registry(path)
    assert "period_form" in str(caught.value)


_PUBLISHED_LABEL_ROWS = {
    "fdi_stats/foreign-direct-investment": "period",
    "hotel_ext/number-of-hotel-guests-and-nights-of-stay-by-month": "year",
    "survey_ext/hotels-and-restaurants-statistics-production-value-by-type-of-revenue-and-main-economic-activity": "year",
    "survey_ext/hotels-and-restaurants-statistics-transformational-revenues-by-revenue-item-and-main-activity": "year",
    "survey_ext/hotels-and-restaurants-statistics-transformational-revenues-by-revenue-item-and-main-activity0": "year",
    "survey_ext/production-value-hotels-and-restaurants-type-of-revenue-and-main-economic-activity-less-10-employees": "year",
    "survey_ext/production-value-of-hotels-and-restaurants-type-revenue-economic-activity-10-employees-and-more": "year",
    "survey_ext/revenues-hotels-restaurants-current-activity-by-revenue-item-and-main-activity-10-employees-and-more": "year_lsn",
    "survey_ext/revenues-of-current-activity-by-revenue-item-and-main-activity-hotels-and-restaurants": "year",
    "survey_ext/transformational-revenues-by-revenue-item-and-main-activity-establishments-with-10-employees-or-more": "year",
    "talent_ext/education-statistics-number-of-graduates-of-private-colleges-and-universities-by-educational": "academic_year",
    "talent_ext/education-statistics-number-of-graduates-of-public-colleges-and-universities-by-academic-degree": "academic_year",
    "talent_ext/education-statistics-number-of-graduates-of-public-colleges-and-universities-by-educational": "year",
    "talent_ext/total-students-on-scholarships-at-home-and-abroad-by-degree-and-gender": "year",
}


def _planted_family_entry(tmp_path: Path, **changes):
    """One collected-family row, so a period test does not load the whole registry."""
    row = next(item for item in _block() if item["source_id"] == "trade_ext").copy()
    row["key"] = "trade_ext/planted-published-label"
    row["slug"] = "planted-published-label"
    path = tmp_path / "one.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    entry = load_registry(path)[0]
    return replace(
        entry,
        period_field="sit=row;form=published_label;field=label",
        columns=(("label", "string"), ("value", "number")),
        publisher="Invented publisher",
        terms_url="",
        **changes,
    )


def test_published_label_is_accepted_by_parse_period_rule() -> None:
    """M1: the closed list accepts published_label. A bare field stays unreadable."""
    from eii_custodian.publicdata.additions.common import (
        PERIOD_FORMS,
        AdditionError,
        parse_period_rule,
    )

    rule = parse_period_rule("sit=row;form=published_label;field=label")
    assert rule.form == "published_label"
    assert rule.sit == "row"
    assert rule.field == "label"
    assert "published_label" in PERIOD_FORMS
    with pytest.raises(AdditionError) as bare:
        parse_period_rule("label")
    assert bare.value.name == "period_field_unreadable"


def test_parse_period_value_refuses_published_label() -> None:
    """M1: the form is closed, and a label is still not a canonical period."""
    from eii_custodian.publicdata.additions.common import (
        PERIOD_FORMS,
        AdditionError,
        parse_period_value,
    )

    assert "published_label" in PERIOD_FORMS
    for label in ("2014", "Q2-2014"):
        with pytest.raises(AdditionError) as caught:
            parse_period_value(label, "published_label")
        assert caught.value.name == "period_form"


def test_published_label_bounds_count_labels_of_two_shapes(tmp_path: Path) -> None:
    """M1: two label shapes yield no bounds and the distinct count."""
    from eii_custodian.publicdata.fetch.kinds import family_period_bounds

    entry = _planted_family_entry(tmp_path, period_first="", period_last="")
    rows = [
        {"label": "2014", "value": 1},
        {"label": "Q2-2014", "value": 2},
        {"label": "2014", "value": 3},
    ]
    assert family_period_bounds(entry, rows) == ("", "", "distinct labels 2")


def test_published_label_missing_label_refuses_by_name(tmp_path: Path) -> None:
    """M1: a missing, null or empty label is refused by name and carries no cell."""
    from eii_custodian.publicdata.fetch.kinds import (
        FamilyPeriodError,
        family_period_bounds,
    )

    entry = _planted_family_entry(tmp_path)
    for value in ("", None):
        with pytest.raises(FamilyPeriodError) as caught:
            family_period_bounds(entry, [{"label": value, "value": 1}])
        assert caught.value.source_id == entry.source_id
        assert caught.value.field == "label"
        assert str(caught.value) == f"{entry.source_id} label"


def test_observe_period_bounds_refuses_published_label_by_name() -> None:
    """M1: a bounds caller refuses this form by name and does not return a label."""
    from eii_custodian.publicdata.additions.common import (
        AdditionError,
        observe_period_bounds,
        parse_period_rule,
    )

    rule = parse_period_rule("sit=row;form=published_label;field=label")
    with pytest.raises(AdditionError) as caught:
        observe_period_bounds(
            [{"label": "2014"}, {"label": "Q2-2014"}],
            rule,
        )
    assert caught.value.name == "period_form"


def test_published_label_with_a_catalogue_last_is_not_read_as_a_period(
    tmp_path: Path,
) -> None:
    """M1: a set period_last must not turn the label into a period or a fetch failure."""
    from eii_custodian.publicdata.fetch.checks import period_failure

    entry = _planted_family_entry(
        tmp_path,
        period_first="2014",
        period_last="Q2-2014",
        row_count_min=2,
        row_count_max=2,
    )
    rows = [{"label": "2014", "value": 1}, {"label": "Q2-2014", "value": 2}]
    assert period_failure(entry, rows, entry.url) is None
    assert (
        fetch_entry(
            entry,
            _transport(entry, rows),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert receipt["period_first"] is None
    assert receipt["period_last"] is None
    assert receipt["coverage_note"] == "distinct labels 2"


def test_recorded_last_label_must_be_present_or_the_fetch_stores_nothing(
    tmp_path: Path,
) -> None:
    """N2: a catalogue last label must occur exactly, or the fetch stores nothing."""
    recorded = "invented-last"
    entry = _planted_family_entry(
        tmp_path,
        period_first="invented-first",
        period_last=recorded,
        row_count_min=2,
        row_count_max=2,
    )
    missing = [
        {"label": "invented-first", "value": 1},
        {"label": "invented-mid", "value": 2},
    ]
    cache = tmp_path / "absent"
    failure = fetch_entry(
        entry,
        _transport(entry, missing),
        cache,
        lambda: "2026-11-15T00:00:00Z",
        lambda _: None,
    )
    assert failure is not None
    assert failure.check == "period_label"
    assert failure.expected == recorded
    assert failure.observed == "absent"
    assert list(cache.rglob("*")) == []
    present = [
        {"label": "invented-first", "value": 1},
        {"label": recorded, "value": 2},
    ]
    kept = tmp_path / "present"
    assert (
        fetch_entry(
            entry,
            _transport(entry, present),
            kept,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    assert list(kept.rglob("*.json"))


def test_fourteen_rows_declare_published_label() -> None:
    """M2: the fourteen bare rows name published_label and their own field."""
    from eii_custodian.publicdata.additions.common import parse_period_rule

    entries = {
        entry.key: entry
        for entry in load_registry(REPO / "custodian/publicdata/sources.yaml")
    }
    assert len(_PUBLISHED_LABEL_ROWS) == 14
    for key, field in _PUBLISHED_LABEL_ROWS.items():
        rule = parse_period_rule(entries[key].period_field)
        assert rule.form == "published_label"
        assert rule.sit == "row"
        assert rule.field == field
        assert (field, "string") in entries[key].columns
        if key.startswith("fdi_stats/"):
            clause = "Two shapes."
        elif key.startswith("hotel_ext/"):
            clause = "Text kept unsplit."
        elif key.startswith("survey_ext/"):
            clause = "Labels not read yet."
        else:
            clause = "School years with a slash."
        assert clause in entries[key].basis_note
    published = {
        entry.key
        for entry in entries.values()
        if "published_label" in entry.period_field
    }
    assert published == set(_PUBLISHED_LABEL_ROWS)
