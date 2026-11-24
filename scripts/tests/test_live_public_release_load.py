"""Offline halves of the public release load. No database and no skip."""

from __future__ import annotations

import ast
import json
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import live_public_release_load as live
import pytest

from eii_core.manifest import ColumnSpec
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.loader import _parquet_rows, owner_connect_kwargs, run_load
from eii_product.store.registry import PACKAGED
from eii_product.store.release_check import (
    RELEASE_MANIFEST_COLUMNS,
    check_release,
    digest_rows,
    manifest_rows,
)

IDENTITY = "ab" * 32
URL = "postgresql://owner:invented-secret-token" + "@" + "127.0.0.1:55440/postgres"
OFF = "postgresql://owner:invented-secret-token" + "@" + "10.1.1.1:55440/postgres"


def test_usage_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    code = live.main(["--bogus"], {"EII_DATABASE_URL": URL}, connect=_boom)
    assert code == 2
    assert (
        capsys.readouterr().out
        == "FAIL public-release-load: usage: live_public_release_load.py [--diverge]\n"
    )


def test_parser_refusal_is_its_own_reason(capsys: pytest.CaptureFixture[str]) -> None:
    code = live.main([], {"EII_DATABASE_URL": "not-a-url"}, connect=_boom)
    assert code == 1
    assert (
        capsys.readouterr().out
        == "FAIL public-release-load: scheme is not postgresql or postgres\n"
    )


def test_host_off_loopback_never_connects(capsys: pytest.CaptureFixture[str]) -> None:
    code = live.main([], {"EII_DATABASE_URL": OFF}, connect=_boom)
    assert code == 1
    assert (
        capsys.readouterr().out
        == "FAIL public-release-load: EII_DATABASE_URL host is not 127.0.0.1\n"
    )


def test_proof_database_name() -> None:
    assert live.proof_database(IDENTITY) == "invented_r_" + IDENTITY[:16]


def test_drop_is_bound_to_the_fixture() -> None:
    database, schema, staging = live.drop_names(IDENTITY)
    assert database == "invented_r_" + IDENTITY[:16]
    assert schema == "r_" + IDENTITY[:16]
    assert staging == schema + "__loading"
    assert "postgres" not in {database, schema, staging}


def test_no_collected_test_needs_a_database() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"skip", "environ", "mark"}:
            message = "a collected test reaches the process environment or skips"
            raise AssertionError(message)
    del source


def test_manifest_only_load_both_stores(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live.require_same_identity(IDENTITY, IDENTITY, IDENTITY)
    with pytest.raises(live._Stop):
        live.require_same_identity(IDENTITY, "cd" * 32, IDENTITY)
    assert _drive(monkeypatch, capsys, [])[0] == 0
    failed = _drive(monkeypatch, capsys, [], extra_table=True)
    assert failed[0] == 1
    assert "FAIL public-release-load: manifest_tables_mismatch\n" in failed[1]


def test_manifest_only_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], extra_table=True)
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == (
        "FAIL public-release-load: manifest_tables_mismatch"
    )


def test_public_tables_parity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    columns = (ColumnSpec("value", "int", False),)
    left = digest_rows(({"value": 15},), columns, ("value",))
    right = digest_rows(({"value": 15},), columns, ("value",))
    live.require_parity(left, right, 1, 1)
    changed = digest_rows(({"value": 16},), columns, ("value",))
    with pytest.raises(live._Stop):
        live.require_parity(left, changed, 1, 1)
    assert _drive(monkeypatch, capsys, [])[0] == 0
    valued = _drive(monkeypatch, capsys, [], rows=_changed_integer())
    assert valued[0] == 1
    assert "FAIL public-release-load: store_verification_failed\n" in valued[1]
    shaped = _drive(monkeypatch, capsys, [], rows=_changed_geometry())
    assert shaped[0] == 1
    assert "FAIL public-release-load: store_verification_failed\n" in shaped[1]


def test_public_tables_parity_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], rows=_changed_integer())
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == (
        "FAIL public-release-load: store_verification_failed"
    )


def test_receipt_complete_not_artefact(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live.require_receipt("complete", IDENTITY, IDENTITY, False)
    with pytest.raises(live._Stop):
        live.require_receipt("complete", IDENTITY, IDENTITY, True)
    assert _drive(monkeypatch, capsys, [])[0] == 0
    failed = _drive(monkeypatch, capsys, [], before_check=_name_receipt)
    assert failed[0] == 1
    assert "FAIL public-release-load: receipt_not_complete\n" in failed[1]


def test_receipt_complete_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], before_check=_name_receipt)
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == (
        "FAIL public-release-load: receipt_not_complete"
    )


def test_same_release_identity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live.require_same_identity(IDENTITY, IDENTITY, IDENTITY)
    assert _drive(monkeypatch, capsys, [])[0] == 0
    failed = _drive(monkeypatch, capsys, [], rows=_other_identity())
    assert failed[0] == 1
    assert "FAIL public-release-load: store_verification_failed\n" in failed[1]


def test_same_release_identity_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], rows=_other_identity())
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == (
        "FAIL public-release-load: store_verification_failed"
    )


def test_loaded_geometry_has_srid_4326(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live.require_srids((4326, 4326))
    with pytest.raises(live._Stop):
        live.require_srids((4326, 0))
    assert _drive(monkeypatch, capsys, [])[0] == 0
    failed = _drive(monkeypatch, capsys, [], srids=(0,))
    assert failed[0] == 1
    assert "FAIL public-release-load: store_verification_failed\n" in failed[1]


def test_loaded_geometry_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], srids=(0,))
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == (
        "FAIL public-release-load: store_verification_failed"
    )


def test_configured_preflight_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _drive(monkeypatch, capsys, [])[0] == 0
    failed = _drive(monkeypatch, capsys, [], before_check=_pending_receipt)
    assert failed[0] == 1
    assert "FAIL public-release-load: preflight_failed\n" in failed[1]


def test_configured_preflight_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], before_check=_pending_receipt)
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == "FAIL public-release-load: preflight_failed"


def test_unlisted_table_loads_nowhere_live(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live.require_unlisted_refused(4, "unlisted_table extra_table")
    with pytest.raises(live._Stop):
        live.require_unlisted_refused(0, "unlisted_table extra_table")
    assert _drive(monkeypatch, capsys, [])[0] == 0
    failed = _drive(monkeypatch, capsys, [], schema_left=True)
    assert failed[0] == 1
    assert "FAIL public-release-load: unlisted_table\n" in failed[1]


def test_unlisted_table_left_out_of_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed = _drive(monkeypatch, capsys, [], schema_left=True)
    assert failed[0] == 1
    assert failed[1].splitlines()[0] == "FAIL public-release-load: unlisted_table"


def test_pass_output_is_the_same_bytes_twice(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _drive(monkeypatch, capsys, [])
    second = _drive(monkeypatch, capsys, [])
    assert first[0] == 0
    assert second[0] == 0
    assert first[1] == second[1]
    lines = first[1].splitlines()
    assert len(lines) == 2
    assert lines[0] == "PASS public-release-load: both stores match"
    payload = json.loads(lines[1])
    assert set(payload) == {
        "checks_run",
        "digests_identical",
        "tables_compared",
        "tables_loaded",
    }
    for value in payload.values():
        assert type(value) is int or type(value) is bool


def test_diverge_exits_3_only_when_detected() -> None:
    assert live.classify_divergence(True, True) == 3
    assert live.classify_divergence(True, False) == 1
    assert live.classify_divergence(False, True) == 1


def test_diverge_on_equal_stores_exits_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _drive(monkeypatch, capsys, ["--diverge"])
    assert code == 3
    assert out == "FAIL public-release-load: store_verification_failed\n"


def test_diverge_zero_changed_rows_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _drive(monkeypatch, capsys, ["--diverge"], before_check=_empty_reader)
    assert code == 1
    assert out == "FAIL public-release-load: divergence not detected\n"


def test_diverge_failing_baseline_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _drive(monkeypatch, capsys, ["--diverge"], extra_table=True)
    assert code == 1
    assert out == "FAIL public-release-load: manifest_tables_mismatch\n"


def test_url_user_does_not_reach_the_loader() -> None:
    database = "invented_r_" + IDENTITY[:16]
    arguments = live.load_arguments("127.0.0.1", 55440, database)
    assert arguments == {"database": database, "host": "127.0.0.1", "port": 55440}
    kwargs = owner_connect_kwargs("127.0.0.1", 55440, database)
    assert "password" not in kwargs
    assert kwargs["user"] == "eii_owner"


def _boom(*_args: object, **_kwargs: object) -> object:
    message = "connection was opened"
    raise AssertionError(message)


class _Preset:
    def __init__(
        self,
        rows: dict[str, tuple[dict[str, object], ...]],
        names: tuple[str, ...],
        columns: dict[str, tuple[ColumnSpec, ...]],
    ) -> None:
        self.rows = rows
        self.names = names
        self.columns = columns


_CACHED: _Preset | None = None


def _preset() -> _Preset:
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    import public_release_fixture as fixture

    from eii_product.store.loader import _parquet_rows
    from eii_product.store.release_check import check_release

    folder = Path(tempfile.mkdtemp(prefix="invented-preset-"))
    try:
        fixture.build_fixture(folder)
        checked = check_release(folder)
        rows: dict[str, tuple[dict[str, object], ...]] = {}
        tables = checked.document["tables"]
        for name, columns in checked.schemas.items():
            file = ""
            if type(tables) is list:
                for entry in tables:
                    if type(entry) is dict and entry.get("name") == name:
                        found = entry.get("file")
                        if type(found) is str:
                            file = found
            rows[name] = tuple(
                dict(row) for row in _parquet_rows(folder / file, columns)
            )
        rows["release_manifest"] = tuple(
            dict(row) for row in manifest_rows(checked.document)
        )
        _CACHED = _Preset(rows, tuple(sorted(rows)), dict(checked.schemas))
        return _CACHED
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _copied_rows() -> dict[str, tuple[dict[str, object], ...]]:
    preset = _preset()
    return {
        name: tuple(dict(row) for row in table) for name, table in preset.rows.items()
    }


def _changed_integer() -> dict[str, tuple[dict[str, object], ...]]:
    rows = _copied_rows()
    table = [dict(row) for row in rows["pub_licence_active"]]
    value = table[0]["active_count"]
    if type(value) is not int:
        message = "active_count is not an integer"
        raise AssertionError(message)
    table[0]["active_count"] = value + 1
    rows["pub_licence_active"] = tuple(table)
    return rows


def _changed_geometry() -> dict[str, tuple[dict[str, object], ...]]:
    rows = _copied_rows()
    table = [dict(row) for row in rows["district"]]
    value = table[0]["geometry"]
    if type(value) is not bytes or len(value) == 0:
        message = "district geometry is not bytes"
        raise AssertionError(message)
    raw = bytearray(value)
    raw[-1] ^= 1
    table[0]["geometry"] = bytes(raw)
    rows["district"] = tuple(table)
    return rows


def _other_identity() -> dict[str, tuple[dict[str, object], ...]]:
    rows = _copied_rows()
    table = [dict(row) for row in rows["release_manifest"]]
    for row in table:
        row["release_id"] = "cd" * 32
    rows["release_manifest"] = tuple(table)
    return rows


def _name_receipt(name: str, folder: Path) -> None:
    if name != "receipt_complete_not_artefact":
        return
    path = folder / "manifest.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if type(document) is not dict:
        message = "manifest is not an object"
        raise AssertionError(message)
    artefacts = document.get("artefacts")
    if type(artefacts) is not list:
        artefacts = []
    artefacts.append({"path": "load_receipt.json", "sha256": "ab" * 32})
    document["artefacts"] = artefacts
    path.write_text(json.dumps(document), encoding="utf-8")


def _pending_receipt(name: str, folder: Path) -> None:
    if name != "configured_preflight_passes":
        return
    path = folder / "load_receipt.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if type(document) is not dict:
        message = "receipt is not an object"
        raise AssertionError(message)
    document["state"] = "pending"
    path.write_text(json.dumps(document), encoding="utf-8")


def _empty_reader(name: str, folder: Path) -> None:
    if name != "diverge":
        return
    import duckdb

    connection = duckdb.connect(str(folder / "release.duckdb"))
    try:
        listed = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
        ).fetchall()
        for (table,) in listed:
            if type(table) is str and table != "release_manifest":
                connection.execute(f'DELETE FROM "{table}"')
    finally:
        connection.close()


def _drive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    *,
    rows: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    extra_table: bool = False,
    srids: tuple[int, ...] | None = None,
    schema_left: bool = False,
    before_check: Callable[[str, Path], None] | None = None,
) -> tuple[int, str]:
    preset = _preset()
    supplied = preset.rows if rows is None else rows
    state = {"n": 0}

    def connect(_target: object, _database: str) -> object:
        state["n"] += 1
        if state["n"] == 3:
            return _RecordingPostgres(
                supplied,
                names=preset.names,
                columns=preset.columns,
                extra_table=extra_table,
                srids=srids,
                schema_left=schema_left,
            )
        return _ControlConnection()

    def owner_connect() -> Callable[..., object]:
        def inner(**_kwargs: object) -> object:
            return _RecordingPostgres(
                preset.rows, names=preset.names, columns=preset.columns
            )

        return inner

    monkeypatch.setattr(live, "_owner_connect", owner_connect)
    code = live.main(
        args,
        {"EII_DATABASE_URL": URL},
        connect=connect,
        before_check=before_check,
    )
    return code, capsys.readouterr().out


class _ControlConnection:
    stand_in = True
    autocommit = True

    def execute(self, sql: str, _params: object = None) -> list[tuple[object, ...]]:
        if "pg_database" in sql:
            return []
        if "pg_roles" in sql:
            return [(1,)]
        return []

    def close(self) -> None:
        """The command closes every connection it opened."""


class _Cursor:
    def __init__(self, owner: _RecordingPostgres) -> None:
        self._owner = owner
        self._rows: list[tuple[object, ...]] = []
        self.description: tuple[tuple[str], ...] | None = None

    def execute(self, sql: str, params: object = None) -> object:
        self._rows = self._owner.execute(sql, params)
        self.description = None if len(self._rows) == 0 else (("value",),)
        return None

    def fetchone(self) -> tuple[object, ...] | None:
        if len(self._rows) == 0:
            return None
        return self._rows[0]

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)

    def close(self) -> None:
        """The adapter closes the cursor it opened."""


class _RecordingPostgres:
    stand_in = True
    autocommit = True

    def __init__(
        self,
        rows: Mapping[str, Sequence[Mapping[str, object]]],
        *,
        names: Sequence[str],
        columns: Mapping[str, Sequence[ColumnSpec]],
        extra_table: bool = False,
        srids: tuple[int, ...] | None = None,
        schema_left: bool = False,
    ) -> None:
        self.rows = rows
        self.names = list(names)
        if extra_table:
            self.names.append("invented_extra")
        self.columns = columns
        self.srids = srids
        self.schema_left = schema_left

    def execute(self, sql: str, params: object = None) -> list[tuple[object, ...]]:
        if "rolsuper" in sql:
            return [("eii_owner", False)]
        if "extnamespace" in sql:
            return [("public",)]
        if "pg_extension" in sql:
            return [("plpgsql",), ("postgis",)]
        if "pg_namespace" in sql:
            if self.schema_left:
                return [("r_left",)]
            return []
        if "pg_database" in sql:
            return []
        if "pg_roles" in sql:
            return [(1,)]
        if "set_config" in sql and type(params) is tuple and len(params) > 0:
            return [(params[0],)]
        if "ST_SRID" in sql:
            table = _quoted_table(sql)
            if self.srids is not None and table in {"district", "grid_cell"}:
                return [(value,) for value in self.srids]
            return [(4326,) for _ in self.rows.get(table, ())]
        if "information_schema.tables" in sql:
            return [(name,) for name in self.names]
        if sql.strip() == "SELECT 1":
            return [(1,)]
        if sql.startswith("SELECT"):
            table = _quoted_table(sql)
            columns: Sequence[ColumnSpec] | None
            if table == "release_manifest":
                columns = RELEASE_MANIFEST_COLUMNS
            else:
                columns = self.columns.get(table)
            if columns is None:
                return []
            return [
                tuple(row[column.name] for column in columns)
                for row in self.rows.get(table, ())
            ]
        return []

    def copy_rows(self, sql: str, _rows: object) -> None:
        del sql

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def close(self) -> None:
        """The command closes every connection it opened."""


def _quoted_table(sql: str) -> str:
    marker = '."'
    if marker not in sql:
        return ""
    return sql.rsplit(marker, 1)[1].rstrip('"')


def embedded_fixture_store(folder: Path, release_id: str) -> EmbeddedStore:
    """Replay a built fixture through the real loader onto the embedded store.

    The recorded Postgres stand-in drives ``run_load`` exactly as the mounted
    offline tests do; no database or network is touched.
    """
    checked = check_release(folder)
    rows: dict[str, tuple[dict[str, object], ...]] = {}
    tables = checked.document["tables"]
    for name, columns in checked.schemas.items():
        file = ""
        if type(tables) is list:
            for entry in tables:
                if type(entry) is dict and entry.get("name") == name:
                    found = entry.get("file")
                    if type(found) is str:
                        file = found
        rows[name] = tuple(dict(row) for row in _parquet_rows(folder / file, columns))
    rows["release_manifest"] = tuple(
        dict(row) for row in manifest_rows(checked.document)
    )
    connection = _RecordingPostgres(rows, names=tuple(rows), columns=checked.schemas)
    if (
        run_load(
            folder,
            host="invented.invalid",
            port=1,
            database="INVENTED",
            connect=lambda **kw: connection,
        )
        != 0
    ):
        raise RuntimeError("invented_release_load_refused")
    return EmbeddedStore(folder / "release.duckdb", release_id, PACKAGED)


def test_parser_fixed_outcomes_stay_distinct(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert live._target({"EII_DATABASE_URL": URL}).host == "127.0.0.1"
    for url, expected in (
        (
            URL.replace("postgresql:", "https:", 1),
            "scheme is not postgresql or postgres",
        ),
        (URL + "?extra=INVENTED", "query or fragment not allowed"),
        (URL.replace("127.0.0.1", "127.0.0.1,127.0.0.2"), "more than one host"),
        (URL.replace("127.0.0.1", ""), "no host"),
        (URL.replace("127.0.0.1", "[127.0.0.1"), "cannot be parsed"),
        (URL.replace(":55440", ":wrong"), "port is not a number from 1 to 65535"),
        (URL.replace(":55440", ""), "no port"),
        (URL.replace("owner:invented-secret-token@", ""), "no user"),
        (URL.replace("/postgres", "/"), "no database name"),
        (
            URL.replace("owner:", "own%00er:", 1),
            "user, password or database holds a NUL character",
        ),
        (OFF, "EII_DATABASE_URL host is not 127.0.0.1"),
    ):
        assert live.main([], {"EII_DATABASE_URL": url}, connect=_boom) == 1
        assert capsys.readouterr().out == "FAIL public-release-load: " + expected + "\n"
