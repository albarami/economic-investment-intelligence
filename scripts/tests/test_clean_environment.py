"""Clean-environment install tests for the uv workspace."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]

# UV_NO_CONFIG=1 also ignores uv settings in a pyproject.toml [tool.uv] table;
# a task that adds such a setting revisits this (OI-40).

UV = shutil.which("uv")
SYNC_OFFLINE = ("sync", "--all-packages", "--locked", "--no-editable", "--offline")
FROM_PARENT = (
    "PATH", "HOME", "LANG", "LC_ALL",
    "XDG_DATA_HOME", "UV_PYTHON_INSTALL_DIR",
)

ALONE: dict[str, tuple[int, str]] = {
    "UV_PYTHON": (2, "No interpreter found at path"),
    "UV_NO_SOURCES": (1, "needs to be updated"),
    "UV_EXCLUDE_NEWER": (1, "needs to be updated"),
    "UV_RESOLUTION": (1, "needs to be updated"),
}


def child_tmp(cache: Path) -> str:
    """Return a dedicated child temp directory beside the uv cache."""
    folder = cache.parent / "child-tmp"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def child_env(cache: Path, project_env: Path | None = None) -> dict[str, str]:
    """Build the allow-listed child environment for uv calls."""
    env: dict[str, str] = {}
    for name in FROM_PARENT:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    tmp = child_tmp(cache)
    env["TMPDIR"] = tmp
    env["TMP"] = tmp
    env["TEMP"] = tmp
    env["UV_CACHE_DIR"] = str(cache)
    env["UV_NO_CONFIG"] = "1"
    if project_env is not None:
        env["UV_PROJECT_ENVIRONMENT"] = str(project_env)
    return env


def with_process_tmp(env: dict[str, str], cache: Path) -> dict[str, str]:
    """Copy ``env`` and point process temp dirs under ``cache``'s parent."""
    out = dict(env)
    tmp = child_tmp(cache)
    out["TMPDIR"] = tmp
    out["TMP"] = tmp
    out["TEMP"] = tmp
    return out


def run(
    args: list[str], cwd: Path, env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture output."""
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def copy_workspace(dst: Path) -> None:
    """Copy workspace inputs into ``dst``."""
    for name in ("pyproject.toml", ".python-version", "uv.lock"):
        shutil.copy2(REPO_ROOT / name, dst / name)
    for member in ("core", "custodian", "product"):
        shutil.copytree(
            REPO_ROOT / member,
            dst / member,
            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "dist", "build"),
        )


def env_python(envdir: Path) -> Path:
    """Return the Python executable inside a uv environment."""
    linux = envdir / "bin" / "python"
    if linux.is_file():
        return linux
    win = envdir / "Scripts" / "python.exe"
    if win.is_file():
        return win
    raise AssertionError("python not found in environment")


def observe(envdir: Path, work: Path, env: dict[str, str]) -> list[list[object]]:
    """Import each package in an isolated interpreter and record outcomes."""
    code = (
        "import importlib, json, sys; "
        "m = importlib.import_module(sys.argv[1]); "
        "print(json.dumps([list(sys.version_info[:2]), m.__version__, m.__file__]))"
    )
    rows: list[list[object]] = []
    env_resolved = envdir.resolve()
    for module in ("eii_core", "eii_custodian", "eii_product"):
        proc = run(
            [str(env_python(envdir)), "-I", "-c", code, module],
            work,
            env,
        )
        if proc.returncode != 0:
            rows.append([proc.returncode, None, None, None])
            continue
        payload = json.loads(proc.stdout.strip())
        version_info, version, module_file = payload
        path = Path(module_file).resolve()
        try:
            rel = path.relative_to(env_resolved).as_posix()
        except ValueError:
            rel = None
        rows.append([proc.returncode, version_info, version, rel])
    return rows


class CleanEnvironment(unittest.TestCase):
    sync: subprocess.CompletedProcess[str]
    lock_before: bytes
    lock_after: bytes
    ws: Path
    cache: Path
    work: Path
    env: Path

    @classmethod
    def setUpClass(cls) -> None:
        if UV is None:
            raise AssertionError("uv not found")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        base = Path(cls._tmp.name)
        cls.cache = base / "cache"
        cls.ws = base / "ws"
        cls.work = base / "work"
        cls.cache.mkdir()
        cls.ws.mkdir()
        cls.work.mkdir()
        cls.env = base / "env"
        copy_workspace(cls.ws)
        cls.lock_before = (cls.ws / "uv.lock").read_bytes()
        cls.sync = run(
            [UV, *SYNC_OFFLINE],
            cls.ws,
            child_env(cls.cache, cls.env),
        )
        cls.lock_after = (cls.ws / "uv.lock").read_bytes()

    def test_lock_is_current(self) -> None:
        cache = Path(self._tmp.name) / "lock-cache"
        cache.mkdir(exist_ok=True)
        proc = run([UV, "lock", "--check", "--offline"], REPO_ROOT, child_env(cache))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_stale_lock_is_detected(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cache = root / "cache"
        ws = root / "ws"
        cache.mkdir()
        ws.mkdir()
        copy_workspace(ws)
        text = (ws / "core/pyproject.toml").read_text(encoding="utf-8")
        replaced = text.replace('version = "0.0.0"', 'version = "0.0.1"', 1)
        self.assertNotEqual(text, replaced)
        (ws / "core/pyproject.toml").write_text(replaced, encoding="utf-8")
        proc = run([UV, "lock", "--check", "--offline"], ws, child_env(cache))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("needs to be updated", proc.stderr)

    def test_sync_all_packages_locked_keeps_lock(self) -> None:
        self.assertEqual(self.sync.returncode, 0, self.sync.stderr)
        self.assertEqual(self.lock_before, self.lock_after)

    def test_each_package_imports_from_clean_environment(self) -> None:
        env = child_env(self.cache)
        code = (
            "import importlib, json, sys; "
            "m = importlib.import_module(sys.argv[1]); "
            "print(json.dumps([list(sys.version_info[:2]), m.__version__, m.__file__]))"
        )
        env_resolved = self.env.resolve()
        for module, member in (
            ("eii_core", "core"),
            ("eii_custodian", "custodian"),
            ("eii_product", "product"),
        ):
            with self.subTest(module=module):
                proc = run(
                    [str(env_python(self.env)), "-I", "-c", code, module],
                    self.work,
                    env,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                version_info, version, module_file = json.loads(proc.stdout.strip())
                self.assertEqual(version_info, [3, 14])
                self.assertEqual(version, "0.0.0")
                path = Path(module_file).resolve()
                rel = path.relative_to(env_resolved)
                parts = set(rel.parts)
                self.assertIn("site-packages", parts)
                src_ws = (self.ws / member / "src").resolve()
                src_repo = (REPO_ROOT / member / "src").resolve()
                self.assertFalse(path.is_relative_to(src_ws))
                self.assertFalse(path.is_relative_to(src_repo))

    def test_bare_environment_cannot_import(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cache = root / "cache"
        bare = root / "bare"
        work = root / "work"
        cache.mkdir()
        work.mkdir()
        proc = run(
            [UV, "venv", "--python", "3.14", "--offline", str(bare)],
            root,
            child_env(cache),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for module in ("eii_core", "eii_custodian", "eii_product"):
            with self.subTest(module=module):
                imp = run(
                    [str(env_python(bare)), "-I", "-c", f"import {module}"],
                    work,
                    child_env(cache),
                )
                self.assertNotEqual(imp.returncode, 0)
                self.assertIn("ModuleNotFoundError", imp.stderr)

    def test_uv_pip_list_names_the_three_packages(self) -> None:
        proc = run(
            [
                UV,
                "pip",
                "list",
                "--python",
                str(env_python(self.env)),
                "--format",
                "json",
                "--offline",
            ],
            self.ws,
            child_env(self.cache),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        names = {row["name"] for row in json.loads(proc.stdout)}
        self.assertEqual(names, {"eii-core", "eii-custodian", "eii-product"})

    def test_hostile_surroundings_do_not_change_the_result(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cache = root / "cache"
        cache2 = root / "cache2"
        cache3 = root / "cache3"
        ws = root / "ws"
        ws3 = root / "ws3"
        work = root / "work"
        badenv = root / "badenv"
        elsewhere = root / "elsewhere"
        hostile = root / "hostile"
        env2 = root / "env2"
        for path in (
            cache, cache2, cache3, ws, ws3, work, badenv, elsewhere, hostile,
        ):
            path.mkdir(parents=True)
        copy_workspace(ws)
        copy_workspace(ws3)
        (hostile / "uv").mkdir()
        (hostile / "uv" / "uv.toml").write_text("no-build = true\n", encoding="utf-8")
        clean = observe(self.env, work, child_env(cache))
        snapshot = dict(os.environ)
        h = {
            "UV_NO_BUILD": "1",
            "UV_PYTHON": f"{elsewhere}/does-not-exist/bin/python",
            "UV_NO_SOURCES": "1",
            "UV_FROZEN": "1",
            "UV_CONFIG_FILE": f"{hostile}/uv/uv.toml",
            "UV_PROJECT": str(elsewhere),
            "UV_WORKING_DIR": str(elsewhere),
            "UV_EXCLUDE_NEWER": "2000-01-01T00:00:00Z",
            "UV_RESOLUTION": "lowest",
            "UV_NO_INSTALL_WORKSPACE": "1",
            "UV_PROJECT_ENVIRONMENT": str(badenv),
            "XDG_CONFIG_HOME": str(hostile),
            "XDG_CONFIG_DIRS": str(hostile),
            "VIRTUAL_ENV": str(elsewhere),
            "PYTHONPATH": str(elsewhere),
            "PYTHONHOME": str(elsewhere),
        }
        lock_bytes = (ws / "uv.lock").read_bytes()
        with patch.dict(os.environ, h, clear=False):
            e = child_env(cache, self.env)
            e["XDG_CONFIG_HOME"] = str(hostile)
            e["XDG_CONFIG_DIRS"] = str(hostile)
            subject = run(
                [UV, *SYNC_OFFLINE],
                ws,
                e,
            )
            self.assertEqual(subject.returncode, 0, subject.stderr)
            self.assertEqual((ws / "uv.lock").read_bytes(), lock_bytes)
            self.assertFalse(any(badenv.iterdir()))
            pip = run(
                [
                    UV,
                    "pip",
                    "list",
                    "--python",
                    str(env_python(self.env)),
                    "--format",
                    "json",
                    "--offline",
                ],
                ws,
                e,
            )
            names = {row["name"] for row in json.loads(pip.stdout)}
            self.assertEqual(names, {"eii-core", "eii-custodian", "eii-product"})
            self.assertEqual(observe(self.env, work, e), clean)

            e2 = child_env(cache2, env2)
            e2.pop("UV_NO_CONFIG", None)
            e2["XDG_CONFIG_HOME"] = str(hostile)
            e2["XDG_CONFIG_DIRS"] = str(hostile)
            tooth1 = run(
                [UV, *SYNC_OFFLINE],
                ws,
                e2,
            )
            self.assertEqual(tooth1.returncode, 2, tooth1.stderr)
            self.assertIn("--no-build", tooth1.stderr)

            parent = with_process_tmp(dict(os.environ), cache3)
            parent["UV_CACHE_DIR"] = str(cache3)
            tooth2 = run(
                [UV, *SYNC_OFFLINE],
                ws3,
                parent,
            )
            self.assertEqual(tooth2.returncode, 2, tooth2.stderr)
            self.assertIn("cannot be used with `UV_FROZEN`", tooth2.stderr)

        self.assertEqual(dict(os.environ), snapshot)
        alone_count = 0
        for name, (want, fragment) in ALONE.items():
            with self.subTest(var=name):
                alone_count += 1
                folder = root / f"alone-{name}"
                folder.mkdir()
                merged = with_process_tmp(
                    {**snapshot, "UV_CACHE_DIR": str(folder), name: h[name]},
                    folder,
                )
                proc = run(
                    [UV, *SYNC_OFFLINE],
                    ws3,
                    merged,
                )
                self.assertEqual(proc.returncode, want, proc.stderr)
                self.assertIn(fragment, proc.stderr)
        self.assertEqual(alone_count, 4)


if __name__ == "__main__":
    unittest.main()
