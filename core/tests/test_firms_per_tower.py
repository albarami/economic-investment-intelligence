"""Firms per tower are a count of companies (DAT-168). Invented rows only."""

import pytest

from eii_core.calc.firms_per_tower import (
    CLASS_KEYS,
    FirmsPerTowerError,
    firms_per_tower,
)


def company(
    key: str,
    tower: str | None = None,
    position: tuple[str, str] | None = None,
    district: str | None = None,
    *,
    district_free_zone: bool = False,
) -> dict[str, object]:
    return {
        "registration_key": key,
        "tower_or_building": tower,
        "position": position,
        "district_key": district,
        "district_free_zone": district_free_zone,
    }


def test_companies_are_counted_per_published_tower() -> None:
    result = firms_per_tower(
        [
            company("INV-FC-ALEPH-ONE", "Invented Tower Aleph", ("51.5", "25.3")),
            company("INV-FC-ALEPH-TWO", "Invented Tower Aleph", ("51.5", "25.3")),
            company("INV-FC-BET-ONE", "Invented Tower Bet", ("51.6", "25.4")),
        ]
    )
    counts = {item.tower: item.count for item in result.towers}
    assert counts == {"Invented Tower Aleph": 2, "Invented Tower Bet": 1}
    aleph = next(item for item in result.towers if item.tower == "Invented Tower Aleph")
    assert aleph.companies == ("INV-FC-ALEPH-ONE", "INV-FC-ALEPH-TWO")
    assert aleph.position_status == "agree"
    assert aleph.position == ("51.5", "25.3")
    assert result.districts == ()
    assert result.unplaced == ()


def test_a_company_with_no_published_building_counts_in_its_district() -> None:
    result = firms_per_tower([company("INV-FC-DISTRICT-ONE", district="INV-NORTH")])
    assert result.towers == ()
    assert len(result.districts) == 1
    assert result.districts[0].district_key == "INV-NORTH"
    assert result.districts[0].count == 1
    assert result.districts[0].companies == ("INV-FC-DISTRICT-ONE",)
    assert result.breaks == ()
    assert result.districts[0].class_key == "district_count"


def test_a_planted_sum_of_employee_counts_is_not_a_tower_count() -> None:
    row = company("INV-FC-ALEPH-ONE", "Invented Tower Aleph", ("51.5", "25.3"))
    row["employee_count"] = 9
    with pytest.raises(FirmsPerTowerError, match="numeric_field"):
        firms_per_tower([row])


def test_a_planted_company_counted_at_a_tower_its_card_does_not_publish_fails() -> None:
    row = company("INV-FC-MISPLACED", district="INV-NORTH")
    row["count_at"] = "Invented Tower Aleph"
    with pytest.raises(FirmsPerTowerError, match="tower_not_published"):
        firms_per_tower([row])


def test_the_breaks_are_equal_count_merge_when_equal_and_use_the_closed_class_keys() -> (
    None
):
    rows: list[dict[str, object]] = []
    for name, count in (
        ("Aleph", 1),
        ("Bet", 2),
        ("Gimel", 3),
        ("Dalet", 4),
        ("He", 5),
    ):
        for index in range(count):
            rows.append(
                company(
                    f"INV-FC-{name}-N{index}",
                    f"Invented Tower {name}",
                    ("51.5", "25.3"),
                )
            )
    distinct = firms_per_tower(rows)
    classes = {item.tower: item.class_key for item in distinct.towers}
    assert classes == {
        "Invented Tower Aleph": "band_low",
        "Invented Tower Bet": "band_mid_low",
        "Invented Tower Gimel": "band_mid",
        "Invented Tower Dalet": "band_mid_high",
        "Invented Tower He": "band_high",
    }
    assert tuple(band.class_key for band in distinct.breaks) == CLASS_KEYS
    assert tuple(band.low for band in distinct.breaks) == (1, 2, 3, 4, 5)

    equal = firms_per_tower(
        [
            company(f"INV-FC-SAME-{name}", f"Invented Tower {name}", ("51.5", "25.3"))
            for name in ("Aleph", "Bet", "Gimel", "Dalet", "He")
        ]
    )
    assert tuple(band.class_key for band in equal.breaks) == ("band_low",)
    assert {item.class_key for item in equal.towers} == {"band_low"}
    assert all(band.class_key in CLASS_KEYS for band in equal.breaks)


def test_an_unplaced_company_is_reported_never_counted_zero() -> None:
    result = firms_per_tower(
        [
            company("INV-FC-ZONE-FREE", district_free_zone=True),
            company("INV-FC-NOWHERE"),
        ]
    )
    reasons = {item.registration_key: item.reason for item in result.unplaced}
    assert reasons["INV-FC-ZONE-FREE"] == "zone_without_district"
    assert reasons["INV-FC-NOWHERE"] == "location_unresolved"
    assert "zone_without_district" not in {
        reasons["INV-FC-NOWHERE"],
    }
    assert result.districts == ()
    assert result.coverage["zone_without_district"] == 1
    assert result.coverage["location_unresolved"] == 1
    assert all(item.count > 0 for item in result.towers)
    assert all(item.count > 0 for item in result.districts)


def test_a_stretched_zone_without_district_key_is_not_applied() -> None:
    """A null cell that is not a reviewed district-free zone keeps its own reason."""
    result = firms_per_tower([company("INV-FC-STRETCHED")])
    assert result.unplaced[0].reason == "location_unresolved"
    assert "zone_without_district" not in result.coverage


def test_towers_whose_rows_disagree_or_lack_a_position_are_reported_per_reason() -> (
    None
):
    result = firms_per_tower(
        [
            company("INV-FC-NONE", "Invented Tower None"),
            company("INV-FC-DALET-ONE", "Invented Tower Dalet", ("51.5", "25.3")),
            company("INV-FC-DALET-TWO", "Invented Tower Dalet", ("51.6", "25.4")),
            company("INV-FC-AGREE", "Invented Tower Agree", ("51.5", "25.3")),
        ]
    )
    status = {item.tower: item.position_status for item in result.towers}
    assert status["Invented Tower None"] == "none"
    assert status["Invented Tower Dalet"] == "disagree"
    assert status["Invented Tower Agree"] == "agree"
    missing = next(
        item for item in result.towers if item.tower == "Invented Tower None"
    )
    split = next(item for item in result.towers if item.tower == "Invented Tower Dalet")
    assert missing.position is None
    assert split.position is None
    assert result.coverage["tower_without_position"] == 2


def test_a_district_count_above_the_tower_range_uses_the_high_class() -> None:
    rows: list[dict[str, object]] = []
    for name, count in (
        ("Aleph", 1),
        ("Bet", 2),
        ("Gimel", 3),
        ("Dalet", 4),
        ("He", 5),
    ):
        for index in range(count):
            rows.append(
                company(
                    f"INV-FC-SCALE-{name}-{index}",
                    f"Invented Tower {name}",
                    ("51.5", "25.3"),
                )
            )
    for index in range(6):
        rows.append(company(f"INV-FC-WIDE-{index}", district="INV-NORTH"))
    result = firms_per_tower(rows)
    assert result.districts[0].count == 6
    assert result.districts[0].class_key == "band_high"


def test_an_otherwise_valid_row_still_counts() -> None:
    result = firms_per_tower(
        [company("INV-FC-PLANT", "Invented Tower Aleph", ("51.5", "25.3"))]
    )
    assert result.towers[0].count == 1
    assert result.towers[0].class_key == "band_low"


@pytest.mark.parametrize(
    ("plant", "reason"),
    (
        ("not_a_mapping", "row_shape"),
        ("unknown_key", "row_shape"),
        ("blank_key", "row_shape"),
        ("untrimmed_key", "row_shape"),
        ("key_not_text", "row_shape"),
        ("free_zone_not_bool", "row_shape"),
        ("position_not_pair", "row_shape"),
        ("position_short", "row_shape"),
        ("position_part_not_text", "row_shape"),
        ("position_lat_not_text", "row_shape"),
        ("position_lon_blank", "row_shape"),
        ("position_lat_blank", "row_shape"),
        ("position_lon_untrimmed", "row_shape"),
        ("position_lat_untrimmed", "row_shape"),
        ("tower_not_text", "row_shape"),
        ("tower_untrimmed", "row_shape"),
        ("count_at_matches_tower", "row_shape"),
        ("number_on_allowed_key", "numeric_field"),
        ("nested_number", "numeric_field"),
    ),
)
def test_one_guarded_count_field_is_refused(plant: str, reason: str) -> None:
    row = company("INV-FC-PLANT", "Invented Tower Aleph", ("51.5", "25.3"))
    if plant == "not_a_mapping":
        with pytest.raises(FirmsPerTowerError, match=reason):
            firms_per_tower(["INV-FC-PLANT"])
        return
    if plant == "unknown_key":
        row["note"] = "extra"
    elif plant == "blank_key":
        row["registration_key"] = "   "
    elif plant == "untrimmed_key":
        row["registration_key"] = " INV-FC-PLANT"
    elif plant == "key_not_text":
        row["registration_key"] = None
    elif plant == "free_zone_not_bool":
        row["district_free_zone"] = "yes"
    elif plant == "position_not_pair":
        row["position"] = ["51.5", "25.3"]
    elif plant == "position_short":
        row["position"] = ("51.5",)
    elif plant == "position_part_not_text":
        row["position"] = (["51.5"], "25.3")
    elif plant == "position_lat_not_text":
        row["position"] = ("51.5", ["25.3"])
    elif plant == "position_lon_blank":
        row["position"] = ("", "25.3")
    elif plant == "position_lat_blank":
        row["position"] = ("51.5", "")
    elif plant == "position_lon_untrimmed":
        row["position"] = (" 51.5", "25.3")
    elif plant == "position_lat_untrimmed":
        row["position"] = ("51.5", " 25.3")
    elif plant == "tower_not_text":
        row["tower_or_building"] = ["Invented Tower Aleph"]
    elif plant == "tower_untrimmed":
        row["tower_or_building"] = " Invented Tower Aleph"
    elif plant == "count_at_matches_tower":
        row["count_at"] = "Invented Tower Aleph"
    elif plant == "number_on_allowed_key":
        row["tower_or_building"] = 2
    elif plant == "nested_number":
        row["position"] = ("51.5", 1)
    else:
        raise AssertionError(plant)
    with pytest.raises(FirmsPerTowerError, match=reason):
        firms_per_tower([row])
