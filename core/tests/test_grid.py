"""Invented frame. Cells come from the grid library's own indexes, not a real place."""

from __future__ import annotations

import math

import pytest

import h3
from eii_core.grid import (
    base_cell,
    cell_centre,
    cells_in_circle,
    cells_in_polygon,
    resolution_8_children,
)
from eii_core.shapes import exact_point, great_circle_m, point_in_polygon


def _pair(latitude: float, longitude: float, resolution: int) -> tuple[int, int]:
    text = h3.latlng_to_cell(latitude, longitude, resolution)
    return h3.str_to_int(text), resolution


def _ring_around(latitude: float, longitude: float, delta: float):
    return (
        exact_point(latitude - delta, longitude - delta),
        exact_point(latitude - delta, longitude + delta),
        exact_point(latitude + delta, longitude + delta),
        exact_point(latitude + delta, longitude - delta),
        exact_point(latitude - delta, longitude - delta),
    )


def test_base_cell_is_the_r9_cell_or_its_stored_r8_parent() -> None:
    fine, _resolution = _pair(0.0, 0.0, 9)
    parent_text = h3.cell_to_parent(h3.int_to_str(fine), 8)
    parent = h3.str_to_int(parent_text)
    assert base_cell(0.0, 0.0, ((fine, 9),)) == fine
    assert base_cell(0.0, 0.0, ((parent, 8),)) == parent


def test_point_without_a_stored_cell_has_no_base_cell() -> None:
    other, _resolution = _pair(10.0, 10.0, 9)
    assert base_cell(0.0, 0.0, ((other, 9),)) is None

    def nearest(latitude, longitude, frame):
        del latitude, longitude
        return frame[0][0]

    def expect_none(holds) -> None:
        assert holds(0.0, 0.0, ((other, 9),)) is None

    expect_none(base_cell)
    with pytest.raises(AssertionError):
        expect_none(nearest)


def test_polygon_selects_by_centre_at_the_stored_resolution() -> None:
    fine, _resolution = _pair(0.0, 0.0, 9)
    parent = h3.str_to_int(h3.cell_to_parent(h3.int_to_str(fine), 8))
    centre = cell_centre(fine)
    ring = _ring_around(centre[0], centre[1], 0.00001)
    selected = cells_in_polygon((ring,), ((fine, 9), (parent, 8)))
    assert selected == (fine,)
    boundary = h3.cell_to_boundary(h3.int_to_str(fine))
    outside = exact_point(
        (centre[0] + boundary[0][0]) / 2 + (boundary[0][0] - centre[0]),
        (centre[1] + boundary[0][1]) / 2 + (boundary[0][1] - centre[1]),
    )
    # A point past a vertex is outside the hexagon. The centre of this cell is inside.
    assert point_in_polygon(exact_point(*centre), (ring,))
    assert not point_in_polygon(outside, (ring,))

    def compacted(polygon, frame):
        chosen = list(cells_in_polygon(polygon, frame))
        return tuple(sorted({*chosen, parent}))

    def flag_resolution(polygon, frame):
        del polygon
        text = h3.latlng_to_cell(0.0, 0.0, 8)
        return (h3.str_to_int(text),)

    def absent(polygon, frame):
        del frame
        return cells_in_polygon(polygon, ((other_cell(), 9),))

    def expect_stored(holds) -> None:
        assert holds((ring,), ((fine, 9),)) == (fine,)

    expect_stored(cells_in_polygon)
    with pytest.raises(AssertionError):
        expect_stored(compacted)
    with pytest.raises(AssertionError):
        expect_stored(flag_resolution)
    with pytest.raises(AssertionError):
        expect_stored(absent)


def other_cell() -> int:
    return _pair(20.0, 20.0, 9)[0]


def test_circle_selects_centres_within_the_distance() -> None:
    fine, _resolution = _pair(0.0, 0.0, 9)
    centre = cell_centre(fine)
    inside = cells_in_circle(centre[0], centre[1], 1.0, ((fine, 9),))
    outside = cells_in_circle(centre[0], centre[1], 0.0, ((fine, 9),))
    assert inside == (fine,)
    # A zero cut-off still contains the centre itself: the disk is closed.
    assert outside == (fine,)
    other = _pair(5.0, 5.0, 9)
    assert cells_in_circle(centre[0], centre[1], 1.0, (other,)) == ()
    far = cells_in_circle(centre[0], centre[1], 2_000_000.0, (other,))
    assert far == (other[0],)


def test_selection_is_sorted_whole_and_repeatable() -> None:
    first = _pair(0.0, 0.0, 9)
    second = _pair(0.02, 0.02, 9)
    frame = (second, first, first)
    centre = cell_centre(first[0])
    ring = _ring_around(centre[0], centre[1], 1.0)
    once = cells_in_polygon((ring,), frame)
    twice = cells_in_polygon((ring,), frame)
    assert once == twice
    assert once == tuple(sorted(set(once)))
    assert first[0] in once


def test_empty_selection_is_empty_not_an_error() -> None:
    fine, _resolution = _pair(0.0, 0.0, 9)
    ring = _ring_around(10.0, 10.0, 0.00001)
    assert cells_in_polygon((ring,), ((fine, 9),)) == ()
    assert cells_in_circle(10.0, 10.0, 1.0, ((fine, 9),)) == ()


def test_overlapping_hexagon_without_its_centre_is_not_selected() -> None:
    fine, _resolution = _pair(0.0, 0.0, 9)
    centre = cell_centre(fine)
    vertex = h3.cell_to_boundary(h3.int_to_str(fine))[0]
    ring = _ring_around(vertex[0], vertex[1], 0.000001)
    assert point_in_polygon(exact_point(*vertex), (ring,))
    assert not point_in_polygon(exact_point(*centre), (ring,))
    assert cells_in_polygon((ring,), ((fine, 9),)) == ()


def test_circle_boundary_keeps_a_centre_and_refuses_the_next_shorter_radius() -> None:
    origin_cell, _resolution = _pair(0.0, 0.0, 9)
    neighbour = _pair(0.02, 0.0, 9)
    origin = cell_centre(origin_cell)
    other = cell_centre(neighbour[0])
    distance = great_circle_m(origin, other)
    assert cells_in_circle(*origin, distance, (neighbour,)) == (neighbour[0],)
    shorter = math.nextafter(distance, 0.0)
    longer = math.nextafter(distance, math.inf)
    assert cells_in_circle(*origin, shorter, (neighbour,)) == ()
    assert cells_in_circle(*origin, longer, (neighbour,)) == (neighbour[0],)


def test_r8_outline_is_its_seven_children() -> None:
    parent = h3.str_to_int(h3.latlng_to_cell(0.0, 0.0, 8))
    children = resolution_8_children(parent)
    expected = tuple(
        sorted(
            h3.str_to_int(item)
            for item in h3.cell_to_children(h3.int_to_str(parent), 9)
        )
    )
    assert children == expected
    assert len(children) == 7
