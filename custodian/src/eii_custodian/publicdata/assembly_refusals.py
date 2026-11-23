"""Observation only: log a closed stage refusal, then propagate it unchanged."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from .assembly_log import _BUILD_LINES, build_lines
from .assembly_refusal_policy import (
    NAMED_REASONS,
    REASON_ATTRIBUTES,
    STAGE_WORDS,
    TEXT_REASONS,
    UNEXPECTED,
)


def closed_reason(stage: str, error: Exception) -> str:
    """Select a literal diagnostic; no exception-controlled text is returned."""
    kind = type(error)
    attribute = REASON_ATTRIBUTES.get(kind)
    value = getattr(error, attribute, None) if attribute is not None else None
    if not isinstance(value, str):
        value = error.args[0] if error.args else None
    if isinstance(value, str):
        if value in NAMED_REASONS.get(kind, ()):
            return next(word for word in NAMED_REASONS[kind] if word == value)
        for pattern, word in TEXT_REASONS.get(kind, ()):
            if pattern.fullmatch(value) is not None:
                return word
    suffix = UNEXPECTED.get(kind)
    return stage + "_unexpected" + ("_" + suffix if suffix is not None else "")


def note_refusal(lines: list[str] | None, stage: str, error: Exception) -> None:
    """Observe a caught refusal only when a build has bound a log and stage."""
    if lines is None or stage not in STAGE_WORDS:
        return
    seen: set[int] = set()
    words: set[str] = set()
    current: BaseException | None = error
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        reason = closed_reason(stage, current)
        if reason not in words:
            lines.append(f"REFUSED {stage} {reason}")
            words.add(reason)
        current = current.__cause__ or current.__context__


@contextmanager
def stage_refusals(lines: list[str] | None, stage: str) -> Iterator[None]:
    """Keep the producer's exception object, traceback and caller's exit policy."""
    with build_lines(
        lines if lines is not None else _BUILD_LINES.get(), observer=note_refusal
    ):
        try:
            yield
        except Exception as error:
            note_refusal(lines, stage, error)
            raise
