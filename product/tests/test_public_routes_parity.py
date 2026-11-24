"""Scoped embedded execution and stand-in ownership, never two-store evidence."""

from dataclasses import replace

import pytest
from public_release_fixture import build_fixture

from eii_core.facts import UNITS
from eii_core.shapes import canonical_ring
from eii_product.api.area_context import AreaContextFactory
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.parity import ParityCase, cover, run_parity
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import PACKAGED, Inventory
from eii_product.tools.make_area import RegisteredShape, ShapeMiss, make_area
from eii_product.tools.registry import public_card_descriptors, public_layer_descriptors


class Shapes:
    def find(self, key):
        if key == "ab" * 32:
            return RegisteredShape(
                canonical_ring(((0.5, 0.5), (0.5, 2.5), (2.5, 2.5), (2.5, 0.5)))
            )
        return ShapeMiss("unknown")


class SecondEngineStandIn:
    """Delegate to the embedded engine; provides no PostgreSQL execution proof."""

    engine = "postgres"

    def __init__(self, store):
        self.store = store
        self.release_id = store.release_id

    def fetch(self, query, params):
        return self.store.fetch(query, params)


@pytest.fixture(scope="module")
def executed(tmp_path_factory):
    folder = tmp_path_factory.mktemp("public-route-parity")
    identity = build_fixture(folder, cards=True)
    from test_live_public_release_load import _RecordingPostgres

    from eii_product.store.loader import _parquet_rows, run_load
    from eii_product.store.release_check import check_release, manifest_rows

    checked = check_release(folder)
    rows = {
        entry["name"]: _parquet_rows(
            folder / entry["file"], checked.schemas[entry["name"]]
        )
        for entry in checked.document["tables"]
    }
    rows["release_manifest"] = manifest_rows(checked.document)
    connection = _RecordingPostgres(rows, names=tuple(rows), columns=checked.schemas)
    assert (
        run_load(
            folder,
            host="invented.invalid",
            port=1,
            database="INVENTED",
            connect=lambda **kw: connection,
        )
        == 0
    )
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    try:
        context = AreaContextFactory(store.release_id, None).for_session(Shapes())
        made = make_area(store, {"shape_id": "ab" * 32}, context)
        assert made.status == "OK"
        area = made.payload["area_id"]
        groups = {
            "public_layers": (
                public_layer_descriptors(),
                tuple(
                    ParityCase(
                        d.key,
                        (("month_key", "2026-03"),)
                        if d.key == "layer:night_lights"
                        else (),
                    )
                    for d in public_layer_descriptors()
                ),
            ),
            "public_cards": (
                public_card_descriptors(context),
                (
                    ParityCase(
                        "night_lights", (("area_id", area), ("month_key", "2026-03"))
                    ),
                    ParityCase(
                        "venue_busyness", (("place_keys", ["INVENTED-venue-a"]),)
                    ),
                    ParityCase(
                        "population_age_sex", (("area_id", area), ("split", "sex"))
                    ),
                ),
            ),
        }
        result = {}
        for name, (tools, cases) in groups.items():
            names = {q for tool in tools for q in tool.queries}
            inventory = Inventory(
                tuple(q for q in PACKAGED.queries if q.name in names),
                PACKAGED.token,
                tuple(q for q in PACKAGED.names if q.name in names),
            )
            run = run_parity(
                (store, SecondEngineStandIn(store)),
                tools,
                cases,
                inventory,
                unit_precision=dict.fromkeys(UNITS, 4),
                round_fact=lambda number, precision: number,
            )
            result[name] = (tools, cases, inventory, run)
        yield result
    finally:
        store.close()


def test_all_named_reads_are_executed(executed):
    union = set()
    for name, (tools, _cases, inventory, result) in executed.items():
        assert result.coverage.passed
        assert all(
            r.status == ("ok" if name == "public_layers" else "OK") and r.facts
            for r in result.results
        ), [(r.tool, r.status, len(r.facts)) for r in result.results]
        expected = {q.name for q in inventory.queries}
        assert expected == {q for t in tools for q in t.queries}
        for trace in result.traces.values():
            assert set(trace) == expected
        union.update(expected)
    new = {
        q.name
        for q in PACKAGED.queries
        if q.name.startswith(
            ("layer_", "night_lights_", "venue_busyness_", "population_age_sex_")
        )
    }
    assert len(new) == 24
    assert "layer_fdi_gazetteer" in new
    assert "layer_company_points" in new
    assert new <= union


NEW_NAMES = tuple(
    q.name
    for q in PACKAGED.queries
    if q.name.startswith(
        ("layer_", "night_lights_", "venue_busyness_", "population_age_sex_")
    )
)


@pytest.mark.parametrize("removed", NEW_NAMES)
def test_each_missing_query_trace_is_refused(executed, removed):
    for tools, cases, inventory, result in executed.values():
        if removed not in {q.name for q in inventory.queries}:
            continue
        traces = {
            engine: tuple(q for q in trace if engine != "postgres" or q != removed)
            for engine, trace in result.traces.items()
        }
        with pytest.raises(StoreRefusal, match="query not executed"):
            cover(
                tools=tools,
                cases=cases,
                traces=traces,
                identities=dict.fromkeys(traces, "INVENTED-release"),
                query_names=tuple(q.name for q in inventory.queries),
            )


@pytest.mark.parametrize(
    "group,index",
    [("public_layers", i) for i in range(len(public_layer_descriptors()))]
    + [("public_cards", i) for i in range(3)],
)
def test_each_missing_case_is_refused(executed, group, index):
    tools, cases, inventory, result = executed[group]
    with pytest.raises(StoreRefusal, match="tool case missing"):
        cover(
            tools=tools,
            cases=cases[:index] + cases[index + 1 :],
            traces=result.traces,
            identities=dict.fromkeys(result.traces, "INVENTED-release"),
            query_names=tuple(q.name for q in inventory.queries),
        )


def test_empty_ownership_is_refused(tmp_path):
    from product.tests.test_tools_http import CardStore

    tools = public_layer_descriptors()
    names = {q for t in tools for q in t.queries}
    inventory = Inventory(
        tuple(q for q in PACKAGED.queries if q.name in names),
        PACKAGED.token,
        tuple(q for q in PACKAGED.names if q.name in names),
    )
    store = CardStore()
    with pytest.raises(StoreRefusal, match="query not owned"):
        run_parity(
            (store, SecondEngineStandIn(store)),
            (replace(tools[0], queries=()),),
            (ParityCase(tools[0].key, ()),),
            inventory,
            unit_precision=dict.fromkeys(UNITS, 4),
            round_fact=lambda number, precision: number,
        )
