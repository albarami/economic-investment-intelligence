"""Fetch, verify and run the pinned secret scanner for the commit hook (task S0-T06).

Commands: ``fetch`` (the one command that needs the network: downloads the release
archive of the version recorded in ``pins.toml``, checks its pinned SHA-256 and
installs the binary under ``data/tools/gitleaks/<version>/``), ``verify`` (no network:
checks that the installed binary reports the pinned version) and ``staged`` (verifies,
then scans the staged changes).

Exit status: 0 success or no finding; 1 finding or failure; 2 usage error.
"""

from __future__ import annotations

import hashlib
import http.client
import io
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "gitleaks"
CACHE = Path("data") / "tools" / "gitleaks"
CONFIG = ".gitleaks.toml"
MEMBER = "gitleaks"
RELEASE_URL = "https://github.com/gitleaks/gitleaks/releases/download/v{v}/gitleaks_{v}_linux_x64.tar.gz"
ARCHIVE_SHA256 = {
    "8.30.1": "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
}
FETCH_COMMAND = "uv run --locked python scripts/hooks_gitleaks.py fetch"
SCAN_ARGS = (
    "git",
    "--staged",
    "--redact",
    "--verbose",
    "--no-banner",
    "--no-color",
    "--exit-code",
    "2",
    "--ignore-gitleaks-allow",
    "--config",
    CONFIG,
)
FINDING_STATUS = 2


class Failure(Exception):
    """A failure; the message is safe to print."""


def read_version(root: Path) -> str:
    """Read the pinned version from the ``gitleaks`` row of ``pins.toml``.

    Args:
        root: The repository root.

    Returns:
        The version, which has an archive checksum in this script.

    Raises:
        Failure: The record is missing, malformed, lacks the row, or the version has no checksum.
    """
    try:
        data = tomllib.loads((root / "pins.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise Failure(f"pins.toml cannot be read ({type(error).__name__})") from error
    rows = [
        r
        for r in data.get("component", [])
        if isinstance(r, dict) and r.get("name") == COMPONENT
    ]
    if len(rows) != 1 or not isinstance(rows[0].get("pin"), str):
        raise Failure("pins.toml has no single gitleaks row with a pin")
    version: str = rows[0]["pin"]
    if version not in ARCHIVE_SHA256:
        raise Failure(
            f"no pinned checksum for gitleaks {version}; add it to this script"
        )
    return version


def binary_path(root: Path, version: str) -> Path:
    """Return the place of the installed binary.

    Args:
        root: The repository root.
        version: The pinned version.

    Returns:
        The path under ``data/tools/gitleaks/<version>/``.
    """
    return root / CACHE / version / MEMBER


def check_platform(system: str, machine: str) -> None:
    """Refuse every platform but Linux on x86-64, the only archive that is pinned.

    Args:
        system: ``sys.platform``.
        machine: ``platform.machine()``.

    Raises:
        Failure: The platform is not supported.
    """
    if not system.startswith("linux") or machine not in {"x86_64", "AMD64"}:
        raise Failure(
            "only Linux on x86-64 is supported; the other archives are not pinned"
        )


def install_archive(data: bytes, archive_hash: str, target: Path) -> None:
    """Check an archive and install its one binary, or write nothing.

    The member is read by its exact name and written by this function; no member is
    extracted by tarfile, so a path inside the archive cannot choose where a file goes.

    Args:
        data: The archive bytes.
        archive_hash: The pinned SHA-256 of the archive.
        target: Where to write the binary.

    Raises:
        Failure: The digest differs, or the archive does not hold exactly one regular member of the exact name.
    """
    if hashlib.sha256(data).hexdigest() != archive_hash:
        raise Failure(
            "the archive does not match the pinned checksum; nothing was written"
        )
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = [m for m in archive.getmembers() if m.name == MEMBER]
            if len(members) != 1 or not members[0].isreg():
                raise Failure(
                    "the archive does not hold one regular gitleaks file; nothing was written"
                )
            handle = archive.extractfile(members[0])
            content = handle.read() if handle is not None else b""
    except (tarfile.TarError, OSError, EOFError) as error:
        raise Failure(f"the archive cannot be read ({type(error).__name__})") from error
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as out:
            out.write(content)
        os.chmod(out.name, 0o755)
        os.replace(out.name, target)
    except OSError as error:
        raise Failure(
            f"the binary cannot be written ({type(error).__name__})"
        ) from error


def verify_binary(root: Path, version: str) -> Path:
    """Check that the installed binary starts and reports the pinned version.

    Args:
        root: The repository root.
        version: The pinned version, which the binary must report.

    Returns:
        The path of the verified binary.

    Raises:
        Failure: The file is missing, cannot start, or reports another version.
    """
    path = binary_path(root, version)
    shown = path.relative_to(root)
    if not path.is_file():
        raise Failure(f"binary not found at {shown}; run: {FETCH_COMMAND}")
    try:
        done = subprocess.run(
            [str(path), "version"],
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            env={},
            check=False,
        )
    except OSError as error:
        raise Failure(
            f"binary at {shown} could not start ({type(error).__name__}); run: {FETCH_COMMAND}"
        ) from error
    if done.returncode != 0 or done.stdout.strip() != version:
        raise Failure(f"binary at {shown} does not report version {version}")
    return path


def staged(root: Path) -> int:
    """Scan the staged changes.

    Args:
        root: The repository root.

    Returns:
        The exit status.

    Raises:
        Failure: A precondition fails.
    """
    path = verify_binary(root, read_version(root))
    try:
        done = subprocess.run([str(path), *SCAN_ARGS], cwd=root, check=False)
    except OSError as error:
        raise Failure(
            f"the scanner could not start ({type(error).__name__})"
        ) from error
    if done.returncode == 0:
        return 0
    if done.returncode != FINDING_STATUS:
        print(
            f"gitleaks: exited with status {done.returncode}, which is not a finding; see above",
            file=sys.stderr,
        )
    return 1


def fetch(root: Path) -> int:
    """Download, check and install the pinned binary.

    Args:
        root: The repository root.

    Returns:
        The exit status.

    Raises:
        Failure: A precondition or a check fails.
    """
    check_platform(sys.platform, platform.machine())
    version = read_version(root)
    path = binary_path(root, version)
    try:
        verify_binary(root, version)
        print(f"gitleaks {version} already installed at {path.relative_to(root)}")
        return 0
    except Failure:
        pass
    try:
        with urllib.request.urlopen(
            RELEASE_URL.format(v=version), timeout=60
        ) as response:
            data = response.read()
    except (OSError, http.client.HTTPException) as error:
        raise Failure(f"download failed ({type(error).__name__})") from error
    install_archive(data, ARCHIVE_SHA256[version], path)
    verify_binary(root, version)
    print(f"gitleaks {version} installed at {path.relative_to(root)}")
    return 0


def main(argv: list[str]) -> int:
    """Entry point.

    Args:
        argv: ``fetch``, ``verify`` or ``staged``.

    Returns:
        The exit status.
    """
    if len(argv) != 1 or argv[0] not in {"fetch", "verify", "staged"}:
        print("usage: hooks_gitleaks.py fetch|verify|staged", file=sys.stderr)
        return 2
    try:
        if argv[0] == "fetch":
            return fetch(ROOT)
        if argv[0] == "staged":
            return staged(ROOT)
        version = read_version(ROOT)
        shown = verify_binary(ROOT, version).relative_to(ROOT)
        print(f"gitleaks {version} verified at {shown}")
        return 0
    except Failure as error:
        print(f"gitleaks: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
