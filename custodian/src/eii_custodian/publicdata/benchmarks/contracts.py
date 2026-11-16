"""Closed benchmark rows. Public splits never cross the record/protected boundary."""

from dataclasses import dataclass, fields
from pathlib import Path

from eii_custodian.publicdata.fetch.decimals import exact_decimal

TABLES = {
    "wb_wdi": "pub_wdi_benchmark",
    "unctad_fdi": "pub_unctad_fdi_benchmark",
    "imf_weo": "pub_weo_benchmark",
    "ilostat_qat": "pub_ilostat_benchmark",
}
STATUSES = ("historical", "publisher_estimate", "publisher_forecast", "unclassified")


@dataclass(frozen=True)
class Benchmark:
    source_id: str
    source_version: str
    country_code: str
    indicator_code: str
    dimension_key: str
    frequency: str
    period: str
    unit: str
    currency: str | None
    scale: str
    price_basis: str | None
    publisher_status: str
    historical_value: str | None
    publisher_estimate_value: str | None
    publisher_forecast_value: str | None
    unclassified_value: str | None
    value_status: str
    source_flags: str
    receipt_sha256: str
    source_row_key: str


def validate_row(row: Benchmark) -> None:
    if row.source_id not in TABLES:
        raise ValueError("benchmark source_id")
    for field in fields(row):
        value = getattr(row, field.name)
        nullable = field.name.endswith("_value") or field.name in {
            "currency",
            "price_basis",
        }
        if value is None and nullable:
            continue
        if not isinstance(value, str) or (not value and field.name != "source_flags"):
            raise ValueError("benchmark row_schema")
    if len(row.receipt_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in row.receipt_sha256
    ):
        raise ValueError("benchmark receipt_hash")
    if row.publisher_status not in STATUSES or row.value_status not in {
        "present",
        "source_missing",
    }:
        raise ValueError("benchmark status_values")
    for status in STATUSES:
        value = getattr(row, status + "_value")
        expected = row.value_status == "present" and row.publisher_status == status
        if (value is not None) != expected:
            raise ValueError("benchmark status_values")
        if value is not None:
            exact_decimal(value, total_digits=1000, fractional_digits=1000, signed=True)


def validate_use(row: Benchmark, operation: str, target: str) -> None:
    """This release supports source-grain context only, including unsplit rows.

    Rule 10: no join to synthetic records, segmentation of worker, residence or
    company records, combination with protected figures, or drawn-area apportionment.
    UNCTAD figures cannot join or sum with announced project amounts.
    """
    validate_row(row)
    if operation != "context" or target != "source_geography":
        raise ValueError(f"{row.source_id} forbidden_use")


def historical_rows(rows: tuple[Benchmark, ...]) -> tuple[Benchmark, ...]:
    for row in rows:
        validate_row(row)
    return tuple(row for row in rows if row.publisher_status == "historical")


@dataclass(frozen=True)
class Release:
    rows: tuple[Benchmark, ...]
    receipt: dict[str, object]
    manifest: dict[str, object]


def read_selected(cache: Path, source_id: str, manifest_sha256: str) -> Release:
    import json
    from dataclasses import asdict
    from datetime import datetime

    from eii_custodian.publicdata.fetch.bounded import file_hash
    from eii_custodian.publicdata.fetch.receipts import sidecar_for
    from eii_custodian.publicdata.fetch.registry import _entry

    from .config import METHOD, Policy, digest_ok, require
    from .fetch import build_rows, entry_check, terms_fingerprint
    from .parse import parse_with_coverage

    require(source_id in TABLES and digest_ok(manifest_sha256), "selected_manifest")
    directory = cache / source_id
    try:
        path = directory / f"{manifest_sha256}.manifest.json"
        require(file_hash(path) == manifest_sha256, "manifest_hash")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        require(
            manifest["complete"] is True
            and manifest["commit_allowed"] is False
            and manifest["method"] == METHOD,
            "manifest_contract",
        )
        policy = Policy.from_mapping(manifest["policy"])
        require(
            policy.source_id == source_id
            and policy.confirmed
            and policy.access == "visitor",
            "manifest_policy",
        )
        entry = _entry(manifest["entry"])
        entry_check(entry, policy)
        receipt = manifest["receipt"]
        raw_hash, output_hash = receipt["sha256"], manifest["output_sha256"]
        require(digest_ok(raw_hash) and digest_ok(output_hash), "output_hash")
        raw = directory / f"{raw_hash}.bin"
        output = directory / f"{output_hash}.json"
        require(
            file_hash(raw) == raw_hash and file_hash(output) == output_hash,
            "output_hash",
        )
        require(
            receipt["publisher"] == policy.publisher
            and receipt["commit_allowed"] is False,
            "source_chain",
        )
        retrieved = receipt["retrieved_utc"]
        require(
            datetime.strptime(retrieved, "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            == retrieved,
            "retrieval_date",
        )
        require(receipt["fetch_host"] == entry.fetch_host, "source_chain")
        parsed = parse_with_coverage(raw.read_bytes(), policy, raw_hash)
        rows = build_rows(parsed.rows)
        expected_receipt = sidecar_for(
            entry,
            digest=raw_hash,
            nbytes=raw.stat().st_size,
            fetch_url=policy.url,
            fetch_host=entry.fetch_host,
            retrieved_utc=retrieved,
            publisher=policy.publisher,
            source_modified=policy.source_version,
            row_count=len(rows),
            terms_sha256=terms_fingerprint(entry),
        )
        expected_receipt["coverage"] = parsed.coverage
        require(receipt == expected_receipt, "source_chain")
        require(
            json.loads(output.read_text(encoding="utf-8"))
            == [asdict(row) for row in rows]
            and manifest["selected"] == len(rows),
            "reparsed_output",
        )
        return Release(rows, receipt, manifest)
    except (OSError, KeyError, TypeError, json.JSONDecodeError, UnicodeError):
        raise ValueError(f"{source_id} selected_manifest_invalid") from None
