"""Exit codes 0 to 7 and the failure lines."""

from __future__ import annotations

import sys

_MIN_CODE = 0
_MAX_CODE = 7

MEANINGS: dict[int, str] = {
    0: "Success",
    1: "A check or step failed; the printed `FAIL` lines say which",
    2: "Usage error: unknown command or flag",
    3: (
        "PostgreSQL required by this command but not answering "
        "(`test`, `load-release`, `freeze`)"
    ),
    4: (
        "Release missing, incomplete, or hash mismatch "
        "(including embedded reader mismatch)"
    ),
    5: "API port already in use",
    6: "Network required but unavailable (`build-public` only)",
    7: (
        "Freeze refused because the register conflicts or the recorded human "
        "review is missing; or frozen-bundle install or start refused because "
        "the installed application's register lacks the line or `freeze.json` "
        "is not complete (OPS-62, OPS-63)"
    ),
}


def finish(code: int, command: str, detail: str) -> int:
    """Print the failure lines and return a code from 0 to 7."""
    if code < _MIN_CODE or code > _MAX_CODE:
        fault = f"internal fault: exit {code} is outside 0 to 7"
        _write(1, command, fault)
        return 1
    if code != 0:
        _write(code, command, detail)
    return code


def _write(code: int, command: str, detail: str) -> None:
    sys.stderr.write(f"FAIL {command}: {detail}\n")
    sys.stderr.write(f"eii: exit {code}: {MEANINGS[code]}\n")
