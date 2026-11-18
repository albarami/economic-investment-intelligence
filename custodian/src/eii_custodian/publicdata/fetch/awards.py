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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .allowlist import approve, host_of
from .award_checks import (
    AwardError,
    check_awards,
    double_space_only,
    match_register,
    validate_check_receipt,
)
from .certificate_pins import intake_file, load_pin, page_transport
from .page_archive import staged_source
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
from .transport import Transport, metadata_limit

SOURCE = "awards_owner_scrape"
METHOD = "awards.ingest_awards@v1"
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


def _xlsx(body: bytes, sheet: str) -> list[list[str]]:
    """Share the coordinate-preserving reader, retaining the intake formula refusal."""
    from .page_html import ShapeError
    from .page_workbook import read_sheet

    try:
        return list(read_sheet(body, sheet).rows.values())
    except ShapeError:
        raise AwardError("schema_missing") from None


def ingest_awards(
    cache: Path, path: Path, digest: str, profile: object, stamp: str
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
        body = path.read_bytes()
    except OSError:
        raise AwardError("intake_missing") from None
    if sha256_hex(body) != digest:
        raise AwardError("snapshot_hash_mismatch")
    try:
        raw = (
            list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
            if schema["format"] == "csv"
            else _xlsx(body, schema["sheet"])
        )
    except (UnicodeError, csv.Error):
        raise AwardError("schema_missing") from None
    if not raw or raw[0] != schema["columns"]:
        raise AwardError("schema_missing")
    rows: list[dict[str, Any]] = []
    dates: list[str] = []
    unparsed = blank = 0
    for cells in raw[1:]:
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
        parsed: str | None = None
        if not value:
            blank += 1
        else:
            try:
                parsed = datetime.strptime(value, "%d/%m/%Y").date().isoformat()
                dates.append(parsed)
            except ValueError:
                unparsed += 1
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
    }
    return AwardBatch(tuple(rows), summary, digest, body, schema["format"])


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
) -> Snapshot:
    """Append one intake snapshot with the sample check on its registry receipt."""
    # Ruling L-1001: a pending basis of use is a record and never refuses.
    if entry.source_id != SOURCE or entry.commit_allowed:
        raise AwardError("receipt_missing")
    for row in batch.rows:
        utc(row.get("retrieved_utc"))
    cache_directory(cache, entry)
    validate_claim(SOURCE, "awarded_value")
    originals = [row["original"] for row in batch.rows]
    check = check_awards(originals, profile, seed, proof_reader)
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
        summary=batch.summary,
        method=METHOD,
        original_scrape_date=SCRAPE_DATE,
        registration_match=match,
        registration_double_space_only=double_space_only(match, profile, registers),
        registration_inputs=registration_inputs or [],
    )
    validate_check_receipt(side)
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


def fetch_awards(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Snapshot:
    """Normal build dispatch; the lead supplies the reviewed intake manifest."""
    from dataclasses import replace

    from .kinds import read_bounded
    from .page_records import _obstacle

    declaration = load_declaration(SOURCE)
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
    cache_directory(cache, entry)
    # Ruling L-1001: a pending basis of use is a record and never refuses.
    if (
        not entry.publisher
        or entry.commit_allowed
        or entry.url != declaration.get("url")
        or not approve(entry.url).ok
    ):
        raise AwardError("receipt_missing")
    manifest_path = intake_file(cache, SOURCE, "intake.json")
    try:
        manifest = json.loads(manifest_path.read_bytes())
        path = intake_file(cache, SOURCE, manifest["file"])
        seed = manifest["seed"]
        stamp = clock()
        batch = ingest_awards(cache, path, manifest["sha256"], profile, stamp)
        registers, registration_inputs = read_registers(
            cache, manifest["register_selections"]
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise AwardError("intake_missing") from None

    pin = (
        load_pin(
            cache,
            SOURCE,
            next(
                (p for p in declaration["pins"] if p["host"] == host_of(entry.url)),
                None,
            )
            if version_two
            else declaration.get("pin"),
        )
        if host_of(entry.url) == "monaqasat.mof.gov.qa"
        or isinstance(declaration.get("pin"), dict)
        else None
    )

    destination = cache
    with staged_source(cache, entry.key) as cache:

        def proof_reader(url: str) -> Mapping[str, str] | Sequence[Mapping[str, str]]:
            if url not in declaration["reviewed_urls"]:
                raise AwardError("blocked_host")
            from .page_requests import page_requests

            scope = (
                page_requests(
                    tuple(declaration["reviewed_urls"]), {pin.host: pin} if pin else {}
                )
                if version_two
                else nullcontext()
            )
            limit = (
                metadata_limit(declaration["max_bytes"])
                if version_two
                else nullcontext()
            )
            with scope, limit, page_transport(None if version_two else pin):
                response, failure = read_bounded(transport, sleep, url)
            if (
                version_two
                and response is not None
                and len(response.body) > declaration["max_bytes"]
            ):
                raise AwardError("metadata_bytes")
            if failure is not None and failure.check == "blocked_host":
                raise AwardError("blocked_host")
            if failure or response is None:
                raise AwardError("proof_fetch_failed")
            if any(
                address not in declaration["reviewed_urls"]
                for address in (*response.hops, response.final_url)
            ):
                raise AwardError("blocked_host")
            _obstacle(response.body)
            proof_entry = replace(
                entry, columns=tuple(tuple(pair) for pair in declaration["columns"])
            )
            rows = parse_body(response.body, proof_entry, declaration)
            if not rows:
                raise AwardError("schema_missing")
            side = sidecar_for(
                entry,
                digest=sha256_hex(response.body),
                nbytes=len(response.body),
                fetch_url=response.final_url,
                fetch_host=entry.fetch_host,
                retrieved_utc=stamp,
                publisher=entry.publisher,
                source_modified="",
                row_count=len(rows),
                terms_sha256="",
            )
            proof_body = response.body
            if version_two:
                from .page_acquire import _html_without_form_secrets

                proof_body = _html_without_form_secrets(proof_body)
                side.update(
                    sha256=sha256_hex(proof_body),
                    bytes=len(proof_body),
                    upstream_sha256=sha256_hex(response.body),
                    representation="form_secret_removed",
                )
            try:
                publish_snapshot(cache / entry.key / "proofs", "html", proof_body, side)
            except OSError:
                raise SnapshotError("snapshot_write_failed") from None
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

        result = _publish_awards(
            entry,
            cache,
            batch,
            profile,
            stamp,
            seed,
            proof_reader,
            registers,
            registration_inputs,
        )
    return read_snapshot(destination / entry.key, result.sha256)


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
