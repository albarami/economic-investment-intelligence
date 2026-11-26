"""Build the places table from a verified manifest and invented stand-ins."""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.grid import ownership_index, point_cell
from eii_custodian.publicdata.places_fsq.constants import (
    ATTRIBUTION,
    LICENCE_NAME,
    METHOD,
)
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.names import NameCheck, check_labels
from eii_custodian.publicdata.places_fsq.parse import (
    ParsedRow,
    account_rows,
    parse_file,
)
from eii_custodian.publicdata.places_fsq.policy import (
    CategoryMapping,
    DuplicateLink,
    PlaceStandIn,
    duplicate_links,
    is_eligible,
    product_categories,
)
from eii_custodian.publicdata.places_fsq.releases import (
    validate_release,
    validate_release_path,
)
from eii_custodian.publicdata.places_fsq.select import FrameBox

Grid = list[dict[str, object]]


@dataclass(frozen=True)
class TableRow:
    """One contract row. The release is the folder name, not a column of the file."""

    fsq_place_id: str
    name: str
    name_ar: None
    category_ids: str
    category_labels: str
    lon: object
    lat: object
    cell: int
    source_release: str
    licence: str
    date_created: object
    date_refreshed: object
    date_closed: object


@dataclass(frozen=True)
class EligiblePlace:
    """A row that is shown and counted, with the release and the attribution."""

    row: TableRow
    product_categories: str | None
    attribution: str
    receipt_sha256: str
    source_release: str


@dataclass(frozen=True)
class Coverage:
    """Counts the build owes the coverage note."""

    name_ar_null: int
    name_ar_filled: int
    point_not_country: int
    country_not_point: int
    no_cell: int
    unmapped_places: int
    duplicate_not_shown: int
    closed_not_shown: int


@dataclass(frozen=True)
class BuiltPlaces:
    """Table rows, the rows that are shown, and the checks beside them."""

    rows: tuple[TableRow, ...]
    eligible: tuple[EligiblePlace, ...]
    duplicates: tuple[DuplicateLink, ...]
    places: tuple[PlaceStandIn, ...]
    coverage: Coverage
    names: NameCheck
    method: str
    release: str


def build_places(
    *,
    files: Mapping[str, Path],
    expected_sha256: Mapping[str, str],
    frame: FrameBox,
    grid: Grid,
    places: Sequence[PlaceStandIn],
    mapping: Sequence[CategoryMapping],
    labels: Sequence[str],
    min_edit_distance: int,
    release: str,
    attribution: str,
    receipt_sha256: str,
) -> BuiltPlaces:
    """Return the table. A missing hash, release or attribution refuses it."""
    try:
        validate_release(release)
        for name in files:
            validate_release_path(name, release)
    except PlacesFsqError:
        raise PlacesFsqError("source_release") from None
    if attribution != ATTRIBUTION or receipt_sha256 == "":
        raise PlacesFsqError("attribution")
    parsed = _parsed(files, expected_sha256)
    account = account_rows(parsed, frame)
    # R1: the ownership index is built once for the batch, not once per place,
    # at the first lookup inside _table_row's try, so an empty batch never
    # builds it and refusal order is unchanged.
    stored = functools.cache(partial(ownership_index, grid))
    located = tuple(
        (row, table_row)
        for row in account.kept
        if (table_row := _table_row(row, grid, release, stored)) is not None
    )
    kept = tuple(row for row, _ in located)
    links = duplicate_links(kept, places)
    table = tuple(table_row for _, table_row in located)
    eligible = tuple(
        _eligible(row, table_row, mapping, attribution, receipt_sha256)
        for row, table_row in located
        if is_eligible(row, frame, links)
    )
    unmapped = sum(
        1 for row in kept if product_categories(row.category_ids, mapping) is None
    )
    names = check_labels(labels, tuple(row.name for row in kept), min_edit_distance)
    if not names.ok:
        raise PlacesFsqError("name_collision")
    coverage = Coverage(
        name_ar_null=len(kept),
        name_ar_filled=0,
        point_not_country=account.point_not_country,
        country_not_point=account.country_not_point,
        no_cell=len(account.kept) - len(kept),
        unmapped_places=unmapped,
        duplicate_not_shown=len(links),
        closed_not_shown=sum(1 for row in kept if row.date_closed is not None),
    )
    return BuiltPlaces(
        rows=table,
        eligible=eligible,
        duplicates=links,
        places=tuple(places),
        coverage=coverage,
        names=names,
        method=METHOD,
        release=release,
    )


def _parsed(
    files: Mapping[str, Path], expected: Mapping[str, str]
) -> tuple[ParsedRow, ...]:
    if not files or set(files) != set(expected):
        raise PlacesFsqError("receipt_mismatch")
    found: list[ParsedRow] = []
    for name in sorted(files):
        path = files[name]
        if sha256_hex(path.read_bytes()) != expected[name]:
            raise PlacesFsqError("receipt_mismatch")
        found.extend(parse_file(path))
    return tuple(found)


def _table_row(
    row: ParsedRow,
    grid: Grid,
    release: str,
    stored: Callable[[], frozenset[int]] | None = None,
) -> TableRow | None:
    try:
        cell = point_cell(
            float(row.lon),
            float(row.lat),
            ownership_index(grid) if stored is None else stored(),
        )
    except FrameError as exc:
        raise PlacesFsqError("cell") from exc
    if cell is None:
        return None
    return TableRow(
        fsq_place_id=row.fsq_place_id,
        name=row.name,
        name_ar=None,
        category_ids=row.category_ids,
        category_labels=row.category_labels,
        lon=row.lon,
        lat=row.lat,
        cell=cell,
        source_release=release,
        licence=LICENCE_NAME,
        date_created=row.date_created,
        date_refreshed=row.date_refreshed,
        date_closed=row.date_closed,
    )


def _eligible(
    row: ParsedRow,
    table_row: TableRow,
    mapping: Sequence[CategoryMapping],
    attribution: str,
    receipt: str,
) -> EligiblePlace:
    return EligiblePlace(
        row=table_row,
        product_categories=product_categories(row.category_ids, mapping),
        attribution=attribution,
        receipt_sha256=receipt,
        source_release=table_row.source_release,
    )
