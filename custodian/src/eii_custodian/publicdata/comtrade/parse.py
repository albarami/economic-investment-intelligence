"""Validate every response row and map it onto the typed trade contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from eii_custodian.publicdata.comtrade.policy import Descriptor, Policy

AGGREGATION_CHAPTER = 2
CLASSIFICATION = "HS-INVENTED"
CUSTOMS = "customs-invented"
TRANSPORT = "mode-invented"
VALUATION = "value-invented"
MEASURE_VALUE = "trade_value"
MEASURE_QUANTITY = "net_weight"


@dataclass(frozen=True)
class TradeRow:
    """One published measure. A null measure stays null and is never zero."""

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
    return ParsedBody(tuple(rows), counted, truncated, error_text)


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
    product = record.get(schema.product_field)
    if not isinstance(product, str) or product == "":
        raise ParseError("schema_retyped")
    if descriptor.chapter not in product and descriptor.subdivision:
        product = _product_from_subdivision(descriptor, product)
    partner2 = record.get(schema.partner2_field)
    if partner2 is None:
        partner2_code = ""
    elif isinstance(partner2, str):
        partner2_code = partner2
    else:
        raise ParseError("schema_retyped")
    flags = record.get(schema.flag_field)
    if flags is None:
        flag_text = ""
    elif isinstance(flags, str):
        flag_text = flags
    else:
        raise ParseError("schema_retyped")
    value_row = _measure(
        record.get(schema.value_field),
        policy,
        MEASURE_VALUE,
        descriptor,
        product,
        partner2_code,
        flag_text,
        source_version,
        receipt_sha256,
    )
    quantity_row = _measure(
        record.get(schema.quantity_field),
        policy,
        MEASURE_QUANTITY,
        descriptor,
        product,
        partner2_code,
        flag_text,
        source_version,
        receipt_sha256,
    )
    return tuple(row for row in (value_row, quantity_row) if row is not None)


def _measure(
    raw: object,
    policy: Policy,
    measure: str,
    descriptor: Descriptor,
    product: str,
    partner2_code: str,
    flags: str,
    source_version: str,
    receipt_sha256: str,
) -> TradeRow | None:
    if raw is None:
        value: Decimal | None = None
    elif isinstance(raw, str):
        value = _decimal(raw, policy)
    else:
        raise ParseError("value_type")
    unit = dict(policy.measure_units).get(measure)
    if unit is None:
        raise ParseError("unit_mapping")
    if raw is None and measure == MEASURE_QUANTITY:
        return _row(
            descriptor,
            product,
            partner2_code,
            measure,
            None,
            unit,
            flags,
            source_version,
            receipt_sha256,
        )
    if raw is None:
        return _row(
            descriptor,
            product,
            partner2_code,
            measure,
            None,
            unit,
            flags,
            source_version,
            receipt_sha256,
        )
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
) -> TradeRow:
    return TradeRow(
        series_role=descriptor.series_role,
        reporter_code=descriptor.reporter_code,
        partner_code=descriptor.partner_code,
        partner2_code=partner2_code,
        frequency=descriptor.frequency,
        period=descriptor.period,
        flow_code=descriptor.flow_code,
        classification=CLASSIFICATION,
        classification_revision=descriptor.classification_revision,
        product_code=product,
        aggregation_level=AGGREGATION_CHAPTER,
        customs_code=CUSTOMS,
        transport_mode_code=TRANSPORT,
        valuation_basis=VALUATION,
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
    exponent = value.as_tuple().exponent
    digits = value.as_tuple().digits
    if not isinstance(exponent, int):
        raise ParseError("value_overflow")
    if exponent < -policy.value_scale:
        raise ParseError("value_overflow")
    if len(digits) > policy.value_precision:
        raise ParseError("value_overflow")
    if value == 0 and text.strip() in {"", "null"}:
        raise ParseError("substituted_zero")
    return value


def _expect(record: dict[str, object], field: str, expected: str) -> None:
    found = record.get(field)
    if found != expected:
        raise ParseError("selection_membership")


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise ParseError("schema_retyped")


def _product_from_subdivision(descriptor: Descriptor, product: str) -> str:
    del descriptor
    return product
