"""The places build-log binding, with an optional assembly-only observer.

This module has no producer imports: the ordinary fetch fingerprint must not
acquire post-fetch assembly dependencies through the legacy places logger.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

Observer = Callable[[list[str] | None, str, Exception], None]
_BUILD_LINES: ContextVar[list[str] | None] = ContextVar(
    "eii_places_build_lines", default=None
)
_OBSERVER: ContextVar[Observer | None] = ContextVar(
    "eii_assembly_observer", default=None
)


@contextmanager
def build_lines(
    lines: list[str] | None, *, observer: Observer | None = None
) -> Iterator[None]:
    """Bind the sink; nested legacy producers inherit an assembly observer."""
    token = _BUILD_LINES.set(lines)
    observer_token = _OBSERVER.set(observer) if observer is not None else None
    try:
        yield
    finally:
        _BUILD_LINES.reset(token)
        if observer_token is not None:
            _OBSERVER.reset(observer_token)


def observe(stage: str, error: Exception, *, lines: list[str] | None = None) -> bool:
    """Deliver a caught error only when assembly explicitly bound its observer."""
    observer = _OBSERVER.get()
    if observer is None:
        return False
    observer(lines if lines is not None else _BUILD_LINES.get(), stage, error)
    return True
