"""C4 Public norms only, following decision 0026 item 12; no production estimate."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction

from .facts import (
    CalculationFact,
    Measure,
    MeasureMismatch,
    WithdrawnProduction,
    emit,
    require_aligned,
)
from .public_series import CALC_CONTEXT, Number, compare, count, finite, ratio

CLOSED_OUTPUTS = (
    "compensation_percent",
    "surplus_percent",
    "goods_percent",
    "services_percent",
)


@dataclass(frozen=True)
class Component:
    key: str
    group: str
    value: Measure
    group_total: Measure
    total_group: str


def _amount(measure: Measure, unit: str) -> Decimal:
    if measure.unit != unit:
        raise MeasureMismatch("unit")
    finite(measure.value)
    return measure.value


def sector_norms(
    *,
    employees: Measure,
    productivity: Measure,
    compensation_thousand: Measure,
    surplus_thousand: Measure,
    goods_percent: Measure,
    services_percent: Measure,
    components: Iterable[Component] = (),
    production: Decimal | None = None,
    output_per_establishment: Decimal | None = None,
) -> dict[str, CalculationFact | Decimal | Fraction]:
    """Percentages from published figures, rounded once at output.

    `production` and `output_per_establishment` are the withdrawn derivations.
    Each is refused by name. Component totals must be their own group and year.
    """
    components = tuple(components)
    if production is not None:
        raise WithdrawnProduction("production")
    if output_per_establishment is not None:
        raise WithdrawnProduction("output_per_establishment")
    require_aligned(
        (
            employees,
            productivity,
            compensation_thousand,
            surplus_thousand,
            goods_percent,
            services_percent,
        ),
    )
    employee_count = employees.value
    if (
        employees.unit != "count"
        or employee_count != employee_count.to_integral_value()
    ):
        raise MeasureMismatch("unit")
    count(int(employee_count))
    productivity_value = _amount(productivity, "qar")
    compensation_value = _amount(compensation_thousand, "qar_thousand")
    surplus_value = _amount(surplus_thousand, "qar_thousand")
    goods_value = _amount(goods_percent, "percent")
    services_value = _amount(services_percent, "percent")
    for value in (productivity_value, compensation_value, surplus_value):
        if value < 0:
            raise ValueError("negative survey value")
    for value in (goods_value, services_value):
        finite(value)
        if not 0 <= value <= 100:
            raise ValueError("invalid percentage")
    inputs = (
        employees,
        productivity,
        compensation_thousand,
        surplus_thousand,
        goods_percent,
        services_percent,
        *(
            row
            for component in components
            for row in (component.value, component.group_total)
        ),
    )
    with localcontext(CALC_CONTEXT):
        compensation = ratio(
            ratio(Fraction(compensation_value) * 1000, Decimal(int(employee_count))),
            productivity_value,
        )
        surplus = ratio(
            ratio(Fraction(surplus_value) * 1000, Decimal(int(employee_count))),
            productivity_value,
        )
        result: dict[str, CalculationFact | Decimal | Fraction] = {
            "compensation_percent": _percent(
                "compensation_percent", compensation * 100, inputs, places=1
            ),
            "surplus_percent": _percent(
                "surplus_percent", surplus * 100, inputs, places=1
            ),
            "goods_percent": _percent("goods_percent", goods_value, inputs, places=1),
            "services_percent": _percent(
                "services_percent", services_value, inputs, places=1
            ),
            "compensation_percent_unrounded": compensation * 100,
            "surplus_percent_unrounded": surplus * 100,
        }
        groups = {"goods": goods_value, "services": services_value}
        for component in components:
            if (
                component.group not in groups
                or component.total_group != component.group
            ):
                raise ValueError("unknown component group")
            if (
                not component.key
                or component.key in result
                or component.key in {"production", "output_per_establishment"}
                or "production" in component.key
                or component.key == "output_value"
            ):
                raise ValueError("invalid component key")
            require_aligned(
                (component.value, component.group_total, employees),
            )
            component_value = _amount(component.value, "qar_thousand")
            group_total = _amount(component.group_total, "qar_thousand")
            finite(component_value)
            finite(group_total)
            if not 0 <= component_value <= group_total:
                raise ValueError("component outside group total")
            result[component.key] = _percent(
                component.key,
                ratio(component_value, group_total) * Fraction(groups[component.group]),
                (*inputs, component.value, component.group_total),
                places=1,
            )
        return result


def _percent(
    name: str,
    value: Decimal | Fraction,
    inputs: Sequence[Measure],
    *,
    places: int,
) -> CalculationFact:
    anchor = inputs[0]
    return emit(
        value,
        unit="percent",
        places=places,
        metric_key=name,
        release_id="published",
        geography=anchor.geography,
        geography_kind=anchor.geography_kind,
        period=anchor.period,
        inputs=inputs,
    )


def share_range(values: Iterable[Number]) -> tuple[Number, Number]:
    """Min and max of displayed shares. The comparison is tested code."""
    values = tuple(values)
    if not values:
        raise ValueError("missing share")
    low = high = values[0]
    for value in values[1:]:
        if compare(value, low) < 0:
            low = value
        if compare(value, high) > 0:
            high = value
    return low, high


def output_keys(result: Mapping[str, object]) -> frozenset[str]:
    """Closed display names. Unrounded companions are not outputs."""
    return frozenset(key for key in result if not str(key).endswith("_unrounded"))
