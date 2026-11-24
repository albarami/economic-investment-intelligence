"""Exact-byte Public application and release installation, without a builder."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from operations.common import Refusal, encoded, read_json, sha
from operations.config import Environment, write_target

HASH = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
LOAD_OUTPUTS = frozenset({"release.duckdb", "load_receipt.json"})


def relative_file(name: str) -> Path:
    path = Path(name)
    if (
        not name
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != name
        or name == "."
        or any(
            p in {".env", ".private", "vault", "custodian", "gateway"}
            for p in path.parts
        )
    ):
        raise Refusal("application_inventory_invalid")
    return path


def file_inventory(
    folder: Path, *, exclude: frozenset[str] = frozenset()
) -> dict[str, str]:
    result = {}
    for path in sorted(folder.rglob("*")):
        name = path.relative_to(folder).as_posix()
        if path.is_symlink():
            raise Refusal("install_symbolic_link")
        if path.is_file() and name not in exclude:
            result[name] = sha(path)
    return result


def public_kind(
    folder: Path, register: Path | None = None, *, parameter_set: str | None = None
) -> dict[str, Any]:
    if parameter_set is not None:
        raise Refusal("public_only_parameter_selection")
    document = read_json(folder / "manifest.json", "release_missing")
    if document.get("release_kind") != "public_only":
        raise Refusal("protected_release_requires_s11_t09")
    if (folder / "freeze.json").exists():
        raise Refusal("public_only_freeze_forbidden")
    if register is not None and register.exists():
        try:
            for line in register.read_bytes().splitlines():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError
                if row.get("release_id") == document.get("release_id"):
                    raise Refusal("public_only_register_forbidden")
        except (OSError, ValueError) as error:
            if isinstance(error, Refusal):
                raise
            raise Refusal("application_register_invalid") from None
    return document


def archive_manifest(
    archive: Path, *, expected_sha256: str | None = None
) -> dict[str, Any]:
    try:
        digest = sha(archive)
        checksum = archive.with_suffix(archive.suffix + ".sha256").read_text().strip()
        if checksum != digest or (
            expected_sha256 is not None and digest != expected_sha256
        ):
            raise Refusal("application_checksum_mismatch")
        with zipfile.ZipFile(archive) as source:
            names = source.namelist()
            if len(names) != len(set(names)):
                raise Refusal("application_inventory_invalid")
            document = json.loads(source.read("application.json"))
            if (
                type(document) is not dict
                or set(document)
                != {"code_version", "files", "features", "python_version"}
                or COMMIT.fullmatch(str(document["code_version"])) is None
                or type(document["files"]) is not dict
                or not document["files"]
                or type(document["features"]) is not list
            ):
                raise Refusal("application_inventory_invalid")
            if set(names) != set(document["files"]) | {"application.json"}:
                raise Refusal("application_inventory_invalid")
            for name, expected in document["files"].items():
                relative_file(name)
                mode = source.getinfo(name).external_attr >> 16
                if (
                    stat.S_ISLNK(mode)
                    or not HASH.fullmatch(str(expected))
                    or hashlib.sha256(source.read(name)).hexdigest() != expected
                ):
                    raise Refusal("application_verification_failed")
            for required in (
                "product/src/eii_product/api/app.py",
                "core/src/eii_core/__init__.py",
                "web/dist/index.html",
                "runtime/dependencies.json",
                "scripts/operations/serve.py",
            ):
                if required not in document["files"]:
                    raise Refusal("application_input_missing")
            return document
    except Refusal:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        raise Refusal("application_verification_failed") from None


def verify_application(
    folder: Path,
    *,
    code_version: str,
    application_sha256: str,
    archive: Path | None = None,
) -> dict[str, Any]:
    if (
        folder.name != application_sha256
        or not HASH.fullmatch(application_sha256)
        or any(part.is_symlink() for part in (folder, *folder.parents))
    ):
        raise Refusal("mutable_application_refused")
    document = read_json(folder / "application.json", "application_verification_failed")
    archived = archive_manifest(
        folder.parent / (application_sha256 + ".zip") if archive is None else archive,
        expected_sha256=application_sha256,
    )
    if document != archived:
        raise Refusal("application_verification_failed")
    if document.get("code_version") != code_version:
        raise Refusal("application_commit_mismatch")
    expected = document.get("files")
    if (
        not isinstance(expected, dict)
        or file_inventory(folder, exclude=frozenset({"application.json"})) != expected
    ):
        raise Refusal("application_verification_failed")
    return document


def verify_runtime(folder: Path) -> None:
    """Prove the extracted dependency closure imports without site or downloads."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                "scripts/operations/serve.py",
                "--verify-runtime",
            ],
            cwd=folder,
            env={
                key: value
                for key, value in os.environ.items()
                if key in {"PATH", "HOME", "LANG", "LC_ALL"}
            },
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal("offline_install_verification_failed") from None
    if result.returncode != 0:
        raise Refusal("offline_install_verification_failed")


def install_application(
    archive: Path, env: Environment, code_version: str
) -> tuple[Path, str]:
    manifest = archive_manifest(archive)
    if manifest["code_version"] != code_version:
        raise Refusal("application_commit_mismatch")
    digest = sha(archive)
    target = write_target(env, env.applications / digest)
    env.applications.mkdir(parents=True, exist_ok=True)
    saved = env.applications / (digest + ".zip")
    if saved.exists() and sha(saved) != digest:
        raise Refusal("install_byte_mismatch")
    if not saved.exists():
        shutil.copyfile(archive, saved)
        saved.with_suffix(".zip.sha256").write_text(digest)
    if target.exists():
        verify_application(target, code_version=code_version, application_sha256=digest)
        if (target / "application.json").read_bytes() != encoded(manifest):
            raise Refusal("install_byte_mismatch")
        return target, digest
    with tempfile.TemporaryDirectory(
        dir=env.applications, prefix=".install-"
    ) as scratch:
        stage = Path(scratch) / digest
        stage.mkdir()
        with zipfile.ZipFile(archive) as source:
            for name in manifest["files"]:
                path = stage / relative_file(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(source.read(name))
        (stage / "application.json").write_bytes(encoded(manifest))
        verify_application(
            stage, code_version=code_version, application_sha256=digest, archive=saved
        )
        verify_runtime(stage)
        os.rename(stage, target)
    return target, digest


def install_release(source: Path, env: Environment, application: Path) -> None:
    from eii_product.store.release_check import check_release

    public_kind(source, application / "infra/export_register.jsonl")
    checked = check_release(source)
    from eii_product.store.startup import verify_artefacts

    verify_artefacts(checked)
    identity = str(checked.document["release_id"])
    if source.name != identity or env.release.name != identity:
        raise Refusal("release_folder_identity_mismatch")
    expected = file_inventory(source, exclude=LOAD_OUTPUTS)
    write_target(env, env.release)
    env.release.parent.mkdir(parents=True, exist_ok=True)
    if env.release.exists():
        if file_inventory(env.release, exclude=LOAD_OUTPUTS) != expected:
            raise Refusal("install_byte_mismatch")
        public_kind(env.release, application / "infra/export_register.jsonl")
        return
    with tempfile.TemporaryDirectory(
        dir=env.release.parent, prefix=".install-"
    ) as scratch:
        stage = Path(scratch) / identity
        stage.mkdir()
        for name in expected:
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, path)
        if file_inventory(stage) != expected:
            raise Refusal("install_byte_mismatch")
        check_release(stage)
        os.rename(stage, env.release)
