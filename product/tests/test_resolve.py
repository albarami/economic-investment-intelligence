"""resolve: six named queries, order, cap, statuses and the closed payload."""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest
from product.tests.make_area_support import (
    MUNICIPALITIES,
    ORIGIN,
    OUTSIDE,
    RELEASE_ID,
    _geometry_hex,
    _wkt,
    geometry_rows,
)
from product.tests.test_make_area_parity import JOINED_INVENTORY, every_registered_run

from eii_product.store.embedded import EmbeddedStore
from eii_product.store.parity import run_parity
from eii_product.store.protocol import QueryResult, StoreHealth
from eii_product.store.registry import PACKAGED, packaged_sql_dir, require_query
from eii_product.tools.make_area import QUERY_NAMES as MAKE_AREA_QUERIES
from eii_product.tools.registry import (
    resolve_parity_cases,
    sector_facts_descriptor,
)
from eii_product.tools.resolve import (
    QUERY_NAMES,
    PayloadError,
    ResolveContext,
    ResolveResult,
    load_index,
    require_candidate,
    resolve,
)


class Rows:
    """Hand-made rows. The engine name is an argument so two stores can differ."""

    def __init__(self, rows: dict[str, tuple], engine: str = "embedded") -> None:
        self.engine = engine
        self.release_id = RELEASE_ID
        self.calls: list[str] = []
        self._rows = rows

    def fetch(self, query: object, params: object) -> QueryResult:
        spec = require_query(PACKAGED, query)
        self.calls.append(spec.name)
        rows = self._rows[spec.name]
        if spec.name == "make_area_gazetteer_point":
            key = params["place_key"]
            rows = tuple(row for row in rows if row[0] == key)
        return QueryResult(tuple(item.name for item in spec.returns), rows)

    def ping(self, timeout_s: float) -> StoreHealth:
        del timeout_s
        return StoreHealth(ok=True)

    def close(self) -> None:
        return None


def _land() -> tuple:
    return tuple((row["code"], _geometry_hex(row)) for row in MUNICIPALITIES)


def _empty() -> dict[str, tuple]:
    return {
        "resolve_gazetteer": (),
        "resolve_district": (("SYN-d1", "SYN-district", "SYN-district"),),
        "resolve_zone": (("SYN-z1", "SYN-zone", "SYN-zone"),),
        "resolve_municipality": _land(),
        "resolve_graph_node": (),
        "resolve_graph_edge": (),
    }


def _place(
    key: str,
    name_en: str,
    name_ar: str = "",
    aliases: str | None = None,
    lon: Decimal | None = ORIGIN[1],
    lat: Decimal | None = ORIGIN[0],
    cell: int | None = 1,
) -> tuple:
    return (key, "locality", name_en, name_ar, aliases, lon, lat, cell)


def _request(text: str, lang: str = "en", kind: str = "place") -> dict[str, object]:
    return {"text": text, "lang": lang, "kind": kind}


def _run(rows: dict[str, tuple], request: dict[str, object]):
    store = Rows(rows)
    result = resolve(store, request, ResolveContext(PACKAGED))
    return store, result


def _keys(result) -> list[str]:
    assert result.payload is not None
    return [item["key"] for item in result.payload["candidates"]]


def _place_candidate(key: str = "SYN-p") -> dict[str, object]:
    return {
        "kind": "place",
        "key": key,
        "label_en": "SYN-label",
        "label_ar": "SYN-label",
        "source": "gazetteer",
        "match": "exact",
    }


def _activity_candidate() -> dict[str, object]:
    return {
        "kind": "activity",
        "key": "activity:SYN-it",
        "label_en": "Italian restaurant",
        "label_ar": "Italian restaurant",
        "source": "activity_spine",
        "match": "exact",
        "commerce_code": "SYN-4",
        "isic_class": "SYN-isic",
        "place_category": "SYN-cat-a",
        "not_mappable": False,
    }


def _spine(mapped: bool = True) -> tuple[tuple, tuple]:
    nodes = [
        (
            "activity:SYN-it",
            "activity",
            "SYN-it",
            "Italian restaurant",
            "Italian restaurant",
        ),
        (
            "activity_class:SYN-isic",
            "activity_class",
            "SYN-isic",
            "SYN-class-label-only",
            "SYN-class-label-only",
        ),
        ("place_category:SYN-cat-b", "place_category", "SYN-cat-b", "", ""),
        ("place_category:SYN-cat-a", "place_category", "SYN-cat-a", "", ""),
        (
            "activity_class:UNMAPPABLE",
            "activity_class",
            "UNMAPPABLE",
            "UNMAPPABLE",
            "",
        ),
    ]
    edges = [
        (
            "classified_as:SYN-it",
            "classified_as",
            "activity:SYN-it",
            "activity_class:SYN-isic",
        ),
        (
            "listed_as:SYN-b",
            "listed_as",
            "activity_class:SYN-isic",
            "place_category:SYN-cat-b",
        ),
        (
            "listed_as:SYN-a",
            "listed_as",
            "activity_class:SYN-isic",
            "place_category:SYN-cat-a",
        ),
    ]
    if not mapped:
        edges[0] = (
            "classified_as:SYN-it",
            "classified_as",
            "activity:SYN-it",
            "activity_class:UNMAPPABLE",
        )
    statuses = (
        "unreviewed",
        "not_mappable_legacy",
        "not_mappable_invalid_prefix",
        "not_mappable_rejected",
    )
    for status in statuses:
        nodes.append(
            (f"activity:SYN-{status}", "activity", f"SYN-{status}", status, status)
        )
        edges.append(
            (
                f"classified_as:SYN-{status}",
                "classified_as",
                f"activity:SYN-{status}",
                "activity_class:UNMAPPABLE",
            )
        )
    return tuple(nodes), tuple(edges)


def test_six_queries_are_read_once_and_name_no_public_place() -> None:
    rows = _empty()
    rows["resolve_gazetteer"] = (_place("SYN-p", "SYN-label"),)
    store, result = _run(rows, _request("SYN-label"))
    assert store.calls == list(QUERY_NAMES)
    assert result.status == "OK"
    again = Rows(rows)
    context = ResolveContext(PACKAGED)
    resolve(again, _request("SYN-label"), context)
    resolve(again, _request("SYN-label"), context)
    assert again.calls == list(QUERY_NAMES)
    tables: set[str] = set()
    for name in QUERY_NAMES:
        spec = PACKAGED.get(name)
        assert spec is not None
        for table in spec.tables:
            tables.add(table.name)
            assert "pub_place" not in table.name
    assert tables == {
        "gazetteer",
        "district",
        "zone",
        "municipality",
        "graph_node",
        "graph_edge",
    }
    for path in packaged_sql_dir().glob("resolve_*"):
        assert "pub_place" not in path.read_text(encoding="utf-8")
    packaged = {query.name for query in PACKAGED.queries}
    assert sector_facts_descriptor().queries
    from eii_product.tools.registry import (
        public_card_descriptors,
        public_layer_descriptors,
        public_transport_queries,
    )

    public_reads = {
        query
        for descriptor in (*public_layer_descriptors(), *public_card_descriptors(None))
        for query in descriptor.queries
    }
    assert packaged == set(MAKE_AREA_QUERIES) | set(QUERY_NAMES) | set(
        sector_facts_descriptor().queries
    ) | {
        query.name
        for query in PACKAGED.queries
        if query.name.startswith("scan_places_")
    } | public_reads | set(public_transport_queries()) | {
        # S3-P10 (L-1509): the served register file's release-listed hash.
        "release_fc_register_sha256"
    }


def test_order_cap_and_a_second_call_keep_the_same_rank() -> None:
    rows = _empty()
    nodes, edges = _spine()
    rows["resolve_graph_node"] = nodes
    rows["resolve_graph_edge"] = edges
    rows["resolve_gazetteer"] = (
        _place("SYN-z", "Lusail"),
        _place("SYN-a", "lusail"),
    )
    _store, result = _run(rows, _request("Lusail", kind="both"))
    assert _keys(result)[:2] == ["SYN-z", "SYN-a"]
    assert result.payload["candidates"][0]["match"] == "exact"
    assert result.payload["candidates"][1]["match"] == "normalised"
    crowded = _empty()
    crowded["resolve_gazetteer"] = tuple(
        _place(f"SYN-{name}", "SYN-crowd") for name in ("f", "e", "d", "c", "b", "a")
    )
    forward, first = _run(crowded, _request("SYN-crowd"))
    backward = _empty()
    backward["resolve_gazetteer"] = tuple(reversed(crowded["resolve_gazetteer"]))
    _store, second = _run(backward, _request("SYN-crowd"))
    assert _keys(first) == ["SYN-a", "SYN-b", "SYN-c", "SYN-d", "SYN-e"]
    assert _keys(second) == _keys(first)
    assert len(first.payload["candidates"]) == 5
    del forward


def test_place_ranks_before_activity_at_the_same_match() -> None:
    rows = _empty()
    nodes, edges = _spine()
    rows["resolve_graph_node"] = (
        *nodes,
        ("activity:SYN-a", "activity", "SYN-a", "SYN-shared", "SYN-shared"),
    )
    rows["resolve_graph_edge"] = (
        *edges,
        (
            "classified_as:SYN-a",
            "classified_as",
            "activity:SYN-a",
            "activity_class:SYN-isic",
        ),
    )
    rows["resolve_gazetteer"] = (_place("SYN-z", "SYN-shared"),)
    _store, result = _run(rows, _request("SYN-shared", kind="both"))
    assert result.payload["candidates"][0]["kind"] == "place"


def test_lang_does_not_filter_and_aliases_match() -> None:
    rows = _empty()
    rows["resolve_gazetteer"] = (
        _place("SYN-en", "SYN-en-only", "SYN-ar-only", "SYN-alias-one; SYN-alias-two"),
    )
    _store, english = _run(rows, _request("SYN-ar-only", lang="en"))
    _store, arabic = _run(rows, _request("SYN-en-only", lang="ar"))
    _store, alias = _run(rows, _request("SYN-alias-two", lang="ar"))
    assert _keys(english) == _keys(arabic) == _keys(alias) == ["SYN-en"]


def test_an_activity_matches_its_labels_and_not_its_class() -> None:
    rows = _empty()
    nodes, edges = _spine()
    rows["resolve_graph_node"] = nodes
    rows["resolve_graph_edge"] = edges
    _store, found = _run(rows, _request("Italian restaurant", kind="activity"))
    assert found.status == "OK"
    candidate = found.payload["candidates"][0]
    assert candidate["source"] == "activity_spine"
    assert candidate["commerce_code"] == "SYN-it"
    assert candidate["isic_class"] == "SYN-isic"
    assert candidate["place_category"] == "SYN-cat-a"
    assert candidate["not_mappable"] is False
    _store, missed = _run(rows, _request("SYN-class-label-only", kind="activity"))
    assert missed.status == "NO_DATA"


def test_each_unmapped_status_stays_visible() -> None:
    rows = _empty()
    nodes, edges = _spine()
    rows["resolve_graph_node"] = nodes
    rows["resolve_graph_edge"] = edges
    for status in (
        "unreviewed",
        "not_mappable_legacy",
        "not_mappable_invalid_prefix",
        "not_mappable_rejected",
    ):
        _store, result = _run(rows, _request(status, kind="activity"))
        assert result.status == "OK"
        candidate = result.payload["candidates"][0]
        assert candidate["not_mappable"] is True
        assert candidate["commerce_code"] == f"SYN-{status}"
        assert candidate["isic_class"] == ""
        assert candidate["place_category"] == ""


def test_outside_null_cell_and_missing_coordinates() -> None:
    inside = _empty()
    inside["resolve_gazetteer"] = (
        _place("SYN-in", "SYN-in", cell=None),
        _place("SYN-out", "SYN-out", lon=OUTSIDE[1], lat=OUTSIDE[0]),
    )
    _store, kept = _run(inside, _request("SYN-in"))
    assert kept.status == "OK"
    assert _keys(kept) == ["SYN-in"]
    outside = _empty()
    outside["resolve_gazetteer"] = (
        _place("SYN-out", "SYN-out", lon=OUTSIDE[1], lat=OUTSIDE[0]),
    )
    _store, scope = _run(outside, _request("SYN-out"))
    assert scope.status == "OUT_OF_SCOPE"
    assert scope.payload is None
    missing = _empty()
    missing["resolve_gazetteer"] = (
        _place("SYN-missing", "SYN-missing", lon=None, lat=None),
    )
    _store, nowhere = _run(missing, _request("SYN-missing"))
    assert nowhere.status == "NO_DATA"
    _store, absent = _run(_empty(), _request("SYN-absent"))
    assert absent.status == "NO_DATA"


def test_a_bad_request_reads_nothing_and_the_payload_is_closed() -> None:
    store = Rows(_empty())
    result = resolve(store, {"text": "SYN-label"}, ResolveContext(PACKAGED))
    assert result.status == "INVALID_ARGUMENT"
    assert result.payload is None
    assert store.calls == []
    assert (
        dataclasses.fields(ResolveResult)
        and "facts" not in ResolveResult.__dataclass_fields__
    )
    require_candidate(_activity_candidate())
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "score": "1"})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "label_en": 1})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "label_en": Decimal("1.5")})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "source": "pub_place"})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "kind": "company"})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "key": "register:SYN-co"})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "key": "1" * 8})
    with pytest.raises(PayloadError):
        require_candidate({**_place_candidate(), "key": "2" * 11})
    rows = _empty()
    rows["resolve_gazetteer"] = (_place("register:SYN-co", "SYN-reg"),)
    _store, refused = _run(rows, _request("SYN-reg"))
    assert refused.status == "INVALID_ARGUMENT"
    assert refused.payload is None


def test_parity_strings_agree_on_two_memory_engines() -> None:
    rows = _empty()
    rows.update(geometry_rows())
    nodes, edges = _spine()
    rows["resolve_gazetteer"] = (_place("SYN-lusail", "Lusail", "Lusail"),)
    rows["resolve_graph_node"] = nodes
    rows["resolve_graph_edge"] = edges
    left = Rows(rows, "embedded")
    right = Rows(rows, "postgres")
    payloads: list[bytes] = []
    result = run_parity(
        (left, right),
        *every_registered_run([], payloads),
        JOINED_INVENTORY,
        unit_precision={},
        round_fact=_refuse_round,
    )
    assert result.coverage.passed is True
    assert len(payloads) == 8
    assert payloads[0::2] == payloads[1::2]
    names = {query.name for query in JOINED_INVENTORY.queries}
    assert set(result.traces["embedded"]) == names == set(result.traces["postgres"])
    texts = [item.decode("utf-8") for item in payloads]
    assert all('"Lusail"' in text or '"Italian restaurant"' in text for text in texts)
    cases = resolve_parity_cases()
    assert [case.inputs[0][1] for case in cases] == [
        "Lusail",
        "Lusail",
        "Italian restaurant",
        "Italian restaurant",
    ]
    assert [case.inputs[1][1] for case in cases] == ["en", "ar", "en", "ar"]


def test_named_sql_runs_on_the_embedded_store(tmp_path: Path) -> None:
    path = tmp_path / "resolve.duckdb"
    _write(path)
    store = EmbeddedStore(path, RELEASE_ID, PACKAGED)
    try:
        index = load_index(store, PACKAGED)
        result = resolve(
            store, _request("Lusail", kind="both"), ResolveContext(PACKAGED)
        )
        activity = resolve(
            store,
            _request("Italian restaurant", kind="activity"),
            ResolveContext(PACKAGED),
        )
    finally:
        store.close()
    assert index.districts[0][0] == "SYN-d1"
    assert index.zones[0][0] == "SYN-z1"
    assert result.status == "OK"
    assert _keys(result) == ["SYN-lusail"]
    assert activity.status == "OK"
    assert activity.payload["candidates"][0]["commerce_code"] == "SYN-it"


def _refuse_round(value: object, places: int) -> object:
    del value, places
    raise AssertionError("round_fact called")


def _write(path: Path) -> None:
    import duckdb

    connection = duckdb.connect(str(path))
    connection.execute(
        "CREATE TABLE gazetteer ("
        "place_key VARCHAR, kind VARCHAR, name_en VARCHAR, name_ar VARCHAR, "
        "aliases VARCHAR, lon DECIMAL(9,6), lat DECIMAL(9,6), cell BIGINT)"
    )
    connection.execute(
        "CREATE TABLE district (district_key VARCHAR, name_en VARCHAR, name_ar VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE zone (zone_code VARCHAR, name_en VARCHAR, name_ar VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE municipality (municipality_code VARCHAR, geometry GEOMETRY)"
    )
    connection.execute(
        "CREATE TABLE graph_node ("
        "node_id VARCHAR, node_type VARCHAR, code VARCHAR, label_en VARCHAR, label_ar VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE graph_edge ("
        "edge_id VARCHAR, edge_type VARCHAR, from_node_id VARCHAR, to_node_id VARCHAR)"
    )
    connection.execute(
        "INSERT INTO gazetteer VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ["SYN-lusail", "locality", "Lusail", "Lusail", None, "0", "0", None],
    )
    connection.execute(
        "INSERT INTO district VALUES ('SYN-d1', 'SYN-district', 'SYN-district')"
    )
    connection.execute("INSERT INTO zone VALUES ('SYN-z1', 'SYN-zone', 'SYN-zone')")
    for row in MUNICIPALITIES:
        connection.execute(
            "INSERT INTO municipality VALUES (?, ?::GEOMETRY)",
            [row["code"], _wkt(row)],
        )
    nodes, edges = _spine()
    connection.executemany("INSERT INTO graph_node VALUES (?, ?, ?, ?, ?)", list(nodes))
    connection.executemany("INSERT INTO graph_edge VALUES (?, ?, ?, ?)", list(edges))
    connection.close()


# S3-T03 box 3: every returned numeral is a fact value. The resolver returns
# no fact, so no numeral may appear in a returned value except inside an
# identifier: a key, a register or classification code (commerce_code,
# isic_class, place_category), the release identity, and the digits of a
# place's proper name in its label fields (lead ruling recorded in
# OPEN_ITEMS.md for this package). Any other numeral is refused.

_NUMERAL_CATEGORIES = frozenset({"Nd", "Nl", "No"})
_IDENTIFIER_LEAVES = {
    "place": frozenset({"key", "label_en", "label_ar"}),
    "activity": frozenset({"key", "commerce_code", "isic_class", "place_category"}),
}


def _has_numeral(value: str) -> bool:
    import unicodedata

    return any(unicodedata.category(char) in _NUMERAL_CATEGORIES for char in value)


def _walk(value: object, path: tuple[str, ...], kind: str | None, seen: list) -> None:
    if isinstance(value, dict):
        own = value.get("kind") if isinstance(value.get("kind"), str) else kind
        for name, item in value.items():
            _walk(item, (*path, str(name)), own, seen)
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk(item, (*path, str(index)), kind, seen)
        return
    seen.append((path, kind, value))


def _returned_values(result: ResolveResult) -> list:
    seen: list = []
    _walk(dataclasses.asdict(result), (), None, seen)
    return seen


def _assert_no_free_numeral(result: ResolveResult) -> int:
    walked = _returned_values(result)
    for path, kind, value in walked:
        leaf = path[-1]
        if value is None:
            continue
        if type(value) is bool:
            assert leaf == "not_mappable", path
            continue
        assert type(value) is str, (path, type(value))
        if not _has_numeral(value):
            continue
        if path == ("release_id",):
            continue
        assert kind is not None and leaf in _IDENTIFIER_LEAVES[kind], path
    return len(walked)


def _numbered_rows() -> dict[str, tuple]:
    rows = _empty()
    nodes, edges = _spine()
    rows["resolve_graph_node"] = (
        *nodes,
        ("activity:SYN-47", "activity", "SYN-4711", "SYN-shared", "SYN-shared"),
    )
    rows["resolve_graph_edge"] = (
        *edges,
        (
            "classified_as:SYN-47",
            "classified_as",
            "activity:SYN-47",
            "activity_class:SYN-isic",
        ),
    )
    rows["resolve_gazetteer"] = (
        _place("SYN-p9", "SYN-shared", "SYN-shared"),
        _place("SYN-p10", "SYN-Street 9", "SYN-شارع ٩"),
    )
    return rows


def test_every_returned_value_is_walked_and_holds_no_free_numeral() -> None:
    rows = _numbered_rows()
    results = [
        _run(rows, _request("SYN-shared", kind="both"))[1],
        _run(rows, _request("SYN-Street 9"))[1],
        _run(rows, _request("SYN-شارع ٩", lang="ar"))[1],
        _run(rows, _request("Italian restaurant", kind="activity"))[1],
        _run(rows, _request("SYN-nothing", kind="both"))[1],
    ]
    assert [item.status for item in results] == ["OK", "OK", "OK", "OK", "NO_DATA"]
    walked = sum(_assert_no_free_numeral(item) for item in results)
    leaves = {path[-1] for item in results for path, _k, _v in _returned_values(item)}
    assert {
        "tool",
        "status",
        "reason",
        "release_id",
        "kind",
        "key",
        "label_en",
        "label_ar",
        "source",
        "match",
        "commerce_code",
        "isic_class",
        "place_category",
        "not_mappable",
    } <= leaves
    assert walked > 40


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commerce_code", 4711),
        ("isic_class", Decimal("47.11")),
        ("place_category", 2.5),
        ("label_en", 12),
        ("not_mappable", 0),
        ("key", 7),
    ],
)
def test_a_numeric_typed_field_is_refused(field: str, value: object) -> None:
    with pytest.raises(PayloadError):
        require_candidate({**_activity_candidate(), field: value})


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        ("activity", "label_en", "Italian restaurant 24"),
        ("activity", "label_ar", "مطعم ٢٤"),
        ("activity", "label_en", "Italian restaurant ½"),
        ("activity", "label_en", "Italian restaurant Ⅳ"),
        ("activity", "label_en", "Italian restaurant ۳"),
    ],
)
def test_a_non_fact_numeral_in_a_returned_value_is_refused(
    kind: str, field: str, value: str
) -> None:
    candidate = _activity_candidate() if kind == "activity" else _place_candidate()
    with pytest.raises(PayloadError):
        require_candidate({**candidate, field: value})


def test_identifier_digits_stay_allowed_only_in_their_named_fields() -> None:
    require_candidate({**_activity_candidate(), "commerce_code": "SYN-4711"})
    require_candidate({**_activity_candidate(), "isic_class": "SYN-5610"})
    require_candidate({**_activity_candidate(), "place_category": "SYN-cat-2"})
    require_candidate({**_activity_candidate(), "key": "activity:SYN-47"})
    require_candidate({**_place_candidate(), "label_en": "SYN-Street 9"})
    require_candidate({**_place_candidate(), "label_ar": "SYN-شارع ٩"})
    with pytest.raises(PayloadError):
        require_candidate({**_activity_candidate(), "label_en": "SYN-4711"})


def test_a_planted_numeral_label_refuses_the_whole_result() -> None:
    rows = _empty()
    nodes, edges = _spine()
    rows["resolve_graph_node"] = (
        *nodes,
        ("activity:SYN-n", "activity", "SYN-n", "SYN-shop 24", "SYN-shop 24"),
    )
    rows["resolve_graph_edge"] = (
        *edges,
        (
            "classified_as:SYN-n",
            "classified_as",
            "activity:SYN-n",
            "activity_class:SYN-isic",
        ),
    )
    _store, result = _run(rows, _request("SYN-shop 24", kind="activity"))
    assert result.status == "INVALID_ARGUMENT"
    assert result.payload is None
