"""Declared row-count, schema and period checks for one fetched body."""

from __future__ import annotations

from dataclasses import dataclass

from eii_custodian.publicdata.fetch.registry import Entry


@dataclass(frozen=True)
class AttemptFailure:
    """A fetch that must not be stored. expected and observed name the compared values."""

    code: int
    url: str
    check: str
    expected: str
    observed: str


def count_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Fail when the row count is missing or outside the declared range."""
    if entry.row_count_min is None and entry.row_count_max is None:
        return None
    span = _count_span(entry)
    if rows is None:
        return AttemptFailure(1, url, "row_count", span, "unreadable")
    count = len(rows)
    if entry.row_count_min is not None and count < entry.row_count_min:
        return AttemptFailure(1, url, "row_count", span, str(count))
    if entry.row_count_max is not None and count > entry.row_count_max:
        return AttemptFailure(1, url, "row_count", span, str(count))
    return None


def schema_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Fail when any row lacks a declared field or gives it the wrong type."""
    if not entry.columns:
        return None
    if not rows:
        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")
    for record in rows:
        if not isinstance(record, dict):
            return AttemptFailure(
                1, url, "schema_missing", entry.columns[0][0], "missing"
            )
        for name, kind in entry.columns:
            if name not in record:
                return AttemptFailure(1, url, "schema_missing", name, "missing")
            if not _type_ok(record[name], kind):
                return AttemptFailure(
                    1, url, "schema_retyped", f"{name}:{kind}", _seen_type(record[name])
                )
    return None


def period_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Fail when the latest period is earlier than the registry records.

    ``published_label`` has no canonical period. This check does not read that
    label and does not compare it with the catalogue last.
    """
    if entry.period_field == "" or entry.period_last == "":
        return None
    if "form=" in entry.period_field:
        return _ruled_period_failure(entry, rows, url)
    if not rows:
        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")
    observed: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            return AttemptFailure(
                1, url, "period_last", entry.period_last, "unreadable"
            )
        value = row.get(entry.period_field)
        if not isinstance(value, str):
            return AttemptFailure(
                1, url, "period_last", entry.period_last, "unreadable"
            )
        observed.append(value)
    latest = max(observed)
    if latest < entry.period_last:
        return AttemptFailure(1, url, "period_last", entry.period_last, latest)
    return None


def _ruled_period_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Compare a closed period rule with the rows. A modified date is not a period."""
    from eii_custodian.publicdata.additions.common import (
        FIELD_UNCONFIRMED,
        AdditionError,
        observe_period_bounds,
        parse_period_rule,
    )

    try:
        rule = parse_period_rule(entry.period_field)
        if rule.form == "published_label" or rule.field == FIELD_UNCONFIRMED:
            return None
        _first, last = observe_period_bounds(rows or [], rule)
    except AdditionError as error:
        return AttemptFailure(1, url, error.name, entry.period_last, error.name)
    if last < entry.period_last:
        return AttemptFailure(1, url, "period_last", entry.period_last, last)
    return None


def _count_span(entry: Entry) -> str:
    """Return the declared row-count range as low..high."""
    low = "" if entry.row_count_min is None else str(entry.row_count_min)
    high = "" if entry.row_count_max is None else str(entry.row_count_max)
    return f"{low}..{high}"


def _seen_type(value: object) -> str:
    """Return a type name for a mismatched field. The cell value is not included."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "other"


def _type_ok(value: object, kind: str) -> bool:
    if value is None:
        return True
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict)
    return False
