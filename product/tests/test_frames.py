"""The frame helper maps only the mutation tester's two renames."""

from __future__ import annotations

import pytest
from product.tests.frames import raised_in


class _Frame:
    def __init__(self, name: str) -> None:
        self.name = name


class _Caught:
    def __init__(self, name: str) -> None:
        self.traceback = [_Frame(name)]


def _caught(name: str) -> _Caught:
    return _Caught(name)


@pytest.mark.parametrize(
    "frame_name",
    ["_order", "x__order__mutmut_orig", "x__order__mutmut_12"],
)
def test_exact_and_mutmut_frames_match_the_named_function(frame_name: str) -> None:
    """A plain frame and the two mutation-tester renames are the named function."""
    assert raised_in(_caught(frame_name), "_order")


@pytest.mark.parametrize(
    "frame_name",
    [
        "_order_extra",
        "x__orderx__mutmut_orig",
        "x__order__mutmut_",
        "x__order__mutmut_1a",
        "x__other__mutmut_orig",
        "order",
    ],
)
def test_other_spellings_do_not_match_the_named_function(frame_name: str) -> None:
    """A different function, a partial rename or a bare name is not a match."""
    assert not raised_in(_caught(frame_name), "_order")
