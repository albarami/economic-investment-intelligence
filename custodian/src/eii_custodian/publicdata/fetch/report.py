"""One result line per source. Lines never carry an environment value."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from eii_custodian.publicdata.fetch.registry import Entry

LocalFileStatus = Literal["present", "absent", "invalid"]

_SOURCE_KEY = re.compile(r"^[a-z][a-z0-9_.-]*(?:/[a-z][a-z0-9_.-]*)*$")
_BARE_DIGITS = re.compile(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])")
_EVIDENCE_STATES = frozenset({"retained", "missing_evidence", "failed", "unattempted"})
_EVIDENCE_REASONS = frozenset(
    {
        "",
        "fetch_failed",
        "publication_failed",
        "not_attempted_after_fail_fast",
        "snapshot_selection_missing",
    }
)


def local_file_statuses(cache: Path, review: Path) -> dict[str, LocalFileStatus]:
    """Describe the two hand-written local inputs without exporting their values.

    The production readers alone decide validity. Reporting a refusal does not
    replace the stage's own refusal or make an absent alias file a build error.
    """
    from eii_custodian.publicdata.frame.live import district_aliases
    from eii_custodian.publicdata.stage import LOCAL_EXPECTATIONS_DIR, _local_expected

    def status(path: Path, reader: Callable[[], object]) -> LocalFileStatus:
        if not path.is_file():
            return "absent"
        try:
            reader()
        except (OSError, ValueError):
            return "invalid"
        return "present"

    expectations = f"{LOCAL_EXPECTATIONS_DIR}/PUB-71.json"
    aliases = "review/district_layer_aliases.csv"
    return {
        expectations: status(
            cache / expectations, lambda: _local_expected(cache, "PUB-71")
        ),
        aliases: status(cache / aliases, lambda: district_aliases(review, cache)),
    }


def evidence_line(
    key: str,
    status: str,
    reason: str = "",
    *,
    registry_keys: frozenset[str] | None = None,
) -> str:
    """Return an evidence outcome only for validated keys and closed reasons."""
    if registry_keys is None:
        from eii_custodian.publicdata.fetch.registry import load_registry

        registry_keys = frozenset(entry.key for entry in load_registry())
    if (
        _SOURCE_KEY.fullmatch(key) is None
        or key not in registry_keys
        or status not in _EVIDENCE_STATES
        or reason not in _EVIDENCE_REASONS
        or _BARE_DIGITS.search(key) is not None
        or _BARE_DIGITS.search(reason) is not None
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

    comparison = (
        f" expected={expected} observed={observed}" if expected or observed else ""
    )
    return f"FAIL {key} {public_address(url)} {check}{comparison}"


def terms_changed_line(key: str, terms_url: str) -> str:
    """Return the line when a terms page differs from the previous build."""
    return f"TERMS {key} changed since the last build ({terms_url})"


def terms_host_line(key: str, host: str, terms_url: str) -> str:
    """Return the advisory when a terms host is not on the allow-list."""
    return f"TERMS {key} not read: host {host} is not on the allow-list ({terms_url})"


def terms_unread_line(key: str, check: str, terms_url: str) -> str:
    """Return the advisory when a terms page cannot be read."""
    return f"TERMS {key} not read: {check} ({terms_url})"


def licence_pending_line(
    key: str, licence_id: str, observed: str, date_read: str
) -> str:
    """Return the advisory when a fetched licence differs from the registry.

    Ruling L-1001 (decision 0059, the PUB-09 and PUB-97 passages): a licence
    different from the registry is recorded with the date read, pending a
    reviewer's record, and fails nothing.
    """
    return (
        f"LICENCE {key} read {date_read}: observed {observed} "
        f"differs from registry {licence_id}; pending a reviewer's record"
    )


def licence_unstated_line(key: str, licence_id: str, date_read: str) -> str:
    """Return the advisory when a portal states no licence at all.

    Ruling L-1016 (applying L-1001): a publisher-terms reading is a record,
    never a gate; a dataset-basis portal row that states no licence is
    recorded with the date read, pending a reviewer's record, and fails
    nothing. publisher_missing and publisher_mismatch stay refusals.
    """
    return (
        f"LICENCE {key} read {date_read}: no licence stated where registry "
        f"{licence_id} was expected; pending a reviewer's record"
    )


TERMS_HOST_NOT_LISTED = "host_not_allow_listed"


def terms_attempt_record(
    entry: Entry, reason: str, attempted_utc: str
) -> dict[str, object]:
    """Return one unread-terms attempt for the build log (S2-T08 part B, class 9).

    The attempt time and reason are kept apart from the row's recorded
    ``terms_read_on`` and own words, which are copied unchanged: an attempt is
    never a reading, so no reading date is made from it.
    """
    return {
        "key": entry.key,
        "terms_url": entry.terms_url,
        "terms_attempted_utc": attempted_utc,
        "terms_unread_reason": reason,
        "terms_read_on": entry.terms_read_on,
        "terms_words": entry.terms_words,
    }


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
