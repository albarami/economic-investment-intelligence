"""Store selection tests (S01-S03)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_database as database
import preflight_store as store


class StoreSelection(unittest.TestCase):
    """Closed store-selection table and probe wiring."""

    def test_selection_table(self) -> None:
        """S01: nine rows of select_store."""
        labels = [
            "1_ok",
            "2_fail",
            "3_absent_reachable",
            "4_absent_unreachable",
            "5_absent_not_found",
            "6_absent_no_answer",
            "7_absent_not_started",
            "8_absent_not_probed",
            "9_embedded",
        ]
        cases: list[
            tuple[store.PgOutcome | None, store.DockerOutcome | None, str, str]
        ] = [
            (
                store.PgOutcome(
                    "ok",
                    "PostgreSQL 18.6 with PostGIS 3.6.4 answers on 127.0.0.1:55440",
                ),
                None,
                "PASS postgresql: PostgreSQL 18.6 with PostGIS 3.6.4 answers on 127.0.0.1:55440",
                "postgres",
            ),
            (
                store.PgOutcome(
                    "fail",
                    "PostgreSQL on 127.0.0.1:1 rejects connections (pg_isready exit status 1)",
                ),
                None,
                "FAIL postgresql: PostgreSQL on 127.0.0.1:1 rejects connections (pg_isready exit status 1)",
                "none",
            ),
            (
                store.PgOutcome(
                    "absent", "no answer on 127.0.0.1:1 (pg_isready exit status 2)"
                ),
                store.DockerOutcome("reachable", "28.0.4"),
                "WARN postgresql: no answer on 127.0.0.1:1 (pg_isready exit status 2); "
                "store embedded; Docker reachable (server 28.0.4)",
                "embedded",
            ),
            (
                store.PgOutcome("absent", "EII_DATABASE_URL is not set"),
                store.DockerOutcome("unreachable", ""),
                "WARN postgresql: EII_DATABASE_URL is not set; store embedded; Docker not reachable",
                "embedded",
            ),
            (
                store.PgOutcome(
                    "absent",
                    "pg_isready not found on PATH, so PostgreSQL cannot answer here",
                ),
                store.DockerOutcome("not_found", ""),
                "WARN postgresql: pg_isready not found on PATH, so PostgreSQL cannot answer here; "
                "store embedded; Docker not found on PATH",
                "embedded",
            ),
            (
                store.PgOutcome("absent", "no answer on 127.0.0.1:1 within 5 s"),
                store.DockerOutcome("no_answer", "5"),
                "WARN postgresql: no answer on 127.0.0.1:1 within 5 s; "
                "store embedded; Docker gave no answer within 5 s",
                "embedded",
            ),
            (
                store.PgOutcome(
                    "absent", "no answer on 127.0.0.1:1 (pg_isready exit status 2)"
                ),
                store.DockerOutcome("not_started", "ENOEXEC"),
                "WARN postgresql: no answer on 127.0.0.1:1 (pg_isready exit status 2); "
                "store embedded; Docker could not be started (ENOEXEC)",
                "embedded",
            ),
            (
                store.PgOutcome(
                    "absent", "no answer on 127.0.0.1:1 (pg_isready exit status 2)"
                ),
                store.DockerOutcome("not_probed", ""),
                "WARN postgresql: no answer on 127.0.0.1:1 (pg_isready exit status 2); "
                "store embedded; Docker not probed",
                "embedded",
            ),
            (None, None, "", "embedded"),
        ]
        ran: list[str] = []
        for idx, (pg, docker, expected_text, expected_store) in enumerate(cases):
            with self.subTest(label=labels[idx]):
                ran.append(labels[idx])
                sel = store.select_store(pg, docker)
                if expected_text:
                    self.assertIsNotNone(sel.line)
                    assert sel.line is not None
                    self.assertEqual(sel.line.text(), expected_text)
                else:
                    self.assertIsNone(sel.line)
                self.assertEqual(sel.store, expected_store)
        self.assertEqual(ran, labels)

    def test_inconsistent_inputs_rejected(self) -> None:
        """S02: inconsistent pg/docker pairs raise ValueError."""
        labels = [
            "ok_with_docker",
            "fail_with_docker",
            "absent_without_docker",
            "none_with_docker",
        ]
        pg_ok = store.PgOutcome("ok", "ok reason")
        pg_fail = store.PgOutcome("fail", "fail reason")
        pg_absent = store.PgOutcome("absent", "absent reason")
        docker = store.DockerOutcome("reachable", "1.0")
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                with self.assertRaises(ValueError):
                    if label == "ok_with_docker":
                        store.select_store(pg_ok, docker)
                    elif label == "fail_with_docker":
                        store.select_store(pg_fail, docker)
                    elif label == "absent_without_docker":
                        store.select_store(pg_absent, None)
                    else:
                        store.select_store(None, docker)
        self.assertEqual(ran, labels)

    def test_docker_probed_only_when_postgres_is_absent(self) -> None:
        """S03: Docker stub called only when PostgreSQL is absent."""
        labels = [
            "accepting_good",
            "rejecting",
            "status_2",
            "status_2_no_docker",
            "embedded_true",
        ]
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                with tempfile.TemporaryDirectory(
                    dir=os.environ.get("TMPDIR", "/tmp"),
                ) as tmp:
                    folder = Path(tmp)
                    stubs.write_stub(folder, "pg_isready")
                    stubs.write_stub(folder, "psql", stdout="180006|3.6.4\n")
                    stubs.write_stub(folder, "docker", stdout="29.0.1\n")
                    port_sock = stubs.loopback_socket()
                    port = port_sock.getsockname()[1]
                    port_sock.close()
                    url = stubs.database_url(None, port)
                    env = {"PATH": str(folder), "EII_DATABASE_URL": url}
                    if label == "accepting_good":
                        (folder / "pg_isready").unlink()
                        stubs.write_stub(
                            folder,
                            "pg_isready",
                            status=0,
                            stdout=f"127.0.0.1:{port} - accepting connections\n",
                        )
                    elif label == "rejecting":
                        (folder / "pg_isready").unlink()
                        stubs.write_stub(
                            folder,
                            "pg_isready",
                            status=1,
                            stdout=f"127.0.0.1:{port} - rejecting connections\n",
                        )
                    elif label in ("status_2", "status_2_no_docker"):
                        (folder / "pg_isready").unlink()
                        stubs.write_stub(
                            folder,
                            "pg_isready",
                            status=2,
                            stdout=f"127.0.0.1:{port} - no response\n",
                        )
                    calls_before = len(stubs.calls(folder))
                    sel = database.check_postgres(
                        env,
                        folder,
                        5.0,
                        embedded=label == "embedded_true",
                        docker=label != "status_2_no_docker",
                    )
                    calls_after = stubs.calls(folder)
                    if label == "accepting_good":
                        self.assertEqual(sel.store, "postgres")
                        self.assertFalse(
                            any(c["program"] == "docker" for c in calls_after)
                        )
                    elif label == "rejecting":
                        self.assertEqual(sel.store, "none")
                        assert sel.line is not None
                        self.assertEqual(
                            sel.line.text(),
                            f"FAIL postgresql: PostgreSQL on 127.0.0.1:{port} rejects "
                            "connections (pg_isready exit status 1)",
                        )
                        self.assertFalse(
                            any(c["program"] == "docker" for c in calls_after)
                        )
                    elif label == "status_2":
                        self.assertEqual(sel.store, "embedded")
                        docker_calls = [
                            c for c in calls_after if c["program"] == "docker"
                        ]
                        self.assertEqual(len(docker_calls), 1)
                    elif label == "status_2_no_docker":
                        assert sel.line is not None
                        self.assertEqual(sel.store, "embedded")
                        self.assertEqual(
                            sel.line.text(),
                            f"WARN postgresql: no answer on 127.0.0.1:{port} "
                            "(pg_isready exit status 2); store embedded; Docker not probed",
                        )
                        self.assertFalse(
                            any(c["program"] == "docker" for c in calls_after)
                        )
                    else:
                        self.assertEqual(sel.store, "embedded")
                        self.assertIsNone(sel.line)
                        self.assertEqual(len(calls_after), calls_before)
        self.assertEqual(ran, labels)


if __name__ == "__main__":
    unittest.main()
