"""Owner awards intake: reviewed columns, day-first dates, blanks and proof lineage.

Only the lead runs this on an owner's file. Tests create invented CSV or OOXML
workbooks. No library or network reader is introduced.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .allowlist import approve, host_of
from .award_checks import (
    AWARD_ABSENT,
    AwardError,
    double_space_only,
    match_register,
    validate_check_receipt,
)
from .award_links import (
    SHAPE_REASONS,
    ProofFetchError,
    check_all_awards,
    sample_from_links,
    validate_links_receipt,
)
from .award_pool import ReaderPool
from .award_store import ProofStore, verify_legacy_proofs
from .certificate_pins import (
    Pin,
    PinError,
    _bounded_intake,
    intake_file,
    load_pin,
    page_transport,
)
from .page_archive import staged_source, verify_source_directory
from .page_records import (
    _value,
    cache_directory,
    load_declaration,
    parse_body,
    validate_claim,
)
from .receipts import sha256_hex, sidecar_for
from .registry import Entry
from .snapshots import Snapshot, SnapshotError, publish_snapshot, read_snapshot, utc
from .transport import Response, Transport, TransportFault, metadata_limit

SOURCE = "awards_owner_scrape"
METHOD = "awards.ingest_awards@v2"
SCRAPE_DATE = "2026-11-03"


@dataclass(frozen=True)
class AwardBatch:
    rows: tuple[dict[str, Any], ...]
    summary: dict[str, object]
    sha256: str
    body: bytes
    extension: str


def _profile(value: object) -> dict[str, Any]:
    if isinstance(value, str) and value == "[LEAD: evidence 3]":
        raise AwardError("awards_profile_pending")
    if not isinstance(value, dict):
        raise AwardError("schema_missing")
    expected = {
        "format",
        "columns",
        "company",
        "registration",
        "value",
        "date",
        "sheet",
        "types",
    }
    columns = value.get("columns")
    if (
        not expected <= set(value)
        or bool(set(value) - expected - {"row_count", "dated_rows", "proof_columns"})
        or value["format"] not in {"csv", "xlsx"}
        or not isinstance(columns, list)
        or not columns
        or len(set(columns)) != len(columns)
        or any(not isinstance(c, str) or not c for c in columns)
        or "report_url" not in columns
        or any(
            value[key] not in columns
            for key in ("company", "registration", "value", "date")
        )
        or not isinstance(value["types"], list)
        or len(value["types"]) != len(columns)
        or any(kind not in {"string", "integer", "number"} for kind in value["types"])
        or any(
            type(value[key]) is not int or value[key] < 0
            for key in ("row_count", "dated_rows")
            if key in value
        )
    ):
        raise AwardError("schema_missing")
    return value


def _xlsx(
    body: bytes,
    sheet: str,
    stored_dates: dict[str, str] | None = None,
    row_numbers: list[int] | None = None,
) -> list[list[str]]:
    """Share the coordinate-preserving reader; a formula reads by its cached value.

    The owner's sheet stores 'Approved Value Number' as formula cells with cached
    values; nothing is evaluated, and a formula without a cached value refuses.
    """
    from .page_html import ShapeError
    from .page_workbook import read_sheet

    try:
        result = read_sheet(body, sheet, cached_formulas=True, date_cells=True)
        if stored_dates is not None:
            stored_dates.update(result.stored_dates)
        if row_numbers is not None:
            row_numbers.extend(result.rows)
        return list(result.rows.values())
    except ShapeError:
        raise AwardError("schema_missing") from None


def ingest_awards(
    cache: Path,
    path: Path,
    digest: str,
    profile: object,
    stamp: str,
    *,
    max_bytes: int | None = None,
) -> AwardBatch:
    """Constrain the file before reading, verify hash, preserve original cells."""
    folder = cache / "intake" / SOURCE
    if (
        not path.resolve().is_relative_to(folder.resolve())
        or path.is_symlink()
        or any(p.is_symlink() for p in (folder, *folder.parents) if p != cache.parent)
    ):
        raise AwardError("intake_path_refused")
    schema = _profile(profile)
    utc(stamp)
    try:
        body = (
            path.read_bytes() if max_bytes is None else _bounded_intake(path, max_bytes)
        )
    except OSError:
        raise AwardError("intake_missing") from None
    if sha256_hex(body) != digest:
        raise AwardError("snapshot_hash_mismatch")
    stored_dates: dict[str, str] = {}
    row_numbers: list[int] = []
    try:
        raw = (
            list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
            if schema["format"] == "csv"
            else _xlsx(body, schema["sheet"], stored_dates, row_numbers)
        )
    except (UnicodeError, csv.Error):
        raise AwardError("schema_missing") from None
    if not raw or raw[0] != schema["columns"]:
        raise AwardError("schema_missing")
    rows: list[dict[str, Any]] = []
    dates: list[str] = []
    unparsed = blank = 0
    unparsed_rows: list[int] = []
    stored_count = 0
    date_column = _column_name(schema["columns"].index(schema["date"]) + 1)
    for index, cells in enumerate(raw[1:], 1):
        row_number = row_numbers[index] if row_numbers else index + 1
        if schema["format"] == "xlsx" and len(cells) < len(raw[0]):
            cells += [""] * (len(raw[0]) - len(cells))
        if len(cells) != len(raw[0]):
            raise AwardError("schema_missing")
        values = {
            column: _value(cell, kind)
            for column, cell, kind in zip(raw[0], cells, schema["types"], strict=True)
        }
        original = dict(zip(raw[0], cells, strict=True))
        value = original[schema["date"]].strip()
        stored = stored_dates.get(f"{date_column}{row_number}")
        parsed: str | None = None
        if not value:
            blank += 1
        else:
            try:
                if stored is not None:
                    stored_count += 1
                    digits = date.fromisoformat(stored)
                    parsed = date(digits.year, digits.day, digits.month).isoformat()
                else:
                    parsed = datetime.strptime(value, "%d/%m/%Y").date().isoformat()
                dates.append(parsed)
            except ValueError:
                unparsed += 1
                unparsed_rows.append(row_number)
        rows.append(
            {
                "original": original,
                "parsed": values,
                "normalised_date": parsed,
                "report_url": original["report_url"],
                "retrieved_utc": stamp,
            }
        )
    summary: dict[str, object] = {
        "row_count": len(rows),
        "dated_rows": len(dates),
        "unparsed_dates": unparsed,
        "blank_dates": blank,
        "date_first": min(dates) if dates else None,
        "date_last": max(dates) if dates else None,
        "completeness": "unknown",
        "stored_date_cells": stored_count,
        "unparsed_date_rows": unparsed_rows,
        "date_reading_assumption": "stored_day_month_swapped",
    }
    return AwardBatch(tuple(rows), summary, digest, body, schema["format"])


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def read_intake(
    cache: Path, declaration: Mapping[str, Any], stamp: str
) -> tuple[AwardBatch, int, object]:
    """Use the same bounded, hash-verified intake for the scrape and list cut-off."""
    try:
        manifest = json.loads(
            _bounded_intake(intake_file(cache, SOURCE, "intake.json"), 65536)
        )
        if not isinstance(manifest, dict) or set(manifest) != {
            "file",
            "sha256",
            "seed",
            "register_selections",
        }:
            raise AwardError("intake_missing")
        if not isinstance(manifest["file"], str) or not isinstance(
            manifest["sha256"], str
        ):
            raise AwardError("intake_missing")
        if type(manifest["seed"]) is not int:
            raise AwardError("award_seed_pending")
        profile = _intake_profile(declaration)
        batch = ingest_awards(
            cache,
            intake_file(cache, SOURCE, manifest["file"]),
            manifest["sha256"],
            profile,
            stamp,
            max_bytes=declaration.get("max_bytes"),
        )
        return batch, manifest["seed"], manifest["register_selections"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise AwardError("intake_missing") from None


def intake_cutoff(cache: Path, stamp: str) -> tuple[str | None, str, str | None]:
    """An unavailable workbook means a full list read, never a fabricated cut-off."""
    from .page_html import ShapeError
    from .page_records import PageError

    try:
        declaration = load_declaration(SOURCE)
        batch, _seed, selections = read_intake(cache, declaration, stamp)
        read_registers(cache, selections)
        if "url" in declaration:
            _proof_urls(batch, declaration, host_of(declaration["url"]))
            _report_pin(cache, declaration)
    except (AwardError, PinError, PageError, ShapeError, SnapshotError) as exc:
        return None, str(exc), None
    last = batch.summary["date_last"]
    return (
        (str(last), "", batch.sha256)
        if last
        else (None, "award_dates_missing", batch.sha256)
    )


def publish_awards(
    entry: Entry,
    cache: Path,
    batch: AwardBatch,
    profile: Mapping[str, Any],
    stamp: str,
    seed: int,
    proof_reader: Callable[[str], Mapping[str, str] | Sequence[Mapping[str, str]]],
    registers: list[dict[str, str]],
    registration_inputs: list[dict[str, object]] | None = None,
) -> Snapshot:
    """Stage a complete standalone intake before publishing either archive."""
    cache_directory(cache, entry)
    with staged_source(cache, entry.key) as stage:
        result = _publish_awards(
            entry,
            stage,
            batch,
            profile,
            stamp,
            seed,
            proof_reader,
            registers,
            registration_inputs,
        )
    return read_snapshot(cache / entry.key, result.sha256)


def _publish_awards(
    entry: Entry,
    cache: Path,
    batch: AwardBatch,
    profile: Mapping[str, Any],
    stamp: str,
    seed: int,
    proof_reader: Callable[[str], Mapping[str, str] | Sequence[Mapping[str, str]]],
    registers: list[dict[str, str]],
    registration_inputs: list[dict[str, object]] | None = None,
    *,
    links: dict[str, Any] | None = None,
    readers: dict[str, object] | None = None,
) -> Snapshot:
    """Append one intake snapshot with full-link and labelled sample evidence."""
    # Ruling L-1001: a pending basis of use is a record and never refuses.
    if entry.source_id != SOURCE or entry.commit_allowed:
        raise AwardError("receipt_missing")
    if type(seed) is not int:
        raise AwardError("award_seed_pending")
    for row in batch.rows:
        utc(row.get("retrieved_utc"))
    cache_directory(cache, entry)
    validate_claim(SOURCE, "awarded_value")
    originals = [row["original"] for row in batch.rows]
    if links is None:
        links = check_all_awards(originals, profile, proof_reader)
    if any(item["result"] == "refused" for item in links["results"]):
        raise AwardError("award_proof_refused")
    # Publication independently checks the full frame against the intake below.
    check = sample_from_links(links, seed)
    match = match_register(originals, profile, registers)
    side = sidecar_for(
        entry,
        digest=batch.sha256,
        nbytes=len(batch.body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc=stamp,
        publisher=entry.publisher,
        source_modified=SCRAPE_DATE,
        row_count=len(batch.rows),
        terms_sha256="",
    )
    side.update(
        as_of=utc(stamp).date().isoformat(),
        period_first=batch.summary.get("date_first"),
        period_last=batch.summary.get("date_last"),
        award_check=check,
        award_check_scope="sample",
        award_links=links,
        award_readers=readers or ReaderPool().receipt(),
        summary=batch.summary,
        method=METHOD,
        original_scrape_date=SCRAPE_DATE,
        registration_match=match,
        registration_double_space_only=double_space_only(match, profile, registers),
        registration_inputs=registration_inputs or [],
    )
    validate_check_receipt(side)
    validate_links_receipt(side, originals)
    raw = publish_snapshot(cache / entry.key / "raw", batch.extension, batch.body, side)
    body = json.dumps(
        {
            "rows": batch.rows,
            "as_of": utc(stamp).date().isoformat(),
            "period_first": batch.summary.get("date_first"),
            "period_last": batch.summary.get("date_last"),
            "summary": batch.summary,
            "raw_identity": raw.sha256,
            "source_sha256": batch.sha256,
            "provenance": "Public",
            "method": METHOD,
            "label": "owner scrape of public award reports, retrieved 2026-11-03",
        },
        sort_keys=True,
    ).encode()
    result = publish_snapshot(
        cache / entry.key,
        "json",
        body,
        dict(side, sha256=sha256_hex(body), bytes=len(body)),
    )
    return result


def _intake_profile(declaration: Mapping[str, Any]) -> dict[str, Any]:
    profile = _profile(declaration.get("profile"))
    version_two = declaration.get("version") == 2
    if version_two:
        from .page_html import ShapeError
        from .page_schema import validate

        try:
            validate(declaration)
        except ShapeError as exc:
            raise AwardError(str(exc)) from None
        if declaration["hold"] is not None:
            raise AwardError(declaration["hold"])
        if declaration["max_bytes"] is None:
            raise AwardError("acquisition_bound_unconfirmed")
        mapping = profile.get("proof_columns")
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"company", "registration", "value"}
            or any(
                mapping[k] not in {c[0] for c in declaration["columns"]}
                for k in mapping
            )
        ):
            raise AwardError("awards_profile_pending")
    return profile


def _proof_response(
    url: str,
    transport: Transport,
    sleep: Callable[[float], None],
    declaration: Mapping[str, Any],
    proof_urls: frozenset[str],
    pin: Pin | None,
    pool: ReaderPool,
) -> Response:
    from .kinds import read_bounded, require_verified_chain
    from .page_requests import page_requests

    version_two = declaration.get("version") == 2

    def send(address: str) -> Response:
        try:
            return transport(address)
        except TransportFault as exc:
            if exc.kind == "unreachable" or exc.status in {429, 503}:
                pool.reduce(
                    "unreachable" if exc.kind == "unreachable" else "http_status"
                )
            raise
        except OSError:
            pool.reduce("unreachable")
            raise

    scope = (
        page_requests(tuple(sorted(proof_urls)), {pin.host: pin} if pin else {})
        if version_two
        else nullcontext()
    )
    limit = metadata_limit(declaration["max_bytes"]) if version_two else nullcontext()
    with scope, limit, page_transport(None if version_two else pin):
        response, failure = read_bounded(send, sleep, url)
    require_verified_chain(failure)
    if (
        version_two
        and response is not None
        and len(response.body) > declaration["max_bytes"]
    ):
        raise AwardError("metadata_bytes")
    if failure is not None and failure.check == "blocked_host":
        raise AwardError("blocked_host")
    if failure or response is None:
        raise ProofFetchError(failure.check if failure else "proof_fetch_failed")
    if any(
        address not in proof_urls for address in (*response.hops, response.final_url)
    ):
        raise AwardError("blocked_host")
    return response


def _proof_reader(
    entry: Entry,
    declaration: Mapping[str, Any],
    store: ProofStore,
    proof_urls: frozenset[str],
    pin: Pin | None,
    pool: ReaderPool,
    transport: Transport | None,
    sleep: Callable[[float], None],
) -> Callable[[str], Sequence[Mapping[str, str]]]:
    from .page_records import _obstacle

    profile = declaration["profile"]
    version_two = declaration.get("version") == 2
    proof_entry = replace(
        entry, columns=tuple(tuple(pair) for pair in declaration["columns"])
    )

    def read(url: str) -> Sequence[Mapping[str, str]]:
        if url not in proof_urls:
            raise AwardError("blocked_host")
        body = store.body(url, replay=transport is None)
        if body is None:
            assert transport is not None
            response = _proof_response(
                url, transport, sleep, declaration, proof_urls, pin, pool
            )
            body = store.save(url, response)
        _obstacle(body)
        rows = parse_body(body, proof_entry, declaration)
        if version_two and rows == [AWARD_ABSENT]:
            return [dict(AWARD_ABSENT)]
        if not rows:
            raise AwardError("schema_missing")
        if version_two:
            return [
                {
                    profile[key]: ""
                    if row[profile["proof_columns"][key]] is None
                    else str(row[profile["proof_columns"][key]])
                    for key in ("company", "registration", "value")
                }
                for row in rows
            ]
        return [
            {key: "" if value is None else str(value) for key, value in row.items()}
            for row in rows
        ]

    return read


def _awards_context(
    entry: Entry, cache: Path, clock: Callable[[], str]
) -> tuple[dict[str, Any], AwardBatch, int, object, frozenset[str], str]:
    declaration = load_declaration(SOURCE)
    _intake_profile(declaration)
    cache_directory(cache, entry)
    if (
        not entry.publisher
        or entry.commit_allowed
        or entry.url != declaration.get("url")
        or not approve(entry.url).ok
    ):
        raise AwardError("receipt_missing")
    verify_source_directory(cache / entry.key)
    verify_legacy_proofs(cache, entry)
    stamp = clock()
    batch, seed, selections = read_intake(cache, declaration, stamp)
    urls = frozenset(_proof_urls(batch, declaration, entry.fetch_host))
    return declaration, batch, seed, selections, urls, stamp


def fetch_awards(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Snapshot:
    """Acquire durable proofs before staging publication; resume is per link."""
    declaration, batch, seed, selections, urls, stamp = _awards_context(
        entry, cache, clock
    )
    registers, registration_inputs = read_registers(cache, selections)
    pin = _report_pin(cache, declaration)
    pool = ReaderPool(declaration.get("max_readers", 1))
    store = ProofStore(cache, entry, declaration, stamp, clock)
    reader = _proof_reader(entry, declaration, store, urls, pin, pool, transport, sleep)
    # The check receipt survives source publication refusal, just like proofs.
    links = check_all_awards(
        [row["original"] for row in batch.rows],
        declaration["profile"],
        reader,
        pool=pool,
    )
    report = _proof_report(links)
    report["award_readers"] = pool.receipt()
    report_body = json.dumps(report, sort_keys=True).encode()
    publish_snapshot(
        cache / entry.key / "proof_checks",
        "json",
        report_body,
        {
            "source_id": SOURCE,
            "key": entry.key,
            "retrieved_utc": stamp,
            "sha256": sha256_hex(report_body),
            "bytes": len(report_body),
        },
    )
    if any(item["result"] == "refused" for item in links["results"]):
        raise AwardError("award_proof_refused")
    with staged_source(cache, entry.key) as stage:
        result = _publish_awards(
            entry,
            stage,
            batch,
            declaration["profile"],
            stamp,
            seed,
            reader,
            registers,
            registration_inputs,
            links=links,
            readers=pool.receipt(),
        )
    return read_snapshot(cache / entry.key, result.sha256)


def replay_awards(
    entry: Entry, cache: Path, clock: Callable[[], str]
) -> dict[str, Any]:
    """Closed offline mode: no transport exists, missing proofs refuse by name."""
    declaration, batch, _seed, _selections, urls, stamp = _awards_context(
        entry, cache, clock
    )
    pool = ReaderPool()  # Local parsing needs no network concurrency.
    store = ProofStore(cache, entry, declaration, stamp)
    reader = _proof_reader(
        entry, declaration, store, urls, None, pool, None, lambda _: None
    )
    report = _proof_report(
        check_all_awards(
            [row["original"] for row in batch.rows], declaration["profile"], reader
        )
    )
    report["award_readers"] = pool.receipt()
    return report


def _proof_report(links: dict[str, Any]) -> dict[str, Any]:
    refusals = [item for item in links["results"] if item["result"] == "refused"]
    return {
        "award_links": links,
        "refused_count": len(refusals),
        "refusals_by_class": {
            reason: sum(item["reason"] == reason for item in refusals)
            for reason in sorted(SHAPE_REASONS)
        },
    }


def _report_pin(cache: Path, declaration: Mapping[str, Any]) -> Pin | None:
    host = host_of(declaration["url"])
    if host != "monaqasat.mof.gov.qa" and not isinstance(declaration.get("pin"), dict):
        return None
    config = (
        next((p for p in declaration["pins"] if p["host"] == host), None)
        if declaration.get("version") == 2
        else declaration.get("pin")
    )
    return load_pin(cache, SOURCE, config)


def _proof_urls(
    batch: AwardBatch, declaration: Mapping[str, Any], host: str
) -> tuple[str, ...]:
    """Only intake-delivered report links may extend the reviewed exact-URL frame."""
    from urllib.parse import urlsplit

    urls = list(declaration["reviewed_urls"])
    if declaration.get("profile", {}).get("format") != "xlsx":
        return tuple(urls)
    prefix = "/TendersOnlineServices/TenderCompaniesDetails/"
    for row in batch.rows:
        link = row["report_url"].strip()
        if not link:
            continue
        parts = urlsplit(link)
        suffix = parts.path.removeprefix(prefix)
        if (
            not approve(link).ok
            or host_of(link) != host
            or not parts.path.startswith(prefix)
            or not suffix
            or not suffix.isascii()
            or not all(c.isalnum() or c in "-_" for c in suffix)
            or parts.query
            or parts.fragment
        ):
            raise AwardError("blocked_host")
        if link not in urls:
            urls.append(link)
    return tuple(urls)


def read_registers(
    cache: Path, selections: object
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Read only explicit archived public-register inputs for the name adapter."""
    if not isinstance(selections, list):
        raise AwardError("register_schema_missing")
    rows: list[dict[str, str]] = []
    lineage: list[dict[str, object]] = []
    fields = {"key", "identity", "format", "registration_column", "name_column"}
    for selection in selections:
        if (
            not isinstance(selection, dict)
            or set(selection) != fields
            or any(not isinstance(value, str) for value in selection.values())
        ):
            raise AwardError("register_schema_missing")
        key = selection["key"]
        source = key.split("/")[0]
        if source not in {"biz_register", "fc_register"} or ".." in Path(key).parts:
            raise AwardError("register_schema_missing")
        directory = cache / key
        if not directory.resolve().is_relative_to(cache.resolve()):
            raise AwardError("intake_path_refused")
        snapshot = read_snapshot(directory, selection["identity"])
        # Ruling L-1001: a pending basis in a stored receipt is a record, never
        # a missing one; identity, key and publisher still have to match.
        # Ruling L-1016 R3 (ruling L-1025 item a): the build itself writes every
        # stored receipt, so a sidecar without the licence_basis key is a
        # defect, not a terms reading, and refuses; a blank or "pending" value
        # stays a record.
        if (
            snapshot.sidecar.get("source_id") != source
            or snapshot.sidecar.get("key") != key
            or not snapshot.sidecar.get("publisher")
            or "licence_basis" not in snapshot.sidecar
        ):
            raise AwardError("receipt_missing")
        try:
            if selection["format"] == "json_records":
                records = json.loads(snapshot.body)
            elif selection["format"] == "csv_records":
                records = list(
                    csv.DictReader(io.StringIO(snapshot.body.decode("utf-8-sig")))
                )
            else:
                raise AwardError("register_schema_missing")
        except (ValueError, UnicodeError, csv.Error):
            raise AwardError("register_schema_missing") from None
        if not isinstance(records, list):
            raise AwardError("register_schema_missing")
        for record in records:
            if not isinstance(record, dict):
                raise AwardError("register_schema_missing")
            registration, name = (
                record.get(selection["registration_column"]),
                record.get(selection["name_column"]),
            )
            if not isinstance(registration, str) or not isinstance(name, str):
                raise AwardError("register_schema_missing")
            rows.append({"registration": registration, "name": name})
        lineage.append(
            {
                "key": key,
                "identity": selection["identity"],
                "sha256": snapshot.sha256,
                "retrieved_utc": snapshot.sidecar["retrieved_utc"],
            }
        )
    return rows, lineage
