"""Validate every response row and map it onto the typed trade contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from eii_custodian.publicdata.comtrade.policy import SOURCE_ID, Descriptor, Policy

MEASURE_VALUE = "trade_value"
MEASURE_QUANTITY = "net_weight"


@dataclass(frozen=True)
class TradeRow:
    """One published measure. A null measure stays null and is never zero."""

    source_id: str
    series_role: str
    reporter_code: str
    partner_code: str
    partner2_code: str
    frequency: str
    period: str
    flow_code: str
    classification: str
    classification_revision: str
    product_code: str
    aggregation_level: int
    customs_code: str
    transport_mode_code: str
    valuation_basis: str
    measure: str
    value: Decimal | None
    unit: str
    source_flags: str
    source_version: str
    receipt_sha256: str

    def full_key(self) -> tuple[str, ...]:
        """Return the dimensional key, including the measure."""
        return (
            self.series_role,
            self.reporter_code,
            self.partner_code,
            self.partner2_code,
            self.frequency,
            self.period,
            self.flow_code,
            self.classification,
            self.classification_revision,
            self.product_code,
            str(self.aggregation_level),
            self.customs_code,
            self.transport_mode_code,
            self.valuation_basis,
            self.measure,
            self.unit,
        )


@dataclass(frozen=True)
class ParsedBody:
    """Rows from one response, plus the raw record count before projection."""

    rows: tuple[TradeRow, ...]
    raw_count: int
    truncated: bool
    error_text: str


def parse_body(
    body: bytes,
    policy: Policy,
    descriptor: Descriptor,
    *,
    source_version: str,
    receipt_sha256: str,
) -> ParsedBody:
    """Parse one body. A short count, a duplicate key or a bad decimal is refused."""
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ParseError("metadata_unreadable") from exc
    if not isinstance(loaded, dict):
        raise ParseError("metadata_unreadable")
    schema = policy.response_schema
    error_text = _optional_text(loaded.get(schema.error_field))
    if error_text:
        raise ParseError("provider_error")
    records = loaded.get(schema.record_array)
    if not isinstance(records, list):
        raise ParseError("metadata_unreadable")
    counted = loaded.get(schema.count_field)
    if isinstance(counted, bool) or not isinstance(counted, int) or counted < 0:
        raise ParseError("short_total")
    if counted != len(records):
        raise ParseError("short_total")
    truncated = loaded.get(schema.truncation_field)
    if not isinstance(truncated, bool):
        raise ParseError("truncation_flag")
    rows: list[TradeRow] = []
    seen: set[tuple[str, ...]] = set()
    for record in records:
        built = _rows_for(record, policy, descriptor, source_version, receipt_sha256)
        for row in built:
            if row.full_key() in seen:
                raise ParseError("duplicate_key")
            seen.add(row.full_key())
            rows.append(row)
    return ParsedBody(tuple(rows), counted, truncated, "")


class ParseError(Exception):
    """A named parse failure. Provider text is not part of the message."""

    def __init__(self, check: str) -> None:
        self.check = check
        super().__init__(check)


def _rows_for(
    record: object,
    policy: Policy,
    descriptor: Descriptor,
    source_version: str,
    receipt_sha256: str,
) -> tuple[TradeRow, ...]:
    if not isinstance(record, dict):
        raise ParseError("schema_retyped")
    schema = policy.response_schema
    _expect(record, schema.reporter_field, descriptor.reporter_code)
    _expect(record, schema.partner_field, descriptor.partner_code)
    _expect(record, schema.period_field, descriptor.period)
    _expect(record, schema.flow_field, descriptor.flow_code)
    product = _required_text(record, schema.product_field)
    _product_member(policy, descriptor, product)
    revision = _required_text(record, schema.revision_field)
    if revision != descriptor.classification_revision:
        raise ParseError("selection_membership")
    classification = _required_text(record, schema.classification_field)
    customs = _required_text(record, schema.customs_field)
    transport = _required_text(record, schema.transport_field)
    valuation = _required_text(record, schema.valuation_field)
    aggregation = _aggregation(record, schema.aggregation_field)
    partner2_code = _optional_code(record, schema.partner2_field)
    flag_text = _optional_code(record, schema.flag_field)
    value_row = _measure(
        record,
        schema.value_field,
        policy,
        MEASURE_VALUE,
        descriptor,
        product,
        partner2_code,
        flag_text,
        source_version,
        receipt_sha256,
        classification,
        revision,
        aggregation,
        customs,
        transport,
        valuation,
    )
    quantity_row = _measure(
        record,
        schema.quantity_field,
        policy,
        MEASURE_QUANTITY,
        descriptor,
        product,
        partner2_code,
        flag_text,
        source_version,
        receipt_sha256,
        classification,
        revision,
        aggregation,
        customs,
        transport,
        valuation,
    )
    return (value_row, quantity_row)


def _measure(
    record: dict[str, object],
    field: str,
    policy: Policy,
    measure: str,
    descriptor: Descriptor,
    product: str,
    partner2_code: str,
    flags: str,
    source_version: str,
    receipt_sha256: str,
    classification: str,
    revision: str,
    aggregation: int,
    customs: str,
    transport: str,
    valuation: str,
) -> TradeRow:
    if field not in record:
        raise ParseError("measure_missing")
    raw = record[field]
    if raw is None:
        value: Decimal | None = None
    elif isinstance(raw, str):
        value = _decimal(raw, policy)
    else:
        raise ParseError("value_type")
    unit = dict(policy.measure_units).get(measure)
    if unit is None:
        raise ParseError("unit_mapping")
    return _row(
        descriptor,
        product,
        partner2_code,
        measure,
        value,
        unit,
        flags,
        source_version,
        receipt_sha256,
        classification,
        revision,
        aggregation,
        customs,
        transport,
        valuation,
    )


def _row(
    descriptor: Descriptor,
    product: str,
    partner2_code: str,
    measure: str,
    value: Decimal | None,
    unit: str,
    flags: str,
    source_version: str,
    receipt_sha256: str,
    classification: str,
    revision: str,
    aggregation: int,
    customs: str,
    transport: str,
    valuation: str,
) -> TradeRow:
    return TradeRow(
        source_id=SOURCE_ID,
        series_role=descriptor.series_role,
        reporter_code=descriptor.reporter_code,
        partner_code=descriptor.partner_code,
        partner2_code=partner2_code,
        frequency=descriptor.frequency,
        period=descriptor.period,
        flow_code=descriptor.flow_code,
        classification=classification,
        classification_revision=revision,
        product_code=product,
        aggregation_level=aggregation,
        customs_code=customs,
        transport_mode_code=transport,
        valuation_basis=valuation,
        measure=measure,
        value=value,
        unit=unit,
        source_flags=flags,
        source_version=source_version,
        receipt_sha256=receipt_sha256,
    )


def _decimal(text: str, policy: Policy) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ParseError("value_type") from exc
    if not value.is_finite():
        raise ParseError("value_type")
    numeric = value.as_tuple()
    exponent = numeric.exponent
    if not isinstance(exponent, int):
        raise ParseError("value_overflow")
    fractional = -exponent if exponent < 0 else 0
    if value == 0:
        integer_digits = 0
    elif exponent >= 0:
        integer_digits = len(numeric.digits) + exponent
    else:
        integer_digits = max(0, len(numeric.digits) + exponent)
    capacity = policy.value_precision - policy.value_scale
    if fractional > policy.value_scale or integer_digits > capacity:
        raise ParseError("value_overflow")
    return value


def _expect(record: dict[str, object], field: str, expected: str) -> None:
    found = record.get(field)
    if found != expected:
        raise ParseError("selection_membership")


def _required_text(record: dict[str, object], field: str) -> str:
    if field not in record:
        raise ParseError("dimension_missing")
    value = record[field]
    if not isinstance(value, str) or value == "":
        raise ParseError("dimension_missing")
    return value


def _optional_code(record: dict[str, object], field: str) -> str:
    if field not in record:
        return ""
    value = record[field]
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise ParseError("schema_retyped")


def _aggregation(record: dict[str, object], field: str) -> int:
    if field not in record:
        raise ParseError("dimension_missing")
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParseError("schema_retyped")
    return value


def _product_member(policy: Policy, descriptor: Descriptor, product: str) -> None:
    requested = dict(descriptor.subdivision)
    if "product" in requested:
        allowed = dict(policy.subdivision_values).get("product", ())
        if requested["product"] not in allowed or product != requested["product"]:
            raise ParseError("product_membership")
        return
    if product != descriptor.chapter:
        raise ParseError("product_membership")


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise ParseError("schema_retyped")
