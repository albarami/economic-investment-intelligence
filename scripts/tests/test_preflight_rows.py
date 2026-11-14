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
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_proc as proc
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
            "uv_status0_stdout",
        ]
        pass_line = (
            "PASS locked-dependencies: uv.lock and web/package-lock.json match "
            "their manifests with network access disabled"
        )
        ran: list[str] = []
        for label in labels:
            with self.subTest(label=label):
                ran.append(label)
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "root"
                    scratch = Path(tmp) / "scratch"
                    root.mkdir()
                    scratch.mkdir()
                    stub_dir = Path(tmp) / "stubs"
                    stub_dir.mkdir()
                    if label == "uv_status0_stdout":
                        stubs.write_stub(stub_dir, "uv", status=0, stdout="x\n")
                    elif label != "uv_missing":
                        stubs.write_stub(
                            stub_dir,
                            "uv",
                            status=0 if label not in ("uv_fail", "both_fail") else 1,
                        )
                    if label != "npm_missing":
                        npm_status = 0
                        npm_stdout = ""
                        npm_stderr = ""
                        if label in ("npm_fail", "both_fail"):
                            npm_status = 1
                        elif label == "npm_stderr":
                            npm_stderr = "warn\n"
                        stubs.write_stub(
                            stub_dir,
                            "npm",
                            status=npm_status,
                            stdout=npm_stdout,
                            stderr=npm_stderr,
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
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: uv.lock does not match the manifests "
                            "without the network (uv lock --check exit status 1); "
                            "npm ls reported a problem with web/package-lock.json (exit status 1)",
                        )
                    elif label == "uv_missing":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: uv not found on PATH",
                        )
                    elif label == "npm_missing":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: npm not found on PATH",
                        )
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
                        self.assertFalse(
                            any(c["program"] == "npm" for c in stubs.calls(stub_dir))
                        )
                    elif label == "uv_timeout":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: uv gave no answer within 0.5 s",
                        )
                    elif label == "npm_stderr":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: npm output not understood (exit status 0)",
                        )
                    elif label == "uv_status0_stdout":
                        self.assertEqual(
                            line.text(),
                            "FAIL locked-dependencies: uv output not understood (exit status 0)",
                        )
                    uv_argv = [
                        str(stub_dir / "uv"),
                        "lock",
                        "--check",
                        "--offline",
                    ]
                    npm_argv = [
                        str(stub_dir / "npm"),
                        "ls",
                        "--package-lock-only",
                        "--offline",
                        "--logs-max=0",
                    ]
                    want_uv_env = {
                        "PATH": str(stub_dir),
                        "LANG": "C",
                        "LC_ALL": "C",
                        "UV_NO_CONFIG": "1",
                    }
                    want_npm_env = {
                        "PATH": str(stub_dir),
                        "LANG": "C",
                        "LC_ALL": "C",
                        "npm_config_userconfig": str(scratch / "absent-user"),
                        "npm_config_globalconfig": str(scratch / "absent-global"),
                        "npm_config_update_notifier": "false",
                        "npm_config_cache": str(scratch / "npm-cache"),
                        "TMPDIR": str(scratch),
                    }
                    recorded = stubs.calls(stub_dir)
                    uv_calls = [c for c in recorded if c["program"] == "uv"]
                    npm_calls = [c for c in recorded if c["program"] == "npm"]
                    if uv_calls:
                        self.assertEqual(uv_calls[0]["argv"], uv_argv)
                        self.assertEqual(uv_calls[0]["cwd"], str(root))
                        self.assertEqual(uv_calls[0]["env"], want_uv_env)
                    if npm_calls:
                        self.assertEqual(npm_calls[0]["argv"], npm_argv)
                        self.assertEqual(npm_calls[0]["cwd"], str(root / "web"))
                        self.assertEqual(npm_calls[0]["env"], want_npm_env)
                        user = npm_calls[0]["env"]["npm_config_userconfig"]
                        glob = npm_calls[0]["env"]["npm_config_globalconfig"]
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
        with tempfile.TemporaryDirectory() as tmp:
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
                    sock.listen(5)
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

    def test_night_lights_key_row(self) -> None:
        """OPS-06: night-lights key presence uses only the supplied mapping."""
        key = stubs.dummy("night")
        cases: tuple[tuple[dict[str, str], str], ...] = (
            ({}, "absent"),
            ({"EARTHDATA_API_KEY": ""}, "absent"),
            ({"EARTHDATA_API_KEY": key}, "present"),
        )
        for env, want in cases:
            with (
                self.subTest(want=want, empty=not env),
                mock.patch.dict(os.environ, {"EARTHDATA_API_KEY": key}, clear=True),
                mock.patch("socket.socket") as sock,
                mock.patch("subprocess.Popen") as child,
            ):
                line = rows.night_lights_key_row(env)
                self.assertEqual(line.text(), f"PASS night-lights-key: {want}")
                self.assertNotIn(key, line.text())
                sock.assert_not_called()
                child.assert_not_called()

    def test_imagery_and_photorealistic_3d_key_rows(self) -> None:
        """OPS-73 and OPS-74: optional map keys report present/absent without printing or connecting."""
        for env_name, check_name, fn in (
            ("ESRI_API_KEY", "imagery-provider-key", rows.imagery_provider_key_row),
            (
                "MAPTILE_API_KEY",
                "photorealistic-3d-key",
                rows.photorealistic_3d_key_row,
            ),
        ):
            key = stubs.dummy(env_name.lower())
            for env, want in (
                ({}, "absent"),
                ({env_name: ""}, "absent"),
                ({env_name: key}, "present"),
            ):
                with (
                    self.subTest(check=check_name, want=want, empty=not env),
                    mock.patch.dict(os.environ, {env_name: key}, clear=True),
                    mock.patch("socket.socket") as sock,
                    mock.patch("subprocess.Popen") as child,
                ):
                    line = fn(env)
                    self.assertEqual(line.text(), f"PASS {check_name}: {want}")
                    self.assertNotIn(key, line.text())
                    sock.assert_not_called()
                    child.assert_not_called()

    def test_traffic_provider_key_row(self) -> None:
        """OPS-06: optional traffic key and each allowed/default setting pass."""
        key = stubs.dummy("traffic")
        for provider in (None, "", "simulated", "tomtom"):
            for value, presence in ((None, "absent"), ("", "absent"), (key, "present")):
                with (
                    self.subTest(
                        provider=provider, presence=presence, unset=value is None
                    ),
                    mock.patch.dict(
                        os.environ,
                        {
                            "TOMTOM_API_KEY": key,
                            "EII_TRAFFIC_PROVIDER": "tomtom",
                        },
                        clear=True,
                    ),
                    mock.patch("socket.socket") as sock,
                    mock.patch("subprocess.Popen") as child,
                ):
                    env: dict[str, str] = {}
                    if provider is not None:
                        env["EII_TRAFFIC_PROVIDER"] = provider
                    if value is not None:
                        env["TOMTOM_API_KEY"] = value
                    line = rows.traffic_provider_key_row(env)
                    want = provider or "simulated"
                    self.assertEqual(
                        line.text(),
                        f"PASS traffic-provider-key: {presence}; EII_TRAFFIC_PROVIDER {want}",
                    )
                    self.assertNotIn(key, line.text())
                    sock.assert_not_called()
                    child.assert_not_called()

    def test_traffic_provider_unknown_value_fails_without_echo(self) -> None:
        """R3 planted violation: reject an unknown setting with a fixed reason."""
        unknown = stubs.dummy("unknown")
        for key in ("", stubs.dummy("traffic")):
            with (
                self.subTest(present=bool(key)),
                mock.patch("socket.socket") as sock,
                mock.patch("subprocess.Popen") as child,
            ):
                line = rows.traffic_provider_key_row(
                    {
                        "EII_TRAFFIC_PROVIDER": unknown,
                        "TOMTOM_API_KEY": key,
                    }
                )
                self.assertEqual(
                    line.text(),
                    "FAIL traffic-provider-key: "
                    "EII_TRAFFIC_PROVIDER must be simulated or tomtom",
                )
                self.assertNotIn(unknown, line.text())
                if key:
                    self.assertNotIn(key, line.text())
                sock.assert_not_called()
                child.assert_not_called()

    def test_env_tracked_row_with_real_git(self) -> None:
        """R08: .env tracking with real git."""
        labels = ["untracked", "staged", "nested", "no_git"]
        ran: list[str] = []
        git_bin = shutil.which("git")
        if git_bin is None:
            self.fail("git not found on PATH")
        with tempfile.TemporaryDirectory() as tmp:
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
        stub_labels = [
            "status1_other_stderr",
            "git_env",
            "untracked_short_stderr",
            "status1_with_stdout",
            "git_enoexec",
            "git_timeout",
        ]
        stub_ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label in stub_labels:
                with self.subTest(label=label):
                    stub_ran.append(label)
                    repo = base / label
                    repo.mkdir()
                    stubs.untracked_repo(repo)
                    (repo / ".env").write_text("x\n", encoding="utf-8")
                    stub_dir = base / f"{label}_stubs"
                    stub_dir.mkdir()
                    if label == "git_enoexec":
                        bad = stub_dir / "git"
                        bad.write_text("x", encoding="utf-8")
                        bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
                        limit = 5.0
                    elif label == "git_timeout":
                        stubs.write_stub(stub_dir, "git", sleep=60.0)
                        limit = 0.5
                    elif label == "status1_other_stderr":
                        stubs.write_stub(
                            stub_dir,
                            "git",
                            status=1,
                            stdout="",
                            stderr="fatal: other\n",
                        )
                        limit = 5.0
                    elif label == "git_env":
                        stubs.write_stub(
                            stub_dir,
                            "git",
                            status=1,
                            stdout="",
                            stderr=rows.GIT_UNTRACKED[0],
                        )
                        limit = 5.0
                    elif label == "untracked_short_stderr":
                        stubs.write_stub(
                            stub_dir,
                            "git",
                            status=1,
                            stdout="",
                            stderr=rows.GIT_UNTRACKED[0],
                        )
                        limit = 5.0
                    else:
                        stubs.write_stub(
                            stub_dir,
                            "git",
                            status=1,
                            stdout="x\n",
                            stderr=rows.GIT_UNTRACKED[1],
                        )
                        limit = 5.0
                    env = {"PATH": str(stub_dir)}
                    line = rows.env_tracked_row(repo, env, limit)
                    if label == "status1_other_stderr":
                        self.assertEqual(
                            line.text(),
                            "FAIL env-not-tracked: git output not understood (exit status 1)",
                        )
                    elif label == "git_env":
                        self.assertEqual(
                            line.text(),
                            "PASS env-not-tracked: .env is not tracked by git",
                        )
                        call = stubs.calls(stub_dir)[0]
                        self.assertEqual(
                            call["env"],
                            {
                                "PATH": str(stub_dir),
                                "LANG": "C",
                                "LC_ALL": "C",
                                "GIT_CONFIG_NOSYSTEM": "1",
                                "GIT_CONFIG_GLOBAL": os.devnull,
                                "GIT_CEILING_DIRECTORIES": str(repo.parent),
                            },
                        )
                        self.assertEqual(
                            call["argv"][1:],
                            ["ls-files", "--error-unmatch", ".env"],
                        )
                    elif label == "untracked_short_stderr":
                        self.assertEqual(
                            line.text(),
                            "PASS env-not-tracked: .env is not tracked by git",
                        )
                    elif label == "status1_with_stdout":
                        self.assertEqual(
                            line.text(),
                            "FAIL env-not-tracked: git output not understood (exit status 1)",
                        )
                    elif label == "git_enoexec":
                        self.assertEqual(
                            line.text(),
                            "FAIL env-not-tracked: git could not be started (ENOEXEC)",
                        )
                    else:
                        self.assertEqual(
                            line.text(),
                            "FAIL env-not-tracked: git gave no answer within 0.5 s",
                        )
        self.assertEqual(ran, labels)
        self.assertEqual(stub_ran, stub_labels)

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
        with tempfile.TemporaryDirectory() as tmp:
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
                            stdout="\r\nMicrosoft Windows [Version 10.0.26100.1]\r\n",
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
                        self.assertEqual(
                            line.text(),
                            "WARN wsl-interop: cmd.exe could not be started (ENOEXEC); see OPS-43",
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
        labels = [
            "r03_uv_fail",
            "r03_npm_fail",
            "r03_uv_timeout",
            "r03_npm_stderr",
            "r08_status0_tracked",
            "r08_status1_marker",
            "r08_status128",
            "r09_status1",
            "r09_bad_output",
            "r08_timeout",
            "r09_timeout",
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label in labels:
                with self.subTest(label=label):
                    ran.append(label)
                    root = base / label / "root"
                    scratch = base / label / "scratch"
                    stub_dir = base / label / "stubs"
                    root.mkdir(parents=True)
                    scratch.mkdir()
                    stub_dir.mkdir()
                    stubs.untracked_repo(root)
                    (root / ".env").write_text("x\n", encoding="utf-8")
                    env = {"PATH": str(stub_dir), "ANTHROPIC_API_KEY": marker}
                    limit = 5.0
                    func: Any = rows.locked_dependencies_row
                    args: tuple[object, ...] = (root, env, scratch, limit)
                    if label.startswith("r03"):
                        _deps_root(root)
                        if label == "r03_uv_fail":
                            stubs.write_stub(
                                stub_dir,
                                "uv",
                                status=1,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                            stubs.write_stub(stub_dir, "npm", status=0)
                        elif label == "r03_npm_fail":
                            stubs.write_stub(stub_dir, "uv", status=0)
                            stubs.write_stub(
                                stub_dir,
                                "npm",
                                status=1,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                        elif label == "r03_uv_timeout":
                            stubs.write_stub(
                                stub_dir,
                                "uv",
                                sleep=60.0,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                            stubs.write_stub(stub_dir, "npm", status=0)
                            limit = 0.5
                        else:
                            stubs.write_stub(stub_dir, "uv", status=0)
                            stubs.write_stub(
                                stub_dir,
                                "npm",
                                status=0,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                        args = (root, env, scratch, limit)
                    elif label.startswith("r08"):
                        func = rows.env_tracked_row
                        args = (root, env, limit)
                        if label == "r08_status0_tracked":
                            stubs.write_stub(
                                stub_dir,
                                "git",
                                status=0,
                                stdout=".env\n",
                                echo=True,
                                stderr=marker,
                            )
                        elif label == "r08_status1_marker":
                            stubs.write_stub(
                                stub_dir,
                                "git",
                                status=1,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                        elif label == "r08_timeout":
                            stubs.write_stub(
                                stub_dir,
                                "git",
                                sleep=60.0,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                            limit = 0.5
                            args = (root, env, limit)
                        else:
                            stubs.write_stub(
                                stub_dir,
                                "git",
                                status=128,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                    else:
                        func = rows.wsl_row
                        args = (root, env, limit)
                        if label == "r09_status1":
                            stubs.write_stub(
                                stub_dir,
                                "cmd.exe",
                                status=1,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                        elif label == "r09_timeout":
                            stubs.write_stub(
                                stub_dir,
                                "cmd.exe",
                                sleep=60.0,
                                echo=True,
                                stdout=marker,
                                stderr=marker,
                            )
                            limit = 0.5
                            args = (root, env, limit)
                        else:
                            stubs.write_stub(
                                stub_dir,
                                "cmd.exe",
                                status=0,
                                stdout="x\r\n",
                                echo=True,
                                stderr=marker,
                            )
                    need_child_spy = label in ("r08_timeout", "r09_timeout")
                    if need_child_spy:
                        child_results: list[proc.ChildResult] = []
                        real_run_child = proc.run_child

                        def spy_run_child(
                            program: str,
                            args: object,
                            env_arg: object,
                            cwd: Path,
                            *,
                            limit: float = proc.PROBE_TIMEOUT_S,
                            _real: Callable[..., proc.ChildResult] = real_run_child,
                            _results: list[proc.ChildResult] = child_results,
                        ) -> proc.ChildResult:
                            from collections.abc import Mapping, Sequence

                            assert isinstance(args, Sequence)
                            assert isinstance(env_arg, Mapping)
                            child = _real(program, args, env_arg, cwd, limit=limit)
                            _results.append(child)
                            return child

                        with mock.patch.object(
                            proc, "run_child", side_effect=spy_run_child
                        ):
                            line = func(*args)
                    else:
                        line = func(*args)
                    text = line.text()
                    if label == "r08_timeout":
                        self.assertEqual(
                            text,
                            "FAIL env-not-tracked: git gave no answer within 0.5 s",
                        )
                    elif label == "r09_timeout":
                        self.assertEqual(
                            text,
                            "WARN wsl-interop: cmd.exe gave no answer within 0.5 s",
                        )
                    self.assertNotIn(marker, text)
                    if need_child_spy:
                        self.assertEqual(len(child_results), 1)
                        child = child_results[0]
                        self.assertTrue(child.timed_out)
                        self.assertIn(marker, child.stdout)
                        self.assertIn(marker, child.stderr)
                    skip_env = frozenset({"C", "1", "false", os.devnull})
                    for call in stubs.calls(stub_dir):
                        for value in call["env"].values():
                            if value in skip_env or len(value) <= 1:
                                continue
                            self.assertNotIn(value, text)
        self.assertEqual(ran, labels)

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
                with tempfile.TemporaryDirectory() as tmp:
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
