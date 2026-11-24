"""Application fact contract plants (DAT-90 through DAT-95, DAT-155)."""

from datetime import date
from decimal import Decimal
from hashlib import sha256

import pytest


def candidate(**changes):
    row = dict(
        fact_id="f_" + "a" * 32,
        value=Decimal("2"),
        unit="count",
        period="2025",
        geography={"kind": "national"},
        provenance="public",
        input_classes=["public"],
        evidence_status="observed",
        reliability="not_applicable",
        coverage_keys=[],
        caveat_keys=[],
        label_en="Count",
        label_ar="العدد",
        lineage_ref="lin_pub_licence_active",
        release_id=sha256(b"SYN-release").hexdigest(),
    )
    row.update(changes)
    return row


@pytest.mark.parametrize(
    "unit,value",
    [
        ("count", 2),
        ("ratio", Decimal("1.23")),
        ("percent", Decimal("20.1")),
        ("calendar_month", "2025-03"),
        ("size_band", "s01_09"),
    ],
)
def test_admitted_units(unit, value):
    from eii_core.facts import Fact

    assert Fact.model_validate(candidate(unit=unit, value=value)).value == value


@pytest.mark.parametrize(
    "changes",
    [
        {"value": None},
        {"value": Decimal("1.5")},
        {"value": "2"},
        {"value": True},
        {"unit": "size_band", "value": "unknown"},
        {
            "geography": {
                "kind": "public",
                "public_code": "municipality:SYN-a",
                "unit_ids": ["SYN-a"],
            }
        },
        {"geography": {"kind": "national", "public_code": "municipality:SYN-a"}},
        {"geography": {"kind": "area_shape", "area_id": "SYN-a"}},
        {"extra": "SYN-extra"},
        {"fact_id": "bad"},
        {"release_id": "published"},
        {"lineage_ref": "bad"},
        {"period": "x"},
        {"label_en": ""},
        {"label_ar": ""},
        {"coverage_keys": ["BAD"]},
        {"caveat_keys": ["BAD"]},
        {"input_classes": ["public", "simulated"]},
        {"input_classes": []},
        {"input_classes": ["public", "public"]},
        {"input_classes": ["public", "user_input"]},
        {"unit": "wage_band", "value": "B01"},
        {"unit": "ratio", "value": "2"},
        {"unit": "percent", "value": True},
        {"unit": "size_band", "value": 2},
        {"unit": "calendar_month", "value": 2025},
        {"evidence_status": "not_measured"},
        {"provenance": "suppressed", "value": 2},
        {"unit": "ratio", "value": Decimal("NaN")},
    ],
)
def test_model_refuses_plants(changes):
    from eii_core.facts import Fact

    with pytest.raises(ValueError):
        Fact.model_validate(candidate(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"value": "2025-13"},
        {"value": "2025-3"},
        {"value": "2025-03-14"},
        {"evidence_status": "inferred"},
        {"reliability": "standard"},
        {"input_classes": ["public", "synthetic"], "provenance": "synthetic"},
    ],
)
def test_calendar_month_refuses_plants(changes):
    from eii_core.facts import Fact

    row = candidate(unit="calendar_month", value="2025-03")
    row.update(changes)
    with pytest.raises(ValueError):
        Fact.model_validate(row)


def identity_inputs():
    return dict(
        release_id=sha256(b"SYN-release").hexdigest(),
        metric_key="licence_density",
        geography={"kind": "national"},
        period="2025",
        qualifiers={"activity": "SYN-a"},
    )


def test_same_semantic_fact_gives_the_same_id():
    from eii_core.facts import fact_id

    assert fact_id(**identity_inputs()) == fact_id(**identity_inputs())


@pytest.mark.parametrize(
    "key,value",
    [
        ("release_id", sha256(b"SYN-other").hexdigest()),
        ("metric_key", "location_quotient"),
        ("geography", {"kind": "public", "public_code": "zone:SYN-a"}),
        ("period", "2024"),
        ("qualifiers", {"activity": "SYN-b"}),
    ],
)
def test_each_semantic_component_changes_the_id(key, value):
    from eii_core.facts import fact_id

    before = identity_inputs()
    after = dict(before, **{key: value})
    assert fact_id(**before) != fact_id(**after)


def test_call_shape_alone_does_not_change_the_id():
    from eii_core.facts import fact_id

    args = identity_inputs()
    assert fact_id(**args) == fact_id(**dict(reversed(tuple(args.items()))))
    with pytest.raises(TypeError):
        fact_id(**args, tool="SYN-other")
    with pytest.raises(ValueError, match="qualifier_unknown"):
        fact_id(**dict(args, qualifiers={"unknown": "SYN-a"}))


def chain_rows():
    line = dict(
        lineage_id="lin_pub_licence_active",
        table_name="pub_licence_active",
        source_id="SYN-source",
        input_class="public",
        transform="eii_core.calc.licence_density@v1",
    )
    source = dict(
        source_id="SYN-source",
        publisher="SYN-publisher",
        title="SYN-dataset",
        url="https://example.invalid/SYN-source",
        licence="SYN-licence",
        retrieved_on=date(2025, 1, 1),
        sha256=sha256(b"SYN-fixture").hexdigest(),
    )
    return [line], [source]


def test_complete_chain():
    from eii_core.facts import validate_chain

    lines, sources = chain_rows()
    assert validate_chain("lin_pub_licence_active", lines, sources) is None


@pytest.mark.parametrize(
    "plant",
    [
        "no_line",
        "no_source",
        "sha256",
        "licence",
        "retrieved_on",
        "transform",
        "table_name",
    ],
)
def test_chain_refuses_plants(plant):
    from eii_core.facts import validate_chain

    lines, sources = chain_rows()
    if plant == "no_line":
        lines = []
    elif plant == "no_source":
        sources = []
    elif plant in {"transform", "table_name"}:
        lines[0][plant] = ""
    else:
        sources[0][plant] = ""
    assert validate_chain("lin_pub_licence_active", lines, sources) is not None


@pytest.mark.parametrize(
    "unit,value",
    [
        ("qar_per_month", Decimal("12.5")),
        ("qar_thousand", Decimal("2.5")),
        ("qar", Decimal("2.5")),
        ("published_text", "SYN-class-12"),
    ],
)
def test_handler_units(unit, value):
    from eii_core.facts import Fact

    assert Fact.model_validate(candidate(unit=unit, value=value)).value == value
    with pytest.raises(ValueError):
        Fact.model_validate(candidate(unit=unit, value=True))


@pytest.mark.parametrize(
    "value",
    [
        "SYN-no-digit",
        "",
        " SYN-1",
        "SYN-1 ",
        "SYN-1\n",
        "SYN-\u0661",
        "SYN-1\u202e",
        "SYN-1\u2028",
        "x" * 200 + "1",
        "1" * 8,
        "1" * 11,
    ],
)
def test_published_text_refuses_plants(value):
    from eii_core.facts import Fact

    with pytest.raises(ValueError):
        Fact.model_validate(candidate(unit="published_text", value=value))


def test_unknown_metric_key_refused():
    from eii_core.facts import fact_id

    with pytest.raises(ValueError, match="metric_unknown"):
        fact_id(**dict(identity_inputs(), metric_key="SYN-unknown"))


def test_unknown_numeric_unit_refused():
    from eii_core.facts import Fact

    with pytest.raises(ValueError, match="unit_unknown"):
        Fact.model_validate(candidate(unit="SYN-unknown", value=2))
