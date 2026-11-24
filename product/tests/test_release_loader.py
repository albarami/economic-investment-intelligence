"""Loader checks on stand-ins and plain rows. No database and no release table."""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr
from datetime import datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from eii_core.manifest import ColumnSpec
from eii_product.store.loader import (
    PARTIAL_READER,
    READER_NAME,
    LoadRefusal,
    OwnerConnectFailed,
    PostgresNotAnswering,
    geometry_alter,
    load_checked,
    owner_connect_kwargs,
    refusal_from_connect,
    require_extensions,
    require_owner,
    run_load,
    verify_staged,
)
from eii_product.store.receipt import RECEIPT_NAME
from eii_product.store.release_check import (
    RELEASE_MANIFEST_COLUMNS,
    CheckedRelease,
    digest_rows,
)

IDENTITY = "ab" * 32
OTHER = "cd" * 32
POINT = struct.pack("<BI2d", 1, 1, 1.0, 2.0)
SECRET = "invented-secret-token"


def test_equal_stores_verify() -> None:
    checked = _checked(1)
    rows = _sides(IDENTITY, (_row(15),))
    verify_staged(rows, rows, checked, {"pub_census_national": (4326,)})


def test_another_release_id_fails() -> None:
    checked = _checked(1)
    left = _sides(IDENTITY, (_row(15),))
    right = _sides(OTHER, (_row(15),))
    with pytest.raises(LoadRefusal) as caught:
        verify_staged(left, right, checked)
    assert caught.value.reason == "store_verification_failed"


def test_changed_integer_fails() -> None:
    checked = _checked(1)
    left = _sides(IDENTITY, (_row(15),))
    right = _sides(IDENTITY, (_row(16),))
    with pytest.raises(LoadRefusal) as caught:
        verify_staged(left, right, checked)
    assert caught.value.reason == "store_verification_failed"


def test_one_row_fewer_fails() -> None:
    checked = _checked(2)
    left = _sides(IDENTITY, (_row(15, "one"), _row(16, "two")))
    right = _sides(IDENTITY, (_row(15, "one"),))
    with pytest.raises(LoadRefusal) as caught:
        verify_staged(left, right, checked)
    assert caught.value.reason == "store_verification_failed"


def test_changed_geometry_byte_fails() -> None:
    checked = _geometry_checked()
    left = _geometry_sides(POINT)
    changed = bytearray(POINT)
    changed[-1] ^= 1
    right = _geometry_sides(bytes(changed))
    with pytest.raises(LoadRefusal) as caught:
        verify_staged(left, right, checked)
    assert caught.value.reason == "store_verification_failed"


def test_missing_release_manifest_fails() -> None:
    checked = _checked(1)
    rows = _sides(IDENTITY, (_row(15),))
    del rows["release_manifest"]
    with pytest.raises(LoadRefusal) as caught:
        verify_staged(rows, rows, checked)
    assert caught.value.reason == "store_verification_failed"


def test_digest_is_blind_to_insert_order() -> None:
    columns = (ColumnSpec("value", "int", False),)
    first = ({"value": 15}, {"value": 16})
    second = ({"value": 16}, {"value": 15})
    assert digest_rows(first, columns, ("value",)) == digest_rows(
        second, columns, ("value",)
    )
    third = ({"value": 15}, {"value": 17})
    assert digest_rows(first, columns, ("value",)) != digest_rows(
        third, columns, ("value",)
    )


def test_decimal_half_even_at_six_places() -> None:
    columns = (ColumnSpec("value", "decimal(18,6)", False),)
    tie = ({"value": Decimal("0.0000015")},)
    even = ({"value": Decimal("0.000002")},)
    below = ({"value": Decimal("0.0000014")},)
    assert digest_rows(tie, columns, ("value",)) == digest_rows(
        even, columns, ("value",)
    )
    assert digest_rows(tie, columns, ("value",)) != digest_rows(
        below, columns, ("value",)
    )


def test_timestamp_keeps_its_time() -> None:
    columns = (ColumnSpec("built", "timestamp", False),)
    morning = ({"built": datetime(2026, 1, 2, 3, 4, 5)},)
    midnight = ({"built": datetime(2026, 1, 2, 0, 0, 0)},)
    assert digest_rows(morning, columns, ("built",)) != digest_rows(
        midnight, columns, ("built",)
    )


def test_staging_failure_leaves_no_receipt_and_no_reader_file(tmp_path: Path) -> None:
    stand = _StandIn(fail="CREATE SCHEMA")
    with pytest.raises(LoadRefusal) as caught:
        load_checked(stand, _checked(1, tmp_path))
    assert caught.value.reason == "engine_operation_failed"
    assert SECRET not in str(caught.value)
    assert not (tmp_path / RECEIPT_NAME).exists()
    assert not (tmp_path / READER_NAME).exists()
    assert not (tmp_path / PARTIAL_READER).exists()


def test_owner_role_unavailable_exits_3_and_is_never_skipped() -> None:
    for role, superuser in (("other", False), ("eii_owner", True)):
        with pytest.raises(LoadRefusal) as caught:
            require_owner(role, superuser)
        assert caught.value.reason == "owner_role_unavailable"
        assert caught.value.exit_code == 3
    require_owner("eii_owner", False)


def test_superuser_or_another_role_is_refused(tmp_path: Path) -> None:
    for stand in (_StandIn(role="other"), _StandIn(superuser=True)):
        with pytest.raises(LoadRefusal) as caught:
            load_checked(stand, _checked(1, tmp_path))
        assert caught.value.reason == "owner_role_unavailable"
        assert caught.value.exit_code == 3
        assert not any(
            sql.startswith("CREATE") or sql.startswith("DROP")
            for sql in stand.statements
        )


def test_postgres_not_answering_exits_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "eii_product.store.loader.check_release",
        lambda folder: _checked(1, folder),
    )

    def connect(**_kwargs: object) -> object:
        raise PostgresNotAnswering()

    code, err = _run(tmp_path, connect)
    assert code == 3
    assert "postgres_not_answering" in err


def test_owner_cannot_connect_exits_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "eii_product.store.loader.check_release",
        lambda folder: _checked(1, folder),
    )

    def connect(**_kwargs: object) -> object:
        raise OwnerConnectFailed()

    code, err = _run(tmp_path, connect)
    assert code == 3
    assert code != 4
    assert "owner_role_unavailable" in err


def test_driver_error_text_is_not_printed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "eii_product.store.loader.check_release",
        lambda folder: _checked(1, folder),
    )

    def connect(**_kwargs: object) -> object:
        raise RuntimeError(SECRET)

    code, err = _run(tmp_path, connect)
    assert code == 1
    assert SECRET not in err
    assert "engine_operation_failed" in err
    refusal = refusal_from_connect(RuntimeError(SECRET))
    assert SECRET not in str(refusal)


def test_password_is_never_an_argument() -> None:
    kwargs = owner_connect_kwargs("127.0.0.1", 55440, "invented")
    assert "password" not in kwargs
    assert kwargs == {
        "dbname": "invented",
        "host": "127.0.0.1",
        "port": 55440,
        "user": "eii_owner",
    }


def test_another_extension_is_refused_before_anything_is_created(
    tmp_path: Path,
) -> None:
    stand = _StandIn(extensions=("fuzzystrmatch", "plpgsql", "postgis"))
    with pytest.raises(LoadRefusal) as caught:
        load_checked(stand, _checked(1, tmp_path))
    assert caught.value.reason == "extension_not_allowed"
    assert caught.value.exit_code == 1
    assert not any("CREATE" in sql or "DROP" in sql for sql in stand.statements)
    with pytest.raises(LoadRefusal) as direct:
        require_extensions(("plpgsql", "postgis", "postgis_topology"))
    assert direct.value.reason == "extension_not_allowed"


def test_loader_never_creates_or_drops_an_extension_or_database(tmp_path: Path) -> None:
    stand = _StandIn(fail="CREATE TABLE")
    with pytest.raises(LoadRefusal):
        load_checked(stand, _checked(1, tmp_path))
    joined = "\n".join(stand.statements)
    assert "CREATE EXTENSION" not in joined
    assert "DROP EXTENSION" not in joined
    assert "CREATE DATABASE" not in joined
    assert "DROP DATABASE" not in joined


def test_geometry_is_loaded_with_srid_4326(tmp_path: Path) -> None:
    sql = geometry_alter("r_" + IDENTITY[:16], "ext_invented", "district", "geometry")
    assert 'USING "ext_invented".ST_GeomFromWKB("geometry", 4326)' in sql
    assert "geometry(Geometry,4326)" in sql
    with pytest.raises(LoadRefusal) as quote:
        geometry_alter("r_" + IDENTITY[:16], "bad name", "district", "geometry")
    assert quote.value.reason == "extension_schema_invalid"
    assert quote.value.exit_code == 1
    stand = _StandIn(schema="bad name")
    with pytest.raises(LoadRefusal) as spaced:
        load_checked(stand, _checked(1, tmp_path))
    assert spaced.value.reason == "extension_schema_invalid"
    assert not any(
        sql.startswith(("BEGIN", "CREATE", "DROP", "ALTER", "COPY"))
        for sql in stand.statements
    )
    checked = _geometry_checked()
    left = _geometry_sides(POINT)
    with pytest.raises(LoadRefusal) as srid:
        verify_staged(left, left, checked, {"district": (0,)})
    assert srid.value.reason == "store_verification_failed"
    assert srid.value.exit_code == 4


def test_each_exit_code_is_the_ruled_one(tmp_path: Path) -> None:
    code, err = _run(tmp_path, _unused_connect)
    assert code == 4
    assert "release_missing" in err
    assert LoadRefusal("schema_exists").exit_code == 1
    assert LoadRefusal("extension_not_allowed").exit_code == 1
    assert LoadRefusal("extension_schema_invalid").exit_code == 1
    assert LoadRefusal("store_verification_failed").exit_code == 4
    assert LoadRefusal("postgres_not_answering").exit_code == 3
    assert LoadRefusal("owner_role_unavailable").exit_code == 3
    assert LoadRefusal("engine_operation_failed").exit_code == 1


def _run(folder: Path, connect) -> tuple[int, str]:
    err = StringIO()
    with redirect_stderr(err):
        code = run_load(
            folder, host="127.0.0.1", port=1, database="invented", connect=connect
        )
    return code, err.getvalue()


def _unused_connect(**_kwargs: object) -> object:
    message = "connection was opened"
    raise AssertionError(message)


def _checked(count: int, folder: Path | None = None) -> CheckedRelease:
    return CheckedRelease(
        folder or Path("."),
        {
            "release_id": IDENTITY,
            "tables": [
                {
                    "file": "tables/pub_census_national.parquet",
                    "name": "pub_census_national",
                    "row_count": count,
                }
            ],
        },
        {
            "pub_census_national": (
                ColumnSpec("period", "string", False),
                ColumnSpec("indicator", "string", False),
                ColumnSpec("value", "int", False),
            )
        },
    )


def _row(value: int, indicator: str = "invented") -> dict[str, object]:
    return {"indicator": indicator, "period": "2026-01", "value": value}


def _geometry_checked() -> CheckedRelease:
    return CheckedRelease(
        Path("."),
        {
            "release_id": IDENTITY,
            "tables": [{"name": "district", "row_count": 1}],
        },
        {
            "district": (
                ColumnSpec("district_key", "string", False),
                ColumnSpec("geometry", "geometry", False, "Geometry", 4326),
            )
        },
    )


def _sides(
    identity: str,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, tuple[Mapping[str, object], ...]]:
    return {
        "pub_census_national": tuple(rows),
        "release_manifest": (_manifest(identity, "pub_census_national"),),
    }


def _geometry_sides(value: bytes) -> dict[str, tuple[Mapping[str, object], ...]]:
    return {
        "district": ({"district_key": "INVENTED-district", "geometry": value},),
        "release_manifest": (_manifest(IDENTITY, "district"),),
    }


def _manifest(identity: str, table: str) -> dict[str, object]:
    return {
        column.name: identity if column.name == "release_id" else table
        for column in RELEASE_MANIFEST_COLUMNS
    }


class _StandIn:
    stand_in = True

    def __init__(
        self,
        *,
        role: str = "eii_owner",
        superuser: bool = False,
        extensions: tuple[str, ...] = ("plpgsql", "postgis"),
        schema: str = "ext_invented",
        fail: str | None = None,
    ) -> None:
        self.role = role
        self.superuser = superuser
        self.extensions = extensions
        self.schema = schema
        self.fail = fail
        self.statements: list[str] = []

    def execute(self, sql: str, _params: object = None) -> list[tuple[object, ...]]:
        if self.fail is not None and self.fail in sql:
            raise RuntimeError(SECRET)
        self.statements.append(sql)
        if "rolsuper" in sql:
            return [(self.role, self.superuser)]
        if "extnamespace" in sql:
            return [(self.schema,)]
        if "extname" in sql:
            return [(name,) for name in self.extensions]
        return []

    def copy_rows(self, sql: str, _rows: object) -> None:
        self.statements.append(sql)

    def close(self) -> None:
        """The loader closes the connection it was given."""
