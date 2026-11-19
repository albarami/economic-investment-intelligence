"""Typed selected-manifest reader for finished Atlas files. No latest-file discovery."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from eii_custodian.publicdata.baci.contracts import Product as BaciProduct
from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import RegistryError, _entry

from .config import (
    FINISHED,
    METHOD,
    SOURCE_ID,
    TABLES,
    AtlasError,
    Config,
    digest_ok,
    require,
)
from .fetch import _entry_check
from .parse import file_hash, parse_archives


def same_key_kind(left: str, right: str, width: int) -> bool:
    """Same kind means equal width only. A BACI code is not an Atlas code."""
    return len(left) == width == len(right) and width > 0 and left != "" and right != ""


def baci_product_is_not_joined(product: BaciProduct, code: str, width: int) -> bool:
    """Equal width does not copy a BACI product onto an Atlas row."""
    return (
        same_key_kind(product.hs_code, code, width) and product.source_id != SOURCE_ID
    )


@dataclass(frozen=True)
class CountryProduct:
    source_id: str
    source_version: str
    grain: str
    hs_revision: str
    hs_detail: str
    year: int
    country_code: str
    product_code: str
    finished_measure: str | None
    measure_unit: str
    measure_status: str
    member_sha256: str


@dataclass(frozen=True)
class CountryPartnerProduct:
    source_id: str
    source_version: str
    grain: str
    hs_revision: str
    hs_detail: str
    year: int
    reporter_code: str
    partner_code: str
    product_code: str
    finished_measure: str | None
    measure_unit: str
    measure_status: str
    member_sha256: str


@dataclass(frozen=True)
class Country:
    source_id: str
    source_version: str
    grain: str
    country_code: str
    source_name: str


@dataclass(frozen=True)
class Product:
    source_id: str
    source_version: str
    grain: str
    hs_revision: str
    product_code: str
    source_description: str


@dataclass(frozen=True)
class Release:
    country_product_year: tuple[CountryProduct, ...]
    cpy_country: tuple[Country, ...]
    cpy_product: tuple[Product, ...]
    country_partner_product_year: tuple[CountryPartnerProduct, ...]
    cppy_country: tuple[Country, ...]
    cppy_product: tuple[Product, ...]
    source_registry: dict[str, object]
    fact_lineage: tuple[dict[str, object], ...]
    manifest: dict[str, object]


def _lines(directory: Path, digest: str) -> list[dict[str, object]]:
    require(digest_ok(digest), "output_hash")
    output = directory / f"{digest}.jsonl"
    require(file_hash(output) == digest, "output_hash")
    return [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()
    ]


def read_selected(cache: Path, selected: str) -> Release:
    """Revalidate both finished archives and every output before returning rows."""
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
        require(manifest.get("finished_only") is True, "rebuild_refused")
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
        try:
            parsed_clock = datetime.strptime(retrieved, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise AtlasError("retrieval_date") from None
        require(
            parsed_clock.strftime("%Y-%m-%dT%H:%M:%SZ") == retrieved,
            "retrieval_date",
        )
        archives = manifest["archives"]
        require(
            isinstance(archives, dict) and set(archives) == set(FINISHED),
            "archive_hash",
        )
        paths: dict[str, Path] = {}
        for grain in FINISHED:
            item = archives[grain]
            digest = item["sha256"]
            require(digest_ok(digest), "archive_hash")
            archive = directory / f"{digest}.zip"
            require(file_hash(archive) == digest, "archive_hash")
            require(archive.stat().st_size == item["bytes"], "archive_bytes")
            download = next(item for item in config.downloads if item.grain == grain)
            require(
                not download.publisher_sha256 or download.publisher_sha256 == digest,
                "archive_checksum",
            )
            require(
                item["host"] in {host_of(url) for url in config.reviewed_urls},
                "source_chain",
            )
            paths[grain] = archive
        primary = archives[FINISHED[0]]["sha256"]
        require(receipt["sha256"] == primary, "archive_hash")
        require(
            receipt["publisher"] == config.publisher
            and receipt["landing_url"] == config.page
            and receipt["licence_basis"] == entry.licence_basis
            and receipt["terms_read_on"] == entry.terms_read_on
            and receipt["commit_allowed"] is False,
            "source_chain",
        )
        require(
            receipt["terms_sha256"] is None or digest_ok(receipt["terms_sha256"]),
            "terms_fingerprint",
        )
        final_host = archives[FINISHED[0]]["host"]
        expected = sidecar_for(
            entry,
            digest=primary,
            nbytes=archives[FINISHED[0]]["bytes"],
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
            parsed = parse_archives(paths, config, Path(temporary))
            for key in parsed:
                require(parsed[key] == manifest[key], "manifest_content")
        outputs = manifest["outputs"]
        loaded = [_lines(directory, outputs[table]["sha256"]) for table in TABLES]
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
            tuple(CountryProduct(**cast(dict[str, Any], row)) for row in loaded[0]),
            tuple(Country(**cast(dict[str, Any], row)) for row in loaded[1]),
            tuple(Product(**cast(dict[str, Any], row)) for row in loaded[2]),
            tuple(
                CountryPartnerProduct(**cast(dict[str, Any], row)) for row in loaded[3]
            ),
            tuple(Country(**cast(dict[str, Any], row)) for row in loaded[4]),
            tuple(Product(**cast(dict[str, Any], row)) for row in loaded[5]),
            registry,
            lineage,
            manifest,
        )
    except (OSError, ValueError, KeyError, TypeError, RegistryError):
        raise AtlasError("selected_manifest_invalid") from None
