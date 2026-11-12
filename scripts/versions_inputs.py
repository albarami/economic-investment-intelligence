"""Safe reads, shape checks and the git candidate list."""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import stat
import subprocess
import tomllib
from collections.abc import Collection, Iterable, Mapping
from pathlib import Path

WATCHED = (
    "pyproject.toml",
    "uv.lock",
    "uv.toml",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    ".npmrc",
    ".python-version",
    ".nvmrc",
    ".node-version",
    ".tool-versions",
    "requirements*.txt",
    "constraints*.txt",
)
GIT_NOT_TOP = "root is not the top of a git work tree"
Failure = tuple[str, str, str]

_JSON_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


class _DuplicateKeyError(ValueError):
    """A JSON object repeated a key."""


def read_input(root: Path, rel: str, kind: str) -> tuple[object | None, str | None]:
    """Read one input, or return the detail of rule ``input``."""
    path = root / rel
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    if not stat.S_ISREG(info.st_mode):
        return None, "not a regular file"
    try:
        data = path.read_bytes()
    except OSError:
        return None, "unreadable"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not valid UTF-8"
    if kind == "text":
        return text, None
    if kind == "toml":
        try:
            return tomllib.loads(text), None
        except tomllib.TOMLDecodeError:
            return None, "not valid TOML"
    try:
        parsed = json.loads(text, object_pairs_hook=_pairs)
    except _DuplicateKeyError:
        return None, "duplicate key"
    except json.JSONDecodeError:
        return None, "not valid JSON"
    if not isinstance(parsed, dict):
        return None, "top level is not an object"
    return parsed, None


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    collected: dict[str, object] = {}
    for key, value in items:
        if key in collected:
            raise _DuplicateKeyError(key)
        collected[key] = value
    return collected


def git_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """Return the allow-list for every git child process."""
    child = {
        "LANG": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    if "PATH" in environ:
        child["PATH"] = environ["PATH"]
    return child


def list_candidates(
    root: Path, environ: Mapping[str, str]
) -> tuple[list[str] | None, str | None]:
    """Return the sorted git candidate paths, or an ``input`` detail."""
    search = environ["PATH"] if "PATH" in environ else ""
    git = shutil.which("git", path=search)
    if git is None:
        return None, "not found on PATH"
    if not (root / ".git").exists():
        return None, GIT_NOT_TOP
    child = git_environment(environ)
    try:
        parsed = subprocess.run(
            [
                git,
                "-c",
                f"core.excludesFile={os.devnull}",
                "-C",
                str(root),
                "rev-parse",
                "--show-toplevel",
            ],
            capture_output=True,
            env=child,
            check=False,
        )
    except OSError as exc:
        return None, f"could not run ({type(exc).__name__})"
    if parsed.returncode != 0:
        return None, f"rev-parse exit status {parsed.returncode}"
    top = parsed.stdout.decode("utf-8", errors="replace")
    if top.endswith("\n"):
        top = top[:-1]
    if top.endswith("\r"):
        top = top[:-1]
    if Path(top).resolve() != root.resolve():
        return None, GIT_NOT_TOP
    try:
        listed = subprocess.run(
            [
                git,
                "-c",
                f"core.excludesFile={os.devnull}",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            env=child,
            check=False,
        )
    except OSError as exc:
        return None, f"could not run ({type(exc).__name__})"
    if listed.returncode != 0:
        return None, f"ls-files exit status {listed.returncode}"
    try:
        text = listed.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None, "output is not valid UTF-8"
    seen: list[str] = []
    for name in text.split("\0"):
        if name and name not in seen:
            seen.append(name)
    seen.sort()
    return seen, None


def find_unscanned(
    root: Path, candidates: Iterable[str], judged: Collection[str]
) -> list[Failure]:
    """Apply rule 17 to a candidate list. It lists no folder and starts no process."""
    failures: list[Failure] = []
    for rel in sorted(candidates):
        final = "" if rel.endswith("/") else rel.rsplit("/", 1)[-1]
        if not any(fnmatch.fnmatchcase(final, pattern) for pattern in WATCHED):
            continue
        try:
            os.lstat(root / rel)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError:
            failures.append(("unscanned", rel, "unreadable"))
            continue
        if rel in judged:
            continue
        if final == "uv.toml":
            failures.append(("unscanned", rel, "shadows tool.uv in pyproject.toml"))
        else:
            failures.append(("unscanned", rel, "not a judged input"))
    return failures


def shape_pyproject(doc: dict[str, object]) -> list[str]:
    """Return the first shape failure of each pyproject field."""
    details: list[str] = []
    project = doc.get("project")
    if not isinstance(project, dict):
        details.append("project is not a table")
    else:
        if "dependencies" in project and not _string_list(project.get("dependencies")):
            details.append("project.dependencies is not a list of strings")
        if "optional-dependencies" in project:
            optional = project.get("optional-dependencies")
            if not isinstance(optional, dict):
                details.append("project.optional-dependencies is not a table")
            else:
                for group, items in optional.items():
                    if not _string_list(items):
                        details.append(
                            f"project.optional-dependencies.{group} is not a list of strings"
                        )
    if "tool" in doc:
        tool = doc.get("tool")
        uv_present = isinstance(tool, dict) and "uv" in tool
        uv = tool.get("uv") if isinstance(tool, dict) else None
        if not isinstance(tool, dict) or (uv_present and not isinstance(uv, dict)):
            details.append("tool.uv is not a table")
    if "dependency-groups" in doc:
        groups = doc.get("dependency-groups")
        if not isinstance(groups, dict):
            details.append("dependency-groups is not a table")
        else:
            for group, items in groups.items():
                if not _string_or_table_list(items):
                    details.append(
                        f"dependency-groups.{group} is not a list of strings and tables"
                    )
    return details


def members_of(doc: dict[str, object]) -> tuple[list[str] | None, str | None]:
    """Return workspace members, or the members input detail.

    When ``tool.uv`` is not a table the members line is not given.
    """
    tool = doc.get("tool", {})
    if not isinstance(tool, dict):
        return None, None
    uv = tool.get("uv", {})
    if not isinstance(uv, dict):
        return None, None
    workspace = uv.get("workspace")
    members = workspace.get("members") if isinstance(workspace, dict) else None
    if not isinstance(members, list) or not all(
        isinstance(item, str) for item in members
    ):
        return None, "tool.uv.workspace.members is not a list of strings"
    return [item for item in members if isinstance(item, str)], None


def shape_uv_lock(doc: dict[str, object]) -> list[str]:
    """Return the first shape failure of each uv lock field."""
    package = doc.get("package")
    if not isinstance(package, list):
        return ["package is not an array of tables"]
    details: list[str] = []
    for index, item in enumerate(package):
        if not isinstance(item, dict):
            details.append(f"package[{index}] is not a table")
            continue
        if not isinstance(item.get("name"), str):
            details.append(f"package[{index}].name is not a string")
        if "version" in item and not isinstance(item.get("version"), str):
            details.append(f"package[{index}].version is not a string")
        if "source" in item and not isinstance(item.get("source"), dict):
            details.append(f"package[{index}].source is not a table")
    return details


def shape_package_json(doc: dict[str, object]) -> list[str]:
    """Return the first shape failure of each package.json field."""
    details: list[str] = []
    for section in _JSON_SECTIONS:
        if section not in doc:
            continue
        value = doc[section]
        if not isinstance(value, dict):
            details.append(f"{section} is not an object")
            continue
        for name, spec in value.items():
            if not isinstance(spec, str):
                details.append(f"{section}.{name} is not a string")
    if "engines" in doc and not isinstance(doc.get("engines"), dict):
        details.append("engines is not an object")
    return details


def shape_package_lock(doc: dict[str, object]) -> list[str]:
    """Return the first shape failure of each npm lock field."""
    if "packages" not in doc:
        return ["packages is missing"]
    packages = doc.get("packages")
    if not isinstance(packages, dict):
        return ["packages is not an object"]
    details: list[str] = []
    for key, value in packages.items():
        if not isinstance(value, dict):
            details.append(f'packages["{key}"] is not an object')
            continue
        if "version" in value and not isinstance(value.get("version"), str):
            details.append(f'packages["{key}"].version is not a string')
    return details


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _string_or_table_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str | dict) for item in value
    )
