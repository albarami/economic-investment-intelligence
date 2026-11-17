"""Validate every archive row before selecting either direction of the target."""

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

from eii_custodian.publicdata.fetch.bounded import file_hash as shared_file_hash
from eii_custodian.publicdata.fetch.bounded import within as shared_within
from eii_custodian.publicdata.fetch.decimals import DecimalRefusal, exact_decimal

from .config import SCHEMAS, TABLES, BaciError, Config, Member, require


def decimal_text(value: str, config: Config) -> str:
    """Unsigned fixed-point ASCII; count all written digits, including zeros."""
    try:
        return exact_decimal(
            value,
            total_digits=config.total_digits,
            fractional_digits=config.fractional_digits,
            signed=False,
        )
    except DecimalRefusal as exc:
        raise BaciError(exc.reason) from None


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


def parse_archive(path: Path, config: Config, output: Path) -> dict[str, object]:
    """v1 deterministic transform; outputs go only to caller-owned staging."""
    require(all(m.kind in SCHEMAS for m in config.members), "member_kind")
    require(
        sum(m.kind == "country" for m in config.members) == 1
        and sum(m.kind == "product" for m in config.members) == 1,
        "dictionaries",
    )
    within(path.stat().st_size, config.archive_bytes, "archive_bytes")
    output.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(path) as zipped:
            inventory = zipped.infolist()
            require(
                len(inventory) == len(config.members)
                and {m.filename for m in inventory} == {m.name for m in config.members},
                "inventory",
            )
            require(len({m.filename for m in inventory}) == len(inventory), "inventory")
            receipts: list[dict[str, object]] = []
            hashes: dict[str, str] = {}
            for member in config.members:
                info = zipped.getinfo(member.name)
                within(info.file_size, member.bytes, "member_bytes")
                size = 0
                digest = hashlib.sha256()
                with zipped.open(info) as source:
                    while chunk := source.read(65536):
                        size += len(chunk)
                        require(size <= member.bytes[1], "member_bytes")
                        digest.update(chunk)
                within(size, member.bytes, "member_bytes")
                require(size == info.file_size, "member_bytes")
                checksum = digest.hexdigest()
                require(
                    not member.sha256 or member.sha256 == checksum, "member_checksum"
                )
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
            countries: set[str] = set()
            products: set[str] = set()
            outputs: dict[str, object] = {}
            for kind, keys, width, key_field, table in (
                ("country", countries, config.country_width, "country_code", TABLES[1]),
                ("product", products, config.product_width, "hs_code", TABLES[2]),
            ):
                member = next(m for m in config.members if m.kind == kind)
                count = 0
                with (output / f"{table}.jsonl").open("w", encoding="utf-8") as target:
                    for row in _rows(zipped, member):
                        key = row[key_field]
                        require(len(key) == width and key not in keys, "dictionary_key")
                        keys.add(key)
                        require(
                            bool(
                                row[
                                    "source_name"
                                    if kind == "country"
                                    else "source_description"
                                ].strip()
                            ),
                            "dictionary_description",
                        )
                        record: dict[str, object] = dict(row)
                        if kind == "country":
                            require(
                                not row["iso3"]
                                or re.fullmatch(r"[A-Z]{3}", row["iso3"]) is not None,
                                "iso3",
                            )
                            record["iso3"] = row["iso3"] or None
                        else:
                            require(
                                row["hs_revision"] == config.hs_revision, "revision"
                            )
                        record.update(
                            source_id="cepii_baci", source_version=config.source_version
                        )
                        target.write(json.dumps(record, sort_keys=True) + "\n")
                        count += 1
                        require(count <= member.rows[1], "dictionary_count")
                within(count, member.rows, "dictionary_count")
                next(r for r in receipts if r["name"] == member.name)["rows"] = count
                outputs[table] = {
                    "sha256": file_hash(output / f"{table}.jsonl"),
                    "rows": count,
                }
            require(config.qatar_key in countries, "qatar_key")
            raw = selected = 0
            coverage: list[dict[str, object]] = []
            with (output / f"{TABLES[0]}.jsonl").open("w", encoding="utf-8") as target:
                for member in config.members:
                    if member.kind != "trade":
                        continue
                    count = kept = 0
                    seen: set[tuple[str, ...]] = set()
                    partners: set[str] = set()
                    covered_products: set[str] = set()
                    for row in _rows(zipped, member):
                        require(row["year"] == str(member.year), "year")
                        require(row["hs_revision"] == config.hs_revision, "revision")
                        exporter, importer, product = (
                            row["exporter_code"],
                            row["importer_code"],
                            row["hs_code"],
                        )
                        require(
                            exporter in countries and importer in countries,
                            "country_key",
                        )
                        require(product in products, "product_key")
                        trade_key = (exporter, importer, product)
                        require(trade_key not in seen, "duplicate_trade_key")
                        seen.add(trade_key)
                        value = decimal_text(row["value"], config)
                        quantity = (
                            None
                            if row["quantity"] in config.missing_quantity
                            else decimal_text(row["quantity"], config)
                        )
                        count += 1
                        raw += 1
                        require(
                            count <= member.rows[1] and raw <= config.raw_rows[1],
                            "trade_count",
                        )
                        if (
                            exporter != config.qatar_key
                            and importer != config.qatar_key
                        ):
                            continue
                        record = dict(row)
                        result: dict[str, object] = dict(record)
                        result.update(
                            year=member.year,
                            value=value,
                            quantity=quantity,
                            source_id="cepii_baci",
                            source_version=config.source_version,
                            value_unit=config.value_unit,
                            quantity_unit=config.quantity_unit,
                            currency=config.currency,
                            valuation_basis=config.valuation_basis,
                            quantity_status="source_missing"
                            if quantity is None
                            else "present",
                            member_sha256=hashes[member.name],
                        )
                        target.write(json.dumps(result, sort_keys=True) + "\n")
                        selected += 1
                        kept += 1
                        partners.add(
                            importer if exporter == config.qatar_key else exporter
                        )
                        covered_products.add(product)
                    within(count, member.rows, "trade_count")
                    next(r for r in receipts if r["name"] == member.name)["rows"] = (
                        count
                    )
                    coverage.append(
                        {
                            "year": member.year,
                            "raw": count,
                            "selected": kept,
                            "partners": sorted(partners),
                            "products": sorted(covered_products),
                            "missing_partners": sorted(countries - partners),
                            "missing_products": sorted(products - covered_products),
                            "missing_cells": "absence is not zero",
                        }
                    )
            within(raw, config.raw_rows, "raw_count")
            outputs[TABLES[0]] = {
                "sha256": file_hash(output / f"{TABLES[0]}.jsonl"),
                "rows": selected,
            }
            return {
                "members": receipts,
                "outputs": outputs,
                "raw": raw,
                "selected": selected,
                "excluded": raw - selected,
                "coverage": coverage,
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
        raise BaciError("archive_integrity") from None
