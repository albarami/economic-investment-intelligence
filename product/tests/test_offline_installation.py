"""A native offline dependency closure installs and imports in isolated Python."""

import sys
from pathlib import Path

from operations.config import Environment
from operations.install import install_application, verify_application
from operations.package import dependency_files, write_archive

ROOT = Path(__file__).resolve().parents[2]


def test_native_offline_archive_installs_identically_without_editable_paths(tmp_path):
    # The fixture's commit label is invented. This proves the actual archive and
    # native import path, not clean-main/hosted approval of this uncommitted tree.
    files = {"uv.lock": (ROOT / "uv.lock").read_bytes()}
    for prefix in ("core/src", "product/src", "scripts/operations"):
        for path in (ROOT / prefix).rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.name != "build.py"
            ):
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    files["web/dist/index.html"] = (
        b"<!doctype html><title>INVENTED archive fixture</title>"
    )
    files.update(dependency_files(files["uv.lock"]))
    archive = write_archive(files, "cd" * 20, tmp_path / "application.zip")
    installed = []
    for name, port in (("staging", 8089), ("live", 8088)):
        home = tmp_path / name
        env = Environment(
            name,
            home / "releases" / ("ab" * 32),
            home / "state",
            port,
            ("127.0.0.1", 5432, "INVENTED_" + name),
        )
        folder, digest = install_application(archive, env, "cd" * 20)
        document = verify_application(
            folder, code_version="cd" * 20, application_sha256=digest
        )
        assert document["python_version"] == ".".join(map(str, sys.version_info[:3]))
        assert not (folder / "custodian").exists()
        assert not any(
            path.suffix == ".pth" for path in (folder / "runtime").rglob("*")
        )
        installed.append((digest, (folder / "application.json").read_bytes()))
    assert installed[0] == installed[1]
