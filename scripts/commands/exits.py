"""Exit codes and the failure lines, including the unapproved candidate outcome."""

from __future__ import annotations

import sys

_MIN_CODE = 0
_MAX_CODE = 8

MEANINGS: dict[int, str] = {
    0: "Success",
    1: (
        "A check or step failed; the printed `FAIL` lines say which; an existing "
        "final schema, a release kind the loader does not support, a host off the "
        "loopback address (`host_not_loopback`), an extension the target database "
        "must not hold, an extension schema that is not a plain identifier "
        "(`extension_schema_invalid`), or an engine operation that failed "
        "(`engine_operation_failed`)"
    ),
    2: "Usage error: unknown command or flag",
    3: (
        "PostgreSQL required by this command but not answering "
        "(`test`, `load-release`, `freeze`); or the owner role cannot connect "
        "on a server that answers"
    ),
    4: (
        "Release missing, incomplete, or hash mismatch (including embedded reader "
        "mismatch); a forbidden manifest field, a forbidden table class, a "
        "privacy-written table (`privacy_written_table`) or an empty table list; "
        "a duplicate manifest key (`duplicate_key`), an unknown manifest key "
        "(`unknown_manifest_key`), a manifest key in another case "
        "(`manifest_key_case`), a manifest value of the wrong type "
        "(`manifest_type_invalid`) or a table listed twice (`duplicate_table`); "
        "an absolute table path (`absolute_path`), a table path with `..` "
        "(`path_traversal`), a symbolic link on a table path (`symbolic_link`) or "
        "a table path outside the release (`path_outside_release`); a source chain "
        "that is missing (`source_link_missing`), incomplete "
        "(`source_link_incomplete`), unknown (`source_link_unknown`) or mismatched "
        "(`source_link_mismatch`); or staged stores that differ in a count, a "
        "digest or the release identity"
    ),
    5: "API port already in use",
    6: "Network required but unavailable (`build-public` only)",
    7: (
        "Freeze refused because the register conflicts or the recorded human "
        "review is missing; or frozen-bundle install or start refused because "
        "the installed application's register lacks the line or `freeze.json` "
        "is not complete (OPS-62, OPS-63)"
    ),
    8: (
        "Candidate written for independent review; approval missing "
        "(candidate_written_approval_missing)"
    ),
}


def finish(code: int, command: str, detail: str) -> int:
    """Print the failure lines and return a recognised exit code."""
    if code < _MIN_CODE or code > _MAX_CODE:
        fault = f"internal fault: exit {code} is outside 0 to 8"
        _write(1, command, fault)
        return 1
    if code != 0:
        _write(code, command, detail)
    return code


def _write(code: int, command: str, detail: str) -> None:
    sys.stderr.write(f"FAIL {command}: {detail}\n")
    sys.stderr.write(f"eii: exit {code}: {MEANINGS[code]}\n")
