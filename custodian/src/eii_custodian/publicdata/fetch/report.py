"""One result line per source. Lines never carry an environment value."""

from __future__ import annotations

import re

_SOURCE_KEY = re.compile(r"^[a-z][a-z0-9_.-]*(?:/[a-z][a-z0-9_.-]*)*$")
_REASON = re.compile(r"^[a-z][a-z0-9_]*$")
_EVIDENCE_STATES = frozenset({"retained", "missing_evidence", "failed", "unattempted"})


def evidence_line(key: str, status: str, reason: str = "") -> str:
    """Return a source-named evidence outcome without record text or identifiers."""
    if (
        _SOURCE_KEY.fullmatch(key) is None
        or status not in _EVIDENCE_STATES
        or (reason and _REASON.fullmatch(reason) is None)
    ):
        raise ValueError("unsafe_report")
    suffix = f" reason={reason}" if reason else ""
    return f"EVIDENCE {key} {status}{suffix}"


def skip_line(key: str, reason: str) -> str:
    """Return the skip line for a row that this task does not fetch."""
    return f"SKIP {key} {reason}"


def pass_line(key: str, digest: str, host: str) -> str:
    """Return the pass line for one stored file."""
    return f"PASS {key} sha256={digest} host={host}"


def fail_line(key: str, url: str, check: str, expected: str, observed: str) -> str:
    """Return the failure line naming the check, the expected value and the observed value."""
    from eii_custodian.publicdata.fetch.transport import public_address

    return (
        f"FAIL {key} {public_address(url)} {check} "
        f"expected={expected} observed={observed}"
    )


def terms_changed_line(key: str, terms_url: str) -> str:
    """Return the line when a terms page differs from the previous build."""
    return f"TERMS {key} changed since the last build ({terms_url})"


def terms_host_line(key: str, host: str, terms_url: str) -> str:
    """Return the advisory when a terms host is not on the allow-list."""
    return f"TERMS {key} not read: host {host} is not on the allow-list ({terms_url})"


def terms_unread_line(key: str, check: str, terms_url: str) -> str:
    """Return the advisory when a terms page cannot be read."""
    return f"TERMS {key} not read: {check} ({terms_url})"


def citation_line(key: str) -> str:
    """Return the line for a citation-only row."""
    return f"PASS {key} sha256=CITATION_ONLY host="


def coverage_line(figure_id: str) -> str:
    """Return the coverage line for a section 10 figure that is not measured yet."""
    return f"COVERAGE {figure_id} not_measured"


def coverage_count_line(key: str, reason: str, count: int) -> str:
    """Return the coverage line counting rows not kept for a named reason."""
    return f"COVERAGE {key} {reason} {count}"


def pin_share_line(inside: int, total: int) -> str:
    """Return the same-PIN address share line of LR-G4 for the build report."""
    return f"address_points_inside_same_pin: {inside}/{total}"


def log_line(relative: str) -> str:
    """Return the build-log path line. The path is relative to the repository."""
    return f"build-log: {relative}"
