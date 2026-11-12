"""Database probe tests (D01-D12)."""

from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_database as database
import preflight_proc as proc


def _host() -> str:
    return "127" + ".0.0.1"


def _pg_url(
    user: str,
    port: int,
    database: str,
    *,
    host: str | None = None,
    password: str | None = None,
    scheme: str = "postgresql",
) -> str:
    host = host or _host()
    at = "@" + host
    if password is None:
        return f"{scheme}://{user}{at}:{port}/{database}"
    return f"{scheme}://{user}:{password}{at}:{port}/{database}"


class DatabaseProbe(unittest.TestCase):
    """URL parsing, probes and store selection."""

    def test_valid_urls(self) -> None:
        """D01: parse_database_url accepts six URL forms."""
        pw_plain = stubs.dummy("p")
        enc_ud_pw = stubs.dummy("p")
        labels = [
            "plain",
            "encoded_password",
            "postgres_scheme",
            "upper_scheme",
            "ipv6",
            "no_password",
            "lone_percent_password",
            "encoded_user_database",
        ]
        cases: list[tuple[str, database.DbTarget, str]] = [
            (
                stubs.database_url(pw_plain, 55440),
                database.DbTarget("127.0.0.1", 55440, "eii_app", pw_plain, "eii"),
                "127.0.0.1:55440",
            ),
            (
                "postgresql://eii_app:"
                + quote("p@ss/word", safe="")
                + ("@" + _host())
                + ":55441/eii",
                database.DbTarget("127.0.0.1", 55441, "eii_app", "p@ss/word", "eii"),
                "127.0.0.1:55441",
            ),
            (
                _pg_url("eii_app", 55442, "eii", scheme="postgres"),
                database.DbTarget("127.0.0.1", 55442, "eii_app", None, "eii"),
                "127.0.0.1:55442",
            ),
            (
                _pg_url("eii_app", 55443, "eii", scheme="POSTGRESQL"),
                database.DbTarget("127.0.0.1", 55443, "eii_app", None, "eii"),
                "127.0.0.1:55443",
            ),
            (
                _pg_url("eii_app", 55444, "eii", host="[::1]"),
                database.DbTarget("::1", 55444, "eii_app", None, "eii"),
                "[::1]:55444",
            ),
            (
                stubs.database_url(None, 55445, user="eii_app", database="eii"),
                database.DbTarget("127.0.0.1", 55445, "eii_app", None, "eii"),
                "127.0.0.1:55445",
            ),
            (
                "postgresql://eii_app:p%" + ("@" + _host()) + ":55446/eii",
                database.DbTarget("127.0.0.1", 55446, "eii_app", "p%", "eii"),
                "127.0.0.1:55446",
            ),
            (
                "postgresql://a%40b:" + enc_ud_pw + ("@" + _host()) + ":55447/d%62",
                database.DbTarget("127.0.0.1", 55447, "a@b", enc_ud_pw, "db"),
                "127.0.0.1:55447",
            ),
        ]
        ran: list[str] = []
        for label, (url, want, where) in zip(labels, cases, strict=True):
            with self.subTest(label=label):
                ran.append(label)
                parsed = database.parse_database_url(url)
                self.assertIsInstance(parsed, database.DbTarget)
                assert isinstance(parsed, database.DbTarget)
                self.assertEqual(parsed.host, want.host)
                self.assertEqual(parsed.port, want.port)
                self.assertEqual(parsed.user, want.user)
                self.assertEqual(parsed.password, want.password)
                self.assertEqual(parsed.database, want.database)
                self.assertEqual(parsed.where(), where)
        self.assertEqual(ran, labels)

    def test_invalid_urls(self) -> None:
        """D02: parse_database_url returns fixed reasons."""
        labels = [
            "mysql",
            "query",
            "fragment",
            "two_hosts",
            "no_host",
            "notaport",
            "port_zero",
            "port_high",
            "no_port",
            "no_user",
            "no_database",
            "database_slash",
            "no_at_sign",
            "bad_parse",
            "mysql_percent",
            "no_user_no_at",
            "two_hosts_no_at",
            "user_nul",
            "password_nul",
            "database_nul",
        ]
        nul_reason = "user, password or database holds a NUL character"
        dummy = stubs.dummy("z")
        reasons = [
            "scheme is not postgresql or postgres",
            "query or fragment not allowed",
            "query or fragment not allowed",
            "more than one host",
            "no host",
            "port is not a number from 1 to 65535",
            "port is not a number from 1 to 65535",
            "port is not a number from 1 to 65535",
            "no port",
            "no user",
            "no database name",
            "no database name",
            "port is not a number from 1 to 65535",
            "cannot be parsed",
            "scheme is not postgresql or postgres",
            "no user",
            "more than one host",
            nul_reason,
            nul_reason,
            nul_reason,
        ]
        h = _host()
        at = "@" + h
        port = 55440
        urls = [
            f"mysql://{h}:1/eii",
            _pg_url("eii_app", 1, "eii") + "?host=evil",
            _pg_url("eii_app", 1, "eii") + "#frag",
            _pg_url("eii_app", 1, "eii", host="h1,h2"),
            "postgresql://eii_app@:1/eii",
            f"postgresql://eii_app{at}:notaport/eii",
            _pg_url("eii_app", 0, "eii"),
            _pg_url("eii_app", 99999, "eii"),
            f"postgresql://eii_app{at}/eii",
            f"postgresql://{at}:1/eii",
            f"postgresql://eii_app{at}:1/",
            f"postgresql://eii_app{at}:1/a/b",
            f"postgresql://eii_app:{dummy}",
            "postgresql://[::1/eii",
            "mysql://u:p%@" + "h:1/db",
            f"postgresql://{h}:1/eii",
            "postgresql://h1:1,h2:2/eii",
            f"postgresql://eii_app%00{at}:{port}/eii",
            f"postgresql://eii_app:%00{at}:{port}/eii",
            f"postgresql://eii_app{at}:{port}/eii%00",
        ]
        ran: list[str] = []
        for label, url, reason in zip(labels, urls, reasons, strict=True):
            with self.subTest(label=label):
                ran.append(label)
                got = database.parse_database_url(url)
                self.assertIsInstance(got, str)
                assert isinstance(got, str)
                self.assertEqual(got, reason)
                self.assertNotIn(dummy, got)
        self.assertEqual(ran, labels)

    def test_target_repr_hides_password(self) -> None:
        """D03: DbTarget repr omits the password."""
        secret = stubs.dummy("k")
        target = database.DbTarget("127.0.0.1", 1, "u", secret, "db")
        self.assertNotIn(secret, repr(target))

    def test_compose_port_env(self) -> None:
        """D04: compose_port_env derives the port or raises."""
        labels = ["valid", "unset", "invalid", "localhost"]
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                if label == "valid":
                    env = {"EII_DATABASE_URL": stubs.database_url(None, 55440)}
                    self.assertEqual(
                        database.compose_port_env(env),
                        "EII_COMPOSE_DB_PORT=55440\n",
                    )
                elif label == "unset":
                    with self.assertRaises(ValueError) as ctx:
                        database.compose_port_env({})
                    self.assertEqual(str(ctx.exception), "EII_DATABASE_URL is not set")
                elif label == "invalid":
                    env = {"EII_DATABASE_URL": "mysql://x"}
                    with self.assertRaises(ValueError) as ctx:
                        database.compose_port_env(env)
                    self.assertEqual(
                        str(ctx.exception),
                        "EII_DATABASE_URL is not a valid connection string "
                        "(scheme is not postgresql or postgres)",
                    )
                else:
                    env = {
                        "EII_DATABASE_URL": stubs.database_url(
                            None, 1, host="localhost"
                        )
                    }
                    with self.assertRaises(ValueError) as ctx:
                        database.compose_port_env(env)
                    self.assertEqual(
                        str(ctx.exception),
                        "EII_DATABASE_URL host is not 127.0.0.1",
                    )
        self.assertEqual(ran, labels)

    def test_pg_isready_outcomes(self) -> None:
        """D05: pg_isready branches without calling psql."""
        labels = [
            "not_found",
            "enoexec",
            "timeout",
            "status_2",
            "rejecting",
            "status_3",
            "garbage",
            "accepting_stderr",
            "status_7",
            "status_2_garbage",
            "host_refused",
            "status_2_stderr",
            "unset_url",
            "user_nul",
            "password_nul",
            "database_nul",
        ]
        nul_reason = "user, password or database holds a NUL character"
        h = _host()
        at = "@" + h
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            sock = stubs.loopback_socket()
            port = sock.getsockname()[1]
            sock.close()
            url = stubs.database_url(None, port)
            base_env: dict[str, str] = {"EII_DATABASE_URL": url}
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case_dir = folder / label
                    case_dir.mkdir()
                    where = f"127.0.0.1:{port}"
                    if label in ("user_nul", "password_nul", "database_nul"):
                        stubs.write_stub(case_dir, "pg_isready")
                        stubs.write_stub(case_dir, "psql")
                        if label == "user_nul":
                            url = f"postgresql://eii_app%00{at}:{port}/eii"
                        elif label == "password_nul":
                            url = f"postgresql://eii_app:%00{at}:{port}/eii"
                        else:
                            url = f"postgresql://eii_app{at}:{port}/eii%00"
                        env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                        outcome = database.probe_postgres(env, case_dir, 0.5)
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            f"EII_DATABASE_URL is not a valid connection string ({nul_reason})",
                        )
                        self.assertEqual(stubs.calls(case_dir), [])
                        continue
                    if label == "unset_url":
                        env = {"PATH": str(case_dir)}
                    elif label == "host_refused":
                        env = {
                            "PATH": str(case_dir),
                            "EII_DATABASE_URL": "postgresql://eii_app@" + "-x:1/eii",
                        }
                        stubs.write_stub(case_dir, "pg_isready")
                        stubs.write_stub(case_dir, "psql")
                    else:
                        env = dict(base_env)
                    if label != "unset_url" and label != "host_refused":
                        stubs.write_stub(case_dir, "psql")
                    if label == "not_found":
                        env["PATH"] = str(case_dir)
                    elif label == "enoexec":
                        bad = case_dir / "pg_isready"
                        bad.write_text("x", encoding="utf-8")
                        bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
                        env["PATH"] = str(case_dir)
                    elif label == "timeout":
                        stubs.write_stub(case_dir, "pg_isready", sleep=60.0)
                        env["PATH"] = str(case_dir)
                    elif label == "status_2_stderr":
                        stubs.write_stub(
                            case_dir,
                            "pg_isready",
                            status=2,
                            stdout=f"{where} - no response\n",
                            stderr="e\n",
                        )
                        env["PATH"] = str(case_dir)
                    elif label not in (
                        "unset_url",
                        "host_refused",
                        "not_found",
                        "enoexec",
                        "timeout",
                    ):
                        if label == "status_2":
                            stubs.write_stub(
                                case_dir,
                                "pg_isready",
                                status=2,
                                stdout=f"{where} - no response\n",
                            )
                        elif label == "rejecting":
                            stubs.write_stub(
                                case_dir,
                                "pg_isready",
                                status=1,
                                stdout=f"{where} - rejecting connections\n",
                            )
                        elif label == "status_3":
                            stubs.write_stub(case_dir, "pg_isready", status=3)
                        elif label == "garbage":
                            stubs.write_stub(
                                case_dir,
                                "pg_isready",
                                status=0,
                                stdout="garbage\n",
                            )
                        elif label == "accepting_stderr":
                            stubs.write_stub(
                                case_dir,
                                "pg_isready",
                                status=0,
                                stdout=f"{where} - accepting connections\n",
                                stderr="x\n",
                            )
                        elif label == "status_7":
                            stubs.write_stub(case_dir, "pg_isready", status=7)
                        else:
                            stubs.write_stub(
                                case_dir,
                                "pg_isready",
                                status=2,
                                stdout="x\n",
                            )
                        env["PATH"] = str(case_dir)
                    outcome = database.probe_postgres(env, case_dir, 0.5)
                    if label == "unset_url":
                        self.assertEqual(outcome.kind, "absent")
                        self.assertEqual(outcome.reason, "EII_DATABASE_URL is not set")
                        self.assertEqual(stubs.calls(case_dir), [])
                        continue
                    psql_called = any(
                        c["program"] == "psql" for c in stubs.calls(case_dir)
                    )
                    self.assertFalse(psql_called, label)
                    if label == "host_refused":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "a command outside the closed list was refused",
                        )
                        self.assertEqual(stubs.calls(case_dir), [])
                        continue
                    if label == "not_found":
                        self.assertEqual(outcome.kind, "absent")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready not found on PATH, so PostgreSQL cannot answer here",
                        )
                    elif label == "enoexec":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready could not be started (ENOEXEC)",
                        )
                    elif label == "timeout":
                        self.assertEqual(outcome.kind, "absent")
                        self.assertEqual(
                            outcome.reason, f"no answer on {where} within 0.5 s"
                        )
                    elif label == "status_2_stderr":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready output not understood (exit status 2)",
                        )
                    elif label == "status_2":
                        self.assertEqual(outcome.kind, "absent")
                        self.assertEqual(
                            outcome.reason,
                            f"no answer on {where} (pg_isready exit status 2)",
                        )
                    elif label == "rejecting":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL on {where} rejects connections (pg_isready exit status 1)",
                        )
                    elif label == "status_3":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready made no connection attempt (exit status 3)",
                        )
                    elif label == "garbage":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready output not understood (exit status 0)",
                        )
                    elif label == "accepting_stderr":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready output not understood (exit status 0)",
                        )
                    elif label == "status_7":
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(outcome.reason, "pg_isready exit status 7")
                    else:
                        self.assertEqual(outcome.kind, "fail")
                        self.assertEqual(
                            outcome.reason,
                            "pg_isready output not understood (exit status 2)",
                        )
        self.assertEqual(ran, labels)

    def test_psql_outcomes(self) -> None:
        """D06: psql branches after accepting pg_isready."""
        labels = [
            "missing",
            "enoexec",
            "timeout",
            "status_2",
            "stderr",
            "two_lines",
            "garbage",
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            sock = stubs.loopback_socket()
            port = sock.getsockname()[1]
            sock.close()
            where = f"127.0.0.1:{port}"
            url = stubs.database_url(None, port)
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case_dir = folder / label
                    case_dir.mkdir()
                    stubs.write_stub(
                        case_dir,
                        "pg_isready",
                        status=0,
                        stdout=f"{where} - accepting connections\n",
                    )
                    if label == "missing":
                        env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                    elif label == "enoexec":
                        bad = case_dir / "psql"
                        bad.write_text("x", encoding="utf-8")
                        bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
                        env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                    elif label == "timeout":
                        stubs.write_stub(case_dir, "psql", sleep=60.0)
                        env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                    elif label == "garbage":
                        stubs.write_stub(case_dir, "psql", status=0, stdout="garbage\n")
                        env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                    else:
                        if label == "status_2":
                            stubs.write_stub(case_dir, "psql", status=2)
                        elif label == "stderr":
                            stubs.write_stub(
                                case_dir,
                                "psql",
                                status=0,
                                stdout="180006|3.6.4\n",
                                stderr="x\n",
                            )
                        else:
                            stubs.write_stub(
                                case_dir,
                                "psql",
                                status=0,
                                stdout="180006|3.6.4\n\n",
                            )
                        env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                    outcome = database.probe_postgres(env, case_dir, 0.5)
                    self.assertEqual(outcome.kind, "fail")
                    if label == "missing":
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL answers on {where}, but psql is not found on PATH, "
                            "so its version and PostGIS cannot be checked",
                        )
                    elif label == "enoexec":
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL answers on {where}, but psql could not be started (ENOEXEC)",
                        )
                    elif label == "timeout":
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL answers on {where}, but the check query gave no result within 0.5 s",
                        )
                    elif label == "status_2":
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL answers on {where}, but the check query failed (psql exit status 2)",
                        )
                    else:
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL answers on {where}, but the check query output is not understood",
                        )
        self.assertEqual(ran, labels)

    def test_server_facts_judged(self) -> None:
        """D07: judge_server_facts version and PostGIS rules."""
        labels = [
            "good",
            "major",
            "minor_ok",
            "no_postgis",
            "postgis_37",
            "postgis_310",
            "postgis_x",
            "server_19",
            "postgis_46",
            "postgis_v",
            "two_reasons",
        ]
        outputs = [
            "180006|3.6.4\n",
            "170005|3.6.4\n",
            "180010|3.6.4\n",
            "180006|\n",
            "180006|3.7.0\n",
            "180006|3.10.0\n",
            "180006|x\n",
            "190001|3.6.4\n",
            "180006|4.6.0\n",
            "180006|v3.6.0\n",
            "170005|\n",
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            sock = stubs.loopback_socket()
            port = sock.getsockname()[1]
            sock.close()
            where = f"127.0.0.1:{port}"
            url = stubs.database_url(None, port)
            for label, stdout in zip(labels, outputs, strict=True):
                with self.subTest(label=label):
                    ran.append(label)
                    case_dir = folder / label
                    case_dir.mkdir()
                    stubs.write_stub(
                        case_dir,
                        "pg_isready",
                        status=0,
                        stdout=f"{where} - accepting connections\n",
                    )
                    stubs.write_stub(case_dir, "psql", status=0, stdout=stdout)
                    env = {"PATH": str(case_dir), "EII_DATABASE_URL": url}
                    outcome = database.probe_postgres(env, case_dir, 5.0)
                    if label == "good":
                        self.assertEqual(outcome.kind, "ok")
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL 18.6 with PostGIS 3.6.4 answers on {where}",
                        )
                    elif label == "minor_ok":
                        self.assertEqual(outcome.kind, "ok")
                        self.assertEqual(
                            outcome.reason,
                            f"PostgreSQL 18.10 with PostGIS 3.6.4 answers on {where}",
                        )
                    else:
                        self.assertEqual(outcome.kind, "fail")
                        prefix = f"PostgreSQL on {where} fails its checks: "
                        if label == "major":
                            want = prefix + "server version 17.5 is not 18.x"
                        elif label == "no_postgis":
                            want = prefix + "PostGIS is not installed in database eii"
                        elif label == "postgis_37":
                            want = prefix + "PostGIS 3.7.0 is not 3.6.x"
                        elif label == "postgis_310":
                            want = prefix + "PostGIS 3.10.0 is not 3.6.x"
                        elif label == "postgis_x":
                            want = prefix + "PostGIS version x not understood"
                        elif label == "server_19":
                            want = prefix + "server version 19.1 is not 18.x"
                        elif label == "postgis_46":
                            want = prefix + "PostGIS 4.6.0 is not 3.6.x"
                        elif label == "postgis_v":
                            want = prefix + "PostGIS version v3.6.0 not understood"
                        else:
                            want = (
                                prefix + "server version 17.5 is not 18.x; "
                                "PostGIS is not installed in database eii"
                            )
                        self.assertEqual(outcome.reason, want)
        self.assertEqual(ran, labels)

    def test_postgres_child_environments(self) -> None:
        """D08: pg_isready and psql child environments."""
        labels = ["with_password", "without_password"]
        hostile = {
            "PGHOST": "evil",
            "PGSERVICE": "evil",
            "PGOPTIONS": "evil",
            "PGSSLMODE": "evil",
            "PGPASSFILE": "/tmp/pass",
            "HOME": "/tmp/home",
        }
        password = stubs.dummy("p")
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            sock = stubs.loopback_socket()
            port = sock.getsockname()[1]
            sock.close()
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case_dir = folder / label
                    case_dir.mkdir()
                    (case_dir / "calls.jsonl").unlink(missing_ok=True)
                    stubs.write_stub(
                        case_dir,
                        "pg_isready",
                        status=0,
                        stdout=f"127.0.0.1:{port} - accepting connections\n",
                    )
                    stubs.write_stub(
                        case_dir,
                        "psql",
                        echo=True,
                        stdout="180006|3.6.4\n",
                    )
                    url = (
                        stubs.database_url(password, port)
                        if label == "with_password"
                        else stubs.database_url(None, port)
                    )
                    env = {
                        "PATH": str(case_dir),
                        **hostile,
                        "PGPASSWORD": stubs.dummy("q"),
                    }
                    env["EII_DATABASE_URL"] = url
                    database.probe_postgres(env, case_dir, 5.0)
                    calls = stubs.calls(case_dir)
                    is_ready = next(c for c in calls if c["program"] == "pg_isready")
                    psql_call = next(c for c in calls if c["program"] == "psql")
                    passfile = str(case_dir / "absent")
                    self.assertEqual(
                        is_ready["env"],
                        {
                            "PATH": str(case_dir),
                            "LANG": "C",
                            "LC_ALL": "C",
                            "PGPASSFILE": passfile,
                        },
                    )
                    want_psql: dict[str, str] = {
                        "PATH": str(case_dir),
                        "LANG": "C",
                        "LC_ALL": "C",
                        "PGHOST": "127.0.0.1",
                        "PGPORT": str(port),
                        "PGUSER": "eii_app",
                        "PGDATABASE": "eii",
                        "PGCONNECT_TIMEOUT": "5",
                        "PGPASSFILE": passfile,
                    }
                    if label == "with_password":
                        want_psql["PGPASSWORD"] = password
                    self.assertEqual(psql_call["env"], want_psql)
                    self.assertFalse(Path(passfile).exists())
                    self.assertEqual(
                        is_ready["argv"][1:],
                        ["-h", "127.0.0.1", "-p", str(port), "-t", "5"],
                    )
                    self.assertEqual(
                        psql_call["argv"][1:],
                        [
                            "-X",
                            "-w",
                            "-q",
                            "-t",
                            "-A",
                            "-F",
                            "|",
                            "-c",
                            proc.CHECK_QUERY,
                        ],
                    )
                    self.assertNotIn(password, json.dumps(is_ready["argv"]))
                    self.assertNotIn(password, json.dumps(psql_call["argv"]))
        self.assertEqual(ran, labels)

    def test_docker_outcomes(self) -> None:
        """D09: probe_docker closed outcomes."""
        labels = [
            "not_found",
            "enoexec",
            "timeout",
            "reachable",
            "empty_stdout",
            "status_1",
            "two_lines",
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case_dir = folder / label
                    case_dir.mkdir()
                    env: dict[str, str]
                    if label == "not_found":
                        env = {"PATH": str(case_dir)}
                    elif label == "enoexec":
                        bad = case_dir / "docker"
                        bad.write_text("x", encoding="utf-8")
                        bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
                        env = {"PATH": str(case_dir)}
                    elif label == "timeout":
                        stubs.write_stub(case_dir, "docker", sleep=60.0)
                        env = {"PATH": str(case_dir)}
                        out = database.probe_docker(env, case_dir, 0.5)
                        self.assertEqual(out.kind, "no_answer")
                        self.assertEqual(out.detail, "0.5")
                        continue
                    elif label == "reachable":
                        stubs.write_stub(case_dir, "docker", stdout="29.0.1\n")
                        env = {"PATH": str(case_dir)}
                    elif label == "empty_stdout":
                        stubs.write_stub(
                            case_dir,
                            "docker",
                            stdout="",
                            stderr="cannot connect\n",
                        )
                        env = {"PATH": str(case_dir)}
                    elif label == "status_1":
                        stubs.write_stub(case_dir, "docker", status=1)
                        env = {"PATH": str(case_dir)}
                    else:
                        stubs.write_stub(case_dir, "docker", stdout="1.0\n2.0\n")
                        env = {"PATH": str(case_dir)}
                    out = database.probe_docker(env, case_dir, 0.5)
                    if label == "not_found":
                        self.assertEqual(out.kind, "not_found")
                    elif label == "enoexec":
                        self.assertEqual(out.kind, "not_started")
                        self.assertEqual(out.detail, "ENOEXEC")
                    elif label == "reachable":
                        self.assertEqual(out.kind, "reachable")
                        self.assertEqual(out.detail, "29.0.1")
                    else:
                        self.assertEqual(out.kind, "unreachable")
        self.assertEqual(ran, labels)

    def test_docker_environment(self) -> None:
        """D10: docker child env pass-through."""
        labels = ["all_present", "path_only"]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            home = str(folder / "home")
            docker_cfg = str(folder / "docker")
            parent = {
                "PATH": "/bin",
                "HOME": home,
                "WSL_DISTRO_NAME": "Ubuntu",
                "DOCKER_HOST": "unix:///var/run/docker.sock",
                "DOCKER_CONTEXT": "default",
                "DOCKER_CONFIG": docker_cfg,
                "COMPOSE_PROJECT_NAME": "evil",
                "DOCKER_CERT_PATH": "/evil",
                "LD_PRELOAD": "/evil.so",
            }
            stubs.write_stub(folder, "docker", echo=True, stdout="1.0.0\n")
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    if label == "path_only":
                        environ = {"PATH": str(folder)}
                    else:
                        environ = dict(parent)
                        environ["PATH"] = str(folder)
                    database.probe_docker(environ, folder, 5.0)
                    recorded = stubs.calls(folder)[-1]["env"]
                    want: dict[str, str] = {
                        "PATH": str(folder),
                        "LANG": "C",
                        "LC_ALL": "C",
                    }
                    if label == "all_present":
                        want.update(
                            {
                                "HOME": home,
                                "WSL_DISTRO_NAME": "Ubuntu",
                                "DOCKER_HOST": "unix:///var/run/docker.sock",
                                "DOCKER_CONTEXT": "default",
                                "DOCKER_CONFIG": docker_cfg,
                            },
                        )
                    self.assertEqual(recorded, want)
        self.assertEqual(ran, labels)

    def test_silent_listener_gets_no_answer(self) -> None:
        """D11: connect to a silent listener times out."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            listener = stubs.loopback_socket()
            port = listener.getsockname()[1]
            listener.listen(5)
            stubs.write_stub(folder, "pg_isready", connect=True)
            stubs.write_stub(folder, "docker", status=0, stdout="")
            url = stubs.database_url(None, port)
            env = {"PATH": str(folder), "EII_DATABASE_URL": url}
            try:
                sel = database.check_postgres(env, folder, 1.0)
            finally:
                listener.close()
            self.assertEqual(sel.store, "embedded")
            assert sel.line is not None
            self.assertEqual(
                sel.line.text(),
                f"WARN postgresql: no answer on 127.0.0.1:{port} within 1 s; "
                "store embedded; Docker not reachable",
            )

    def test_no_client_program(self) -> None:
        """D12: empty PATH yields absent PostgreSQL."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            empty = folder / "empty"
            empty.mkdir()
            sock = stubs.loopback_socket()
            port = sock.getsockname()[1]
            sock.close()
            env = {
                "PATH": str(empty),
                "EII_DATABASE_URL": stubs.database_url(None, port),
            }
            sel = database.check_postgres(env, folder, 5.0)
            self.assertEqual(sel.store, "embedded")
            assert sel.line is not None
            self.assertEqual(
                sel.line.text(),
                "WARN postgresql: pg_isready not found on PATH, so PostgreSQL cannot answer here; "
                "store embedded; Docker not found on PATH",
            )
            self.assertEqual(stubs.calls(folder), [])


if __name__ == "__main__":
    unittest.main()
