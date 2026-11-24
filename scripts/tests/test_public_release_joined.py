"""Joined build, install, load and start on an invented reviewed assembly.

Nothing is patched between the steps except the Postgres connection, which is
an in-memory stand-in on the loader's own `stand_in` seam; the embedded store
is a real DuckDB file. The real two-store proof is the lead's (open item).
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any
from unittest.mock import patch

import duckdb
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from public_assembly_fixture import approve, inputs
from s3_t28_support import WorkspaceCase

from eii_custodian.release import assembly, producer
from eii_product.store import loader
from eii_product.store.postgres import release_schema
from eii_product.store.receipt import RECEIPT_NAME, ReceiptRefusal
from eii_product.store.release_check import ReleaseRefusal
from eii_product.store.startup import StartupRefusal
from operations.config import Environment
from operations.install import install_release
from operations.runtime import check_stores

QUOTED = re.compile(r'"([^"]+)"\."([^"]+)"')
URL = "postgres://eii_app" + "@" + "127.0.0.1:5432/INVENTED_live"


class StandInStore:
    """Schemas of one invented database: {schema: {table: [row tuples]}}."""

    def __init__(self) -> None:
        self.schemas: dict[str, dict[str, list[tuple[object, ...]]]] = {}


class StandIn:
    """The loader's and startup's `stand_in` connection over one store."""

    stand_in = True

    def __init__(self, store: StandInStore, crash_on: str | None = None) -> None:
        self.store = store
        self.crash_on = crash_on

    def execute(self, sql: str, params: Any = None) -> list[tuple[object, ...]]:
        schemas = self.store.schemas
        if self.crash_on is not None and self.crash_on in sql:
            raise KeyboardInterrupt
        if "rolbypassrls" in sql:
            return [("eii_app", False, False)]
        if "rolsuper" in sql:
            return [("eii_owner", False)]
        if "extnamespace" in sql:
            return [("public",)]
        if "pg_extension" in sql:
            return [("plpgsql",), ("postgis",)]
        if "pg_namespace WHERE nspname" in sql:
            return [(params[0],)] if params[0] in schemas else []
        if "pg_class" in sql:
            return [(name,) for name in sorted(schemas.get(params[0], {}))]
        words = re.findall(r'"([^"]+)"', sql)
        if sql.startswith("CREATE SCHEMA"):
            schemas[words[0]] = {}
        elif sql.startswith("CREATE TABLE"):
            schemas[words[0]][words[1]] = []
        elif sql.startswith("ALTER SCHEMA"):
            schemas[words[1]] = schemas.pop(words[0])
        elif sql.startswith("DROP SCHEMA"):
            schemas.pop(words[0], None)
        elif sql.startswith("SELECT"):
            schema, table = QUOTED.findall(sql)[-1]
            return list(schemas[schema][table])
        return []

    def copy_rows(self, sql: str, values: list[tuple[object, ...]]) -> None:
        schema, table = QUOTED.findall(sql)[0]
        self.store.schemas[schema][table].extend(values)

    def close(self) -> None:
        """Nothing to release."""


class Joined(WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = StandInStore()
        self.identity = self.build()
        self.env = Environment(
            "live",
            self.root / "live/releases" / self.identity,
            self.root / "live/state",
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        install_release(
            self.root / "exports" / self.identity,
            self.env,
            self.root / "INVENTED-application",
        )

    def build(self) -> str:
        cache = self.root / "data/public_cache"
        inputs(cache, keyed=True)
        approve(cache)
        producer.produce(cache)
        built = self.root / "exports/INVENTED-building"
        identity = assembly.build(cache, built)
        built.rename(built.parent / identity)
        return identity

    def load(self, crash_on: str | None = None) -> None:
        loader.perform(
            self.env.release,
            host="127.0.0.1",
            port=5432,
            database="INVENTED_live",
            connect=lambda **_: StandIn(self.store, crash_on),
        )

    def start(self) -> Any:
        return check_stores(
            self.env,
            {"EII_DATABASE_URL": URL},
            connect=lambda _: StandIn(self.store),
        )

    def refused(self, reason: str) -> None:
        with self.assertRaises(
            (ReceiptRefusal, ReleaseRefusal, StartupRefusal)
        ) as caught:
            self.start()
        self.assertEqual(getattr(caught.exception, "reason", None), reason)

    def receipt(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(
            (self.env.release / RECEIPT_NAME).read_bytes()
        )
        return loaded

    def write_receipt(self, body: dict[str, Any]) -> None:
        (self.env.release / RECEIPT_NAME).write_text(json.dumps(body))

    def tables(self) -> dict[str, list[tuple[object, ...]]]:
        return self.store.schemas[release_schema(self.identity)]

    def test_green_build_install_load_start_with_identical_stores(self) -> None:
        self.load()
        checked = self.start()
        self.assertEqual(checked.document["release_id"], self.identity)
        receipt = self.receipt()
        self.assertEqual(receipt["state"], "complete")
        self.assertEqual(receipt["release_id"], self.identity)
        self.assertEqual(receipt["engines"], ["embedded", "postgres"])
        self.assertEqual(set(receipt["tables"]), set(self.tables()))
        self.assertEqual(list(self.store.schemas), [release_schema(self.identity)])
        # Reinstalling the same bytes beside the load outputs changes nothing.
        install_release(
            self.root / "exports" / self.identity,
            self.env,
            self.root / "INVENTED-application",
        )
        self.assertIs(type(self.start()), type(checked))
        # No fallback: live never starts on the embedded store alone.
        with self.assertRaises(StartupRefusal) as caught:
            check_stores(self.env, {}, embedded=True)
        self.assertEqual(caught.exception.reason, "embedded_environment_refused")

    def test_missing_receipt(self) -> None:
        self.load()
        (self.env.release / RECEIPT_NAME).unlink()
        self.refused("receipt_missing")

    def test_incomplete_receipt_state(self) -> None:
        self.load()
        self.write_receipt(dict(self.receipt(), state="loading"))
        self.refused("receipt_not_complete")

    def test_incomplete_receipt_inventory(self) -> None:
        for field in ("tables", "digests", "row_counts"):
            with self.subTest(field=field):
                self.store = StandInStore()
                for name in ("release.duckdb", RECEIPT_NAME):
                    (self.env.release / name).unlink(missing_ok=True)
                self.load()
                body = self.receipt()
                if field == "tables":
                    body[field] = [n for n in body[field] if n != "pub_bank_credit"]
                else:
                    body[field].pop("pub_bank_credit")
                self.write_receipt(body)
                self.refused("startup_parity_failed")

    def test_foreign_receipt(self) -> None:
        self.load()
        self.write_receipt(dict(self.receipt(), release_id="bc" * 32))
        self.refused("receipt_release_mismatch")

    def test_store_divergence_on_either_side(self) -> None:
        self.load()
        rows = self.tables()["pub_bank_credit"]
        original = list(rows)
        rows[0] = (*rows[0][:-1], "INVENTED-diverged")
        self.refused("startup_parity_failed")
        rows[:] = original
        self.start()
        with duckdb.connect(str(self.env.release / "release.duckdb")) as connection:
            connection.execute("UPDATE pub_bank_credit SET source_id = 'INVENTED-x'")
        self.refused("startup_parity_failed")

    def test_extra_table_in_postgres_embedded_or_folder(self) -> None:
        self.load()
        self.tables()["INVENTED_extra"] = []
        self.refused("startup_inventory_mismatch")
        del self.tables()["INVENTED_extra"]
        self.start()
        reader = self.env.release / "release.duckdb"
        with duckdb.connect(str(reader)) as connection:
            connection.execute('CREATE TABLE "INVENTED_extra" (x INTEGER)')
        self.refused("startup_inventory_mismatch")
        with duckdb.connect(str(reader)) as connection:
            connection.execute('DROP TABLE "INVENTED_extra"')
        self.start()
        extra = self.env.release / "INVENTED_extra.json"
        extra.write_bytes(b"{}")
        self.refused("startup_inventory_mismatch")
        extra.unlink()
        self.start()
        (self.env.release / "tables/INVENTED_extra.parquet").write_bytes(b"INVENTED")
        self.refused("unlisted_table")

    def test_interrupted_first_load(self) -> None:
        # A killed loader runs no cleanup: the stage and partial reader remain.
        with (
            patch("eii_product.store.loader._abandon"),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.load(crash_on="RENAME TO")
        self.assertTrue((self.env.release / loader.PARTIAL_READER).exists())
        self.assertFalse((self.env.release / RECEIPT_NAME).exists())
        self.refused("interrupted_load_refused")

    def test_interrupted_reload_beside_a_complete_one(self) -> None:
        self.load()
        stage = loader.staging_schema(self.identity)
        self.store.schemas[stage] = copy.deepcopy(self.tables())
        self.refused("interrupted_load_refused")

    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(data=st.data())
    def test_any_one_postgres_row_change_diverges(self, data: st.DataObject) -> None:
        if not (self.env.release / RECEIPT_NAME).exists():
            self.load()
        saved = copy.deepcopy(self.store.schemas)
        try:
            tables = self.tables()
            name = data.draw(st.sampled_from(sorted(n for n in tables if tables[n])))
            rows = tables[name]
            index = data.draw(st.integers(0, len(rows) - 1))
            text = [i for i, v in enumerate(rows[index]) if isinstance(v, str)]
            kind = data.draw(st.sampled_from(["drop", "duplicate", "value"]))
            if kind == "drop":
                del rows[index]
            elif kind == "duplicate":
                rows.append(rows[index])
            else:
                column = data.draw(st.sampled_from(text))
                row = list(rows[index])
                row[column] = "INVENTED-" + str(row[column])
                rows[index] = tuple(row)
            self.refused(
                "startup_identity_mismatch"
                if name == "release_manifest"
                else "startup_parity_failed"
            )
        finally:
            self.store.schemas = saved
