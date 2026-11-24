"""Offline stand-in for the live control command. It never opens a database service."""

from __future__ import annotations

from pathlib import Path

import pytest
from live_store_registry import main
from store_live_controls import COLUMNS, FIXTURE_ID, ROWS

from eii_product.store.postgres import (
    control_schema,
    release_schema,
    require_control_schema_name,
)
from eii_product.store.protocol import StoreRefusal

URL = "postgresql://SYN-user" + "@" + "127.0.0.1:55432" + "/SYN-db"
_POSTGIS_CATALOGUE = (
    "SELECT n.nspname FROM pg_catalog.pg_extension AS e "
    "JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace "
    "WHERE e.extname = 'postgis'"
)
OFF = "postgresql://SYN-user" + "@" + "192.0.2.1:55432" + "/SYN-db"
SECRET = "SYN-secret-token"


def test_absent_service_exits_1_with_a_fixed_reason_and_no_pass_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def connect(target: object) -> object:
        del target
        raise RuntimeError(SECRET)

    code = main([], {"EII_DATABASE_URL": URL}, connect=connect)
    output = capsys.readouterr().out
    assert code == 1
    assert "PASS" not in output
    assert "engine operation failed" in output
    assert SECRET not in output


def test_missing_environment_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([], {}, connect=_refuse)
    output = capsys.readouterr().out
    assert code == 1
    assert "database environment missing" in output
    assert "PASS" not in output


def test_existing_control_schema_is_refused_and_not_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _Service(schema_exists=True)
    code = main([], {"EII_DATABASE_URL": URL}, connect=script.connect)
    output = capsys.readouterr().out
    assert code == 1
    assert "control schema exists" in output
    assert "PASS" not in output
    assert not any(sql.startswith("DROP SCHEMA") for sql, _params in script.calls)


def test_schema_is_dropped_after_a_failure(capsys: pytest.CaptureFixture[str]) -> None:
    script = _Service(fail_reads=True)
    code = main([], {"EII_DATABASE_URL": URL}, connect=script.connect)
    output = capsys.readouterr().out
    assert code == 1
    assert "PASS" not in output
    assert any(sql.startswith("DROP SCHEMA") for sql, _params in script.calls)


def test_failed_drop_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    script = _Service(drop_fails=True)
    code = main([], {"EII_DATABASE_URL": URL}, connect=script.connect)
    output = capsys.readouterr().out
    assert code == 1
    assert "control schema cleanup failed" in output
    assert "PASS" not in output


def test_divergence_exits_3_only_after_a_passing_baseline(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    script = _Service()
    code = main(
        ["--diverge"],
        {"EII_DATABASE_URL": URL},
        connect=script.connect,
        destination=tmp_path / "report.json",
    )
    output = capsys.readouterr().out
    assert code == 3
    assert "PASS" not in output
    assert "field mismatch" in output
    assert not (tmp_path / "report.json").exists()
    assert any(sql.startswith("DROP SCHEMA") for sql, _params in script.calls)


def test_driver_error_text_is_not_printed(capsys: pytest.CaptureFixture[str]) -> None:
    script = _Service(fail_reads=True)
    code = main([], {"EII_DATABASE_URL": URL}, connect=script.connect)
    output = capsys.readouterr().out
    assert code == 1
    assert SECRET not in output


def test_control_schema_name_cannot_match_the_release_pattern() -> None:
    name = control_schema(FIXTURE_ID)
    assert name.startswith("ctl_")
    assert len(name) == 20
    release = release_schema(FIXTURE_ID)
    assert release.startswith("r_")
    with pytest.raises(StoreRefusal) as caught:
        require_control_schema_name(release)
    assert str(caught.value) == "release identity invalid"


def test_set_up_commits_before_the_read_only_reads(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    script = _Service()
    code = main(
        [],
        {"EII_DATABASE_URL": URL},
        connect=script.connect,
        destination=tmp_path / "report.json",
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "PASS store-registry: both engines match" in output
    sql = [text for text, _params in script.calls]
    assert sql.index("COMMIT") < sql.index("BEGIN READ ONLY")
    assert (tmp_path / "report.json").is_file()


def test_failed_prepare_prints_engine_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A prepare that does not fail on PostgreSQL alone prints the engine names, then refuses."""
    from live_store_registry import _refuse_unexpected_prepare

    _refuse_unexpected_prepare(["postgres"])
    assert capsys.readouterr().out == ""
    with pytest.raises(StoreRefusal) as caught:
        _refuse_unexpected_prepare(["embedded", "postgres"])
    assert str(caught.value) == "engine operation failed"
    assert capsys.readouterr().out.strip() == "embedded,postgres"


def test_write_refusal_requires_the_engine_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Any exception is not proof that the engine refused the write."""
    script = _Service(write_runtime=True)
    code = main(
        [],
        {"EII_DATABASE_URL": URL},
        connect=script.connect,
        destination=tmp_path / "report.json",
    )
    output = capsys.readouterr().out
    assert code == 1
    assert "PASS" not in output
    assert "engine operation failed" in output
    assert SECRET not in output


def test_unknown_argument_is_a_usage_refusal_before_any_engine(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown argument exits 2 on one fixed line, and no engine is touched."""
    called = {"count": 0}

    def connect(target: object) -> object:
        del target
        called["count"] += 1
        raise AssertionError("connected")

    code = main(["--syn-unknown"], {"EII_DATABASE_URL": URL}, connect=connect)
    output = capsys.readouterr().out
    assert code == 2
    assert output == "FAIL store-registry: usage: live_store_registry.py [--diverge]\n"
    assert called["count"] == 0


def test_target_off_loopback_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    called = {"count": 0}

    def connect(target: object) -> object:
        del target
        called["count"] += 1
        raise AssertionError("connected")

    code = main([], {"EII_DATABASE_URL": OFF}, connect=connect)
    output = capsys.readouterr().out
    assert code == 1
    assert "EII_DATABASE_URL host is not 127.0.0.1" in output
    assert "PASS" not in output
    assert called["count"] == 0


class _EngineWriteRefusal(Exception):
    """Stand-in for the engine's read-only refusal. The code is PostgreSQL 25006."""

    sqlstate = "25006"


def _is_geometry(sql: str) -> bool:
    return "control_shape" in sql or "ST_AsWKB" in sql or "ST_AsBinary" in sql


def _refuse(target: object) -> object:
    del target
    raise AssertionError("connected")


class _Service:
    def __init__(
        self,
        *,
        schema_exists: bool = False,
        fail_reads: bool = False,
        drop_fails: bool = False,
        write_runtime: bool = False,
    ) -> None:
        self.schema_exists = schema_exists
        self.fail_reads = fail_reads
        self.drop_fails = drop_fails
        self.write_runtime = write_runtime
        self.calls: list[tuple[str, object]] = []
        self.autocommit = True

    def connect(self, target: object) -> _Service:
        del target
        return self

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def close(self) -> None:
        return None


class _Cursor:
    def __init__(self, owner: _Service) -> None:
        self.owner = owner
        self.sql = ""
        self.params: object = None

    def execute(self, sql: str, params: object = None) -> None:
        self.sql = sql
        self.params = params
        self.owner.calls.append((sql, params))
        if sql.startswith("EXPLAIN FROM"):
            raise RuntimeError("prepare refused")
        if self.owner.drop_fails and sql.startswith("DROP SCHEMA"):
            raise RuntimeError(SECRET)
        if sql.startswith("INSERT INTO control_rows"):
            if self.owner.write_runtime:
                raise RuntimeError(SECRET)
            raise _EngineWriteRefusal("write refused")
        if (
            self.owner.fail_reads
            and "FROM control_rows" in sql
            and not sql.startswith("EXPLAIN")
        ):
            raise RuntimeError(SECRET)

    def fetchone(self) -> tuple[object, ...] | None:
        if "information_schema.schemata" in self.sql:
            return (1,) if self.owner.schema_exists else None
        if "set_config" in self.sql and isinstance(self.params, tuple):
            return (self.params[0],)
        if self.sql == _POSTGIS_CATALOGUE:
            return ("syn_gis",)
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        if self.sql.startswith("EXPLAIN"):
            return [("plan",)]
        if _is_geometry(self.sql):
            from store_live_controls import POINT_A, POINT_B

            return [("SYN-g0", POINT_A), ("SYN-g1", POINT_B), ("SYN-g2", None)]
        wanted: set[str] = set()
        if isinstance(self.params, dict):
            raw = self.params.get("units", [])
            if isinstance(raw, list):
                wanted = {item for item in raw if isinstance(item, str)}
        return [row for row in ROWS if row[0] in wanted]

    @property
    def description(self) -> tuple[tuple[str], ...]:
        if _is_geometry(self.sql):
            return tuple((name,) for name in ("shape_id", "shape"))
        return tuple((name,) for name in COLUMNS)

    def close(self) -> None:
        return None
