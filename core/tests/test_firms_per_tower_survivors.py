"""Exact refusal and placement regressions using invented companies."""

from typing import Any

import pytest
from test_firms_per_tower import company

from eii_core.calc import firms_per_tower as calc


def _unchecked(value: object) -> Any:
    return value


def _refusal(
    caught: pytest.ExceptionInfo[calc.FirmsPerTowerError], reason: str
) -> None:
    assert str(caught.value) == reason
    assert caught.value.reason == reason
    assert caught.value.args == (reason,)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("registration_key", "", "row_shape"),
        ("registration_key", None, "row_shape"),
        ("registration_key", " INV-ONE", "row_shape"),
        ("employee_count", "invented", "numeric_field"),
        ("tower_or_building", 2, "numeric_field"),
        ("position", ((1,), "2.0"), "numeric_field"),
        ("count_at", "Invented Other Tower", "tower_not_published"),
        ("count_at", "Invented Tower", "row_shape"),
        ("unknown", "invented", "row_shape"),
        ("district_free_zone", "false", "row_shape"),
        ("tower_or_building", ["Invented Tower"], "row_shape"),
        ("tower_or_building", " Invented Tower", "row_shape"),
        ("position", ["1.0", "2.0"], "row_shape"),
        ("position", ("1.0",), "row_shape"),
        ("position", ([], "2.0"), "row_shape"),
        ("position", ("1.0", []), "row_shape"),
        ("position", ("", "2.0"), "row_shape"),
        ("position", ("1.0", ""), "row_shape"),
        ("position", (" 1.0", "2.0"), "row_shape"),
        ("position", ("1.0", "2.0 "), "row_shape"),
    ],
)
def test_refusal_fields(field: str, value: object, reason: str) -> None:
    row = company("INV-ONE", "Invented Tower", ("1.0", "2.0"))
    row[field] = value
    with pytest.raises(calc.FirmsPerTowerError) as caught:
        calc.firms_per_tower([row])
    _refusal(caught, reason)


def test_refusal_non_dictionary() -> None:
    with pytest.raises(calc.FirmsPerTowerError) as caught:
        calc.firms_per_tower(_unchecked(["invented"]))
    _refusal(caught, "row_shape")


def test_position_status_refusal() -> None:
    # _position rejects this before _position_status in the public entry point.
    with pytest.raises(calc.FirmsPerTowerError) as caught:
        calc._position_status([{"position": "invented"}])
    _refusal(caught, "row_shape")


def test_mixed_placement_order_counts_and_coverage() -> None:
    result = calc.firms_per_tower(
        [
            company("INV-LOST-A"),
            company("INV-TOWER-A", "Invented Tower A", ("1.0", "2.0"), "INV-NORTH"),
            company("INV-DISTRICT-A", district="INV-NORTH"),
            company("INV-LOST-B"),
            company("INV-TOWER-B", "Invented Tower B"),
            company("INV-DISTRICT-B", district="INV-NORTH"),
            company("INV-FREE-A", district_free_zone=True),
            company("INV-FREE-B", district_free_zone=True),
        ]
    )
    assert result.towers == (
        calc.TowerCount(
            "Invented Tower A", 1, "band_low", ("1.0", "2.0"), "agree", ("INV-TOWER-A",)
        ),
        calc.TowerCount(
            "Invented Tower B", 1, "band_low", None, "none", ("INV-TOWER-B",)
        ),
    )
    assert result.districts == (
        calc.DistrictCount(
            "INV-NORTH", 2, "band_low", ("INV-DISTRICT-A", "INV-DISTRICT-B")
        ),
    )
    assert result.unplaced == (
        calc.UnplacedCompany("INV-LOST-A", "location_unresolved"),
        calc.UnplacedCompany("INV-LOST-B", "location_unresolved"),
        calc.UnplacedCompany("INV-FREE-A", "zone_without_district"),
        calc.UnplacedCompany("INV-FREE-B", "zone_without_district"),
    )
    assert result.coverage == {
        "tower_without_position": 1,
        "location_unresolved": 2,
        "zone_without_district": 2,
    }
    assert result.breaks == (calc.ClassBreak("band_low", 1, 1, "Invented Tower B"),)


def test_omitted_defaults_and_empty_text() -> None:
    result = calc.firms_per_tower([{"registration_key": "INV-OMITTED"}])
    assert result == calc.FirmsPerTower(
        (),
        (),
        (calc.UnplacedCompany("INV-OMITTED", "location_unresolved"),),
        {"location_unresolved": 1},
        (),
    )
    row = company("INV-EMPTY", "", district="")
    assert calc.firms_per_tower([row]).unplaced == (
        calc.UnplacedCompany("INV-EMPTY", "location_unresolved"),
    )
    assert calc.firms_per_tower([]) == calc.FirmsPerTower((), (), (), {}, ())


def test_intermediate_groups_have_empty_class_before_assignment() -> None:
    # Public calculation replaces these intermediate records in _apply_classes.
    assert calc._towers([company("INV-TOWER", "Invented Tower")]) == [
        calc.TowerCount("Invented Tower", 1, "", None, "none", ("INV-TOWER",))
    ]
    assert calc._districts([company("INV-DISTRICT", district="INV-NORTH")]) == [
        calc.DistrictCount("INV-NORTH", 1, "", ("INV-DISTRICT",))
    ]


@pytest.mark.parametrize(
    ("count", "bands", "expected"),
    [
        (
            2,
            [
                calc.ClassBreak("band_low", 2, 4, "Invented A"),
                calc.ClassBreak("band_mid", 1, 3, "Invented B"),
            ],
            "band_low",
        ),
        (
            4,
            [
                calc.ClassBreak("band_low", 2, 4, "Invented A"),
                calc.ClassBreak("band_mid", 3, 5, "Invented B"),
            ],
            "band_low",
        ),
        (
            2,
            [
                calc.ClassBreak("band_low", 3, 2, "Invented A"),
                calc.ClassBreak("band_mid", 5, 6, "Invented B"),
            ],
            "band_low",
        ),
    ],
)
def test_class_selection_on_direct_band_inputs(
    count: int, bands: list[calc.ClassBreak], expected: str
) -> None:
    # _breaks supplies disjoint increasing bands; exercise the helper's own inputs.
    assert calc._class_of(count, bands) == expected
