"""Closed parsing primitives shared by every decision-0017 family pass.

Passes B, C and D import the names in this module and do not edit it.
A table holds only rows whose contract key is present. A missing measure is
never stored as zero. A period comes from a closed form, never from a file's
modified date.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

ADDITION_FAMILIES = frozenset(
    {
        "prop_resi_units",
        "visits_museum",
        "visits_phcc",
        "permits_muni",
        "est_size_act",
        "mfg_industry",
        "trade_wr",
        "pop_muni_age",
        "hotels_muni",
        "trade_logistics",
        "est_census_2015_muni",
        "lf_muni_sex",
        "pop_muni_age_sex",
        "active_sex_age_act",
        "active_nat_occ_act",
        "comp_nat_act",
        "students_muni",
        "visitors_markets",
    }
)
PERIOD_FORMS = frozenset(
    {
        "year_text",
        "year_number",
        "year_month",
        "date",
        "date_as_year",
        "year_header",
        "month_name_year",
        "school_year",
        "year_text_and_month_name",
        "published_label",
    }
)
FIELD_UNCONFIRMED = "to_be_confirmed"
METHOD_VERSION = "1"
# S2-T08 part B (mismatch 2): a year is four ASCII digits; \d alone admits any
# script's digits, which would also sort after every ASCII year.
_YEAR = re.compile(r"^\d{4}$", re.ASCII)
_YEAR_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_SCHOOL = re.compile(r"^(\d{4})-(\d{4})$")
_DIGITS = re.compile(r"^\d+$")
_DECIMAL = re.compile(r"^\d+(\.\d+)?$")
_MONTH_HEADER = re.compile(r"^([a-z]+)_(\d{4})$")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_MONTH_INDEX = {name: index for index, name in enumerate(MONTHS, start=1)}
_MONTH_INDEX.update({name.upper(): index for name, index in list(_MONTH_INDEX.items())})
_LOWER_MONTH = {name.lower(): index for index, name in enumerate(MONTHS, start=1)}
LINEAGE_FIELDS = (
    "source_key",
    "publisher",
    "licence_id",
    "licence_basis",
    "retrieved_utc",
    "sha256",
    "period",
    "method",
)


class AdditionError(Exception):
    """A named refusal. The name is the check; the message does not carry a cell."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(name)


class MeasureKind(Enum):
    """A measure cell is a number or an admitted missing form."""

    NUMBER = "number"
    MISSING = "missing"


@dataclass(frozen=True)
class Coverage:
    """How many source rows were left out, and the named reason."""

    reason: str
    count: int


@dataclass(frozen=True)
class PeriodRule:
    """Where a period sits and which closed form it uses."""

    sit: str
    form: str
    field: str
    month_field: str


@dataclass(frozen=True)
class ContractQuestion:
    """The contract's words, the inventory's words, and the smallest contract change."""

    contract: str
    inventory: str
    change: str


@dataclass(frozen=True)
class FitResult:
    """Rows the contract key can hold, and the rows it cannot."""

    kept: tuple[dict[str, object], ...]
    blocked: tuple[Coverage, ...]
    questions: tuple[ContractQuestion, ...]


@dataclass(frozen=True)
class FamilyParse:
    """One slug's rows, coverage, observed periods and contract questions."""

    table: str
    rows: tuple[dict[str, object], ...]
    coverage: tuple[Coverage, ...]
    period_first: str
    period_last: str
    questions: tuple[ContractQuestion, ...]


@dataclass(frozen=True)
class MeasureRead:
    """A parsed measure. A missing read has no number."""

    kind: MeasureKind
    number: Decimal | None


def parse_period_rule(period_field: str) -> PeriodRule:
    """Parse a registry period rule. A form outside the closed list fails by name."""
    parts: dict[str, str] = {}
    seen: set[str] = set()
    for piece in period_field.split(";"):
        if "=" not in piece:
            raise AdditionError("period_field_unreadable")
        key, value = piece.split("=", 1)
        if key in seen:
            raise AdditionError("period_field_unreadable")
        seen.add(key)
        parts[key] = value
    form = parts.get("form", "")
    if form not in PERIOD_FORMS:
        raise AdditionError("period_form")
    sit = parts.get("sit", "")
    if sit not in {"row", "columns"}:
        raise AdditionError("period_sit")
    field = parts.get("field", "")
    if sit == "row" and field == "":
        raise AdditionError("period_field_empty")
    return PeriodRule(sit, form, field, parts.get("month", ""))


def parse_period_value(value: object, form: str) -> str:
    """Return the canonical period for one cell. The form list is closed.

    ``published_label`` is closed and has no canonical period, so this route
    refuses it by name. A reader cannot take the label for a period here.
    """
    if form not in PERIOD_FORMS:
        raise AdditionError("period_form")
    if form == "published_label":
        raise AdditionError("period_form")
    if form == "year_text":
        if isinstance(value, str) and _YEAR.fullmatch(value):
            return value
        raise AdditionError("period_form")
    if form == "year_number":
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and _YEAR.fullmatch(str(value))
        ):
            return str(value)
        raise AdditionError("period_form")
    if form == "year_month":
        return _year_month(value)
    if form == "date":
        return _date(value)
    if form == "date_as_year":
        text = _date(value)
        if not text.endswith("-01-01"):
            raise AdditionError("period_form")
        return text[:4]
    if form == "school_year":
        if not isinstance(value, str):
            raise AdditionError("period_form")
        match = _SCHOOL.fullmatch(value)
        if match is None or int(match.group(2)) != int(match.group(1)) + 1:
            raise AdditionError("period_form")
        return value
    raise AdditionError("period_form")


def observe_period_bounds(rows: list[object], rule: PeriodRule) -> tuple[str, str]:
    """Return the first and last period present in the rows.

    The function has no modified-date argument. An unconfirmed field name is
    refused by name rather than guessed. ``published_label`` has no canonical
    period, so a caller that asks for bounds is refused by name.
    """
    if rule.form == "published_label":
        raise AdditionError("period_form")
    if rule.field == FIELD_UNCONFIRMED:
        raise AdditionError("period_field_unconfirmed")
    found = _collect_periods(rows, rule)
    if not found:
        raise AdditionError("period_absent")
    ordered = sorted(found)
    return ordered[0], ordered[-1]


def read_measure(
    value: object, *, missing_forms: frozenset[str], integral: bool
) -> MeasureRead:
    """Read a measure. An admitted missing form yields no number. Other text fails."""
    if value is None:
        return MeasureRead(MeasureKind.MISSING, None)
    if isinstance(value, str):
        if value.strip() == "" or value in missing_forms:
            return MeasureRead(MeasureKind.MISSING, None)
        pattern = _DIGITS if integral else _DECIMAL
        if pattern.fullmatch(value):
            number = Decimal(value)
            if integral and number != number.to_integral_value():
                raise AdditionError("measure_not_integral")
            return MeasureRead(MeasureKind.NUMBER, number)
        raise AdditionError("measure_unparsed")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdditionError("measure_unparsed")
    number = Decimal(str(value))
    if not number.is_finite():
        raise AdditionError("measure_unparsed")
    if integral and number != number.to_integral_value():
        raise AdditionError("measure_not_integral")
    return MeasureRead(MeasureKind.NUMBER, number)


def fit_to_contract(
    rows: tuple[dict[str, object], ...],
    *,
    key_fields: tuple[str, ...],
    question: ContractQuestion | None = None,
) -> FitResult:
    """Keep rows that hold every key field. The others are blocked, not bent."""
    kept: list[dict[str, object]] = []
    blocked = 0
    for row in rows:
        if any(row.get(field) in (None, "") for field in key_fields):
            blocked += 1
            continue
        kept.append(dict(row))
    coverage = (Coverage("contract_key_unheld", blocked),) if blocked else ()
    questions = (question,) if question is not None and blocked else ()
    return FitResult(tuple(kept), coverage, questions)


def refuse_duplicate_keys(
    rows: tuple[dict[str, object], ...], key_fields: tuple[str, ...]
) -> None:
    """Refuse two rows that share a contract key."""
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in seen:
            raise AdditionError("duplicate_key")
        seen.add(key)


def attach_lineage(
    row: Mapping[str, object],
    *,
    source_key: str,
    publisher: str,
    licence_id: str,
    licence_basis: str,
    retrieved_utc: str,
    sha256: str,
    period: str,
    method: str,
) -> dict[str, object]:
    """Copy a row and attach the source chain a figure must carry."""
    carried = dict(row)
    carried.update(
        {
            "source_key": source_key,
            "publisher": publisher,
            "licence_id": licence_id,
            "licence_basis": licence_basis,
            "retrieved_utc": retrieved_utc,
            "sha256": sha256,
            "period": period,
            "method": method,
        }
    )
    require_lineage(carried)
    return carried


def require_lineage(row: Mapping[str, object]) -> None:
    """Refuse a figure that lacks its source, period, retrieval, method, licence or hash."""
    for field in LINEAGE_FIELDS:
        value = row.get(field)
        if not isinstance(value, str) or value == "":
            raise AdditionError("lineage_incomplete")


def require_closed(value: str, allowed: frozenset[str], name: str) -> str:
    """Return value when it is in the closed list."""
    if value not in allowed:
        raise AdditionError(name)
    return value


def receipt_text(receipt: Mapping[str, object], field: str) -> str:
    """Return one non-empty receipt string, or refuse the figure."""
    value = receipt.get(field)
    if not isinstance(value, str) or value == "":
        raise AdditionError("lineage_incomplete")
    return value


def _collect_periods(rows: list[object], rule: PeriodRule) -> list[str]:
    found: list[str] = []
    if rule.sit == "columns":
        for row in rows:
            if not isinstance(row, dict):
                raise AdditionError("period_unreadable")
            for key in row:
                if not isinstance(key, str):
                    raise AdditionError("period_unreadable")
                parsed = _header_period(key, rule.form)
                if parsed is not None:
                    found.append(parsed)
        return found
    for row in rows:
        if not isinstance(row, dict):
            raise AdditionError("period_unreadable")
        if rule.form == "year_text_and_month_name":
            year = parse_period_value(row.get(rule.field), "year_text")
            month = row.get(rule.month_field)
            if not isinstance(month, str) or month not in _MONTH_INDEX:
                raise AdditionError("period_form")
            found.append(f"{year}-{_MONTH_INDEX[month]:02d}")
            continue
        found.append(parse_period_value(row.get(rule.field), rule.form))
    return found


def _header_period(key: str, form: str) -> str | None:
    if form == "year_header":
        if _YEAR.fullmatch(key):
            return key
        return None
    if form == "month_name_year":
        match = _MONTH_HEADER.fullmatch(key)
        if match is None:
            return None
        month = _LOWER_MONTH.get(match.group(1))
        if month is None:
            raise AdditionError("period_form")
        return f"{match.group(2)}-{month:02d}"
    raise AdditionError("period_form")


def _year_month(value: object) -> str:
    if not isinstance(value, str):
        raise AdditionError("period_form")
    match = _YEAR_MONTH.fullmatch(value)
    if match is None or not 1 <= int(match.group(2)) <= 12:
        raise AdditionError("period_form")
    return value


def _date(value: object) -> str:
    if not isinstance(value, str):
        raise AdditionError("period_form")
    match = _DATE.fullmatch(value)
    if (
        match is None
        or not 1 <= int(match.group(2)) <= 12
        or not 1 <= int(match.group(3)) <= 31
    ):
        raise AdditionError("period_form")
    return value
