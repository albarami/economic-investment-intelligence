"""Read-only adapters, binding and result checks. PostgreSQL is a recording stand-in."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from product.tests.frames import raised_in
from store_live_controls import (
    COLUMNS,
    DUCK_CREATE,
    DUCK_INSERT,
    FIXTURE_DIR,
    FIXTURE_ID,
    ROWS,
    expected,
    units,
)

from eii_product.store.embedded import EmbeddedStore
from eii_product.store.parity import prepare_all
from eii_product.store.postgres import (
    PostgresStore,
    control_schema,
    release_schema,
    require_control_schema_name,
    require_identity,
)
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import bind, load_inventory, translate

INVENTORY = load_inventory(FIXTURE_DIR)
MEMBER = INVENTORY.lookup("control_rows")
SECRET = "SYN-secret-token"
POSTGIS_CATALOGUE = (
    "SELECT n.nspname FROM pg_catalog.pg_extension AS e "
    "JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace "
    "WHERE e.extname = 'postgis'"
)
_GEOMETRY_BODY = (
    "SELECT g.shape_id, g.shape\n"
    "FROM control_shape AS g\n"
    "ORDER BY g.shape_id ASC NULLS LAST"
)
_BARE_GEOMETRY = (
    "SELECT g.shape_id, upper(encode(ST_AsBinary(g.shape, 'NDR'), 'hex')) AS shape\n"
    "FROM control_shape AS g\n"
    "ORDER BY g.shape_id ASC NULLS LAST"
)


def test_control_query_returns_the_expected_rows(tmp_path: Path) -> None:
    store = _duck(tmp_path)
    assert store.fetch(MEMBER, {"units": units()}) == expected(units())
    assert store.fetch(MEMBER, {"units": []}).rows == ()
    assert store.fetch(MEMBER, {"units": ["SYN-b"]}) == expected(["SYN-b"])


def test_external_read_is_refused_after_open(tmp_path: Path) -> None:
    """A file the test can read with external access on is refused by the adapter."""
    import duckdb

    source = tmp_path / "syn_read.csv"
    source.write_text("syn_value\nSYN-ok\n", encoding="utf-8")
    statement = f"SELECT syn_value FROM read_csv('{source.as_posix()}')"
    proof = duckdb.connect()
    assert proof.execute(statement).fetchall() == [("SYN-ok",)]
    proof.close()
    store = _duck(tmp_path)
    connection = store._connection
    assert connection is not None
    with pytest.raises(duckdb.Error):
        connection.execute(statement)


def test_embedded_blank_description_is_refused(tmp_path: Path) -> None:
    """A cursor with no description is refused before rows are read."""
    store = _duck(tmp_path)
    store._connection = _StandIn(fail=False, blank=True)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "result description missing"


def test_embedded_driver_error_is_engine_operation_failed(tmp_path: Path) -> None:
    """A driver error on fetch is engine operation failed and hides the driver text."""
    store = _duck(tmp_path)
    store._connection = _StandIn(fail=True, blank=False)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "engine operation failed"
    assert "SYN-driver" not in str(caught.value)


def test_closed_embedded_store_is_unavailable(tmp_path: Path) -> None:
    """Fetch after close is refused because the connection is gone."""
    store = _duck(tmp_path)
    store.close()
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "STORE_UNAVAILABLE"


def test_insert_external_access_and_load_are_refused(tmp_path: Path) -> None:
    import duckdb

    store = _duck(tmp_path)
    connection = store._connection
    assert connection is not None
    with pytest.raises(duckdb.Error):
        connection.execute(
            "INSERT INTO control_rows VALUES ('SYN-z', 'SYN-z', DATE '2000-01-04', 1, NULL)"
        )
    with pytest.raises(duckdb.Error):
        connection.execute("SET enable_external_access = true")
    with pytest.raises(duckdb.Error):
        connection.execute("LOAD spatial")
    assert len(store.fetch(MEMBER, {"units": units()}).rows) == 3


def test_two_threads_each_receive_every_row(tmp_path: Path) -> None:
    store = _duck(tmp_path)
    found: list[object] = []

    def read() -> None:
        found.append(store.fetch(MEMBER, {"units": units()}))

    threads = [threading.Thread(target=read) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert found == [expected(units()), expected(units())]


def test_postgres_read_runs_inside_one_read_only_transaction() -> None:
    connection = _Script()
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    assert store.fetch(MEMBER, {"units": ["SYN-a"]}) == expected(["SYN-a"])
    schema = control_schema(FIXTURE_ID)
    query = translate(
        (FIXTURE_DIR / "control_rows.sql")
        .read_text(encoding="utf-8")
        .split("\n", 4)[4],
        "postgres",
    )
    assert connection.calls == [
        (POSTGIS_CATALOGUE, None),
        ("BEGIN READ ONLY", None),
        ("SELECT set_config('search_path', %s, true)", (schema,)),
        (query.strip(), {"units": ["SYN-a"]}),
        ("COMMIT", None),
    ]


def test_configuration_is_locked_after_open(tmp_path: Path) -> None:
    """A setting that is legal before the lock is refused once the file is open."""
    import duckdb

    store = _duck(tmp_path)
    connection = store._connection
    assert connection is not None
    with pytest.raises(duckdb.Error) as caught:
        connection.execute("SET threads = 1")
    assert "configuration has been locked" in str(caught.value)


def test_autocommit_flipped_after_open_sends_nothing() -> None:
    """A connection flipped after open is refused before any statement of that call."""
    connection = _Script()
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    connection.autocommit = False
    before = list(connection.calls)
    with pytest.raises(StoreRefusal) as fetched:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(fetched.value) == "engine operation failed"
    with pytest.raises(StoreRefusal) as planned:
        store.plan(MEMBER, {"units": ["SYN-a"]})
    assert str(planned.value) == "engine operation failed"
    with pytest.raises(StoreRefusal) as pinged:
        store.ping(1)
    assert str(pinged.value) == "engine operation failed"
    assert connection.calls == before


def test_postgres_ping_failure_is_unavailable() -> None:
    """A failed ping statement is STORE_UNAVAILABLE and carries no driver text."""
    connection = _Script(fail_sql="SELECT 1")
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.ping(1)
    assert str(caught.value) == "STORE_UNAVAILABLE"
    assert SECRET not in str(caught.value)


def test_postgis_catalogue_driver_failure_is_engine_operation_failed() -> None:
    """A driver error while reading the extension schema is not an empty catalogue."""
    connection = _Script(fail_sql="pg_extension")
    with pytest.raises(StoreRefusal) as caught:
        PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    assert str(caught.value) == "engine operation failed"
    assert SECRET not in str(caught.value)
    assert raised_in(caught, "_read_postgis_schema")


def test_postgres_column_name_must_be_text() -> None:
    """A description whose name is not text is refused in the adapter."""
    connection = _Script(name_values=(1,))
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "result columns invalid"
    assert raised_in(caught, "_column_name")


def test_postgres_refuses_a_connection_that_is_not_autocommit() -> None:
    connection = _Script()
    connection.autocommit = False
    with pytest.raises(StoreRefusal) as caught:
        PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    assert str(caught.value) == "engine operation failed"
    assert connection.calls == []
    with pytest.raises(StoreRefusal) as caught:
        PostgresStore(connection, FIXTURE_ID, INVENTORY)
    assert str(caught.value) == "engine operation failed"
    assert connection.calls == []


def test_translate_does_not_rewrite_a_quoted_identifier() -> None:
    """A colon-name inside quotes is not a placeholder. The lint refuses the query."""
    quoted = 'SELECT ":label" AS label'
    assert translate(quoted, "postgres") == quoted
    assert translate(quoted, "embedded") == quoted


def test_wrong_returned_schema_never_runs_the_query() -> None:
    connection = _Script(returned_schema="r_notthisone0000")
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "engine operation failed"
    assert all("control_rows" not in sql for sql, _params in connection.calls)


def test_failing_set_config_never_runs_the_query() -> None:
    connection = _Script(fail_sql="set_config")
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "engine operation failed"
    assert all("control_rows" not in sql for sql, _params in connection.calls)


def test_parameter_type_plants() -> None:
    """A value of the wrong Python type is a type refusal, not a name refusal."""
    spec = INVENTORY.get("control_rows")
    assert spec is not None
    plants: tuple[dict[str, object], ...] = (
        {"units": True},
        {"units": datetime(2000, 1, 1, 0, 0)},
        {"units": ["SYN-a", 1]},
        {"units": None},
    )
    for params in plants:
        with pytest.raises(StoreRefusal) as caught:
            bind(spec, params, "embedded")
        assert str(caught.value) == "parameter types invalid"


def test_parameter_name_plants() -> None:
    """A missing or extra name is a name refusal, not a type refusal."""
    spec = INVENTORY.get("control_rows")
    assert spec is not None
    plants: tuple[dict[str, object], ...] = (
        {},
        {"units": ["SYN-a"], "extra": "SYN-a"},
    )
    for params in plants:
        with pytest.raises(StoreRefusal) as caught:
            bind(spec, params, "embedded")
        assert str(caught.value) == "parameter names invalid"


def test_date_parameter_rejects_datetime(tmp_path: Path) -> None:
    folder = tmp_path / "dated"
    _write(
        folder,
        "syn_dated",
        "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.period = :on_day ORDER BY p.unit_id ASC NULLS LAST",
        "on_day date",
    )
    inventory = load_inventory(folder)
    spec = inventory.get("syn_dated")
    assert spec is not None
    with pytest.raises(StoreRefusal) as caught:
        bind(spec, {"on_day": datetime(2000, 1, 1)}, "embedded")
    assert str(caught.value) == "parameter types invalid"
    store = EmbeddedStore(_file(tmp_path), FIXTURE_ID, inventory)
    assert store.fetch(inventory.lookup("syn_dated"), {"on_day": date(2000, 1, 1)}).rows


def test_bind_refuses_dollar_quotes_and_a_percent_literal() -> None:
    """bind refuses a dollar quote and a literal percent before it returns text."""
    plants = (
        ("syn_dollar", "SELECT $$ :name $$ AS unit_id"),
        ("syn_tagged", "SELECT $tag$ :name $tag$ AS unit_id"),
        ("syn_percent", "SELECT '50%' AS unit_id"),
    )
    for name, sql in plants:
        spec = _bare_spec(name, sql)
        for engine in ("postgres", "embedded"):
            with pytest.raises(StoreRefusal) as caught:
                bind(spec, {}, engine)
            assert str(caught.value) == "forbidden construct"


def test_adapters_send_nothing_for_a_dollar_quote_or_percent(tmp_path: Path) -> None:
    """Neither adapter sends a statement when bind refuses the text."""
    plants = (
        ("syn_dollar", "SELECT $$ :name $$ AS unit_id"),
        ("syn_tagged", "SELECT $tag$ :name $tag$ AS unit_id"),
        ("syn_percent", "SELECT '50%' AS unit_id"),
    )
    for name, sql in plants:
        folder = tmp_path / name
        _write(folder, name, sql, "", contract=False)
        inventory = load_inventory(folder)
        member = inventory.lookup(name)
        connection = _Script()
        postgres = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
        before = list(connection.calls)
        with pytest.raises(StoreRefusal) as caught:
            postgres.fetch(member, {})
        assert str(caught.value) == "forbidden construct"
        assert connection.calls == before
        embedded = EmbeddedStore(_file(tmp_path), FIXTURE_ID, inventory)
        sent: list[str] = []
        embedded._connection = _StatementRecorder(sent)
        with pytest.raises(StoreRefusal) as embedded_caught:
            embedded.fetch(member, {})
        assert str(embedded_caught.value) == "forbidden construct"
        assert sent == []


def test_distinct_placeholders_stay_distinct() -> None:
    translated = translate("SELECT :unit AS one, :units AS many", "embedded")
    assert translated == "SELECT $unit AS one, $units AS many"


def test_placeholder_in_literal_or_comment_is_forbidden() -> None:
    for text in ("SELECT ':name' AS label", "SELECT 1 AS label -- :name"):
        with pytest.raises(StoreRefusal) as caught:
            translate(text, "embedded")
        assert str(caught.value) == "forbidden construct"


def test_quote_and_sql_word_are_data(tmp_path: Path) -> None:
    folder = tmp_path / "quoted"
    _write(
        folder,
        "syn_label",
        "SELECT :label AS label ORDER BY label ASC NULLS LAST",
        "label text",
        returns="label text",
        order="label",
        contract=False,
    )
    inventory = load_inventory(folder)
    store = EmbeddedStore(_file(tmp_path), FIXTURE_ID, inventory)
    value = "SYN-'; DROP TABLE control_rows; --"
    result = store.fetch(inventory.lookup("syn_label"), {"label": value})
    assert result.rows == ((value,),)
    store.close()
    control = EmbeddedStore(_file(tmp_path), FIXTURE_ID, INVENTORY)
    assert len(control.fetch(MEMBER, {"units": units()}).rows) == 3


def test_missing_description_is_refused() -> None:
    connection = _Script()
    connection.blank_description = True
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "result description missing"


def test_short_row_is_result_width_invalid() -> None:
    connection = _Script(rows=(("SYN-a",),))
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "result width invalid"


def test_unknown_engine_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        translate("SELECT 1 AS label", "other")
    assert str(caught.value) == "unknown engine"


def test_missing_duckdb_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(StoreRefusal) as caught:
        EmbeddedStore(tmp_path / "missing.duckdb", FIXTURE_ID, INVENTORY)
    assert str(caught.value) == "STORE_UNAVAILABLE"


def test_renamed_result_column_is_refused() -> None:
    connection = _Script(columns=("other",))
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "result columns invalid"


def test_text_in_a_bigint_column_is_refused() -> None:
    connection = _Script(
        rows=(("SYN-a", "SYN-a", date(2000, 1, 1), "two", Decimal("1")),)
    )
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "result types invalid"


def test_short_identity_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        require_identity("ab")
    assert str(caught.value) == "release identity invalid"


def test_malformed_identity_makes_no_driver_call() -> None:
    connection = _Script()
    with pytest.raises(StoreRefusal) as caught:
        PostgresStore.for_control(connection, "not-an-identity", INVENTORY)
    assert str(caught.value) == "release identity invalid"
    assert connection.calls == []
    assert release_schema(FIXTURE_ID).startswith("r_")
    with pytest.raises(StoreRefusal):
        require_control_schema_name(release_schema(FIXTURE_ID))


def test_driver_error_text_is_not_in_the_refusal() -> None:
    connection = _Script(fail_sql="control_rows")
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        store.fetch(MEMBER, {"units": ["SYN-a"]})
    assert str(caught.value) == "engine operation failed"
    assert SECRET not in str(caught.value)


def test_prepare_of_the_control_query_and_a_missing_column(tmp_path: Path) -> None:
    store = _duck(tmp_path)
    prepare_all(store, INVENTORY)
    store.close()
    folder = tmp_path / "missing"
    _write(
        folder,
        "syn_missing",
        "SELECT p.missing_value AS missing_value FROM control_rows AS p ORDER BY missing_value ASC NULLS LAST",
        "",
        returns="missing_value bigint",
        order="missing_value",
    )
    broken = load_inventory(folder)
    embedded = EmbeddedStore(_file(tmp_path), FIXTURE_ID, broken)
    with pytest.raises(StoreRefusal) as caught:
        prepare_all(embedded, broken)
    assert str(caught.value) == "prepare failed query=syn_missing engine=embedded"


def test_postgres_prepare_explains_inside_the_transaction() -> None:
    connection = _Script()
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    prepare_all(store, INVENTORY)
    sql = [call[0] for call in connection.calls]
    explain = next(
        index for index, text in enumerate(sql) if text.startswith("EXPLAIN")
    )
    assert sql[explain - 2] == "BEGIN READ ONLY"
    assert "set_config" in sql[explain - 1]
    assert sql[explain + 1] == "COMMIT"


def test_postgres_explain_failure_is_prepare_failed() -> None:
    connection = _Script(fail_sql="EXPLAIN")
    store = PostgresStore.for_control(connection, FIXTURE_ID, INVENTORY)
    with pytest.raises(StoreRefusal) as caught:
        prepare_all(store, INVENTORY)
    assert str(caught.value) == "prepare failed query=control_rows engine=postgres"


def test_geometry_statement_wraps_only_the_geometry_item(tmp_path: Path) -> None:
    """The statement differs from the query file only in the wrapped geometry item."""
    folder = tmp_path / "geom"
    body = (
        "SELECT g.shape_id, g.shape\n"
        "FROM control_shape AS g\n"
        "ORDER BY g.shape_id ASC NULLS LAST"
    )
    _geometry_query(folder, body)
    inventory = load_inventory(folder)
    member = inventory.lookup("control_shape")
    embedded_sql = (
        "SELECT g.shape_id, hex(ST_AsWKB(g.shape)) AS shape\n"
        "FROM control_shape AS g\n"
        "ORDER BY g.shape_id ASC NULLS LAST"
    )
    postgres_sql = (
        "SELECT g.shape_id,"
        " upper(encode(\"syn_gis\".ST_AsBinary(g.shape, 'NDR'), 'hex')) AS shape\n"
        "FROM control_shape AS g\n"
        "ORDER BY g.shape_id ASC NULLS LAST"
    )
    sent: list[str] = []
    embedded = EmbeddedStore(_file(tmp_path), FIXTURE_ID, inventory)
    embedded._connection = _StatementRecorder(sent)
    embedded.plan(member, {})
    embedded.fetch(member, {})
    assert sent == ["EXPLAIN " + embedded_sql, embedded_sql]
    connection = _Script(
        rows=(
            ("SYN-g0", "0101000000000000000000C03F000000000000D03F"),
            ("SYN-g2", None),
        ),
        columns=("shape_id", "shape"),
    )
    postgres = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
    postgres.plan(member, {})
    assert postgres.fetch(member, {}).rows[1][1] is None
    statements = [sql for sql, _params in connection.calls]
    assert postgres_sql in statements
    assert any(sql.startswith("EXPLAIN " + postgres_sql) for sql in statements)
    plain = translate(
        (FIXTURE_DIR / "control_rows.sql")
        .read_text(encoding="utf-8")
        .split("\n", 4)[4],
        "embedded",
    )
    spec = INVENTORY.get("control_rows")
    assert spec is not None
    assert bind(spec, {"units": ["SYN-a"]}, "embedded")[0] == plain.strip()


def test_postgres_geometry_statement_uses_the_catalogue_schema(
    tmp_path: Path,
) -> None:
    """The geometry control names the extension schema from the catalogue, quoted."""
    folder = tmp_path / "geom-schema"
    _geometry_query(folder, _GEOMETRY_BODY)
    inventory = load_inventory(folder)
    member = inventory.lookup("control_shape")
    schema = "syn_ext"
    qualified = _BARE_GEOMETRY.replace("ST_AsBinary(", f'"{schema}".ST_AsBinary(', 1)
    connection = _Script(
        rows=(
            ("SYN-g0", "0101000000000000000000C03F000000000000D03F"),
            ("SYN-g2", None),
        ),
        columns=("shape_id", "shape"),
        postgis_schema=schema,
    )
    store = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
    assert connection.calls == [(POSTGIS_CATALOGUE, None)]
    store.plan(member, {})
    assert store.fetch(member, {}).rows[1][1] is None
    statements = [sql for sql, _params in connection.calls]
    assert qualified in statements
    assert _BARE_GEOMETRY not in statements
    assert qualified.replace(f'"{schema}".', "", 1) == _BARE_GEOMETRY
    assert any(sql == "EXPLAIN " + qualified for sql in statements)
    assert statements.count(POSTGIS_CATALOGUE) == 1


def test_empty_extension_catalogue_is_refused_at_open() -> None:
    """An absent extension is refused at open, and nothing is sent after the catalogue."""
    for opener in (PostgresStore.for_control, PostgresStore):
        connection = _Script(postgis_schema=None)
        with pytest.raises(StoreRefusal) as caught:
            opener(connection, FIXTURE_ID, INVENTORY)
        assert str(caught.value) == "extension schema invalid"
        assert connection.calls == [(POSTGIS_CATALOGUE, None)]


def test_extension_schema_with_a_quote_or_a_space_is_refused() -> None:
    """A schema name that is not a plain identifier is refused at open."""
    for name in ('syn"gis', "syn gis"):
        for opener in (PostgresStore.for_control, PostgresStore):
            connection = _Script(postgis_schema=name)
            with pytest.raises(StoreRefusal) as caught:
                opener(connection, FIXTURE_ID, INVENTORY)
            assert str(caught.value) == "extension schema invalid"
            assert connection.calls == [(POSTGIS_CATALOGUE, None)]


def test_geometry_fetch_returns_hand_wkb_without_an_extension(tmp_path: Path) -> None:
    """hex(ST_AsWKB) of a point is the hand-written form, and a spatial-only function stays absent."""
    import duckdb
    from store_live_controls import POINT_A, POINT_B

    folder = tmp_path / "geom"
    _geometry_query(
        folder,
        "SELECT g.shape_id, g.shape\n"
        "FROM control_shape AS g\n"
        "ORDER BY g.shape_id ASC NULLS LAST",
    )
    inventory = load_inventory(folder)
    store = EmbeddedStore(_geom_file(tmp_path), FIXTURE_ID, inventory)
    result = store.fetch(inventory.lookup("control_shape"), {})
    assert result.columns == ("shape_id", "shape")
    assert result.rows == (
        ("SYN-g0", POINT_A),
        ("SYN-g1", POINT_B),
        ("SYN-g2", None),
    )
    connection = store._connection
    assert connection is not None
    with pytest.raises(duckdb.Error):
        connection.execute("SELECT ST_AsHEXWKB(shape) FROM control_shape")


def test_empty_and_filled_lists_bind(tmp_path: Path) -> None:
    folder = tmp_path / "lists"
    _write(
        folder,
        "syn_lists",
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE p.unit_id = ANY(:names) AND p.count_value = ANY(:counts) "
        "ORDER BY p.unit_id ASC NULLS LAST",
        "names list[text], counts list[bigint]",
    )
    inventory = load_inventory(folder)
    listed = EmbeddedStore(_file(tmp_path), FIXTURE_ID, inventory)
    member = inventory.lookup("syn_lists")
    assert listed.fetch(member, {"names": [], "counts": []}).rows == ()
    filled = listed.fetch(member, {"names": ["SYN-a"], "counts": [2]})
    assert filled.rows == (("SYN-a",),)


def _bare_spec(name: str, sql: str) -> object:
    from eii_product.store.registry import QuerySpec, ReturnSpec

    return QuerySpec(
        name, (), (ReturnSpec("unit_id", "text"),), ("unit_id",), sql, "ab", ()
    )


def _geometry_query(folder: Path, body: str) -> None:
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / "control_shape.sql").write_text(
        "-- name: control_shape\n-- params:\n"
        "-- returns: shape_id text, shape geometry\n-- order: shape_id\n" + body + "\n",
        encoding="utf-8",
    )
    (folder / "control_shape.toml").write_text(
        '[[tables]]\nname = "control_shape"\nanchor = "invented control table"\n'
        'key = ["shape_id"]\n\n[[tables.columns]]\nname = "shape_id"\n'
        'type = "string"\nnullable = false\n\n[[tables.columns]]\nname = "shape"\n'
        'type = "geometry"\nnullable = true\n',
        encoding="utf-8",
    )


class _StatementRecorder:
    def __init__(self, sent: list[str]) -> None:
        self.sent = sent

    def cursor(self) -> _StatementRecorder:
        return self

    def execute(self, sql: str, params: object = None) -> None:
        del params
        self.sent.append(sql)

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    description = (("shape_id",), ("shape",))

    def close(self) -> None:
        return None


def _duck(folder: Path) -> EmbeddedStore:
    return EmbeddedStore(_file(folder), FIXTURE_ID, INVENTORY)


def _geom_file(folder: Path) -> Path:
    path = folder / "geom.duckdb"
    import duckdb
    from store_live_controls import DUCK_GEOM_CREATE, GEOM_WKT

    connection = duckdb.connect(str(path))
    connection.execute(DUCK_GEOM_CREATE)
    connection.execute(
        "INSERT INTO control_shape VALUES (?, ?::GEOMETRY)",
        [GEOM_WKT[0][0], GEOM_WKT[0][1]],
    )
    connection.execute(
        "INSERT INTO control_shape VALUES (?, ?::GEOMETRY)",
        [GEOM_WKT[1][0], GEOM_WKT[1][1]],
    )
    connection.execute("INSERT INTO control_shape VALUES (?, NULL)", [GEOM_WKT[2][0]])
    connection.close()
    return path


def _file(folder: Path) -> Path:
    path = folder / "control.duckdb"
    if path.exists():
        return path
    import duckdb
    from store_live_controls import DUCK_GEOM_CREATE, GEOM_WKT

    connection = duckdb.connect(str(path))
    connection.execute(DUCK_CREATE)
    connection.executemany(DUCK_INSERT, ROWS)
    connection.execute(DUCK_GEOM_CREATE)
    for shape_id, wkt in GEOM_WKT:
        if wkt is None:
            connection.execute("INSERT INTO control_shape VALUES (?, NULL)", [shape_id])
            continue
        connection.execute(
            "INSERT INTO control_shape VALUES (?, ?::GEOMETRY)",
            [shape_id, wkt],
        )
    connection.close()
    return path


def _write(
    folder: Path,
    name: str,
    sql: str,
    params: str,
    *,
    returns: str = "unit_id text",
    order: str = "unit_id",
    contract: bool = True,
) -> None:
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    header = f"-- name: {name}\n-- params: {params}\n-- returns: {returns}\n-- order: {order}\n"
    (folder / f"{name}.sql").write_text(header + sql + "\n", encoding="utf-8")
    text = (
        '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        'type = "string"\nnullable = false\n'
    )
    if not contract:
        text = (
            '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\n'
            'key = []\n\n[[tables.columns]]\nname = "unit_id"\n'
            'type = "string"\nnullable = false\n'
        )
    (folder / f"{name}.toml").write_text(text, encoding="utf-8")


class _Column:
    def __init__(self, name: str) -> None:
        self.name = name


class _Script:
    def __init__(
        self,
        *,
        rows: tuple[tuple[object, ...], ...] | None = None,
        columns: tuple[str, ...] = COLUMNS,
        fail_sql: str = "",
        returned_schema: str = "",
        postgis_schema: str | None = "syn_gis",
        name_values: tuple[object, ...] | None = None,
    ) -> None:
        self.calls: list[tuple[str, object]] = []
        self.rows = rows
        self.columns = columns
        self.fail_sql = fail_sql
        self.returned_schema = returned_schema
        self.postgis_schema = postgis_schema
        self.name_values = name_values
        self.autocommit = True
        self.blank_description = False

    def close(self) -> None:
        return None

    def cursor(self) -> _Cursor:
        return _Cursor(self)


class _Cursor:
    def __init__(self, owner: _Script) -> None:
        self.owner = owner
        self.sql = ""
        self.params: object = None

    def execute(self, sql: str, params: object = None) -> None:
        self.sql = sql
        self.params = params
        self.owner.calls.append((sql, params))
        if self.owner.fail_sql and self.owner.fail_sql in sql:
            raise RuntimeError(SECRET)

    def fetchone(self) -> tuple[object, ...] | None:
        if self.sql == POSTGIS_CATALOGUE:
            if self.owner.postgis_schema is None:
                return None
            return (self.owner.postgis_schema,)
        if "set_config" in self.sql:
            if self.owner.returned_schema:
                return (self.owner.returned_schema,)
            if isinstance(self.params, tuple):
                return (self.params[0],)
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        if self.sql.startswith("EXPLAIN"):
            return [("plan",)]
        if self.owner.rows is not None:
            return list(self.owner.rows)
        selected = self.params
        wanted: list[str] = []
        if isinstance(selected, dict):
            raw = selected.get("units", [])
            if isinstance(raw, list):
                wanted = [item for item in raw if isinstance(item, str)]
        return [row for row in ROWS if row[0] in wanted]

    @property
    def description(self) -> Sequence[object] | None:
        if self.owner.blank_description:
            return None
        if self.owner.name_values is not None:
            return tuple((value,) for value in self.owner.name_values)
        return tuple(_Column(name) for name in self.owner.columns)

    def close(self) -> None:
        return None


class _StandIn:
    """A connection whose cursor fails or returns no description."""

    def __init__(self, *, fail: bool, blank: bool) -> None:
        self.fail = fail
        self.blank = blank

    def cursor(self) -> _StandIn:
        return self

    def execute(self, sql: str, params: object = None) -> None:
        del sql, params
        if self.fail:
            raise RuntimeError("SYN-driver")

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    @property
    def description(self) -> tuple[tuple[str, ...], ...] | None:
        if self.blank:
            return None
        return (("count_value",),)

    def close(self) -> None:
        return None
