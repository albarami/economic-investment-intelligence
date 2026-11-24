"""Hand-worked rings for the exact simple-polygon test. Nothing here is a place."""

from __future__ import annotations

from eii_core.shapes import ring_is_simple, ring_sha256

# Square used by test_canonical_form_and_hash. The digest is the current literal.
SQUARE = ((0, 0), (0, 1), (1, 1), (1, 0))
SQUARE_SHA256 = "47033591053ffb590c31b2947b2b73fd7285307e9057fe8f92e796f655517386"

# (lat, lon). Drawn below as (longitude, latitude).
# Bow-tie: (0,0)-(1,1) crosses (1,0)-(0,1) at (0.5, 0.5).
BOW_TIE = ((0, 0), (1, 1), (0, 1), (1, 0))
# Vertex (lat 0, lon 2) lies on the non-adjacent edge (0,0)-(0,4).
TOUCH = ((0, 0), (0, 4), (3, 4), (0, 2), (3, 0))
# Adjacent edges (0,0)-(0,2) and (0,2)-(0,1) overlap on the same line.
FOLD_BACK = ((0, 0), (0, 2), (0, 1), (1, 1))
# (0, 0) occurs again at a non-consecutive index.
REPEATED = ((0, 0), (0, 3), (2, 3), (2, 0), (0, 0), (1, 1))
# Concave at (lat 1, lon 1): the notch turns inward and no edges meet.
CONCAVE = ((0, 0), (0, 3), (1, 3), (1, 1), (2, 1), (2, 0))
# Collinear vertex (0, 1) continues the edge; adjacent edges share only that vertex.
CONTINUATION = ((0, 0), (0, 1), (0, 2), (1, 2), (1, 0))


def test_bow_tie_is_not_simple() -> None:
    assert ring_is_simple(BOW_TIE) is False
    assert ring_is_simple((*BOW_TIE, BOW_TIE[0])) is False


def test_ring_touching_itself_at_one_vertex_is_not_simple() -> None:
    assert ring_is_simple(TOUCH) is False


def test_collinear_fold_back_is_not_simple() -> None:
    assert ring_is_simple(FOLD_BACK) is False


def test_repeated_vertex_is_not_simple() -> None:
    assert ring_is_simple(REPEATED) is False


def test_convex_square_is_simple() -> None:
    assert ring_is_simple(SQUARE) is True
    assert ring_is_simple((*SQUARE, SQUARE[0])) is True


def test_concave_ring_is_simple() -> None:
    assert ring_is_simple(CONCAVE) is True


def test_collinear_continuation_is_simple() -> None:
    assert ring_is_simple(CONTINUATION) is True


def test_ring_sha256_of_the_square_is_unchanged() -> None:
    assert ring_sha256(SQUARE) == SQUARE_SHA256
    assert ring_sha256((*SQUARE, SQUARE[0])) == SQUARE_SHA256
