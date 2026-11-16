"""Typed selected-manifest reader for Gravity. No latest-file discovery."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from eii_custodian.publicdata.baci.contracts import Country as BaciCountry
from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import RegistryError, _entry

from .config import METHOD, SOURCE_ID, TABLES, Config, GravityError, digest_ok, require
from .fetch import _entry_check
from .parse import file_hash, parse_archive


def same_key_kind(left: str, right: str, width: int) -> bool:
    """Same kind means equal width only. A BACI code is not a Gravity code."""
    return len(left) == width == len(right) and width > 0 and left != "" and right != ""


def baci_country_is_not_joined(country: BaciCountry, code: str, width: int) -> bool:
    """Width may match. The BACI row is never copied onto a Gravity record."""
    return (
        same_key_kind(country.country_code, code, width)
        and country.source_id != SOURCE_ID
    )


@dataclass(frozen=True)
class Bilateral:
    source_version: str
    hs_revision: str
    hs_detail: str
    year: int
    origin_code: str
    destination_code: str
    distance: str | None
    distance_unit: str
    distance_status: str
    contig: str | None
    common_language: str | None
    colonial_link: str | None
    trade_agreement: str | None
    gdp_origin: str | None
    gdp_origin_unit: str
    gdp_origin_status: str
    gdp_destination: str | None
    gdp_destination_unit: str
    gdp_destination_status: str
    source_id: str
    member_sha256: str


@dataclass(frozen=True)
class Country:
    source_id: str
    source_version: str
    country_code: str
    source_name: str


@dataclass(frozen=True)
class Release:
    bilateral: tuple[Bilateral, ...]
    country: tuple[Country, ...]
    source_registry: dict[str, object]
    fact_lineage: tuple[dict[str, object], ...]
    manifest: dict[str, object]


def read_selected(cache: Path, selected: str) -> Release:
    """Revalidate the archive, output bytes and lineage before returning rows."""
    require(digest_ok(selected), "selected_manifest")
    directory = cache / SOURCE_ID
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
        require(manifest["publisher_mapping"] == "pending", "publisher_mapping")
        receipt = manifest["receipt"]
        entry = _entry(manifest["entry"])
        _entry_check(entry, config)
        require(
            manifest["terms_fingerprint_kind"] == "visible_text", "terms_fingerprint"
        )
        retrieved = receipt["retrieved_utc"]
        require(
            datetime.strptime(retrieved, "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            == retrieved,
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
        require(
            not config.publisher_sha256 or config.publisher_sha256 == digest,
            "archive_checksum",
        )
        require(
            receipt["terms_sha256"] is None or digest_ok(receipt["terms_sha256"]),
            "terms_fingerprint",
        )
        final_host = manifest["archive_host"]
        require(
            final_host in {host_of(url) for url in config.reviewed_urls}, "source_chain"
        )
        expected = sidecar_for(
            entry,
            digest=digest,
            nbytes=archive.stat().st_size,
            fetch_url=entry.url,
            fetch_host=final_host,
            retrieved_utc=retrieved,
            publisher=entry.publisher,
            source_modified=config.source_version,
            row_count=manifest["raw"],
            terms_sha256=receipt["terms_sha256"] or "",
        )
        require(receipt == expected, "source_chain")
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=directory) as temporary:
            parsed = parse_archive(archive, config, Path(temporary))
            for key in parsed:
                require(parsed[key] == manifest[key], "manifest_content")
        outputs = manifest["outputs"]
        rows: list[list[dict[str, object]]] = []
        for table in TABLES:
            output_hash = outputs[table]["sha256"]
            output = directory / f"{output_hash}.jsonl"
            require(file_hash(output) == output_hash, "output_hash")
            rows.append(
                [
                    json.loads(line)
                    for line in output.read_text(encoding="utf-8").splitlines()
                ]
            )
        registry = {
            "source_id": SOURCE_ID,
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
                "source_id": SOURCE_ID,
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
            tuple(Bilateral(**cast(dict[str, Any], row)) for row in rows[0]),
            tuple(Country(**cast(dict[str, Any], row)) for row in rows[1]),
            registry,
            lineage,
            manifest,
        )
    except (OSError, ValueError, KeyError, TypeError, RegistryError):
        raise GravityError("selected_manifest_invalid") from None
