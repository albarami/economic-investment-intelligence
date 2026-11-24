"""Exact reader refusals against the imported invented stand-in only."""

import json
from pathlib import Path
from typing import Any

import pytest
from product.tests.test_fc_register_read import FIXTURE, _copy, _plant_reader, listed
from product.tests.test_fc_register_read import (
    configured_register as configured_register,
)

from eii_product.register_file import RegisterRefusal, read_fc_register_rows


def _unchecked(value: object) -> Any:
    return value


def _refusal(caught: pytest.ExceptionInfo[RegisterRefusal], reason: str) -> None:
    assert str(caught.value) == reason
    assert caught.value.reason == reason
    assert caught.value.args == (reason,)


@pytest.mark.parametrize("setting", ["", False, 3, []])
def test_setting_refusal(setting: object) -> None:
    with pytest.raises(RegisterRefusal) as caught:
        read_fc_register_rows(_unchecked(setting), listed_sha256="0" * 64)
    _refusal(caught, "row_shape")


def test_path_refusal(tmp_path: Path) -> None:
    with pytest.raises(RegisterRefusal) as caught:
        copy = str(_copy(tmp_path))
        read_fc_register_rows(
            copy, listed_sha256=listed(copy), asked_path="invented-other.json"
        )
    _refusal(caught, "path_refused")


@pytest.mark.parametrize("raw", ["{", "[]", "null", "false"])
def test_document_refusal(tmp_path: Path, raw: str) -> None:
    path = _copy(tmp_path)
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(RegisterRefusal) as caught:
        read_fc_register_rows(str(path), listed_sha256=listed(str(path)))
    _refusal(caught, "row_shape")


@pytest.mark.parametrize(
    "plant",
    [
        "duplicate_registration_key",
        "duplicate_row_id",
        "lon_without_lat",
        "lat_without_lon",
        "lon_syntax",
        "lat_syntax",
        "card_not_object",
        "card_missing_field",
        "card_extra_field",
        "card_blank",
        "card_untrimmed",
        "card_not_text",
        "release_hash_not_text",
        "release_hash_syntax",
        "source_hash_not_text",
        "source_hash_syntax",
        "year_not_text",
        "year_syntax",
        "date_not_text",
        "date_syntax",
        "date_impossible",
    ],
)
def test_existing_plants_have_exact_refusals(tmp_path: Path, plant: str) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _plant_reader(parsed, plant)
    path = _copy(tmp_path)
    path.write_text(json.dumps(parsed), encoding="utf-8")
    with pytest.raises(RegisterRefusal) as caught:
        read_fc_register_rows(str(path), listed_sha256=listed(str(path)))
    _refusal(caught, "row_shape")


@pytest.mark.parametrize(
    ("route", "value"),
    [
        (("rows",), []),
        (("rows",), {}),
        (("rows", 0), []),
        (("rows", 0, "unknown"), "invented"),
        (("rows", 0, "row_id"), "invented-wrong"),
        (("rows", 0, "row_id"), None),
        (("rows", 0, "district_free_zone"), "false"),
        (("rows", 0, "registration_key"), ""),
        (("rows", 0, "registration_key"), " INV-SPACE"),
        (("rows", 0, "registration_key"), False),
        (("rows", 0, "card", "trade_name"), ""),
        (("gazetteer",), {}),
        (("gazetteer", 0), []),
        (("gazetteer", 0, "place_code"), "invented-wrong"),
        (("gazetteer", 0, "place_code"), None),
        (("gazetteer", 1, "tower_or_building"), "Invented Tower Aleph"),
        (("districts",), {}),
        (("districts", 0), []),
        (("districts", 0, "ring"), []),
        (("districts", 0, "ring"), None),
        (("districts", 0, "ring"), [["1.0", "2.0"], ["1.1", "2.0"], ["1.0", "2.0"]]),
        (("districts", 0, "ring", 0), ["1.0"]),
        (("districts", 0, "ring", 0), "invented"),
        (("districts", 0, "ring", 0, 0), "invented"),
        (("districts", 0, "ring", 0, 1), "invented"),
        (("districts", 0, "ring", 0, 0), None),
        (("districts", 0, "ring", 0, 1), None),
        (("source",), []),
        (("lineage",), []),
    ],
)
def test_field_refusals(
    tmp_path: Path, route: tuple[str | int, ...], value: object
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    target = parsed
    for part in route[:-1]:
        target = target[part]
    target[route[-1]] = value
    path = _copy(tmp_path)
    path.write_text(json.dumps(parsed), encoding="utf-8")
    with pytest.raises(RegisterRefusal) as caught:
        read_fc_register_rows(str(path), listed_sha256=listed(str(path)))
    _refusal(caught, "row_shape")


def test_duplicate_district_refusal(tmp_path: Path) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["districts"].append(parsed["districts"][0])
    path = _copy(tmp_path)
    path.write_text(json.dumps(parsed), encoding="utf-8")
    with pytest.raises(RegisterRefusal) as caught:
        read_fc_register_rows(str(path), listed_sha256=listed(str(path)))
    _refusal(caught, "row_shape")


def test_gazetteer_fields_and_explicit_same_path(tmp_path: Path) -> None:
    path = str(_copy(tmp_path))
    bundle = read_fc_register_rows(path, listed_sha256=listed(path), asked_path=path)
    assert bundle is not None
    assert tuple(bundle.gazetteer) == (
        "Invented Tower Aleph",
        "Invented Tower Bet",
        "Invented Tower Gimel",
        "Invented Tower Dalet",
    )
    assert (
        bundle.gazetteer["Invented Tower Aleph"].tower_or_building
        == "Invented Tower Aleph"
    )
    assert (
        bundle.gazetteer["Invented Tower Aleph"].place_code == "place:INV-TOWER-ALEPH"
    )
    assert bundle.rows[0].card == (
        ("trade_name", "Invented House Aleph"),
        ("activity", "Sample finance activity"),
    )
    assert bundle.districts["INV-NORTH"].ring == (
        ("51.4", "25.2"),
        ("51.6", "25.2"),
        ("51.6", "25.4"),
        ("51.4", "25.2"),
    )


def test_reader_decodes_utf8_after_the_hash(tmp_path: Path) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["rows"][0]["card"]["trade_name"] = "Invented \u0628\u064a\u062a"
    path = _copy(tmp_path)
    path.write_bytes(json.dumps(parsed, ensure_ascii=False).encode("utf-8"))
    bundle = read_fc_register_rows(str(path), listed_sha256=listed(str(path)))
    assert bundle is not None
    assert bundle.rows[0].card[0] == ("trade_name", "Invented \u0628\u064a\u062a")
    path.write_bytes(json.dumps(parsed, ensure_ascii=False).encode("utf-16"))
    with pytest.raises(RegisterRefusal) as caught:
        read_fc_register_rows(str(path), listed_sha256=listed(str(path)))
    _refusal(caught, "row_shape")
