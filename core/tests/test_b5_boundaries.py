"""B5 closed boundary regressions, with invented values only."""

from decimal import Decimal as D

import pytest
from method_rows import measure

from eii_core.calc import sector_economics as e
from eii_core.calc.public_series import rounded


def test_percent_requires_explicit_places():
    with pytest.raises(TypeError, match="places"):
        e._percent("invented", D("1.25"), (measure(1),))


def test_rounding_halfway_literal():
    assert rounded(D("1.25"), 1) == "1.3"
    assert rounded(D("-1.25"), 1) == "-1.3"


def test_repeated_iterable_inputs_accept_generators():
    from method_rows import energy, trade
    from test_decimal_context_contract import representation
    from test_mutation_regressions import invented_norms
    from test_sector_economics import component

    from eii_core.calc import facts as f
    from eii_core.calc import public_methods as m

    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    prior_months = tuple(f"2024-{i:02}" for i in range(1, 13))
    rows = [trade("invented", "invented", months[0], 3, 1)]
    prior = [trade("invented", "invented", prior_months[0], 2, 1)]

    def supply(convert):
        return m.supplier_metrics(
            convert(rows),
            convert(["invented"]),
            convert(months),
            convert(prior_months + months),
            reviewed=True,
            prior_rows=convert(prior),
            prior_months=convert(prior_months),
        )

    assert representation(supply(iter)) == representation(supply(list))
    assert f.least_real(iter(["public", "synthetic"])) == "synthetic"
    assert f.weakest_evidence(iter(["observed", "inferred"])) == "inferred"
    f.require_aligned(iter([measure(1), measure(2)]))

    def emit(convert):
        return f.emit(
            D("1.25"),
            unit="ratio",
            places=1,
            metric_key="invented",
            release_id="invented",
            geography="municipality:invented_muni",
            geography_kind="public",
            period="2025-05",
            inputs=convert([measure(1), measure(2)]),
        )

    assert representation(emit(iter)) == representation(emit(list))
    components = [component("invented", "goods", "1", "2")]
    assert representation(
        e.sector_norms(**invented_norms(), components=iter(components))
    ) == representation(e.sector_norms(**invented_norms(), components=components))
    assert e.share_range(iter([D(2), D(1)])) == (D(1), D(2))
    annual = [energy("invented", 2021, 1000000), energy("invented", 2025, 2000000)]

    def momentum(convert):
        return m.zone_momentum(
            convert(annual),
            energy("national", 2021, 3000000),
            energy("national", 2025, 4000000),
        )

    assert representation(momentum(iter)) == representation(momentum(list))


class PlantedText(str):
    """A text subtype must never enter closed metadata."""


class PlantedDecimal(D):
    """A numeric subtype could override arithmetic."""


@pytest.mark.parametrize(
    "field",
    [
        "period",
        "geography",
        "geography_kind",
        "metric_key",
        "unit",
        "input_class",
        "evidence_status",
    ],
)
def test_measure_refuses_text_subclasses(field):
    from dataclasses import replace

    row = measure(1)
    with pytest.raises(ValueError):
        replace(row, **{field: PlantedText(getattr(row, field))})


@pytest.mark.parametrize("kind", ["source", "registry", "withheld", "fact"])
def test_metadata_constructors_refuse_text_subclasses(kind):
    from dataclasses import fields, replace

    from method_rows import chain
    from test_calculation_facts import fact

    from eii_core.calc.facts import RegistrySource, WithheldInput

    objects = {
        "source": chain(),
        "registry": RegistrySource(
            "invented",
            "invented",
            "invented",
            "invented",
            "https://example.org/invented",
        ),
        "withheld": WithheldInput(
            "invented",
            "invented",
            "zone:invented",
            "public",
            "2025",
            "count",
            "invented",
            (chain(),),
        ),
        "fact": fact(),
    }
    row = objects[kind]
    # These are the admission fields, not optional comparison-base metadata.
    names = [
        field.name
        for field in fields(row)
        if isinstance(getattr(row, field.name), str) and getattr(row, field.name)
    ]
    assert names
    for name in names:
        with pytest.raises(ValueError):
            replace(row, **{name: PlantedText(getattr(row, name))})


def test_number_and_band_admissions_refuse_subclasses():
    from dataclasses import replace

    from test_calculation_facts import fact

    from eii_core.calc import facts as f
    from eii_core.calc import public_series as s

    for call in (
        lambda: s.finite(PlantedDecimal(1)),
        lambda: replace(measure(1), value=PlantedDecimal(1)),
        lambda: replace(fact(), value=PlantedDecimal(1)),
        lambda: f.Suppressed(PlantedText("invented")),
        lambda: replace(fact(), unit="wage_band", value=PlantedText("B01")),
        lambda: f.least_real((PlantedText("public"),)),
        lambda: f.weakest_evidence((PlantedText("observed"),)),
        lambda: s.decomposition(
            {"invented": (PlantedDecimal(1), D(3))}, {"invented": (D(1), D(4))}
        ),
        lambda: s.decomposition(
            {"invented": (D(1), PlantedDecimal(3))}, {"invented": (D(1), D(4))}
        ),
        lambda: s.decomposition(
            {
                PlantedText("invented"): (
                    measure(1, period="2020"),
                    measure(3, "qar_per_month", "2020"),
                )
            },
            {
                "invented": (
                    measure(1, period="2021"),
                    measure(4, "qar_per_month", "2021"),
                )
            },
        ),
        lambda: f.order_changes(
            (
                replace(
                    f.compare_public_facts(fact(), fact(150, "2025-02")),
                    ratio_unrounded=PlantedDecimal(1),
                ),
            )
        ),
    ):
        with pytest.raises(ValueError):
            call()


def test_zero_base_refused_before_large_after_display():
    from eii_core.calc.public_series import decomposition

    before = {
        "invented": (measure(1, period="2020"), measure(0, "qar_per_month", "2020"))
    }
    after = {
        "invented": (
            measure(1, period="2021"),
            measure("1E60", "qar_per_month", "2021"),
        )
    }
    with pytest.raises(ValueError, match=r"^non-positive denominator$"):
        decomposition(before, after)


def test_empty_weighted_mean_refusal_message():
    from eii_core.calc.public_series import weighted_mean

    with pytest.raises(ValueError, match=r"^non-positive denominator$"):
        weighted_mean({})


@pytest.mark.parametrize("field", ["geography", "geography_kind"])
def test_exact_geography_type_refusal_message(field):
    from dataclasses import replace

    row = measure(1)
    with pytest.raises(ValueError, match=r"^geography mismatch$"):
        replace(row, **{field: PlantedText(getattr(row, field))})


def test_exact_fact_unit_type_refusal_message():
    from dataclasses import replace

    from test_calculation_facts import fact

    with pytest.raises(ValueError, match=r"^unsupported numeric unit$"):
        replace(fact(), unit=PlantedText("count"))
