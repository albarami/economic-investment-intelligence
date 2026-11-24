"""Invented identifiers. Full refusal text and the closed area-id grammar."""

from __future__ import annotations

from decimal import Decimal

import pytest

from eii_product.tools.areas import (
    INVALID_ARGUMENT,
    AreaIdError,
    build_area_id,
    canonical_json,
    format_six,
    parse_area_id,
)

_RELEASE = "abcdef0123456789rest"
_PREFIX = "abcdef0123456789"
_OTHER = "1234567890abcdef"
_SHAPE = "ab" * 32
_PIN = f"ma1/{_PREFIX}/distance/5/none/1.500000/2.500000"


def full_message(error: BaseException, expected: str) -> None:
    """Compare the whole refusal with a hand-written literal."""
    assert str(error) == expected


def test_a_pin_id_round_trips_the_hand_written_fields() -> None:
    built = build_area_id(
        release_id=_RELEASE,
        mode="distance",
        cutoff=5,
        cell=None,
        latitude=Decimal("1.5"),
        longitude=Decimal("2.5"),
    )
    assert built == _PIN
    parsed = parse_area_id(_PIN, _RELEASE)
    assert parsed == {
        "mode": "distance",
        "cutoff": 5,
        "cell": None,
        "latitude": Decimal("1.500000"),
        "longitude": Decimal("2.500000"),
    }


def test_a_polygon_id_keeps_only_the_shape() -> None:
    text = f"ma1/{_PREFIX}/polygon/{_SHAPE}"
    assert build_area_id(release_id=_RELEASE, shape_id=_SHAPE) == text
    assert parse_area_id(text, _RELEASE) == {"shape_id": _SHAPE}


def test_one_missing_pin_field_is_refused() -> None:
    cases = (
        {"cutoff": 5, "latitude": Decimal("1.5"), "longitude": Decimal("2.5")},
        {"mode": "distance", "latitude": Decimal("1.5"), "longitude": Decimal("2.5")},
        {"mode": "distance", "cutoff": 5, "longitude": Decimal("2.5")},
        {"mode": "distance", "cutoff": 5, "latitude": Decimal("1.5")},
    )
    for fields in cases:
        with pytest.raises(AreaIdError) as caught:
            build_area_id(release_id=_RELEASE, **fields)
        full_message(caught.value, INVALID_ARGUMENT)


def test_malformed_ids_use_the_full_text() -> None:
    shape = f"ma1/{_PREFIX}/polygon/{_SHAPE}"
    samples = (
        "ma1",
        "no/abcdef0123456789/polygon",
        f"ma1/{_OTHER}/distance/5/none/1.500000/2.500000",
        f"ma1/{_PREFIX}/polygon/zz",
        f"{shape}/extra",
        f"ma1/{_PREFIX}/fly/5/none/1.500000/2.500000",
        f"{_PIN}/extra",
        f"ma1/{_PREFIX}/distance/x/none/1.500000/2.500000",
        f"ma1/{_PREFIX}/distance/5/nope/1.500000/2.500000",
        f"ma1/{_PREFIX}/distance/5/none/1/2.500000",
    )
    for text in samples:
        with pytest.raises(AreaIdError) as caught:
            parse_area_id(text, _RELEASE)
        full_message(caught.value, INVALID_ARGUMENT)


def test_six_places_keep_the_sign_and_truncate_the_tail() -> None:
    assert format_six(Decimal("1")) == "1.000000"
    assert format_six(Decimal("-1.5")) == "-1.500000"
    assert format_six(Decimal("1.23456789")) == "1.234567"
    assert format_six(Decimal("1E+2")) == "100.000000"
    assert format_six(Decimal("Infinity")) == "Infinity.000000"


def test_canonical_json_is_the_hand_written_bytes() -> None:
    assert canonical_json(None) == b"null"
    assert canonical_json(True) == b"true"
    assert canonical_json(False) == b"false"
    assert canonical_json(2) == b"2"
    assert canonical_json("a") == b'"a"'
    assert canonical_json("é") == '"é"'.encode()
    assert canonical_json([1, None]) == b"[1,null]"
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonical_json(Decimal("1E+2")) == b"100"
    assert canonical_json(Decimal("NaN")) == b"NaN"
    assert canonical_json(Decimal("Infinity")) == b"Infinity"
    assert canonical_json((1, 2)) == b"[1,2]"
    assert canonical_json({10: 0, 2: 1}) == b'{"10":0,"2":1}'
    assert canonical_json({"é": 1}) == '{"é":1}'.encode()
    with pytest.raises(TypeError) as caught:
        canonical_json(object())
    full_message(caught.value, INVALID_ARGUMENT)
