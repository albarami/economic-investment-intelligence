"""Injected Gravity acquisition. Registration or a paid tier fetches nothing."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import NoReturn

from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.bounded import (
    publish_complete,
    read_metadata,
    stream_download,
)
from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import LICENCE_BASES, Entry
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import StreamTransport, Transport

from .config import METHOD, SOURCE_ID, TABLES, Config, GravityError, require, safe_url
from .parse import file_hash, parse_archive


@dataclass(frozen=True)
class Result:
    digest: str
    host: str
    terms_sha256: str
    terms_unread: str
    retrieved_utc: str


def _refuse(reason: str) -> NoReturn:
    raise GravityError(reason) from None


def _reviewed(url: str, config: Config) -> None:
    require(safe_url(url) and url in config.reviewed_urls, "blocked_host")


def _entry_check(entry: Entry, config: Config) -> None:
    require(entry.source_id == SOURCE_ID and entry.key == SOURCE_ID, "source_id")
    require(not entry.commit_allowed and entry.nightly_live_fetch, "registry_policy")
    require(
        entry.licence_basis in LICENCE_BASES and bool(entry.licence_id), "licence_basis"
    )
    require(
        (entry.licence_basis == "owner_decision" and entry.decision_record == "0026")
        or (entry.licence_basis != "owner_decision" and entry.decision_record == ""),
        "licence_basis",
    )
    require(bool(entry.terms_words.strip()), "terms_metadata")
    try:
        require(
            date.fromisoformat(entry.terms_read_on).isoformat() == entry.terms_read_on,
            "terms_date",
        )
    except ValueError:
        raise GravityError("terms_date") from None
    require(entry.publisher == config.publisher and bool(entry.title_en), "publisher")
    require(entry.landing_url == config.page, "page")
    require(bool(config.source_version.strip()), "version")
    require(bool(config.licence_words.strip()), "licence_words")
    require(
        entry.row_count_min == config.raw_rows[0]
        and entry.row_count_max == config.raw_rows[1],
        "raw_bounds",
    )
    require(
        entry.period_first == str(config.period_first)
        and entry.period_last == str(config.period_last),
        "period_bounds",
    )
    require(entry.release_tables == TABLES and bool(entry.columns), "release_contract")
    _reviewed(entry.url, config)
    require(entry.fetch_host == host_of(entry.url), "blocked_host")
    if entry.terms_url:
        _reviewed(entry.terms_url, config)


def _metadata(
    url: str, transport: Transport, config: Config, sleep: Callable[[float], None]
) -> bytes:
    return read_metadata(
        url,
        transport,
        review=lambda address: _reviewed(address, config),
        max_bytes=config.archive_bytes[1],
        sleep=sleep,
        refuse=_refuse,
    )


def _download(
    entry: Entry,
    config: Config,
    transport: StreamTransport,
    target: Path,
    sleep: Callable[[float], None],
) -> str:
    return stream_download(
        entry.url,
        transport,
        target,
        review=lambda address: _reviewed(address, config),
        byte_bounds=config.archive_bytes,
        sleep=sleep,
        refuse=_refuse,
    )


def _publish(path: Path, destination: Path) -> None:
    """Content-addressed writes never remove or overwrite earlier complete bytes."""
    publish_complete(path, destination, _refuse)


def fetch_gravity(
    entry: Entry,
    config: Config,
    metadata_transport: Transport,
    stream_transport: StreamTransport | None,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Result:
    require(config.confirmed and not entry.skip_reason, "gravity_metadata_unconfirmed")
    require(config.bound_origin != "pending", "bounds_unconfirmed")
    require(config.access == "visitor", "access_obstacle")
    _entry_check(entry, config)
    require(callable(stream_transport), "stream_transport_missing")
    assert stream_transport is not None
    page = _metadata(config.page, metadata_transport, config, sleep)
    require(
        hashlib.sha256(page).hexdigest() == config.page_sha256,
        "metadata_changed_review_needed",
    )
    terms_hash = ""
    terms_unread = "terms_to_be_read"
    if entry.terms_url:
        try:
            terms_hash = terms_text_sha256(
                _metadata(entry.terms_url, metadata_transport, config, sleep)
            )
            terms_unread = ""
        except GravityError as exc:
            if str(exc) != "network_exhausted":
                raise
            terms_unread = "network_exhausted"
    retrieved = clock()
    try:
        require(
            datetime.strptime(retrieved, "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            == retrieved,
            "retrieval_date",
        )
    except ValueError:
        raise GravityError("retrieval_date") from None
    directory = cache / SOURCE_ID
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".stage-", dir=directory) as temporary:
            stage = Path(temporary)
            archive = stage / "archive.zip"
            host = _download(entry, config, stream_transport, archive, sleep)
            digest = file_hash(archive)
            require(
                not config.publisher_sha256 or digest == config.publisher_sha256,
                "archive_checksum",
            )
            parsed = parse_archive(archive, config, stage)
            receipt = sidecar_for(
                entry,
                digest=digest,
                nbytes=archive.stat().st_size,
                fetch_url=entry.url,
                fetch_host=host,
                retrieved_utc=retrieved,
                publisher=entry.publisher,
                source_modified=config.source_version,
                row_count=int(str(parsed["raw"])),
                terms_sha256=terms_hash,
            )
            manifest = {
                "complete": True,
                "config": asdict(config),
                "method": METHOD,
                "entry": {
                    **{
                        key: value
                        for key, value in asdict(entry).items()
                        if key not in {"layer", "basis_note", "columns"}
                    },
                    "columns": [
                        {"name": name, "type": kind} for name, kind in entry.columns
                    ],
                },
                "receipt": receipt,
                "attribution": config.attribution,
                "terms_fingerprint_kind": "visible_text",
                "terms_unread": terms_unread,
                "archive_sha256": digest,
                "archive_host": host,
                **parsed,
            }
            manifest_file = stage / "manifest.json"
            manifest_file.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            manifest_digest = file_hash(manifest_file)
            _publish(archive, directory / f"{digest}.zip")
            outputs = parsed["outputs"]
            assert isinstance(outputs, dict)
            for table in TABLES:
                item = outputs[table]
                _publish(
                    stage / f"{table}.jsonl", directory / f"{item['sha256']}.jsonl"
                )
            _publish(manifest_file, directory / f"{manifest_digest}.manifest.json")
            return Result(manifest_digest, host, terms_hash, terms_unread, retrieved)
    except (OSError, TypeError, AttributeError, RuntimeError, ValueError):
        raise GravityError("write_or_stream_failed") from None
