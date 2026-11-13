"""Offline binding, normalisation, refusal and real DuckDB tests; no PostgreSQL IO."""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import sys
import unittest
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal, localcontext
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
import live_store_spike as live
import psycopg

import store_spike as spike
import store_spike_fixture as fixture
from store_spike_normalise import (
    ParityMismatch,
    QueryResult,
    SpikeRefusal,
    compare,
    normalise,
)


def synthetic_url(authority: str) -> str:
    return "postgresql://SYN-user" + "@" + authority + "/SYN-db"


class ComparisonTests(unittest.TestCase):
    def test_deliberate_integer_divergence_fails(self) -> None:
        original = QueryResult("SYN-fixture", ("count_value",), ((1,),))
        changed = QueryResult("SYN-fixture", ("count_value",), ((2,),))
        with self.assertRaisesRegex(ParityMismatch, "field mismatch row=0 column=0"):
            compare(original, changed)

    def test_complete_result_plants(self) -> None:
        original = fixture.expected(list(fixture.UNITS))
        row = original.rows[0]
        changed_row = (*row[:3], Decimal(cast(int, row[3])), row[4])
        plants = (
            (replace(original, fixture_id="SYN-wrong"), "fixture identity"),
            (replace(original, columns=("SYN-other",)), "column mismatch"),
            (replace(original, rows=original.rows[:-1]), "row count"),
            (replace(original, rows=original.rows[::-1]), "field mismatch"),
            (replace(original, rows=(row[:-1], *original.rows[1:])), "row width"),
            (
                replace(original, rows=(changed_row, *original.rows[1:])),
                "field mismatch",
            ),
            (
                replace(original, rows=(("SYN-other", *row[1:]), *original.rows[1:])),
                "field mismatch",
            ),
        )
        for changed, reason in plants:
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ParityMismatch, reason):
                    compare(original, changed)
                with self.assertRaisesRegex(ParityMismatch, reason):
                    compare(changed, original)

    def test_equal_results_and_empty_results(self) -> None:
        for units in ([], list(fixture.UNITS)):
            compare(fixture.expected(units), fixture.expected(units))

    def test_decimal_comparison_is_after_rounding(self) -> None:
        def value(raw: str) -> QueryResult:
            return QueryResult(
                "SYN-fixture", ("decimal_control",), ((normalise(Decimal(raw)),),)
            )

        compare(value("1.2345645"), value("1.2345644"))
        with self.assertRaises(ParityMismatch):
            compare(value("1.2345645"), value("1.2345655"))


class NormaliseTests(unittest.TestCase):
    def test_integral_types_are_int(self) -> None:
        for value in (0, -3, Decimal("3.000"), 3.0, -0.0, Decimal("1E+40")):
            with self.subTest(value=value):
                self.assertIs(type(normalise(value)), int)
                self.assertEqual(normalise(value), int(value))

    def test_half_even_positive_negative_even_odd(self) -> None:
        for raw, wanted in (
            ("1.2345645", "1.234564"),
            ("1.2345655", "1.234566"),
            ("-1.2345645", "-1.234564"),
            ("-1.2345655", "-1.234566"),
            ("0.9999999", "1.000000"),
            ("0.0000001", "0.000000"),
            ("0.0000015", "0.000002"),
        ):
            with self.subTest(raw=raw), localcontext() as context:
                context.rounding = ROUND_DOWN
                context.prec = 4
                result = normalise(Decimal(raw))
                self.assertIs(type(result), Decimal)
                self.assertEqual(result, Decimal(wanted))
                self.assertEqual(cast(Decimal, result).as_tuple().exponent, -6)

    def test_large_decimal_does_not_use_ambient_precision(self) -> None:
        value = Decimal("123456789012345678901234567890.1234565")
        self.assertEqual(
            normalise(value), Decimal("123456789012345678901234567890.123456")
        )

    def test_float_uses_repr_before_rounding(self) -> None:
        value = 0.0000025
        self.assertNotEqual(
            Decimal(value).quantize(Decimal("0.000001")),
            Decimal(repr(value)).quantize(Decimal("0.000001")),
        )
        self.assertEqual(normalise(value), normalise(Decimal(repr(value))))

    def test_text_date_datetime_and_null(self) -> None:
        self.assertEqual(normalise("SYN-e\u0301"), "SYN-é")
        self.assertEqual(normalise(date(2000, 1, 1)), date(2000, 1, 1))
        self.assertIs(type(normalise(datetime(2000, 1, 1, 12))), date)
        self.assertEqual(normalise(datetime(2000, 1, 1, 12)), date(2000, 1, 1))
        self.assertIsNone(normalise(None))

    def test_unsupported_and_nonfinite_refuse(self) -> None:
        for value in (
            True,
            False,
            b"SYN",
            [],
            {},
            object(),
            complex(1, 2),
            float("nan"),
            float("inf"),
            float("-inf"),
            Decimal("NaN"),
            Decimal("sNaN"),
            Decimal("Infinity"),
        ):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(SpikeRefusal):
                    normalise(value)


class BindingTests(unittest.TestCase):
    def test_whole_tokens_for_both_drivers(self) -> None:
        sql = "SELECT :units, :units_more, :x_2, CAST(:units AS TEXT)"
        for engine, wanted in (
            (
                "postgres",
                "SELECT %(units)s, %(units_more)s, %(x_2)s, CAST(%(units)s AS TEXT)",
            ),
            ("embedded", "SELECT $units, $units_more, $x_2, CAST($units AS TEXT)"),
        ):
            self.assertEqual(spike.translate(sql, cast(spike.Engine, engine)), wanted)
        self.assertEqual(
            spike.translate("x::text x:units :Units :3bad :unitsUpper", "embedded"),
            "x::text x:units :Units :3bad :unitsUpper",
        )
        with self.assertRaisesRegex(SpikeRefusal, "unknown engine"):
            spike.translate(sql, cast(spike.Engine, "unknown"))

    def test_bound_value_never_enters_query_and_lists_are_copied(self) -> None:
        for engine in ("postgres", "embedded"):
            for units in ([], ["SYN-unit-' OR 'x'='x"]):
                sql, values = spike.prepare(spike.QUERY_NAME, {"units": units}, engine)
                self.assertEqual(values, {"units": units})
                self.assertIsNot(values["units"], units)
                for unit in units:
                    self.assertNotIn(unit, sql)
                self.assertNotIn(":units", sql)

    def test_unknown_query_missing_extra_wrong_parameters(self) -> None:
        for name, params in (
            ("unknown", {"units": []}),
            ("SELECT 1", {"units": []}),
            (spike.QUERY_NAME, {}),
            (spike.QUERY_NAME, {"units": [], "extra": []}),
            (spike.QUERY_NAME, {"units": "SYN-unit-a"}),
            (spike.QUERY_NAME, {"units": ()}),
            (spike.QUERY_NAME, {"units": [None]}),
            (spike.QUERY_NAME, {"units": [1]}),
            (spike.QUERY_NAME, {"units": ["SYN-unit-a", True]}),
        ):
            with self.subTest(name=name, params=params):
                with self.assertRaises(SpikeRefusal):
                    spike.prepare(name, params, "embedded")

    def test_headers_query_hash_and_shape(self) -> None:
        raw = spike.SQL_PATH.read_bytes()
        text = raw.decode("utf-8")
        self.assertEqual(spike.query_hash(), hashlib.sha256(raw).hexdigest())
        self.assertIn(f"-- name: {spike.QUERY_NAME}\n", text)
        self.assertIn("-- params: units list[text]\n", text)
        self.assertIn("-- order: label, unit_id\n", text)
        self.assertIn(
            "-- returns: unit_id text, label text, period date, count_value bigint, decimal_control numeric\n",
            text,
        )
        self.assertIn("SUM(p.count_value)", text)
        self.assertIn("p.label ASC NULLS LAST, p.unit_id ASC NULLS LAST", text)
        self.assertNotIn(";", text)

    def test_result_columns_width_and_scalars(self) -> None:
        with self.assertRaisesRegex(SpikeRefusal, "columns"):
            spike.result(("SYN-other",), [])
        with self.assertRaisesRegex(SpikeRefusal, "width"):
            spike.result(fixture.COLUMNS, [(1,)])
        with self.assertRaisesRegex(SpikeRefusal, "unsupported"):
            spike.result(fixture.COLUMNS, [(True,) * len(fixture.COLUMNS)])
        compare(spike.result(fixture.COLUMNS, []), fixture.expected([]))

    def test_both_adapters_bind_and_reject_missing_description(self) -> None:
        expected = fixture.expected(list(fixture.UNITS))
        for engine in ("embedded", "postgres"):
            connection = MagicMock()
            cursor = (
                connection.execute.return_value
                if engine == "embedded"
                else connection.cursor.return_value.__enter__.return_value
            )
            cursor.description = (
                [(name,) for name in fixture.COLUMNS]
                if engine == "embedded"
                else [type("Column", (), {"name": name})() for name in fixture.COLUMNS]
            )
            cursor.fetchall.return_value = expected.rows
            store = (
                spike.DuckStore(connection)
                if engine == "embedded"
                else spike.PostgresStore(connection)
            )
            compare(
                store.fetch(spike.QUERY_NAME, {"units": list(fixture.UNITS)}), expected
            )
            sql, values = (
                connection.execute if engine == "embedded" else cursor.execute
            ).call_args.args
            self.assertEqual(values, {"units": list(fixture.UNITS)})
            self.assertIn("$units" if engine == "embedded" else "%(units)s", sql)
            cursor.description = None
            with self.assertRaisesRegex(SpikeRefusal, "description"):
                store.fetch(spike.QUERY_NAME, {"units": []})


class FixtureTests(unittest.TestCase):
    def test_fixed_fixture_content_identity(self) -> None:
        self.assertEqual(
            fixture.FIXTURE_ID,
            "e9a2855d1a9d84a4ceedcaf2db1fe689b5c91af4e239431a16cef5d7e0e9baee",
        )

    def test_reader_configuration_is_locked_and_external_access_disabled(self) -> None:
        with fixture.duck_fixture() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT current_setting('enable_external_access'), "
                    "current_setting('lock_configuration')"
                ).fetchall(),
                [(False, True)],
            )
            with self.assertRaises(duckdb.Error):
                connection.execute("SET threads = 1")

    def test_both_postgres_text_columns_have_c_collation(self) -> None:
        self.assertIn('unit_id TEXT COLLATE "C" NOT NULL', fixture.PG_CREATE)
        self.assertIn('label TEXT COLLATE "C"', fixture.PG_CREATE)

    def test_identity_and_expected_order(self) -> None:
        payload = json.loads(fixture.FIXTURE_BYTES)
        self.assertEqual(payload["name"], "SYN-store-spike-v1")
        self.assertEqual(payload["columns"], list(fixture.COLUMNS))
        self.assertEqual(len(payload["rows"]), len(fixture.ROWS))
        self.assertEqual(
            fixture.FIXTURE_ID, hashlib.sha256(fixture.FIXTURE_BYTES).hexdigest()
        )
        wanted_units = (
            "SYN-unit-g",
            "SYN-unit-f",
            "SYN-unit-b",
            "SYN-unit-e",
            "SYN-unit-a",
            "SYN-unit-d",
            "SYN-unit-c",
        )
        self.assertEqual(
            tuple(row[0] for row in fixture.expected(list(fixture.UNITS)).rows),
            wanted_units,
        )

    def test_real_duckdb_query_empty_subset_quote_and_readonly(self) -> None:
        with fixture.duck_fixture() as connection:
            store = spike.DuckStore(connection)
            for units in (
                list(fixture.UNITS),
                [],
                [fixture.UNITS[0]],
                ["SYN-unit-' OR 'x'='x"],
            ):
                compare(
                    fixture.expected(units),
                    store.fetch(spike.QUERY_NAME, {"units": units}),
                )
            for sql in (
                "INSERT INTO spike_control SELECT * FROM spike_control",
                "SET enable_external_access = true",
            ):
                with self.assertRaises(duckdb.Error):
                    connection.execute(sql)
        with self.assertRaises(duckdb.Error):
            connection.execute("SELECT 1")

    def test_real_duckdb_divergence_fails(self) -> None:
        with fixture.duck_fixture(diverge=True) as connection:
            with self.assertRaisesRegex(ParityMismatch, "field mismatch"):
                compare(
                    fixture.expected(list(fixture.UNITS)),
                    spike.DuckStore(connection).fetch(
                        spike.QUERY_NAME, {"units": list(fixture.UNITS)}
                    ),
                )

    def test_duckdb_files_removed_on_success_and_failure(self) -> None:
        real_connect = duckdb.connect
        for fail in (False, True):
            with patch("duckdb.connect", wraps=real_connect) as connect:
                try:
                    with fixture.duck_fixture():
                        path = Path(connect.call_args.args[0])
                        self.assertTrue(path.is_file())
                        self.assertEqual(connect.call_args.kwargs, {"read_only": True})
                        if fail:
                            raise SpikeRefusal("SYN-body-failed")
                except SpikeRefusal as error:
                    self.assertEqual(str(error), "SYN-body-failed")
                self.assertFalse(path.parent.exists())

    def test_duckdb_closes_after_setup_failures(self) -> None:
        for failure_point in ("writer", "reader"):
            writer, reader = MagicMock(), MagicMock()
            failing = writer if failure_point == "writer" else reader
            failing.execute.side_effect = RuntimeError("SYN-failure")
            with patch("duckdb.connect", side_effect=[writer, reader]) as connect:
                with (
                    self.assertRaisesRegex(RuntimeError, "SYN-failure"),
                    fixture.duck_fixture(),
                ):
                    self.fail("setup must refuse")
            writer.close.assert_called_once()
            if failure_point == "reader":
                reader.close.assert_called_once()
            self.assertFalse(Path(connect.call_args.args[0]).parent.exists())

    def test_database_target_refusals_and_configured_port(self) -> None:
        for raw, reason in (
            ("", "missing"),
            ("SYN-malformed", "invalid"),
            (synthetic_url("127.0.0.1"), "invalid"),
            (synthetic_url("example.invalid:55440"), "loopback"),
        ):
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(SpikeRefusal, reason),
            ):
                fixture.database_target({"EII_DATABASE_URL": raw})
        for port in (55440, 55441):
            target = fixture.database_target(
                {"EII_DATABASE_URL": synthetic_url(f"127.0.0.1:{port}")}
            )
            self.assertEqual(target.port, port)
            self.assertIsNone(target.password)

    def test_postgres_temp_setup_bound_rows_and_cleanup(self) -> None:
        env = {"EII_DATABASE_URL": synthetic_url("127.0.0.1:55441")}
        for phase in ("success", "setup", "body", "rollback"):
            connection = MagicMock()
            if phase == "setup":
                connection.execute.side_effect = RuntimeError("SYN-setup")
            if phase == "rollback":
                connection.rollback.side_effect = RuntimeError("SYN-rollback")
            with patch("psycopg.connect", return_value=connection) as connect:
                try:
                    with fixture.postgres_fixture(env) as opened:
                        self.assertIs(opened, connection)
                        if phase == "body":
                            raise RuntimeError("SYN-body")
                except RuntimeError as error:
                    self.assertEqual(str(error), f"SYN-{phase}")
                else:
                    self.assertEqual(phase, "success")
            self.assertEqual(
                connect.call_args.kwargs,
                {
                    "host": "127.0.0.1",
                    "port": 55441,
                    "dbname": "SYN-db",
                    "user": "SYN-user",
                    "password": None,
                    "connect_timeout": 5,
                },
            )
            connection.rollback.assert_called_once()
            connection.close.assert_called_once()
            connection.commit.assert_not_called()
            if phase == "success":
                self.assertEqual(
                    [call.args[0] for call in connection.execute.call_args_list],
                    [
                        "SET LOCAL search_path = pg_temp",
                        "SET LOCAL statement_timeout = '5s'",
                        fixture.PG_CREATE,
                    ],
                )
                self.assertIn('TEXT COLLATE "C"', fixture.PG_CREATE)
                self.assertIn("CREATE TEMPORARY TABLE", fixture.PG_CREATE)
                self.assertIn("ON COMMIT DROP", fixture.PG_CREATE)
                connection.cursor.return_value.__enter__.return_value.executemany.assert_called_once_with(
                    fixture.PG_INSERT, fixture.ROWS
                )


class LiveContractTests(unittest.TestCase):
    def call_main(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = live.main(args, {})
        return code, output.getvalue()

    def test_configuration_error_and_usage_never_connect(self) -> None:
        with patch("psycopg.connect") as connect:
            self.assertEqual(
                self.call_main([]),
                (1, "FAIL store-spike: database environment missing\n"),
            )
            for args in (["SYN-unknown"], ["--diverge", "--diverge"]):
                code, out = self.call_main(args)
                self.assertEqual(code, 2)
                self.assertIn("usage:", out)
            connect.assert_not_called()

    def test_driver_error_and_canary_are_redacted(self) -> None:
        canary = "SYN-canary-not-a-credential"
        for error, code, diagnostic in (
            (psycopg.OperationalError(canary), 1, "engine operation failed"),
            (ImportError(canary), 1, "driver missing; install the engine group"),
            (SpikeRefusal("unsupported scalar"), 1, "unsupported scalar"),
            (
                ParityMismatch("field mismatch row=0 column=3"),
                3,
                "field mismatch row=0 column=3",
            ),
        ):
            with patch.object(live, "run_live", side_effect=error):
                actual, out = self.call_main([])
            self.assertEqual(actual, code)
            self.assertEqual(out, f"FAIL store-spike: {diagnostic}\n")
            self.assertNotIn(canary, out)

    def test_real_import_and_connection_refusals_with_mocks(self) -> None:
        original_import = builtins.__import__
        for module in ("duckdb", "psycopg"):

            def missing(
                name: str,
                globals: Mapping[str, object] | None = None,
                locals: Mapping[str, object] | None = None,
                fromlist: Sequence[str] = (),
                level: int = 0,
                *,
                missing_module: str = module,
            ) -> object:
                if name == missing_module:
                    raise ImportError("SYN-canary")
                return original_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=missing):
                code, out = self.call_main([])
            self.assertEqual(code, 1)
            self.assertIn("driver missing", out)
        with patch(
            "psycopg.connect", side_effect=psycopg.OperationalError("SYN-canary")
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                code = live.main(
                    [],
                    {"EII_DATABASE_URL": synthetic_url("127.0.0.1:55440")},
                )
            self.assertEqual(code, 1)
            self.assertEqual(
                output.getvalue(), "FAIL store-spike: engine operation failed\n"
            )

    def test_live_orchestration_pass_divergence_and_corrupt_baseline(self) -> None:
        for diverge, corrupt in ((False, False), (True, False), (False, True)):
            pg = MagicMock()
            pg.info.server_version = 180000
            store = MagicMock()

            def fetch(
                query: str,
                params: dict[str, list[str]],
                *,
                corrupt_result: bool = corrupt,
            ) -> QueryResult:
                self.assertEqual(query, spike.QUERY_NAME)
                wanted = fixture.expected(params["units"])
                return replace(wanted, rows=()) if corrupt_result else wanted

            store.fetch.side_effect = fetch
            with (
                patch.object(live, "postgres_fixture") as resource,
                patch.object(live, "PostgresStore", return_value=store),
            ):
                resource.return_value.__enter__.return_value = pg
                code, out = self.call_main(["--diverge"] if diverge else [])
            self.assertEqual(code, 3 if diverge or corrupt else 0)
            if corrupt:
                self.assertNotIn("PASS", out)
            else:
                self.assertIn("PASS store-spike: both engines match", out)
                evidence = json.loads(out.splitlines()[1])
                self.assertEqual(evidence["fixture_sha256"], fixture.FIXTURE_ID)
                self.assertEqual(evidence["query_sha256"], spike.query_hash())
                self.assertEqual(evidence["fixture_rows"], len(fixture.ROWS))
                self.assertEqual(evidence["result_rows"], len(fixture.UNITS))
                self.assertEqual(
                    evidence["ordered_rows"],
                    json.loads(
                        json.dumps(
                            fixture.expected(list(fixture.UNITS)).rows, default=str
                        )
                    ),
                )
                self.assertEqual(
                    [call.args for call in store.fetch.call_args_list],
                    [
                        (spike.QUERY_NAME, {"units": units})
                        for units in (
                            list(fixture.UNITS),
                            [],
                            [fixture.UNITS[0]],
                            ["SYN-unit-' OR 'x'='x"],
                        )
                    ],
                )
            if diverge:
                self.assertIn("FAIL store-spike: field mismatch", out)

    def test_no_baseline_and_undetected_divergence_refuse(self) -> None:
        for empty in (False, True):
            with (
                patch.object(live, "postgres_fixture"),
                patch.object(live, "DuckStore"),
                patch.object(live, "PostgresStore") as store,
                patch.object(live, "compare"),
            ):
                store.return_value.fetch.return_value = replace(
                    fixture.expected([]),
                    rows=() if empty else fixture.expected(list(fixture.UNITS)).rows,
                )
                code, out = self.call_main(["--diverge"])
            self.assertEqual(code, 1)
            self.assertIn(
                "baseline result missing" if empty else "divergence was not detected",
                out,
            )
