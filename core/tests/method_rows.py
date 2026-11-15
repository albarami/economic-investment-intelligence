"""Typed rows for the method tests. Invented chains are not registry receipts."""

from decimal import Decimal

from eii_core.calc.facts import Measure, RegistrySource, SourceChain
from eii_core.calc.public_methods import AnnualEnergy, TradeRow


def chain(ref: str = "invented_lineage") -> SourceChain:
    return SourceChain(
        ref,
        "invented_table",
        "card",
        "1",
        "invented_publisher",
        "invented_dataset",
        "https://example.org/invented",
        "invented_fixture",
        "2026-11-14",
        "a" * 64,
    )


def registry_source(
    ref: str,
    publisher: str,
    dataset: str,
    licence: str,
    url: str,
) -> SourceChain:
    """Arithmetic fixture chain only; these are not the publisher's receipt details."""
    return SourceChain(
        ref,
        "fixture_table",
        "card",
        "1",
        publisher,
        dataset,
        url,
        licence,
        "2026-11-14",
        "a" * 64,
    )


def measure(
    value: object,
    unit: str = "count",
    period: str = "2025-05",
    geography: str = "invented_muni",
    kind: str = "municipality",
    input_class: str = "public",
    status: str = "observed",
    metric: str = "input",
    source: SourceChain | RegistrySource | None = None,
) -> Measure:
    if unit in ("wage_band", "size_band", "volume_band"):
        numeric = value
    else:
        numeric = Decimal(str(value).replace(",", ""))
    if kind in ("municipality", "zone", "district", "place"):
        geography = kind + ":" + geography
        kind = "public"
    return Measure(
        numeric,
        unit,
        period,
        geography,
        kind,
        input_class,
        (source or chain(),),
        status,
        metric,
    )


def energy(zone: str, year: int, value: object, complete: bool = True) -> AnnualEnergy:
    amount = Decimal(str(value).replace(",", ""))
    kind = "national" if zone == "national" else "zone"
    return AnnualEnergy(
        zone,
        year,
        amount,
        complete,
        measure(amount, "kwh", str(year), zone, kind, metric="electricity"),
    )


def trade(
    product: str,
    origin: str,
    month: str,
    value: object,
    weight: object,
    unit: str = "kg",
) -> TradeRow:
    amount = Decimal(str(value).replace(",", ""))
    assert isinstance(weight, (str, int, Decimal))
    mass = Decimal(weight)
    weight_unit = "kg" if unit == "kg" else "quantity"
    return TradeRow(
        product,
        origin,
        month,
        amount,
        mass,
        unit,
        measure(amount, "qar", month, "national", "national", metric="import_value"),
        measure(
            mass, weight_unit, month, "national", "national", metric="import_weight"
        ),
    )
