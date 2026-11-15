"""Property aggregates and venue visits. Fixtures are invented."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import duckdb  # type: ignore[import-untyped]
import pytest
import yaml  # type: ignore[import-untyped]

from eii_custodian.publicdata.additions.build import build_additions, checked_selection
from eii_custodian.publicdata.additions.common import (
    AdditionError,
    observe_period_bounds,
    parse_period_rule,
    parse_period_value,
    require_lineage,
)
from eii_custodian.publicdata.additions.property_venues import (
    load_venue_crosswalk,
    parse_health_centres,
    parse_museum,
    parse_property,
)
from eii_custodian.publicdata.additions.storage import publish
from eii_custodian.publicdata.fetch.registry import Entry, load_registry

REVIEW = Path(__file__).resolve().parents[1] / "publicdata" / "review"
RECEIPT = {"retrieved_utc": "2026-03-04T05:06:07Z", "sha256": "ab" * 32}


def _field_map() -> dict[str, object]:
    loaded = yaml.safe_load(
        (REVIEW / "additions_property_venues.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(loaded, dict)
    return loaded


def _entry(source_id: str) -> Entry:
    return next(entry for entry in load_registry() if entry.source_id == source_id)


def _frame(folder: Path) -> Path:
    folder.mkdir(parents=True)
    (folder / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "SYN Coast,syn_coast\n"
        "SYN Coast AR,syn_coast\n"
        "SYN Inland,syn_inland\n"
        "SYN Inland AR,syn_inland\n",
        encoding="utf-8",
    )
    (folder / "district_crosswalk.csv").write_text(
        "name,district_keys\nSYN North,syn_north\nSYN North AR,syn_north\n",
        encoding="utf-8",
    )
    return folder


def _deal(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "registration_date": "2025-08-24",
        "encrypted_transaction_number": "SYN-DEAL-A",
        "encrypted_parcel_number": "SYN-PARCEL-A",
        "sm_lbldy": "SYN Coast AR",
        "municipality_name": "SYN Coast",
        "sm_lmntq": "SYN North AR",
        "district_name": "SYN North",
        "nw_l_qr": "SYN-UNIT",
        "property_type": "Residential Unit",
        "area_square_meters": 80,
        "price_per_square_meter": 10,
        "property_value": 800,
    }
    row.update(overrides)
    return row


def _property(folder: Path, rows: list[dict[str, object]]) -> object:
    return parse_property(
        _entry("prop_resi_units"),
        rows,
        RECEIPT,
        _field_map(),
        {"frame": _frame(folder), "review": folder, "venues": ()},
    )


def _coverage(parsed: object, reason: str) -> int:
    return sum(item.count for item in parsed.coverage if item.reason == reason)  # type: ignore[attr-defined]


def test_repeated_transaction_is_one_deal_and_a_disagreement_is_not_summed(
    tmp_path: Path,
) -> None:
    """One agreed price counts once. Disagreeing prices block the deal and are not summed."""
    agreed = _property(
        tmp_path / "agreed",
        [
            _deal(encrypted_parcel_number="SYN-PARCEL-A", price_per_square_meter=10),
            _deal(
                encrypted_parcel_number="SYN-PARCEL-B",
                price_per_square_meter=10,
                property_value=900,
            ),
        ],
    )
    assert agreed.rows[0]["deal_count"] == 1  # type: ignore[attr-defined]
    assert agreed.rows[0]["median_price"] == Decimal("10.00")  # type: ignore[attr-defined]
    assert "property_value" not in agreed.rows[0]  # type: ignore[attr-defined]
    blocked = _property(
        tmp_path / "blocked",
        [
            _deal(price_per_square_meter=10, property_value=100),
            _deal(
                encrypted_parcel_number="SYN-PARCEL-B",
                price_per_square_meter=20,
                property_value=400,
            ),
            _deal(
                encrypted_transaction_number="SYN-DEAL-B",
                encrypted_parcel_number="SYN-PARCEL-C",
                price_per_square_meter=10,
                property_value=800,
            ),
        ],
    )
    assert blocked.rows[0]["deal_count"] == 1  # type: ignore[attr-defined]
    assert blocked.rows[0]["median_price"] == Decimal("10.00")  # type: ignore[attr-defined]
    assert _coverage(blocked, "repeated_deal_price_disagreement") == 1
    assert "500" not in repr(blocked.rows)  # type: ignore[attr-defined]


def test_median_uses_the_middle_and_the_mean_of_two_middle_values(
    tmp_path: Path,
) -> None:
    """An odd count uses the middle price. An even count averages the two middle prices."""
    odd = _property(
        tmp_path / "odd",
        [
            _deal(encrypted_transaction_number="SYN-DEAL-A", price_per_square_meter=10),
            _deal(encrypted_transaction_number="SYN-DEAL-B", price_per_square_meter=30),
            _deal(encrypted_transaction_number="SYN-DEAL-C", price_per_square_meter=20),
        ],
    )
    assert odd.rows[0]["median_price"] == Decimal("20.00")  # type: ignore[attr-defined]
    even = _property(
        tmp_path / "even",
        [
            _deal(encrypted_transaction_number="SYN-DEAL-A", price_per_square_meter=10),
            _deal(encrypted_transaction_number="SYN-DEAL-B", price_per_square_meter=20),
        ],
    )
    assert even.rows[0]["median_price"] == Decimal("15.00")  # type: ignore[attr-defined]
    assert even.rows[0]["price_basis"] == "per_m2"  # type: ignore[attr-defined]


def test_nonpositive_price_is_excluded_and_identifiers_stay_out(tmp_path: Path) -> None:
    """A non-positive price is coverage, and no identifier value or field name is emitted."""
    parsed = _property(
        tmp_path / "price",
        [
            _deal(),
            _deal(
                encrypted_transaction_number="SYN-DEAL-Z",
                price_per_square_meter=0,
                property_value=0,
            ),
        ],
    )
    assert parsed.rows[0]["deal_count"] == 1  # type: ignore[attr-defined]
    assert _coverage(parsed, "nonpositive_price") == 1
    rendered = repr(parsed)
    assert "SYN-DEAL-A" not in rendered
    assert "SYN-PARCEL-A" not in rendered
    assert "encrypted_transaction_number" not in rendered
    assert "encrypted_parcel_number" not in rendered


def test_unmatched_ambiguous_and_unmapped_districts_are_not_guessed(
    tmp_path: Path,
) -> None:
    """An unmatched district is left out. An ambiguous name and an unmapped municipality stop assignment."""
    unmatched = _property(
        tmp_path / "unmatched",
        [_deal(), _deal(district_name="SYN Absent", sm_lmntq="SYN Absent AR")],
    )
    assert len(unmatched.rows) == 1  # type: ignore[attr-defined]
    assert _coverage(unmatched, "unmatched_district") == 1
    assert "SYN Absent" not in repr(unmatched)
    ambiguous = _property(
        tmp_path / "ambiguous",
        [
            _deal(),
            _deal(
                municipality_name="SYN Inland",
                sm_lbldy="SYN Inland AR",
                encrypted_transaction_number="SYN-DEAL-B",
            ),
        ],
    )
    assert ambiguous.rows == ()  # type: ignore[attr-defined]
    assert _coverage(ambiguous, "ambiguous_district") == 2
    with pytest.raises(AdditionError) as unmapped:
        _property(tmp_path / "unmapped", [_deal(municipality_name="SYN Missing")])
    assert unmapped.value.name == "unmapped_municipality"
    assert "SYN Missing" not in str(unmapped.value)
    with pytest.raises(AdditionError) as disagreed:
        _property(tmp_path / "disagree", [_deal(sm_lbldy="SYN Inland AR")])
    assert disagreed.value.name == "municipality_disagreement"


def test_a_district_name_with_two_keys_is_not_stored(tmp_path: Path) -> None:
    """One published name that maps to two keys does not fit a single district_key."""
    frame = _frame(tmp_path / "frame")
    (frame / "district_crosswalk.csv").write_text(
        "name,district_keys\n"
        "SYN North,syn_north;syn_south\n"
        "SYN North AR,syn_north;syn_south\n",
        encoding="utf-8",
    )
    parsed = parse_property(
        _entry("prop_resi_units"),
        [_deal()],
        RECEIPT,
        _field_map(),
        {"frame": frame, "review": frame, "venues": ()},
    )
    assert parsed.rows == ()
    assert _coverage(parsed, "district_key_not_singular") == 1


def test_per_unit_is_not_built_and_the_question_is_recorded(tmp_path: Path) -> None:
    """Both price columns are present. Only the per-square-metre aggregate is built."""
    parsed = _property(tmp_path / "basis", [_deal()])
    assert {row["price_basis"] for row in parsed.rows} == {"per_m2"}  # type: ignore[attr-defined]
    assert any("per-unit" in question.change for question in parsed.questions)  # type: ignore[attr-defined]
    assert any("PUB-107" in question.change for question in parsed.questions)  # type: ignore[attr-defined]


def _venues(folder: Path, rows: str) -> tuple[dict[str, str], ...]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "venue_crosswalk.csv").write_text(
        "source_key,published_name,venue_key,place_id,reviewer_role,reviewed_on\n"
        + rows,
        encoding="utf-8",
    )
    return load_venue_crosswalk(folder / "venue_crosswalk.csv")


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


def _museum(folder: Path, rows: list[dict[str, object]], links: str) -> object:
    return parse_museum(
        _entry("visits_museum"),
        rows,
        RECEIPT,
        _field_map(),
        {"frame": folder, "review": folder, "venues": _venues(folder, links)},
    )


_LINKS = (
    "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum,"
    "SYN Hall,syn_hall,,reviewer,2026-01-02\n"
    "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum,"
    "SYN Hall AR,syn_hall,,reviewer,2026-01-02\n"
)


def test_museum_alias_keeps_one_key_and_a_dash_drops_the_row(tmp_path: Path) -> None:
    """The same published name in two months is one venue. A dash is not a zero."""
    parsed = _museum(
        tmp_path / "alias",
        [
            _museum_row(number="4"),
            _museum_row(month="February", number="9"),
            _museum_row(month="March", number="-"),
        ],
        _LINKS,
    )
    assert [row["value"] for row in parsed.rows] == [4, 9]  # type: ignore[attr-defined]
    assert {row["venue_key"] for row in parsed.rows} == {"syn_hall"}  # type: ignore[attr-defined]
    assert parsed.rows[0]["place_id"] is None  # type: ignore[attr-defined]
    assert "lon" not in parsed.rows[0] and "lat" not in parsed.rows[0]  # type: ignore[attr-defined]
    assert _coverage(parsed, "missing_measure") == 1


def test_unknown_or_prefix_venue_names_stop_the_build(tmp_path: Path) -> None:
    """A name with no exact crosswalk row, including a prefix or a case change, is refused."""
    with pytest.raises(AdditionError) as unknown:
        _museum(tmp_path / "unknown", [_museum_row(museum="SYN Other")], _LINKS)
    assert unknown.value.name == "unmapped_venue_name"
    with pytest.raises(AdditionError) as prefix:
        _museum(tmp_path / "prefix", [_museum_row(museum="SYN Hall extra")], _LINKS)
    assert prefix.value.name == "unmapped_venue_name"
    with pytest.raises(AdditionError) as folded:
        _museum(tmp_path / "case", [_museum_row(museum="syn hall")], _LINKS)
    assert folded.value.name == "unmapped_venue_name"
    with pytest.raises(AdditionError) as text:
        _museum(tmp_path / "text", [_museum_row(number="shut")], _LINKS)
    assert text.value.name == "measure_unparsed"


def test_conflicting_or_unreviewed_crosswalk_rows_are_refused(tmp_path: Path) -> None:
    """Two rows for one published name, or a row without a review date, do not load."""
    with pytest.raises(AdditionError) as conflict:
        _venues(tmp_path / "conflict", _LINKS + _LINKS.splitlines()[0] + "\n")
    assert conflict.value.name == "venue_crosswalk_conflict"
    with pytest.raises(AdditionError) as blank:
        _venues(
            tmp_path / "blank",
            "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum,"
            "SYN Hall,syn_hall,,,2026-01-02\n",
        )
    assert blank.value.name == "unreviewed_venue"


def test_null_health_centre_year_is_not_zero_or_twelve_months(tmp_path: Path) -> None:
    """A null year column drops that year. A fractional count stops the build."""
    entry = _entry("visits_phcc")
    links = _venues(
        tmp_path / "health",
        "visits_phcc/phcc-patient-visits-by-health-center-and-region,"
        "SYN Centre,syn_centre,,reviewer,2026-01-02\n",
    )
    row: dict[str, object] = {
        "region": "SYN Region",
        "health_center_name": "SYN Centre",
        "2020": None,
        "2021": 4.0,
        "2022": None,
        "2023": None,
        "2024": None,
    }
    parsed = parse_health_centres(
        entry, [row], RECEIPT, _field_map(), {"venues": links}
    )
    assert [(item["period"], item["value"]) for item in parsed.rows] == [("2021", 4)]
    assert _coverage(parsed, "missing_value") == 4
    assert parsed.rows[0]["name_ar"] is None
    with pytest.raises(AdditionError) as fractional:
        parse_health_centres(
            entry,
            [{**row, "2021": 1.5}],
            RECEIPT,
            _field_map(),
            {"venues": links},
        )
    assert fractional.value.name == "measure_not_integral"


def test_a_period_form_outside_the_list_fails_by_name() -> None:
    """A closed form parses. Any other form fails, and a modified date is not a period."""
    assert parse_period_value("2025-08-24", "date") == "2025-08-24"
    rule = parse_period_rule("sit=row;form=date;field=registration_date")
    assert observe_period_bounds([{"registration_date": "2025-08-24"}], rule) == (
        "2025-08-24",
        "2025-08-24",
    )
    with pytest.raises(AdditionError) as unknown:
        parse_period_rule("sit=row;form=file_modified;field=source_modified")
    assert unknown.value.name == "period_form"
    with pytest.raises(AdditionError) as unconfirmed:
        observe_period_bounds(
            [{"year": "2015", "source_modified": "2011-02-03"}],
            parse_period_rule("sit=row;form=year_text;field=to_be_confirmed"),
        )
    assert unconfirmed.value.name == "period_field_unconfirmed"


def test_duplicate_selection_hash_and_publish_failures(tmp_path: Path) -> None:
    """A repeated key, a hash that does not match, and a failed publish leave no new tables."""
    with pytest.raises(AdditionError) as repeated:
        checked_selection((("visits_museum/one", "ab"), ("visits_museum/one", "cd")))
    assert repeated.value.name == "duplicate_slug_selection"
    entry = _entry("visits_museum")
    body = json.dumps([_museum_row()]).encode()
    digest = hashlib.sha256(body).hexdigest()
    cache = tmp_path / "cache"
    folder = cache / entry.key
    folder.mkdir(parents=True)
    (folder / f"{digest}.json").write_bytes(b"not-the-body")
    (folder / f"{digest}.meta.json").write_text(json.dumps(RECEIPT), encoding="utf-8")
    review = tmp_path / "review"
    _venues(review, _LINKS)
    (review / "additions_property_venues.yaml").write_text(
        (REVIEW / "additions_property_venues.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(AdditionError) as mismatch:
        build_additions(
            cache, (entry,), {entry.key: digest}, review, review, tmp_path / "out"
        )
    assert mismatch.value.name == "hash_mismatch"
    assert not (tmp_path / "out" / "current").exists()
    with pytest.raises(AdditionError) as absent:
        build_additions(
            cache, (entry,), {entry.key: "cd" * 32}, review, review, tmp_path / "out"
        )
    assert absent.value.name == "hash_absent"
    output = tmp_path / "kept"
    publish(
        output,
        (("pub_venue_visits", (("value", "INTEGER"),), ((4,),)),),
        {},
        {},
    )
    with pytest.raises(AdditionError):
        publish(output, (("Bad-Name", (("value", "INTEGER"),), ((4,),)),), {}, {})
    assert (output / "current" / "tables" / "pub_venue_visits.parquet").is_file()


def test_built_property_table_round_trips_and_lineage_is_required(
    tmp_path: Path,
) -> None:
    """A published per-square-metre median reads back, and a figure without lineage is refused."""
    entry = _entry("prop_resi_units")
    rows = [
        _deal(encrypted_transaction_number="SYN-DEAL-A", price_per_square_meter=10),
        _deal(encrypted_transaction_number="SYN-DEAL-B", price_per_square_meter=20),
    ]
    body = json.dumps(rows).encode()
    digest = hashlib.sha256(body).hexdigest()
    cache = tmp_path / "cache"
    folder = cache / entry.key
    folder.mkdir(parents=True)
    (folder / f"{digest}.json").write_bytes(body)
    side = dict(RECEIPT)
    side["sha256"] = digest
    (folder / f"{digest}.meta.json").write_text(json.dumps(side), encoding="utf-8")
    review = tmp_path / "review"
    review.mkdir()
    (review / "additions_property_venues.yaml").write_text(
        (REVIEW / "additions_property_venues.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (review / "venue_crosswalk.csv").write_text(
        "source_key,published_name,venue_key,place_id,reviewer_role,reviewed_on\n",
        encoding="utf-8",
    )
    frame = _frame(tmp_path / "frame")
    destination = build_additions(
        cache, (entry,), {entry.key: digest}, review, frame, tmp_path / "out"
    )
    path = str(destination / "tables" / "pub_property_resi.parquet")
    found = duckdb.sql(
        f"select median_price, deal_count, price_basis from read_parquet('{path}')"
    ).fetchall()
    assert len(found) == 1
    assert Decimal(str(found[0][0])) == Decimal("15.00")
    assert found[0][1] == 2
    assert found[0][2] == "per_m2"
    parsed = _property(tmp_path / "lineage", rows)
    broken = dict(parsed.rows[0])  # type: ignore[attr-defined]
    del broken["method"]
    with pytest.raises(AdditionError) as missing:
        require_lineage(broken)
    assert missing.value.name == "lineage_incomplete"


def test_two_rows_that_share_a_venue_period_publish_nothing(tmp_path: Path) -> None:
    """A duplicate contract key publishes no current manifest."""
    entry = _entry("visits_museum")
    review = tmp_path / "review"
    _venues(review, _LINKS)
    (review / "additions_property_venues.yaml").write_text(
        (REVIEW / "additions_property_venues.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    body = json.dumps([_museum_row(), _museum_row()]).encode()
    digest = hashlib.sha256(body).hexdigest()
    cache = tmp_path / "cache"
    folder = cache / entry.key
    folder.mkdir(parents=True)
    (folder / f"{digest}.json").write_bytes(body)
    (folder / f"{digest}.meta.json").write_text(
        json.dumps(RECEIPT | {"sha256": digest}), encoding="utf-8"
    )
    with pytest.raises(AdditionError) as duplicate:
        build_additions(
            cache, (entry,), {entry.key: digest}, review, review, tmp_path / "out"
        )
    assert duplicate.value.name == "duplicate_key"
    assert not (tmp_path / "out" / "current" / "manifest.json").exists()
