"""Fixture trees, stub tools and runners for the version-pin tests."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_versions as check_versions
import versions_inputs as versions_inputs
import versions_record as versions_record
import versions_tools as versions_tools

_SCRIPTS = Path(__file__).resolve().parent.parent

_GIT_FOUND = shutil.which("git")
if _GIT_FOUND is None:
    raise RuntimeError("git is required by the tests")
GIT: str = _GIT_FOUND

GOOD_INTERPRETER = (3, 14, 6)
SUMMARY_OK = "checked 12 components: OK"
PACK = "pack, confirm at slice S1"
CITE = "docs/a.md line 5"
SHELL_ENV_KEYS = frozenset({"PWD", "SHLVL", "_", "OLDPWD"})


def summary(k: int) -> str:
    """Return the failure summary line for the twelve-component fixture."""
    return f"checked 12 components: {k} failure(s)"


def escaped(text: str) -> str:
    """Return the one-line form the check writes for an unquoted input string."""
    return text.encode("unicode_escape").decode("ascii")


def git_env() -> dict[str, str]:
    """Return the allow-list used when the tests themselves run git."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture",
    }


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the real git binary against a scratch tree."""
    return subprocess.run(
        [GIT, "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(),
    )


def git_init(root: Path) -> None:
    """Create a scratch repository with no commit."""
    git(root, "init", "-q")


def _row(pairs: Sequence[tuple[str, str]]) -> str:
    body = ", ".join(f'{key} = "{value}"' for key, value in pairs)
    return "{ " + body + " },"


def _pack(name: str, kind: str, pin: str, retreat: str, state: str) -> str:
    pairs = [
        ("name", name),
        ("kind", kind),
        ("pin", pin),
        ("retreat", retreat),
        ("label", PACK),
        ("cite", CITE),
        ("state", state),
        ("first_use", "S0-T12"),
    ]
    return _row(pairs)


def pins_text() -> str:
    """Return the GOOD pin record: twelve components, trailing commas."""
    rows = [
        _row(
            (
                ("name", "python"),
                ("kind", "toolchain"),
                ("pin", "3.14.x"),
                ("retreat", "none recorded"),
                ("label", PACK),
                ("cite", CITE),
                ("state", "installed"),
                ("first_use", "S0-T02"),
            )
        ),
        _row(
            (
                ("name", "uv"),
                ("kind", "toolchain"),
                ("pin", "0.11.31"),
                ("retreat", "none recorded"),
                ("label", "ASSUMPTION"),
                ("cite", CITE),
                ("state", "installed"),
                ("first_use", "S0-T02"),
                ("source", "fixture"),
            )
        ),
        _row(
            (
                ("name", "node"),
                ("kind", "toolchain"),
                ("pin", "22.x"),
                ("floor", "22.12.0"),
                ("retreat", "none recorded"),
                ("label", PACK),
                ("cite", CITE),
                ("state", "installed"),
                ("first_use", "S0-T03"),
            )
        ),
        _row(
            (
                ("name", "npm"),
                ("kind", "toolchain"),
                ("pin", "10.9.x"),
                ("retreat", "none recorded"),
                ("label", "ASSUMPTION"),
                ("cite", CITE),
                ("state", "installed"),
                ("first_use", "S0-T03"),
                ("source", "fixture"),
            )
        ),
        _row(
            (
                ("name", "alpha"),
                ("kind", "python"),
                ("pin", "1.2.3"),
                ("retreat", "none recorded"),
                ("label", "ASSUMPTION"),
                ("cite", CITE),
                ("state", "installed"),
                ("first_use", "S0-T12"),
                ("source", "fixture"),
            )
        ),
        _pack("beta", "python", "2.0.x", "1.5.x", "recorded"),
        _pack("gamma", "python", "3.0.0", "replace:delta", "recorded"),
        _pack("delta", "python", "3.1.0", "none recorded", "recorded"),
        _pack("left", "npm", "4.5.6", "none recorded", "installed"),
        _pack("right", "npm", "7.1.x", "6.0.0", "recorded"),
        _row(
            (
                ("name", "@scope/pkg"),
                ("kind", "npm"),
                ("pin", "1.0.0"),
                ("retreat", "none recorded"),
                ("label", "ASSUMPTION"),
                ("cite", CITE),
                ("state", "installed"),
                ("first_use", "S0-T12"),
                ("source", "fixture"),
            )
        ),
        _pack("service", "external", "18", "none recorded", "recorded"),
    ]
    header = (
        'schema = 1\nconfirm_at = "slice S1"\nspike_result = "not yet run"\n'
        "component = [\n"
    )
    return header + "\n".join(rows) + "\n]\n"


def make_tree(root: Path) -> None:
    """Write the GOOD fixture and make it a scratch git repository."""
    write(root, "pins.toml", pins_text())
    write(
        root,
        "pyproject.toml",
        "\n".join(
            (
                "[project]",
                'name = "eii-workspace"',
                'requires-python = ">=3.14"',
                "",
                "[dependency-groups]",
                'dev = ["alpha==1.2.3"]',
                "",
                "[tool.uv]",
                'required-version = "==0.11.31"',
                "",
                "[tool.uv.workspace]",
                'members = ["core", "custodian"]',
                "",
            )
        ),
    )
    write(
        root,
        "core/pyproject.toml",
        "\n".join(
            (
                "[project]",
                'name = "eii-core"',
                'requires-python = ">=3.14"',
                "",
                "[build-system]",
                'requires = ["uv_build>=0.11.31,<0.12"]',
                'build-backend = "uv_build"',
                "",
            )
        ),
    )
    write(
        root,
        "custodian/pyproject.toml",
        "\n".join(
            (
                "[project]",
                'name = "eii-custodian"',
                'requires-python = ">=3.14"',
                'dependencies = ["eii-core"]',
                "",
                "[build-system]",
                'requires = ["uv_build>=0.11.31,<0.12"]',
                'build-backend = "uv_build"',
                "",
            )
        ),
    )
    write(
        root,
        "uv.lock",
        "\n".join(
            (
                "version = 1",
                "",
                "[[package]]",
                'name = "eii-workspace"',
                'source = { virtual = "." }',
                "",
                "[[package]]",
                'name = "eii-core"',
                'source = { editable = "core" }',
                "",
                "[[package]]",
                'name = "eii-custodian"',
                'source = { editable = "custodian" }',
                "",
                "[[package]]",
                'name = "alpha"',
                'version = "1.2.3"',
                'source = { registry = "https://pypi.org/simple" }',
                "",
            )
        ),
    )
    write(root, ".python-version", "3.14\n")
    write(root, ".nvmrc", "22\n")
    write(
        root,
        "web/package.json",
        "\n".join(
            (
                "{",
                '  "engines": {"node": ">=22.12.0 <23"},',
                '  "dependencies": {"left": "4.5.6"},',
                '  "devDependencies": {"@scope/pkg": "1.0.0"}',
                "}",
                "",
            )
        ),
    )
    write(
        root,
        "web/package-lock.json",
        "\n".join(
            (
                "{",
                '  "lockfileVersion": 3,',
                '  "packages": {',
                '    "": {},',
                '    "node_modules/left": {"version": "4.5.6"},',
                '    "node_modules/@scope/pkg": {"version": "1.0.0"}',
                "  }",
                "}",
                "",
            )
        ),
    )
    write(root, "docs/a.md", "".join(f"line {index}\n" for index in range(1, 41)))
    git_init(root)


def edit(root: Path, rel: str, old: str, new: str) -> None:
    """Replace the one occurrence of ``old`` in a fixture file."""
    path = root / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"edit count {count} for {old!r} in {rel}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def edit_row(root: Path, marker: str, old: str, new: str) -> None:
    """Replace ``old`` inside the one pin-record line that contains ``marker``."""
    path = root / "pins.toml"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    found = [index for index, line in enumerate(lines) if marker in line]
    if len(found) != 1:
        raise AssertionError(f"row count {len(found)} for {marker!r}")
    index = found[0]
    count = lines[index].count(old)
    if count != 1:
        raise AssertionError(f"edit count {count} for {old!r}")
    lines[index] = lines[index].replace(old, new, 1)
    path.write_text("".join(lines), encoding="utf-8")


def write(root: Path, rel: str, text: str) -> None:
    """Write a relative file, creating parent folders."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_tool(bindir: Path, name: str, body: str) -> None:
    """Write an executable POSIX shell script."""
    bindir.mkdir(parents=True, exist_ok=True)
    path = bindir / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def make_bindir(bindir: Path, with_git: bool = True) -> None:
    """Create a stub directory and, by default, a git symlink."""
    bindir.mkdir(parents=True, exist_ok=True)
    if with_git:
        link = bindir / "git"
        if not link.exists():
            link.symlink_to(GIT)


def make_tools(
    bindir: Path,
    uv: str = "uv 0.11.31 (x86_64-unknown-linux-gnu)",
    node: str = "v22.22.3",
    npm: str = "10.9.8",
    with_git: bool = True,
) -> None:
    """Write the three version stubs and the git symlink."""
    make_bindir(bindir, with_git=with_git)
    make_tool(bindir, "uv", f"printf '%s\\n' '{uv}'\n")
    make_tool(bindir, "node", f"printf '%s\\n' '{node}'\n")
    make_tool(bindir, "npm", f"printf '%s\\n' '{npm}'\n")


def ready(case: unittest.TestCase) -> tuple[Path, str]:
    """Build a GOOD tree and a sibling stub directory, both removed later."""
    folder = tempfile.TemporaryDirectory()
    case.addCleanup(folder.cleanup)
    root = Path(folder.name) / "tree"
    root.mkdir()
    make_tree(root)
    bindir = Path(folder.name) / "bin"
    make_tools(bindir)
    return root, str(bindir)


def run(
    root: Path,
    interpreter: tuple[int, int, int] = GOOD_INTERPRETER,
    path: str = "",
) -> list[str]:
    """Run the check in-process and return its output lines."""
    lines, _count = check_versions.run_checks(
        root, interpreter=interpreter, environ={"PATH": path}
    )
    return lines


def cli(
    args: Sequence[str], env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run the check as a child process with exactly ``env``."""
    script = _SCRIPTS / "check_versions.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=dict(env),
        check=False,
    )


def _digest_file(path: Path) -> str:
    if path.is_symlink():
        payload = b"link:" + os.readlink(path).encode("utf-8", "surrogateescape")
    else:
        payload = path.read_bytes()
    return hashlib.sha256(payload).hexdigest()


def tree_digest(root: Path) -> dict[str, str]:
    """Hash every file of a scratch tree the test made."""
    digest: dict[str, str] = {}
    for folder, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in filenames:
            path = Path(folder) / name
            rel = path.relative_to(root).as_posix()
            digest[rel] = _digest_file(path)
    return digest


def closed_set_digest(root: Path, rels: Sequence[str]) -> dict[str, str]:
    """Hash only the listed relative paths."""
    digest: dict[str, str] = {}
    for rel in rels:
        path = root / rel
        digest[rel] = _digest_file(path)
    return digest
