"""Check the product through the owner's own host: the lead's own shell only."""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from . import table

RUNNER = "node_modules/playwright/cli.js"
ARGV = ("node", RUNNER, "test", "--config", "playwright.remote-check.config.ts")
BROWSERS = "data/tools/playwright"
KEPT = ("PATH", "HOME")
Launch = Callable[[Sequence[str], Path, Mapping[str, str], float], "int | None"]


def default_launch() -> Launch:
    """The one child launch of this command, kept out of the command modules."""
    from remote_check_browser import launch

    return launch


def browse(root: Path, environ: Mapping[str, str], host: str, launch: Launch) -> bytes:
    """Run the pinned runner once; the bytes of the result file it wrote."""
    from operations.common import Refusal
    from operations.remote_check import BROWSER_SECONDS, RESULT_BYTES

    web = root / "web"
    if not (web / RUNNER).is_file():
        raise Refusal("browser_unavailable")
    if not (root / BROWSERS).is_dir():
        raise Refusal("browser_unavailable")
    with tempfile.TemporaryDirectory(prefix="eii-remote-check-") as folder:
        result = Path(folder) / "result.json"
        # A closed child environment: no credential and no other setting.
        child = {key: environ[key] for key in KEPT if key in environ}
        child.update(
            TMPDIR=folder,
            PLAYWRIGHT_BROWSERS_PATH=str(root / BROWSERS),
            EII_REMOTE_CHECK_ORIGIN="https://" + host,
            EII_REMOTE_CHECK_RESULT=str(result),
        )
        try:
            code = launch(ARGV, web, child, BROWSER_SECONDS)
        except OSError:
            raise Refusal("browser_unavailable") from None
        if code is None:
            raise Refusal("browser_timeout")
        if code != 0:
            raise Refusal("browser_failed")
        if not result.is_file():
            raise Refusal("browser_result_missing")
        with result.open("rb") as stream:
            return stream.read(RESULT_BYTES + 1)


def run(
    root: Path,
    environ: Mapping[str, str],
    args: Sequence[str],
    *,
    resolve: Any = None,
    opener: Any = None,
    launch: Launch | None = None,
) -> int:
    """Exit 0 when every item passes, 1 when one fails, 2 before any request."""
    if args:
        table.write_usage()
        return 2
    from operations import remote, remote_check
    from operations.common import Refusal

    try:
        host = remote.remote_host(environ.get(remote.HOST_NAME, ""))
        address = remote_check.resolved(host, resolve or remote_check.system_addresses)
    except Refusal as refusal:
        # Refused before any request; the host itself is never printed.
        print("FAIL remote-check: " + refusal.reason, file=sys.stderr)
        return 2
    started = launch or default_launch()
    try:
        outcomes = remote_check.check(
            opener or remote_check.default_opener,
            address,
            host,
            lambda: browse(root, environ, host, started),
        )
    except Exception:
        # No exception text, address or environment value reaches a line.
        print("FAIL remote-check: operation_failed", file=sys.stderr)
        return 1
    for line in remote_check.lines(outcomes):
        print(line)
    return 0 if all(item.reason is None for item in outcomes.values()) else 1
