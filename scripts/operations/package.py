"""Prepare one offline application archive from an exact clean committed tree.

The installed product dependency closure is copied once, then reused byte for
byte in both environments. No package manager is allowed to download anything.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.metadata
import re
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from operations.common import Refusal, encoded, sha
from operations.install import archive_manifest, relative_file

SOURCE_PREFIXES = (
    "core/src/",
    "product/src/",
    "scripts/operations/",
    "scripts/commands/",
    "evals/prepared/",
)
SOURCE_FILES = frozenset(
    {
        "uv.lock",
        "pyproject.toml",
        "core/pyproject.toml",
        "product/pyproject.toml",
        "infra/export_register.jsonl",
    }
)


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal("application_source_unavailable") from None
    if result.returncode != 0:
        raise Refusal("application_source_unavailable")
    return result.stdout


def source_files(root: Path, code_version: str) -> dict[str, bytes]:
    if _git(root, "rev-parse", "HEAD").decode().strip() != code_version:
        raise Refusal("application_commit_mismatch")
    _git(
        root,
        "diff",
        "--exit-code",
        "HEAD",
        "--",
        "core",
        "product",
        "scripts/operations",
        "scripts/commands",
        "web",
        "uv.lock",
        "pyproject.toml",
    )
    if _git(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        "core",
        "product",
        "scripts/operations",
        "scripts/commands",
        "web",
    ):
        raise Refusal("application_source_unavailable")
    names = (
        _git(root, "ls-tree", "-r", "--name-only", code_version).decode().splitlines()
    )
    selected = [
        name
        for name in names
        if name in SOURCE_FILES or name.startswith(SOURCE_PREFIXES)
    ]
    if any(
        name.endswith(".py") and name not in names
        for name in ("scripts/operations/serve.py", "scripts/operations/entry.py")
    ):
        raise Refusal("application_input_missing")
    result = {}
    for name in selected:
        # Custodian orchestration is never shipped in the API's executable tree.
        if name in {
            "scripts/operations/build.py",
            "scripts/commands/build_public.py",
            "scripts/commands/build_release.py",
        }:
            continue
        relative_file(name)
        result[name] = _git(root, "show", code_version + ":" + name)
    return result


def dependency_files(lock: bytes) -> dict[str, bytes]:
    packages = {p["name"]: p for p in tomllib.loads(lock.decode())["package"]}
    installed = {
        re.sub(r"[-_.]+", "-", str(d.metadata["Name"]).lower()): d
        for d in importlib.metadata.distributions()
    }
    queue: list[tuple[str, list[str]]] = [("eii-product", [])]
    required: set[str] = set()
    visited: set[tuple[str, tuple[str, ...]]] = set()
    while queue:
        name, extras = queue.pop()
        selection = name, tuple(sorted(extras))
        if selection in visited:
            continue
        visited.add(selection)
        required.add(name)
        package = packages[name]
        dependencies = list(package.get("dependencies", []))
        for extra in extras:
            dependencies.extend(package.get("optional-dependencies", {}).get(extra, []))
        for dep in dependencies:
            marker = dep.get("marker")
            if marker == "sys_platform == 'win32'" and sys.platform != "win32":
                continue
            if (
                marker == "implementation_name != 'pypy'"
                and sys.implementation.name == "pypy"
            ):
                continue
            if (
                marker == "platform_python_implementation != 'PyPy'"
                and sys.implementation.name == "pypy"
            ):
                continue
            if marker == "python_full_version < '3.15'" and sys.version_info[:2] >= (
                3,
                15,
            ):
                continue
            if marker and marker not in {
                "sys_platform == 'win32'",
                "implementation_name != 'pypy'",
                "platform_python_implementation != 'PyPy'",
                "python_full_version < '3.15'",
            }:
                raise Refusal("offline_dependency_marker_unreviewed")
            queue.append((dep["name"], dep.get("extra", [])))
    result: dict[str, bytes] = {}
    versions = {}
    for name in sorted(required - {"eii-core", "eii-product"}):
        distribution = installed.get(name)
        if (
            distribution is None
            or distribution.version != packages[name]["version"]
            or not distribution.files
        ):
            raise Refusal("offline_dependency_missing")
        versions[name] = distribution.version
        for item in distribution.files:
            relative = Path(str(item))
            if ".." in relative.parts or relative.suffix in {".pyc", ".pth"}:
                continue
            original = Path(str(distribution.locate_file(item)))
            if not original.is_file() or original.is_symlink():
                raise Refusal("offline_dependency_missing")
            target = "runtime/site-packages/" + relative.as_posix()
            relative_file(target)
            value = original.read_bytes()
            if item.hash is not None:
                if item.hash.mode != "sha256" or hashlib.sha256(
                    value
                ).digest() != base64.urlsafe_b64decode(
                    item.hash.value + "=" * (-len(item.hash.value) % 4)
                ):
                    raise Refusal("offline_dependency_missing")
            if target in result and result[target] != value:
                raise Refusal("offline_dependency_conflict")
            result[target] = value
    result["runtime/dependencies.json"] = encoded(
        dict(packages=versions, lock_sha256=hashlib.sha256(lock).hexdigest())
    )
    return result


def feature_inventory(files: Mapping[str, bytes]) -> list[str]:
    features = []
    for name, body in sorted(files.items()):
        if name.startswith("product/src/eii_product/api/") and name.endswith(".py"):
            for node in ast.walk(ast.parse(body)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if (
                            isinstance(decorator, ast.Call)
                            and isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr in {"get", "post", "put", "delete"}
                        ):
                            if (
                                decorator.args
                                and isinstance(decorator.args[0], ast.Constant)
                                and isinstance(decorator.args[0].value, str)
                            ):
                                features.append(
                                    decorator.func.attr.upper()
                                    + " "
                                    + decorator.args[0].value
                                )
        if name.startswith("product/src/eii_product/assistant/catalogue/assets/"):
            features.append(
                "catalogue:"
                + name.rsplit("/", 1)[1]
                + ":"
                + hashlib.sha256(body).hexdigest()
            )
        if name.startswith("web/dist/assets/"):
            features.append("component:" + name.rsplit("/", 1)[1])
    return sorted(set(features))


def prepare_archive(
    root: Path, code_version: str, output: Path, environ: Mapping[str, str]
) -> Path:
    files = source_files(root, code_version)
    original_sources = dict(files)
    files.update(dependency_files(files["uv.lock"]))
    env = {k: v for k, v in environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL"}}
    env.update(npm_config_offline="true", npm_config_update_notifier="false")
    try:
        # This invokes only installed, locked build tools. No npm install occurs.
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=root / "web",
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise Refusal("application_web_build_timeout") from None
    except OSError:
        raise Refusal("application_web_build_unavailable") from None
    if result.returncode != 0:
        raise Refusal("application_web_build_nonzero")
    for path in sorted((root / "web/dist").rglob("*")):
        if path.is_symlink():
            raise Refusal("application_inventory_invalid")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    # A concurrent edit cannot enter the archive unnoticed.
    if source_files(root, code_version) != original_sources:
        raise Refusal("application_commit_mismatch")
    return write_archive(files, code_version, output)


def write_archive(files: Mapping[str, bytes], code_version: str, output: Path) -> Path:
    """Seal prepared source, assets and the installed offline dependency closure."""
    manifest: dict[str, Any] = dict(
        code_version=code_version,
        files={
            name: hashlib.sha256(body).hexdigest()
            for name, body in sorted(files.items())
        },
        features=feature_inventory(files),
        python_version=".".join(map(str, sys.version_info[:3])),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(
            {**files, "application.json": encoded(manifest)}.items()
        ):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)
    output.with_suffix(output.suffix + ".sha256").write_text(sha(output))
    archive_manifest(output)
    return output
