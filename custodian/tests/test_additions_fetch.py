"""Registry completion, observed receipts and the additions build."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.support.fetch_build import run_build

from eii_custodian.publicdata.additions.build import build_additions
from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.checks import schema_failure
from eii_custodian.publicdata.fetch.registry import (
    Entry,
    RegistryError,
    load_registry,
    require_addition_completion,
)
from eii_custodian.publicdata.fetch.snapshots import checked_times, read_snapshot
from eii_custodian.publicdata.fetch.transport import Response

FAMILY_COUNTS = {
    "prop_resi_units": 1,
    "visits_museum": 1,
    "visits_phcc": 1,
    "permits_muni": 10,
    "est_size_act": 7,
    "mfg_industry": 21,
    "trade_wr": 1,
    "pop_muni_age": 1,
    "hotels_muni": 1,
    "trade_logistics": 3,
    "est_census_2015_muni": 1,
    "lf_muni_sex": 4,
    "pop_muni_age_sex": 2,
    "active_sex_age_act": 2,
    "active_nat_occ_act": 6,
    "comp_nat_act": 10,
    "students_muni": 1,
    "visitors_markets": 4,
}

PROPERTY_COLUMNS = (
    ("registration_date", "string"),
    ("encrypted_transaction_number", "string"),
    ("encrypted_parcel_number", "string"),
    ("sm_lbldy", "string"),
    ("municipality_name", "string"),
    ("sm_lmntq", "string"),
    ("district_name", "string"),
    ("nw_l_qr", "string"),
    ("property_type", "string"),
    ("area_square_meters", "integer"),
    ("price_per_square_meter", "integer"),
    ("property_value", "integer"),
)


def test_addition_rows_declare_columns_periods_and_splits() -> None:
    """Each of the 77 slugs declares columns, a closed count and an observed period rule."""
    entries = load_registry()
    found = [entry for entry in entries if entry.source_id in FAMILY_COUNTS]
    assert len(found) == 77
    for family, count in FAMILY_COUNTS.items():
        assert sum(entry.source_id == family for entry in found) == count
    for entry in found:
        assert entry.key == f"{entry.source_id}/{entry.slug}"
        assert entry.licence_id == "CC-BY-4.0"
        assert entry.licence_basis == "dataset"
        assert entry.publisher != ""
        assert entry.columns
        assert entry.row_count_min == entry.row_count_max
        assert entry.row_count_min is not None
        assert entry.period_field != ""
        assert "form=" in entry.period_field
        assert entry.period_first != ""
        assert entry.period_last != ""
        assert "modified" not in entry.period_field
    property_row = next(
        entry for entry in found if entry.source_id == "prop_resi_units"
    )
    assert property_row.columns == PROPERTY_COLUMNS
    assert property_row.period_first == "2025-08-24"
    assert property_row.period_last == "2025-12-31"
    assert property_row.row_count_min == 570
    museum = next(entry for entry in found if entry.source_id == "visits_museum")
    assert museum.columns[-1] == ("number", "string")
    assert museum.period_first == "2013-01"
    assert museum.period_last == "2024-12"
    arrivals = [
        entry
        for entry in found
        if entry.source_id == "visitors_markets"
        and entry.slug != "hotel-guests-by-nationality-hotel-rating-and-hotel-stays"
    ]
    assert len(arrivals) == 3
    assert all(entry.public_splits == ("nationality",) for entry in arrivals)
    occupation = [entry for entry in found if entry.source_id == "active_nat_occ_act"]
    assert all(entry.public_splits == ("nationality", "sex") for entry in occupation)


def test_an_incomplete_family_row_is_refused() -> None:
    """A decision-0017 row with no columns, or the old split list, does not load."""
    entries = load_registry()
    cleared = tuple(
        replace(entry, columns=()) if entry.source_id == "prop_resi_units" else entry
        for entry in entries
    )
    with pytest.raises(RegistryError, match="columns empty"):
        require_addition_completion(cleared)
    narrowed = tuple(
        replace(entry, public_splits=("nationality",))
        if entry.source_id == "active_nat_occ_act"
        else entry
        for entry in entries
    )
    with pytest.raises(RegistryError, match="split declaration"):
        require_addition_completion(narrowed)


def test_an_undeclared_period_or_month_field_is_refused() -> None:
    """field= and month= must name a declared column. The marker is not a column."""
    undeclared = _closed(
        (("count", "string"),),
        "est_size_act",
        "sit=row;form=year_text;field=year",
    )
    with pytest.raises(RegistryError, match="period_field_undeclared") as missing:
        require_addition_completion((undeclared,))
    assert undeclared.key in str(missing.value)
    undeclared_month = _closed(
        (("year", "string"),),
        "permits_muni",
        "sit=row;form=year_text_and_month_name;field=year;month=month",
    )
    with pytest.raises(RegistryError, match="period_field_undeclared") as month:
        require_addition_completion((undeclared_month,))
    assert undeclared_month.key in str(month.value)
    declared = _closed(
        (("year", "string"), ("activity_code", "string")),
        "est_size_act",
        "sit=row;form=year_text;field=year",
    )
    declared_month = _closed(
        (("year", "string"), ("month", "string")),
        "permits_muni",
        "sit=row;form=year_text_and_month_name;field=year;month=month",
    )
    require_addition_completion((declared, declared_month))
    marker = _closed(
        (("count", "string"),),
        "est_size_act",
        "sit=row;form=year_text;field=to_be_confirmed",
    )
    month_marker = _closed(
        (("year", "string"),),
        "permits_muni",
        "sit=row;form=year_text_and_month_name;field=year;month=to_be_confirmed",
    )
    require_addition_completion((marker, month_marker))


def test_a_repeated_period_key_is_unreadable() -> None:
    """A repeated key in a period rule is refused, including a later declared name."""
    repeated = _closed(
        (("year", "string"), ("activity_code", "string")),
        "est_size_act",
        "sit=row;form=year_text;field=not_a_column;field=year",
    )
    with pytest.raises(RegistryError, match="period_field_unreadable") as caught:
        require_addition_completion((repeated,))
    assert repeated.key in str(caught.value)
    same = _closed(
        (("year", "string"),),
        "est_size_act",
        "sit=row;form=year_text;field=year;field=year",
    )
    with pytest.raises(RegistryError, match="period_field_unreadable") as again:
        require_addition_completion((same,))
    assert same.key in str(again.value)


def test_est_size_declares_year_and_activity_code_first() -> None:
    """The seven size bulletins declare year, then activity_code, before the rest."""
    rows = [entry for entry in load_registry() if entry.source_id == "est_size_act"]
    assert len(rows) == 7
    for entry in rows:
        assert entry.columns[0] == ("year", "string")
        assert entry.columns[1] == ("activity_code", "string")


def test_schema_checks_every_row_and_allows_null() -> None:
    """A later row of the wrong type fails. A null cell is not a type error and not a zero."""
    entry = _bare((("count", "integer"), ("geo", "object")))
    valid = [
        {"count": 1, "geo": {"kind": "point"}},
        {"count": None, "geo": None},
    ]
    assert schema_failure(entry, valid, "https://www.data.gov.qa/x") is None
    failure = schema_failure(
        entry,
        [
            {"count": 1, "geo": {"kind": "point"}},
            {"count": "no", "geo": {"kind": "point"}},
        ],
        "https://www.data.gov.qa/x",
    )
    assert failure is not None
    assert failure.check == "schema_retyped"
    url = "https://www.data.gov.qa/x"
    valid_row = {"count": 1, "geo": {"kind": "point"}}
    later_empty = schema_failure(entry, [valid_row, {}], url)
    assert later_empty is not None
    assert later_empty.check == "schema_missing"
    assert later_empty.expected == "count"
    later_none = schema_failure(entry, [valid_row, None], url)
    assert later_none is not None
    assert later_none.check == "schema_missing"
    assert later_none.expected == "count"
    empty = schema_failure(entry, [], url)
    assert empty is not None
    assert empty.check == "schema_missing"
    assert empty.expected == "count"


def test_an_open_row_count_range_is_refused() -> None:
    """A decision-0017 row whose count is a range is refused by the closed message."""
    opened = replace(
        _closed(
            (("year", "string"),),
            "est_size_act",
            "sit=row;form=year_text;field=year",
        ),
        row_count_max=2,
    )
    with pytest.raises(RegistryError) as caught:
        require_addition_completion((opened,))
    assert str(caught.value) == f"{opened.key}: row count range not closed"


def test_empty_period_bounds_are_refused() -> None:
    """A decision-0017 row with an empty period bound is refused by the closed message."""
    emptied = replace(
        _closed(
            (("year", "string"),),
            "est_size_act",
            "sit=row;form=year_text;field=year",
        ),
        period_first="",
    )
    with pytest.raises(RegistryError) as caught:
        require_addition_completion((emptied,))
    assert str(caught.value) == f"{emptied.key}: period bounds empty"


def test_a_visitors_market_without_nationality_is_refused() -> None:
    """Removing nationality from a visitors row is refused by the closed message."""
    entry = next(
        item for item in load_registry() if item.source_id == "visitors_markets"
    )
    stripped = replace(entry, public_splits=())
    with pytest.raises(RegistryError) as caught:
        require_addition_completion((stripped,))
    assert str(caught.value) == f"{stripped.key}: split declaration"


def test_receipt_records_the_observed_period_not_the_modified_date(
    tmp_path: Path,
) -> None:
    """The sidecar period is the month in the file. The portal modified date stays provenance."""
    entry = replace(
        _family("visits_museum"),
        url=_EXPORT,
        row_count_min=1,
        row_count_max=1,
        period_first="2024-01",
        period_last="2024-01",
    )
    assert (
        fetch_entry(entry, _transport([_museum_row()]), tmp_path, _clock, _sleep)
        is None
    )
    side = _sidecar(tmp_path)
    assert side["period_first"] == "2024-01"
    assert side["period_last"] == "2024-01"
    assert side["source_modified"] == "2011-02-03"
    stale = replace(entry, period_last="2024-12")
    failure = fetch_entry(
        stale, _transport([_museum_row()]), tmp_path / "stale", _clock, _sleep
    )
    assert failure is not None
    assert failure.check == "period_last"
    assert failure.observed == "2024-01"


def test_unconfirmed_period_field_does_not_copy_the_declared_bounds(
    tmp_path: Path,
) -> None:
    """When the year column is still unnamed, the sidecar periods are null."""
    entry = _bare(
        (("value", "integer"),),
        source_id="est_size_act",
        key="est_size_act/invented",
        slug="invented",
        period_field="sit=row;form=year_text;field=to_be_confirmed",
        period_first="2015",
        period_last="2022",
        row_count_min=1,
        row_count_max=1,
    )
    assert (
        fetch_entry(entry, _transport([{"value": 3}]), tmp_path, _clock, _sleep) is None
    )
    side = _sidecar(tmp_path)
    assert side["period_first"] is None
    assert side["period_last"] is None
    assert side["source_modified"] == "2011-02-03"


def test_measure_text_outside_the_reviewed_list_stores_nothing(tmp_path: Path) -> None:
    """A museum count that is neither a number nor a reviewed dash is not cached."""
    entry = replace(
        _family("visits_museum"),
        url=_EXPORT,
        row_count_min=1,
        row_count_max=1,
        period_first="2024-01",
        period_last="2024-01",
    )
    failure = fetch_entry(
        entry, _transport([_museum_row(number="shut")]), tmp_path, _clock, _sleep
    )
    assert failure is not None
    assert failure.check == "measure_unparsed"
    assert list(tmp_path.rglob("*.meta.json")) == []


def test_fetch_publishes_venue_rows_and_a_parser_failure_publishes_nothing(
    tmp_path: Path,
) -> None:
    """A fetched museum export becomes a table. An unmapped name leaves no current manifest."""
    entry = replace(
        _family("visits_museum"),
        url=_EXPORT,
        row_count_min=1,
        row_count_max=1,
        period_first="2024-01",
        period_last="2024-01",
    )
    review = tmp_path / "review"
    review.mkdir()
    (review / "additions_property_venues.yaml").write_text(
        (
            Path(__file__).resolve().parents[1]
            / "publicdata"
            / "review"
            / "additions_property_venues.yaml"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (review / "venue_crosswalk.csv").write_text(
        "source_key,published_name,venue_key,place_id,reviewer_role,reviewed_on\n"
        "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum,"
        "SYN Hall,syn_hall,,reviewer,2026-01-02\n"
        "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum,"
        "SYN Hall AR,syn_hall,,reviewer,2026-01-02\n",
        encoding="utf-8",
    )
    outcome = run_build(
        (entry,),
        _transport([_museum_row()]),
        tmp_path / "cache",
        _clock,
        _sleep,
        additions_review=review,
        additions_frame=review,
        additions_output=tmp_path / "out",
    )
    assert outcome.failure is None
    assert (
        tmp_path / "out" / "current" / "tables" / "pub_venue_visits.parquet"
    ).is_file()
    (review / "venue_crosswalk.csv").write_text(
        "source_key,published_name,venue_key,place_id,reviewer_role,reviewed_on\n",
        encoding="utf-8",
    )
    failed = run_build(
        (entry,),
        _transport([_museum_row()]),
        tmp_path / "cache-fail",
        _clock,
        _sleep,
        additions_review=review,
        additions_frame=review,
        additions_output=tmp_path / "out-fail",
    )
    assert failed.failure is not None
    assert failed.failure.check == "unmapped_venue_name"
    assert not (tmp_path / "out-fail" / "current").exists()


def test_a_later_pass_without_a_parser_is_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Taking one family's parser out leaves that slug pending, with no table file.

    Every decision-0017 family has a parser. This test removes est_size_act from
    that module's PARSERS for the duration of the test.
    """
    from eii_custodian.publicdata.additions import industry

    monkeypatch.delitem(industry.PARSERS, "est_size_act")
    entry = _family("est_size_act")
    body = b"[]"
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    cache = tmp_path / "cache"
    digest = write_cached(cache, entry, body).stem
    review = tmp_path / "review"
    review.mkdir()
    (review / "additions_property_venues.yaml").write_text(
        "version: 1\n", encoding="utf-8"
    )
    (review / "venue_crosswalk.csv").write_text(
        "source_key,published_name,venue_key,place_id,reviewer_role,reviewed_on\n",
        encoding="utf-8",
    )
    destination = build_additions(
        cache, (entry,), {entry.key: digest}, review, review, tmp_path / "out"
    )
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert entry.key in manifest["pending_slugs"]
    report = json.loads((destination / "build_report.json").read_text(encoding="utf-8"))
    assert entry.key in report["pending_slugs"]
    assert all(item["name"] != "pub_establishment_size" for item in manifest["tables"])
    assert not (destination / "tables" / "pub_establishment_size.parquet").is_file()


def _closed(
    columns: tuple[tuple[str, str], ...], source_id: str, period_field: str
) -> Entry:
    return _bare(
        columns,
        source_id=source_id,
        period_field=period_field,
        row_count_min=1,
        row_count_max=1,
        period_first="2015",
        period_last="2015",
    )


def _family(source_id: str) -> Entry:
    return next(entry for entry in load_registry() if entry.source_id == source_id)


def _bare(columns: tuple[tuple[str, str], ...], **overrides: object) -> Entry:
    values: dict[str, object] = {
        "key": "planted",
        "source_id": "planted",
        "slug": "planted",
        "kind": "portal_dataset",
        "title_en": "Planted",
        "publisher": "National Planning Council",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "decision_record": "",
        "fetch_host": "www.data.gov.qa",
        "url": _EXPORT,
        "terms_url": "",
        "nightly_live_fetch": False,
        "public_splits": (),
        "commit_allowed": False,
        "release_tables": (),
        "caveat_keys": (),
        "columns": columns,
        "row_count_min": None,
        "row_count_max": None,
        "period_first": "",
        "period_last": "",
        "period_field": "",
        "reconciliation": "none",
        "skip_reason": "",
        "extension": "json",
        "landing_url": _EXPORT,
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
    }
    values.update(overrides)
    return _entry_from(values)


_EXPORT = (
    "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/invented/exports/json"
)
_META = "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/invented"


def _clock() -> str:
    return "2026-03-04T05:06:07Z"


def _sleep(_seconds: float) -> None:
    return None


def _museum_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2024",
        "month": "January",
        "lshhr": "SYN-MONTH",
        "museum": "SYN Hall",
        "lmthf": "SYN Hall AR",
        "number": "4",
    }
    row.update(overrides)
    return row


def _transport(rows: list[dict[str, object]]):
    body = json.dumps(rows).encode()
    meta = json.dumps(
        {
            "metas": {
                "default": {
                    "publisher": "National Planning Council",
                    "license": "CC BY",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "modified": "2011-02-03",
                }
            }
        }
    ).encode()

    def transport(url: str) -> Response:
        if url == _META:
            return Response(url, meta, ())
        if url == _EXPORT:
            return Response(url, body, ())
        raise AssertionError(url)

    return transport


def _entry_from(values: dict[str, object]) -> Entry:
    """Build one entry from a fixture map, narrowing each field to its exact type."""
    return Entry(
        key=_map_text(values, "key"),
        source_id=_map_text(values, "source_id"),
        slug=_map_text(values, "slug"),
        kind=_map_text(values, "kind"),
        title_en=_map_text(values, "title_en"),
        publisher=_map_text(values, "publisher"),
        licence_id=_map_text(values, "licence_id"),
        licence_basis=_map_text(values, "licence_basis"),
        decision_record=_map_text(values, "decision_record"),
        fetch_host=_map_text(values, "fetch_host"),
        url=_map_text(values, "url"),
        terms_url=_map_text(values, "terms_url"),
        terms_words="invented terms words for a test",
        terms_read_on="2026-11-14",
        nightly_live_fetch=_map_flag(values, "nightly_live_fetch"),
        public_splits=_map_texts(values, "public_splits"),
        commit_allowed=_map_flag(values, "commit_allowed"),
        release_tables=_map_texts(values, "release_tables"),
        caveat_keys=_map_texts(values, "caveat_keys"),
        columns=_map_columns(values, "columns"),
        row_count_min=_map_count(values, "row_count_min"),
        row_count_max=_map_count(values, "row_count_max"),
        period_first=_map_text(values, "period_first"),
        period_last=_map_text(values, "period_last"),
        period_field=_map_text(values, "period_field"),
        reconciliation=_map_text(values, "reconciliation"),
        skip_reason=_map_text(values, "skip_reason"),
        extension=_map_text(values, "extension"),
        landing_url=_map_text(values, "landing_url"),
        licence_url=_map_text(values, "licence_url"),
    )


def _map_text(values: dict[str, object], name: str) -> str:
    value = values[name]
    if isinstance(value, str):
        return value
    raise AssertionError(name)


def _map_flag(values: dict[str, object], name: str) -> bool:
    value = values[name]
    if isinstance(value, bool):
        return value
    raise AssertionError(name)


def _map_texts(values: dict[str, object], name: str) -> tuple[str, ...]:
    value = values[name]
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return value
    raise AssertionError(name)


def _map_columns(values: dict[str, object], name: str) -> tuple[tuple[str, str], ...]:
    value = values[name]
    if isinstance(value, tuple) and all(
        isinstance(pair, tuple)
        and len(pair) == 2
        and isinstance(pair[0], str)
        and isinstance(pair[1], str)
        for pair in value
    ):
        return value
    raise AssertionError(name)


def _map_count(values: dict[str, object], name: str) -> int | None:
    value = values[name]
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise AssertionError(name)


def _sidecar(folder: Path) -> dict[str, object]:
    indexes = sorted(folder.glob("**/index/*.json"))
    snapshots = [read_snapshot(path.parent.parent, path.stem) for path in indexes]
    found = [snapshot.receipt_path for snapshot in snapshots]
    assert len(found) == 1
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
    loaded = snapshots[0].sidecar
    assert isinstance(loaded, dict)
    return loaded
