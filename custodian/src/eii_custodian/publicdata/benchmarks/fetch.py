"""Benchmark build boundary: validate all uses before returning any row."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import StreamTransport, Transport

from .config import Policy
from .contracts import Benchmark, validate_use


def build_rows(
    rows: tuple[Benchmark, ...],
    *,
    operation: str = "context",
    target: str = "source_geography",
) -> tuple[Benchmark, ...]:
    for row in rows:
        validate_use(row, operation, target)
    return rows


# Imports remain local to acquisition so the contract has no transport dependency.
def _fetch_benchmark(
    entry: Entry | None,
    policy: Policy,
    metadata: Transport,
    stream: StreamTransport | None,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Result:
    """Fetch one explicitly selected, independently reviewed benchmark."""
    import hashlib
    import json
    import tempfile
    from dataclasses import asdict
    from datetime import datetime
    from pathlib import Path

    from eii_custodian.publicdata.fetch.bounded import (
        file_hash,
        publish_complete,
        read_metadata,
        stream_download,
    )
    from eii_custodian.publicdata.fetch.receipts import sidecar_for

    from .config import METHOD, require, safe_url
    from .parse import parse_with_coverage

    def refuse(reason: str) -> NoReturn:
        raise BenchmarkRefusal(reason) from None

    def review(url: str) -> None:
        if not safe_url(url) or url not in policy.reviewed_urls:
            refuse("blocked_host")

    if not policy.confirmed or entry is None or entry.skip_reason:
        refuse("benchmark_metadata_unconfirmed")
    if policy.access != "visitor":
        refuse("access_obstacle")
    entry_check(entry, policy)
    require(stream is not None, "stream_transport_missing")
    assert stream is not None
    page = read_metadata(
        policy.page,
        metadata,
        review=review,
        max_bytes=policy.bytes[1],
        sleep=sleep,
        refuse=refuse,
        bounded_read=True,
    )
    require(
        hashlib.sha256(page).hexdigest() == policy.page_sha256,
        "metadata_changed_review_needed",
    )
    retrieved = clock()
    require(
        datetime.strptime(retrieved, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        == retrieved,
        "retrieval_date",
    )
    directory = cache / policy.source_id
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stage-", dir=directory) as temporary:
        stage = Path(temporary)
        raw = stage / "raw.bin"
        review(policy.url)
        host = stream_download(
            policy.url,
            stream,
            raw,
            review=review,
            byte_bounds=policy.bytes,
            sleep=sleep,
            refuse=refuse,
        )
        digest = file_hash(raw)
        parsed = parse_with_coverage(raw.read_bytes(), policy, digest)
        rows = build_rows(parsed.rows)
        output = stage / "rows.json"
        output.write_text(
            json.dumps([asdict(row) for row in rows], sort_keys=True), encoding="utf-8"
        )
        output_hash = file_hash(output)
        receipt = sidecar_for(
            entry,
            digest=digest,
            nbytes=raw.stat().st_size,
            fetch_url=policy.url,
            fetch_host=host,
            retrieved_utc=retrieved,
            publisher=policy.publisher,
            source_modified=policy.source_version,
            row_count=len(rows),
            terms_sha256=terms_fingerprint(entry),
        )
        receipt["coverage"] = parsed.coverage
        encoded_entry = {
            key: value
            for key, value in asdict(entry).items()
            if key not in {"layer", "basis_note", "comtrade_policy", "columns"}
        }
        encoded_entry["refetch"] = {
            key: value
            for key, value in asdict(entry.refetch).items()
            if key != "family" or value
        }
        encoded_entry["columns"] = [{"name": n, "type": t} for n, t in entry.columns]
        manifest = stage / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "complete": True,
                    "method": METHOD,
                    "policy": asdict(policy),
                    "entry": encoded_entry,
                    "receipt": receipt,
                    "output_sha256": output_hash,
                    "selected": len(rows),
                    "commit_allowed": False,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        selected = file_hash(manifest)
        publish_complete(raw, directory / f"{digest}.bin", refuse)
        publish_complete(output, directory / f"{output_hash}.json", refuse)
        publish_complete(manifest, directory / f"{selected}.manifest.json", refuse)
        return Result(selected, host)


def entry_check(entry: Entry, policy: Policy) -> None:
    from eii_custodian.publicdata.fetch.allowlist import host_of

    from .config import require
    from .contracts import TABLES

    require(
        entry.source_id == policy.source_id and entry.key == policy.source_id,
        "source_id",
    )
    require(not entry.commit_allowed and entry.nightly_live_fetch, "registry_policy")
    require(
        entry.publisher == policy.publisher
        and entry.landing_url == policy.page
        and entry.url == policy.url,
        "source_chain",
    )
    require(entry.fetch_host == host_of(policy.url), "blocked_host")
    require(
        entry.release_tables == (TABLES[policy.source_id],) and bool(entry.columns),
        "release_contract",
    )
    if policy.native_columns:
        require(
            tuple(name for name, kind in entry.columns) == policy.native_columns
            and all(kind == "string" for name, kind in entry.columns),
            "native_schema",
        )
    require((entry.row_count_min, entry.row_count_max) == policy.raw_rows, "raw_bounds")
    require(
        bool(entry.licence_id)
        and bool(entry.terms_words)
        and bool(entry.terms_read_on),
        "terms_metadata",
    )


@dataclass(frozen=True)
class Result:
    digest: str
    host: str


def fetch_benchmark(
    entry: Entry | None,
    policy: Policy,
    metadata: Transport,
    stream: StreamTransport | None,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Result:
    """Suppress all injected transport, path and response diagnostics."""
    if not policy.confirmed or entry is None or entry.skip_reason:
        raise ValueError(f"{policy.source_id} benchmark_metadata_unconfirmed")
    if policy.access != "visitor":
        raise ValueError(f"{policy.source_id} access_obstacle")
    try:
        return _fetch_benchmark(entry, policy, metadata, stream, cache, clock, sleep)
    except BenchmarkRefusal as exc:
        raise ValueError(f"{policy.source_id} {exc.reason}") from None
    except (ValueError, OSError, RuntimeError, TypeError, AttributeError):
        raise ValueError(f"{policy.source_id} benchmark_validation_failed") from None


def terms_fingerprint(entry: Entry) -> str:
    """Bind recorded terms words, date and basis, without claiming a live page read."""
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(
            {
                name: getattr(entry, name)
                for name in (
                    "terms_words",
                    "terms_read_on",
                    "licence_basis",
                    "licence_id",
                    "terms_url",
                    "licence_url",
                )
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


class BenchmarkRefusal(Exception):
    """Internal closed diagnostic, never response or transport text."""

    def __init__(self, reason: str) -> None:
        self.reason = (
            reason
            if reason
            in {
                "access_obstacle",
                "blocked_host",
                "cache_integrity",
                "metadata_bytes",
                "archive_bytes",
                "declared_length",
                "stream_chunk",
                "length_mismatch",
                "network_exhausted",
                "transport_metadata_invalid",
            }
            else "benchmark_validation_failed"
        )
        super().__init__(self.reason)


def owner_obstacle(policy: Policy) -> dict[str, object] | None:
    if policy.access not in {"registration", "sign_in", "robot_check", "paid_tier"}:
        return None
    return {
        "source_id": policy.source_id,
        "reason": policy.access,
        "evidence_sha256": policy.page_sha256,
        "price_amount": None,
        "price_currency": None,
    }
