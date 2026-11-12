"""Load the DuckDB extensions from one folder, with the network off (ARC-14).

Usage: python -I -B extension_check.py FOLDER MODE

MODE is ``load`` (load spatial and h3, use both, lock the configuration),
``install`` (try to install into the folder), ``autoload`` (use a spatial
function without loading it) or ``files`` (describe every entry below the
folder, a file with its SHA-256). Each line describes one step or entry. Exit
status: 0 all steps ran, 2 usage error. DuckDB is imported through
``importlib`` because the checks that read this file run in an environment that
may lack it.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import stat
import sys
from typing import Any

EXIT_USAGE = 2
EXTENSIONS = ("spatial", "h3")
SETTINGS = (
    "autoinstall_known_extensions",
    "autoload_known_extensions",
    "allow_unsigned_extensions",
)
CLASSES = (
    ("not found", "not-found"),
    ("signature is either missing or invalid", "bad-signature"),
    ("Read-only file system", "read-only"),
    ("Could not establish connection", "no-network"),
    ("is not in the catalog", "not-in-catalog"),
    ("has been locked", "locked"),
)
USE_QUERY = "select ST_AsText(ST_Point(1, 2)), h3_latlng_to_cell_string(10.0, 10.0, 8)"


def classify(error: Exception) -> str:
    """Name the reason in a DuckDB error message.

    Args:
        error: The exception raised by DuckDB.

    Returns:
        A label from ``CLASSES``, or ``other``.
    """
    text = str(error)
    for needle, label in CLASSES:
        if needle in text:
            return label
    return "other"


def describe(step: str, error: Exception) -> str:
    """Write the line for a failed step."""
    return f"{step} error {type(error).__name__} {classify(error)}"


def connect(duckdb: Any, folder: str) -> Any:
    """Open an in-memory connection that reads extensions from one folder only.

    Args:
        duckdb: The imported ``duckdb`` module.
        folder: The extension folder.

    Returns:
        The connection; both automatic installation and automatic loading are off.
    """
    return duckdb.connect(
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "extension_directories": [folder],
        }
    )


def setting(con: Any, name: str) -> str:
    """Read one setting as text."""
    return str(con.execute("select current_setting(?)", [name]).fetchone()[0])


def run_load(duckdb: Any, folder: str) -> list[str]:
    """Load both extensions, use them, then lock the configuration."""
    con = connect(duckdb, folder)
    lines = [f"engine duckdb {con.execute('select version()').fetchone()[0]}"]
    lines.append("settings " + " ".join(f"{n}={setting(con, n)}" for n in SETTINGS))
    for name in EXTENSIONS:
        try:
            con.execute(f"LOAD {name}")
            lines.append(f"LOAD {name} ok")
        except duckdb.Error as error:
            lines.append(describe(f"LOAD {name}", error))
    rows = con.execute(
        "select extension_name, install_path from duckdb_extensions() "
        "where loaded and extension_name in ('spatial', 'h3') order by 1"
    ).fetchall()
    prefix = folder.rstrip("/") + "/"
    for name, path in rows:
        lines.append(
            f"PATH {name} {'inside' if path.startswith(prefix) else 'outside'}"
        )
    if len(rows) == len(EXTENSIONS):
        lines.append(
            "USE " + " ".join(str(v) for v in con.execute(USE_QUERY).fetchone())
        )
    con.execute("SET lock_configuration=true")
    try:
        con.execute("SET autoinstall_known_extensions=true")
        lines.append("LOCK autoinstall changed")
    except duckdb.Error as error:
        lines.append(describe("LOCK autoinstall", error))
    return lines


def run_install(duckdb: Any, folder: str) -> list[str]:
    """Try to install into the folder; the network is off."""
    con = connect(duckdb, folder)
    lines = []
    for step, sql in (
        ("INSTALL h3", "INSTALL h3 FROM community"),
        ("FORCE spatial", "FORCE INSTALL spatial"),
    ):
        try:
            con.execute(sql)
            lines.append(f"{step} ok")
        except duckdb.Error as error:
            lines.append(describe(step, error))
    return lines


def run_autoload(duckdb: Any, folder: str) -> list[str]:
    """Use a spatial function without loading the extension."""
    con = connect(duckdb, folder)
    try:
        con.execute("select ST_Point(1, 2)")
    except duckdb.Error as error:
        return [describe("QUERY st_point", error)]
    return ["QUERY st_point ok"]


def _raise(error: OSError) -> None:
    """Make ``os.walk`` stop on a folder it cannot read instead of skipping it."""
    raise error


def run_files(duckdb: Any, folder: str) -> list[str]:
    """Describe every entry below the folder; a symbolic link is not followed.

    Returns:
        ``DIR <path>``, ``FILE <path> <SHA-256>`` or ``OTHER <path>`` per entry,
        the paths relative to the folder, sorted by path.
    """
    found = []
    for top, folders, files in os.walk(folder, onerror=_raise):
        for name in folders + files:
            path = os.path.join(top, name)
            relative = os.path.relpath(path, folder)
            mode = os.lstat(path).st_mode
            if stat.S_ISREG(mode):
                with open(path, "rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                found.append((relative, f"FILE {relative} {digest}"))
            else:
                kind = "DIR" if stat.S_ISDIR(mode) else "OTHER"
                found.append((relative, f"{kind} {relative}"))
    return [line for _, line in sorted(found)]


MODES = {
    "load": run_load,
    "install": run_install,
    "autoload": run_autoload,
    "files": run_files,
}


def main(argv: list[str]) -> int:
    """Run one mode.

    Args:
        argv: ``FOLDER MODE``.

    Returns:
        0, or ``EXIT_USAGE`` for wrong arguments.
    """
    if len(argv) != 2 or argv[1] not in MODES:
        print(
            "extension_check: usage: FOLDER load|install|autoload|files",
            file=sys.stderr,
        )
        return EXIT_USAGE
    duckdb = importlib.import_module("duckdb")
    for line in MODES[argv[1]](duckdb, argv[0]):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
