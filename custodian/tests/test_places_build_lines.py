"""Build log contexts restore their caller on normal and refused frame exits."""

from contextlib import nullcontext

import pytest

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.places.integrate import _BUILD_LINES, build_lines


@pytest.mark.parametrize("refuse", [False, True])
def test_nested_build_lines_restore_the_callers_context(refuse):
    previous = _BUILD_LINES.get()
    outer, inner = [], []
    with build_lines(outer):
        assert _BUILD_LINES.get() is outer
        outcome = (
            pytest.raises(FrameError, match=r"^SYN_frame_refused$")
            if refuse
            else nullcontext()
        )
        with outcome, build_lines(inner):
            assert _BUILD_LINES.get() is inner
            if refuse:
                raise FrameError("SYN_frame_refused")
        assert _BUILD_LINES.get() is outer
    assert _BUILD_LINES.get() is previous
