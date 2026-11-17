"""Validate finished Atlas rows before Qatar selection. No measure is computed."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zlib
from collections.abc import Iterator
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from eii_custodian.publicdata.fetch.bounded import CHUNK_BYTES
from eii_custodian.publicdata.fetch.bounded import file_hash as shared_file_hash
from eii_custodian.publicdata.fetch.bounded import within as shared_within
from eii_custodian.publicdata.fetch.decimals import DecimalRefusal, read_measure

from .config import (
    COUNTRY_TABLES,
    GRAIN_TABLES,
    PRODUCT_TABLES,
    SOURCE_ID,
    AtlasError,
    Config,
    Download,
    Measure,
    Member,
    require,
)

HS_DETAIL = "configured revision only; no concordance inferred"


def file_hash(path: Path) -> str:
    return shared_file_hash(path)


def within(value: int, span: tuple[int, int], reason: str) -> None:
    require(shared_within(value, span), reason)


def _rows(zipped: ZipFile, member: Member) -> Iterator[dict[str, str]]:
    with zipped.open(member.name) as source:
        reader = csv.reader(
            io.TextIOWrapper(source, encoding="utf-8", newline=""), strict=True
        )
        require(next(reader, None) == list(member.header), "header")
        for fields in reader:
            require(len(fields) == len(member.columns), "row_schema")
            yield dict(
                zip(
                    (member.columns[name] for name in member.header),
                    fields,
                    strict=True,
                )
            )


def _measure(value: str, measure: Measure) -> tuple[str | None, str]:
    try:
        return read_measure(
            value,
            total_digits=measure.total_digits,
            fractional_digits=measure.fractional_digits,
            signed=measure.signed,
            missing=measure.missing,
        )
    except DecimalRefusal as exc:
        raise AtlasError(exc.reason) from None


def _year(value: str, config: Config) -> tuple[int, str]:
    require(re.fullmatch(r"[0-9]{4}", value) is not None, "year")
    year = int(value)
    require(str(year) == value, "year")
    inside = config.period_first <= year <= config.period_last
    if config.year_selection == "native":
        require(year <= config.period_last, "stale_period")
        require(inside, "year")
        return year, "keep"
    if not inside:
        return year, "exclude"
    return year, "keep"


def _inventory(
    zipped: ZipFile, download: Download
) -> tuple[list[dict[str, object]], dict[str, str]]:
    inventory = zipped.infolist()
    within(len(inventory), download.member_count, "member_count")
    require(
        len(inventory) == len(download.members)
        and {item.filename for item in inventory}
        == {member.name for member in download.members},
        "inventory",
    )
    receipts: list[dict[str, object]] = []
    hashes: dict[str, str] = {}
    for member in download.members:
        info = zipped.getinfo(member.name)
        within(info.file_size, member.bytes, "member_bytes")
        size = 0
        digest = hashlib.sha256()
        with zipped.open(info) as source:
            while chunk := source.read(CHUNK_BYTES):
                size += len(chunk)
                require(size <= member.bytes[1], "member_bytes")
                digest.update(chunk)
        within(size, member.bytes, "member_bytes")
        require(size == info.file_size, "member_bytes")
        checksum = digest.hexdigest()
        require(not member.sha256 or member.sha256 == checksum, "member_checksum")
        hashes[member.name] = checksum
        receipts.append(
            {
                "name": member.name,
                "sha256": checksum,
                "bytes": size,
                "header": list(member.header),
                "rows": 0,
            }
        )
    return receipts, hashes


def _parse_one(
    path: Path, download: Download, config: Config, output: Path
) -> dict[str, object]:
    within(path.stat().st_size, download.archive_bytes, "archive_bytes")
    grain = download.grain
    require(grain in GRAIN_TABLES, "rebuild_refused")
    measure = config.measures[0]
    require(measure.name == "finished_measure", "measure_fields")
    with ZipFile(path) as zipped:
        receipts, hashes = _inventory(zipped, download)
        countries: set[str] = set()
        products: set[str] = set()
        country_member = next(
            member for member in download.members if member.kind == "country"
        )
        product_member = next(
            member for member in download.members if member.kind == "product"
        )
        data_member = next(
            member for member in download.members if member.kind == grain
        )
        country_count = 0
        country_table = COUNTRY_TABLES[grain]
        with (output / f"{country_table}.jsonl").open("w", encoding="utf-8") as target:
            for row in _rows(zipped, country_member):
                key = row["country_code"]
                require(
                    len(key) == config.country_width and key not in countries,
                    "dictionary_key",
                )
                countries.add(key)
                require(bool(row["source_name"].strip()), "dictionary_description")
                target.write(
                    json.dumps(
                        {
                            "source_id": SOURCE_ID,
                            "source_version": config.source_version,
                            "grain": grain,
                            "country_code": key,
                            "source_name": row["source_name"],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                country_count += 1
                require(country_count <= country_member.rows[1], "dictionary_count")
        within(country_count, country_member.rows, "dictionary_count")
        next(item for item in receipts if item["name"] == country_member.name)[
            "rows"
        ] = country_count
        product_count = 0
        product_table = PRODUCT_TABLES[grain]
        with (output / f"{product_table}.jsonl").open("w", encoding="utf-8") as target:
            for row in _rows(zipped, product_member):
                key = row["product_code"]
                require(
                    len(key) == config.product_width and key not in products,
                    "dictionary_key",
                )
                products.add(key)
                require(row["hs_revision"] == config.hs_revision, "revision")
                require(
                    bool(row["source_description"].strip()), "dictionary_description"
                )
                target.write(
                    json.dumps(
                        {
                            "source_id": SOURCE_ID,
                            "source_version": config.source_version,
                            "grain": grain,
                            "hs_revision": row["hs_revision"],
                            "product_code": key,
                            "source_description": row["source_description"],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                product_count += 1
                require(product_count <= product_member.rows[1], "dictionary_count")
        within(product_count, product_member.rows, "dictionary_count")
        next(item for item in receipts if item["name"] == product_member.name)[
            "rows"
        ] = product_count
        require(config.qatar_key in countries, "qatar_key")
        raw = selected = 0
        seen: set[tuple[str, ...]] = set()
        by_year: dict[int, dict[str, object]] = {}
        excluded_years: dict[int, int] = {}
        data_table = GRAIN_TABLES[grain]
        with (output / f"{data_table}.jsonl").open("w", encoding="utf-8") as target:
            for row in _rows(zipped, data_member):
                year, disposition = _year(row["year"], config)
                require(row["hs_revision"] == config.hs_revision, "revision")
                product = row["product_code"]
                require(product in products, "product_key")
                country_code = reporter_code = partner_code = ""
                trade_key: tuple[str, ...]
                if grain == "country_product_year":
                    country_code = row["country_code"]
                    require(country_code in countries, "country_key")
                    trade_key = (row["year"], country_code, product)
                else:
                    reporter_code = row["reporter_code"]
                    partner_code = row["partner_code"]
                    require(
                        reporter_code in countries and partner_code in countries,
                        "country_key",
                    )
                    trade_key = (row["year"], reporter_code, partner_code, product)
                require(trade_key not in seen, "duplicate_trade_key")
                seen.add(trade_key)
                text, status = _measure(row["finished_measure"], measure)
                raw += 1
                require(
                    raw <= data_member.rows[1] and raw <= download.raw_rows[1],
                    "trade_count",
                )
                if disposition == "exclude":
                    excluded_years[year] = excluded_years.get(year, 0) + 1
                    continue
                bucket = by_year.setdefault(
                    year,
                    {
                        "year": year,
                        "raw": 0,
                        "selected": 0,
                        "partners": set(),
                        "products": set(),
                    },
                )
                bucket["raw"] = int(str(bucket["raw"])) + 1
                assert isinstance(bucket["products"], set)
                keep = (
                    country_code == config.qatar_key
                    if grain == "country_product_year"
                    else config.qatar_key in {reporter_code, partner_code}
                )
                if not keep:
                    continue
                record: dict[str, object] = {
                    "source_id": SOURCE_ID,
                    "source_version": config.source_version,
                    "grain": grain,
                    "hs_revision": config.hs_revision,
                    "hs_detail": HS_DETAIL,
                    "year": year,
                    "product_code": product,
                    "finished_measure": text,
                    "measure_unit": measure.unit,
                    "measure_status": status,
                    "member_sha256": hashes[data_member.name],
                }
                if grain == "country_product_year":
                    record["country_code"] = country_code
                else:
                    record["reporter_code"] = reporter_code
                    record["partner_code"] = partner_code
                target.write(json.dumps(record, sort_keys=True) + "\n")
                selected += 1
                bucket["selected"] = int(str(bucket["selected"])) + 1
                bucket["products"].add(product)
                if grain != "country_product_year":
                    assert isinstance(bucket["partners"], set)
                    bucket["partners"].add(
                        partner_code
                        if reporter_code == config.qatar_key
                        else reporter_code
                    )
        within(raw, data_member.rows, "trade_count")
        within(raw, download.raw_rows, "raw_count")
        require(config.period_last in by_year, "year_coverage")
        if config.year_selection == "native":
            require(
                sorted(by_year)
                == list(range(config.period_first, config.period_last + 1)),
                "year_coverage",
            )
        next(item for item in receipts if item["name"] == data_member.name)["rows"] = (
            raw
        )
        coverage = []
        for year in sorted(by_year):
            bucket = by_year[year]
            covered = bucket["products"]
            assert isinstance(covered, set)
            item: dict[str, object] = {
                "year": year,
                "raw": bucket["raw"],
                "selected": bucket["selected"],
                "products": sorted(covered),
                "missing_products": sorted(products - covered),
                "missing_cells": "absence is not zero",
                "hs_revision": config.hs_revision,
                "hs_detail": HS_DETAIL,
            }
            if grain != "country_product_year":
                partners = bucket["partners"]
                assert isinstance(partners, set)
                item["partners"] = sorted(partners)
                item["missing_partners"] = sorted(countries - partners)
            coverage.append(item)
        return {
            "members": receipts,
            "raw": raw,
            "selected": selected,
            "excluded": raw - selected,
            "coverage": coverage,
            "excluded_coverage": [
                {"year": year, "rows": excluded_years[year]}
                for year in sorted(excluded_years)
            ],
            "outputs": {
                country_table: {
                    "sha256": file_hash(output / f"{country_table}.jsonl"),
                    "rows": country_count,
                },
                product_table: {
                    "sha256": file_hash(output / f"{product_table}.jsonl"),
                    "rows": product_count,
                },
                data_table: {
                    "sha256": file_hash(output / f"{data_table}.jsonl"),
                    "rows": selected,
                },
            },
        }


def parse_archives(
    paths: dict[str, Path], config: Config, output: Path
) -> dict[str, object]:
    """Read the two finished archives. A rebuild grain is refused before a row is kept."""
    require(config.finished_only is True, "rebuild_refused")
    require(set(paths) == set(GRAIN_TABLES), "finished_grain")
    output.mkdir(parents=True, exist_ok=True)
    try:
        by_grain: dict[str, object] = {}
        outputs: dict[str, object] = {}
        raw = selected = 0
        for download in config.downloads:
            parsed = _parse_one(paths[download.grain], download, config, output)
            by_grain[download.grain] = {
                key: value for key, value in parsed.items() if key != "outputs"
            }
            grain_outputs = parsed["outputs"]
            assert isinstance(grain_outputs, dict)
            outputs.update(grain_outputs)
            raw += int(str(parsed["raw"]))
            selected += int(str(parsed["selected"]))
        within(raw, config.raw_rows, "raw_count")
        return {
            "by_grain": by_grain,
            "outputs": outputs,
            "raw": raw,
            "selected": selected,
            "excluded": raw - selected,
            "hs_revision": config.hs_revision,
            "hs_detail": HS_DETAIL,
            "publisher_mapping": config.publisher_mapping,
            "finished_only": True,
        }
    except (
        BadZipFile,
        zlib.error,
        UnicodeError,
        csv.Error,
        EOFError,
        RuntimeError,
        NotImplementedError,
    ):
        raise AtlasError("archive_integrity") from None
