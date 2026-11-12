"""Extension tree and the launcher's use of it. No sandbox is started."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support
from test_sandbox_argv import tempfile_tree

import extension_tree
import sandbox_launch as launch

FETCH = "run " + extension_tree.FETCH_COMMAND
P = "v2.0.0/linux_amd64/"
H3 = hashlib.sha256(support.FAKE_EXTENSION_BYTES["h3"]).hexdigest()


def _clear(folder: Path) -> None:
    for child in folder.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)


def _link_into(path: Path, vault: Path) -> None:
    dest = vault / path.name
    path.rename(dest)
    path.symlink_to(dest)


class ExtensionTreeRules(unittest.TestCase):
    def test_extension_tree_cases(self) -> None:
        labels = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            for number in range(1, 27):
                labels.append(number)
                self._one(base, number)
        self.assertEqual(labels, list(range(1, 27)))

    def _one(self, base: Path, number: int) -> None:
        folder = base / f"c{number}" / "ext"
        vault = base / f"c{number}" / "vault"
        vault.mkdir(parents=True)
        pins = support.fake_extensions(folder)
        before = support.descriptor_snapshot()
        with patch.object(extension_tree, "PINNED", pins):
            self._mutate(number, folder, vault)
            if number <= 22:
                files, problems = self._tree(
                    folder, "v9.9.9" if number == 22 else "v2.0.0"
                )
                checked = extension_tree.check_folder(
                    folder, "v9.9.9" if number == 22 else "v2.0.0"
                )
                if number == 2:
                    self.assertIsNone(files)
                    self.assertEqual(problems, [])
                    self.assertEqual(checked, self._want(number), number)
                else:
                    self.assertEqual(problems, self._want(number), number)
                    self.assertEqual(checked, self._want(number), number)
                if number in (1, 20):
                    self.assertEqual(
                        [item.relative for item in files or []],
                        extension_tree.relative_files("v2.0.0"),
                    )
                    for item in files or []:
                        self.assertEqual(
                            os.readlink(f"/proc/self/fd/{item.descriptor}"),
                            str(folder / item.relative),
                        )
                        binary = item.relative.endswith(".duckdb_extension")
                        self.assertEqual(item.sha256 is None, not binary)
                    extension_tree.close_files(files or [])
                else:
                    self.assertEqual(files or [], [])
            else:
                self.assertEqual(
                    extension_tree.check_folder(
                        self._folder_arg(number, folder, base), "v2.0.0"
                    ),
                    self._want(number),
                )
        self.assertEqual(support.descriptor_snapshot(), before, number)

    def _tree(
        self, folder: Path, engine: str
    ) -> tuple[list[extension_tree.Verified] | None, list[str]]:
        root = os.open(folder, extension_tree.PART_FLAGS)
        try:
            return extension_tree.open_tree(root, engine)
        finally:
            os.close(root)

    def _folder_arg(self, number: int, folder: Path, base: Path) -> Path:
        if number == 23:
            link = folder.with_name("via")
            link.symlink_to(folder)
            return link
        if number == 24:
            real = folder.with_name("real")
            folder.rename(real)
            parent = folder.with_name("parent")
            parent.symlink_to(real.parent)
            # real.parent is the case folder, which is not a link. The folder itself
            # must sit below a linked parent, so move it under a real directory.
            holder = base / "c24" / "held"
            holder.mkdir()
            moved = holder / "ext"
            real.rename(moved)
            parent.unlink()
            parent.symlink_to(holder)
            return parent / "ext"
        if number == 25:
            return folder.with_name("missing")
        file = folder.with_name("file")
        file.write_text("x\n", encoding="utf-8")
        return file

    def _mutate(self, number: int, folder: Path, vault: Path) -> None:
        version = folder / "v2.0.0"
        platform = version / "linux_amd64"
        h3 = platform / "h3.duckdb_extension"
        h3_info = platform / "h3.duckdb_extension.info"
        spatial = platform / "spatial.duckdb_extension"
        spatial_info = platform / "spatial.duckdb_extension.info"
        if number == 2:
            _clear(folder)
        elif number == 3:
            _link_into(version, vault)
        elif number == 4:
            _link_into(platform, vault)
        elif number == 5:
            _link_into(h3, vault)
        elif number == 6:
            _link_into(h3_info, vault)
        elif number == 7:
            os.link(spatial, vault / spatial.name)
        elif number == 8:
            spatial_info.unlink()
            os.mkfifo(spatial_info)
        elif number == 9:
            h3.unlink()
            h3.mkdir()
        elif number == 10:
            (platform / "x.duckdb_extension").write_bytes(b"x\n")
        elif number == 11:
            (platform / "sub").mkdir()
        elif number == 12:
            h3_info.unlink()
        elif number == 13:
            shutil.rmtree(version)
            (folder / "EXTENSIONS.json").write_text("{}\n", encoding="utf-8")
        elif number == 14:
            shutil.rmtree(platform)
        elif number == 15:
            shutil.rmtree(version)
            version.write_text("x\n", encoding="utf-8")
        elif number == 16:
            h3.write_bytes(b"")
        elif number == 17:
            h3.write_bytes(b"h3-byte")
        elif number == 18:
            h3.write_bytes(b"h3-BYTES")
        elif number == 19:
            spatial_info.write_bytes(b"")
        elif number == 20:
            extra = folder / "v1.0.0" / "linux_amd64"
            extra.mkdir(parents=True)
            (extra / "x").write_bytes(b"x\n")
        elif number == 21:
            h3_info.unlink()
            spatial.write_bytes(b"")

    def _want(self, number: int) -> list[str]:
        missing = f"v2.0.0 is missing: {FETCH}"
        table = {
            1: [],
            2: [missing],
            3: ["v2.0.0 is a symbolic link"],
            4: [f"{P[:-1]} is a symbolic link"],
            5: [f"{P}h3.duckdb_extension is a symbolic link"],
            6: [f"{P}h3.duckdb_extension.info is a symbolic link"],
            7: [f"{P}spatial.duckdb_extension has 2 hard links, expected 1"],
            8: [f"{P}spatial.duckdb_extension.info is not a regular file"],
            9: [f"{P}h3.duckdb_extension is not a regular file"],
            10: [f"unexpected entry {P}x.duckdb_extension"],
            11: [f"unexpected entry {P}sub"],
            12: [f"{P}h3.duckdb_extension.info is missing: {FETCH}"],
            13: [missing],
            14: [f"v2.0.0/linux_amd64 is missing: {FETCH}"],
            15: ["v2.0.0 is not a folder"],
            16: [f"{P}h3.duckdb_extension is empty"],
            17: [f"{P}h3.duckdb_extension has size 7, pinned 8"],
            18: [
                f"{P}h3.duckdb_extension has a SHA-256 that differs from the pinned {H3}"
            ],
            19: [f"{P}spatial.duckdb_extension.info is empty"],
            20: [],
            21: [
                f"{P}h3.duckdb_extension.info is missing: {FETCH}",
                f"{P}spatial.duckdb_extension is empty",
            ],
            22: [
                "no pinned hashes for engine v9.9.9 on linux_amd64: "
                "review the files and record them in scripts/extension_tree.py"
            ],
            23: ["the extension folder is or lies below a symbolic link"],
            24: ["the extension folder is or lies below a symbolic link"],
            25: [f"the extension folder is missing: {FETCH}"],
            26: ["the extension folder is not a folder"],
        }
        return table[number]

    def test_launcher_binds_the_checked_files(self) -> None:
        labels = []
        with tempfile_tree() as tree:
            labels.append("a")
            opened = tree.open("build-world")
            try:
                self.assertEqual(list(opened), tree.bound("build-world"))
                self.assertEqual(len(opened), 14)
                for path in launch.extension_files(tree.layout("build-world")):
                    descriptor = opened[path]
                    self.assertEqual(
                        os.readlink(f"/proc/self/fd/{descriptor}"), str(path)
                    )
                    status = os.fstat(descriptor)
                    self.assertTrue(stat.S_ISREG(status.st_mode))
                    self.assertEqual(status.st_nlink, 1)
            finally:
                launch.close_all(opened)
            labels.append("b")
            _clear(tree.extensions)
            opened = tree.open("build-world")
            try:
                file_set = set(launch.extension_files(tree.layout("build-world")))
                self.assertEqual(
                    list(opened),
                    [
                        path
                        for path in tree.bound("build-world")
                        if path not in file_set
                    ],
                )
            finally:
                launch.close_all(opened)
            support.fake_extensions(tree.extensions)
            labels.append("c")
            self._swap_error(
                tree, tree.extensions / "v2.0.0", "v2.0.0 is a symbolic link"
            )
            labels.append("d")
            self._swap_error(
                tree,
                tree.extensions / "v2.0.0" / "linux_amd64",
                "v2.0.0/linux_amd64 is a symbolic link",
            )
            labels.append("e")
            binary = tree.extensions / "v2.0.0" / "linux_amd64" / "h3.duckdb_extension"
            os.link(binary, tree.base / "h3-link")
            with self.assertRaises(launch.SandboxError) as caught:
                tree.open("build-world")
            self.assertEqual(
                str(caught.exception),
                f"extension folder {tree.extensions}: {P}h3.duckdb_extension has 2 hard links, expected 1",
            )
            binary.unlink()
            os.rename(tree.base / "h3-link", binary)
            labels.append("f")
            real = tree.extensions.with_name("ext-real")
            tree.extensions.rename(real)
            tree.extensions.symlink_to(real)
            with self.assertRaises(launch.SandboxError) as caught:
                tree.open("build-world")
            self.assertEqual(
                str(caught.exception),
                f"mount source is or lies below a symbolic link: {tree.extensions}",
            )
            tree.extensions.unlink()
            real.rename(tree.extensions)
            labels.append("g")
            _link_into(tree.extensions / "v2.0.0", tree.vault)
            calls: list[object] = []
            with (
                patch.object(
                    support.exposed(launch, "os"), "access", return_value=True
                ),
                patch.object(
                    support.exposed(launch, "subprocess"),
                    "Popen",
                    lambda *args, **kwargs: calls.append(args),
                ),
                self.assertRaises(launch.SandboxError) as caught,
            ):
                launch.run_in_sandbox(
                    "build-world", tree.layout("build-world"), ["/bin/true"]
                )
            self.assertIn("v2.0.0 is a symbolic link", str(caught.exception))
            self.assertEqual(calls, [])
            labels.append("h")
            _clear(tree.extensions)
            support.fake_extensions(tree.extensions)
            opened = tree.open("build-world")
            files = launch.extension_files(tree.layout("build-world"))
            binaries = [path for path in files if path.suffix == ""]
            # suffix of h3.duckdb_extension is .duckdb_extension; select by name ending.
            binaries = [
                path for path in files if path.name.endswith(".duckdb_extension")
            ]
            partial = {
                path: fd
                for path, fd in opened.items()
                if path not in files or path in binaries
            }
            try:
                with self.assertRaises(launch.SandboxError) as caught:
                    launch.build_argv(
                        launch.profile_named("build-world"),
                        tree.layout("build-world"),
                        tree.interpreter(),
                        ["/bin/true"],
                        partial,
                    )
                shown = ", ".join(str(path) for path in binaries)
                self.assertEqual(
                    str(caught.exception),
                    f"only some extension files have a descriptor: {shown}",
                )
            finally:
                launch.close_all(opened)
            labels.append("i")
            opened = tree.open("build-world")
            kept = {path: fd for path, fd in opened.items() if path not in set(files)}
            try:
                argv = launch.build_argv(
                    launch.profile_named("build-world"),
                    tree.layout("build-world"),
                    tree.interpreter(),
                    ["/bin/true", "-I", "-B", "/tmp/probe"],
                    kept,
                )
            finally:
                launch.close_all(opened)
            self.assertEqual(len(argv), 72)
            cache = str(tree.cache)
            index = argv.index(cache)
            self.assertEqual(
                argv[index + 1 : index + 4],
                ["--dir", str(tree.extensions), "--ro-bind-fd"],
            )
        self.assertEqual(labels, list("abcdefghi"))

    def _swap_error(self, tree: tempfile_tree, path: Path, detail: str) -> None:
        _link_into(path, tree.vault)
        with self.assertRaises(launch.SandboxError) as caught:
            tree.open("build-world")
        self.assertEqual(
            str(caught.exception), f"extension folder {tree.extensions}: {detail}"
        )
        path.unlink()
        (tree.vault / path.name).rename(path)

    def test_every_source_descriptor_names_its_object_after_a_swap(self) -> None:
        system = {Path("/usr/lib/x86_64-linux-gnu"), Path("/usr/lib64")}
        labels = []
        for profile in ("build-world", "build-release"):
            labels.append(profile)
            with tempfile_tree() as tree:
                before = support.descriptor_snapshot()
                opened = tree.open(profile)
                try:
                    swapped = set()
                    for path, descriptor in opened.items():
                        if path in system:
                            continue
                        status = os.fstat(descriptor)
                        moved = path.with_name(path.name + ".moved")
                        os.rename(path, moved)
                        if stat.S_ISREG(status.st_mode):
                            path.write_bytes(b"new\n")
                        else:
                            path.mkdir()
                        again = os.fstat(descriptor)
                        self.assertEqual(
                            (again.st_ino, again.st_dev), (status.st_ino, status.st_dev)
                        )
                        self.assertEqual(
                            os.readlink(f"/proc/self/fd/{descriptor}"), str(moved)
                        )
                        swapped.add(path)
                    self.assertEqual(swapped, set(opened) - system)
                    self.assertEqual(len(swapped), 12)
                finally:
                    launch.close_all(opened)
                self.assertEqual(support.descriptor_snapshot(), before)
        self.assertEqual(labels, ["build-world", "build-release"])
