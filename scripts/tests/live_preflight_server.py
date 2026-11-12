"""Live PostgreSQL and Docker probes (V01-V04; not collected as test_*.py)."""

from __future__ import annotations

import os
import re
import shutil
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_database as database
import sandbox_check

CLOSED_PORT = 29441


class LiveServer(unittest.TestCase):
    """Real-service checks run by the lead with Compose up."""

    @classmethod
    def setUpClass(cls) -> None:
        raw = os.environ.get("EII_DATABASE_URL", "")
        if not raw:
            raise AssertionError(
                "EII_DATABASE_URL is unset; start the eii-poc Compose service and "
                "export EII_DATABASE_URL (see plan Docker section)",
            )
        parsed = database.parse_database_url(raw)
        if isinstance(parsed, str):
            raise AssertionError(
                f"EII_DATABASE_URL is not a valid connection string ({parsed})",
            )
        if parsed.host != "127.0.0.1":
            raise AssertionError(
                f"EII_DATABASE_URL host must be 127.0.0.1, got {parsed.host!r}",
            )
        banned = sandbox_check.BANNED_PORTS
        if parsed.port in banned:
            raise AssertionError(
                f"EII_DATABASE_URL port {parsed.port} is banned for tests",
            )
        if CLOSED_PORT in banned:
            raise AssertionError(
                f"closed-port fixture {CLOSED_PORT} is banned for tests"
            )
        if shutil.which("pg_isready") is None or shutil.which("psql") is None:
            raise AssertionError("pg_isready and psql must be on PATH for live probes")

    def test_service_answers_and_passes(self) -> None:
        """V01: healthy service yields PASS postgresql."""
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            sel = database.check_postgres(
                os.environ,
                scratch,
                5.0,
                docker=False,
            )
            self.assertEqual(sel.store, "postgres")
            assert sel.line is not None
            self.assertRegex(
                sel.line.text(),
                r"PASS postgresql: PostgreSQL 18\.[0-9]+ with PostGIS 3\.6\.[0-9]+ "
                r"answers on 127\.0\.0\.1:[0-9]+",
            )
            parts = urlsplit(os.environ["EII_DATABASE_URL"])
            if parts.password:
                self.assertNotIn(parts.password, sel.line.text())

    def test_missing_database_is_a_fail(self) -> None:
        """V02: wrong database name fails closed."""
        parts = urlsplit(os.environ["EII_DATABASE_URL"])
        missing_db = "eii_absent_db"
        swapped = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                "/" + missing_db,
                parts.query,
                parts.fragment,
            ),
        )
        env = dict(os.environ)
        env["EII_DATABASE_URL"] = swapped
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            sel = database.check_postgres(env, scratch, 5.0, docker=False)
            self.assertEqual(sel.store, "none")
            assert sel.line is not None
            port = parts.port or 5432
            self.assertEqual(
                sel.line.text(),
                f"FAIL postgresql: PostgreSQL answers on 127.0.0.1:{port}, "
                "but the check query failed (psql exit status 2)",
            )

    def test_closed_port_selects_embedded(self) -> None:
        """V03: closed port 29441 selects embedded."""
        try:
            socket.create_connection(("127.0.0.1", CLOSED_PORT), timeout=0.5).close()
        except ConnectionRefusedError:
            pass
        else:
            self.fail("port 29441 on 127.0.0.1 is not closed; free it or tell the lead")
        env = dict(os.environ)
        env["EII_DATABASE_URL"] = stubs.database_url(None, CLOSED_PORT)
        start = time.monotonic()
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            sel = database.check_postgres(env, scratch, 5.0, docker=False)
        self.assertLess(time.monotonic() - start, 5.0)
        self.assertEqual(sel.store, "embedded")
        assert sel.line is not None
        self.assertEqual(
            sel.line.text(),
            "WARN postgresql: no answer on 127.0.0.1:29441 (pg_isready exit status 2); "
            "store embedded; Docker not probed",
        )

    def test_docker_reachable_read_only(self) -> None:
        """V04: docker info is read-only and folds into store line."""
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            docker = database.probe_docker(os.environ, scratch, 5.0)
            if docker.kind != "reachable":
                self.fail("start Docker Desktop or make docker info reach a daemon")
            self.assertIsNotNone(re.fullmatch(database.VERSION_RE, docker.detail))
            env = dict(os.environ)
            env["EII_DATABASE_URL"] = stubs.database_url(None, CLOSED_PORT)
            sel = database.check_postgres(env, scratch, 5.0, docker=True)
            assert sel.line is not None
            self.assertTrue(
                sel.line.text().endswith(f"Docker reachable (server {docker.detail})")
            )


if __name__ == "__main__":
    unittest.main()
