"""Closed checks for Public split columns and for what may read them.

The functions take typed descriptors. They do not read prose. Contracts that
this workspace states as field tables are read from document 03 section 6.
Protected release tables and generator outputs are not field tables here:
callers pass those descriptors themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PUBLIC_SPLIT_TABLES = frozenset(
    {
        "pub_wage_table",
        "pub_labour_sex_municipality",
        "pub_population_age_sex",
        "pub_active_sex_age",
        "pub_active_nationality_occupation",
        "pub_compensation_nationality",
        "pub_students",
        "pub_visitor_markets",
        "pub_pop_agesex_grid",
    }
)
_RECORD_KINDS = frozenset(
    {
        "worker_source",
        "residence_source",
        "company_source",
        "protected_derived",
        "generator_output",
        "mobility_feed",
    }
)
_FORBIDDEN_PARTS = frozenset(
    {
        "sex",
        "gender",
        "nationality",
        "citizenship",
        "ethnicity",
        "religion",
        "language",
        "age",
    }
)
_PUBLIC_EXTRA = frozenset(
    {
        "sex",
        "gender",
        "nationality",
        "citizenship",
        "ethnicity",
        "religion",
        "language",
    }
)
_SEX_GENDER = frozenset(
    {
        "female",
        "male",
        "females",
        "males",
        "woman",
        "man",
        "women",
        "men",
        "f",
        "m",
        "sex",
        "gender",
    }
)
_NATIONALITY = frozenset(
    {
        "qatari",
        "non_qatari",
        "non-qatari",
        "nationality",
        "citizen",
        "citizenship",
        "international_visitors",
    }
)
_EXCEPTIONS = frozenset(
    {
        ("employment_spell", "nationality_group"),
        ("establishment", "establishment_nationality"),
    }
)
_MOVEMENT_COLUMNS = frozenset({"age_band", "gender", "nationality_group"})
_PRESENCE_SPLIT_FIELDS = (
    "observation_start",
    "observation_end",
    "cell",
    "day_type",
    "summer",
    "hour",
    "split_kind",
    "split_value",
    "count",
    "panel_devices",
)
_OD_SPLIT_FIELDS = (
    "observation_start",
    "observation_end",
    "origin_cell",
    "destination_cell",
    "day_type",
    "summer",
    "hour",
    "split_kind",
    "split_value",
    "count",
    "panel_devices",
)
_MOVEMENT_FIELDS = {
    "presence_split_hourly": frozenset(_PRESENCE_SPLIT_FIELDS),
    "od_split_hourly": frozenset(_OD_SPLIT_FIELDS),
}
_NAME = re.compile(r"^[a-z0-9_]+$")
_ANCHORS = frozenset(
    {
        "mob.split_anchor.population_age_sex",
        "mob.split_anchor.visitor_arrivals",
    }
)
_KIND_BY_TABLE = {
    "legal_entity": "company_source",
    "establishment": "company_source",
    "establishment_activity": "company_source",
    "employment_spell": "worker_source",
    "salary_file": "worker_source",
    "salary_record": "worker_source",
    "residence": "residence_source",
    "presence_hourly": "mobility_feed",
    "od_hourly": "mobility_feed",
}
_JOINS = {
    "worker": "join_worker",
    "residence": "join_residence",
    "company": "join_company",
}
_SEGMENTS = {
    "worker": "segment_worker",
    "residence": "segment_residence",
    "company": "segment_company",
}


@dataclass(frozen=True)
class ColumnSpec:
    """One column and the closed values it admits, when it has a list."""

    name: str
    closed_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class TableSpec:
    """A table descriptor. kind selects which rule applies."""

    name: str
    kind: str
    columns: tuple[ColumnSpec, ...]
    breakdown_dimensions: tuple[str, ...] = ()
    source_splits: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class UseRequest:
    """A typed request to use a Public split figure."""

    table: str
    source_splits: tuple[tuple[str, tuple[str, ...]], ...]
    consumer: str
    geography: str
    categories: str
    lineage: str
    join_to: str = "none"
    segments: str = "none"
    person_key: bool = False
    device_key: bool = False
    trip_key: bool = False
    combines_protected: bool = False
    apportions: bool = False
    reserved_use: str = ""
    anchor: str = ""
    summed_over_source_categories: bool = False


@dataclass(frozen=True)
class Verdict:
    """Whether a descriptor is admitted, and the closed reason."""

    admitted: bool
    reason: str


def validate_table_dimensions(table: TableSpec) -> Verdict:
    """Admit a sex or nationality column only on the terms DAT-141 states."""
    refused = _unreadable_names(table)
    if refused is not None:
        return refused
    if table.kind in _RECORD_KINDS:
        return _record(table)
    if table.kind == "movement_split":
        return _movement(table)
    if table.kind == "public_split":
        return _public(table)
    return Verdict(False, "kind_unlisted")


def validate_split_use(request: UseRequest) -> Verdict:
    """Admit Public display, cited movement anchors, and the reserved grid sum."""
    if request.reserved_use != "":
        return _reserved(request)
    if request.consumer == "worker_record":
        return Verdict(False, "worker_record")
    if request.consumer == "joining_key":
        return Verdict(False, "joining_key")
    if request.consumer == "movement_anchor":
        return _anchor(request)
    flagged = _flags(request)
    if flagged is not None:
        return flagged
    if request.consumer != "public_display":
        return Verdict(False, "consumer_unlisted")
    return Verdict(True, "admitted_public")


def workspace_descriptors() -> tuple[TableSpec, ...]:
    """Read section 6 field tables, plus the two movement split tables named in prose."""
    text = _contracts_text()
    start = text.index("## 6. Source contracts")
    end = text.index("## 7. The release contract")
    found: list[TableSpec] = []
    for name, fields in _field_tables(text[start:end]):
        kind = _KIND_BY_TABLE.get(name)
        if kind is None:
            continue
        found.append(
            TableSpec(name, kind, tuple(ColumnSpec(field) for field in fields))
        )
    found.append(_movement_table("presence_split_hourly", _PRESENCE_SPLIT_FIELDS))
    found.append(_movement_table("od_split_hourly", _OD_SPLIT_FIELDS))
    return tuple(found)


def _record(table: TableSpec) -> Verdict:
    for column in table.columns:
        if (table.name, _folded(column.name)) in _EXCEPTIONS:
            for value in column.closed_values:
                if _names_sex_or_gender(value):
                    return Verdict(False, "forbidden_closed_value")
                if value.casefold() == "international_visitors":
                    return Verdict(False, "international_visitors_on_worker")
            continue
        if _parts(column.name) & _FORBIDDEN_PARTS:
            return Verdict(False, "forbidden_dimension")
        for value in column.closed_values:
            if _forbidden_value(value):
                return Verdict(False, "forbidden_closed_value")
    return Verdict(True, "admitted")


def _movement(table: TableSpec) -> Verdict:
    expected = _MOVEMENT_FIELDS.get(table.name)
    if expected is not None:
        found = tuple(_folded(column.name) for column in table.columns)
        if frozenset(found) != expected or len(found) != len(expected):
            return Verdict(False, "movement_column_unlisted")
    for column in table.columns:
        if (
            _parts(column.name) & _FORBIDDEN_PARTS
            and _folded(column.name) not in _MOVEMENT_COLUMNS
        ):
            return Verdict(False, "forbidden_dimension")
    return Verdict(True, "admitted")


def _public(table: TableSpec) -> Verdict:
    for column in table.columns:
        folded = _folded(column.name)
        if folded in {"sex", "nationality_group"}:
            refused = _declared(table, folded)
            if refused is not None:
                return refused
            continue
        if _parts(column.name) & _PUBLIC_EXTRA:
            return Verdict(False, "forbidden_dimension")
    for dimension in table.breakdown_dimensions:
        folded = _folded(dimension)
        if folded in {"sex", "nationality_group"}:
            refused = _declared(table, folded)
            if refused is not None:
                return refused
            continue
        if _parts(dimension) & _PUBLIC_EXTRA:
            return Verdict(False, "forbidden_dimension")
    return Verdict(True, "admitted")


def _declared(table: TableSpec, name: str) -> Verdict | None:
    if table.name not in PUBLIC_SPLIT_TABLES:
        return Verdict(False, "split_table_unlisted")
    token = "sex" if name == "sex" else "nationality"
    if not table.source_splits or any(
        token not in splits for _, splits in table.source_splits
    ):
        return Verdict(False, "split_undeclared")
    return None


def _reserved(request: UseRequest) -> Verdict:
    if request.reserved_use != "grid_whole_cells":
        return Verdict(False, "reserved_unknown")
    if request.consumer == "worker_record":
        return Verdict(False, "worker_record")
    if request.consumer == "joining_key":
        return Verdict(False, "joining_key")
    if request.consumer != "public_display":
        return Verdict(False, "consumer_unlisted")
    if request.geography != "area_shape":
        return Verdict(False, "invented_geography")
    category = _category(request.categories)
    if category is not None:
        return category
    if request.apportions:
        return Verdict(False, "tabulated_apportionment")
    if request.table != "pub_pop_agesex_grid":
        return Verdict(False, "reserved_wrong_table")
    if request.combines_protected:
        return Verdict(False, "protected_composite")
    if request.join_to != "none" or request.segments != "none":
        return Verdict(False, "join_worker")
    if request.person_key or request.device_key or request.trip_key:
        return Verdict(False, "person_key")
    if request.lineage != "public":
        return Verdict(False, "mixed_lineage")
    return Verdict(True, "reserved_grid_cells")


def _anchor(request: UseRequest) -> Verdict:
    if request.anchor not in _ANCHORS:
        return Verdict(False, "anchor_uncited")
    if not request.summed_over_source_categories:
        return Verdict(False, "anchor_not_summed")
    flagged = _flags(request)
    if flagged is not None:
        return flagged
    return Verdict(True, "admitted_movement_anchor")


def _flags(request: UseRequest) -> Verdict | None:
    if request.join_to in _JOINS:
        return Verdict(False, _JOINS[request.join_to])
    if request.join_to != "none":
        return Verdict(False, "join_worker")
    if request.segments in _SEGMENTS:
        return Verdict(False, _SEGMENTS[request.segments])
    if request.segments != "none":
        return Verdict(False, "segment_worker")
    if request.person_key:
        return Verdict(False, "person_key")
    if request.device_key:
        return Verdict(False, "device_key")
    if request.trip_key:
        return Verdict(False, "trip_key")
    if request.combines_protected:
        return Verdict(False, "protected_composite")
    if request.apportions:
        return Verdict(False, "tabulated_apportionment")
    if request.geography != "source":
        return Verdict(False, "invented_geography")
    if request.categories == "merged":
        return Verdict(False, "merged_category")
    if request.categories == "renamed":
        return Verdict(False, "renamed_category")
    if request.categories == "summed_unpublished":
        return Verdict(False, "unpublished_total")
    if request.categories != "source":
        return Verdict(False, "invented_category")
    if request.lineage != "public":
        return Verdict(False, "mixed_lineage")
    return None


def _movement_table(name: str, fields: tuple[str, ...]) -> TableSpec:
    """Columns named in section 6.5 for one movement split feed table."""
    return TableSpec(
        name, "movement_split", tuple(ColumnSpec(field) for field in fields)
    )


def _field_tables(section: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    parts = re.split(r"(?m)^Table `([a-z0-9_]+)`", section)
    tables: list[tuple[str, tuple[str, ...]]] = []
    index = 1
    while index + 1 < len(parts):
        name = parts[index]
        body = parts[index + 1]
        fields: list[str] = []
        if isinstance(body, str):
            for line in body.splitlines():
                if not line.startswith("| `"):
                    continue
                cell = line.split("|")[1]
                fields.extend(re.findall(r"`([A-Za-z0-9_]+)`", cell))
        if isinstance(name, str):
            tables.append((name, tuple(fields)))
        index += 2
    return tuple(tables)


def _repository_root(start: Path) -> Path:
    """Return the nearest parent that holds AGENTS.md and the contracts file."""
    for folder in start.resolve().parents:
        if (folder / "AGENTS.md").is_file() and (
            folder / "docs" / "03_DATA_CONTRACTS.md"
        ).is_file():
            return folder
    raise FileNotFoundError(
        "docs/03_DATA_CONTRACTS.md: no parent folder of the module "
        "holds it beside AGENTS.md"
    )


def _contracts_text() -> str:
    root = _repository_root(Path(__file__).resolve())
    return (root / "docs" / "03_DATA_CONTRACTS.md").read_text(encoding="utf-8")


def _folded(name: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return separated.casefold()


def _unreadable_names(table: TableSpec) -> Verdict | None:
    """A table, column or dimension name is ASCII snake case after case folding."""
    names = (
        table.name,
        *(column.name for column in table.columns),
        *table.breakdown_dimensions,
    )
    for name in names:
        if _NAME.fullmatch(name.casefold()) is None:
            return Verdict(False, "name_unreadable")
    return None


def _names_sex_or_gender(value: str) -> bool:
    """True when a closed value names a sex or a gender. The spelling is not stripped."""
    folded = value.casefold()
    parts = {folded, *folded.split("_"), *folded.split("-")}
    return bool(parts & _SEX_GENDER)


def _parts(name: str) -> set[str]:
    return set(_folded(name).split("_"))


def _category(categories: str) -> Verdict | None:
    if categories == "merged":
        return Verdict(False, "merged_category")
    if categories == "renamed":
        return Verdict(False, "renamed_category")
    if categories == "summed_unpublished":
        return Verdict(False, "unpublished_total")
    if categories != "source":
        return Verdict(False, "invented_category")
    return None


def _forbidden_value(value: str) -> bool:
    folded = value.casefold()
    parts = {folded, *folded.split("_"), *folded.split("-")}
    return bool(parts & _SEX_GENDER or parts & _NATIONALITY)
