"""Fixtures and stand-ins for the generator-sandbox tests."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import unittest
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_apparmor
import ci_sandbox
import extension_tree
import sandbox_launch as launch
import sandbox_profiles as tables

ROOT = Path(__file__).resolve().parents[2]
PROBE_REL = Path("scripts/sandbox_inside/sentinel_probe.py")
CHECK_REL = Path("scripts/sandbox_inside/extension_check.py")
ATTEMPTS = [
    "read_outside",
    "write_outside",
    "read_cache",
    "write_cache",
    "write_vault",
    "tcp_loopback",
    "unix_abstract",
    "tcp_unrouted",
    "dns_lookup",
]
INSIDE_EQUAL = [
    "read_outside error FileNotFoundError ENOENT",
    "write_outside error FileNotFoundError ENOENT",
    "read_cache ok",
    "write_cache error OSError EROFS",
    "write_vault ok",
    "tcp_loopback error ConnectionRefusedError ECONNREFUSED",
    "unix_abstract error ConnectionRefusedError ECONNREFUSED",
    "tcp_unrouted error OSError ENETUNREACH",
]
DNS_LINE = re.compile(r"dns_lookup error gaierror -[23]")
FAKE_EXTENSION_BYTES = {"h3": b"h3-bytes", "spatial": b"spatial-bytes"}
PINNED_BYTES = b"profile text\n"
OK = ci_sandbox.CommandResult(0, "", "")
LISTING_OK = ci_sandbox.CommandResult(
    0,
    '{"version": "2", "profiles": {"/usr/bin/man": "enforce", "bwrap": "enforce", '
    '"unpriv_bwrap": "enforce"}, "processes": {}}\n',
    "",
)
LABEL_OK = ci_sandbox.CommandResult(0, "bwrap//&unpriv_bwrap (enforce)\n", "")
FETCH_HINT = "run uv run --locked python scripts/engine_extensions.py fetch"
SYNC_HINT = "run uv sync --managed-python --all-packages --locked --group engine"
DIE_DRIVER = """
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import sandbox_launch as launch
payload = json.loads(sys.argv[2])
marker = sys.argv[3]
root = Path(payload["root"])
layout = launch.Layout(
    code_root=root,
    cache=root / "data" / "public_cache",
    vault=root / "data" / "vault" / "b1",
    extensions=root / "data" / "engine_extensions",
    scenario=Path(payload["scenario"]),
)
command = launch.python_command(
    "-c",
    "import time; time.sleep(60)",
    venv=Path(payload["venv"]),
)
command.append(marker)
launch.run_in_sandbox("build-world", layout, command, timeout=120)
"""


def assert_not_root() -> None:
    """Refuse to run a mode check as root, which ignores file modes."""
    if os.geteuid() == 0:
        raise AssertionError("the sandbox tests do not run as root")


def assert_inside(testcase: unittest.TestCase, lines: list[str]) -> None:
    """Compare the nine inside lines; the name-lookup code may be -2 or -3."""
    testcase.assertEqual(lines[:-1], INSIDE_EQUAL)
    testcase.assertIsNotNone(DNS_LINE.fullmatch(lines[-1]))


def descriptor_snapshot() -> dict[str, str]:
    """Map open descriptors to the paths the kernel gives them.
    The descriptor of the listing itself is closed before the check, so it is
    left out.
    """
    return {
        name: os.readlink(f"/proc/self/fd/{name}")
        for name in os.listdir("/proc/self/fd")
        if os.path.lexists(f"/proc/self/fd/{name}")
    }


class Fixture:
    """One temporary repository, its outside sentinel and its scenario file."""

    def __init__(self, base: Path, root: Path, outside: Path, scenario: Path) -> None:
        self.base = base
        self.root = root
        self.outside = outside
        self.scenario = scenario
        self.hidden = [
            root / ".env",
            root / "README.md",
            root / "data" / "vault" / "other" / "secret.txt",
            root / "data" / "releases" / "r1" / "manifest.txt",
        ]

    def layout(self, profile_name: str) -> launch.Layout:
        """Return the layout the named profile declares."""
        common = {
            "code_root": self.root,
            "cache": self.root / "data" / "public_cache",
            "vault": self.root / "data" / "vault" / "b1",
            "extensions": self.root / "data" / "engine_extensions",
        }
        if profile_name == "build-world":
            return launch.Layout(**common, scenario=self.scenario)
        return launch.Layout(
            **common, staging=self.root / "data" / "releases" / ".staging" / "b1"
        )


def make_fixture(tmp: str | Path) -> Fixture:
    """Build the fixture tree under a resolved base."""
    assert_not_root()
    base = Path(tmp).resolve()
    root = base / "repo"
    for folder in (
        "core/src",
        "custodian/src",
        "scripts/sandbox_inside",
        "data/public_cache",
        "data/vault/b1",
        "data/vault/other",
        "data/releases/r1",
        "data/releases/.staging/b1",
        "data/engine_extensions",
    ):
        (root / folder).mkdir(parents=True)
    for name in (PROBE_REL, CHECK_REL):
        shutil.copyfile(ROOT / name, root / name)
    (root / "data" / "public_cache" / "ok.txt").write_text("cache\n", encoding="utf-8")
    (root / "data" / "vault" / "other" / "secret.txt").write_text(
        "secret\n", encoding="utf-8"
    )
    (root / "data" / "releases" / "r1" / "manifest.txt").write_text(
        "manifest\n", encoding="utf-8"
    )
    (root / ".env").write_text("env-sentinel\n", encoding="utf-8")
    (root / "README.md").write_text("readme\n", encoding="utf-8")
    outside = base / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_text("sentinel\n", encoding="utf-8")
    scenario = base / "scenario.bin"
    scenario.write_text("scenario\n", encoding="utf-8")
    swap = base / "swap"
    swap.mkdir()
    (swap / "swapped.txt").write_text("swapped\n", encoding="utf-8")
    return Fixture(base, root, outside, scenario)


def probe_config(
    fx: Fixture, port: int, abstract: str, hidden: list[str] | None = None
) -> str:
    """Return the probe's JSON configuration for a fixture."""
    import json

    interpreter = launch.interpreter_for(launch.current_venv())
    hidden_paths = hidden if hidden is not None else [str(path) for path in fx.hidden]
    return json.dumps(
        {
            "sentinel": str(fx.outside / "sentinel.txt"),
            "outside_dir": str(fx.outside),
            "cache_dir": str(fx.root / "data" / "public_cache"),
            "vault_dir": str(fx.root / "data" / "vault" / "b1"),
            "staging_dir": str(fx.root / "data" / "releases" / ".staging" / "b1"),
            "hidden": hidden_paths,
            "port": port,
            "abstract": abstract,
            "venv_dir": str(launch.current_venv()),
            "code_dir": str(fx.root / "core" / "src"),
            "interpreter_dir": str(interpreter.real),
            "inside_dir": str(fx.root / "scripts" / "sandbox_inside"),
            "extensions_dir": str(fx.root / "data" / "engine_extensions"),
        }
    )


def _lines(done: subprocess.CompletedProcess[str], what: str) -> list[str]:
    if done.returncode != 0 or done.stderr:
        raise AssertionError(
            f"{what}: status {done.returncode}, stderr {done.stderr!r}, stdout {done.stdout!r}"
        )
    text = done.stdout
    if text and not text.endswith("\n"):
        raise AssertionError(f"{what}: stdout does not end with a newline: {text!r}")
    return text.splitlines()


def run_inside(
    profile_name: str,
    fx: Fixture,
    config: str,
    attempts: Sequence[str],
    extensions: Path | None = None,
) -> list[str]:
    """Run the probe inside a profile and return its lines."""
    layout = fx.layout(profile_name)
    if extensions is not None:
        layout = dataclasses.replace(layout, extensions=extensions)
    result = launch.run_in_sandbox(
        profile_name,
        layout,
        launch.python_command(str(fx.root / PROBE_REL), config, *attempts),
        timeout=60,
    )
    return _lines(
        subprocess.CompletedProcess(
            [], result.returncode, result.stdout, result.stderr
        ),
        profile_name,
    )


def run_loader(
    profile_name: str, fx: Fixture, extensions: Path, mode: str
) -> list[str]:
    """Run the extension loader inside a profile and return its lines."""
    layout = dataclasses.replace(fx.layout(profile_name), extensions=extensions)
    result = launch.run_in_sandbox(
        profile_name,
        layout,
        launch.python_command(str(fx.root / CHECK_REL), str(extensions), mode),
        timeout=60,
    )
    return _lines(
        subprocess.CompletedProcess(
            [], result.returncode, result.stdout, result.stderr
        ),
        mode,
    )


def run_outside(fx: Fixture, config: str, attempts: Sequence[str]) -> list[str]:
    """Run the probe beside the sandbox and return its lines."""
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(fx.root / PROBE_REL), config, *attempts],
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    return _lines(done, "outside")


def exposed(module: object, name: str) -> Any:
    """Return an attribute of a module that mypy does not treat as a re-export."""
    return getattr(module, name)


def require_environment(testcase: Any) -> None:
    """Fail, never skip, when bubblewrap or the project environment is missing."""
    testcase.assertTrue(
        os.access(tables.BWRAP, os.X_OK),
        "bubblewrap is required at /usr/bin/bwrap: install the distribution package "
        "bubblewrap; the sandbox tests are never skipped (TST-62)",
    )
    launch.current_venv()


def require_engine(testcase: Any) -> None:
    """Fail, never skip, when the engine group is not installed."""
    try:
        importlib.import_module("duckdb")
    except ImportError:
        testcase.fail(f"duckdb is not installed: {SYNC_HINT}")


@contextmanager
def sandbox_argv(
    fx: Fixture, profile_name: str, command: Sequence[str]
) -> Iterator[tuple[list[str], dict[Path, int]]]:
    """Open the fixture's sources and yield the command line and the descriptors."""
    interpreter = launch.interpreter_for(launch.current_venv())
    profile = launch.profile_named(profile_name)
    descriptors = launch.open_sources(profile, fx.layout(profile_name), interpreter)
    try:
        argv = launch.build_argv(
            profile, fx.layout(profile_name), interpreter, command, descriptors
        )
        yield argv, descriptors
    finally:
        launch.close_all(descriptors)


def run_argv(
    argv: Sequence[str],
    descriptors: Mapping[Path, int],
    env: Mapping[str, str],
    extra: Sequence[int] = (),
) -> list[str]:
    """Run an argument list directly, with the mount descriptors passed through."""
    done = subprocess.run(
        list(argv),
        env=dict(env),
        pass_fds=sorted([*descriptors.values(), *extra]),
        capture_output=True,
        text=True,
        check=False,
    )
    return _lines(done, "argv")


def swap_source(fx: Fixture, kind: str) -> None:
    """Replace a checked path after it has been opened."""
    if kind == "rename":
        os.rename(fx.root / "data" / "public_cache", fx.base / "cache.moved")
        os.rename(fx.base / "swap", fx.root / "data" / "public_cache")
        return
    if kind == "link":
        os.rename(fx.root / "data" / "vault" / "b1", fx.base / "vault.moved")
        os.symlink(fx.base / "swap", fx.root / "data" / "vault" / "b1")
        return
    if kind == "scenario":
        os.rename(fx.scenario, fx.base / "scenario.moved")
        os.mkdir(fx.scenario)
        return
    raise AssertionError(f"unknown swap {kind}")


def _drop_remount(argv: list[str], destination: str) -> None:
    """Remove the ``--remount-ro`` pair whose destination is ``destination``."""
    index = 0
    while index < len(argv) - 1:
        if argv[index] == "--remount-ro" and argv[index + 1] == destination:
            del argv[index : index + 2]
            return
        index += 1
    raise AssertionError(f"no --remount-ro {destination}")


def mutate(argv: Sequence[str], kind: str, fx: Fixture) -> list[str]:
    """Return a copy of an argument list with exactly one planted change."""
    found = list(argv)
    if kind == "no-unshare-net":
        found.remove("--unshare-net")
    elif kind == "share-net":
        found.insert(found.index("--chdir"), "--share-net")
    elif kind == "bind-outside":
        index = found.index("--chdir")
        found[index:index] = ["--ro-bind", str(fx.outside), str(fx.outside)]
    elif kind == "cache-writable":
        index = found.index(str(fx.root / "data" / "public_cache"))
        if found[index - 2] != "--ro-bind-fd":
            raise AssertionError("cache bind is not read-only")
        found[index - 2] = "--bind-fd"
    elif kind == "no-remount-ro":
        _drop_remount(found, "/")
    elif kind == "no-extension-remount-ro":
        _drop_remount(found, str(fx.root / "data" / "engine_extensions"))
    elif kind == "no-clearenv":
        found.remove("--clearenv")
    elif kind == "bind-repo":
        index = found.index("--chdir")
        found[index:index] = ["--ro-bind", str(fx.root), str(fx.root)]
    else:
        raise AssertionError(f"unknown mutation {kind}")
    if sum(left != right for left, right in zip(argv, found, strict=False)) == 0 and (
        len(found) == len(argv)
    ):
        raise AssertionError(f"mutation {kind} changed nothing")
    return found


class FakeError(Exception):
    """Stand-in for ``duckdb.Error``."""


class InvalidInputException(FakeError):
    """Stand-in for the locked-configuration error."""


class _Connection:
    """One fake connection. Statements are recorded on the module."""

    def __init__(self, module: FakeDuckdb, config: dict[str, Any]) -> None:
        self.module = module
        self.config = config
        self._one: Any = None
        self._all: Any = None

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> _Connection:
        self.module.statements.append(sql)
        for needle, error in self.module.fail_on:
            if needle in sql:
                raise error
        self._one, self._all = self.module.respond(sql, params, self.config)
        return self

    def fetchone(self) -> Any:
        return self._one

    def fetchall(self) -> Any:
        return self._all


class FakeDuckdb:
    """Stand-in for the ``duckdb`` module used by the fetch and the loader."""

    Error = FakeError

    def __init__(self) -> None:
        self.version = "v2.0.0"
        self.configs: list[Any] = []
        self.statements: list[str] = []
        self.fail_on: list[tuple[str, BaseException]] = []
        self.allow_lock_change = False
        self.loaded = ["spatial", "h3"]
        self.use_row: tuple[str, ...] = ("POINT (1 2)", "abc")
        self.listing = [("h3", "1.2.3", "community"), ("spatial", "1.2.3", "core")]

    def connect(self, config: dict[str, Any] | None = None) -> _Connection:
        self.configs.append(config)
        return _Connection(self, config or {})

    def respond(
        self, sql: str, params: Sequence[Any] | None, config: dict[str, Any]
    ) -> tuple[Any, Any]:
        """Answer one statement and, for an install, write the four small files."""
        if sql == "select version()":
            return (self.version,), None
        if sql.startswith("INSTALL "):
            name = "h3" if "h3" in sql else "spatial"
            self._write(name, config)
            return None, None
        if sql.startswith("FORCE INSTALL"):
            return None, None
        if sql.startswith("LOAD "):
            return None, None
        if sql.startswith("select current_setting"):
            return ("False",), None
        if "install_path" in sql:
            folder = config["extension_directories"][0].rstrip("/")
            rows = [(name, f"{folder}/{name}") for name in sorted(self.loaded)]
            return None, rows
        if "extension_version" in sql:
            return None, list(self.listing)
        if sql.startswith("select ST_AsText") or sql == (
            "select ST_AsText(ST_Point(1, 2)), h3_latlng_to_cell_string(10.0, 10.0, 8)"
        ):
            return self.use_row, None
        if (
            sql == "SET autoinstall_known_extensions=true"
            and not self.allow_lock_change
        ):
            raise InvalidInputException("configuration has been locked")
        if sql.startswith("select ST_Point"):
            raise FakeError("Catalog Error: ST_Point is not in the catalog")
        return None, None

    def _write(self, name: str, config: dict[str, Any]) -> None:
        folders = config.get("extension_directories") or []
        if not folders:
            return
        base = Path(folders[0]) / self.version / "linux_amd64"
        base.mkdir(parents=True, exist_ok=True)
        (base / f"{name}.duckdb_extension").write_bytes(FAKE_EXTENSION_BYTES[name])
        (base / f"{name}.duckdb_extension.info").write_bytes(b"info")


class FakeRunner:
    """Return queued command results and record every argument list."""

    def __init__(self, results: Sequence[ci_sandbox.CommandResult]) -> None:
        self._results = list(results)
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> ci_sandbox.CommandResult:
        self.calls.append(list(argv))
        if not self._results:
            raise AssertionError("runner called beyond the queue")
        return self._results.pop(0)


class FakeFiles:
    """Bytes of the two profile paths; the target changes after the install."""

    def __init__(
        self,
        source: bytes | None,
        target: bytes | None,
        after: bytes | None,
        runner: FakeRunner | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self.after = after
        self.runner = runner

    def __call__(self, path: Path) -> bytes:
        if path == ci_sandbox.PROFILE_SOURCE:
            data = self.source
        elif path == ci_sandbox.PROFILE_TARGET:
            installed = self.runner is not None and any(
                call == ci_sandbox.INSTALL_ARGV for call in self.runner.calls
            )
            data = self.after if installed else self.target
        else:
            data = None
        if data is None:
            raise FileNotFoundError(path)
        return data


@contextmanager
def pinned_profile() -> Iterator[None]:
    """Patch the profile pin to the synthetic bytes ``PINNED_BYTES``."""
    digest = hashlib.sha256(PINNED_BYTES).hexdigest()
    with (
        patch.object(ci_apparmor, "PROFILE_SIZE", len(PINNED_BYTES)),
        patch.object(ci_apparmor, "PROFILE_SHA256", digest),
    ):
        yield


def load_module(name: str, path: Path) -> Any:
    """Load one program under ``scripts/sandbox_inside`` by its path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_extensions(folder: Path) -> dict[tuple[str, str], dict[str, tuple[int, str]]]:
    """Write four small extension files and return the pin table they match."""
    platform = folder / "v2.0.0" / "linux_amd64"
    platform.mkdir(parents=True)
    pins: dict[str, tuple[int, str]] = {}
    for name, data in FAKE_EXTENSION_BYTES.items():
        (platform / f"{name}.duckdb_extension").write_bytes(data)
        (platform / f"{name}.duckdb_extension.info").write_bytes(b"info")
        pins[name] = (len(data), hashlib.sha256(data).hexdigest())
    return {("v2.0.0", "linux_amd64"): pins}


def extension_copy(base: Path) -> Path:
    """Copy the four real extension files to a new folder and return it."""
    target = base / "ext"
    platform = target / "v2.0.0" / "linux_amd64"
    platform.mkdir(parents=True)
    for name in extension_tree.relative_files(extension_tree.ENGINE):
        shutil.copyfile(ROOT / "data" / "engine_extensions" / name, target / name)
    return target


def files_lines(folder: Path) -> list[str]:
    """Return the loader's ``files`` lines for exactly the four pinned files."""
    engine = extension_tree.ENGINE
    lines = [f"DIR {engine}", f"DIR {engine}/{extension_tree.PLATFORM}"]
    for relative in extension_tree.relative_files(engine):
        digest = hashlib.sha256((folder / relative).read_bytes()).hexdigest()
        lines.append(f"FILE {relative} {digest}")
    return lines


def marker_processes(marker: str) -> list[int]:
    """Return process ids, other than this one, whose command line holds ``marker``."""
    me = os.getpid()
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if marker.encode() in raw:
            found.append(pid)
    return found
