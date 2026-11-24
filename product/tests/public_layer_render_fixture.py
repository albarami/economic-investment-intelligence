"""Invented release rows served by the real ASGI routes for mounted UI tests.

Only the store is an in-memory named-read fixture. Neither producer, HTTP route,
Fact validator nor renderer is replaced. Run from the repository root.
"""

import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from product.tests.public_http_support import Client
from product.tests.test_tools_http import CardStore

from eii_product.api.app import create_app
from eii_product.ledger.local import LocalLedger
from eii_product.store.registry import PACKAGED, require_query


def seed_contract_rows(store):
    original = store.tables["fdi_projects"][0]
    query = require_query(PACKAGED, PACKAGED.lookup("layer_fdi_projects"))
    row = {
        field.name: (
            7
            if field.type_name == "bigint"
            else Decimal("12.5")
            if field.type_name == "numeric"
            else "INVENTED-" + field.name + " 2"
        )
        for field in query.returns
    }
    row.update(
        source_id=original["source_id"],
        project_key="fdi_abcdefabcdefabcd",
        company="INVENTED Company 2",
        announced="2025-03-04",
        project_year=2025,
        project_month=2,
        capex_unit="Mn USD",
        capex_currency="USD",
        lat=Decimal("1.25"),
        lng=Decimal("1.5"),
        sector="INVENTED Sector 2",
        source_country="INVENTED Country 2",
        place_key="INVENTED-landmark-a",
        tags='["INVENTED-tag 2"]',
    )
    unplaced = {
        **row,
        "project_key": "fdi_bbcdefabcdefabcd",
        "company": "INVENTED Unplaced",
        "sector": "INVENTED Other Sector",
        "source_country": "INVENTED Other Country",
        "announced": "2024-02",
        "project_year": 2024,
        "location_text": "INVENTED Other Location",
        "place_key": "INVENTED-missing",
        "lat": None,
        "lng": None,
        "jobs": None,
        "capex_value": None,
    }
    crosswalk = {
        **row,
        "project_key": "fdi_cccdefabcdefabcd",
        "company": "INVENTED Crosswalk",
        "lat": None,
        "lng": None,
    }
    direct = {
        **row,
        "project_key": "fdi_ddcdefabcdefabcd",
        "company": "INVENTED Direct Point",
        "place_key": None,
    }
    store.tables["fdi_projects"] = [row, unplaced, crosswalk, direct]
    fsq_source = "INVENTED-fsq-source"
    source = {
        **store.tables["source_registry"][0],
        "source_id": fsq_source,
        "title": "INVENTED Foursquare credit",
        "publisher": "INVENTED Foursquare publisher",
    }
    store.tables["source_registry"] = [*store.tables["source_registry"], source]
    store.tables["fact_lineage"] = [
        {**line, "source_id": fsq_source}
        if line["table_name"] == "pub_place_fsq"
        else line
        for line in store.tables["fact_lineage"]
    ]
    store.tables["pub_place_fsq"] = [
        {**place, "source_id": fsq_source, "source_release": "2025-01-10"}
        for place in store.tables["pub_place_fsq"]
    ]


def registry_input(body, store):
    """Use the fixture's actual release/source/lineage rows, never invent a link."""
    features = body["payload"]["layers"][0]["features"]
    metrics = {}
    for feature in features:
        metrics[feature["fact_id"]] = feature["metric_key"]
        for slot, metric in (
            ("capex_fact_id", "fdi_capex"),
            ("jobs_fact_id", "fdi_jobs"),
            ("lon_fact_id", "fdi_location"),
            ("lat_fact_id", "fdi_location"),
        ):
            if slot in feature:
                metrics[feature[slot]] = metric
        for field in feature.get("field_segments", {}).values():
            for segment in field:
                if segment["kind"] == "reference":
                    metrics[segment["recordId"]] = "fdi_field"
    lineages = []
    for ref in dict.fromkeys(fact["lineage_ref"] for fact in body["facts"]):
        rows = [
            line for line in store.tables["fact_lineage"] if line["lineage_id"] == ref
        ]
        method, version = rows[0]["transform"].rsplit("@", 1)
        lineages.append(
            dict(
                lineageId=ref,
                releaseId=store.release_id,
                tableName=rows[0]["table_name"],
                method=method,
                methodVersion=version,
                sourceIds=[line["source_id"] for line in rows],
                inputClasses=["public"],
            )
        )
    source_ids = {source for line in lineages for source in line["sourceIds"]}
    return dict(
        facts=[
            dict(
                fact=fact,
                metricKey=metrics.get(fact["fact_id"], "fdi_field"),
                presentation="ordinary",
            )
            for fact in body["facts"]
        ],
        releases=[dict(releaseId=store.release_id)],
        tables=[
            dict(tableName=line["tableName"], releaseId=store.release_id)
            for line in lineages
        ],
        lineages=lineages,
        sources=[
            dict(
                sourceId=source["source_id"],
                kind="public_dataset",
                inputClass="public",
                publisher=source["publisher"],
                datasetOrPage=source["title"],
                licenceOrTerms=source["licence"],
                retrievalDate=str(source["retrieved_on"]),
                sha256=source["sha256"],
            )
            for source in store.tables["source_registry"]
            if source["source_id"] in source_ids
        ],
    )


def route_cases():
    store = CardStore()
    seed_contract_rows(store)
    with TemporaryDirectory(prefix="layer-render-") as temporary:
        ledger = LocalLedger(Path(temporary) / "ledger.sqlite")
        try:
            app = create_app(
                Path("product/tests/fixtures/tiles"),
                store=store,
                ledger=ledger,
                fc_setting_reader=lambda: None,
            )
            client = Client(app)
            cases = {}
            for name, key in (
                ("fdi", "fdi_projects"),
                ("mixed", "public_places"),
                ("fsq_only", "public_places"),
                ("public_only", "public_places"),
                ("undated", "fdi_projects"),
            ):
                if name == "fsq_only":
                    public = store.tables["pub_place"]
                    store.tables["pub_place"] = []
                if name == "public_only":
                    store.tables["pub_place"] = public
                    store.tables["pub_place_fsq"] = []
                if name == "undated":
                    store.tables["fdi_projects"] = [
                        {
                            **store.tables["fdi_projects"][0],
                            "announced": None,
                            "project_year": None,
                            "project_month": None,
                        }
                    ]
                response = client.get("/api/layers/" + key)
                body = response.json()
                cases[name] = dict(
                    status=response.status_code,
                    body=body,
                    registry=registry_input(body, store)
                    if response.status_code == 200
                    else None,
                )
            assert ledger.rows() == []
            return cases
        finally:
            ledger.close()


if __name__ == "__main__":
    print(json.dumps(route_cases()))
