"""Lead-run BE-60 proof; the suite exercises the command with an offline runner."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import live_public_release_load as load_proof
from fastapi import FastAPI
from public_release_fixture import build_fixture
from starlette.types import Message, Scope

from eii_core.reasons import reason
from eii_core.shapes import canonical_ring
from eii_product.api.app import create_app
from eii_product.api.area_context import AreaContextFactory, RoutingSource
from eii_product.api.session_store import SessionShapes
from eii_product.assistant.catalogue.load import catalogue_directory, load_catalogue
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.engine import execute, require_identical
from eii_product.assistant.playbooks.registry import Definition, load_playbook
from eii_product.assistant.templates.writer import compose
from eii_product.ledger.local import LocalLedger
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.loader import perform
from eii_product.store.parity import TracingStore
from eii_product.store.postgres import PostgresStore
from eii_product.store.protocol import (
    EngineName,
    Param,
    QueryResult,
    ReleaseStore,
    StoreHealth,
)
from eii_product.store.registry import PACKAGED, QueryName
from eii_product.tools.make_area import QUERY_NAMES as AREA_QUERIES
from eii_product.tools.make_area import MakeAreaContext, make_area
from eii_product.tools.resolve import QUERY_NAMES as RESOLVE_QUERIES

# The resolver, selected-key make_area, and the latter's exact Public snapshot.
# S3-T24 joins this inventory to its expanded real-store proof.
RESOLVE_ROUTE_QUERIES = frozenset(
    (
        *RESOLVE_QUERIES,
        *AREA_QUERIES,
        "layer_public_places",
        "layer_public_places_fsq",
        "layer_commercial_points",
        "layer_address_points",
        "layer_landmarks",
        "layer_fdi_projects",
        "layer_fdi_gazetteer",
        "public_lineage_for_table",
        "sector_facts_sources",
    )
)


def require_resolve_coverage(traces: Mapping[str, Sequence[str]]) -> None:
    """An inventory declaration is insufficient: both engines must execute it."""
    if set(traces) != {"postgres", "embedded"} or any(
        RESOLVE_ROUTE_QUERIES != set(trace) for trace in traces.values()
    ):
        raise ValueError("resolve_query_coverage")


def _post(
    app: FastAPI, tool: str, arguments: Mapping[str, object]
) -> tuple[int, dict[str, Any]]:
    """Drive the mounted ASGI route directly, using no network or test mock."""

    async def request() -> tuple[int, dict[str, Any]]:
        sent: list[Message] = []
        received = False

        async def receive() -> Message:
            nonlocal received
            if not received:
                received = True
                return {
                    "type": "http.request",
                    "body": json.dumps(arguments).encode(),
                    "more_body": False,
                }
            await asyncio.Event().wait()
            raise RuntimeError("unreachable")

        async def send(message: Message) -> None:
            sent.append(message)

        scope: Scope = dict(
            type="http",
            asgi={"version": "3.0", "spec_version": "2.3"},
            http_version="1.1",
            method="POST",
            scheme="http",
            path="/api/tools/" + tool,
            query_string=b"",
            root_path="",
            headers=[(b"content-type", b"application/json")],
            server=("testserver", 80),
            client=("127.0.0.1", 1234),
        )
        await app(scope, receive, send)
        status = next(
            message["status"]
            for message in sent
            if message["type"] == "http.response.start"
        )
        body = b"".join(
            message.get("body", b"")
            for message in sent
            if message["type"] == "http.response.body"
        )
        return status, cast(dict[str, Any], json.loads(body))

    return asyncio.run(request())


class ResolveTrace:
    """Delegate to the actual mounted engine and record successful executions."""

    def __init__(self, store: ReleaseStore) -> None:
        self.store = store
        self.release_id = store.release_id
        self.engine: EngineName = store.engine
        self.calls: list[str] = []

    def fetch(self, query: QueryName, params: Mapping[str, Param]) -> QueryResult:
        from eii_product.store.registry import require_query

        spec = require_query(PACKAGED, query)
        result = self.store.fetch(query, params)
        self.calls.append(spec.name)
        return result

    def ping(self, timeout_s: float) -> StoreHealth:
        return self.store.ping(timeout_s)

    def close(self) -> None:
        self.store.close()


def resolve_route_cases(
    store: ReleaseStore, ledger: LocalLedger
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Mounted bilingual requests; no provider, new route or fabricated pin."""
    traced = ResolveTrace(store)
    app = create_app(
        Path("product/tests/fixtures/tiles"),
        store=traced,
        ledger=ledger,
        key_reader=lambda: None,
        offline_reader=lambda: True,
        fc_setting_reader=lambda: None,
    )
    results = []
    for lang in ("en", "ar"):
        for en, ar, kind, status, key in (
            ("INVENTED-Garden", "حديقة مخترعة", "place", "OK", "INVENTED-landmark-a"),
            ("INVENTED-Court", "ساحة مخترعة", "place", "OK", "district:INVENTED-null"),
            ("INVENTED-Outside", "خارج مخترع", "place", "OUT_OF_SCOPE", None),
            ("INVENTED-missing", "غير موجود مخترع", "both", "NO_DATA", None),
            (
                "INVENTED-Craft",
                "حرفة مخترعة",
                "activity",
                "OK",
                "activity:INVENTED-craft",
            ),
        ):
            http_status, body = _post(
                app,
                "resolve",
                {"text": en if lang == "en" else ar, "lang": lang, "kind": kind},
            )
            if (
                http_status != 200
                or body["status"] != status
                or body["release_id"] != store.release_id
            ):
                raise ValueError("resolve_route_case")
            if key is not None and body["payload"]["candidates"][0]["key"] != key:
                raise ValueError("resolve_key_substitution")
            results.append(
                {k: v for k, v in body.items() if k not in {"call_id", "engine"}}
            )
            if kind != "place" or status != "OK":
                continue
            area_status, made = _post(
                app,
                "make_area",
                {
                    "place_key": body["payload"]["candidates"][0]["key"],
                    "mode": "distance",
                    "cutoff": 250,
                },
            )
            if area_status != 200 or made["status"] != "OK":
                raise ValueError("resolve_area_case")
            null = key == "district:INVENTED-null"
            if (made["payload"]["record"]["anchor_cell"] is None) != null:
                raise ValueError("resolve_nearest_cell")
            results.append(
                {k: v for k, v in made.items() if k not in {"call_id", "engine"}}
            )
    return results, tuple(traced.calls)


SELECTED_CASES = ("polygon", "distance", "walk", "drive", "default")
SELECTED_QUERIES = (
    "make_area_municipalities",
    "make_area_grid_cells",
    "layer_night_lights_months",
    "night_lights_cells",
    "population_age_sex_rows",
    "population_age_sex_bands",
    "public_lineage_for_table",
    "sector_facts_sources",
)


def require_selected_queries(traces: Mapping[str, Sequence[str]]) -> None:
    if set(traces) != {"postgres", "embedded"} or any(
        not set(SELECTED_QUERIES) <= set(names) for names in traces.values()
    ):
        raise ValueError("selected_query_missing")


def require_selected_cases(executed: set[tuple[str, str]]) -> None:
    """Selected case coverage is independent of query coverage."""
    required = {
        (engine, case) for engine in ("postgres", "embedded") for case in SELECTED_CASES
    }
    if executed != required:
        raise ValueError("selected_case_missing")


def require_live_selected_record(record: object) -> None:
    """A control result is not a lead-run live evidence record.

    The lead assembles this record from both command runs on the exact joined
    commit. Unit evidence and this worker's return cannot close that gate.
    """
    if (
        not isinstance(record, dict)
        or record.get("kind") != "live"
        or record.get("normal_exit") != 0
        or record.get("diverge_exit") != 3
        or not isinstance(record.get("commit"), str)
        or len(record["commit"]) != 40
        or not isinstance(record.get("release_id"), str)
        or len(record["release_id"]) != 64
        or not isinstance(record.get("queries"), dict)
        or record.get("cases")
        != {engine: list(SELECTED_CASES) for engine in ("postgres", "embedded")}
    ):
        raise ValueError("live_selected_evidence_pending")
    require_selected_queries(record["queries"])


def selected_route(
    mode: str, minutes: int, lat: Decimal, lon: Decimal
) -> tuple[tuple[object, object], ...]:
    """Invented routing fixture only; never a provider or a live-data source."""
    d = Decimal(minutes) / Decimal(1000)
    return (
        (lat - d, lon - d),
        (lat - d, lon + d),
        (lat + d, lon + d),
        (lat + d, lon - d),
        (lat - d, lon - d),
    )


def selected_runs(
    store: ReleaseStore,
    definition: Definition,
    catalogue: Catalogue,
    ledger: LocalLedger,
) -> dict[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]]:
    """Execute every selection, language and repeat on this actual store."""
    shapes = SessionShapes()
    shape = shapes.add(
        canonical_ring(
            (
                (Decimal(".99"), Decimal(".99")),
                (Decimal(".99"), Decimal("1.01")),
                (Decimal("1.01"), Decimal("1.01")),
                (Decimal("1.01"), Decimal(".99")),
                (Decimal(".99"), Decimal(".99")),
            )
        )
    )
    context = AreaContextFactory(
        store.release_id, RoutingSource.from_call(selected_route)
    ).for_session(shapes)
    results = {}
    for case in SELECTED_CASES:
        selected: dict[str, Any] = (
            {"shape_id": shape}
            if case == "polygon"
            else {
                "pin": {"lat": 1, "lon": 1},
                **(
                    {}
                    if case == "default"
                    else {"mode": case, "cutoff": 500 if case == "distance" else 15}
                ),
            }
        )
        request = (
            {"shape_id": shape}
            if case == "polygon"
            else {
                "latitude": 1,
                "longitude": 1,
                "mode": selected.get("mode", "walk"),
                "cutoff": selected.get("cutoff", 5),
            }
        )
        expected = make_area(store, request, context)
        if expected.status != "OK" or expected.payload is None:
            raise ValueError("selected_fixture_invalid")
        for lang in ("en", "ar"):
            for repeat in ("a", "b"):
                bundle = execute(
                    store,
                    definition,
                    {"activity": "INVENTED-activity", "lang": lang, **selected},
                    catalogue,
                    ledger,
                    "INVENTED-" + store.engine + "-" + case + "-" + lang + "-" + repeat,
                    area_context=context,
                )
                headline = next(
                    step
                    for step in bundle.steps
                    if step["key"] == ("wider" if case == "drive" else "near")
                )
                require_identical(headline["payload"], dict(expected.payload))
                results[(case, lang, repeat)] = (
                    bundle.wire(),
                    compose(bundle, definition, catalogue).wire(),
                )
    return results


def judge(
    left: object, right: object, left_brief: object, right_brief: object, diverge: bool
) -> int:
    """The altered comparison returns three; an unexpected difference fails."""
    try:
        require_identical(left, right)
        require_identical(left_brief, right_brief)
    except ValueError:
        return 3 if diverge else 1
    return 1 if diverge else 0


def public_query_names() -> tuple[str, ...]:
    """Exact owned S3-T22 query inventory plus mounted source-chain reads."""
    from eii_product.tools.registry import (
        public_card_descriptors,
        public_layer_descriptors,
        public_transport_queries,
    )

    names = {
        q
        for tool in (
            *public_layer_descriptors(),
            *public_card_descriptors(cast(Any, None)),
        )
        for q in tool.queries
    }
    return tuple(sorted(names | set(public_transport_queries())))


def evidence_complete(record: Mapping[str, object], identity: str, commit: str) -> bool:
    """Lead gate predicate: pending, incomplete or another commit never closes it."""
    queries = record.get("queries")
    required = set(public_query_names()) | RESOLVE_ROUTE_QUERIES | set(SELECTED_QUERIES)
    return (
        record.get("state") == "complete"
        and record.get("release_id") == identity
        and record.get("commit") == commit
        and record.get("exits") == [0, 3]
        and isinstance(queries, dict)
        and set(queries) == {"postgres", "embedded"}
        and all(
            isinstance(queries[engine], list) and required <= set(queries[engine])
            for engine in queries
        )
    )


def public_projection(
    store: ReleaseStore, folder: Path
) -> tuple[list[dict[str, Any]], tuple[str, ...], MakeAreaContext]:
    """Execute one store's complete projection; offline tests make no live claim."""
    from eii_core.shapes import canonical_ring
    from eii_product.api.area_context import AreaContextFactory
    from eii_product.api.public_layers import PUBLIC_LAYER_KEYS, read_layer
    from eii_product.api.release import MountedRelease
    from eii_product.api.session_store import SessionShapes
    from eii_product.store.parity import TracingStore
    from eii_product.tools.make_area import RegisteredShape, ShapeMiss, make_area
    from eii_product.tools.public_context_tools import run_card

    class Shapes(SessionShapes):
        def find(self, key: str) -> RegisteredShape | ShapeMiss:
            return (
                RegisteredShape(
                    canonical_ring(((0.5, 0.5), (0.5, 2.5), (2.5, 2.5), (2.5, 0.5)))
                )
                if key == "ab" * 32
                else ShapeMiss("unknown")
            )

    found: list[str] = []
    traced = TracingStore(store, found)
    context = AreaContextFactory(store.release_id, None).for_session(Shapes())
    made = make_area(traced, {"shape_id": "ab" * 32}, context)
    if made.payload is None:
        raise ValueError("fixture_area_missing")
    mount = MountedRelease(traced, folder)
    output = [mount.summary()]
    for key in PUBLIC_LAYER_KEYS:
        body = mount.layer(read_layer(traced, key))
        output.append(body)
    for tool, args in (
        (
            "night_lights",
            {"area_id": made.payload["area_id"], "month_key": "2026-03"},
        ),
        (
            "population_age_sex",
            {"area_id": made.payload["area_id"], "split": "sex"},
        ),
        ("venue_busyness", {"place_keys": ["INVENTED-venue-a"]}),
    ):
        result = run_card(traced, tool, args, context)
        from eii_product.api.results import PublicResult

        if not isinstance(result, PublicResult):
            raise ValueError("fixture_card_missing")
        mount.card(result)
        output.append(
            dict(
                tool=tool,
                status=result.status,
                facts=[f.model_dump(mode="json") for f in result.facts],
                payload=result.payload,
            )
        )
    output.extend(mount.project(*emitted) for emitted in mount.emitted.values())
    return output, tuple(found), context


def public_routes_proof(
    postgres: PostgresStore,
    embedded: EmbeddedStore,
    folder: Path,
    ledger: LocalLedger,
    *,
    diverge: bool = False,
) -> dict[str, tuple[str, ...]]:
    """Require actual adapters before executing or reporting two-store evidence."""
    from eii_product.store.parity import ParityCase, cover
    from eii_product.tools.registry import (
        public_card_descriptors,
        public_layer_descriptors,
    )

    del ledger
    if type(postgres) is not PostgresStore or type(embedded) is not EmbeddedStore:
        raise ValueError("actual_stores_required")
    traces: dict[str, tuple[str, ...]] = {}
    outputs = []
    for store in (postgres, embedded):
        output, trace, context = public_projection(store, folder)
        traces[store.engine] = trace
        outputs.append(output)
    tools = (*public_layer_descriptors(), *public_card_descriptors(context))
    cover(
        tools=tools,
        cases=tuple(ParityCase(t.key, ()) for t in tools),
        traces=traces,
        identities={s.engine: s.release_id for s in (postgres, embedded)},
        query_names=public_query_names(),
    )
    require_identical(outputs[0], outputs[1])
    if diverge:
        changed = deepcopy(outputs[1])
        changed.pop()
        if judge(outputs[0], changed, {}, {}, True) != 3:
            raise ValueError("divergence_not_detected")
    print(
        json.dumps(dict(release_id=postgres.release_id, queries=traces), sort_keys=True)
    )
    return traces


def _run(environ: Mapping[str, str], diverge: bool) -> int:
    target = load_proof._target(environ)
    with tempfile.TemporaryDirectory(prefix="invented-playbook-") as temporary:
        folder = Path(temporary) / "release"
        identity = build_fixture(folder, resolver=True)
        database = load_proof.proof_database(identity)
        setup = load_proof._open(target, None, target.database)
        created = False
        try:
            if load_proof._exists(setup, "pg_database", "datname", database):
                raise ValueError("proof_database_exists")
            if not load_proof._exists(setup, "pg_roles", "rolname", "eii_owner"):
                raise ValueError("owner_role_unavailable")
            load_proof._statement(
                setup,
                f'CREATE DATABASE "{database}" TEMPLATE template0 OWNER eii_owner',
            )
            created = True
            proof = load_proof._open(target, None, database)
            try:
                load_proof._statement(proof, "CREATE EXTENSION postgis")
            finally:
                load_proof._close(proof)
            perform(
                folder,
                host=target.host,
                port=target.port,
                database=database,
                connect=load_proof._owner_connect(),
            )
            with ExitStack() as stack:
                connection = load_proof._open(target, None, database)
                stack.callback(load_proof._close, connection)
                postgres = PostgresStore(connection, identity, PACKAGED)
                embedded = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
                stack.callback(embedded.close)
                ledger = LocalLedger(Path(temporary) / "ledger.sqlite")
                stack.callback(ledger.close)
                catalogue = load_catalogue(catalogue_directory())
                if not isinstance(catalogue, Catalogue):
                    raise ValueError("catalogue_invalid")
                definition = load_playbook("site_check", catalogue)
                route_results = []
                route_traces: dict[str, tuple[str, ...]] = {}
                for store in (postgres, embedded):
                    route_result, route_trace = resolve_route_cases(store, ledger)
                    route_results.append(route_result)
                    route_traces[store.engine] = route_trace
                require_resolve_coverage(route_traces)
                require_identical(route_results[0], route_results[1])
                print(
                    "PASS resolve-route: "
                    + json.dumps(
                        {
                            "release_id": identity,
                            "executed_queries": {
                                engine: sorted(set(trace))
                                for engine, trace in route_traces.items()
                            },
                        },
                        sort_keys=True,
                    )
                )
                traces: dict[str, list[str]] = {"postgres": [], "embedded": []}
                runs = []
                executed: set[tuple[str, str]] = set()
                for store in (postgres, embedded):
                    results = selected_runs(
                        TracingStore(store, traces[store.engine]),
                        definition,
                        catalogue,
                        ledger,
                    )
                    executed.update(
                        (store.engine, case) for case, _lang, _repeat in results
                    )
                    runs.append(results)
                require_selected_cases(executed)
                require_selected_queries(traces)
                for key, (bundle_wire, rendered) in runs[0].items():
                    right, right_brief = runs[1][key]
                    require_identical(bundle_wire, right)
                    require_identical(rendered, right_brief)
                    case, lang, _repeat = key
                    baseline, brief = runs[0][(case, lang, "a")]
                    require_identical(baseline, bundle_wire)
                    require_identical(brief, rendered)
                baseline, brief = next(iter(runs[0].values()))
                right, right_brief = next(iter(runs[1].values()))
                public_routes_proof(postgres, embedded, folder, ledger, diverge=diverge)
                changed = deepcopy(right)
                if diverge:
                    changed["steps"].reverse()
                print("selected-cases: " + ",".join(SELECTED_CASES))
                print("selected-release: " + identity)
                for engine, names in traces.items():
                    print(engine + " executed-queries: " + ",".join(sorted(set(names))))
                return judge(baseline, changed, brief, right_brief, diverge)
        finally:
            try:
                if created:
                    load_proof._remove(setup, identity)
            finally:
                load_proof._close(setup)


def main(
    args: Sequence[str],
    environ: Mapping[str, str],
    *,
    runner: Callable[[Mapping[str, str], bool], int] = _run,
) -> int:
    if list(args) not in ([], ["--diverge"]):
        print("FAIL public-playbook: usage")
        return 2
    try:
        code = runner(environ, list(args) == ["--diverge"])
    except Exception as error:
        print("FAIL public-playbook: " + reason(error))
        return 1
    print(
        {0: "PASS public-playbook", 3: "PASS public-playbook: divergence detected"}.get(
            code, "FAIL public-playbook: comparison"
        )
    )
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
