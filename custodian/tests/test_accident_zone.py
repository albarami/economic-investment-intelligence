"""S3-T12 / decision 0047 amendment: accident context on source zones.

Invented records only, in the registered field shape of the `accident` entry
(`accident_year` string, `zone` integer, `total` integer). No cache is read.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.accidents import (
    COVERAGE_KEYS,
    AccidentRefusal,
    AccidentReview,
    accident_zone_rows,
)

COLUMNS = frozenset(
    {"accident_year", "zone", "total", "street", "accident_time", "city"}
)
ZONES = frozenset({"INVENTED-zone-a", "INVENTED-zone-b"})
REVIEW = AccidentReview(
    measure_confirmed=True,
    crosswalk={51: "INVENTED-zone-a", 52: "INVENTED-zone-b"},
)
SOURCE = "accident"
AS_OF = "2026-11-20"


def records() -> list[dict[str, object]]:
    return [
        {"accident_year": "2024", "zone": 51, "total": 2, "street": 9},
        {"accident_year": "2024", "zone": 51, "total": 3, "city": "INVENTED"},
        {"accident_year": "2024", "zone": 52, "total": 0},
        {"accident_year": "2025", "zone": 51, "total": 4},
    ]


def build(**changes: object) -> list[dict[str, object]]:
    arguments: dict[str, object] = dict(
        records=records(),
        review=REVIEW,
        zone_codes=ZONES,
        columns=COLUMNS,
        source_id=SOURCE,
        as_of=AS_OF,
    )
    arguments.update(changes)
    return accident_zone_rows(**arguments)  # type: ignore[arg-type]


def test_valid_rows_sum_total_on_the_exact_source_zone_and_year() -> None:
    assert build() == [
        {
            "source_zone": "51",
            "period": "2024",
            "zone_code": "INVENTED-zone-a",
            "accident_count": 5,
            "coverage_key": "counted",
            "as_of": date(2026, 11, 20),
            "source_id": SOURCE,
        },
        {
            "source_zone": "51",
            "period": "2025",
            "zone_code": "INVENTED-zone-a",
            "accident_count": 4,
            "coverage_key": "counted",
            "as_of": date(2026, 11, 20),
            "source_id": SOURCE,
        },
        {
            "source_zone": "52",
            "period": "2024",
            "zone_code": "INVENTED-zone-b",
            "accident_count": 0,
            "coverage_key": "counted",
            "as_of": date(2026, 11, 20),
            "source_id": SOURCE,
        },
    ]
    # No street, time, person, vehicle or coordinate crosses (rule 10).
    assert {key for row in build() for key in row} == {
        "source_zone",
        "period",
        "zone_code",
        "accident_count",
        "coverage_key",
        "as_of",
        "source_id",
    }


def test_unconfirmed_total_counts_nothing_and_never_counts_rows() -> None:
    rows = build(review=AccidentReview(False, REVIEW.crosswalk))
    assert {row["coverage_key"] for row in rows} == {"measure_unconfirmed"}
    assert {row["accident_count"] for row in rows} == {None}


def test_zone_without_reviewed_crosswalk_is_geography_missing_not_zero() -> None:
    rows = build(review=AccidentReview(True, {51: "INVENTED-zone-a"}))
    missing = [row for row in rows if row["source_zone"] == "52"]
    assert missing == [
        {
            "source_zone": "52",
            "period": "2024",
            "zone_code": None,
            "accident_count": None,
            "coverage_key": "geography_missing",
            "as_of": date(2026, 11, 20),
            "source_id": SOURCE,
        }
    ]


def test_year_keeps_its_published_precision_and_invents_nothing() -> None:
    dated = [{"accident_year": "2024-03-09", "zone": 51, "total": 1}]
    assert [row["period"] for row in build(records=dated)] == ["2024"]


# One input changed per case; every other input stays valid (L-1409).
@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"records": []}, "accident_records_empty"),
        ({"records": [*records(), "INVENTED"]}, "accident_record_invalid"),
        (
            {"records": [{"accident_year": "2024", "zone": 51}]},
            "accident_field_missing",
        ),
        (
            {"records": [{**records()[0], "unit_id": "INVENTED"}]},
            "accident_field_unknown",
        ),
        (
            {"records": [{**records()[0], "zone": "51"}]},
            "accident_zone_invalid",
        ),
        ({"records": [{**records()[0], "zone": True}]}, "accident_zone_invalid"),
        ({"records": [{**records()[0], "zone": -1}]}, "accident_zone_invalid"),
        ({"records": [{**records()[0], "zone": None}]}, "accident_zone_invalid"),
        (
            {"records": [{**records()[0], "accident_year": "24"}]},
            "accident_year_invalid",
        ),
        (
            {"records": [{**records()[0], "accident_year": 2024}]},
            "accident_year_invalid",
        ),
        (
            {"records": [{**records()[0], "accident_year": "2024-13-01"}]},
            "accident_year_invalid",
        ),
        (
            {"records": [{**records()[0], "accident_year": "2024-02-30"}]},
            "accident_year_invalid",
        ),
        ({"records": [{**records()[0], "total": None}]}, "accident_total_invalid"),
        ({"records": [{**records()[0], "total": True}]}, "accident_total_invalid"),
        ({"records": [{**records()[0], "total": 1.5}]}, "accident_total_invalid"),
        ({"records": [{**records()[0], "total": -1}]}, "accident_total_invalid"),
        (
            {
                "records": [
                    {**records()[0], "total": 2**62},
                    {**records()[0], "total": 2**62},
                ]
            },
            "accident_count_overflow",
        ),
        (
            {"review": AccidentReview(True, {51: "INVENTED-zone-z"})},
            "accident_crosswalk_invalid",
        ),
        (
            {
                "review": AccidentReview(
                    True, {51: "INVENTED-zone-a", 52: "INVENTED-zone-a"}
                )
            },
            "accident_geography_allocation",
        ),
        ({"source_id": ""}, "accident_source_invalid"),
        ({"as_of": "2026-11"}, "accident_as_of_invalid"),
        # fromisoformat takes the week form; only the shape check refuses it.
        ({"as_of": "2026-W47-5"}, "accident_as_of_invalid"),
    ],
)
def test_each_refusal_has_its_own_closed_reason(
    changes: dict[str, object], reason: str
) -> None:
    with pytest.raises(AccidentRefusal, match="^" + reason + "$") as caught:
        build(**changes)
    assert caught.value.reason == reason


YEARS = st.sampled_from(("2023", "2024", "2025"))
RECORD = st.fixed_dictionaries(
    {
        "accident_year": YEARS,
        "zone": st.sampled_from((51, 52, 53)),
        "total": st.integers(min_value=0, max_value=10**6),
    }
)


@given(st.lists(RECORD, min_size=1, max_size=40), st.randoms())
def test_order_invariance_exact_sums_and_source_zone_retention(
    drawn: list[dict[str, object]], shuffle: object
) -> None:
    review = AccidentReview(True, {51: "INVENTED-zone-a", 52: "INVENTED-zone-b"})
    first = build(records=drawn, review=review)
    shuffled = list(drawn)
    shuffle.shuffle(shuffled)  # type: ignore[attr-defined]
    assert build(records=shuffled, review=review) == first
    # Exact-integer oracle: each (zone, year) count is the sum of its totals;
    # indistinguishable records are never deduplicated.
    for row in first:
        same = [
            r
            for r in drawn
            if str(r["zone"]) == row["source_zone"]
            and r["accident_year"] == row["period"]
        ]
        assert same
        if row["source_zone"] == "53":
            assert row["coverage_key"] == "geography_missing"
            assert row["accident_count"] is None and row["zone_code"] is None
        else:
            assert row["coverage_key"] == "counted"
            assert row["accident_count"] == sum(int(r["total"]) for r in same)  # type: ignore[call-overload]
            assert row["zone_code"] == review.crosswalk[int(row["source_zone"])]  # type: ignore[arg-type]
    assert {(r["source_zone"], r["period"]) for r in first} == {
        (str(r["zone"]), r["accident_year"]) for r in drawn
    }
    assert set(COVERAGE_KEYS) >= {row["coverage_key"] for row in first}


def _registered_absence(row):  # the gather_audit rule, unchanged
    from eii_custodian.publicdata import completeness as c

    return (
        {row.key: c.Absence(row.skip_reason, row.caveat_keys[0])}
        if row.skip_reason and row.caveat_keys
        else {}
    )


def _own(results):
    return [item for item in results if item["id"] == "accident"]


def _absence_inputs(row):
    from eii_custodian.publicdata import completeness as c

    return dict(
        entries=[row],
        pack=c.Pack({row.source_id: ()}, frozenset()),
        inventory={row.source_id: ()},
        catalogue={"pub_accident_zone"},
        receipts={},
        outputs={},
        absences=_registered_absence(row),
        cached_source_ids=(),
    )


def test_pending_registered_source_is_one_sealed_absence_and_no_table() -> None:
    """Amendment 3, pending source: NO_DATA with the registered caveat."""
    from custodian.tests.singles_entries import _loaded

    from eii_custodian.publicdata import completeness as c
    from eii_custodian.publicdata.accidents import SOURCE_MISSING_CAVEAT

    row = _loaded("accident")
    assert row.release_tables == ("pub_accident_zone",)
    assert row.caveat_keys == (SOURCE_MISSING_CAVEAT,)
    inputs = _absence_inputs(row)
    assert _own(c.check(**inputs)) == [
        {
            "id": "accident",
            "state": "NO_DATA",
            "reason": "partition_byte_bound_unconfirmed",
            "caveat": SOURCE_MISSING_CAVEAT,
        }
    ]
    # No receipt or table is fabricated: an output for the absent source fails.
    inputs["outputs"] = {"accident": ("pub_accident_zone",)}
    assert {
        "id": "accident",
        "state": "failed",
        "reason": "source_completeness: output for absent source",
    } in _own(c.check(**inputs))


def test_pending_source_without_its_caveat_fails_the_report() -> None:
    """Plant: drop only the registered caveat (the base-commit registry state)."""
    from dataclasses import replace

    from custodian.tests.singles_entries import _loaded

    from eii_custodian.publicdata import completeness as c

    row = replace(_loaded("accident"), caveat_keys=())
    assert _own(c.check(**_absence_inputs(row))) == [
        {
            "id": "accident",
            "state": "failed",
            "reason": "source_absence_reason_missing",
        }
    ]
