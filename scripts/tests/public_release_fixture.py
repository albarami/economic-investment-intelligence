"""A seeded public_only fixture built by the release writer."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

from eii_core.manifest import CATALOGUE, ColumnSpec, by_name
from eii_custodian.release.public_only import TableWrite, write_public_only

SEED = 15
MARKER = "INVENTED-"
SOURCE_ID = "src-invented"
SOURCE_SHA = "ab" * 32
SOURCE_TITLE = f"{MARKER}dataset"
SOURCE_PUBLISHER = f"{MARKER}publisher"
SOURCE_URL = "https://invented.invalid/page"
SOURCE_LICENCE = f"{MARKER}licence"
SOURCE_BASIS = f"{MARKER}basis"
SOURCE_RETRIEVED = "2026-01-02"
LINEAGE_TRANSFORM = "invented.module.hold@v1"
# Document 04 names access_score_grid on the worldpop_qat_2020 registry row, so
# DAT-70 holds the table. Graph tables are not part of this fixture.
HOLD_ACCESS_SCORE_GRID = True
_FRAME_AND_LINEAGE = frozenset(
    {"grid_cell", "district", "source_registry", "fact_lineage"}
)
_CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "03_DATA_CONTRACTS.md"
_NAME_EXACT = frozenset(
    {
        "attribution",
        "buying_entity",
        "company",
        "fsq_place_id",
        "place_id",
        "publisher",
        "title",
        "title_ar",
        "title_en",
    }
)


def included_names() -> tuple[str, ...]:
    """Catalogue order of the tables this fixture writes."""
    names: list[str] = []
    for table in CATALOGUE:
        if table.manifest_class == "public":
            if table.name == "access_score_grid" and not HOLD_ACCESS_SCORE_GRID:
                continue
            names.append(table.name)
        elif table.name in _FRAME_AND_LINEAGE:
            names.append(table.name)
    return tuple(names)


def missing_public(names: Sequence[str]) -> str | None:
    """The first public catalogue table absent from names."""
    held = set(names)
    for table in CATALOGUE:
        if table.manifest_class != "public":
            continue
        if table.name == "access_score_grid" and not HOLD_ACCESS_SCORE_GRID:
            continue
        if table.name not in held:
            return table.name
    return None


def forbidden_name(names: Sequence[str]) -> str | None:
    """A protected, simulated or privacy-written table in names."""
    for name in names:
        table = by_name(name)
        if table is None:
            continue
        if (
            table.manifest_class in {"protected", "simulated"}
            or table.writer == "privacy"
        ):
            return name
    return None


def unmarked_name(tables: Sequence[TableWrite]) -> str | None:
    """A name-like value that does not start with the invented marker."""
    for table in tables:
        for row in table.rows:
            for column in table.columns:
                if not _name_like(column.name):
                    continue
                value = row[column.name]
                if type(value) is str and not value.startswith(MARKER):
                    return value
    return None


def unknown_source(tables: Sequence[TableWrite]) -> str | None:
    """A source_id that is not a source_registry row."""
    registered: set[object] = set()
    for table in tables:
        if table.name == "source_registry":
            registered.update(row["source_id"] for row in table.rows)
    for table in tables:
        for row in table.rows:
            if "source_id" not in row:
                continue
            if row["source_id"] not in registered:
                value = row["source_id"]
                return value if type(value) is str else "unknown"
    return None


def fixture_tables() -> tuple[TableWrite, ...]:
    """Every fixture table, with invented rows."""
    parsed = _column_index()
    tables: list[TableWrite] = []
    for name in included_names():
        columns = list(parsed[name])
        catalogue = by_name(name)
        if (
            catalogue is not None
            and catalogue.manifest_class == "public"
            and all(column.name != "source_id" for column in columns)
        ):
            columns.append(ColumnSpec("source_id", "string", False))
        if name == "pub_property_quarter":
            columns = [
                ColumnSpec(
                    column.name,
                    column.logical_type,
                    True
                    if column.name in {"land_deal_count", "price_basis"}
                    else column.nullable,
                    column.geometry_type,
                    column.srid,
                )
                for column in columns
            ]
        rows = _rows(name, tuple(columns))
        tables.append(TableWrite(name, tuple(columns), rows))
    return tuple(tables)


def build_fixture(
    destination: Path,
    *,
    playbook: bool = False,
    cards: bool = False,
    resolver: bool = False,
    artefacts: tuple[dict[str, str], ...] = (),
) -> str:
    """Build the fixture release and return its release id."""
    return write_public_only(
        destination,
        _scalars(),
        _cards_sources() if cards or resolver else _manifest_sources(),
        _resolve_tables()
        if resolver
        else _cards_tables()
        if cards
        else _playbook_tables()
        if playbook
        else fixture_tables(),
        artefacts=artefacts,
    )


def _scalars() -> dict[str, object]:
    return {
        "build_id": "build-invented",
        "built_at": "2026-01-02T00:00:00Z",
        "code_version": "invented-code",
        "engine_versions": {
            "duckdb": "2.0.0",
            "postgis_target": "3.6",
            "python": "3.14",
        },
        "release_contract_version": "release.v1",
        "release_kind": "public_only",
        "rules_version_id": "invented-rules",
    }


def _manifest_sources() -> tuple[dict[str, str], ...]:
    return (_source_record(),)


def _source_record() -> dict[str, str]:
    """One invented source. No field is a value of a real source."""
    return {
        "licence": SOURCE_LICENCE,
        "licence_basis": SOURCE_BASIS,
        "publisher": SOURCE_PUBLISHER,
        "retrieved_on": SOURCE_RETRIEVED,
        "sha256": SOURCE_SHA,
        "source_id": SOURCE_ID,
        "title": SOURCE_TITLE,
        "url": SOURCE_URL,
    }


def _rows(
    name: str, columns: tuple[ColumnSpec, ...]
) -> tuple[Mapping[str, object], ...]:
    if name == "grid_cell":
        return (_grid_row(columns, 0), _grid_row(columns, 1))
    if name == "fact_lineage":
        return _lineage_rows(columns)
    return (_one_row(name, columns),)


def _lineage_rows(columns: tuple[ColumnSpec, ...]) -> tuple[Mapping[str, object], ...]:
    rows: list[dict[str, object]] = []
    for name in included_names():
        catalogue = by_name(name)
        if catalogue is None or catalogue.manifest_class != "public":
            continue
        row = _one_row("fact_lineage", columns)
        row["input_class"] = "public"
        row["lineage_id"] = f"lin_{name}"
        row["source_id"] = SOURCE_ID
        row["table_name"] = name
        row["transform"] = LINEAGE_TRANSFORM
        rows.append(row)
    return tuple(rows)


def _grid_row(columns: tuple[ColumnSpec, ...], index: int) -> dict[str, object]:
    row = _one_row("grid_cell", columns)
    row["cell"] = 9 if index == 0 else 8
    if index == 1:
        row["district_key"] = None
    return row


def _one_row(name: str, columns: tuple[ColumnSpec, ...]) -> dict[str, object]:
    row: dict[str, object] = {}
    for column in columns:
        row[column.name] = _value(name, column)
    if name == "source_registry":
        row["source_id"] = SOURCE_ID
        row["title"] = SOURCE_TITLE
        row["publisher"] = SOURCE_PUBLISHER
        row["attribution"] = f"{MARKER}attribution"
        row["url"] = SOURCE_URL
        row["licence"] = SOURCE_LICENCE
        row["licence_basis"] = SOURCE_BASIS
        row["sha256"] = SOURCE_SHA
        row["retrieved_on"] = date.fromisoformat(SOURCE_RETRIEVED)
    if name == "fact_lineage":
        row["source_id"] = SOURCE_ID
        row["lineage_id"] = "lin_invented"
        row["input_class"] = "public"
    return row


def _value(name: str, column: ColumnSpec) -> object:
    if column.name == "source_id":
        return SOURCE_ID
    if column.name == "busyness_index":
        return 40
    if _name_like(column.name):
        return f"{MARKER}{name}-{column.name}"
    logical = column.logical_type
    if logical in {"int", "cell"}:
        return SEED
    if logical.startswith("decimal("):
        return Decimal("1.2500")
    if logical == "bool":
        return True
    if logical == "date":
        return date(2026, 1, 2)
    if logical == "geometry":
        return _point()
    if column.name == "sha256":
        return "cd" * 32
    return f"v-{name}-{column.name}"


def _name_like(name: str) -> bool:
    if name == "table_name":
        return False
    if name in _NAME_EXACT:
        return True
    return name == "name" or name.startswith("name_") or name.endswith("_name")


def _point() -> bytes:
    import struct

    return struct.pack("<BI2d", 1, 1, 1.0, 2.0)


def _column_index() -> dict[str, tuple[ColumnSpec, ...]]:
    text = _CONTRACTS.read_text(encoding="utf-8")
    start = text.index("### 7.3 Columns")
    end = text.index("The following closed lists", start)
    found: dict[str, tuple[ColumnSpec, ...]] = {}
    for line in text[start:end].splitlines():
        if not line.startswith("| `"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        names = [item.strip() for item in parts[0].replace("`", "").split(",")]
        columns = tuple(_columns(parts[1]))
        for name in names:
            found[name.strip()] = columns
    return found


def _columns(cell: str) -> list[ColumnSpec]:
    if "Release columns:" in cell:
        cell = cell.split("Release columns:", 1)[1]
    specs: list[ColumnSpec] = []
    seen: set[str] = set()
    for segment in _split_semi(cell):
        if "as int" in segment and "as string" in segment and "fields" in segment:
            groups = _as_clauses(segment)
        else:
            groups = _segment_columns(segment)
        for column_name, logical, nullable in groups:
            if column_name in seen:
                continue
            seen.add(column_name)
            if logical == "geometry":
                specs.append(
                    ColumnSpec(column_name, logical, nullable, "Geometry", 4326)
                )
            else:
                specs.append(ColumnSpec(column_name, logical, nullable))
    return specs


def _segment_columns(segment: str) -> list[tuple[str, str, bool]]:
    text = segment
    if not text.startswith("`") and ":" in text:
        text = text.split(":", 1)[1]
    groups: list[tuple[str, str, bool]] = []
    while text.strip():
        names, text = _take_names(text)
        if not names:
            break
        logical, nullable, text = _take_type(text)
        if "a column of the other kind of row is null" in segment:
            nullable = True
        for column_name in names:
            groups.append((column_name, logical, nullable))
        text = text.lstrip()
        if text.startswith(","):
            text = text[1:]
        elif text.startswith("and "):
            text = text[4:]
    return groups


def _as_clauses(segment: str) -> list[tuple[str, str, bool]]:
    int_part, _, rest = segment.partition("as int")
    int_names = re.findall(r"`([a-z][a-z0-9_]*)`", int_part.split("fields", 1)[-1])
    str_names = re.findall(r"`([a-z][a-z0-9_]*)`", rest.split("as string", 1)[0])
    return [(name, "int", True) for name in int_names] + [
        (name, "string", True) for name in str_names
    ]


def _take_names(text: str) -> tuple[list[str], str]:
    names: list[str] = []
    while True:
        text = text.lstrip()
        match = re.match(r"`([a-z][a-z0-9_]*)`", text)
        if match is None:
            break
        names.append(match.group(1))
        text = text[match.end() :].lstrip()
        if text.startswith("("):
            after = _skip_paren(text).lstrip()
            if after.startswith(",") or after.startswith("and "):
                text = after
            else:
                break
        if text.startswith(","):
            text = text[1:]
            continue
        if text.startswith("and "):
            text = text[4:]
            continue
        break
    return names, text


def _take_type(text: str) -> tuple[str, bool, str]:
    text = text.lstrip()
    nullable = False
    match = re.match(r"decimal\([0-9]+,[0-9]+\)", text)
    if match:
        logical = match.group(0)
        text = text[match.end() :]
    else:
        match = re.match(r"(int|bool|date|cell|geometry|string|timestamp|Cnt)\b", text)
        if match:
            word = match.group(1)
            logical = "int" if word == "Cnt" else word
            text = text[match.end() :]
        else:
            logical = "string"
    text = text.lstrip()
    if text.startswith("("):
        inner, text = _paren_inner(text)
        if re.search(r"\bY\b", inner):
            nullable = True
    return logical, nullable, text


def _paren_inner(text: str) -> tuple[str, str]:
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[1:index], text[index + 1 :]
    return "", ""


def _skip_paren(text: str) -> str:
    _inner, rest = _paren_inner(text)
    return rest


def _split_semi(cell: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for char in cell:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == ";" and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _playbook_frames() -> tuple[TableWrite, ...]:
    """Invented frame and empty graph inputs for the Public no-data journey."""
    parsed = _column_index()
    import struct

    tables = []
    ring = ((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0), (0.0, 0.0))
    polygon = struct.pack("<BIII", 1, 3, 1, len(ring)) + b"".join(
        struct.pack("<2d", *point) for point in ring
    )
    for name in ("zone", "municipality", "gazetteer"):
        columns = parsed[name]
        row = _one_row(name, columns)
        if "geometry" in row:
            row["geometry"] = polygon
        if name == "gazetteer":
            row.update(place_key="INVENTED-pin", aliases=None, cell=None)
        tables.append(TableWrite(name, columns, (row,)))
    fields = {
        "graph_node": (
            "node_id",
            "node_type",
            "code",
            "label_en",
            "label_ar",
            "provenance",
            "source_id",
        ),
        "graph_edge": (
            "edge_id",
            "edge_type",
            "from_node_id",
            "to_node_id",
            "provenance",
            "basis",
            "period",
            "attr_unit",
            "attr_unit_2",
            "source_id",
        ),
    }
    for name, names in fields.items():
        columns = tuple(
            ColumnSpec(
                key,
                "string",
                key in {"period", "attr_unit", "attr_unit_2", "source_id"},
            )
            for key in names
        )
        if name == "graph_edge":
            columns += tuple(
                ColumnSpec(key, "decimal(18,4)", True)
                for key in ("attr_value", "attr_value_2")
            )
        tables.append(TableWrite(name, columns, ()))
    return tuple(tables)


def _playbook_tables() -> tuple[TableWrite, ...]:
    tables = []
    for table in fixture_tables():
        if table.name == "pub_sector_accounts":
            rows = []
            for indicator, value, unit in (
                ("employees:INVENTED-size", 200, "count"),
                ("productivity_of_employee", 200000, "QAR"),
                ("compensation", 6000, "QAR_thousand"),
                ("operating_surplus", 8000, "QAR_thousand"),
                ("goods_share", 40, "percent"),
                ("services_share", 30, "percent"),
            ):
                row = _one_row(table.name, table.columns)
                row.update(
                    activity_code="INVENTED-activity",
                    period="2025",
                    indicator=indicator,
                    value=Decimal(value),
                    unit=unit,
                )
                rows.append(row)
            table = TableWrite(table.name, table.columns, tuple(rows))
        tables.append(table)
    return tuple(tables) + _playbook_frames()


def _cards_sources() -> tuple[dict[str, str], ...]:
    return _manifest_sources() + tuple(
        {**_source_record(), "source_id": key, "title": MARKER + key}
        for key in ("ntl_blackmarble", "busy_besttime", "worldpop_qat_agesex")
    )


def _resolve_tables() -> tuple[TableWrite, ...]:
    """Opt-in bilingual gazetteer and spine; all inputs remain invented."""
    tables = []
    for table in _cards_tables():
        rows = table.rows
        if table.name == "gazetteer":
            base = dict(rows[0])
            rows = (
                {
                    **base,
                    "name_en": "INVENTED-Garden",
                    "name_ar": "حديقة مخترعة",
                    "aliases": "INVENTED-Garden alias",
                },
                {
                    **base,
                    "place_key": "district:INVENTED-null",
                    "kind": "district",
                    "name_en": "INVENTED-Court",
                    "name_ar": "ساحة مخترعة",
                    "aliases": None,
                    "lon": Decimal("2.5"),
                    "lat": Decimal("2.5"),
                    "cell": None,
                },
                {
                    **base,
                    "place_key": "INVENTED-outside",
                    "name_en": "INVENTED-Outside",
                    "name_ar": "خارج مخترع",
                    "aliases": None,
                    "lon": Decimal("4"),
                    "lat": Decimal("4"),
                    "cell": None,
                },
            )
        elif table.name == "graph_node":
            rows = tuple(
                {
                    "node_id": key,
                    "node_type": kind,
                    "code": code,
                    "label_en": en,
                    "label_ar": ar,
                    "provenance": "public",
                    "source_id": SOURCE_ID,
                }
                for key, kind, code, en, ar in (
                    (
                        "activity:INVENTED-craft",
                        "activity",
                        "INVENTED-code",
                        "INVENTED-Craft",
                        "حرفة مخترعة",
                    ),
                    (
                        "isic:INVENTED-craft",
                        "isic_class",
                        "INVENTED-class",
                        "INVENTED-Class",
                        "فئة مخترعة",
                    ),
                    (
                        "category:INVENTED-craft",
                        "place_category",
                        "INVENTED-category",
                        "INVENTED-Category",
                        "صنف مخترع",
                    ),
                )
            )
        elif table.name == "graph_edge":
            rows = tuple(
                {
                    "edge_id": key,
                    "edge_type": kind,
                    "from_node_id": origin,
                    "to_node_id": target,
                    "provenance": "public",
                    "basis": "INVENTED-basis",
                    "period": None,
                    "attr_unit": None,
                    "attr_unit_2": None,
                    "source_id": SOURCE_ID,
                    "attr_value": None,
                    "attr_value_2": None,
                }
                for key, kind, origin, target in (
                    (
                        "INVENTED-classified",
                        "classified_as",
                        "activity:INVENTED-craft",
                        "isic:INVENTED-craft",
                    ),
                    (
                        "INVENTED-listed",
                        "listed_as",
                        "isic:INVENTED-craft",
                        "category:INVENTED-craft",
                    ),
                )
            )
        elif table.name == "fact_lineage":
            rows = (
                *rows,
                *(
                    {
                        **dict(rows[0]),
                        "lineage_id": "lin_" + name,
                        "table_name": name,
                        "source_id": SOURCE_ID,
                        "input_class": "public",
                        "transform": LINEAGE_TRANSFORM,
                    }
                    for name in ("graph_node", "graph_edge", "zone", "municipality")
                ),
            )
        tables.append(TableWrite(table.name, table.columns, rows))
    return tuple(tables)


def _cards_tables() -> tuple[TableWrite, ...]:
    """S3-T22 invented card/layer inputs; opt-in, never a real source read."""
    from shapely.geometry import Polygon

    import h3

    cells = [h3.str_to_int(h3.latlng_to_cell(lat, lat, 9)) for lat in (1, 1.5, 2, 2.9)]
    centres = [h3.cell_to_latlng(h3.int_to_str(cell)) for cell in cells]
    square = Polygon([(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)]).wkb
    built = []
    for table in _playbook_tables():

        def row(base: TableWrite = table, /, **values: object) -> dict[str, object]:
            return {**_one_row(base.name, base.columns), **values}

        rows: Sequence[Mapping[str, object]] = table.rows
        if table.name == "source_registry":
            rows = []
            for source in _cards_sources():
                values: dict[str, object] = dict(source)
                values["retrieved_on"] = date.fromisoformat(source["retrieved_on"])
                values["kind"] = "public_dataset"
                rows.append(row(**values))
        elif table.name == "fact_lineage":
            source_for = {
                "pub_night_lights": "ntl_blackmarble",
                "pub_venue_busyness": "busy_besttime",
                "pub_pop_agesex_grid": "worldpop_qat_agesex",
            }
            rows = [
                {
                    **item,
                    "source_id": source_for.get(str(item["table_name"]), SOURCE_ID),
                    "lineage_id": "lin_pub_parcel_invented_suffix"
                    if item["table_name"] == "pub_parcel"
                    else item["lineage_id"],
                }
                for item in rows
            ]
            rows.append(
                row(
                    lineage_id="lin_gazetteer",
                    table_name="gazetteer",
                    source_id=SOURCE_ID,
                    input_class="public",
                    transform=LINEAGE_TRANSFORM,
                )
            )
        elif table.name == "gazetteer":
            rows = [
                row(
                    place_key="INVENTED-landmark-a",
                    kind="landmark",
                    lon=Decimal("1.0"),
                    lat=Decimal("1.0"),
                    cell=cells[0],
                )
            ]
        elif table.name == "pub_register_company":
            # S3-T12 box 12: one invented register company at a frame cell and
            # one whose registered location does not resolve (never drawn).
            rows = [
                row(
                    registration_number="INVENTED-register-a",
                    registered_cell=cells[1],
                    establishment_nationality="INVENTED-nationality",
                ),
                row(
                    registration_number="INVENTED-register-b",
                    registered_cell=None,
                    establishment_nationality=None,
                ),
            ]
        elif table.name == "grid_cell":
            rows = [
                row(
                    cell=cell,
                    resolution=9,
                    parent_r7=h3.str_to_int(h3.cell_to_parent(h3.int_to_str(cell), 7)),
                    geometry=Polygon(
                        [
                            (lon, lat)
                            for lat, lon in h3.cell_to_boundary(h3.int_to_str(cell))
                        ]
                    ).wkb,
                )
                for cell in cells
            ]
        elif table.name == "pub_night_lights":
            rows = [
                row(
                    cell=cell,
                    period="2026-03",
                    radiance=Decimal(value),
                    source_id="ntl_blackmarble",
                )
                for cell, value in zip(
                    cells, ("4.0000", "7.0000", "10.0000", "5.0000"), strict=True
                )
            ]
            rows.append(
                row(
                    cell=cells[0],
                    period="2026-02",
                    radiance=Decimal("3.0000"),
                    source_id="ntl_blackmarble",
                )
            )
        elif table.name == "pub_pop_agesex_grid":
            rows = [
                row(
                    grid_key=f"INVENTED-grid-{i}",
                    lat=Decimal(str(lat)).quantize(Decimal("0.000001")),
                    lon=Decimal(str(lon)).quantize(Decimal("0.000001")),
                    age_band=band,
                    sex=sex,
                    people=Decimal(10),
                    period="2025",
                    source_id="worldpop_qat_agesex",
                )
                for i, (lat, lon) in enumerate(centres)
                for band in ("a00_14", "a15_64")
                for sex in ("female", "male")
            ]
        elif table.name == "pub_venue_busyness":
            days = (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            )
            rows = [
                row(
                    place_id="INVENTED-venue-a",
                    day_of_week=day,
                    hour=hour,
                    busyness_index=40,
                    retrieved_on=date(2026, 1, 2),
                    provider_updated_on=date(2026, 1, 1),
                    source_id="busy_besttime",
                )
                for day in days
                for hour in range(24)
                if (day, hour) != ("friday", 3)
            ]
        elif table.name == "pub_place":
            rows = [
                row(
                    place_id="INVENTED-venue-" + key,
                    name="INVENTED-venue-" + key,
                    lon=Decimal("1.0"),
                    lat=Decimal("1.0"),
                    cell=cells[0],
                )
                for key in ("a", "b")
            ]
        elif table.name == "zone":
            rows = [
                row(
                    zone_code="INVENTED-zone-" + key,
                    name_en="INVENTED-zone-" + key,
                    name_ar="INVENTED-zone-" + key,
                    geometry=square,
                )
                for key in ("a", "b", "c", "d", "e", "floor", "zero", "missing")
            ]
        elif table.name == "pub_zone_utility":
            rows = [
                row(
                    zone_code="INVENTED-zone-" + key,
                    period=period,
                    utility="electricity",
                    value=Decimal(value),
                    unit="kWh",
                    partial_year=False,
                )
                for key, baseline, end in (
                    ("a", 1000000, 1100000),
                    ("b", 1000000, 1200000),
                    ("c", 1000000, 1300000),
                    ("d", 1000000, 1400000),
                    ("e", 1000000, 1500000),
                    ("floor", 400000, 600000),
                    ("zero", 0, 100000),
                )
                for period, value in (("2021", baseline), ("2025", end))
            ]
        elif table.name == "district":
            rows = [
                row(
                    district_key="INVENTED-district-" + key,
                    name_en="INVENTED-district-" + key,
                    name_ar="INVENTED-district-" + key,
                    geometry=square,
                )
                for key in "abcdefghij"
            ]
        elif table.name == "pub_land_price":
            rows = [
                row(
                    district_key="INVENTED-district-" + key,
                    use_category="invented_commercial",
                    period="2025",
                    guide_price=Decimal(value),
                    price_basis="per_ft2",
                )
                for key, value in zip(
                    "abcdefghij", (1, 2, 2, 3, 5, 8, 8, 8, 13, 21), strict=True
                )
            ]
            rows += [
                row(
                    district_key="INVENTED-district-" + key,
                    use_category="invented_residential",
                    period="2025",
                    guide_price=Decimal(value),
                    price_basis="per_ft2",
                )
                for key, value in (("a", 50), ("j", 30))
            ]
        elif table.name == "pub_rail_plan":
            rows = [
                row(feature_key="fea-abcdefabcdefabcd", feature_kind="planned_station")
            ]
        elif table.name == "pub_accident_zone":
            # S3-T12: invented source zones; an older year, a zero count and a
            # zone without a reviewed crosswalk (never zero, never placed).
            rows = [
                row(
                    source_zone=source_zone,
                    period=period,
                    zone_code=None if code is None else "INVENTED-zone-" + code,
                    accident_count=count,
                    coverage_key="counted" if code else "geography_missing",
                )
                for source_zone, period, code, count in (
                    ("51", "2023", "a", 9),
                    ("51", "2024", "a", 5),
                    ("52", "2024", "b", 0),
                    ("53", "2024", None, None),
                )
            ]
        elif table.name == "pub_health_centre":
            rows = [
                row(
                    feature_key="fea-bcdefabcdefabcde",
                    feature_kind="centre",
                    period=None,
                )
            ]
        elif table.name == "pub_zoning":
            rows = [
                row(
                    feature_key="fea-cdefabcdefabcdef",
                    geometry=square,
                    permitted_uses='{"use":"INVENTED-use"}',
                    height_rule="{}",
                    setback_rule="{}",
                )
            ]
        elif table.name == "pub_parcel":
            rows = [row(feature_key="fea-defabcdefabcdefa", geometry=square)]
        elif table.name == "pub_property_sale":
            rows = [
                row(
                    district_key="INVENTED-district-a",
                    period="2025-01",
                    property_type="INVENTED-property",
                    deal_count=1,
                    median_price_per_m2=Decimal("40.00"),
                )
            ]
        elif table.name == "pub_property_quarter":
            rows = [
                row(
                    district_key="INVENTED-district-a",
                    period="2025-Q1",
                    use_key="invented_commercial",
                    unit_type="all",
                    median_price_per_ft2=Decimal("40.00"),
                    land_deal_count=1,
                    land_median_price_per_ft2=Decimal("30.00"),
                    median_price=None,
                    price_basis=None,
                )
            ]
        elif table.name == "pub_property_resi":
            rows = [
                row(
                    district_key="INVENTED-district-a",
                    period="2025-01",
                    unit_type="INVENTED-unit",
                    price_basis="per_unit",
                )
            ]
        elif table.name in {"pub_poi_comm", "pub_address_point", "pub_place_fsq"}:
            rows = [
                row(
                    cell=cells[0],
                    lon=Decimal("1.0"),
                    lat=Decimal("1.0"),
                    **(
                        {"source_release": "2025-01-10"}
                        if table.name == "pub_place_fsq"
                        else {}
                    ),
                )
            ]
        elif table.name == "fdi_projects":
            rows = [
                row(
                    project_key="fdi_abcdefabcdefabcd",
                    announced="2025-01-02",
                    project_year=2025,
                    project_month=0,
                    capex_currency="USD",
                    capex_unit="Mn USD",
                    lat=Decimal("1.0"),
                    lng=Decimal("1.0"),
                    tags='["INVENTED-tag"]',
                )
            ]
        built.append(TableWrite(table.name, table.columns, tuple(rows)))
    return tuple(built)
