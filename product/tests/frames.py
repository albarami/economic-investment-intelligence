"""Map a mutation-tester frame back to the function that raised."""

from __future__ import annotations

import re
from typing import Protocol

# mutmut 3 renames the original to x_<name>__mutmut_orig and a mutant to
# x_<name>__mutmut_<digits>. A full match keeps every other spelling intact.
_RENAMED = re.compile(r"\Ax_(?P<function>.+)__mutmut_(?:orig|[0-9]+)\Z")


class _NamedFrame(Protocol):
    name: str


class _FrameList(Protocol):
    def __getitem__(self, index: int) -> _NamedFrame: ...


class _Caught(Protocol):
    traceback: _FrameList


def raised_in(caught: _Caught, name: str) -> bool:
    """Return whether the last frame is exactly ``name``.

    ``x_<name>__mutmut_orig`` and ``x_<name>__mutmut_<digits>`` map back to
    ``name``. Every other spelling is compared unchanged.

    Args:
        caught: An exception info object whose last traceback frame has ``name``.
        name: The function that must be that last frame.

    Returns:
        True when the mapped last frame is exactly ``name``.
    """
    frame_name = caught.traceback[-1].name
    renamed = _RENAMED.fullmatch(frame_name)
    if renamed is not None:
        frame_name = renamed.group("function")
    return frame_name == name
