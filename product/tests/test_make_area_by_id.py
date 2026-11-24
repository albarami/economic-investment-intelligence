"""make_area by a returned area_id (decision 0087): the BE-86 decode, nothing else."""

from __future__ import annotations

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from product.tests.make_area_support import (
    NO_CELL,
    ORIGIN,
    RELEASE_ID,
    SHAPE_INSIDE,
    SHAPE_OTHER,
    RecordingStore,
    box_route,
    context,
    geometry_rows,
)

from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import (
    INVALID_ARGUMENT,
    AreaIdRequest,
    ArgumentError,
    canonical_payload,
    make_area,
    validate_request,
)


def _run(request: dict):
    store = RecordingStore(PACKAGED, geometry_rows())
    return make_area(store, request, context(PACKAGED, routing=box_route)), store


def _pin(mode: str, cutoff: int, point=ORIGIN) -> dict:
    return {
        "latitude": float(point[0]),
        "longitude": float(point[1]),
        "mode": mode,
        "cutoff": cutoff,
    }


REQUESTS = (
    _pin("distance", 250),
    _pin("walk", 5),
    _pin("drive", 10),
    {"shape_id": SHAPE_INSIDE},
    _pin("distance", 1000, NO_CELL),
)


def _walk_id() -> str:
    return _run(_pin("walk", 5))[0].payload["area_id"]


@pytest.mark.parametrize("request_body", REQUESTS)
def test_area_id_input_gives_the_byte_identical_payload(request_body) -> None:
    first, _store = _run(request_body)
    second, _store = _run({"area_id": first.payload["area_id"]})
    assert second.status == "OK"
    assert canonical_payload(second) == canonical_payload(first)


def test_the_closed_schema_accepts_exactly_the_identifier() -> None:
    area_id = _walk_id()
    assert validate_request({"area_id": area_id}, None) == AreaIdRequest(area_id)


# Each case changes ONE input of a valid {"area_id": id} request.
@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda i: {"area_id": i, "mode": "walk"}, id="extra-field"),
        pytest.param(lambda i: {"area_id": i, "ring": []}, id="geometry-field"),
        pytest.param(lambda i: {"area_id": i.encode()}, id="not-text"),
        pytest.param(lambda i: {"area_id": "ma1/not-an-area"}, id="malformed"),
        pytest.param(lambda i: {"area_id": i + "/0"}, id="extra-part"),
    ],
)
def test_schema_refusals_read_nothing(change) -> None:
    request = change(_walk_id())
    with pytest.raises(ArgumentError, match=f"^{INVALID_ARGUMENT}$"):
        validate_request(request, None)
    result, store = _run(request)
    assert (result.status, result.payload, store.calls) == (INVALID_ARGUMENT, None, [])


def test_another_releases_identifier_passes_grammar_and_refuses_before_a_read():
    foreign = _walk_id().replace(RELEASE_ID[:16], "ff" * 8, 1)
    assert isinstance(validate_request({"area_id": foreign}, None), AreaIdRequest)
    result, store = _run({"area_id": foreign})
    assert (result.status, result.payload, store.calls) == (INVALID_ARGUMENT, None, [])


def test_another_session_shape_identifier_refuses() -> None:
    other = f"ma1/{RELEASE_ID[:16]}/polygon/{SHAPE_OTHER}"
    assert isinstance(validate_request({"area_id": other}, None), AreaIdRequest)
    result, _store = _run({"area_id": other})
    assert (result.status, result.payload) == (INVALID_ARGUMENT, None)


def test_a_respelled_identifier_refuses_on_the_recomputed_id() -> None:
    parts = _walk_id().split("/")
    parts[4] = "none"
    result, store = _run({"area_id": "/".join(parts)})
    assert (result.status, result.payload) == (INVALID_ARGUMENT, None)
    assert store.calls  # refused after the read, by the BE-86 equality


_VALID = [_run(r)[0].payload["area_id"] for r in REQUESTS]


@st.composite
def _identifiers(draw) -> str:
    base = draw(st.sampled_from(_VALID))
    if draw(st.booleans()):
        return base
    position = draw(st.integers(0, len(base)))
    inserted = draw(st.text(alphabet="/0123456789abcdefnoe.-", max_size=3))
    cut = draw(st.integers(0, 3))
    return base[:position] + inserted + base[position + cut :]


# A well-formed identifier whose pin lies off the land is decoded like the pin
# request it spells: BE-86's decode answers OUT_OF_SCOPE (or NO_DATA where the
# pin has no base cell) with no payload; it never answers OK for another area.
_DECODED_REFUSALS = {INVALID_ARGUMENT, "OUT_OF_SCOPE", "NO_DATA"}
_OFF_LAND = "ma1/abababababababab/distance/250/619056821840379903/0.000000/0.100000"


@settings(max_examples=200, deadline=None)
@given(_identifiers())
@example(_OFF_LAND)
def test_an_ok_answer_always_carries_the_requested_identifier(area_id) -> None:
    result, _store = _run({"area_id": area_id})
    assert result.status in {"OK"} | _DECODED_REFUSALS
    if result.status == "OK":
        assert result.payload["area_id"] == area_id
    else:
        assert result.payload is None


def test_an_identifier_off_the_land_answers_out_of_scope_without_payload() -> None:
    result, _store = _run({"area_id": _OFF_LAND})
    assert (result.status, result.payload) == ("OUT_OF_SCOPE", None)
