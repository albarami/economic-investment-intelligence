"""Hand-worked exact cases for the private geometry that the survivors sit in.

Coordinates are invented. A point is (latitude, longitude).
"""

from __future__ import annotations

from fractions import Fraction

from eii_core.shapes import (
    _adjacent_overlap,
    _boundary,
    _complement_inside,
    _edges_share_point,
    _interior_faces_complement,
    _on_segment,
    _orient,
    _ray_inside,
    _segment_inside,
    _segment_t,
    _vertex_t,
    point_in_ring,
    polygon_inside_land,
)


def _p(lat: int | Fraction, lon: int | Fraction) -> tuple[Fraction, Fraction]:
    return (Fraction(lat), Fraction(lon))


def test_orient_of_a_worked_triple_is_five() -> None:
    # dx=2, dy=1, px=1, py=3, cross = 2*3 - 1*1 = 5.
    assert _orient(_p(1, 1), _p(2, 3), _p(4, 2)) == Fraction(5)


def test_on_segment_accepts_the_span_and_refuses_the_outside() -> None:
    start, end = _p(0, 0), _p(0, 4)
    assert _on_segment(start, start, end) is True
    assert _on_segment(_p(0, 2), start, end) is True
    assert _on_segment(end, start, end) is True
    assert _on_segment(_p(1, 2), start, end) is False
    assert _on_segment(_p(0, 5), start, end) is False
    # Nonzero origin: a point past lon 3 is outside, and (3, 2) is on the vertical span.
    assert _on_segment(_p(1, 4), _p(1, 1), _p(1, 3)) is False
    assert _on_segment(_p(1, 3), _p(1, 1), _p(1, 3)) is True
    assert _on_segment(_p(3, 2), _p(1, 2), _p(4, 2)) is True


def test_segment_parameter_of_a_crossing_and_of_its_edges() -> None:
    # Horizontal lat 0, lon 0..2 meets vertical lon 1, lat 1..-1 at tee 1/2.
    assert _segment_t(_p(0, 0), _p(0, 2), _p(1, 1), _p(-1, 1)) == Fraction(1, 2)
    assert _segment_t(_p(0, 0), _p(0, 2), _p(1, 0), _p(1, 2)) is None
    # The lines meet on A's span and before B's start: you = -1.
    assert _segment_t(_p(0, 0), _p(0, 2), _p(1, 1), _p(2, 1)) is None
    # Meetings on an endpoint stay inside the closed span.
    assert _segment_t(_p(0, 0), _p(0, 2), _p(1, 0), _p(-1, 0)) == Fraction(0)
    assert _segment_t(_p(0, 0), _p(0, 2), _p(1, 2), _p(-1, 2)) == Fraction(1)
    assert _segment_t(_p(0, 0), _p(0, 2), _p(0, 1), _p(-1, 1)) == Fraction(1, 2)
    # B runs lat 3..1 at lon 1. The line meets lat 0 at you = 3/2.
    assert _segment_t(_p(0, 0), _p(0, 4), _p(3, 1), _p(1, 1)) is None
    # A is lat 1, lon 1..5. B is lon 3, lat 0..2. They meet at tee 1/2.
    assert _segment_t(_p(1, 1), _p(1, 5), _p(0, 3), _p(2, 3)) == Fraction(1, 2)
    # B ends on A, so you is 1 and tee is 1/2.
    assert _segment_t(_p(0, 0), _p(0, 2), _p(1, 1), _p(0, 1)) == Fraction(1, 2)


def test_vertex_parameter_uses_the_longer_component() -> None:
    assert _vertex_t(_p(0, 0), _p(0, 4), _p(0, 2)) == Fraction(1, 2)
    assert _vertex_t(_p(1, 1), _p(5, 1), _p(3, 1)) == Fraction(1, 2)
    assert _vertex_t(_p(0, 0), _p(0, 1), _p(0, 1)) == Fraction(1)
    assert _vertex_t(_p(0, 0), _p(1, 0), _p(1, 0)) == Fraction(1)
    assert _vertex_t(_p(0, 0), _p(2, 2), _p(1, 1)) == Fraction(1, 2)
    assert _vertex_t(_p(0, 0), _p(0, 4), _p(1, 2)) is None


def test_edges_share_a_crossing_whose_side_is_one() -> None:
    # orient((0,0), (-3,-2), (-2,-1)) = 1, and the segments still cross.
    assert _edges_share_point(_p(0, 0), _p(-3, -2), _p(-2, -1), _p(-3, -3)) is True


def test_edges_share_a_worked_crossing_a_touch_and_nothing() -> None:
    # Proper cross. side of (1,0) against (0,0)->(1,0) is +1, so a == 1 test flips.
    assert _edges_share_point(_p(0, 0), _p(1, 0), _p(1, 0), _p(-1, 1)) is True
    assert _edges_share_point(_p(0, 0), _p(0, 4), _p(0, 2), _p(1, 2)) is True
    # Only the right endpoint lies on the other segment.
    assert _edges_share_point(_p(0, 0), _p(1, 1), _p(2, 0), _p(0, 2)) is True
    # Only the far endpoint lies on the first segment.
    assert _edges_share_point(_p(0, 0), _p(0, 4), _p(1, 1), _p(0, 2)) is True
    assert _edges_share_point(_p(0, 0), _p(0, 1), _p(5, 5), _p(6, 6)) is False


def test_adjacent_overlap_is_more_than_the_shared_vertex() -> None:
    assert _adjacent_overlap(_p(0, 0), _p(0, 2), _p(0, 1)) is True
    assert _adjacent_overlap(_p(0, 0), _p(0, 0), _p(1, 0)) is True
    assert _adjacent_overlap(_p(0, 0), _p(0, 1), _p(1, 0)) is False


def test_ray_keeps_an_interior_point_and_an_exterior_point() -> None:
    square = (_p(0, 0), _p(0, 4), _p(4, 4), _p(4, 0), _p(0, 0))
    assert _ray_inside(_p(2, 2), square) is True
    assert _ray_inside(_p(2, 6), square) is False
    # One count through the downward edge. Hand trace in the test name's neighbours.
    triangle = (_p(0, 0), _p(4, 1), _p(0, 3), _p(0, 0))
    assert _ray_inside(_p(1, 1), triangle) is True
    assert _ray_inside(_p(0, 1), triangle) is True
    assert _ray_inside(_p(0, 1), square) is True
    assert _ray_inside(_p(2, 2), triangle) is True
    # num is 0 on the upward edge, so a comparison with 1 drops the count.
    assert _ray_inside(_p(1, 4), square) is True
    assert point_in_ring(_p(2, 2), square) is True
    assert point_in_ring(_p(2, 6), square) is False


def test_segment_inside_the_square_splits_on_the_boundary() -> None:
    land = (((_p(0, 0), _p(0, 2), _p(2, 2), _p(2, 0), _p(0, 0)),),)
    # Exit at tee 1/2. The outside sample is (1, 5/2); a one-third sample is not.
    assert _segment_inside(_p(1, 1), _p(1, 3), land) is False
    # Both ends are outside and the middle is inside. Dropping crossings flips it.
    wide = (((_p(0, 0), _p(0, 4), _p(4, 4), _p(4, 0), _p(0, 0)),),)
    assert _segment_inside(_p(-1, 1), _p(5, 1), wide) is False
    assert _segment_inside(_p(9, 9), _p(9, 9), land) is False
    # Outside only before the boundary, so dropping the t = 0 mark would accept it.
    assert _segment_inside(_p(-1, 1), _p(1, 1), land) is False
    # Parallel to a land edge: the outside half is caught by the vertex mark.
    assert _segment_inside(_p(0, -1), _p(0, 1), land) is False


def test_boundary_keeps_four_edges_when_the_first_step_is_empty() -> None:
    ring = (_p(0, 0), _p(0, 0), _p(0, 1), _p(1, 1), _p(1, 0), _p(0, 0))
    assert len(_boundary(((ring,),))) == 4


def test_boundary_keeps_the_edge_that_was_walked_twice() -> None:
    first = (_p(0, 0), _p(0, 2), _p(2, 2), _p(2, 0), _p(0, 0))
    beside = (_p(0, 2), _p(0, 4), _p(2, 4), _p(2, 2), _p(0, 2))
    assert (_p(0, 2), _p(2, 2)) in _boundary(((first,), (first,), (beside,)))


def test_a_colinear_ring_on_the_boundary_is_not_inside() -> None:
    outer = (
        _p(0, 0),
        _p(0, 6),
        _p(6, 6),
        _p(6, 0),
        _p(4, 0),
        _p(4, 2),
        _p(2, 2),
        _p(2, 0),
        _p(0, 0),
    )
    ring = (_p(0, 0), _p(0, 1), _p(0, 3), _p(0, 0))
    assert polygon_inside_land(ring, ((outer,),)) is False


def test_complement_midpoint_inside_differs_from_the_end() -> None:
    square = (_p(0, 0), _p(0, 4), _p(4, 4), _p(4, 0), _p(0, 0))
    # Midpoint latitude 3 is inside. The end latitude 5, and t=2, are outside.
    assert _complement_inside(_p(1, 2), _p(5, 2), square) is True
    # t=1/2 is inside; t=1/3 is latitude -1/2, outside.
    assert (
        _complement_inside(_p(Fraction(-5, 2), 2), _p(Fraction(7, 2), 2), square)
        is True
    )


def test_interior_on_the_far_side_of_a_later_edge() -> None:
    square = (_p(0, 0), _p(0, 2), _p(2, 2), _p(2, 0), _p(0, 0))
    # Opposite the second edge (0,2)->(2,2). The first edge does not hold the midpoint.
    assert _interior_faces_complement(_p(2, 2), _p(0, 2), square) is True
    # Same direction as the bottom edge, and the dot of the unit edge is 1.
    assert _interior_faces_complement(_p(0, 0), _p(0, 1), square) is False
    raised = (_p(1, 1), _p(1, 2), _p(3, 2), _p(3, 1), _p(1, 1))
    assert _interior_faces_complement(_p(1, 1), _p(1, 2), raised) is False
    # The sample at t = 1/2 lies on lon 4..5. t = 1/3 and t = 1 do not.
    narrow = (_p(3, 4), _p(3, 5), _p(5, 5), _p(5, 4), _p(3, 4))
    assert _interior_faces_complement(_p(3, 9), _p(3, 0), narrow) is True
    # The matching edge is the second one, so skipping the first edge must not stop.
    second = (_p(3, 4), _p(3, 6), _p(5, 6), _p(5, 4), _p(3, 4))
    assert _interior_faces_complement(_p(5, 6), _p(3, 6), second) is True
    assert _interior_faces_complement(_p(9, 9), _p(9, 8), square) is False
    # The corner is on the first edge, which is not parallel, and on the second, which is.
    assert _interior_faces_complement(_p(2, 2), _p(-2, 2), square) is True
    repeated = (_p(0, 2), _p(0, 2), _p(2, 2), _p(2, 0), _p(0, 0), _p(0, 2))
    assert _interior_faces_complement(_p(-2, 2), _p(2, 2), repeated) is False
    assert _interior_faces_complement(_p(2, 2), _p(-2, 2), repeated) is True
