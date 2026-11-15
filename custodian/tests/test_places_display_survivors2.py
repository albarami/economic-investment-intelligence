"""The display mutants that survived the first campaign, second file. All invented."""

from __future__ import annotations

from decimal import Decimal

from eii_custodian.publicdata.places.display import (
    PubPlace,
    _absorb_outside,
    _with_merged_ids,
)

_LICENCE = "SYN-LICENCE"
_RELEASE = "2026-10-21.0"
_SOURCE = "syn-source"


def _row(place_id: str, confidence: Decimal) -> PubPlace:
    """One invented pub_place row at one invented point, with no stored merge list."""
    return PubPlace(
        place_id,
        "SYN Cafe",
        None,
        "syn_other",
        "other",
        Decimal("51.500000"),
        Decimal("25.300000"),
        7,
        _RELEASE,
        _SOURCE,
        _LICENCE,
        confidence,
        "",
    )


def test_a_later_row_under_one_place_id_absorbs_on_its_own_confidence() -> None:
    """The second branch of the outer walk reads the last row of that place id.

    Two invented rows carry one place id, so the walk's own ``by_id`` holds the
    later of them. The keeper ties with the earlier row on confidence, so the
    first branch is false and the second decides on the later row's 0.4000.
    """
    first = _row("SYN-P-X", Decimal("0.5000"))
    second = _row("SYN-P-X", Decimal("0.4000"))
    keeper = _row("SYN-P-Y", Decimal("0.5000"))
    absorbed: dict[str, str] = {}
    _absorb_outside(
        (first, second, keeper),
        (("SYN-P-X", "SYN-P-Y"),),
        frozenset(),
        absorbed,
    )
    assert absorbed == {"SYN-P-X": "SYN-P-Y"}


def test_a_row_with_no_merges_is_the_very_row_given() -> None:
    """A row with no absorbed twin and no stored list is passed through, not rebuilt."""
    row = _row("SYN-P-A", Decimal("0.9000"))
    found = _with_merged_ids((row,), {})
    assert found == (row,)
    assert found[0] is row
