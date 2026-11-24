"""Complete envelope comparison supplements the numeric parity guard."""

import json

import pytest
from product.tests.scan_places_support import fixture

from eii_product.tools import registry
from eii_product.tools.scan_places import scan_places


def canonical(result):
    data = result.model_dump(mode="json")
    del data["engine"], data["call_id"]
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def test_scan_places_registered():
    assert "scan_places" in registry.tool_keys()


def test_complete_fact_parity_detects_divergence():
    store, context, request, _ = fixture()
    result = scan_places(store, request, context)
    baseline = canonical(result)
    for field, value in [
        ("lineage_ref", "lin_wrong"),
        ("evidence_status", "inferred"),
        ("value", 999),
    ]:
        changed = result.model_copy(
            update={
                "facts": [
                    result.facts[0].model_copy(update={field: value}),
                    *result.facts[1:],
                ]
            }
        )
        with pytest.raises(AssertionError):
            assert canonical(changed) == baseline
    data = result.model_dump(mode="json")
    assert data["payload"]["outline"] is not None


@pytest.mark.parametrize("plant", ["date", "place", "caveat", "outline", "block"])
def test_complete_payload_parity_detects_divergence(plant):
    from copy import deepcopy

    store, context, request, _ = fixture()
    result = scan_places(store, request, context)
    data = result.model_dump(mode="json")
    del data["engine"], data["call_id"]
    other = deepcopy(data)
    if plant == "date":
        other["facts"][-1]["value"] = "2024-01-01"
    elif plant == "place":
        other["payload"]["places"][0]["place_id"] = "SYN-other"
    elif plant == "caveat":
        other["caveat_keys"] = []
    elif plant == "outline":
        other["payload"]["outline"]["coordinates"][0] = "0.001"
    else:
        other["blocks"]["places_fsq"] = "OK"
    with pytest.raises(AssertionError):
        assert json.dumps(
            other, sort_keys=True, separators=(",", ":")
        ).encode() == canonical(result)


@pytest.mark.parametrize("plant", ["case", "skipped", "unowned"])
def test_parity_coverage_plants(plant):
    from dataclasses import replace

    from eii_product.store.parity import run_parity
    from eii_product.store.protocol import StoreRefusal
    from eii_product.store.registry import PACKAGED, Inventory
    from eii_product.tools.scan_places import QUERY_NAMES

    first, context, request, _ = fixture()
    second, _, _, _ = fixture()
    second.engine = "postgres"
    names = QUERY_NAMES + (("scan_places_neighbours",) if plant == "skipped" else ())
    inventory = Inventory(
        tuple(q for q in PACKAGED.queries if q.name in names),
        PACKAGED.token,
        tuple(q for q in PACKAGED.names if q.name in names),
    )
    descriptor = registry.scan_places_descriptor(context, [])
    if plant == "unowned":
        descriptor = replace(
            descriptor,
            queries=tuple(q for q in QUERY_NAMES if q != "scan_places_places"),
        )
    cases = (
        () if plant == "case" else registry.scan_places_parity_cases(request["area_id"])
    )
    with pytest.raises(
        StoreRefusal,
        match={
            "case": "tool case missing",
            "skipped": "query not executed",
            "unowned": "query not owned",
        }[plant],
    ):
        run_parity(
            (first, second),
            (descriptor,),
            cases,
            inventory,
            unit_precision={"metres": 3, "ratio": 4, "published_text": 0},
            round_fact=lambda value, places: value,
        )


@pytest.mark.parametrize("scenario", ["mapped", "mapping_missing", "no_base_cell"])
def test_scan_places_parity_guard_with_stand_in_second_engine(tmp_path, scenario):
    from dataclasses import replace
    from datetime import date
    from decimal import Decimal

    import duckdb
    from product.tests.make_area_support import write_database
    from product.tests.scan_places_support import records, replace_rows

    from eii_core.calc.public_series import rounded
    from eii_product.store.embedded import EmbeddedStore
    from eii_product.store.parity import run_parity
    from eii_product.store.registry import PACKAGED, Inventory
    from eii_product.tools.scan_places import QUERY_NAMES

    store, context, request, _ = fixture()
    row = records(store, "places")[0]
    if scenario == "no_base_cell":
        from product.tests.make_area_support import NO_CELL

        from eii_product.tools.make_area import make_area

        area = make_area(
            store,
            dict(
                latitude=NO_CELL[0], longitude=NO_CELL[1], mode="distance", cutoff=250
            ),
            context.area,
        )
        assert area.payload["units"] == {}
        assert area.payload["record"]["anchor_cell"] is None
        request["area_id"] = area.payload["area_id"]
        row.update(lat=NO_CELL[0], lon=NO_CELL[1])
        replace_rows(store, "places", [row])
    if scenario == "mapping_missing":
        context = replace(context, mapping=None)
    fsq = {
        key: row[key]
        for key in (
            "name",
            "name_ar",
            "lon",
            "lat",
            "cell",
            "source_release",
            "licence",
        )
    }
    fsq.update(
        fsq_place_id="SYN-fsq",
        category_ids="SYN-source-category",
        category_labels="SYN Food",
    )
    replace_rows(store, "fsq", [fsq])
    replace_rows(
        store,
        "verification",
        [
            dict(
                place_id="SYN-place",
                check_date=date(2025, 1, 1),
                reviewer_role="SYN-reviewer",
                verification_link="https://example.invalid/SYN",
                status="verified_open",
                source_id="roads_osm",
            )
        ],
    )
    replace_rows(
        store,
        "visits",
        [
            dict(
                venue_key="SYN-venue",
                place_id="SYN-place",
                venue_kind="museum_or_exhibition",
                name_en="SYN Orchard",
                name_ar=None,
                region=None,
                period="2025",
                indicator="visitors",
                value=12,
                unit="visits",
            )
        ],
    )
    store.engine = "postgres"  # A stand-in label, never a Postgres connection.
    path = tmp_path / "SYN-places.duckdb"
    write_database(path)
    connection = duckdb.connect(str(path))
    types = {
        "text": "VARCHAR",
        "numeric": "DECIMAL(24,8)",
        "date": "DATE",
        "bigint": "BIGINT",
    }
    for query in PACKAGED.queries:
        if not query.name.startswith("scan_places_"):
            continue
        table = query.tables[0].name
        connection.execute(
            "CREATE TABLE "
            + table
            + " ("
            + ", ".join(c.name + " " + types[c.type_name] for c in query.returns)
            + ")"
        )
        rows = store._rows[query.name]
        if rows:
            connection.executemany(
                "INSERT INTO "
                + table
                + " VALUES ("
                + ",".join("?" for _ in query.returns)
                + ")",
                rows,
            )
    connection.close()
    inventory = Inventory(
        tuple(q for q in PACKAGED.queries if q.name in QUERY_NAMES),
        PACKAGED.token,
        tuple(q for q in PACKAGED.names if q.name in QUERY_NAMES),
    )
    embedded = EmbeddedStore(path, store.release_id, inventory)
    payloads = []

    def round_fact(value, places):
        return (
            value
            if isinstance(value, str)
            else Decimal(rounded(Decimal(value), places))
        )

    try:
        result = run_parity(
            (embedded, store),
            (registry.scan_places_descriptor(context, payloads),),
            registry.scan_places_parity_cases(request["area_id"]),
            inventory,
            unit_precision={
                "metres": 3,
                "ratio": 4,
                "count": 0,
                "calendar_date": 0,
                "published_text": 0,
            },
            round_fact=round_fact,
        )
        assert result.coverage.passed
        assert payloads[0] == payloads[1]
        assert set(result.traces["embedded"]) == set(QUERY_NAMES)
    finally:
        embedded.close()
