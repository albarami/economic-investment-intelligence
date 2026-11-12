"""Fetch, record and verify the DuckDB extensions in the project-local folder.

Commands: ``fetch`` (needs the network; run before any sandbox is entered) and
``verify`` (reads files only). Only the two extensions ``spatial`` and ``h3`` are
handled; what the folder must hold and how it is checked are in
``extension_tree``. The signature check of DuckDB stays on; nothing here
switches it off.
"""

from __future__ import annotations

import importlib
import json
import platform
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any, TextIO

import extension_tree as tree

ROOT = Path(__file__).resolve().parents[1]
FOLDER = Path("data") / "engine_extensions"
RECORD_NAME = "EXTENSIONS.json"
SYNC_COMMAND = "uv sync --managed-python --all-packages --locked --group engine"
STATEMENTS = ("INSTALL spatial", "INSTALL h3 FROM community")
EXIT_USAGE = 2
# name -> (repository, host, licence); the hosts are those the installed files name.
SOURCES = {
    "h3": ("community", "community-extensions.duckdb.org", "Apache-2.0"),
    "spatial": ("core", "extensions.duckdb.org", "MIT"),
}
LISTING_SQL = (
    "select extension_name, extension_version, installed_from from duckdb_extensions() "
    "where extension_name in ('spatial', 'h3') order by 1"
)


def connect(duckdb: Any, folder: Path) -> Any:
    """Open an in-memory connection that installs only into ``folder``.

    Args:
        duckdb: The imported ``duckdb`` module.
        folder: The extension folder.

    Returns:
        A connection with automatic installation and loading switched off. The
        default folder in the home directory is not used.
    """
    return duckdb.connect(
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "extension_directories": [str(folder)],
        }
    )


def build_record(
    engine: str,
    rows: Sequence[Sequence[str]],
    files: Sequence[tree.Verified],
    retrieved_on: str,
) -> dict[str, Any]:
    """Build the record of what was fetched, from the checked files.

    Args:
        engine: The engine version tag.
        rows: ``(name, extension version, installed from)`` per extension.
        files: The files of ``open_folder``, checked through their descriptors.
        retrieved_on: The date, ``YYYY-MM-DD``.

    Returns:
        The record, ready for ``json.dumps``.
    """
    by_name = {Path(item.relative).name: item for item in files}
    entries = []
    for name, version, source in sorted(rows, key=lambda row: row[0]):
        repository, host, licence = SOURCES[name]
        binary, info = by_name[name + tree.BINARY], by_name[name + tree.INFO]
        entries.append(
            {
                "name": name,
                "repository": source or repository,
                "host": host,
                "licence": licence,
                "extension_version": version,
                "file": binary.relative,
                "size": binary.size,
                "sha256": binary.sha256,
                "info_file": info.relative,
                "info_size": info.size,
            }
        )
    return {
        "schema": 1,
        "engine": "duckdb",
        "engine_version": engine,
        "platform": tree.PLATFORM,
        "retrieved_on": retrieved_on,
        "extensions": entries,
    }


def fetch(
    root: Path,
    duckdb: Any,
    today: Callable[[], date],
    out: TextIO,
) -> int:
    """Install both extensions into the folder and record them.

    Args:
        root: The repository root.
        duckdb: The imported ``duckdb`` module.
        today: Gives today's date.
        out: Where the report goes.

    Returns:
        0 when the files are as pinned and the record is written, 1 otherwise.
    """
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    try:
        con = connect(duckdb, folder)
        engine = str(con.execute("select version()").fetchone()[0])
        for statement in STATEMENTS:
            con.execute(statement)
        rows = con.execute(LISTING_SQL).fetchall()
    except duckdb.Error as error:
        first = str(error).splitlines()[0] if str(error) else ""
        print(f"FAIL fetch: {type(error).__name__}: {first}", file=out)
        return 1
    print(f"engine duckdb {engine} {tree.PLATFORM}", file=out)
    files, problems = tree.open_folder(folder, engine)
    for problem in problems:
        print(f"FAIL {problem}", file=out)
    if problems:
        print("engine extensions: FAILED", file=out)
        return 1
    try:
        record = build_record(engine, rows, files, today().isoformat())
    finally:
        tree.close_files(files)
    for entry in record["extensions"]:
        print(
            f"file {entry['file']} {entry['size']} bytes sha256 {entry['sha256']}",
            file=out,
        )
    (folder / RECORD_NAME).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"record written: {(FOLDER / RECORD_NAME).as_posix()}", file=out)
    print("engine extensions: OK", file=out)
    return 0


def verify(root: Path, duckdb: Any, out: TextIO) -> int:
    """Check the folder against the pinned table; read files only.

    Args:
        root: The repository root.
        duckdb: The imported ``duckdb`` module.
        out: Where the report goes.

    Returns:
        0 when the folder is as pinned, 1 otherwise.
    """
    engine = str(duckdb.connect().execute("select version()").fetchone()[0])
    print(f"engine duckdb {engine} {tree.PLATFORM}", file=out)
    problems = tree.check_folder(root / FOLDER, engine)
    for problem in problems:
        print(f"FAIL {problem}", file=out)
    print(
        "engine extensions: FAILED" if problems else "engine extensions: OK", file=out
    )
    return 1 if problems else 0


def main(
    argv: Sequence[str],
    *,
    root: Path = ROOT,
    duckdb: Any = None,
    today: Callable[[], date] = date.today,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run ``fetch`` or ``verify``.

    Args:
        argv: The arguments after the program name.
        root: The repository root.
        duckdb: The DuckDB module; imported when None.
        today: Gives today's date.
        out: Standard output; the real one when None.
        err: Standard error; the real one when None.

    Returns:
        0 on success, 1 when a check or the fetch failed, 2 for a usage error.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if list(argv) not in (["fetch"], ["verify"]):
        print("engine_extensions: usage: fetch | verify", file=err)
        return EXIT_USAGE
    if sys.platform != "linux" or platform.machine() != "x86_64":
        print(f"FAIL this task supports only {tree.PLATFORM}", file=out)
        return 1
    try:
        engine_module = (
            duckdb if duckdb is not None else importlib.import_module("duckdb")
        )
    except ImportError:
        print(f"FAIL duckdb is not installed: run {SYNC_COMMAND}", file=out)
        return 1
    if argv[0] == "fetch":
        return fetch(root, engine_module, today, out)
    return verify(root, engine_module, out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
