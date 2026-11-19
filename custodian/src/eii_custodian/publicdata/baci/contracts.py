"""Typed selected-manifest reader. Never discover or fall back to a latest file."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import (
    TERMS_READ_ON_PENDING,
    RegistryError,
    _entry,
)

from .config import METHOD, TABLES, BaciError, Config, digest_ok, require
from .fetch import _entry_check
from .parse import file_hash, parse_archive


@dataclass(frozen=True)
class Trade:
    source_version: str
    hs_revision: str
    year: int
    exporter_code: str
    importer_code: str
    hs_code: str
    value: str
    quantity: str | None
    value_unit: str
    quantity_unit: str
    currency: str
    valuation_basis: str
    quantity_status: str
    source_id: str
    member_sha256: str


@dataclass(frozen=True)
class Country:
    source_id: str
    source_version: str
    country_code: str
    source_name: str
    iso3: str | None


@dataclass(frozen=True)
class Product:
    source_id: str
    source_version: str
    hs_revision: str
    hs_code: str
    source_description: str


@dataclass(frozen=True)
class Release:
    trade: tuple[Trade, ...]
    country: tuple[Country, ...]
    product: tuple[Product, ...]
    source_registry: dict[str, object]
    fact_lineage: tuple[dict[str, object], ...]
    manifest: dict[str, object]


def read_selected(cache: Path, selected: str) -> Release:
    """Revalidate archive, all output bytes and lineage before returning rows."""
    require(digest_ok(selected), "selected_manifest")
    directory = cache / "cepii_baci"
    try:
        path = directory / f"{selected}.manifest.json"
        require(file_hash(path) == selected, "manifest_hash")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        require(
            isinstance(manifest, dict) and manifest.get("complete") is True,
            "manifest_complete",
        )
        config = Config.from_mapping(manifest["config"])
        require(
            config.confirmed and config.access == "visitor", "manifest_configuration"
        )
        require(
            manifest["method"] == METHOD
            and manifest["attribution"] == config.attribution,
            "lineage",
        )
        receipt = manifest["receipt"]
        entry = _entry(manifest["entry"])
        _entry_check(entry, config)
        require(
            manifest["terms_fingerprint_kind"] == "visible_text", "terms_fingerprint"
        )
        retrieved = receipt["retrieved_utc"]
        try:
            parsed_clock = datetime.strptime(retrieved, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise BaciError("retrieval_date") from None
        require(
            parsed_clock.strftime("%Y-%m-%dT%H:%M:%SZ") == retrieved,
            "retrieval_date",
        )
        digest = manifest["archive_sha256"]
        require(digest_ok(digest), "archive_hash")
        archive = directory / f"{digest}.zip"
        require(
            file_hash(archive) == digest and receipt["sha256"] == digest, "archive_hash"
        )
        require(
            receipt["publisher"] == config.publisher
            and receipt["landing_url"] == config.page
            and receipt["licence_basis"] == entry.licence_basis
            and receipt["terms_read_on"] == entry.terms_read_on
            and receipt["commit_allowed"] is False,
            "source_chain",
        )
        # Ruling L-1001: the pending reading date is a record, not a date; any
        # other non-empty value that is not a real date still fails this read.
        if receipt["terms_read_on"] != TERMS_READ_ON_PENDING:
            date.fromisoformat(receipt["terms_read_on"])
        require(
            not config.publisher_sha256 or config.publisher_sha256 == digest,
            "archive_checksum",
        )
        require(
            receipt["terms_sha256"] is None or digest_ok(receipt["terms_sha256"]),
            "terms_fingerprint",
        )
        require(receipt["fetch_host"] == entry.fetch_host, "source_chain")
        expected_receipt = sidecar_for(
            entry,
            digest=digest,
            nbytes=archive.stat().st_size,
            fetch_url=entry.url,
            fetch_host=entry.fetch_host,
            retrieved_utc=retrieved,
            publisher=entry.publisher,
            source_modified=config.source_version,
            row_count=manifest["raw"],
            terms_sha256=receipt["terms_sha256"] or "",
        )
        require(receipt == expected_receipt, "source_chain")
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=directory) as temporary:
            parsed = parse_archive(archive, config, Path(temporary))
            for key in parsed:
                require(parsed[key] == manifest[key], "manifest_content")
        outputs = manifest["outputs"]
        rows: list[list[dict[str, object]]] = []
        for table in TABLES:
            output_hash = outputs[table]["sha256"]
            require(digest_ok(output_hash), "output_hash")
            output = directory / f"{output_hash}.jsonl"
            require(file_hash(output) == output_hash, "output_hash")
            rows.append(
                [
                    json.loads(line)
                    for line in output.read_text(encoding="utf-8").splitlines()
                ]
            )
        registry = {
            "source_id": "cepii_baci",
            "kind": "public_dataset",
            "title": entry.title_en,
            "publisher": config.publisher,
            "url": config.page,
            "licence": entry.licence_id,
            "licence_basis": entry.licence_basis,
            "retrieved_on": retrieved[:10],
            "sha256": selected,
            "commit_allowed": False,
            "attribution": config.attribution,
            "public_splits": None,
        }
        lineage: tuple[dict[str, object], ...] = tuple(
            {
                "lineage_id": "lin_" + table,
                "table_name": table,
                "source_id": "cepii_baci",
                "input_class": "public",
                "transform": METHOD,
                "partition_id": None,
                "measure": None,
                "breakdown": None,
                "family_role": None,
                "rules_version_id": None,
            }
            for table in TABLES
        )
        return Release(
            tuple(Trade(**cast(dict[str, Any], row)) for row in rows[0]),
            tuple(Country(**cast(dict[str, Any], row)) for row in rows[1]),
            tuple(Product(**cast(dict[str, Any], row)) for row in rows[2]),
            registry,
            lineage,
            manifest,
        )
    except (OSError, ValueError, KeyError, TypeError, RegistryError):
        raise BaciError("selected_manifest_invalid") from None
