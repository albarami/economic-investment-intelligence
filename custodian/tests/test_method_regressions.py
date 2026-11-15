"""Invented-row parsing-to-calculation tests, not pinned public-file replays."""

import json
from dataclasses import replace
from decimal import Decimal as D

import pytest

from eii_core.calc.facts import CalculationFact, Measure, SourceChain
from eii_core.calc.public_methods import (
    AnnualEnergy,
    TradeRow,
    coverage_share,
    licence_churn,
    licence_density,
    location_quotient,
    supplier_metrics,
    zone_momentum,
)
from eii_core.calc.public_series import decomposition
from eii_core.calc.sector_economics import sector_norms
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.series.parse import parse_rows, selected_source
from eii_custodian.publicdata.series.reconcile import emit_fact


def measure(
    value, unit="count", period="2025-05", geography="invented", kind="municipality"
):
    if kind in ("municipality", "zone", "district", "place"):
        geography = kind + ":" + geography
        kind = "public"
    return Measure(
        D(value),
        unit,
        period,
        geography,
        kind,
        "public",
        (
            SourceChain(
                "invented",
                "invented",
                "card",
                "1",
                "invented",
                "invented",
                "https://example.org/invented",
                "invented_fixture",
                "2026-11-14",
                "b" * 64,
            ),
        ),
    )


def parsed(source, rows):
    """Use S2-T03 exact-copy parser with visibly invented source columns."""
    entry = next(e for e in load_registry() if e.key == source)
    columns = tuple(
        (key, "string" if isinstance(value, str) else "number")
        for key, value in rows[0].items()
    )
    entry = replace(entry, columns=columns)
    return parse_rows(
        entry, rows, {key: key.removeprefix("invented_") for key, _ in columns}
    )


def test_method_c1_and_c2_parsed_counts():
    row = parsed(
        "lic_active",
        [
            {
                "invented_local": 10,
                "invented_all": 100,
                "invented_national": 20,
                "invented_activities": 1000,
                "invented_population": 200,
            }
        ],
    )[0]
    # The population is the residents figure, not the national licence total.
    assert licence_density(
        measure(row["local"]),
        measure(row["population"]),
    ).value == D(500)
    assert location_quotient(
        measure(row["local"]),
        measure(row["all"]),
        measure(row["national"], geography="national", kind="national"),
        measure(row["activities"], geography="national", kind="national"),
    )["value"].value == D(5)
    cancellations = parsed(
        "lic_cancelled", [{"invented_month": "2025-01", "invented_count": 2}]
    )
    calendar = tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))
    result = licence_churn(
        measure(10),
        {r["month"]: measure(r["count"], period=r["month"]) for r in cancellations},
        {},
        calendar,
        measure(3, geography="national", kind="national"),
        measure(2, geography="national", kind="national"),
    )
    assert result["including_percent"].value == D(20)
    assert result["undated_count"].value == 1


def test_method_c3_parsed_workers_and_wages_with_table_identity():
    rows = parsed(
        "wage_occ",
        [
            {
                "invented_group": "invented_a",
                "invented_n0": 3,
                "invented_w0": 10,
                "invented_n1": 1,
                "invented_w1": 14,
            },
            {
                "invented_group": "invented_b",
                "invented_n0": 1,
                "invented_w0": 30,
                "invented_n1": 3,
                "invented_w1": 34,
            },
        ],
    )
    assert {r["table_code"] for r in rows} == {"wage_occ"}

    def pair(count: object, wage: object, period: str):
        return (
            measure(count, period=period, geography="national", kind="national"),
            measure(
                wage,
                unit="qar_per_month",
                period=period,
                geography="national",
                kind="national",
            ),
        )

    result = decomposition(
        {r["group"]: pair(r["n0"], r["w0"], "2020") for r in rows},
        {r["group"]: pair(r["n1"], r["w1"], "2025") for r in rows},
    )

    def shown(key: str) -> D:
        row = result[key]
        assert isinstance(row, CalculationFact)
        return row.value

    assert shown("change") == D(14)
    assert shown("within") == D(4)
    assert shown("mix") == D(10)
    assert shown("fixed_composition_change") == D(4)
    assert emit_fact(result, ("wage_occ",), {"wage_occ": "open"}, ()) is None


def test_method_c4_parsed_norms_stay_behind_signoff():
    row = parsed(
        "sec_hr_ind",
        [
            {
                "invented_productivity": 100,
                "invented_compensation": 1,
                "invented_surplus": D(".5"),
            }
        ],
    )[0]
    common = {"period": "2022", "geography": "national", "kind": "national"}
    result = sector_norms(
        employees=measure(10, **common),
        productivity=measure(row["productivity"], unit="qar", **common),
        compensation_thousand=measure(
            row["compensation"], unit="qar_thousand", **common
        ),
        surplus_thousand=measure(row["surplus"], unit="qar_thousand", **common),
        goods_percent=measure(20, unit="percent", **common),
        services_percent=measure(10, unit="percent", **common),
    )
    assert result["compensation_percent"].value == D(100)
    assert result["surplus_percent"].value == D(50)
    assert (
        emit_fact(result, ("sec_hr_ind",), {"sec_hr_ind": "resolved:invented"}, ())
        is None
    )


def test_method_c5_parsed_values_and_units():
    rows = parsed(
        "cus_imp_2025",
        [
            {"invented_value": 30, "invented_weight": 2, "invented_unit": "kg"},
            {"invented_value": 10, "invented_weight": 0, "invented_unit": "kg"},
        ],
    )
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    result = supplier_metrics(
        [
            TradeRow(
                "invented_line",
                "invented_origin",
                "2025-01",
                D(r["value"]),
                D(r["weight"]),
                r["unit"],
                measure(
                    r["value"],
                    unit="qar",
                    period="2025-01",
                    geography="national",
                    kind="national",
                ),
                measure(
                    r["weight"],
                    unit="kg",
                    period="2025-01",
                    geography="national",
                    kind="national",
                ),
            )
            for r in rows
        ],
        ("invented_line",),
        months,
        months,
        reviewed=True,
    )
    assert result["hhi"].value == D(10000)
    assert result["origins"]["invented_origin"]["unit_value"].value == D(15)
    assert result["total_value"].value == D(40)


def test_method_c8_and_c9_invented_parsed_rows():
    # This generic parser check is not a claim of a confirmed census schema.
    row = parsed(
        "util_elec",
        [
            {
                "invented_private": 3,
                "invented_employed": 4,
                "invented_before": 1000000,
                "invented_after": 2000000,
            }
        ],
    )[0]
    assert coverage_share(measure(row["private"]), measure(row["employed"]))[
        "percent"
    ].value == D(75)
    result = zone_momentum(
        [
            AnnualEnergy(
                "invented",
                2021,
                D(row["before"]),
                True,
                measure(
                    row["before"],
                    unit="kwh",
                    period="2021",
                    geography="invented",
                    kind="zone",
                ),
            ),
            AnnualEnergy(
                "invented",
                2025,
                D(row["after"]),
                True,
                measure(
                    row["after"],
                    unit="kwh",
                    period="2025",
                    geography="invented",
                    kind="zone",
                ),
            ),
        ],
        AnnualEnergy(
            "national",
            2021,
            D(10),
            True,
            measure(
                10, unit="kwh", period="2021", geography="national", kind="national"
            ),
        ),
        AnnualEnergy(
            "national",
            2025,
            D(20),
            True,
            measure(
                20, unit="kwh", period="2025", geography="national", kind="national"
            ),
        ),
    )
    assert result["zones"]["invented"]["ratio"].value == D(2)
    assert result["zones"]["invented"]["relative"].value == D(1)


def test_method_c20_parsed_numeric_comparison():
    from eii_core.calc.facts import CalculationFact, SourceChain, compare_public_facts

    row = parsed("util_elec", [{"invented_before": 120, "invented_after": 150}])[0]
    chain = SourceChain(
        "invented",
        "invented",
        "C20",
        "1",
        "invented",
        "invented",
        "https://example.org/invented",
        "invented_fixture",
        "2026-11-14",
        "b" * 64,
    )
    before = CalculationFact(
        D(row["before"]),
        "count",
        "invented",
        "invented",
        "national",
        "2025-01",
        ("public",),
        (chain,),
        geography_kind="national",
    )
    result = compare_public_facts(
        before, replace(before, value=D(row["after"]), period="2025-02")
    )
    assert result.difference.value == D(30)
    assert result.ratio.value == D("1.25")


@pytest.mark.parametrize("plant", ["stale_hash", "missing_basis", "missing_file"])
def test_method_receipt_plants(tmp_path, plant):
    entry = replace(
        next(e for e in load_registry() if e.key == "sec_hr_ind"),
        columns=(("invented_value", "integer"),),
    )
    body = b'[{"invented_value": 10}]'
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=1,
        terms_sha256="",
    )
    commit_pair(tmp_path / entry.key, digest, "json", body, receipt)
    if plant == "stale_hash":
        (tmp_path / entry.key / f"{digest}.json").write_bytes(
            b'[{"invented_value": 11}]'
        )
    elif plant == "missing_basis":
        del receipt["licence_basis"]
        (tmp_path / entry.key / f"{digest}.meta.json").write_text(json.dumps(receipt))
    else:
        (tmp_path / entry.key / f"{digest}.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        selected_source(tmp_path, entry, digest)
