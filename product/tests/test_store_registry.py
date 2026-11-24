"""Closed door, query headers and the packaged inventory."""

from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from product.tests.frames import raised_in
from store_live_controls import FIXTURE_DIR, FIXTURE_ID

from eii_product.store.embedded import EmbeddedStore
from eii_product.store.postgres import PostgresStore
from eii_product.store.protocol import EXACT_REASONS, StoreRefusal
from eii_product.store.registry import PACKAGED, QueryName, load_inventory

STORE = Path(__file__).resolve().parents[1] / "src" / "eii_product" / "store"
_POSTGIS_CATALOGUE = (
    "SELECT n.nspname FROM pg_catalog.pg_extension AS e "
    "JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace "
    "WHERE e.extname = 'postgis'"
)
DRIVERS = {"duckdb", "psycopg", "sqlglot"}
PLANES = {"eii_custodian", "eii_gateway", "scripts"}


def test_fetch_refuses_sql_text_and_unknown_names(tmp_path: Path) -> None:
    """SQL text, a bare name, an unknown name and a foreign member never reach a driver."""
    inventory = load_inventory(FIXTURE_DIR)
    other = tmp_path / "other"
    _query(
        other,
        "syn_other",
        _body("syn_other", "SELECT p.unit_id FROM control_rows AS p"),
    )
    foreign = load_inventory(other).lookup("syn_other")
    connection = _Recording()
    postgres = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
    embedded = _embedded(tmp_path, inventory)
    sent: list[str] = []
    embedded._connection = _Recorder(sent)
    sql_text = (FIXTURE_DIR / "control_rows.sql").read_text(encoding="utf-8")
    for store in (postgres, embedded):
        for query in (sql_text, "control_rows", "syn_missing", foreign):
            with pytest.raises(StoreRefusal) as caught:
                store.fetch(query, {"units": ["SYN-a"]})
            assert str(caught.value) == "unknown query"
            with pytest.raises(StoreRefusal) as planned:
                store.plan(query, {"units": ["SYN-a"]})
            assert str(planned.value) == "unknown query"
    assert connection.calls == [(_POSTGIS_CATALOGUE, None)]
    assert sent == []


def test_foreign_name_equal_to_a_real_one_is_refused(tmp_path: Path) -> None:
    """A second load of the same folder mints a different token for the same name."""
    inventory = load_inventory(FIXTURE_DIR)
    foreign = load_inventory(FIXTURE_DIR).lookup("control_rows")
    connection = _Recording()
    postgres = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
    embedded = _embedded(tmp_path, inventory)
    sent: list[str] = []
    embedded._connection = _Recorder(sent)
    assert foreign.name == "control_rows"
    for store in (postgres, embedded):
        with pytest.raises(StoreRefusal) as caught:
            store.fetch(foreign, {"units": ["SYN-a"]})
        assert str(caught.value) == "unknown query"
        with pytest.raises(StoreRefusal) as planned:
            store.plan(foreign, {"units": ["SYN-a"]})
        assert str(planned.value) == "unknown query"
    assert connection.calls == [(_POSTGIS_CATALOGUE, None)]
    assert sent == []


def test_query_name_is_final() -> None:
    """A subclass must not be able to mint a name. The type is marked final."""
    assert getattr(QueryName, "__final__", False) is True


def test_query_name_outside_the_loader_is_refused() -> None:
    """Only the loader may construct a query name."""
    with pytest.raises(StoreRefusal) as caught:
        QueryName("control_rows", object())
    assert str(caught.value) == "unknown query"


def test_lookup_of_an_unknown_name_is_refused() -> None:
    inventory = load_inventory(FIXTURE_DIR)
    with pytest.raises(StoreRefusal) as caught:
        inventory.lookup("syn_missing")
    assert str(caught.value) == "unknown query"


def test_refusal_messages_come_from_the_closed_list() -> None:
    """Every built reason is accepted, and an invented reason is refused."""
    for reason in EXACT_REASONS:
        assert str(StoreRefusal(reason)) == reason
    assert (
        str(StoreRefusal("field mismatch row=0 column=1"))
        == "field mismatch row=0 column=1"
    )
    prepared = "prepare failed query=control_rows engine=embedded"
    assert str(StoreRefusal(prepared)) == prepared
    with pytest.raises(ValueError):
        StoreRefusal("invented reason")


def test_store_import_loads_no_driver_and_no_parser(tmp_path: Path) -> None:
    """Importing the store loads no driver. A module that imports one fails the same check."""
    assert _drivers_loaded("eii_product.store", []) == []
    plant = tmp_path / "syn_driver_plant.py"
    plant.write_text("import duckdb\n", encoding="utf-8")
    assert _drivers_loaded("syn_driver_plant", [tmp_path]) == ["duckdb"]


def test_store_sources_import_no_other_plane(tmp_path: Path) -> None:
    """Store sources do not import the custodian, the gateway or scripts."""
    for path in sorted(STORE.glob("*.py")):
        assert imported_planes(path.read_text(encoding="utf-8")) == set()
    plant = tmp_path / "syn_plane.py"
    plant.write_text("import eii_custodian\n", encoding="utf-8")
    assert imported_planes(plant.read_text(encoding="utf-8")) == {"eii_custodian"}


def test_packaged_inventory_matches_its_query_files() -> None:
    """The inventory is the packaged folder. An empty folder is a count of zero, not a fixed tuple."""
    from eii_product.store.registry import packaged_sql_dir

    sql_count = len(list(packaged_sql_dir().glob("*.sql")))
    assert len(PACKAGED.queries) == sql_count
    assert len(PACKAGED.names) == sql_count


def test_missing_query_folder_is_refused(tmp_path: Path) -> None:
    """An absent folder, or one without a package marker, is not an empty success."""
    with pytest.raises(StoreRefusal) as missing:
        load_inventory(tmp_path / "missing")
    assert str(missing.value) == "query resources missing"
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(StoreRefusal) as unmarked:
        load_inventory(bare)
    assert str(unmarked.value) == "query resources missing"


def test_missing_header_line_is_refused(tmp_path: Path) -> None:
    _refuse_header(
        tmp_path, "syn_missing_header", "-- name: syn_missing_header\nSELECT 1\n"
    )


def test_extra_header_line_is_refused(tmp_path: Path) -> None:
    _refuse_header(
        tmp_path,
        "syn_extra_header",
        _header("syn_extra_header") + "-- order: unit_id\nSELECT 1\n",
    )


def test_repeated_header_line_is_refused(tmp_path: Path) -> None:
    text = (
        "-- name: syn_repeated_header\n-- name: syn_repeated_header\n"
        "-- returns: unit_id text\n-- order: unit_id\nSELECT 1\n"
    )
    _refuse_header(tmp_path, "syn_repeated_header", text)


def test_misplaced_header_line_is_refused(tmp_path: Path) -> None:
    text = (
        "-- params: units list[text]\n-- name: syn_misplaced_header\n"
        "-- returns: unit_id text\n-- order: unit_id\nSELECT 1\n"
    )
    _refuse_header(tmp_path, "syn_misplaced_header", text)


def test_header_name_differs_from_the_stem(tmp_path: Path) -> None:
    _refuse_header(tmp_path, "syn_stem", _header("syn_other") + "SELECT 1\n")


def test_two_files_with_one_name_are_refused(tmp_path: Path) -> None:
    folder = tmp_path / "dup"
    _query(
        folder, "syn_one", _body("syn_one", "SELECT p.unit_id FROM control_rows AS p")
    )
    _query(
        folder, "syn_two", _body("syn_one", "SELECT p.unit_id FROM control_rows AS p")
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(folder)
    assert str(caught.value) == "query header invalid"


def test_unknown_parameter_type_is_refused(tmp_path: Path) -> None:
    header = (
        "-- name: syn_bad_param\n-- params: units float\n"
        "-- returns: unit_id text\n-- order: unit_id\n"
    )
    _refuse_header(tmp_path, "syn_bad_param", header + "SELECT 1\n")


def test_boolean_return_type_is_refused(tmp_path: Path) -> None:
    header = "-- name: syn_bool\n-- params:\n-- returns: flag bool\n-- order: flag\n"
    _refuse_header(tmp_path, "syn_bool", header + "SELECT 1\n")


def test_sql_without_a_contract_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "bare_sql"
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / "syn_bare.sql").write_text(
        _body("syn_bare", "SELECT 1\n"), encoding="utf-8"
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(folder)
    assert str(caught.value) == "query header invalid"


def test_geometry_return_must_match_the_contract_column(tmp_path: Path) -> None:
    """A geometry return is tied to a geometry column, and the other way round."""
    _geometry_header(
        tmp_path / "tied",
        "shape geometry",
        'type = "geometry"',
    )
    inventory = load_inventory(tmp_path / "tied")
    assert inventory.get("syn_geom") is not None
    _geometry_header(tmp_path / "other", "shape text", 'type = "geometry"')
    with pytest.raises(StoreRefusal) as other:
        load_inventory(tmp_path / "other")
    assert str(other.value) == "query header invalid"
    _geometry_header(tmp_path / "missing", "shape geometry", 'type = "string"')
    with pytest.raises(StoreRefusal) as missing:
        load_inventory(tmp_path / "missing")
    assert str(missing.value) == "query header invalid"


def test_geometry_fit_accepts_only_the_pinned_text() -> None:
    from eii_product.store.registry import _fits

    pinned = "0101000000000000000000C03F000000000000D03F"
    assert _fits(pinned, "geometry") is True
    assert _fits(None, "geometry") is True
    assert _fits("01ab", "geometry") is False
    assert _fits("010", "geometry") is False
    assert _fits(pinned.lower(), "geometry") is False


def test_same_token_without_the_query_is_unknown() -> None:
    """A name minted for this token is unknown once the query list no longer holds it."""
    from eii_product.store.registry import Inventory, require_query

    inventory = load_inventory(FIXTURE_DIR)
    shrunk = Inventory((), inventory.token, inventory.names)
    with pytest.raises(StoreRefusal) as caught:
        require_query(shrunk, inventory.lookup("control_rows"))
    assert str(caught.value) == "unknown query"


def test_sample_of_an_unknown_parameter_type_is_refused() -> None:
    """sample_params refuses a type the header vocabulary does not name."""
    from eii_product.store.registry import (
        ParamSpec,
        QuerySpec,
        ReturnSpec,
        sample_params,
    )

    spec = QuerySpec(
        "syn_sample",
        (ParamSpec("n", "bytea"),),
        (ReturnSpec("unit_id", "text"),),
        ("unit_id",),
        "SELECT p.unit_id AS unit_id FROM control_rows AS p",
        "ab",
        (),
    )
    with pytest.raises(StoreRefusal) as caught:
        sample_params(spec)
    assert str(caught.value) == "parameter types invalid"


def test_missing_package_marker_on_the_resources_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """packaged_sql_dir turns a missing package into query resources missing."""
    from eii_product.store import registry

    def missing(name: str) -> object:
        del name
        raise ModuleNotFoundError

    monkeypatch.setattr(registry, "files", missing)
    with pytest.raises(StoreRefusal) as caught:
        registry.packaged_sql_dir()
    assert str(caught.value) == "query resources missing"


@pytest.mark.parametrize(
    ("label", "toml"),
    [
        (
            "select_word",
            '[[tables]]\nname = "control_rows"\n# select\nanchor = "invented control table"\nkey = []\n\n[[tables.columns]]\nname = "unit_id"\ntype = "string"\nnullable = false\n',
        ),
        ("broken_toml", "tables = [\n"),
        ("empty_tables", "tables = []\n"),
        ("table_not_a_dict", 'tables = ["syn"]\n'),
        (
            "bad_name",
            '[[tables]]\nname = "SYN"\nanchor = "invented control table"\nkey = []\n\n[[tables.columns]]\nname = "unit_id"\ntype = "string"\nnullable = false\n',
        ),
        (
            "blank_anchor",
            '[[tables]]\nname = "control_rows"\nanchor = ""\nkey = []\n\n[[tables.columns]]\nname = "unit_id"\ntype = "string"\nnullable = false\n',
        ),
        (
            "key_not_a_list",
            '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\nkey = 1\n\n[[tables.columns]]\nname = "unit_id"\ntype = "string"\nnullable = false\n',
        ),
        (
            "no_columns",
            '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\nkey = []\ncolumns = []\n',
        ),
        (
            "column_not_a_dict",
            '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\nkey = []\ncolumns = ["unit_id"]\n',
        ),
        (
            "nullable_not_bool",
            '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\nkey = []\n\n[[tables.columns]]\nname = "unit_id"\ntype = "string"\nnullable = "no"\n',
        ),
        (
            "key_not_a_column",
            '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\nkey = ["missing"]\n\n[[tables.columns]]\nname = "unit_id"\ntype = "string"\nnullable = false\n',
        ),
    ],
)
def test_contract_defect_is_query_header_invalid(
    tmp_path: Path, label: str, toml: str
) -> None:
    """Each contract guard refuses a file that fails only that guard."""
    root = tmp_path / label
    root.mkdir()
    (root / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (root / "syn_contract.sql").write_text(
        "-- name: syn_contract\n-- params:\n-- returns: unit_id text\n-- order: unit_id\n"
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST\n",
        encoding="utf-8",
    )
    (root / "syn_contract.toml").write_text(toml, encoding="utf-8")
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"


def test_text_column_is_not_wrapped_as_geometry(tmp_path: Path) -> None:
    """A text column is refused when the header calls it geometry."""
    root = tmp_path / "false_accept"
    _two_tables(
        root,
        "SELECT p.shape FROM control_text AS p ORDER BY p.shape ASC NULLS LAST\n",
        "shape geometry",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"


def test_own_scope_text_projection_is_not_tied_as_geometry(tmp_path: Path) -> None:
    """A text column is not geometry because a CTE reused its alias for one."""
    root = tmp_path / "text_outer"
    _scope_query(
        root,
        "WITH cover AS (SELECT g.unit_id AS unit_id FROM control_geom AS g) "
        "SELECT g.shape FROM control_text AS g ORDER BY g.shape ASC NULLS LAST\n",
        "shape geometry",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"


def test_own_scope_geometry_projection_is_tied_and_wrapped(tmp_path: Path) -> None:
    """A geometry column stays geometry when a CTE reuses its alias for text."""
    from eii_product.store.registry import bind

    root = tmp_path / "geom_outer"
    _scope_query(
        root,
        "WITH cover AS (SELECT g.unit_id AS unit_id FROM control_text AS g) "
        "SELECT g.shape FROM control_geom AS g ORDER BY g.shape ASC NULLS LAST\n",
        "shape geometry",
    )
    inventory = load_inventory(root)
    spec = inventory.get("syn_scope")
    assert spec is not None
    embedded, _bound = bind(spec, {}, "embedded")
    assert "ST_AsWKB" in embedded


def test_own_scope_duplicate_alias_is_not_tied_as_geometry(tmp_path: Path) -> None:
    """One select that uses alias g twice is not tied to the later geometry table."""
    root = tmp_path / "twice"
    _scope_query(
        root,
        "SELECT g.shape FROM control_text AS g "
        "INNER JOIN control_geom AS g ON g.unit_id = g.unit_id "
        "ORDER BY g.shape ASC NULLS LAST\n",
        "shape geometry",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"


def test_contract_cte_name_is_refused_before_the_tie(tmp_path: Path) -> None:
    """A CTE named as a contract table is refused before the geometry tie types it."""
    root = tmp_path / "contract_name"
    _scope_query(
        root,
        "WITH a AS (SELECT x.shape AS shape FROM control_geom AS x), "
        "control_geom AS (SELECT t.shape AS shape FROM control_text AS t) "
        "SELECT a.shape FROM a ORDER BY a.shape ASC NULLS LAST\n",
        "shape text",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"
    assert raised_in(caught, "_refuse_contract_cte")


def test_unquoted_contract_cte_case_is_refused_before_the_tie(tmp_path: Path) -> None:
    """An unquoted contract-table CTE in another case is refused before the tie."""
    root = tmp_path / "control_geom_case"
    _case_query(
        root,
        "WITH CONTROL_GEOM AS (SELECT t.unit_id AS unit_id FROM control_geom AS t) "
        "SELECT c.unit_id AS unit_id FROM CONTROL_GEOM AS c "
        "ORDER BY c.unit_id ASC NULLS LAST\n",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"
    assert raised_in(caught, "_refuse_non_lower_name")


def test_upper_case_table_reference_is_refused_before_the_tie(tmp_path: Path) -> None:
    """An upper-case table reference with no CTE is refused before the tie."""
    root = tmp_path / "plain_table_case"
    _case_query(
        root,
        "SELECT t.unit_id AS unit_id FROM CONTROL_TEXT AS t "
        "ORDER BY t.unit_id ASC NULLS LAST\n",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"
    assert raised_in(caught, "_refuse_non_lower_name")


def test_forward_cte_is_unresolved_in_the_tie(tmp_path: Path) -> None:
    """An earlier body cannot see a later sibling, so the tie does not type it."""
    root = tmp_path / "forward_name"
    _scope_query(
        root,
        "WITH earlier AS (SELECT x.shape AS shape FROM later_name AS x), "
        "later_name AS (SELECT t.shape AS shape FROM control_geom AS t) "
        "SELECT earlier.shape FROM earlier ORDER BY earlier.shape ASC NULLS LAST\n",
        "shape geometry",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"
    assert raised_in(caught, "_resolve")


def test_later_body_geometry_tie_uses_the_earlier_cte(tmp_path: Path) -> None:
    """A nested later sibling must not retype the shape read from an earlier CTE."""
    from eii_product.store.registry import bind

    root = tmp_path / "earlier_shape"
    _scope_query(
        root,
        "WITH earlier AS (SELECT g.shape AS shape FROM control_geom AS g), "
        "holder AS (WITH reader AS (SELECT e.shape AS shape FROM earlier AS e), "
        "earlier AS (SELECT t.shape AS shape FROM control_text AS t) "
        "SELECT reader.shape AS shape FROM reader) "
        "SELECT holder.shape FROM holder ORDER BY holder.shape ASC NULLS LAST\n",
        "shape geometry",
    )
    inventory = load_inventory(root)
    spec = inventory.get("syn_scope")
    assert spec is not None
    embedded, _bound = bind(spec, {}, "embedded")
    assert "ST_AsWKB" in embedded


def test_inner_cte_shadows_the_outer_name_in_the_tie(tmp_path: Path) -> None:
    """The nested query's shape is the inner CTE's text column, not a geometry."""
    from eii_product.store.registry import bind

    root = tmp_path / "inner_shape"
    _scope_query(
        root,
        "WITH outer_cte AS (SELECT t.shape AS shape FROM control_text AS t), "
        "holder AS (WITH outer_cte AS (SELECT x.shape AS shape FROM outer_cte AS x) "
        "SELECT y.shape AS shape FROM outer_cte AS y) "
        "SELECT holder.shape FROM holder ORDER BY holder.shape ASC NULLS LAST\n",
        "shape text",
    )
    inventory = load_inventory(root)
    spec = inventory.get("syn_scope")
    assert spec is not None
    embedded, _bound = bind(spec, {}, "embedded")
    assert "ST_AsWKB" not in embedded


def test_text_return_of_a_text_column_is_accepted(tmp_path: Path) -> None:
    """The same text column is accepted when the header calls it text."""
    from eii_product.store.lint import lint_inventory
    from eii_product.store.registry import bind

    root = tmp_path / "false_refuse"
    _two_tables(
        root,
        "SELECT p.shape FROM control_text AS p ORDER BY p.shape ASC NULLS LAST\n",
        "shape text",
    )
    inventory = load_inventory(root)
    lint_inventory(inventory)
    spec = inventory.get("syn_shape")
    assert spec is not None
    embedded, _bound = bind(spec, {}, "embedded")
    postgres, _bound = bind(spec, {}, "postgres", postgis_schema='"syn_gis"')
    assert "ST_AsWKB" not in embedded
    assert "ST_AsBinary" not in postgres


def test_geometry_wrap_plants(tmp_path: Path) -> None:
    """Direct bind reaches each geometry-text refusal on its own input."""
    from eii_product.store.registry import (
        ContractColumn,
        ContractTable,
        QuerySpec,
        ReturnSpec,
        bind,
    )

    table = ContractTable(
        "control_shape",
        "invented control table",
        ("shape_id",),
        (
            ContractColumn("shape_id", "string", False),
            ContractColumn("shape", "geometry", True),
        ),
    )
    plants = (
        (
            "SELECT g.shape, g.shape_id FROM control_shape AS g",
            "result columns invalid",
            ("shape",),
        ),
        (
            "SELECT shape FROM control_shape AS g",
            "forbidden construct",
            ("shape",),
        ),
        (
            "SELECT g.shape FROM control_shape AS g UNION ALL "
            "SELECT g.shape FROM control_shape AS g",
            "forbidden construct",
            ("shape",),
        ),
        (
            "SELECT g.shape",
            "forbidden construct",
            ("shape",),
        ),
    )
    for sql, reason, returns in plants:
        spec = QuerySpec(
            "syn_geom",
            (),
            tuple(ReturnSpec(name, "geometry") for name in returns),
            ("shape",),
            sql,
            "ab",
            (table,),
        )
        with pytest.raises(StoreRefusal) as caught:
            bind(spec, {}, "embedded")
        assert str(caught.value) == reason
    missing_schema = QuerySpec(
        "syn_geom",
        (),
        (ReturnSpec("shape", "geometry"),),
        ("shape",),
        "SELECT g.shape FROM control_shape AS g",
        "ab",
        (table,),
    )
    with pytest.raises(StoreRefusal) as caught:
        bind(missing_schema, {}, "postgres")
    assert str(caught.value) == "extension schema invalid"


def test_control_inventory_loads() -> None:
    """The control query is loaded from the fixture folder and is not packaged."""
    inventory = load_inventory(FIXTURE_DIR)
    assert tuple(query.name for query in inventory.queries) == (
        "control_rows",
        "control_shape",
    )
    assert inventory.lookup("control_rows").name == "control_rows"
    assert inventory.get("control_rows") is not None
    assert PACKAGED.get("control_rows") is None


def imported_planes(source: str) -> set[str]:
    """Return forbidden plane roots imported by this source."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            root = module.split(".", 1)[0]
            if root in PLANES:
                found.add(root)
    return found


def _drivers_loaded(module: str, extra: list[Path]) -> list[str]:
    code = (
        "import json, sys\n"
        "sys.path[:0] = sys.argv[2:]\n"
        "import importlib\n"
        "importlib.import_module(sys.argv[1])\n"
        "found = sorted({name.split('.', 1)[0] for name in sys.modules if name.split('.', 1)[0] in "
        + repr(sorted(DRIVERS))
        + "})\n"
        "print(json.dumps(found))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, module, *[str(path) for path in extra]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    import json

    loaded: list[str] = json.loads(proc.stdout)
    return loaded


def _refuse_header(folder: Path, name: str, text: str) -> None:
    root = folder / name
    root.mkdir()
    (root / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (root / f"{name}.sql").write_text(text, encoding="utf-8")
    (root / f"{name}.toml").write_text(_contract(), encoding="utf-8")
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"


def _query(folder: Path, name: str, body: str) -> None:
    folder.mkdir(exist_ok=True)
    marker = folder / "__init__.py"
    if not marker.exists():
        marker.write_text('"""marker"""\n', encoding="utf-8")
    (folder / f"{name}.sql").write_text(body, encoding="utf-8")
    (folder / f"{name}.toml").write_text(_contract(), encoding="utf-8")


def _header(name: str) -> str:
    return (
        f"-- name: {name}\n-- params: units list[text]\n"
        "-- returns: unit_id text\n-- order: unit_id\n"
    )


def _body(name: str, statement: str) -> str:
    return _header(name) + statement + "\nORDER BY p.unit_id ASC NULLS LAST\n"


def _geometry_header(folder: Path, returns: str, shape_type: str) -> None:
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / "syn_geom.sql").write_text(
        "-- name: syn_geom\n-- params:\n"
        f"-- returns: {returns}\n-- order: shape\n"
        "SELECT g.shape FROM control_shape AS g ORDER BY g.shape ASC NULLS LAST\n",
        encoding="utf-8",
    )
    (folder / "syn_geom.toml").write_text(
        '[[tables]]\nname = "control_shape"\nanchor = "invented control table"\n'
        'key = ["shape"]\n\n[[tables.columns]]\nname = "shape"\n'
        f"{shape_type}\nnullable = true\n",
        encoding="utf-8",
    )


def _case_query(folder: Path, body: str) -> None:
    """One text table and one geometry table, ordered by unit_id."""
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / "syn_scope.sql").write_text(
        "-- name: syn_scope\n-- params:\n"
        "-- returns: unit_id text\n-- order: unit_id\n" + body,
        encoding="utf-8",
    )
    (folder / "syn_scope.toml").write_text(
        '[[tables]]\nname = "control_text"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        'type = "string"\nnullable = false\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "string"\nnullable = true\n\n'
        '[[tables]]\nname = "control_geom"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        'type = "string"\nnullable = false\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "geometry"\nnullable = true\n',
        encoding="utf-8",
    )


def _scope_query(folder: Path, body: str, returns: str) -> None:
    """A text table and a geometry table, same column names, one statement."""
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / "syn_scope.sql").write_text(
        "-- name: syn_scope\n-- params:\n"
        f"-- returns: {returns}\n-- order: shape\n" + body,
        encoding="utf-8",
    )
    (folder / "syn_scope.toml").write_text(
        '[[tables]]\nname = "control_text"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        'type = "string"\nnullable = false\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "string"\nnullable = true\n\n'
        '[[tables]]\nname = "control_geom"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        'type = "string"\nnullable = false\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "geometry"\nnullable = true\n',
        encoding="utf-8",
    )


def _two_tables(folder: Path, body: str, returns: str) -> None:
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / "syn_shape.sql").write_text(
        "-- name: syn_shape\n-- params:\n"
        f"-- returns: {returns}\n-- order: shape\n" + body,
        encoding="utf-8",
    )
    (folder / "syn_shape.toml").write_text(
        '[[tables]]\nname = "control_text"\nanchor = "invented control table"\n'
        'key = ["shape"]\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "string"\nnullable = true\n\n'
        '[[tables]]\nname = "control_geom"\nanchor = "invented control table"\n'
        'key = ["shape"]\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "geometry"\nnullable = true\n',
        encoding="utf-8",
    )


def _contract() -> str:
    return (
        '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        'type = "string"\nnullable = false\n'
    )


def _embedded(folder: Path, inventory: object) -> EmbeddedStore:
    import duckdb

    from eii_product.store.registry import Inventory

    path = folder / "closed.duckdb"
    duckdb.connect(str(path)).close()
    assert isinstance(inventory, Inventory)
    return EmbeddedStore(path, FIXTURE_ID, inventory)


class _Recorder:
    def __init__(self, sent: list[str]) -> None:
        self.sent = sent

    def cursor(self) -> _Recorder:
        return self

    def execute(self, sql: str, params: object = None) -> None:
        del params
        self.sent.append(sql)

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    description = None

    def close(self) -> None:
        return None


class _Recording:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.autocommit = True

    def cursor(self) -> _Recording:
        return self

    def execute(self, sql: str, params: object = None) -> None:
        self.sql = sql
        self.calls.append((sql, params))

    def fetchone(self) -> tuple[object, ...] | None:
        if getattr(self, "sql", "") == _POSTGIS_CATALOGUE:
            return ("syn_gis",)
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    @property
    def description(self) -> Sequence[object] | None:
        return None

    def close(self) -> None:
        return None
