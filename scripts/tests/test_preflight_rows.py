"""Preflight row tests (R03-R11)."""

from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_rows as rows

REPO_ROOT = Path(__file__).resolve().parents[2]


def _deps_root(base: Path) -> None:
    """Lay out a minimal root for locked-dependencies probes."""
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
                "packages": {
                    "": {"name": "t08-probe", "version": "1.0.0"},
                },
            },
        )
        + "\n",
        encoding="utf-8",
    )


class Rows(unittest.TestCase):
    """Individual preflight rows."""

    def test_locked_dependencies_row(self) -> None:
        """R03: locked-dependencies outcomes and child env."""
        labels = [
            "both_ok",
            "uv_fail",
            "npm_fail",
            "uv_missing",
            "npm_missing",
            "no_package_json",
            "no_package_lock",
            "uv_timeout",
            "npm_stderr",
            "both_fail",
        ]
        pass_line = (
            "PASS locked-dependencies: uv.lock and web/package-lock.json match "
            "their manifests with network access disabled"
        )
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                with tempfile.TemporaryDirectory(
                    dir=os.environ.get("TMPDIR", "/tmp"),
                ) as tmp:
                    root = Path(tmp) / "root"
                    scratch = Path(tmp) / "scratch"
                    root.mkdir()
                    scratch.mkdir()
                    stub_dir = Path(tmp) / "stubs"
                    stub_dir.mkdir()
                    if label != "uv_missing":
                        stubs.write_stub(
                            stub_dir,
                            "uv",
                            status=0 if label not in ("uv_fail", "both_fail") else 1,
                        )
                    if label not in (
                        "npm_missing",
                        "no_package_json",
                        "no_package_lock",
                    ):
                        stubs.write_stub(
                            stub_dir,
                            "npm",
                            status=0 if label not in ("npm_fail", "both_fail") else 1,
                            stderr="" if label != "npm_stderr" else "warn\n",
                        )
                    if label == "uv_timeout":
                        (stub_dir / "uv").unlink()
                        stubs.write_stub(stub_dir, "uv", sleep=60.0)
                    if label == "no_package_json":
                        _deps_root(root)
                        (root / "web" / "package.json").unlink()
                    elif label == "no_package_lock":
                        _deps_root(root)
                        (root / "web" / "package-lock.json").unlink()
                    else:
                        _deps_root(root)
                    env = {"PATH": str(stub_dir)}
                    limit = 0.5 if label == "uv_timeout" else 5.0
                    line = rows.locked_dependencies_row(root, env, scratch, limit)
                    if label == "both_ok":
                        self.assertEqual(line.text(), pass_line)
                    elif label == "uv_fail":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: uv.lock does not match the manifests "
                            "without the network (uv lock --check exit status 1)",
                        )
                    elif label == "npm_fail":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: npm ls reported a problem with "
                            "web/package-lock.json (exit status 1)",
                        )
                    elif label == "both_fail":
                        self.assertIn("uv.lock does not match", line.text())
                        self.assertIn("npm ls reported a problem", line.text())
                    elif label == "uv_missing":
                        self.assertIn("uv not found on PATH", line.text())
                    elif label == "npm_missing":
                        self.assertIn("npm not found on PATH", line.text())
                    elif label == "no_package_json":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: web/package.json is missing",
                        )
                        self.assertFalse(
                            any(c["program"] == "npm" for c in stubs.calls(stub_dir))
                        )
                    elif label == "no_package_lock":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: web/package-lock.json is missing",
                        )
                    elif label == "uv_timeout":
                        self.assertIn("uv gave no answer within 0.5 s", line.text())
                    elif label == "npm_stderr":
                        self.assertEqual(line.text(), pass_line)
                    if label in (
                        "both_ok",
                        "uv_fail",
                        "npm_fail",
                        "both_fail",
                        "npm_stderr",
                    ):
                        recorded = stubs.calls(stub_dir)
                        uv_calls = [c for c in recorded if c["program"] == "uv"]
                        npm_calls = [c for c in recorded if c["program"] == "npm"]
                        if uv_calls:
                            self.assertEqual(uv_calls[0]["cwd"], str(root))
                            uv_env = uv_calls[0]["env"]
                            self.assertEqual(
                                set(uv_env.keys()),
                                {"PATH", "LANG", "LC_ALL", "UV_NO_CONFIG"},
                            )
                        if npm_calls:
                            self.assertEqual(npm_calls[0]["cwd"], str(root / "web"))
                            npm_env = npm_calls[0]["env"]
                            self.assertEqual(
                                set(npm_env.keys()),
                                {
                                    "PATH",
                                    "LANG",
                                    "LC_ALL",
                                    "npm_config_userconfig",
                                    "npm_config_globalconfig",
                                    "npm_config_update_notifier",
                                    "npm_config_cache",
                                    "TMPDIR",
                                },
                            )
                            user = npm_env["npm_config_userconfig"]
                            glob = npm_env["npm_config_globalconfig"]
                            self.assertNotEqual(user, glob)
                            self.assertFalse(Path(user).exists())
                            self.assertFalse(Path(glob).exists())
        self.assertEqual(ran, labels)

    def test_foundation_rows(self) -> None:
        """R04: release rows in foundation and configured modes."""
        labels = ["unset", "empty", "configured"]
        not_cfg = "not_configured (EII_RELEASE_DIR is not set)"
        not_built = "not_built (EII_RELEASE_DIR is set, and this check is not built in slice S0)"
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                if label == "unset":
                    env: dict[str, str] = {}
                elif label == "empty":
                    env = {"EII_RELEASE_DIR": ""}
                else:
                    env = {"EII_RELEASE_DIR": "data/releases/x"}
                got = rows.release_rows(env)
                if label in ("unset", "empty"):
                    for key in (
                        "release",
                        "load-receipt",
                        "embedded-reader",
                        "recorded-replays",
                    ):
                        self.assertEqual(got[key].text(), f"WARN {key}: {not_cfg}")
                else:
                    for key in ("release", "load-receipt", "embedded-reader"):
                        self.assertEqual(got[key].text(), f"FAIL {key}: {not_built}")
                    self.assertEqual(
                        got["recorded-replays"].text(),
                        f"WARN recorded-replays: {not_built}",
                    )
        self.assertEqual(ran, labels)

    def test_tiles_row(self) -> None:
        """R05: freeze bundle counting."""
        labels = [
            "no_data",
            "empty_freeze",
            "dir_no_json",
            "one_bundle",
            "dangling_link",
            "not_a_dir",
            "list_error",
        ]
        warn = (
            "WARN tiles-glyphs-fonts: no_freeze_bundle (no freeze.json under data/freeze; "
            "checked with full severity once a freeze bundle exists)"
        )
        fail_one = (
            "FAIL tiles-glyphs-fonts: freeze bundle found (1 freeze.json under data/freeze), "
            "and the tile, glyph and font hash check is not built in slice S0"
        )
        ran: list[str] = []
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            base = Path(tmp)
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    root = base / label
                    root.mkdir()
                    if label == "empty_freeze":
                        (root / "data" / "freeze").mkdir(parents=True)
                    elif label == "dir_no_json":
                        (root / "data" / "freeze" / "x").mkdir(parents=True)
                    elif label == "one_bundle":
                        bundle = root / "data" / "freeze" / "x"
                        bundle.mkdir(parents=True)
                        (bundle / "freeze.json").write_text("{}", encoding="utf-8")
                    elif label == "dangling_link":
                        bundle = root / "data" / "freeze" / "x"
                        bundle.mkdir(parents=True)
                        (bundle / "freeze.json").symlink_to(root / "missing.json")
                    elif label == "not_a_dir":
                        (root / "data").mkdir(parents=True, exist_ok=True)
                        (root / "data" / "freeze").write_text("x", encoding="utf-8")
                    if label == "list_error":
                        with mock.patch(
                            "os.listdir",
                            side_effect=PermissionError(
                                13, "listdir", str(root / "data" / "freeze")
                            ),
                        ):
                            line = rows.tiles_row(root)
                        self.assertEqual(
                            line.text(),
                            "FAIL tiles-glyphs-fonts: data/freeze cannot be listed (EACCES)",
                        )
                    else:
                        line = rows.tiles_row(root)
                        if label in ("no_data", "empty_freeze", "dir_no_json"):
                            self.assertEqual(line.text(), warn)
                        elif label in ("one_bundle", "dangling_link"):
                            self.assertEqual(line.text(), fail_one)
                        else:
                            self.assertEqual(
                                line.text(),
                                "FAIL tiles-glyphs-fonts: data/freeze is not a folder",
                            )
        self.assertEqual(ran, labels)

    def test_api_port_row(self) -> None:
        """R06: api-port bind outcomes."""
        labels = ["in_use", "free", "eacces", "time_wait"]
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                if label == "in_use":
                    sock = stubs.loopback_socket()
                    port = sock.getsockname()[1]
                    sock.listen(5)
                    try:
                        line = rows.api_port_row(port)
                        self.assertEqual(
                            line.text(),
                            f"FAIL api-port: 127.0.0.1:{port} is in use",
                        )
                    finally:
                        sock.close()
                elif label == "free":
                    sock = stubs.loopback_socket()
                    port = sock.getsockname()[1]
                    sock.close()
                    line = rows.api_port_row(port)
                    self.assertEqual(
                        line.text(), f"PASS api-port: 127.0.0.1:{port} is free"
                    )
                elif label == "eacces":
                    sock = stubs.loopback_socket()
                    port = sock.getsockname()[1]
                    sock.close()
                    with mock.patch(
                        "socket.socket.bind",
                        side_effect=OSError(13, "Permission denied"),
                    ):
                        line = rows.api_port_row(port)
                    self.assertEqual(
                        line.text(),
                        f"FAIL api-port: 127.0.0.1:{port} cannot be bound (EACCES)",
                    )
                else:
                    listener = stubs.loopback_socket(reuse=True)
                    port = listener.getsockname()[1]
                    listener.listen(1)
                    client = socket.create_connection(("127.0.0.1", port))
                    accepted = listener.accept()[0]
                    accepted.close()
                    client.close()
                    listener.close()
                    line = rows.api_port_row(port)
                    self.assertEqual(
                        line.text(), f"PASS api-port: 127.0.0.1:{port} is free"
                    )
        self.assertEqual(ran, labels)

    def test_model_key_row(self) -> None:
        """R07: model-key present or absent."""
        labels = ["absent", "empty", "present"]
        key = stubs.dummy("k")
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                if label == "absent":
                    env: dict[str, str] = {}
                elif label == "empty":
                    env = {"ANTHROPIC_API_KEY": ""}
                else:
                    env = {"ANTHROPIC_API_KEY": key}
                line = rows.model_key_row(env)
                want = "present" if label == "present" else "absent"
                self.assertEqual(line.text(), f"PASS model-key: {want}")
                self.assertNotIn(key, line.text())
        self.assertEqual(ran, labels)

    def test_env_tracked_row_with_real_git(self) -> None:
        """R08: .env tracking with real git."""
        labels = ["untracked", "staged", "nested", "no_git"]
        ran: list[str] = []
        git_bin = shutil.which("git")
        if git_bin is None:
            self.fail("git not found on PATH")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            base = Path(tmp)
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    if label == "nested":
                        outer = base / "outer"
                        inner = outer / "inner"
                        inner.mkdir(parents=True)
                        stubs.untracked_repo(outer)
                        (inner / ".env").write_text("x\n", encoding="utf-8")
                        env = {"PATH": os.pathsep.join([os.path.dirname(git_bin)])}
                        line = rows.env_tracked_row(inner, env, 5.0)
                        self.assertEqual(
                            line.text(),
                            "FAIL env-not-tracked: git output not understood (exit status 128)",
                        )
                    elif label == "no_git":
                        repo = base / "nogit"
                        repo.mkdir()
                        stubs.untracked_repo(repo)
                        (repo / ".env").write_text("x\n", encoding="utf-8")
                        empty = base / "empty"
                        empty.mkdir()
                        line = rows.env_tracked_row(repo, {"PATH": str(empty)}, 5.0)
                        self.assertEqual(
                            line.text(), "FAIL env-not-tracked: git not found on PATH"
                        )
                    else:
                        repo = base / label
                        repo.mkdir()
                        stubs.untracked_repo(repo)
                        (repo / ".env").write_text("secret\n", encoding="utf-8")
                        if label == "staged":
                            subprocess.run(
                                ["git", "add", ".env"],
                                cwd=repo,
                                check=True,
                                capture_output=True,
                            )
                        env = {"PATH": os.pathsep.join([os.path.dirname(git_bin)])}
                        line = rows.env_tracked_row(repo, env, 5.0)
                        if label == "untracked":
                            self.assertEqual(
                                line.text(),
                                "PASS env-not-tracked: .env is not tracked by git",
                            )
                        else:
                            self.assertEqual(
                                line.text(),
                                "FAIL env-not-tracked: .env is tracked by git",
                            )
        self.assertEqual(ran, labels)

    def test_wsl_row(self) -> None:
        """R09: cmd.exe /c ver outcomes."""
        labels = [
            "ok",
            "missing",
            "enoexec",
            "timeout",
            "status_1",
            "bad_output",
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            root = folder / "root"
            root.mkdir()
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    stub_dir = folder / label
                    stub_dir.mkdir()
                    if label == "ok":
                        stubs.write_stub(
                            stub_dir,
                            "cmd.exe",
                            stdout="Microsoft Windows [Version 10.0.26100.1]\r\n",
                            stderr="warning\n",
                        )
                        env = {"PATH": str(stub_dir)}
                        line = rows.wsl_row(root, env, 5.0)
                        self.assertEqual(
                            line.text(),
                            "PASS wsl-interop: cmd.exe printed a Windows version",
                        )
                    elif label == "missing":
                        line = rows.wsl_row(root, {"PATH": str(stub_dir)}, 5.0)
                        self.assertEqual(
                            line.text(),
                            "WARN wsl-interop: cmd.exe not found on PATH",
                        )
                    elif label == "enoexec":
                        bad = stub_dir / "cmd.exe"
                        bad.write_text("x", encoding="utf-8")
                        bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
                        line = rows.wsl_row(root, {"PATH": str(stub_dir)}, 5.0)
                        self.assertIn(
                            "cmd.exe could not be started (ENOEXEC)", line.text()
                        )
                    elif label == "timeout":
                        stubs.write_stub(stub_dir, "cmd.exe", sleep=60.0)
                        line = rows.wsl_row(root, {"PATH": str(stub_dir)}, 0.5)
                        self.assertEqual(
                            line.text(),
                            "WARN wsl-interop: cmd.exe gave no answer within 0.5 s",
                        )
                    elif label == "status_1":
                        stubs.write_stub(stub_dir, "cmd.exe", status=1)
                        line = rows.wsl_row(root, {"PATH": str(stub_dir)}, 5.0)
                        self.assertEqual(
                            line.text(), "WARN wsl-interop: cmd.exe exit status 1"
                        )
                    else:
                        stubs.write_stub(stub_dir, "cmd.exe", status=0, stdout="x\r\n")
                        line = rows.wsl_row(root, {"PATH": str(stub_dir)}, 5.0)
                        self.assertEqual(
                            line.text(),
                            "WARN wsl-interop: cmd.exe output not understood",
                        )
        self.assertEqual(ran, labels)

    def test_rows_never_echo_child_output(self) -> None:
        """R10: failing rows do not leak child stdout/stderr."""
        marker = stubs.dummy("MARK")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            root = Path(tmp) / "root"
            scratch = Path(tmp) / "scratch"
            stub_dir = Path(tmp) / "stubs"
            root.mkdir()
            scratch.mkdir()
            stub_dir.mkdir()
            _deps_root(root)
            stubs.write_stub(
                stub_dir, "uv", status=1, echo=True, stdout=marker, stderr=marker
            )
            stubs.write_stub(
                stub_dir, "npm", status=1, echo=True, stdout=marker, stderr=marker
            )
            stubs.write_stub(
                stub_dir, "git", status=9, echo=True, stdout=marker, stderr=marker
            )
            stubs.write_stub(
                stub_dir, "cmd.exe", status=9, echo=True, stdout=marker, stderr=marker
            )
            env = {"PATH": str(stub_dir), "ANTHROPIC_API_KEY": marker}
            for func, args in (
                (rows.locked_dependencies_row, (root, env, scratch, 5.0)),
                (rows.env_tracked_row, (root, env, 5.0)),
                (rows.wsl_row, (root, env, 5.0)),
            ):
                line = func(*args)
                self.assertNotIn(marker, line.text())

    def test_locked_dependencies_with_real_npm(self) -> None:
        """R11: real npm ls with uv stub."""
        npm = shutil.which("npm")
        node = shutil.which("node")
        if npm is None or node is None:
            self.fail("npm and node must be on PATH")
        labels = ["ok", "mismatch"]
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                with tempfile.TemporaryDirectory(
                    dir=os.environ.get("TMPDIR", "/tmp"),
                ) as tmp:
                    root = Path(tmp) / "root"
                    scratch = Path(tmp) / "scratch"
                    stub_dir = Path(tmp) / "stubs"
                    root.mkdir()
                    scratch.mkdir()
                    stub_dir.mkdir()
                    _deps_root(root)
                    if label == "mismatch":
                        pkg = json.loads(
                            (root / "web" / "package.json").read_text(encoding="utf-8")
                        )
                        pkg["dependencies"] = {"left-pad": "1.3.0"}
                        (root / "web" / "package.json").write_text(
                            json.dumps(pkg) + "\n",
                            encoding="utf-8",
                        )
                    stubs.write_stub(stub_dir, "uv", status=0)
                    path = os.pathsep.join(
                        [str(stub_dir), os.path.dirname(npm), os.path.dirname(node)],
                    )
                    env = {"PATH": path}
                    line = rows.locked_dependencies_row(root, env, scratch, 5.0)
                    if label == "ok":
                        self.assertEqual(
                            line.text(),
                            "PASS locked-dependencies: uv.lock and web/package-lock.json match "
                            "their manifests with network access disabled",
                        )
                    else:
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: npm ls reported a problem with "
                            "web/package-lock.json (exit status 1)",
                        )
        self.assertEqual(ran, labels)


if __name__ == "__main__":
    unittest.main()
