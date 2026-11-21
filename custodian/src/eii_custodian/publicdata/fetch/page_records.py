"""Reviewed cached page tables, explicit dated lineage and closed use limits."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.additions.split_policy import (
    UseRequest,
    validate_split_use,
)

from .allowlist import approve, host_of
from .certificate_pins import (
    Capture,
    Pin,
    PinError,
    admit_capture,
    load_capture,
    load_pin,
    page_transport,
    validate_pin,
)
from .kinds import read_bounded, read_terms_page, require_verified_chain
from .page_archive import staged_source
from .receipts import archive_auxiliary, sha256_hex, sidecar_for
from .registry import LICENCE_BASES, Entry, read_yaml
from .snapshots import (
    Snapshot,
    SnapshotError,
    publish_snapshot,
    read_snapshot,
    reviewed_selections,
    utc,
)
from .transport import Transport

SOURCES = frozenset(
    {
        "fc_register",
        "insurance_tables",
        "events_visit_qatar",
        "events_qncc",
        "suppliers_tawteen",
        "manateq_tariffs",
        "monaqasat_classified",
        "schools_private_directory",
        "awards_owner_scrape",
    }
)
PINNED = frozenset({"monaqasat_classified", "schools_private_directory"})
REVIEW = Path(__file__).resolve().parents[4] / "publicdata/review/s2_t29_sources.yaml"
METHOD = "page_records.parse_page_snapshot@v1"


class PageError(ValueError):
    """Closed reason only; build adds the source ID without upstream diagnostics."""


def load_declaration(source: str, path: Path = REVIEW) -> dict[str, Any]:
    value = read_yaml(path)
    if not isinstance(value, dict) or not isinstance(value.get("sources"), dict):
        raise PageError("schema_missing")
    row = value["sources"].get(source)
    if not isinstance(row, dict):
        raise PageError("schema_missing")
    if any("[LEAD: evidence 1]" in str(value) for value in row.values()):
        raise PageError("page_evidence_pending")
    return row


def validate_claim(source: str, claim: str) -> None:
    """Only source-owned meanings enter this table contract; no inferred coverage."""
    allowed = {"published_fields"}
    if source == "awards_owner_scrape":
        allowed = {"awarded_value"}
    if source not in SOURCES or claim not in allowed:
        raise PageError("unsupported_source_claim")


def validate_use(request: UseRequest) -> None:
    verdict = validate_split_use(request)
    if not verdict.admitted:
        raise PageError(verdict.reason)


class _Table(HTMLParser):
    def __init__(self, table_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.depth = 0
        self.matches = 0
        self.cell: list[str] | None = None
        self.row: list[str] | None = None
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self.depth:
                raise PageError("schema_missing")
            if dict(attrs).get("id") == self.table_id:
                self.depth = 1
                self.matches += 1
        if not self.depth:
            return
        if tag == "tr":
            if self.row is not None:
                raise PageError("schema_missing")
            self.row = []
        if tag in {"td", "th"}:
            if self.cell is not None or self.row is None:
                raise PageError("schema_missing")
            if any(k in {"colspan", "rowspan"} and v != "1" for k, v in attrs):
                raise PageError("schema_missing")
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.depth:
            return
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "table":
            self.depth = 0


def _value(text: str, kind: str) -> str | int | None:
    if text == "":
        return None
    try:
        if kind == "integer":
            return int(text)
        if kind == "number":
            value = Decimal(text)
            if not value.is_finite():
                raise ValueError
            return str(value)
        if kind == "string":
            return text
    except (ValueError, InvalidOperation):
        pass
    raise PageError("schema_missing")


def parse_body(
    body: bytes, entry: Entry, declaration: Mapping[str, Any]
) -> list[dict[str, object]]:
    """Strict reviewed table shape; no heuristic discovery or helper counts."""
    if declaration.get("version") == 2:
        from .page_html import ShapeError
        from .page_shapes import parse

        try:
            if declaration.get("columns") != [[n, k] for n, k in entry.columns]:
                raise ShapeError("schema_missing")
            return parse(body, declaration)
        except ShapeError as exc:
            raise PageError(str(exc)) from None
    forbidden = {"capacity", "enrolment", "catchment", "press_seats"}
    if entry.source_id == "schools_private_directory" and any(
        name.casefold() in forbidden for name, _ in entry.columns
    ):
        raise PageError("unsupported_source_claim")
    columns = declaration.get("columns")
    if not entry.columns or columns != [[n, k] for n, k in entry.columns]:
        raise PageError("schema_missing")
    parser = _Table(str(declaration.get("table_id", "")))
    try:
        parser.feed(body.decode("utf-8"))
        parser.close()
    except UnicodeError:
        raise PageError("schema_missing") from None
    if (
        parser.matches != 1
        or parser.depth
        or parser.cell is not None
        or parser.row is not None
        or not parser.rows
        or parser.rows[0] != [n for n, _ in entry.columns]
    ):
        raise PageError("schema_missing")
    rows: list[dict[str, object]] = []
    for raw in parser.rows[1:]:
        if len(raw) != len(entry.columns):
            raise PageError("schema_missing")
        rows.append(
            {
                name: _value(value, kind)
                for (name, kind), value in zip(entry.columns, raw, strict=True)
            }
        )
    if (entry.row_count_min is not None and len(rows) < entry.row_count_min) or (
        entry.row_count_max is not None and len(rows) > entry.row_count_max
    ):
        raise PageError("row_count")
    return rows


def _validate(entry: Entry, declaration: Mapping[str, Any]) -> None:
    if entry.commit_allowed:
        raise PageError("commit_refused")
    # Ruling L-1001: pending terms fields (words, reading date) and a pending
    # basis of use (blank or the recorded "pending" value) are records and
    # never refuse the row; an unknown basis still does.
    if not entry.publisher or (
        entry.licence_basis not in LICENCE_BASES and entry.licence_basis != ""
    ):
        raise PageError("receipt_missing")
    if entry.licence_basis == "owner_decision" and entry.decision_record != "0026":
        raise PageError("receipt_missing")
    try:
        date.fromisoformat(str(declaration.get("as_of", "")))
    except ValueError:
        raise PageError("snapshot_date_missing") from None
    if not declaration.get("period"):
        raise PageError("snapshot_date_missing")
    if entry.period_last and str(declaration["period"]) < entry.period_last:
        raise PageError("stale_period")
    if (
        entry.row_count_min is not None or entry.row_count_max is not None
    ) and declaration.get("bounds_basis") != "observed":
        raise PageError("bounds_unconfirmed")
    urls = declaration.get("reviewed_urls")
    if (
        not isinstance(urls, list)
        or not urls
        or any(not isinstance(url, str) or not approve(url).ok for url in urls)
    ):
        raise PageError("blocked_host")
    if (
        declaration.get("url") != entry.url
        or entry.url not in urls
        or not approve(entry.url).ok
    ):
        raise PageError("blocked_host")
    if Path(entry.key).is_absolute() or ".." in Path(entry.key).parts:
        raise PageError("cache_path_refused")


def _obstacle(body: bytes) -> None:
    if any(
        word in body.lower()
        for word in (
            b"sign in",
            b"sign-in",
            b"paywall",
            b"robot check",
            b"registration required",
        )
    ):
        raise PageError("unavailable")


def record_failure(cache: Path, entry: Entry, stamp: str, reason: str) -> None:
    cache_directory(cache, entry)
    utc(stamp)
    side: dict[str, object] = {
        "source_id": entry.source_id,
        "key": entry.key,
        "retrieved_utc": stamp,
    }
    body = json.dumps(
        {
            "source_id": entry.source_id,
            "attempted_utc": stamp,
            "reason": reason,
            "coverage": "NO_DATA",
        },
        sort_keys=True,
    ).encode()
    publish_snapshot(cache / entry.key / "failures", "json", body, side)


def fetch_page(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
    *,
    declaration: Mapping[str, Any] | None = None,
    capture: Capture | None = None,
    pin: Pin | None = None,
) -> Snapshot:
    """Fetch through the normal seam, parse before publishing, retain both inputs."""
    review = (
        declaration if declaration is not None else load_declaration(entry.source_id)
    )
    if entry.source_id == "suppliers_tawteen" and (
        review.get("version") != 2 or review.get("kind") != "refusal"
    ):
        raise PageError("anonymous_access_not_approved")
    if review.get("version") == 2:
        from .page_acquire import fetch
        from .page_html import ShapeError

        try:
            return fetch(entry, review, transport, cache, clock, sleep)
        except ShapeError as exc:
            raise PageError(str(exc)) from None
    _validate(entry, review)
    cache_directory(cache, entry)
    stamp = clock()
    utc(stamp)
    if entry.source_id in PINNED:
        if pin is None:
            pin = load_pin(cache, entry.source_id, review.get("pin"))
        validate_pin(host_of(entry.url), pin)
    evidence: dict[str, object] = {}
    with page_transport(pin, browser=entry.source_id == "schools_private_directory"):
        response, failure = read_bounded(transport, sleep, entry.url)
    require_verified_chain(failure)
    if failure is not None or response is None:
        if entry.source_id != "schools_private_directory":
            raise PageError(failure.check if failure else "access_failed")
        if capture is None and pin is not None:
            try:
                capture = load_capture(cache, entry.source_id, pin)
            except (PinError, SnapshotError) as exc:
                record_failure(cache, entry, stamp, str(exc))
                raise PageError(str(exc)) from None
            except ValueError:
                record_failure(cache, entry, stamp, "capture_evidence_missing")
                raise PageError("capture_evidence_missing") from None
        if capture is None:
            record_failure(cache, entry, stamp, "access_failed")
            raise PageError("access_failed")
        try:
            response, evidence = admit_capture(capture, entry.url)
        except (PinError, SnapshotError) as exc:
            record_failure(cache, entry, stamp, str(exc))
            raise PageError(str(exc)) from None
        except ValueError:
            record_failure(cache, entry, stamp, "capture_evidence_missing")
            raise PageError("capture_evidence_missing") from None
    for url in (*response.hops, response.final_url):
        if url not in review["reviewed_urls"] or not approve(url).ok:
            raise PageError("blocked_host")
        if pin is not None:
            validate_pin(host_of(url), pin)
    _obstacle(response.body)
    rows = parse_body(response.body, entry, review)
    side = sidecar_for(
        entry,
        digest=sha256_hex(response.body),
        nbytes=len(response.body),
        fetch_url=response.final_url,
        fetch_host=host_of(response.final_url),
        retrieved_utc=stamp,
        publisher=entry.publisher,
        source_modified="",
        row_count=len(rows),
        terms_sha256="",
    )
    side.update(
        as_of=review["as_of"],
        source_period=review["period"],
        method=METHOD,
        capture=evidence,
    )
    destination = cache
    with staged_source(cache, entry.key) as cache:
        if entry.terms_url:
            with page_transport(pin):
                terms = read_terms_page(entry, transport, sleep)
            side["terms_sha256"] = terms.sha256 or None
            side["terms_unread"] = terms.failure.check if terms.failure else ""
            if terms.failure is None:
                archive_auxiliary(
                    entry,
                    cache / entry.key,
                    "terms",
                    terms.body,
                    stamp,
                    entry.terms_url,
                )
        raw = publish_snapshot(cache / entry.key / "raw", "html", response.body, side)
        raw_identity = raw.sha256
        raw = read_snapshot(cache / entry.key / "raw", raw_identity)
        payload = parse_page_snapshot(raw, entry, review)
        parsed = json.dumps(payload, sort_keys=True).encode()
        parsed_side = dict(
            side,
            sha256=sha256_hex(parsed),
            bytes=len(parsed),
            page_sha256=raw.sha256,
            raw_identity=raw_identity,
        )
        result = publish_snapshot(cache / entry.key, "json", parsed, parsed_side)
    return read_snapshot(destination / entry.key, result.sha256)


def parse_page_snapshot(
    snapshot: Snapshot, entry: Entry, declaration: Mapping[str, Any]
) -> dict[str, object]:
    _validate(entry, declaration)
    # Ruling L-1001: a pending basis (blank or the recorded "pending" value)
    # is a record, never a missing receipt; a receipt that holds no basis
    # record at all is malformed and still refuses, and so does a foreign
    # source id.
    if (
        snapshot.sidecar.get("source_id") != entry.source_id
        or "licence_basis" not in snapshot.sidecar
    ):
        raise PageError("receipt_missing")
    return {
        "source_id": entry.source_id,
        "rows": parse_body(snapshot.body, entry, declaration),
        "page_sha256": snapshot.sha256,
        "raw_identity": snapshot.sha256,
        "as_of": declaration["as_of"],
        "source_period": declaration["period"],
        "retrieved_utc": snapshot.sidecar["retrieved_utc"],
        "method": METHOD,
        "provenance": "Public",
        "completeness": "unknown",
    }


def selected_page(cache: Path, entry: Entry) -> Snapshot:
    cache_directory(cache, entry)
    identity = reviewed_selections(cache).get(entry.key)
    if identity is None:
        raise PageError("snapshot_selection_invalid")
    parsed = read_snapshot(cache / entry.key, identity)
    # Ruling L-1016 (applying L-1001): the build itself writes this parsed
    # receipt, so a sidecar without the licence_basis key is a defect, not a
    # terms reading; a blank or "pending" value stays a record.
    if "licence_basis" not in parsed.sidecar:
        raise PageError("receipt_missing")
    payload = json.loads(parsed.body)
    if payload.get("version") == 2:
        from .page_html import ShapeError

        if (
            payload.get("source_id") != entry.source_id
            or payload.get("method") != "page_acquire.fetch@v2"
            or not payload.get("inputs")
        ):
            raise PageError("receipt_missing")
        try:
            value = payload["as_of"]
            if (
                not isinstance(value, str)
                or date.fromisoformat(value).isoformat() != value
                or value != utc(payload["retrieved_utc"]).date().isoformat()
            ):
                raise ValueError
        except (ValueError, KeyError, ShapeError):
            raise PageError("snapshot_date_missing") from None
        if (
            parsed.sidecar.get("inputs") != payload["inputs"]
            or parsed.sidecar.get("as_of") != value
        ):
            raise PageError("receipt_missing")
        for index, item in enumerate(payload["inputs"]):
            if item["key"] != "inputs/input-" + str(index):
                raise PageError("receipt_missing")
            input_directory = cache / entry.key / item["key"]
            if (
                input_directory.is_symlink()
                or not input_directory.resolve().is_relative_to(
                    (cache / entry.key).resolve()
                )
                or any(path.is_symlink() for path in input_directory.rglob("*"))
            ):
                raise PageError("cache_path_refused")
            raw_input = read_snapshot(input_directory, item["identity"])
            if (
                raw_input.sha256 != item["sha256"]
                # Ruling L-1001: a pending basis value (blank or the recorded
                # "pending") is a record, never missing. Ruling L-1016 (applying
                # L-1001): the build itself writes this receipt, so a receipt
                # with the licence_basis key absent is a defect, not a terms
                # reading, and still refuses.
                or raw_input.sidecar.get("source_id") != entry.source_id
                or "licence_basis" not in raw_input.sidecar
            ):
                raise PageError("receipt_missing")
        return parsed
    raw = read_snapshot(cache / entry.key / "raw", payload["raw_identity"])
    if (
        payload["page_sha256"] != raw.sha256
        or not payload.get("as_of")
        # Ruling L-1016 (applying L-1001): the build itself writes this raw
        # receipt, so a receipt with the licence_basis key absent is a
        # defect, not a terms reading, and still refuses.
        or "licence_basis" not in raw.sidecar
    ):
        raise PageError("receipt_missing")
    return parsed


def cache_directory(cache: Path, entry: Entry) -> Path:
    """Constrain all page archive roles before any read or write."""
    key = Path(entry.key)
    if key.is_absolute() or ".." in key.parts:
        raise PageError("cache_path_refused")
    directory = cache / key
    for role in ("", "raw", "proofs", "failures", "terms", "inputs"):
        path = directory / role
        if not path.resolve().is_relative_to(cache.resolve()):
            raise PageError("cache_path_refused")
        for parent in (path, *path.parents):
            if parent == cache:
                break
            if parent.is_symlink():
                raise PageError("cache_path_refused")
    return directory
