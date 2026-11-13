"""Synthetic-only acceptance tests for the area spike (S1-T03)."""

import json
import socket
import subprocess
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest
from shapely.geometry import Point, Polygon

import h3
from eii_product.areas_spike.engine import scaled_actor
from eii_product.areas_spike.hour_speeds import load_factors
from eii_product.areas_spike.road import load_road
from eii_product.areas_spike.router import isochrone, routed_area
from eii_product.areas_spike.shapes import (
    Circle,
    canonical_ring,
    drawn_area,
    radius_area,
)
from eii_product.areas_spike.snap import snap_polygon, snap_radius

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike"
ROAD = load_road(FIXTURES / "road_network.json")
FACTORS = load_factors(FIXTURES / "speed_table.json")
FRAME = tuple(json.loads((FIXTURES / "frame_cells.json").read_text())["cells"])
PIN = next(node for node in ROAD["nodes"] if node["id"] == ROAD["pin"])
POINT = (PIN["lat"], PIN["lon"])
PIN_CELL = h3.latlng_to_cell(*POINT, 9)
DRAWN = ((-0.01, -0.01), (-0.01, 0.01), (0.01, 0.01), (0.01, -0.01))


def fixture_outputs() -> str:
    areas = {
        "radius": radius_area(POINT, ROAD["radius_m"], PIN_CELL, FRAME),
        "drawn": drawn_area(DRAWN, FRAME),
    }
    for mode in ("walk", "drive"):
        for hour in range(len(FACTORS)):
            areas[f"{mode}-{hour}"] = routed_area(
                ROAD, mode, ROAD["cutoff_seconds"], hour, FACTORS, FRAME
            )
    return (
        json.dumps(
            {name: asdict(area) for name, area in areas.items()},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def test_snapped_output_holds_only_whole_frame_cells() -> None:
    # Invented geometry, not an attribute of a named place.
    pin = h3.latlng_to_cell(0.0, 0.0, 9)
    frame = tuple(sorted(h3.grid_disk(pin, 1)))
    outline = ((-0.02, -0.02), (-0.02, 0.02), (0.02, 0.02), (0.02, -0.02))
    cells = snap_polygon(outline, frame)

    assert cells
    assert set(cells) == set(frame)
    for cell in cells:
        assert cell in frame, f"Non-frame cell: {cell}"
        assert h3.get_resolution(cell) == 9, f"Coarser parent: {cell}"

    mixed = snap_polygon(DRAWN, FRAME)
    assert {h3.get_resolution(cell) for cell in mixed} == {8, 9}
    assert set(mixed) <= set(FRAME)
    assert h3.cell_to_parent(PIN_CELL, 8) not in mixed
    assert mixed == tuple(sorted(mixed))


def test_routing_opens_no_server() -> None:
    # The finite tile-building subprocess finishes before routing begins.
    scaled_actor.cache_clear()
    for factor in set(FACTORS) | {1.0}:
        scaled_actor(json.dumps(ROAD, sort_keys=True), factor)
    with (
        patch.object(socket, "socket", side_effect=AssertionError("Socket opened")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("Connection opened")
        ),
        patch.object(
            subprocess,
            "Popen",
            side_effect=AssertionError("Process started while routing"),
        ),
    ):
        for mode in ("walk", "drive"):
            for hour in range(len(FACTORS)):
                assert routed_area(
                    ROAD, mode, ROAD["cutoff_seconds"], hour, FACTORS, FRAME
                ).cells


def test_drive_isochrone_changes_with_the_hour(tmp_path: Path) -> None:
    outlines = [
        isochrone(ROAD, "drive", ROAD["cutoff_seconds"], hour, FACTORS)
        for hour in range(len(FACTORS))
    ]
    for first in range(len(FACTORS)):
        for second in range(len(FACTORS)):
            assert (outlines[first] == outlines[second]) == (
                FACTORS[first] == FACTORS[second]
            )
    walking = [
        isochrone(ROAD, "walk", ROAD["cutoff_seconds"], hour, FACTORS)
        for hour in range(len(FACTORS))
    ]
    assert all(outline == walking[0] for outline in walking)
    changed = tmp_path / "speed_table.json"
    changed.write_text(json.dumps({"factors": [factor / 2 for factor in FACTORS]}))
    assert (
        isochrone(ROAD, "drive", ROAD["cutoff_seconds"], 0, load_factors(changed))
        != outlines[0]
    )
    assert (
        isochrone(ROAD, "walk", ROAD["cutoff_seconds"], 0, load_factors(changed))
        == walking[0]
    )
    for hour, outline in enumerate(outlines):
        assert (
            isochrone(ROAD, "drive", ROAD["cutoff_seconds"], hour, FACTORS) == outline
        )


def test_cutoff_keeps_reached_place_inside_and_far_place_outside() -> None:
    nodes = {node["id"]: node for node in ROAD["nodes"]}
    # These named invented places lie on the fixture's roads. The request uses
    # its cutoff, edge drive speeds and walking speed; no retreat edge times.
    for mode, near_id, far_id in (
        ("walk", "SYN-N-4-4", "SYN-N-4-5"),
        ("drive", "SYN-N-4-5", "SYN-N-4-8"),
    ):
        ring = isochrone(ROAD, mode, ROAD["cutoff_seconds"], 0, FACTORS)
        polygon = Polygon([(lon, lat) for lat, lon in ring])
        near, far = nodes[near_id], nodes[far_id]
        assert polygon.contains(Point(near["lon"], near["lat"]))
        assert not polygon.contains(Point(far["lon"], far["lat"]))
    for mode in ("walk", "drive"):
        short = isochrone(ROAD, mode, ROAD["cutoff_seconds"] / 2, 0, FACTORS)
        long = isochrone(ROAD, mode, ROAD["cutoff_seconds"], 0, FACTORS)
        assert short != long


def test_single_road_has_engine_polygon() -> None:
    collinear = {**ROAD, "pin": ROAD["edges"][0]["source"], "edges": ROAD["edges"][:1]}
    ring = isochrone(collinear, "drive", ROAD["cutoff_seconds"], 0, FACTORS)
    polygon = Polygon([(lon, lat) for lat, lon in ring])
    nodes = {node["id"]: node for node in ROAD["nodes"]}
    near = nodes[ROAD["edges"][0]["target"]]
    far = nodes[ROAD["pin"]]
    assert polygon.is_valid
    assert polygon.contains(Point(near["lon"], near["lat"]))
    assert not polygon.contains(Point(far["lon"], far["lat"]))


def test_each_shape_is_kept_exactly() -> None:
    drawn = drawn_area(DRAWN, FRAME)
    assert drawn.exact == (*DRAWN, DRAWN[0])
    assert canonical_ring((*DRAWN, DRAWN[0], DRAWN[0])) == drawn.exact
    assert canonical_ring((DRAWN[0], *reversed(DRAWN[1:]))) == drawn.exact
    radius = radius_area(POINT, ROAD["radius_m"], PIN_CELL, FRAME)
    assert radius.exact == Circle(POINT, ROAD["radius_m"])
    for bearing in range(0, 360, 15):
        assert h3.great_circle_distance(
            POINT, radius.exact.point(bearing), unit="m"
        ) == pytest.approx(ROAD["radius_m"], abs=1e-6)
    pin_center = h3.cell_to_latlng(PIN_CELL)
    expected = tuple(
        cell
        for cell in FRAME
        if h3.great_circle_distance(pin_center, h3.cell_to_latlng(cell), unit="m")
        <= ROAD["radius_m"]
    )
    assert radius.cells == expected
    for mode in ("walk", "drive"):
        area = routed_area(ROAD, mode, ROAD["cutoff_seconds"], 0, FACTORS, FRAME)
        assert area.exact == isochrone(ROAD, mode, ROAD["cutoff_seconds"], 0, FACTORS)


def test_radius_includes_boundary_and_uses_pin_cell_center() -> None:
    neighbor = next(cell for cell in FRAME if cell != PIN_CELL)
    distance = h3.great_circle_distance(
        h3.cell_to_latlng(PIN_CELL), h3.cell_to_latlng(neighbor), unit="m"
    )
    assert neighbor in snap_radius(PIN_CELL, distance, FRAME)
    assert neighbor not in snap_radius(PIN_CELL, distance / 2, FRAME)
    shifted = (POINT[0] + 0.0001, POINT[1])
    assert (
        radius_area(shifted, ROAD["radius_m"], PIN_CELL, FRAME).cells
        == radius_area(POINT, ROAD["radius_m"], PIN_CELL, FRAME).cells
    )


def test_center_containment_keeps_entire_cell() -> None:
    lat, lon = h3.cell_to_latlng(PIN_CELL)
    tiny = (
        (lat - 0.000001, lon - 0.000001),
        (lat - 0.000001, lon + 0.000001),
        (lat + 0.000001, lon + 0.000001),
        (lat + 0.000001, lon - 0.000001),
    )
    assert snap_polygon(tiny, FRAME) == (PIN_CELL,)


def test_circle_away_from_equator() -> None:
    circle = Circle((12.5, 32.5), ROAD["radius_m"])
    for bearing in range(0, 360, 15):
        assert h3.great_circle_distance(
            circle.center, circle.point(bearing), unit="m"
        ) == pytest.approx(circle.radius_m, abs=1e-6)


def test_deterministic_fixtures_pass() -> None:
    scaled_actor.cache_clear()
    first = fixture_outputs()
    scaled_actor.cache_clear()
    assert first == fixture_outputs()
    assert first == (FIXTURES / "expected_outputs.json").read_text()


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_distances_and_cutoffs(value: float) -> None:
    with pytest.raises(ValueError, match="Radius"):
        snap_radius(PIN_CELL, value, FRAME)
    with pytest.raises(ValueError, match="Cutoff"):
        isochrone(ROAD, "drive", value, 0, FACTORS)


@pytest.mark.parametrize("hour", [-1, 24])
def test_invalid_hour(hour: int) -> None:
    with pytest.raises(ValueError, match="hour"):
        isochrone(ROAD, "drive", ROAD["cutoff_seconds"], hour, FACTORS)


def test_invalid_mode() -> None:
    with pytest.raises(ValueError, match="mode"):
        isochrone(ROAD, "flight", ROAD["cutoff_seconds"], 0, FACTORS)


@pytest.mark.parametrize(
    "ring",
    [(), ((0.0, 0.0),), ((0.0, 0.0), (0.0, 1.0)), ((0.0, 0.0), (0.0, 1.0), (0.0, 2.0))],
)
def test_invalid_polygon(ring: tuple[tuple[float, float], ...]) -> None:
    with pytest.raises(ValueError, match="polygon"):
        canonical_ring(ring)


@pytest.mark.parametrize(
    "factors",
    [
        [1.0] * 23,
        [1.0] * 25,
        [0.0] * 24,
        [-1.0] * 24,
        [float("nan")] * 24,
        [float("inf")] * 24,
        [1.0] * 23 + [0.0],
        [1.0] * 23 + [float("nan")],
    ],
)
def test_invalid_factors(tmp_path: Path, factors: list[float]) -> None:
    path = tmp_path / "speed_table.json"
    path.write_text(json.dumps({"factors": factors}))
    with pytest.raises(ValueError):
        load_factors(path)


def test_empty_snap_is_refused() -> None:
    with pytest.raises(ValueError, match="no frame cell"):
        snap_polygon(DRAWN, ())
    with pytest.raises(ValueError, match="no frame cell"):
        snap_radius(PIN_CELL, ROAD["radius_m"], ())
