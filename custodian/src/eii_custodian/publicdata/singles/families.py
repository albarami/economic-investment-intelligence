"""Open-data family rows: declared portal columns only, one release table per family."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from eii_custodian.publicdata.fetch.registry import Entry


class FamilyError(Exception):
    """The family export is not the declared shape. Nothing is returned."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class FamilyCell:
    """One declared field on one published row."""

    source_key: str
    slug: str
    row_index: int
    period_label: str | None
    field_name: str
    field_value: str
    source_id: str
    publisher: str
    licence_id: str
    licence_basis: str
    retrieved_utc: str
    sha256: str


def family_table_name(source_id: str) -> str:
    """The release table of one collected family."""
    return f"pub_{source_id}"


def _encode(value: object) -> str:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise FamilyError("field_value")
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _kind_ok(value: object, kind: str) -> bool:
    if value is None:
        return True
    if kind == "string":
        return isinstance(value, str)
    if kind in {"integer", "date"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    return False


def decode_family_archive(body: bytes) -> object:
    """Decode one family JSON archive; refuse a repeated object member."""

    def hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        built: dict[str, object] = {}
        for key, value in pairs:
            if key in built:
                raise FamilyError("duplicate_member")
            built[key] = value
        return built

    try:
        return json.loads(body, parse_float=Decimal, object_pairs_hook=hook)
    except FamilyError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FamilyError("archive_unreadable") from exc


def _period_label(entry: Entry, row: Mapping[str, object]) -> str | None:
    if not entry.period_field or "form=" not in entry.period_field:
        return None
    from eii_custodian.publicdata.additions.common import parse_period_rule

    field = parse_period_rule(entry.period_field).field
    if not field:
        return None
    raw = row.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise FamilyError("period_label")
    stripped = raw.strip()
    return stripped if stripped else None


def parse_family_rows(
    entry: Entry,
    rows: Sequence[Mapping[str, object]],
    *,
    retrieved_utc: str,
    sha256: str,
) -> tuple[FamilyCell, ...]:
    """Unpivot declared columns only. An undeclared key is refused."""
    declared = {name for name, _kind in entry.columns}
    kinds = dict(entry.columns)
    if not declared:
        raise FamilyError("columns_empty")
    built: list[FamilyCell] = []
    for index, row in enumerate(rows):
        if set(row) != declared:
            raise FamilyError("unexpected_column")
        period = _period_label(entry, row)
        for name in sorted(declared):
            value = row[name]
            if not _kind_ok(value, kinds[name]):
                raise FamilyError("field_kind")
            built.append(
                FamilyCell(
                    source_key=entry.key,
                    slug=entry.slug,
                    row_index=index,
                    period_label=period,
                    field_name=name,
                    field_value=_encode(value),
                    source_id=entry.source_id,
                    publisher=entry.publisher,
                    licence_id=entry.licence_id,
                    licence_basis=entry.licence_basis,
                    retrieved_utc=retrieved_utc,
                    sha256=sha256,
                )
            )
    return tuple(built)


def row_key(cell: FamilyCell) -> tuple[str, int, str]:
    """The stable contract key of one cell."""
    return (cell.source_key, cell.row_index, cell.field_name)
