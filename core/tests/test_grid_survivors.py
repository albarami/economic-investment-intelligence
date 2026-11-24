"""Invented coordinates. The refusal text of a resolution-8 child lookup."""

from __future__ import annotations

import pytest

import h3
from eii_core.grid import resolution_8_children


def full_message(error: BaseException, expected: str) -> None:
    """Compare the whole refusal with a hand-written literal."""
    assert str(error) == expected


def test_a_finer_cell_is_refused_with_the_full_text() -> None:
    finer = h3.str_to_int(h3.latlng_to_cell(0.0, 0.0, 9))
    with pytest.raises(ValueError) as caught:
        resolution_8_children(finer)
    full_message(caught.value, "resolution-8 cell required")
