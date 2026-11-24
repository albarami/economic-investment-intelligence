"""Test-owned embedded release; invented rows and fixture-byte source hashes only."""

import tempfile
from contextlib import contextmanager
from datetime import date
from hashlib import sha256
from pathlib import Path

from eii_product.store.embedded import EmbeddedStore
from eii_product.store.registry import PACKAGED, Inventory

SECTOR_INVENTORY = Inventory(
    tuple(q for q in PACKAGED.queries if q.name.startswith("sector_facts_")),
    PACKAGED.token,
    tuple(q for q in PACKAGED.names if q.name.startswith("sector_facts_")),
)

IDENTITY = sha256(b"SYN-sector-release").hexdigest()


def repository_path(relative, origin=__file__):
    """Find the copied repository from a test, including mutmut's nested tests."""
    for parent in Path(origin).resolve().parents:
        candidate = parent / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(relative)


def licence_rows():
    return {
        "pub_licence_active": [
            dict(
                municipality_code=municipality,
                activity_code=activity,
                period="2025-05",
                active_count=count,
                source_id="SYN-pub_licence_active",
            )
            for municipality, activity, count in [
                ("SYN-local", "SYN-restaurant", 361),
                ("SYN-local", "SYN-other", 13239),
                ("SYN-elsewhere", "SYN-restaurant", 4421),
                ("SYN-elsewhere", "SYN-other", 231601),
            ]
        ],
        "pub_population_municipality": [
            dict(
                municipality_code="SYN-local",
                period="2025",
                indicator="residents",
                value=111282,
                unit="persons",
                source_id="SYN-pub_population_municipality",
            )
        ],
    }


def with_lineage(data):
    output = {table: [dict(row) for row in rows] for table, rows in data.items()}
    sources, lines = [], []
    for table, rows in data.items():
        source = "SYN-" + table
        sources.append(
            dict(
                source_id=source,
                publisher="SYN-publisher",
                title=source,
                url="https://example.invalid/" + source,
                licence="SYN-fixture-licence",
                retrieved_on=date(2025, 1, 1),
                sha256=sha256(repr(rows).encode()).hexdigest(),
            )
        )
        lines.append(
            dict(
                lineage_id="lin_" + table,
                table_name=table,
                source_id=source,
                input_class="public",
                transform="eii_core.calc.fixture@v1",
            )
        )
    if "pub_licence_active" in data and "pub_population_municipality" in data:
        for table in ("pub_licence_active", "pub_population_municipality"):
            lines.append(
                dict(
                    lineage_id="lin_pub_licence_active_density",
                    table_name="pub_licence_active",
                    source_id="SYN-" + table,
                    input_class="public",
                    transform="eii_core.calc.licence_density@v1",
                )
            )
    if "pub_licence_active" in data and "pub_licence_cancelled" in data:
        for numerator in ("pub_licence_active", "pub_licence_cancelled"):
            for source_table in ("pub_licence_active", "pub_licence_cancelled"):
                lines.append(
                    dict(
                        lineage_id="lin_" + numerator + "_churn",
                        table_name=numerator,
                        source_id="SYN-" + source_table,
                        input_class="public",
                        transform="eii_core.calc.licence_churn@v1",
                    )
                )
    output["fact_lineage"], output["source_registry"] = lines, sources
    return output


@contextmanager
def release_store(data):
    import duckdb

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "SYN-release.duckdb"
        connection = duckdb.connect(str(path))
        tables = {
            table.name: table
            for query in SECTOR_INVENTORY.queries
            for table in query.tables
        }
        for name, table in tables.items():
            columns = {c.name: c.type_name for c in table.columns}
            sqltypes = {
                "string": "VARCHAR",
                "int": "BIGINT",
                "bool": "BOOLEAN",
                "date": "DATE",
            }
            connection.execute(
                "CREATE TABLE "
                + name
                + " ("
                + ", ".join(c + " " + sqltypes.get(t, t) for c, t in columns.items())
                + ")"
            )
            for row in data.get(name, []):
                connection.execute(
                    "INSERT INTO "
                    + name
                    + " VALUES ("
                    + ", ".join("?" for _ in columns)
                    + ")",
                    [row.get(c) for c in columns],
                )
        connection.close()
        store = EmbeddedStore(path, IDENTITY, SECTOR_INVENTORY)
        try:
            yield store
        finally:
            store.close()


@contextmanager
def licence_store():
    with release_store(with_lineage(licence_rows())) as store:
        yield store


def pay_rows():
    import json

    groups = json.loads(
        repository_path("core/tests/fixtures/methods/public_methods.json").read_text()
    )["published"]["C3"]["groups"]
    rows = []
    for index, group in enumerate(groups):
        for period, side in [("2020", "before"), ("2025", "after")]:
            for indicator, column, unit in [
                ("paid_workers", "workers_", "persons"),
                ("monthly_average_wage", "wage_", "QAR"),
            ]:
                rows.append(
                    dict(
                        table_code="wage_occ",
                        period=period,
                        breakdown_key="SYN-group-" + str(index),
                        indicator=indicator,
                        value=group[column + side].replace(",", ""),
                        unit=unit,
                        source_id="SYN-pub_wage_table",
                    )
                )
    return {"pub_wage_table": rows}


def utility_rows():
    rows = []
    for zone, before, after in [
        ("SYN-a", 1000000, 6500000),
        ("SYN-b", 1000000, 5400000),
        ("SYN-c", 1000000, 4000000),
        ("SYN-d", 429964072, 1436402796),
        ("SYN-other", 41_347_035_928, 54_377_697_204),
    ]:
        for period, value in [("2021", before), ("2025", after)]:
            rows.append(
                dict(
                    zone_code=zone,
                    period=period,
                    utility="electricity",
                    value=value,
                    unit="kWh",
                    partial_year=False,
                    source_id="SYN-pub_zone_utility",
                )
            )
    return {"pub_zone_utility": rows}


def churn_rows():
    """C2's two municipal worked rows, carried by invented area/activity keys."""
    active = [
        dict(
            municipality_code=area,
            activity_code="SYN-restaurant",
            period="2025-05",
            active_count=count,
            source_id="SYN-pub_licence_active",
        )
        for area, count in (("SYN-local", 2109), ("SYN-second", 361))
    ]
    cancelled = [
        dict(
            municipality_code=area,
            activity_code="SYN-restaurant",
            period=month,
            cancelled_count=count,
            bulk_month=flag,
            source_id="SYN-pub_licence_cancelled",
        )
        for area, month, count, flag in (
            ("SYN-local", "2024-01", 300, True),
            ("SYN-local", "2024-09", 18, True),
            ("SYN-second", "2024-01", 49, True),
            ("SYN-elsewhere", "2024-09", 11214, True),
            ("SYN-elsewhere", "2020-07", 40791, True),
            ("SYN-elsewhere", "2022-06", 14212, True),
            ("SYN-elsewhere", "2015-01", 87285, True),
            ("SYN-local", "UNDATED", 7386, False),
        )
    ]
    return {"pub_licence_active": active, "pub_licence_cancelled": cancelled}


def norm_rows(activity="SYN-restaurant"):
    """C4 inputs from the untouched arithmetic fixture; group remainders invented."""
    import json
    from decimal import Decimal

    years = json.loads(
        repository_path("core/tests/fixtures/methods/public_methods.json").read_text()
    )["published"]["C4"]["years"]
    rows = []
    for period, values in years.items():
        values = {k: Decimal(v.replace(",", "")) for k, v in values.items()}
        for indicator, value, unit in (
            ("employees:SYN-size", values["employees"], "count"),
            ("productivity_of_employee", values["productivity"], "QAR"),
            ("compensation", values["compensation_thousand"], "QAR_thousand"),
            ("operating_surplus", values["surplus_thousand"], "QAR_thousand"),
            ("goods_share", values["goods_percent"], "percent"),
            ("services_share", values["services_percent"], "percent"),
            ("intermediate_goods:Food%20Stuff", values["food"], "QAR_thousand"),
            ("intermediate_goods:Beverages", values["beverages"], "QAR_thousand"),
            (
                "intermediate_goods:SYN-other",
                values["goods_total"] - values["food"] - values["beverages"],
                "QAR_thousand",
            ),
            (
                "intermediate_services:Rents%20of%20Buildings",
                values["rent"],
                "QAR_thousand",
            ),
            (
                "intermediate_services:SYN-other",
                values["services_total"] - values["rent"],
                "QAR_thousand",
            ),
        ):
            rows.append(
                dict(
                    activity_code=activity,
                    period=period,
                    indicator=indicator,
                    value=value,
                    unit=unit,
                    source_id="SYN-pub_sector_accounts",
                )
            )
    return {"pub_sector_accounts": rows}


def fixed_rows(activity="SYN-restaurant"):
    from decimal import Decimal

    return {
        "pub_establishment_size": [
            dict(
                table_code="SYN-size",
                activity_key=activity,
                period="2022",
                size_class="s01_09",
                indicator="employees",
                value=37,
                unit="persons",
                source_id="SYN-pub_establishment_size",
            ),
        ],
        "pub_census_2015_municipality": [
            dict(
                municipality_code="SYN-local",
                period="2015",
                indicator="establishments",
                value=53,
                unit="count",
                source_id="SYN-pub_census_2015_municipality",
            ),
        ],
        "pub_trade_wr": [
            dict(
                trade_type=activity,
                period="2025",
                indicator=indicator,
                value=value,
                unit="QAR",
                source_id="SYN-pub_trade_wr",
            )
            for indicator, value in (
                ("purchases", Decimal("17.35")),
                ("sales", Decimal("41.73")),
            )
        ],
        "pub_hotels_municipality": [
            dict(
                municipality_code="SYN-local",
                period="2025",
                facility_type="SYN-hotel",
                facility_count=71,
                source_id="SYN-pub_hotels_municipality",
            ),
        ],
        "pub_visitor_markets": [
            dict(
                table_code="SYN-visitors",
                nationality_group="SYN-group",
                breakdown_key="SYN-all",
                period="2025",
                indicator=indicator,
                value=value,
                unit="persons",
                source_id="SYN-pub_visitor_markets",
            )
            for indicator, value in (("arrivals", 89), ("guests", 97))
        ],
    }
