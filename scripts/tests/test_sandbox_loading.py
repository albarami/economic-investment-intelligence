"""Extension loading inside the sandbox. The engine group must be installed."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import extension_tree
import sandbox_check
import sandbox_launch as launch
import sandbox_profiles as tables

pytestmark = pytest.mark.sandbox
REAL = support.ROOT / "data" / "engine_extensions"
OFFSET = 260_000


class LoadingRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        support.require_environment(cls)
        support.require_engine(cls)

    def test_load_offline_read_only_in_both_profiles(self) -> None:
        self.assertEqual(
            extension_tree.check_folder(REAL, extension_tree.ENGINE),
            [],
            "engine extensions are not fetched or differ from the pin; run: "
            + extension_tree.FETCH_COMMAND,
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            config = support.probe_config(fx, port, abstract, hidden=[])
            expected_files = support.files_lines(REAL)
            for profile in ("build-world", "build-release"):
                self.assertEqual(
                    support.run_loader(profile, fx, REAL, "load"),
                    list(sandbox_check.LOAD_LINES),
                )
                self.assertEqual(
                    support.run_loader(profile, fx, REAL, "files"), expected_files
                )
                self.assertEqual(
                    support.run_inside(
                        profile, fx, config, ["tcp_unrouted", "fds"], extensions=REAL
                    ),
                    ["tcp_unrouted error OSError ENETUNREACH", "fds none"],
                )
        self.assertEqual(sandbox_check.check_extensions(), [])

    def test_signature_check_stays_on(self) -> None:
        labels = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            folder = base / "ext"
            platform = folder / "v2.0.0" / "linux_amd64"
            platform.mkdir(parents=True)
            source = REAL / "v2.0.0" / "linux_amd64"
            shutil.copyfile(
                source / "h3.duckdb_extension", platform / "h3.duckdb_extension"
            )
            shutil.copyfile(
                source / "h3.duckdb_extension.info",
                platform / "h3.duckdb_extension.info",
            )
            binary = platform / "h3.duckdb_extension"
            pinned = _h3_pin(binary)
            fx = support.make_fixture(base / "fx")
            labels.append("clean")
            with patch.object(extension_tree, "PINNED", pinned):
                self.assertEqual(
                    support.run_loader("build-world", fx, folder, "load"),
                    _partial(ok=True),
                )
            labels.append("changed")
            changed = bytearray(binary.read_bytes())
            changed[OFFSET] ^= 1
            binary.write_bytes(changed)
            with patch.object(extension_tree, "PINNED", _h3_pin(binary)):
                self.assertEqual(
                    support.run_loader("build-world", fx, folder, "load"),
                    _partial(ok=False),
                )
            labels.append("missing-info")
            binary.write_bytes(bytes(changed))
            # restore the clean binary so only the missing info is the fault
            shutil.copyfile(source / "h3.duckdb_extension", binary)
            (platform / "h3.duckdb_extension.info").unlink()
            with patch.object(extension_tree, "PINNED", _h3_pin(binary)):
                with self.assertRaises(launch.SandboxError) as caught:
                    support.run_loader("build-world", fx, folder, "load")
            self.assertEqual(
                str(caught.exception),
                "extension folder "
                f"{folder}: v2.0.0/linux_amd64/h3.duckdb_extension.info is missing: run "
                + extension_tree.FETCH_COMMAND,
            )
            self.assertEqual(
                (source / "h3.duckdb_extension").read_bytes()[:8],
                (REAL / "v2.0.0" / "linux_amd64" / "h3.duckdb_extension").read_bytes()[
                    :8
                ],
            )
        self.assertEqual(labels, ["clean", "changed", "missing-info"])

    def test_empty_folder_and_read_only_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fx = support.make_fixture(base / "fx")
            empty = base / "empty"
            empty.mkdir()
            self.assertEqual(
                support.run_loader("build-world", fx, empty, "load"),
                [
                    f"engine duckdb {extension_tree.ENGINE}",
                    "settings autoinstall_known_extensions=False autoload_known_extensions=False "
                    "allow_unsigned_extensions=False",
                    "LOAD spatial error IOException not-found",
                    "LOAD h3 error IOException not-found",
                    "LOCK autoinstall error InvalidInputException locked",
                ],
            )
            self.assertEqual(
                support.run_loader("build-world", fx, empty, "install"),
                [
                    "INSTALL h3 error IOException read-only",
                    "FORCE spatial error IOException read-only",
                ],
            )
            self.assertEqual(
                support.run_loader("build-world", fx, REAL, "install"),
                ["INSTALL h3 ok", "FORCE spatial error IOException no-network"],
            )

    def test_automatic_loading_is_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = support.make_fixture(tmp)
            self.assertEqual(
                support.run_loader("build-world", fx, REAL, "autoload"),
                ["QUERY st_point error CatalogException not-in-catalog"],
            )

    def test_namespace_creation_refused_is_reported(self) -> None:
        done = subprocess.run(
            [
                tables.BWRAP,
                "--unshare-user",
                "--disable-userns",
                "--dev-bind",
                "/",
                "/",
                str(launch.current_venv() / "bin" / "python"),
                "scripts/sandbox_check.py",
                "check",
            ],
            cwd=support.ROOT,
            env={},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stderr, "")
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertRegex(lines[0], r"bubblewrap [0-9]+\.[0-9]+\.[0-9]+")
        refused = (
            "could not enter the sandbox {name}: bwrap: Creating new namespace failed: "
            "nesting depth or /proc/sys/user/max_*_namespaces exceeded (ENOSPC)"
        )
        self.assertEqual(
            lines[1], "FAIL profile build-world: " + refused.format(name="build-world")
        )
        self.assertEqual(
            lines[2],
            "FAIL profile build-release: " + refused.format(name="build-release"),
        )
        self.assertEqual(lines[3], "sandbox: FAILED")

    def test_extension_files_are_the_checked_objects(self) -> None:
        labels = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (_port, _abstract),
        ):
            base = Path(tmp).resolve()
            folder = support.extension_copy(base)
            fx = support.make_fixture(base / "fx")
            expected = support.files_lines(folder)
            platform = folder / "v2.0.0" / "linux_amd64"
            names = [
                "h3.duckdb_extension",
                "spatial.duckdb_extension",
                "h3.duckdb_extension.info",
                "spatial.duckdb_extension.info",
            ]
            for index, name in enumerate(names, start=1):
                labels.append(str(index))
                self._swap_case(fx, folder, platform / name, "file", expected)
            labels.append("5")
            self._swap_case(fx, folder, platform, "platform", expected)
            labels.append("6")
            evil = fx.root / "data" / "vault" / "b1" / "evil" / "linux_amd64"
            evil.mkdir(parents=True)
            for name in names:
                (evil / name).write_bytes(b"garbage\n")
            self._swap_case(
                fx, folder, folder / "v2.0.0", "version", expected, evil.parent
            )
        self.assertEqual(labels, ["1", "2", "3", "4", "5", "6"])

    def _swap_case(
        self,
        fx: support.Fixture,
        folder: Path,
        path: Path,
        kind: str,
        expected_files: list[str],
        evil: Path | None = None,
    ) -> None:
        for mode, expected in (
            ("files", expected_files),
            ("load", list(sandbox_check.LOAD_LINES)),
        ):
            real_open = extension_tree.open_tree

            def wrapped(
                root: int,
                engine: str,
                pinned: object = None,
                real: Callable[..., tuple[Any, list[str]]] = real_open,
                path: Path = path,
                kind: str = kind,
                evil: Path | None = evil,
            ) -> tuple[Any, list[str]]:
                found = real(root, engine, pinned)
                _apply_swap(path, kind, evil)
                return found

            with patch.object(
                support.exposed(launch, "extension_tree"), "open_tree", wrapped
            ):
                self.assertEqual(
                    support.run_loader("build-world", fx, folder, mode), expected
                )
            self.assertTrue(path.exists() or path.is_symlink())
            _undo_swap(path, kind)


def _h3_pin(binary: Path) -> dict[tuple[str, str], dict[str, tuple[int, str]]]:
    data = binary.read_bytes()
    return {
        (extension_tree.ENGINE, extension_tree.PLATFORM): {
            "h3": (len(data), hashlib.sha256(data).hexdigest())
        }
    }


def _partial(ok: bool) -> list[str]:
    load = "LOAD h3 ok" if ok else "LOAD h3 error IOException bad-signature"
    lines = [
        f"engine duckdb {extension_tree.ENGINE}",
        "settings autoinstall_known_extensions=False autoload_known_extensions=False "
        "allow_unsigned_extensions=False",
        "LOAD spatial error IOException not-found",
        load,
    ]
    if ok:
        lines.append("PATH h3 inside")
    lines.append("LOCK autoinstall error InvalidInputException locked")
    return lines


def _apply_swap(path: Path, kind: str, evil: Path | None) -> None:
    if kind == "file" and path.suffix == "":
        data = path.read_bytes()
        path.rename(path.with_name(path.name + ".moved"))
        if path.name.endswith(".info.moved") or path.name.endswith(".info"):
            path.write_bytes(b"garbage\n")
            return
        changed = bytearray(data)
        changed[len(changed) // 2] ^= 1
        path.write_bytes(changed)
        return
    if kind == "file":
        data = path.read_bytes()
        path.rename(path.with_name(path.name + ".moved"))
        if ".info" in path.name:
            path.write_bytes(b"garbage\n")
        else:
            changed = bytearray(data)
            changed[len(changed) // 2] ^= 1
            path.write_bytes(changed)
        return
    if kind == "platform":
        path.rename(path.with_name(path.name + ".moved"))
        path.mkdir()
        for name in (
            "h3.duckdb_extension",
            "h3.duckdb_extension.info",
            "spatial.duckdb_extension",
            "spatial.duckdb_extension.info",
        ):
            (path / name).write_bytes(b"garbage\n")
        return
    path.rename(path.with_name(path.name + ".moved"))
    if evil is None:
        raise AssertionError("version swap needs the vault folder")
    path.symlink_to(evil)


def _undo_swap(path: Path, kind: str) -> None:
    moved = path.with_name(path.name + ".moved")
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    if moved.exists() or moved.is_symlink():
        moved.rename(path)
