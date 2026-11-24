"""Fact builder preserves calculation values and resolves every input source."""

from datetime import date
from decimal import Decimal
from hashlib import sha256

import pytest

from eii_core.calc import licence_density
from eii_core.calc.facts import Measure, SourceChain


def fixture():
    digest = sha256(b"SYN-fixture").hexdigest()
    source = SourceChain(
        "lin_pub_licence_active",
        "pub_licence_active",
        "eii_core.calc.licence_density",
        "v1",
        "SYN-publisher",
        "SYN-dataset",
        "https://example.invalid/SYN-source",
        "SYN-licence",
        "2025-01-01",
        digest,
    )
    lines = [
        dict(
            lineage_id=source.lineage_ref,
            table_name=source.table,
            source_id="SYN-source",
            input_class="public",
            transform=source.method + "@v1",
        )
    ]
    sources = [
        dict(
            source_id="SYN-source",
            publisher=source.publisher,
            title=source.dataset,
            url=source.url,
            licence=source.licence,
            retrieved_on=date(2025, 1, 1),
            sha256=digest,
        )
    ]

    def measure(value):
        return Measure(
            Decimal(value), "count", "2025", "national", "national", "public", (source,)
        )

    return licence_density(measure(361), measure(111282)), lines, sources


def test_calculated_value_identity_and_release():
    from eii_product.tools.fact_builder import build_calculated

    value, lines, sources = fixture()
    release = sha256(b"SYN-release").hexdigest()
    fact = build_calculated(
        value,
        release_id=release,
        lineage_ref="lin_pub_licence_active",
        lineage_rows=lines,
        source_rows=sources,
        qualifiers={},
    )
    assert fact.value is value.value
    assert fact.release_id == release
    assert fact.evidence_status == "observed"
    assert fact.caveat_keys == ["calculated"]


def test_published_value_is_not_calculated():
    from eii_product.tools.fact_builder import build_published

    _, lines, sources = fixture()
    value = Decimal("2.3456")
    fact = build_published(
        value=value,
        unit="ratio",
        metric_key="licence_density",
        period="2025",
        geography={"kind": "national"},
        release_id=sha256(b"SYN-release").hexdigest(),
        lineage_ref="lin_pub_licence_active",
        lineage_rows=lines,
        source_rows=sources,
        qualifiers={},
    )
    assert fact.value is value
    assert "calculated" not in fact.caveat_keys


@pytest.mark.parametrize(
    "plant", ["digit", "unknown", "missing_source", "missing_hash"]
)
def test_builder_refuses_plants(plant, monkeypatch):
    from eii_product.tools import fact_builder as builder

    value, lines, sources = fixture()
    if plant == "digit":
        monkeypatch.setitem(builder.LABELS, "licence_density", ("Count 2", "العدد"))
    elif plant == "unknown":
        monkeypatch.delitem(builder.LABELS, "licence_density")
    elif plant == "missing_source":
        sources = []
    else:
        sources[0]["sha256"] = ""
    assert (
        builder.build_calculated(
            value,
            release_id=sha256(b"SYN-release").hexdigest(),
            lineage_ref="lin_pub_licence_active",
            lineage_rows=lines,
            source_rows=sources,
            qualifiers={},
        )
        is None
    )


def test_multitable_chain_requires_every_source_and_numerator():
    from dataclasses import replace

    from eii_product.tools.fact_builder import build_calculated

    value, lines, sources = fixture()
    other = replace(
        value.sources[0],
        lineage_ref="lin_pub_population_municipality",
        table="pub_population_municipality",
        dataset="SYN-residents",
        sha256=sha256(b"SYN-residents").hexdigest(),
    )
    value = replace(value, sources=(*value.sources, other))
    args = dict(
        release_id=sha256(b"SYN-release").hexdigest(),
        lineage_ref="lin_pub_licence_active",
        qualifiers={},
    )
    from eii_core.facts import validate_chain

    assert (
        build_calculated(value, lineage_rows=lines, source_rows=sources, **args) is None
    )
    lines.append(dict(lines[0], source_id="SYN-residents"))
    sources.append(
        dict(
            sources[0],
            source_id="SYN-residents",
            title=other.dataset,
            sha256=other.sha256,
        )
    )
    assert (
        build_calculated(value, lineage_rows=lines, source_rows=sources, **args)
        is not None
    )
    bad = [
        dict(row, lineage_id=other.lineage_ref, table_name=other.table) for row in lines
    ]
    assert (
        validate_chain(
            other.lineage_ref,
            bad,
            sources,
            required_sources=value.sources,
            numerator_table=value.sources[0].table,
        )
        == "lineage_numerator_mismatch"
    )


def test_stock_first_calculation_requires_cancellations_lineage():
    from dataclasses import replace

    from eii_product.tools.fact_builder import build_calculated

    value, lines, sources = fixture()
    cancelled = replace(
        value.sources[0],
        lineage_ref="lin_pub_licence_cancelled",
        table="pub_licence_cancelled",
        dataset="SYN-cancellations",
        sha256=sha256(b"SYN-cancellations").hexdigest(),
    )
    value = replace(
        value, metric_key="including_ratio", sources=(*value.sources, cancelled)
    )
    lines.append(dict(lines[0], source_id="SYN-cancellations"))
    sources.append(
        dict(
            sources[0],
            source_id="SYN-cancellations",
            title=cancelled.dataset,
            sha256=cancelled.sha256,
        )
    )
    stock_ref = "lin_pub_licence_active_churn"
    cancelled_ref = "lin_pub_licence_cancelled_churn"
    lines = [
        dict(row, lineage_id=ref, table_name=table)
        for ref, table in (
            (stock_ref, "pub_licence_active"),
            (cancelled_ref, "pub_licence_cancelled"),
        )
        for row in lines
    ]
    args = dict(
        release_id=sha256(b"SYN-release").hexdigest(),
        lineage_rows=lines,
        source_rows=sources,
        qualifiers={},
        numerator_table="pub_licence_cancelled",
    )
    assert build_calculated(value, lineage_ref=stock_ref, **args) is None
    fact = build_calculated(value, lineage_ref=cancelled_ref, **args)
    assert fact is not None
    assert fact.lineage_ref == cancelled_ref
