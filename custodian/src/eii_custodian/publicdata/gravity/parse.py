"""Validate every Gravity row before keeping either direction of the target."""

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
from eii_custodian.publicdata.fetch.decimals import (
    DecimalRefusal,
    looks_numeric,
    read_measure,
)

from .config import (
    SOURCE_ID,
    TABLES,
    Config,
    GravityError,
    Measure,
    Member,
    require,
)

HS_DETAIL = "recorded marker; no revision inferred"


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
        raise GravityError(exc.reason) from None


def _flag(value: str, config: Config) -> str | None:
    if value in config.flag_missing:
        return None
    if value in config.flag_tokens:
        return value
    require(not looks_numeric(value), "flag_token")
    raise GravityError("missing_undeclared")


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


def parse_archive(path: Path, config: Config, output: Path) -> dict[str, object]:
    """v1 transform. Publisher columns stay pending; fixture fields are not relabelled."""
    within(path.stat().st_size, config.archive_bytes, "archive_bytes")
    output.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(path) as zipped:
            inventory = zipped.infolist()
            within(len(inventory), config.member_count, "member_count")
            require(
                len(inventory) == len(config.members)
                and {item.filename for item in inventory}
                == {member.name for member in config.members},
                "inventory",
            )
            receipts: list[dict[str, object]] = []
            hashes: dict[str, str] = {}
            for member in config.members:
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
            country_member = next(
                member for member in config.members if member.kind == "country"
            )
            count = 0
            with (output / f"{TABLES[1]}.jsonl").open("w", encoding="utf-8") as target:
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
                                "country_code": key,
                                "source_name": row["source_name"],
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    count += 1
                    require(count <= country_member.rows[1], "dictionary_count")
            within(count, country_member.rows, "dictionary_count")
            next(item for item in receipts if item["name"] == country_member.name)[
                "rows"
            ] = count
            outputs: dict[str, object] = {
                TABLES[1]: {
                    "sha256": file_hash(output / f"{TABLES[1]}.jsonl"),
                    "rows": count,
                }
            }
            require(config.qatar_key in countries, "qatar_key")
            measures = {measure.name: measure for measure in config.measures}
            bilateral = next(
                member for member in config.members if member.kind == "bilateral"
            )
            raw = selected = 0
            seen: set[tuple[str, str, str]] = set()
            by_year: dict[int, dict[str, object]] = {}
            excluded_years: dict[int, int] = {}
            with (output / f"{TABLES[0]}.jsonl").open("w", encoding="utf-8") as target:
                for row in _rows(zipped, bilateral):
                    year, disposition = _year(row["year"], config)
                    origin, destination = row["origin_code"], row["destination_code"]
                    require(
                        origin in countries and destination in countries, "country_key"
                    )
                    trade_key = (row["year"], origin, destination)
                    require(trade_key not in seen, "duplicate_trade_key")
                    seen.add(trade_key)
                    parsed = {
                        name: _measure(row[name], measures[name]) for name in measures
                    }
                    flags = {
                        name: _flag(row[name], config)
                        for name in (
                            "contig",
                            "common_language",
                            "colonial_link",
                            "trade_agreement",
                        )
                    }
                    raw += 1
                    require(
                        raw <= bilateral.rows[1] and raw <= config.raw_rows[1],
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
                        },
                    )
                    assert isinstance(bucket["partners"], set)
                    bucket["raw"] = int(str(bucket["raw"])) + 1
                    if origin != config.qatar_key and destination != config.qatar_key:
                        continue
                    record: dict[str, object] = {
                        "source_version": config.source_version,
                        "hs_revision": config.hs_revision,
                        "hs_detail": HS_DETAIL,
                        "year": year,
                        "origin_code": origin,
                        "destination_code": destination,
                        "source_id": SOURCE_ID,
                        "member_sha256": hashes[bilateral.name],
                    }
                    for name, (text, status) in parsed.items():
                        record[name] = text
                        record[f"{name}_unit"] = measures[name].unit
                        record[f"{name}_status"] = status
                    record.update(flags)
                    target.write(json.dumps(record, sort_keys=True) + "\n")
                    selected += 1
                    bucket["selected"] = int(str(bucket["selected"])) + 1
                    bucket["partners"].add(
                        destination if origin == config.qatar_key else origin
                    )
            within(raw, bilateral.rows, "trade_count")
            within(raw, config.raw_rows, "raw_count")
            require(config.period_last in by_year, "year_coverage")
            if config.year_selection == "native":
                require(
                    sorted(by_year)
                    == list(range(config.period_first, config.period_last + 1)),
                    "year_coverage",
                )
            next(item for item in receipts if item["name"] == bilateral.name)[
                "rows"
            ] = raw
            outputs[TABLES[0]] = {
                "sha256": file_hash(output / f"{TABLES[0]}.jsonl"),
                "rows": selected,
            }
            coverage = []
            for year in sorted(by_year):
                bucket = by_year[year]
                partners = bucket["partners"]
                assert isinstance(partners, set)
                coverage.append(
                    {
                        "year": year,
                        "raw": bucket["raw"],
                        "selected": bucket["selected"],
                        "partners": sorted(partners),
                        "missing_partners": sorted(countries - partners),
                        "missing_cells": "absence is not zero",
                        "hs_revision": config.hs_revision,
                        "hs_detail": HS_DETAIL,
                    }
                )
            return {
                "members": receipts,
                "outputs": outputs,
                "raw": raw,
                "selected": selected,
                "excluded": raw - selected,
                "coverage": coverage,
                "excluded_coverage": [
                    {"year": year, "rows": excluded_years[year]}
                    for year in sorted(excluded_years)
                ],
                "hs_revision": config.hs_revision,
                "hs_detail": HS_DETAIL,
                "publisher_mapping": config.publisher_mapping,
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
        raise GravityError("archive_integrity") from None
