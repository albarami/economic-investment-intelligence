"""S3-T12 accident read over a mounted invented release (amendments 1 and 3).

The committed web fixture is exactly these HTTP bodies and chains; the web
App test renders it. Invented rows only; no cache, no network.
"""

import json
from pathlib import Path

import pytest
from product.tests.test_mounted_release_http import loaded as loaded
from product.tests.test_mounted_release_http import mounted as mounted
from product.tests.test_tools_http import CardStore

from eii_product.api.public_layers import read_layer
from eii_product.store.protocol import QueryResult

FIXTURE = Path("web/tests/fixtures/accident-layer.json")


class Traced:
    """Records each named read; may hide the accident table from the manifest."""

    def __init__(self, store, *, absent=False, no_geometry=False):
        self.absent, self.no_geometry = absent, no_geometry
        self.read = store.fetch  # bound before any patch, so no recursion
        self.engine, self.release_id = store.engine, store.release_id
        self.names: list[str] = []

    def fetch(self, query, params):
        self.names.append(query.name)
        if self.absent and query.name == "layer_accidents":
            raise AssertionError("absent table queried")
        result = self.read(query, params)
        if self.no_geometry and query.name == "layer_zone_geometry":
            return QueryResult(result.columns, ())
        if self.absent and query.name == "public_release_manifest":
            index = result.columns.index("table_name")
            return QueryResult(
                result.columns,
                tuple(r for r in result.rows if r[index] != "pub_accident_zone"),
            )
        return result


def projection(client, store, monkeypatch):
    def layer(**changes):
        traced = Traced(store, **changes)
        with monkeypatch.context() as patch:
            patch.setattr(store, "fetch", traced.fetch)
            response = client.get("/api/layers/accidents")
        assert response.status_code == 200
        return response.json()

    bodies = {
        "accidents": client.get("/api/layers/accidents").json(),
        "rail_plan": client.get("/api/layers/rail_plan").json(),
        "geography_missing": layer(no_geometry=True),
        "source_missing": layer(absent=True),
    }
    chains = {
        fact["fact_id"]: client.get("/api/facts/" + fact["fact_id"] + "/lineage").json()
        for body in bodies.values()
        for fact in body["facts"]
    }
    return dict(release=client.get("/api/release").json(), chains=chains, **bodies)


def test_mounted_accident_bodies_are_the_web_fixture(mounted, monkeypatch):
    client, store, _rows = mounted
    got = projection(client, store, monkeypatch)
    assert got["accidents"]["status"] == "ok"
    assert [
        f["source_zone"] for f in got["accidents"]["payload"]["layers"][0]["features"]
    ] == ["51", "52"]
    for key, reason in (
        ("geography_missing", "accident_geography_missing"),
        ("source_missing", "accident_source_missing"),
    ):
        assert (got[key]["status"], got[key]["reason"], got[key]["facts"]) == (
            "NO_DATA",
            reason,
            [],
        )
        assert got[key]["payload"]["layers"][0]["features"] == []
    assert got == json.loads(FIXTURE.read_text(encoding="utf-8"))
    # The web App test spawns this test and renders this exact projection.
    print("ACCIDENT_PROJECTION=" + json.dumps(got, sort_keys=True))


@pytest.mark.parametrize("engine", ["embedded", "in_memory"])
def test_absent_table_answers_no_data_before_any_table_query(mounted, engine):
    """Amendment 3: the sealed manifest decides; no accident or zone read runs."""
    store = mounted[1] if engine == "embedded" else CardStore()
    traced = Traced(store, absent=True)
    body = read_layer(traced, "accidents")
    assert (body["status"], body["reason"], body["facts"]) == (
        "NO_DATA",
        "accident_source_missing",
        [],
    )
    assert body["coverage_report"] == {"counts": {}}
    assert traced.names == ["public_release_manifest"]
