"""Full preflight run tests (U01-U09, U11, U12)."""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight as preflight_mod
import preflight_database as database
import preflight_proc as proc
import preflight_rows as rows
import preflight_store as store

REPO_ROOT = Path(__file__).resolve().parents[2]
WIN_LINE = "\r\nMicrosoft Windows [Version 10.0.26100.1]\r\n"


def _preflight_root(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "pyproject.toml", base / "pyproject.toml")
    shutil.copy2(REPO_ROOT / "uv.lock", base / "uv.lock")
    web = base / "web"
    web.mkdir()
    (web / "package.json").write_text(
        '{"name": "t08-probe", "version": "1.0.0", "private": true}\n',
        encoding="utf-8",
    )
    (web / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "t08-probe",
                "version": "1.0.0",
                "lockfileVersion": 3,
                "requires": True,
                "packages": {"": {"name": "t08-probe", "version": "1.0.0"}},
            },
        )
        + "\n",
        encoding="utf-8",
    )
    stubs.untracked_repo(base)
    (base / ".env").write_text("x\n", encoding="utf-8")
    return base


def _env0(
    tmp: Path,
) -> tuple[dict[str, str], Path, int, int]:
    """Build ENV0, root, api_port and db_port."""
    stub_dir = tmp / "stubs"
    stub_dir.mkdir()
    git_dir = tmp / "gitonly"
    git_dir.mkdir()
    git_real = shutil.which("git")
    if git_real is None:
        msg = "git not found on PATH"
        raise AssertionError(msg)
    (git_dir / "git").symlink_to(git_real)
    stubs.write_stub(stub_dir, "docker", status=0, stdout="")
    stubs.write_stub(
        stub_dir,
        "cmd.exe",
        status=0,
        stdout=WIN_LINE,
    )
    stubs.write_stub(stub_dir, "uv", status=0)
    stubs.write_stub(stub_dir, "npm", status=0)
    db_sock = stubs.loopback_socket()
    db_port = db_sock.getsockname()[1]
    db_sock.close()
    api_sock = stubs.loopback_socket()
    api_port = api_sock.getsockname()[1]
    api_sock.close()
    home = tmp / "home"
    home.mkdir()
    path = os.pathsep.join([str(stub_dir), str(git_dir)])
    env = {
        "PATH": path,
        "HOME": str(home),
        "EII_DATABASE_URL": stubs.database_url(None, db_port),
    }
    root = _preflight_root(tmp / "repo")
    return env, root, api_port, db_port


class Preflight(unittest.TestCase):
    """run_preflight, up_decision and main."""

    def _u01_lines(self, api_port: int) -> list[str]:
        return [
            "PASS locked-dependencies: uv.lock and web/package-lock.json match "
            "their manifests with network access disabled",
            "WARN postgresql: pg_isready not found on PATH, so PostgreSQL cannot answer here; "
            "store embedded; Docker not reachable",
            "WARN release: not_configured (EII_RELEASE_DIR is not set)",
            "WARN load-receipt: not_configured (EII_RELEASE_DIR is not set)",
            "WARN embedded-reader: not_configured (EII_RELEASE_DIR is not set)",
            "WARN tiles-glyphs-fonts: no_freeze_bundle (no freeze.json under data/freeze; "
            "checked with full severity once a freeze bundle exists)",
            "WARN recorded-replays: not_configured (EII_RELEASE_DIR is not set)",
            f"PASS api-port: 127.0.0.1:{api_port} is free",
            "PASS model-key: absent",
            "PASS env-not-tracked: .env is not tracked by git",
            "PASS wsl-interop: cmd.exe printed a Windows version",
            "store: embedded",
        ]

    def test_foundation_preflight_exits_zero(self) -> None:
        """U01: foundation preflight is WARN-heavy but exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            env, root, api_port, _db = _env0(Path(tmp))
            report = preflight_mod.run_preflight(root, env, api_port=api_port)
            want = self._u01_lines(api_port)
            self.assertEqual(report.text_lines(), want)
            self.assertEqual(report.status, 0)
            self.assertEqual(sum("not_configured" in line for line in want), 4)

    def test_foundation_keeps_other_severities(self) -> None:
        """U02: one fault per label; first five status 1, last two 0."""
        labels = [
            "uv_fail",
            "pg_reject",
            "freeze",
            "port_held",
            "env_staged",
            "pg_no_answer",
            "cmd_missing",
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case = base / label
                    case.mkdir()
                    env, root, api_port, db_port = _env0(case)
                    stub_dir = case / "stubs"
                    holder: socket.socket | None = None
                    freeze_line = (
                        "FAIL tiles-glyphs-fonts: freeze bundle found (1 freeze.json under "
                        "data/freeze), and the tile, glyph and font hash check is not built in slice S0"
                    )
                    if label == "uv_fail":
                        stubs.write_stub(stub_dir, "uv", status=1)
                    elif label == "pg_reject":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=1,
                            stdout=f"127.0.0.1:{db_port} - rejecting connections\n",
                        )
                    elif label == "freeze":
                        bundle = root / "data" / "freeze" / "x"
                        bundle.mkdir(parents=True)
                        (bundle / "freeze.json").write_text("{}", encoding="utf-8")
                    elif label == "port_held":
                        holder = stubs.loopback_socket()
                        held_port = holder.getsockname()[1]
                        holder.listen(5)
                        api_port = held_port
                    elif label == "env_staged":
                        subprocess.run(["git", "add", ".env"], cwd=root, check=True)
                    elif label == "pg_no_answer":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=2,
                            stdout=f"127.0.0.1:{db_port} - no response\n",
                        )
                    elif label == "cmd_missing":
                        (stub_dir / "cmd.exe").unlink()
                    report = preflight_mod.run_preflight(root, env, api_port=api_port)
                    want = self._u01_lines(api_port)
                    if label == "uv_fail":
                        want[0] = (
                            "FAIL locked-dependencies: uv.lock does not match the manifests "
                            "without the network (uv lock --check exit status 1)"
                        )
                    elif label == "pg_reject":
                        want[1] = (
                            f"FAIL postgresql: PostgreSQL on 127.0.0.1:{db_port} rejects "
                            "connections (pg_isready exit status 1)"
                        )
                        want[-1] = "store: none"
                    elif label == "freeze":
                        want[5] = freeze_line
                    elif label == "port_held":
                        want[7] = f"FAIL api-port: 127.0.0.1:{api_port} is in use"
                    elif label == "env_staged":
                        want[9] = "FAIL env-not-tracked: .env is tracked by git"
                    elif label == "pg_no_answer":
                        want[1] = (
                            f"WARN postgresql: no answer on 127.0.0.1:{db_port} "
                            "(pg_isready exit status 2); store embedded; Docker not reachable"
                        )
                    elif label == "cmd_missing":
                        want[10] = "WARN wsl-interop: cmd.exe not found on PATH"
                    self.assertEqual(report.text_lines(), want)
                    if label in (
                        "uv_fail",
                        "pg_reject",
                        "freeze",
                        "port_held",
                        "env_staged",
                    ):
                        self.assertEqual(report.status, 1)
                    else:
                        self.assertEqual(report.status, 0)
                    if holder is not None:
                        holder.close()
        self.assertEqual(ran, labels)

    def test_configured_release_mode(self) -> None:
        """U03: configured release dir yields not_built FAIL rows."""
        not_built = "not_built (EII_RELEASE_DIR is set, and this check is not built in slice S0)"
        with tempfile.TemporaryDirectory() as tmp:
            env, root, api_port, _ = _env0(Path(tmp))
            env["EII_RELEASE_DIR"] = "data/releases/x"
            report = preflight_mod.run_preflight(root, env, api_port=api_port)
            texts = report.text_lines()
            self.assertEqual(texts[2], f"FAIL release: {not_built}")
            self.assertEqual(texts[3], f"FAIL load-receipt: {not_built}")
            self.assertEqual(texts[4], f"FAIL embedded-reader: {not_built}")
            self.assertEqual(texts[6], f"WARN recorded-replays: {not_built}")
            self.assertEqual(report.status, 1)

    def test_up_decision(self) -> None:
        """U04: up_decision exit codes."""
        labels = [
            "unset",
            "empty",
            "release_fail",
            "api_only",
            "api_and_other",
            "all_ok",
            "unset_ok",
            "load_receipt_only",
            "embedded_reader_only",
            "two_release_rows",
        ]
        not_built = "not_built (EII_RELEASE_DIR is set, and this check is not built in slice S0)"
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                if label in ("unset", "unset_ok"):
                    env: dict[str, str] = {}
                elif label == "empty":
                    env = {"EII_RELEASE_DIR": ""}
                else:
                    env = {"EII_RELEASE_DIR": "data/releases/x"}
                lines: tuple[store.Line, ...]
                if label == "release_fail":
                    lines = (
                        store.Line("FAIL", "release", not_built),
                        store.Line("PASS", "api-port", "127.0.0.1:1 is free"),
                    )
                elif label == "load_receipt_only":
                    lines = (
                        store.Line("FAIL", "load-receipt", not_built),
                        store.Line("PASS", "api-port", "127.0.0.1:1 is free"),
                    )
                elif label == "embedded_reader_only":
                    lines = (
                        store.Line("FAIL", "embedded-reader", not_built),
                        store.Line("PASS", "api-port", "127.0.0.1:1 is free"),
                    )
                elif label == "two_release_rows":
                    lines = (
                        store.Line("FAIL", "release", not_built),
                        store.Line("FAIL", "load-receipt", not_built),
                        store.Line("FAIL", "embedded-reader", not_built),
                        store.Line("PASS", "api-port", "127.0.0.1:1 is free"),
                    )
                elif label == "api_only":
                    lines = (store.Line("FAIL", "api-port", "127.0.0.1:1 is in use"),)
                elif label == "api_and_other":
                    lines = (
                        store.Line("FAIL", "python", "bad"),
                        store.Line("FAIL", "api-port", "127.0.0.1:1 is in use"),
                    )
                elif label == "all_ok":
                    lines = (store.Line("PASS", "api-port", "127.0.0.1:1 is free"),)
                else:
                    lines = (store.Line("PASS", "api-port", "127.0.0.1:1 is free"),)
                report = preflight_mod.Report(
                    tuple(lines),
                    "embedded",
                    1 if label != "all_ok" else 0,
                )
                code, msg = preflight_mod.up_decision(env, report)
                if label in ("unset", "empty", "unset_ok"):
                    self.assertEqual(
                        (code, msg),
                        (
                            4,
                            "./eii up requires a configured, complete release: "
                            "EII_RELEASE_DIR is not set",
                        ),
                    )
                elif label == "release_fail":
                    self.assertEqual(
                        (code, msg),
                        (4, "release missing, incomplete or not verified: release"),
                    )
                elif label == "load_receipt_only":
                    self.assertEqual(
                        (code, msg),
                        (
                            4,
                            "release missing, incomplete or not verified: load-receipt",
                        ),
                    )
                elif label == "embedded_reader_only":
                    self.assertEqual(
                        (code, msg),
                        (
                            4,
                            "release missing, incomplete or not verified: embedded-reader",
                        ),
                    )
                elif label == "two_release_rows":
                    self.assertEqual(
                        (code, msg),
                        (
                            4,
                            "release missing, incomplete or not verified: "
                            "release, load-receipt, embedded-reader",
                        ),
                    )
                elif label == "api_only":
                    self.assertEqual((code, msg), (5, "API port already in use"))
                elif label == "api_and_other":
                    self.assertEqual(
                        (code, msg), (1, "a check failed: python, api-port")
                    )
                else:
                    self.assertEqual((code, msg), (0, ""))
        self.assertEqual(ran, labels)

    def test_embedded_selection(self) -> None:
        """U05: embedded mode skips or softens PostgreSQL."""
        labels = ["embedded_true", "docker_false"]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case = Path(tmp) / label
                    case.mkdir()
                    env, root, api_port, db_port = _env0(case)
                    stub_dir = case / "stubs"
                    stubs.write_stub(
                        stub_dir,
                        "pg_isready",
                        status=2,
                        stdout=f"127.0.0.1:{db_port} - no response\n",
                    )
                    stubs.write_stub(stub_dir, "docker", stdout="1.0\n")
                    report = preflight_mod.run_preflight(
                        root,
                        env,
                        embedded=label == "embedded_true",
                        docker=label != "docker_false",
                        api_port=api_port,
                    )
                    names = [c["program"] for c in stubs.calls(stub_dir)]
                    if label == "embedded_true":
                        self.assertFalse(
                            any(n in ("pg_isready", "docker") for n in names)
                        )
                        self.assertNotIn(
                            "postgresql", [ln.check for ln in report.lines]
                        )
                        self.assertEqual(report.text_lines()[-1], "store: embedded")
                    else:
                        self.assertFalse(any(n == "docker" for n in names))
                        self.assertEqual(
                            report.text_lines()[1],
                            f"WARN postgresql: no answer on 127.0.0.1:{db_port} "
                            "(pg_isready exit status 2); store embedded; Docker not probed",
                        )
                        self.assertEqual(report.text_lines()[-1], "store: embedded")
        self.assertEqual(ran, labels)

    def test_only_closed_commands_started(self) -> None:
        """U06: every child matches command_allowed."""
        u01_set = frozenset({"uv", "npm", "docker", "git", "cmd.exe"})
        scenarios: list[tuple[str, frozenset[str], dict[str, object] | None]] = [
            ("u01", u01_set, None),
            (
                "uv_fail",
                u01_set,
                {"uv_status": 1},
            ),
            ("freeze", u01_set, {"freeze": True}),
            ("port_held", u01_set, {"port_held": True}),
            ("env_staged", u01_set, {"env_staged": True}),
            (
                "pg_reject",
                frozenset({"uv", "npm", "pg_isready", "git", "cmd.exe"}),
                {"pg_reject": True},
            ),
            (
                "pg_no_answer",
                frozenset({"uv", "npm", "pg_isready", "docker", "git", "cmd.exe"}),
                {"pg_no_answer": True},
            ),
            (
                "cmd_missing",
                frozenset({"uv", "npm", "docker", "git"}),
                {"cmd_missing": True},
            ),
            (
                "d06_two_lines",
                frozenset({"uv", "npm", "pg_isready", "psql", "git", "cmd.exe"}),
                {"psql_two_lines": True},
            ),
        ]
        ran: list[str] = []
        real = proc.run_child
        recorded: list[tuple[str, tuple[str, ...]]] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label, expect_names, opts in scenarios:
                with self.subTest(label=label):
                    recorded.clear()
                    ran.append(label)
                    case = base / label
                    case.mkdir()
                    env, root, api_port, db_port = _env0(case)
                    stub_dir = case / "stubs"
                    holder: socket.socket | None = None
                    if opts:
                        if opts.get("uv_status"):
                            stubs.write_stub(stub_dir, "uv", status=1)
                        if opts.get("freeze"):
                            bundle = root / "data" / "freeze" / "x"
                            bundle.mkdir(parents=True)
                            (bundle / "freeze.json").write_text("{}", encoding="utf-8")
                        if opts.get("port_held"):
                            holder = stubs.loopback_socket()
                            api_port = holder.getsockname()[1]
                            holder.listen(5)
                        if opts.get("env_staged"):
                            subprocess.run(["git", "add", ".env"], cwd=root, check=True)
                        if opts.get("pg_reject"):
                            stubs.write_stub(
                                stub_dir,
                                "pg_isready",
                                status=1,
                                stdout=f"127.0.0.1:{db_port} - rejecting connections\n",
                            )
                        if opts.get("pg_no_answer"):
                            stubs.write_stub(
                                stub_dir,
                                "pg_isready",
                                status=2,
                                stdout=f"127.0.0.1:{db_port} - no response\n",
                            )
                        if opts.get("cmd_missing"):
                            (stub_dir / "cmd.exe").unlink()
                        if opts.get("psql_two_lines"):
                            stubs.write_stub(
                                stub_dir,
                                "pg_isready",
                                status=0,
                                stdout=f"127.0.0.1:{db_port} - accepting connections\n",
                            )
                            stubs.write_stub(
                                stub_dir,
                                "psql",
                                status=0,
                                stdout="180006|3.6.4\n\n",
                            )

                    def spy(
                        program: str,
                        args: object,
                        env_arg: object,
                        cwd: Path,
                        *,
                        limit: float = proc.PROBE_TIMEOUT_S,
                    ) -> proc.ChildResult:
                        from collections.abc import Mapping, Sequence

                        assert isinstance(args, Sequence)
                        assert isinstance(env_arg, Mapping)
                        recorded.append((Path(program).name, tuple(args)))
                        return real(program, args, env_arg, cwd, limit=limit)

                    with mock.patch("preflight_proc.run_child", side_effect=spy):
                        preflight_mod.run_preflight(root, env, api_port=api_port)
                    names = {name for name, _ in recorded}
                    self.assertEqual(names, set(expect_names))
                    for name, args in recorded:
                        self.assertTrue(proc.command_allowed(name, args))
                    if holder is not None:
                        holder.close()
        self.assertEqual(
            ran,
            [s[0] for s in scenarios],
        )

    def test_no_secret_in_any_line(self) -> None:
        """U07: secrets stay in env, not in lines or argv."""
        labels = [
            "good",
            "psql_echo",
            "pg_2",
            "reject",
            "pg_3",
            "psql_sleep",
            "url_only",
            "url_query",
        ]
        key = stubs.dummy("key")
        password = stubs.dummy("pw")
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    case = Path(tmp) / label
                    case.mkdir()
                    env, root, api_port, db_port = _env0(case)
                    env["ANTHROPIC_API_KEY"] = key
                    stub_dir = case / "stubs"
                    url = stubs.database_url(password, db_port)
                    if label == "url_only":
                        env["EII_DATABASE_URL"] = f"postgresql://eii_app:{password}"
                    elif label == "url_query":
                        env["EII_DATABASE_URL"] = url + "?sslmode=disable"
                    else:
                        env["EII_DATABASE_URL"] = url
                    if label == "good":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=0,
                            stdout=f"127.0.0.1:{db_port} - accepting connections\n",
                        )
                        stubs.write_stub(
                            stub_dir, "psql", status=0, stdout="180006|3.6.4\n"
                        )
                    elif label == "psql_echo":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=0,
                            stdout=f"127.0.0.1:{db_port} - accepting connections\n",
                        )
                        stubs.write_stub(stub_dir, "psql", status=2, echo=True)
                    elif label == "pg_2":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=2,
                            stdout=f"127.0.0.1:{db_port} - no response\n",
                        )
                    elif label == "reject":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=1,
                            stdout=f"127.0.0.1:{db_port} - rejecting connections\n",
                        )
                    elif label == "pg_3":
                        stubs.write_stub(stub_dir, "pg_isready", status=3)
                    elif label == "psql_sleep":
                        stubs.write_stub(
                            stub_dir,
                            "pg_isready",
                            status=0,
                            stdout=f"127.0.0.1:{db_port} - accepting connections\n",
                        )
                        stubs.write_stub(stub_dir, "psql", sleep=60.0)
                    if label != "good":
                        for name in ("docker", "cmd.exe", "uv", "npm", "git"):
                            path = stub_dir / name
                            if path.exists():
                                path.unlink()
                            stubs.write_stub(stub_dir, name, echo=True, status=9)
                    report = preflight_mod.run_preflight(
                        root, env, api_port=api_port, limit=0.5
                    )
                    blob = "\n".join(report.text_lines())
                    self.assertNotIn(key, blob)
                    self.assertNotIn(password, blob)
                    self.assertNotIn(env["EII_DATABASE_URL"], blob)
                    quoted_pw = urllib.parse.quote(password, safe="")
                    self.assertNotIn(quoted_pw, blob)
                    for call in stubs.calls(stub_dir):
                        self.assertNotIn(password, json.dumps(call["argv"]))
                        self.assertNotIn(key, json.dumps(call["env"]))
                        others = {
                            k: v
                            for k, v in call["env"].items()
                            if not (call["program"] == "psql" and k == "PGPASSWORD")
                        }
                        self.assertNotIn(password, json.dumps(others))
                        if call["program"] == "psql" and "PGPASSWORD" in call["env"]:
                            self.assertEqual(call["env"]["PGPASSWORD"], password)
                    main_out = io.StringIO()
                    with (
                        mock.patch.object(preflight_mod, "ROOT", root),
                        mock.patch.dict(os.environ, env, clear=True),
                        mock.patch("sys.stdout", main_out),
                    ):
                        preflight_mod.main([])
                    main_blob = main_out.getvalue()
                    self.assertNotIn(key, main_blob)
                    self.assertNotIn(password, main_blob)
                    self.assertNotIn(quoted_pw, main_blob)
                    self.assertNotIn(env["EII_DATABASE_URL"], main_blob)
        self.assertEqual(ran, labels)

    def test_main(self) -> None:
        """U08: main usage and patched run."""
        labels = ["usage", "run"]
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                if label == "usage":
                    err = io.StringIO()
                    with mock.patch("sys.stderr", err):
                        code = preflight_mod.main(["x"])
                    self.assertEqual(code, 2)
                    self.assertEqual(
                        err.getvalue(), "usage: preflight.py takes no arguments\n"
                    )
                else:
                    fixed = preflight_mod.Report(
                        (store.Line("FAIL", "model-key", "absent"),),
                        "embedded",
                        1,
                    )
                    out = io.StringIO()
                    with (
                        mock.patch.object(
                            preflight_mod,
                            "run_preflight",
                            return_value=fixed,
                        ) as run_mock,
                        mock.patch("sys.stdout", out),
                    ):
                        code = preflight_mod.main([])
                    self.assertEqual(
                        out.getvalue(), "FAIL model-key: absent\nstore: embedded\n"
                    )
                    self.assertEqual(code, 1)
                    run_mock.assert_called_once_with(preflight_mod.ROOT, os.environ)
        self.assertEqual(ran, labels)

    def test_check_names_and_order(self) -> None:
        """U09: CHECKS order matches report lines."""
        literal = (
            "locked-dependencies",
            "postgresql",
            "release",
            "load-receipt",
            "embedded-reader",
            "tiles-glyphs-fonts",
            "recorded-replays",
            "api-port",
            "model-key",
            "env-not-tracked",
            "wsl-interop",
        )
        self.assertEqual(preflight_mod.CHECKS, literal)
        with tempfile.TemporaryDirectory() as tmp:
            env, root, api_port, _ = _env0(Path(tmp))
            report = preflight_mod.run_preflight(root, env, api_port=api_port)
            checks = tuple(line.check for line in report.lines)
            self.assertEqual(checks, preflight_mod.CHECKS)

    def test_constants(self) -> None:
        """U11: module constants match the plan."""
        self.assertEqual(proc.PROBE_TIMEOUT_S, 5.0)
        self.assertEqual(proc.PG_ISREADY_WAIT, "5")
        self.assertEqual(rows.API_PORT, 8000)
        self.assertEqual(database.SERVER_MAJOR, 18)
        self.assertEqual(database.POSTGIS_LINE, (3, 6))
        self.assertEqual(
            database.FACTS_RE.pattern,
            r"(\d{5,6})\|([0-9A-Za-z.]*)",
        )
        self.assertEqual(len(proc.COMMANDS), 7)
        self.assertEqual(
            tuple(proc.PASS_THROUGH.keys()),
            tuple(name for name, _ in proc.COMMANDS),
        )

    def test_every_probe_gets_the_limit(self) -> None:
        """U12: run_child spy sees PROBE_TIMEOUT_S on every program."""
        with tempfile.TemporaryDirectory() as tmp:
            env, root, api_port, db_port = _env0(Path(tmp))
            stub_dir = Path(tmp) / "stubs"
            stubs.write_stub(
                stub_dir,
                "pg_isready",
                status=2,
                stdout=f"127.0.0.1:{db_port} - no response\n",
            )
            limits: list[tuple[str, float]] = []
            real = proc.run_child

            def spy(
                program: str,
                args: object,
                env_arg: object,
                cwd: Path,
                *,
                limit: float = proc.PROBE_TIMEOUT_S,
            ) -> proc.ChildResult:
                limits.append((Path(program).name, limit))
                from collections.abc import Mapping, Sequence

                assert isinstance(args, Sequence)
                assert isinstance(env_arg, Mapping)
                return real(program, args, env_arg, cwd, limit=limit)

            with mock.patch("preflight_proc.run_child", side_effect=spy):
                preflight_mod.run_preflight(root, env, api_port=api_port)
            programs = [name for name, _ in limits]
            self.assertEqual(
                sorted(programs),
                sorted(["pg_isready", "docker", "uv", "npm", "git", "cmd.exe"]),
            )
            self.assertTrue(all(limit == proc.PROBE_TIMEOUT_S for _, limit in limits))


if __name__ == "__main__":
    unittest.main()
