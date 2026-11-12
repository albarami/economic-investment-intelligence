"""Preflight checks: run every row and decide store and exit status."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import preflight_database as database
import preflight_proc as proc
import preflight_rows as rows
import preflight_store as store

CHECKS = (
    "locked-dependencies",
    "postgresql",
    "release",
    "load-receipt",
    "embedded-reader",
    "tiles-glyphs-fonts",
    "recorded-replays",
    "api-port",
    "model-key",
    "env-not-tracked",
    "wsl-interop",
)
EXIT_USAGE = 2
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Report:
    """Full preflight report."""

    lines: tuple[store.Line, ...]
    store: str
    status: int

    def text_lines(self) -> list[str]:
        """Return printable lines including store."""
        out = [line.text() for line in self.lines]
        out.append(f"store: {self.store}")
        return out


def run_preflight(
    root: Path,
    environ: Mapping[str, str],
    *,
    embedded: bool = False,
    docker: bool = True,
    limit: float = proc.PROBE_TIMEOUT_S,
    api_port: int = rows.API_PORT,
) -> Report:
    """Run every preflight row inside a temporary scratch folder."""
    with tempfile.TemporaryDirectory(prefix="eii-preflight-") as scratch_name:
        scratch = Path(scratch_name)
        out_lines: list[store.Line] = []

        out_lines.append(
            rows.locked_dependencies_row(root, environ, scratch, limit),
        )
        if embedded:
            sel = database.check_postgres(
                environ,
                scratch,
                limit,
                embedded=True,
                docker=docker,
            )
        else:
            sel = database.check_postgres(
                environ,
                scratch,
                limit,
                embedded=False,
                docker=docker,
            )
        if sel.line is not None:
            out_lines.append(sel.line)

        rel = rows.release_rows(environ)
        out_lines.append(rel["release"])
        out_lines.append(rel["load-receipt"])
        out_lines.append(rel["embedded-reader"])
        out_lines.append(rows.tiles_row(root))
        out_lines.append(rel["recorded-replays"])
        out_lines.append(rows.api_port_row(api_port))
        out_lines.append(rows.model_key_row(environ))
        out_lines.append(rows.env_tracked_row(root, environ, limit))
        out_lines.append(rows.wsl_row(root, environ, limit))

        status = 1 if any(line.severity == "FAIL" for line in out_lines) else 0
        return Report(tuple(out_lines), sel.store, status)


def up_decision(
    environ: Mapping[str, str],
    report: Report,
) -> tuple[int, str]:
    """Map a report to an exit code for ./eii up."""
    if not environ.get("EII_RELEASE_DIR", ""):
        return (
            4,
            "./eii up requires a configured, complete release: EII_RELEASE_DIR is not set",
        )
    failed = [line.check for line in report.lines if line.severity == "FAIL"]
    release_failed = [c for c in failed if c in rows.RELEASE_ROWS]
    if release_failed:
        joined = ", ".join(release_failed)
        return (4, f"release missing, incomplete or not verified: {joined}")
    if failed == ["api-port"]:
        return (5, "API port already in use")
    if failed:
        joined = ", ".join(failed)
        return (1, f"a check failed: {joined}")
    return (0, "")


def main(argv: Sequence[str]) -> int:
    """CLI entry: print lines and return status."""
    if argv:
        sys.stderr.write("usage: preflight.py takes no arguments\n")
        return EXIT_USAGE
    report = run_preflight(ROOT, os.environ)
    for line in report.text_lines():
        print(line)
    return report.status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
