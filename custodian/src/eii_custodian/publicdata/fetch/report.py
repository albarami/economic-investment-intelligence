"""One result line per source. Lines never carry an environment value."""

from __future__ import annotations


def skip_line(key: str, reason: str) -> str:
    """Return the skip line for a row that this task does not fetch."""
    return f"SKIP {key} {reason}"


def pass_line(key: str, digest: str, host: str) -> str:
    """Return the pass line for one stored file."""
    return f"PASS {key} sha256={digest} host={host}"


def fail_line(key: str, url: str, check: str, expected: str, observed: str) -> str:
    """Return the failure line naming the check, the expected value and the observed value."""
    return f"FAIL {key} {url} {check} expected={expected} observed={observed}"


REASON_FORBID = "terms read at fetch forbid the use"
REASON_CHANGED = "terms changed since they were read"


def owner_line(key: str, terms_url: str) -> str:
    """Return the owner-facing line when the terms read at fetch forbid the use."""
    return f"OWNER {key} switched off: {REASON_FORBID} ({terms_url})"


def owner_changed_line(key: str, terms_url: str) -> str:
    """Return the owner-facing line when the terms no longer contain the recorded phrase."""
    return f"OWNER {key} switched off: {REASON_CHANGED}; read them again ({terms_url})"


def citation_line(key: str) -> str:
    """Return the line for a citation-only row."""
    return f"PASS {key} sha256=CITATION_ONLY host="


def coverage_line(figure_id: str) -> str:
    """Return the coverage line for a section 10 figure that is not measured yet."""
    return f"COVERAGE {figure_id} not_measured"


def log_line(relative: str) -> str:
    """Return the build-log path line. The path is relative to the repository."""
    return f"build-log: {relative}"
