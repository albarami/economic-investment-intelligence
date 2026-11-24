"""Clean-environment install tests for the uv workspace."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import cast
from unittest.mock import patch

from packaging import markers

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workspace_guard as guard

REPO_ROOT = Path(__file__).resolve().parents[2]

# UV_NO_CONFIG=1 also ignores uv settings in a pyproject.toml [tool.uv] table;
# a task that adds such a setting revisits this (OI-40).

_uv = shutil.which("uv")
if _uv is None:
    raise RuntimeError("uv not found")
UV: str = _uv
SYNC_OFFLINE = (
    "sync",
    "--all-packages",
    "--locked",
    "--no-editable",
    "--no-dev",
    "--offline",
)
DEPENDENCY_GROUPS_TABLE = r"(?ms)^\[dependency-groups\]\n.*?(?=^\[|\Z)"
FROM_PARENT = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "XDG_DATA_HOME",
    "UV_PYTHON_INSTALL_DIR",
)

ALONE: dict[str, tuple[int, str]] = {
    "UV_PYTHON": (2, "No interpreter found at path"),
    "UV_NO_SOURCES": (1, "needs to be updated"),
    "UV_EXCLUDE_NEWER": (1, "published after the exclude newer time"),
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
    args: list[str],
    cwd: Path,
    env: dict[str, str],
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


def _plant_store_probe(ws: Path) -> None:
    """Put one invented query into the temporary copy only."""
    folder = ws / "product" / "src" / "eii_product" / "store" / "sql"
    (folder / "syn_probe.sql").write_text(
        "-- name: syn_probe\n"
        "-- params:\n"
        "-- returns: label text\n"
        "-- order: label\n"
        "SELECT p.label AS label\n"
        "FROM syn_probe AS p\n"
        "ORDER BY p.label ASC NULLS LAST\n",
        encoding="utf-8",
    )
    (folder / "syn_probe.toml").write_text(
        '[[tables]]\nname = "syn_probe"\nanchor = "invented control table"\n'
        'key = ["label"]\n\n[[tables.columns]]\nname = "label"\n'
        'type = "string"\nnullable = false\n',
        encoding="utf-8",
    )


def copy_workspace(dst: Path) -> None:
    """Copy workspace inputs into ``dst``."""
    for name in ("pyproject.toml", ".python-version", "uv.lock"):
        shutil.copy2(REPO_ROOT / name, dst / name)
    for member in ("core", "custodian", "gateway", "product"):
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
    for module in ("eii_core", "eii_custodian", "eii_gateway", "eii_product"):
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


def _seed_copy(src: str, dst: str, *, linked: dict[tuple[int, int], str]) -> str:
    stat = os.stat(src)
    key = (stat.st_dev, stat.st_ino)
    previous = linked.get(key)
    if previous is not None:
        os.link(previous, dst)
    else:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
        linked[key] = dst
    return dst


def seed_cache(cache: Path, source: Path | None = None) -> None:
    """Preserve links; only the class seed reads the original uv cache."""
    if source is None:
        proc = subprocess.run(
            [UV, "cache", "dir"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"uv cache dir failed: {proc.stderr.strip()}")
        source = Path(proc.stdout.strip())
    shutil.copytree(
        source,
        cache,
        symlinks=True,
        copy_function=partial(_seed_copy, linked={}),
        dirs_exist_ok=True,
    )


def member_manifest(root: Path, member: str) -> dict[str, object]:
    """Parse one member manifest."""
    text = (root / member / "pyproject.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def workspace_package_names(root: Path) -> set[str]:
    """Return the distribution names of the workspace members."""
    names: set[str] = set()
    for member in guard.MEMBER_DIRS:
        project = member_manifest(root, member).get("project", {})
        if isinstance(project, dict):
            name = project.get("name")
            if isinstance(name, str):
                names.add(guard.normalise(name))
    return names


def expected_installed_names(root: Path) -> set[str]:
    """Return the names a clean installation resolves to: members and locked closure."""
    manifests = {member: member_manifest(root, member) for member in guard.MEMBER_DIRS}
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    return reachable_locked_names(
        manifests,
        lock,
        cast(dict[str, str], markers.default_environment()),
    )


def _entry_applies_to_environment(
    package: Mapping[str, object],
    environment: Mapping[str, str],
) -> bool:
    """Whether one lock package entry resolves for ``environment``.

    An entry without ``resolution-markers`` applies to every environment.  One
    with them applies only where one of its markers holds: uv's lock writes the
    fork markers of a forked package in this field, and an entry whose markers
    all fail names a fork this environment does not use.
    """
    listed = package.get("resolution-markers")
    if listed is None:
        return True
    if not isinstance(listed, list):
        raise AssertionError(
            f"lock package entry has a non-list resolution-markers field: {listed!r}"
        )
    for one in listed:
        if not isinstance(one, str):
            raise AssertionError(
                f"lock package entry has a non-string resolution-marker: {one!r}"
            )
        if markers.Marker(one).evaluate(environment):
            return True
    return False


def reachable_locked_names(
    manifests: Mapping[str, Mapping[str, object]],
    lock: Mapping[str, object],
    environment: Mapping[str, str],
) -> set[str]:
    """Compute the expected installed names from the manifests, lock and environment.

    The workspace member names plus every package of the lock that is reachable
    from them through the lock's own dependency edges: an entry of a package is
    traversed only when its fork selection applies to ``environment`` (an entry
    with ``resolution-markers`` only when one of them holds, an entry without
    them always; two active entries of one name are refused as ambiguous), an
    edge is followed only when its marker holds for ``environment``, an extra's
    edges only when the edge that leads there selects that extra, and an
    optional edge's marker is evaluated with ``extra`` set to that extra.  The
    root manifest's dependency groups are never followed: the clean installation
    installs the members' own dependencies only.
    """
    entries: dict[str, list[Mapping[str, object]]] = {}
    packages = lock.get("package", [])
    if isinstance(packages, list):
        for package in packages:
            if isinstance(package, dict) and isinstance(package.get("name"), str):
                key = guard.normalise(str(package["name"]))
                entries.setdefault(key, []).append(package)
    queue: list[tuple[str, frozenset[str]]] = []
    for manifest in manifests.values():
        project = manifest.get("project", {})
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            queue.append((guard.normalise(str(project["name"])), frozenset()))
    expected: set[str] = set()
    seen: set[tuple[str, frozenset[str]]] = set()
    while queue:
        name, extras = queue.pop()
        if (name, extras) in seen:
            continue
        seen.add((name, extras))
        expected.add(name)
        active: list[Mapping[str, object]] = [
            package
            for package in entries.get(name, [])
            if _entry_applies_to_environment(package, environment)
        ]
        if len(active) > 1:
            raise AssertionError(
                f"the lock is ambiguous for this test: {len(active)} active "
                f"entries of package '{name}' for one environment"
            )
        for package in active:
            edges: list[tuple[object, Mapping[str, str]]] = []
            dependencies = package.get("dependencies", [])
            if isinstance(dependencies, list):
                for edge in dependencies:
                    edges.append((edge, environment))
            optional = package.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for extra in extras:
                    chosen = optional.get(extra)
                    if isinstance(chosen, list):
                        edge_env: Mapping[str, str] = {**environment, "extra": extra}
                        for edge in chosen:
                            edges.append((edge, edge_env))
            for edge, edge_env in edges:
                if not isinstance(edge, dict) or not isinstance(edge.get("name"), str):
                    continue
                marker = edge.get("marker")
                if isinstance(marker, str) and not markers.Marker(marker).evaluate(
                    edge_env
                ):
                    continue
                selected: list[str] = []
                wanted = edge.get("extra")
                if isinstance(wanted, list):
                    selected = [str(one) for one in wanted if isinstance(one, str)]
                queue.append((guard.normalise(str(edge["name"])), frozenset(selected)))
    return expected


def installed_names_equal(installed: set[str], expected: set[str]) -> bool:
    """The one comparison: installed names equal the expected names exactly."""
    return installed == expected


INVENTED_MEMBER_LOCK = """version = 1

[[package]]
name = "eii-core"
version = "0.0.0"
source = { editable = "core" }

[[package]]
name = "eii-custodian"
version = "0.0.0"
source = { editable = "custodian" }

[[package]]
name = "eii-gateway"
version = "0.0.0"
source = { editable = "gateway" }

[[package]]
name = "eii-product"
version = "0.0.0"
source = { editable = "product" }
"""

LOCK_TRANSITIVE = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-direct" },
]

[[package]]
name = "plant-direct"
version = "1.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-transit" },
]

[[package]]
name = "plant-transit"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)

LOCK_MARKERS = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-marker-base" },
]

[[package]]
name = "plant-marker-base"
version = "1.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-marker-true", marker = "python_version >= '3'" },
    { name = "plant-marker-false", marker = "python_version < '3'" },
]

[[package]]
name = "plant-marker-true"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-marker-false"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)

LOCK_EXTRAS = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-extra-host", extra = ["picked"] },
]

[[package]]
name = "plant-extra-host"
version = "1.0"
source = { registry = "https://example.com/simple" }

[package.optional-dependencies]
picked = [
    { name = "plant-extra-picked" },
]
skipped = [
    { name = "plant-extra-skipped" },
]

[[package]]
name = "plant-extra-picked"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-extra-skipped"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)

LOCK_SPELLING = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-spelt" },
]

[[package]]
name = "plant-spelt"
version = "1.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-spelt-child" },
]

[[package]]
name = "plant-spelt-child"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)

LOCK_UNREACHABLE = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-reached" },
]

[[package]]
name = "plant-reached"
version = "1.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-deep" },
]

[[package]]
name = "plant-deep"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-orphan"
version = "1.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-reached" },
    { name = "plant-orphan-dep" },
]

[[package]]
name = "plant-orphan-dep"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)


LOCK_FORKS = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-fork-base" },
]

[[package]]
name = "plant-fork-base"
version = "1.0"
source = { registry = "https://example.com/simple" }
resolution-markers = [
    "python_version >= '3.0'",
]
dependencies = [
    { name = "plant-fork-active-child" },
]

[[package]]
name = "plant-fork-base"
version = "2.0"
source = { registry = "https://example.com/simple" }
resolution-markers = [
    "python_version < '3.0'",
]
dependencies = [
    { name = "plant-fork-phantom-child" },
]

[[package]]
name = "plant-fork-active-child"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-fork-phantom-child"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)

LOCK_EXTRA_MARKERS = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-extra-marker-host", extra = ["picked"] },
]

[[package]]
name = "plant-extra-marker-host"
version = "1.0"
source = { registry = "https://example.com/simple" }

[package.optional-dependencies]
picked = [
    { name = "plant-extra-marker-match", marker = "extra == 'picked'" },
    { name = "plant-extra-marker-cross", marker = "extra == 'skipped'" },
]
skipped = [
    { name = "plant-extra-marker-skip", marker = "extra == 'skipped'" },
]

[[package]]
name = "plant-extra-marker-match"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-extra-marker-cross"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-extra-marker-skip"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)

LOCK_AMBIGUOUS = (
    INVENTED_MEMBER_LOCK
    + """dependencies = [
    { name = "plant-fork-ambiguous" },
]

[[package]]
name = "plant-fork-ambiguous"
version = "1.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-fork-first-child" },
]

[[package]]
name = "plant-fork-ambiguous"
version = "2.0"
source = { registry = "https://example.com/simple" }
dependencies = [
    { name = "plant-fork-second-child" },
]

[[package]]
name = "plant-fork-first-child"
version = "1.0"
source = { registry = "https://example.com/simple" }

[[package]]
name = "plant-fork-second-child"
version = "1.0"
source = { registry = "https://example.com/simple" }
"""
)


def write_invented_workspace(
    root: Path,
    member_dependencies: Mapping[str, Sequence[str]],
    lock_text: str,
) -> None:
    """Write an invented workspace: four member manifests and one invented lock."""
    for member, name, _module in guard.MEMBER_ROWS:
        lines = [
            "[project]",
            f'name = "{name}"',
            'version = "0.0.0"',
        ]
        deps = member_dependencies.get(member, ())
        if deps:
            lines.append("dependencies = [")
            lines.extend(f'  "{dep}",' for dep in deps)
            lines.append("]")
        folder = root / member
        folder.mkdir(parents=True)
        (folder / "pyproject.toml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    (root / "uv.lock").write_text(lock_text, encoding="utf-8")


class ExpectedInstalledNames(unittest.TestCase):
    """Invented workspaces pin the expected set to the lock's own resolution."""

    def test_product_declares_server_dependencies(self) -> None:
        project = member_manifest(REPO_ROOT, "product")["project"]
        self.assertIsInstance(project, dict)
        dependencies = cast(list[str], cast(dict[str, object], project)["dependencies"])
        self.assertIn("fastapi==0.162.5", dependencies)
        self.assertIn("uvicorn==0.54.0", dependencies)

    def expected_for(
        self,
        product_dependencies: Sequence[str],
        lock_text: str,
    ) -> set[str]:
        """Write one invented workspace and return its expected installed names."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        write_invented_workspace(root, {"product": product_dependencies}, lock_text)
        return expected_installed_names(root)

    def test_transitive_dependency_is_expected(self) -> None:
        expected = self.expected_for(("plant-direct>=1",), LOCK_TRANSITIVE)
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES) | {"plant-direct", "plant-transit"},
        )

    def test_true_marker_transitive_is_expected_and_false_marker_one_is_not(
        self,
    ) -> None:
        expected = self.expected_for(("plant-marker-base>=1",), LOCK_MARKERS)
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES) | {"plant-marker-base", "plant-marker-true"},
        )

    def test_selected_extra_is_expected_and_unselected_extra_is_not(self) -> None:
        expected = self.expected_for(
            ("plant-extra-host[picked]>=1",),
            LOCK_EXTRAS,
        )
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES) | {"plant-extra-host", "plant-extra-picked"},
        )

    def test_manifest_and_lock_spellings_are_one_expected_name(self) -> None:
        expected = self.expected_for(("Plant_Spelt>=1",), LOCK_SPELLING)
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES) | {"plant-spelt", "plant-spelt-child"},
        )

    def test_package_no_member_reaches_is_not_expected(self) -> None:
        expected = self.expected_for(("plant-reached>=1",), LOCK_UNREACHABLE)
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES) | {"plant-reached", "plant-deep"},
        )

    def test_inactive_fork_child_is_not_expected_and_active_fork_child_is(
        self,
    ) -> None:
        expected = self.expected_for(("plant-fork-base>=1",), LOCK_FORKS)
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES) | {"plant-fork-base", "plant-fork-active-child"},
        )

    def test_extra_marker_expected_through_selected_extra_and_not_an_unselected_one(
        self,
    ) -> None:
        expected = self.expected_for(
            ("plant-extra-marker-host[picked]>=1",),
            LOCK_EXTRA_MARKERS,
        )
        self.assertEqual(
            expected,
            set(guard.MEMBER_NAMES)
            | {"plant-extra-marker-host", "plant-extra-marker-match"},
        )

    def test_two_active_entries_of_one_name_are_refused(self) -> None:
        with self.assertRaises(AssertionError) as caught:
            self.expected_for(("plant-fork-ambiguous>=1",), LOCK_AMBIGUOUS)
        self.assertIn("plant-fork-ambiguous", str(caught.exception))
        self.assertIn("ambiguous", str(caught.exception))


class CacheSeeding(unittest.TestCase):
    def test_seed_preserves_links_across_filesystems_and_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            (source / "archive").mkdir(parents=True)
            original = source / "archive" / "file"
            original.write_text("invented cache entry", encoding="utf-8")
            (source / "alias").hardlink_to(original)
            (source / "directory-link").symlink_to("archive", target_is_directory=True)
            (source / "file-link").symlink_to("archive/file")
            first, second = root / "first", root / "second"
            real_link = os.link

            def cross_device_link(src: str, dst: str) -> None:
                if Path(src).is_relative_to(source):
                    raise OSError(errno.EXDEV, "invented cross-device link")
                real_link(src, dst)

            discoveries = [
                subprocess.CompletedProcess([UV, "cache", "dir"], 0, str(folder), "")
                for folder in (source, first)
            ]
            with (
                patch.object(subprocess, "run", side_effect=discoveries),
                patch.object(os, "link", side_effect=cross_device_link),
                patch.object(shutil, "copy2", wraps=shutil.copy2) as copies,
            ):
                seed_cache(first)
                seed_cache(second)
            for child in (first, second):
                for name, target in (
                    ("directory-link", "archive"),
                    ("file-link", "archive/file"),
                ):
                    self.assertTrue((child / name).is_symlink(), name)
                    self.assertEqual(os.readlink(child / name), target)
                    self.assertTrue((child / name).resolve().is_relative_to(child))
                    self.assertTrue((child / name).exists())
                self.assertTrue((child / "alias").samefile(child / "archive/file"))
                self.assertEqual(
                    (child / "archive/file").read_text(encoding="utf-8"),
                    "invented cache entry",
                )
            self.assertTrue((first / "archive/file").samefile(second / "archive/file"))
            self.assertEqual(copies.call_count, 1)


class CleanEnvironment(unittest.TestCase):
    sync: subprocess.CompletedProcess[str]
    lock_before: bytes
    lock_after: bytes
    ws: Path
    cache: Path
    seed: Path
    work: Path
    env: Path
    _tmp: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        base = Path(cls._tmp.name)
        cls.seed = base / "seed"
        seed_cache(cls.seed)
        cls.cache = base / "cache"
        cls.ws = base / "ws"
        cls.work = base / "work"
        cls.cache.mkdir()
        cls.ws.mkdir()
        cls.work.mkdir()
        cls.env = base / "env"
        copy_workspace(cls.ws)
        _plant_store_probe(cls.ws)
        seed_cache(cls.cache, cls.seed)
        cls.lock_before = (cls.ws / "uv.lock").read_bytes()
        cls.sync = run(
            [UV, *SYNC_OFFLINE],
            cls.ws,
            child_env(cls.cache, cls.env),
        )
        cls.lock_after = (cls.ws / "uv.lock").read_bytes()

    def test_server_imports_and_missing_dependency_plant(self) -> None:
        code = "from fastapi.sse import EventSourceResponse, ServerSentEvent; import uvicorn"
        control = run(
            [str(env_python(self.env)), "-I", "-c", code],
            self.work,
            child_env(self.cache),
        )
        self.assertEqual(control.returncode, 0, control.stderr)
        with tempfile.TemporaryDirectory(dir=self._tmp.name) as temporary:
            root = Path(temporary)
            cache, environment = root / "cache", root / "env"
            seed_cache(cache, self.seed)
            installed = run(
                [UV, *SYNC_OFFLINE, "--no-install-package", "fastapi"],
                self.ws,
                child_env(cache, environment),
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            missing = run(
                [str(env_python(environment)), "-I", "-c", code],
                self.work,
                child_env(cache),
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("No module named 'fastapi'", missing.stderr)

    def test_server_missing_uvicorn_plant(self) -> None:
        code = "from fastapi.sse import EventSourceResponse, ServerSentEvent; import uvicorn"
        control = run(
            [str(env_python(self.env)), "-I", "-c", code],
            self.work,
            child_env(self.cache),
        )
        self.assertEqual(control.returncode, 0, control.stderr)
        with tempfile.TemporaryDirectory(dir=self._tmp.name) as temporary:
            root = Path(temporary)
            cache, environment = root / "cache", root / "env"
            seed_cache(cache, self.seed)
            installed = run(
                [UV, *SYNC_OFFLINE, "--no-install-package", "uvicorn"],
                self.ws,
                child_env(cache, environment),
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            missing = run(
                [str(env_python(environment)), "-I", "-c", code],
                self.work,
                child_env(cache),
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("No module named 'uvicorn'", missing.stderr)

    def test_installed_store_enumeration_is_the_planted_probe(self) -> None:
        # Another test reinstalls the class environment from an unplanted copy.
        root = Path(self._tmp.name) / "probe"
        cache = root / "cache"
        env = root / "env"
        cache.mkdir(parents=True)
        seed_cache(cache, self.seed)
        installed = run([UV, *SYNC_OFFLINE], self.ws, child_env(cache, env))
        self.assertEqual(installed.returncode, 0, installed.stderr)
        code = (
            "import json, sys\n"
            "import eii_product.store\n"
            "from eii_product.store.registry import load_inventory, packaged_sql_dir\n"
            "roots = {'duckdb', 'psycopg', 'sqlglot'}\n"
            "loaded = sorted({name.split('.', 1)[0] for name in sys.modules "
            "if name.split('.', 1)[0] in roots})\n"
            "inventory = load_inventory(packaged_sql_dir())\n"
            "names = sorted(path.name for path in packaged_sql_dir().iterdir())\n"
            "print(json.dumps({'names': [inventory.lookup('syn_probe').name], "
            "'drivers': loaded, 'sql': names}))\n"
        )
        proc = run(
            [str(env_python(env)), "-I", "-c", code],
            self.work,
            child_env(cache),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["names"], ["syn_probe"])
        self.assertEqual(payload["drivers"], [])
        self.assertIn("syn_probe.sql", payload["sql"])

    def test_lock_is_current(self) -> None:
        cache = Path(self._tmp.name) / "lock-cache"
        cache.mkdir(exist_ok=True)
        seed_cache(cache, self.seed)
        proc = run([UV, "lock", "--check", "--offline"], REPO_ROOT, child_env(cache))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def prepare_offline_resolution(self, ws: Path, cache: Path) -> None:
        """Keep resolution plants independent of cached registry metadata.

        Only these disposable fixtures omit registry requirements. The clean
        installation checks still exercise the complete repository lock.
        """
        root_toml = (ws / "pyproject.toml").read_text(encoding="utf-8")
        stripped, removed = re.subn(DEPENDENCY_GROUPS_TABLE, "", root_toml)
        self.assertEqual(removed, 1)
        (ws / "pyproject.toml").write_text(stripped, encoding="utf-8")
        import ast

        dropped: list[str] = []
        for member in ("core", "custodian", "gateway", "product"):
            pyproject = ws / member / "pyproject.toml"
            lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
            marked = [
                index
                for index, line in enumerate(lines)
                if line.startswith("dependencies = [")
            ]
            self.assertEqual(len(marked), 1)
            dep_line = lines[marked[0]].rstrip("\n")
            entries = ast.literal_eval(dep_line.removeprefix("dependencies = "))
            kept = [entry for entry in entries if entry.startswith("eii-")]
            dropped.extend(entry for entry in entries if not entry.startswith("eii-"))
            quoted = ", ".join(f'"{entry}"' for entry in kept)
            lines[marked[0]] = f"dependencies = [{quoted}]\n"
            pyproject.write_text("".join(lines), encoding="utf-8")
        self.assertIn("pyyaml==6.0.3", dropped)
        self.assertEqual(dropped.count("pyyaml==6.0.3"), 1)
        regen = run([UV, "lock", "--offline"], ws, child_env(cache))
        self.assertEqual(regen.returncode, 0, regen.stderr)

    def add_dated_dependency(self, ws: Path) -> Path:
        """Provide an invented, dated wheel through a file-only package index."""
        index = ws / "fixture-index"
        package = index / "plant"
        package.mkdir(parents=True)
        wheel = package / "plant-0.0.0-py3-none-any.whl"
        info = "plant-0.0.0.dist-info"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                f"{info}/METADATA",
                "Metadata-Version: 2.1\nName: plant\nVersion: 0.0.0\n",
            )
            archive.writestr(
                f"{info}/WHEEL",
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            archive.writestr(f"{info}/RECORD", "")
        (package / "index.html").write_text(
            f'<a href="{wheel.name}" data-upload-time="2020-01-01T00:00:00Z">'
            f"{wheel.name}</a>",
            encoding="utf-8",
        )
        product = ws / "product/pyproject.toml"
        text = product.read_text(encoding="utf-8")
        original = 'dependencies = ["eii-core"'
        self.assertEqual(text.count(original), 1)
        product.write_text(
            text.replace(original, 'dependencies = ["eii-core", "plant==0.0.0"'),
            encoding="utf-8",
        )
        return index

    def test_stale_lock_is_detected(self) -> None:
        tmp = tempfile.TemporaryDirectory(dir=self._tmp.name)
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cache = root / "cache"
        ws = root / "ws"
        cache.mkdir()
        ws.mkdir()
        seed_cache(cache, self.seed)
        copy_workspace(ws)
        self.prepare_offline_resolution(ws, cache)
        current = run([UV, "lock", "--check", "--offline"], ws, child_env(cache))
        self.assertEqual(current.returncode, 0, current.stderr)
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
            ("eii_gateway", "gateway"),
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

    def test_installed_catalogue_assets_load_outside_source_workspace(self) -> None:
        self.assertEqual(self.sync.returncode, 0, self.sync.stderr)
        self.assertFalse(self.work.is_relative_to(self.ws))
        code = """
import hashlib
import json
from pathlib import Path
from eii_product.assistant.catalogue import (
    Catalogue, catalogue_directory, load_catalogue,
)
from eii_product.assistant.catalogue.schema import FILE_NAMES
folder = catalogue_directory()
loaded = load_catalogue(folder)
assert isinstance(loaded, Catalogue), loaded
print(json.dumps({
    "folder": str(folder),
    "hashes": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
               for name in FILE_NAMES},
    "version": loaded.version,
    "counts": [len(loaded.claims), len(loaded.components), len(loaded.fragments),
               len(loaded.questions), len(loaded.directives)],
}))
"""
        proc = run(
            [str(env_python(self.env)), "-I", "-c", code],
            self.work,
            child_env(self.cache),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        folder = Path(result["folder"]).resolve()
        self.assertIn("site-packages", folder.relative_to(self.env.resolve()).parts)
        self.assertFalse(folder.is_relative_to(self.ws))
        self.assertFalse(folder.is_relative_to(REPO_ROOT / "product"))
        import hashlib

        from eii_product.assistant.catalogue import Catalogue, load_catalogue
        from eii_product.assistant.catalogue.schema import FILE_NAMES

        source = REPO_ROOT / "product/src/eii_product/assistant/catalogue/assets"
        expected = {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in FILE_NAMES
        }
        self.assertEqual(result["hashes"], expected)
        loaded = load_catalogue(source)
        self.assertIsInstance(loaded, Catalogue)
        assert isinstance(loaded, Catalogue)
        self.assertEqual(result["version"], loaded.version)
        self.assertEqual(
            result["counts"],
            [
                len(loaded.claims),
                len(loaded.components),
                len(loaded.fragments),
                len(loaded.questions),
                len(loaded.directives),
            ],
        )

    def test_bare_environment_cannot_import(self) -> None:
        tmp = tempfile.TemporaryDirectory(dir=self._tmp.name)
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cache = root / "cache"
        bare = root / "bare"
        work = root / "work"
        cache.mkdir()
        work.mkdir()
        seed_cache(cache, self.seed)
        proc = run(
            [UV, "venv", "--python", "3.14", "--offline", str(bare)],
            root,
            child_env(cache),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for module in ("eii_core", "eii_custodian", "eii_gateway", "eii_product"):
            with self.subTest(module=module):
                imp = run(
                    [str(env_python(bare)), "-I", "-c", f"import {module}"],
                    work,
                    child_env(cache),
                )
                self.assertNotEqual(imp.returncode, 0)
                self.assertIn("ModuleNotFoundError", imp.stderr)

    def test_installed_names_equal_the_workspace_and_the_locked_declared_packages(
        self,
    ) -> None:
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
        installed = {
            guard.normalise(str(row["name"])) for row in json.loads(proc.stdout)
        }
        expected = expected_installed_names(REPO_ROOT)
        self.assertTrue(installed_names_equal(installed, expected))
        declared = sorted(expected - workspace_package_names(REPO_ROOT))
        self.assertTrue(declared)
        plants = (
            ("undeclared", installed | {"eii-undeclared-plant"}),
            ("declared-missing", installed - {declared[0]}),
            ("pyyaml-missing", installed - {"pyyaml"}),
        )
        for label, corrupted in plants:
            with self.subTest(plant=label):
                self.assertFalse(installed_names_equal(corrupted, expected))

    def test_hostile_surroundings_do_not_change_the_result(self) -> None:
        tmp = tempfile.TemporaryDirectory(dir=self._tmp.name)
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
            cache,
            cache2,
            cache3,
            ws,
            ws3,
            work,
            badenv,
            elsewhere,
            hostile,
        ):
            path.mkdir(parents=True)
        seed_cache(cache, self.seed)
        seed_cache(cache2, self.seed)
        seed_cache(cache3, self.seed)
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
            names = {
                guard.normalise(str(row["name"])) for row in json.loads(pip.stdout)
            }
            self.assertTrue(
                installed_names_equal(names, expected_installed_names(REPO_ROOT))
            )
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
        self.prepare_offline_resolution(ws3, cache3)
        # The cutoff plant needs a publication date, not a real registry or its
        # cached metadata. All four alone cases use this same offline fixture.
        index = self.add_dated_dependency(ws3)
        fixture_env = child_env(cache3, root / "fixture-env")
        fixture_env["UV_DEFAULT_INDEX"] = index.as_uri()
        regen = run([UV, "lock", "--offline"], ws3, fixture_env)
        self.assertEqual(regen.returncode, 0, regen.stderr)
        current = run([UV, "lock", "--check", "--offline"], ws3, fixture_env)
        self.assertEqual(current.returncode, 0, current.stderr)
        control = run([UV, *SYNC_OFFLINE], ws3, fixture_env)
        self.assertEqual(control.returncode, 0, control.stderr)
        alone_count = 0
        for name, (want, fragment) in ALONE.items():
            with self.subTest(var=name):
                alone_count += 1
                folder = root / f"alone-{name}"
                folder.mkdir()
                seed_cache(folder, self.seed)
                merged = with_process_tmp(
                    {
                        **snapshot,
                        "UV_CACHE_DIR": str(folder),
                        "UV_DEFAULT_INDEX": index.as_uri(),
                        name: h[name],
                    },
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
