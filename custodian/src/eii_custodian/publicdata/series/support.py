"""Typed non-portal support for PUB-67; never a substitute portal source chain."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.review.activity import (
    METHOD_VERSION,
    IsicClass,
    parse_isic_rows,
)
from eii_custodian.publicdata.review.cache_fixture import read_csv
from eii_custodian.publicdata.series.frame import frame_municipalities
from eii_custodian.publicdata.series.parse import Municipality, selected_body

SUPPORT_KEYS = ("cls_isic4", "bnd_hdx", "bnd_zone_2020")
_REVIEW = Path(__file__).resolve().parents[4] / "publicdata/review"
REVIEW_FILES = ("municipality_names.csv", "municipality_aliases.json")


class SupportSource(TypedDict):
    key: str
    source_id: str
    dataset: str
    publisher: str
    licence_id: str
    licence_basis: str
    retrieved_utc: str
    sha256: str
    fetch_url: str


class FrameSupport(TypedDict):
    output: str
    sha256: str
    method: str
    upstream: list[SupportSource]
    review_sha256: dict[str, str]


class SupportingProvenance(TypedDict):
    schema: str
    classifier_version: str
    classification: SupportSource
    frame: FrameSupport


def _source(entry: Entry, receipt: Mapping[str, object]) -> SupportSource:
    if receipt.get("title_en") != entry.title_en:
        raise ValueError("invalid supporting provenance dataset")
    return SupportSource(
        key=entry.key,
        source_id=entry.source_id,
        dataset=str(receipt["title_en"]),
        publisher=str(receipt["publisher"]),
        licence_id=entry.licence_id,
        licence_basis=entry.licence_basis,
        retrieved_utc=str(receipt["retrieved_utc"]),
        sha256=str(receipt["sha256"]),
        fetch_url=str(receipt["fetch_url"]),
    )


def load_support(
    cache: Path,
    entries: Sequence[Entry],
    selected: Mapping[str, str],
    municipalities: Sequence[Municipality],
) -> tuple[tuple[IsicClass, ...], SupportingProvenance]:
    """Require exact same-build supporting selections, not cache discovery."""
    if set(selected) != set(SUPPORT_KEYS):
        raise ValueError("supporting provenance selections required")
    sources = {}
    bodies = {}
    for key in SUPPORT_KEYS:
        matched = [entry for entry in entries if entry.key == key]
        if len(matched) != 1:
            raise ValueError("supporting provenance registry identity")
        entry = matched[0]
        body, receipt = selected_body(cache, entry, selected[key])
        bodies[key] = body
        sources[key] = _source(entry, receipt)
    classes = parse_isic_rows(read_csv(bodies["cls_isic4"])).classes
    if not classes:
        raise ValueError("supporting provenance has no ISIC classes")
    frame_output = cache / "frame_s2_t02/municipalities.json"
    payload = json.loads(frame_output.read_text())
    if not isinstance(payload, dict) or payload.get("upstream_sha256") != {
        key: selected[key] for key in SUPPORT_KEYS[1:]
    }:
        raise ValueError("supporting provenance frame inputs differ")
    if tuple(municipalities) != frame_municipalities(cache):
        raise ValueError("supporting provenance frame differs")
    output = "frame_s2_t02/municipalities.json"
    support = SupportingProvenance(
        schema="pub67-support.v1",
        classifier_version=METHOD_VERSION,
        classification=sources["cls_isic4"],
        frame=FrameSupport(
            output=output,
            sha256=sha256_hex((cache / output).read_bytes()),
            method="frame.v1",
            upstream=[sources[key] for key in SUPPORT_KEYS[1:]],
            review_sha256={
                name: sha256_hex((_REVIEW / name).read_bytes()) for name in REVIEW_FILES
            },
        ),
    )
    validate_support(support)
    return classes, support


def validate_support(value: object) -> None:
    """Closed runtime admission for document 03's PUB-67 supporting block."""

    def refuse() -> None:
        raise ValueError("invalid supporting provenance")

    def fields(row: object, keys: set[str]) -> bool:
        return isinstance(row, dict) and set(row) == keys

    def digest(value: object) -> bool:
        return (
            isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None
        )

    def source(row: object, key: str) -> None:
        if not fields(row, set(SupportSource.__annotations__)):
            refuse()
        assert isinstance(row, dict)
        if any(not isinstance(v, str) or not v.strip() for v in row.values()):
            refuse()
        try:
            stamp = row["retrieved_utc"]
            if (
                re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", stamp
                )
                is None
            ):
                refuse()
            datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            refuse()
        if row["key"] != key or row["source_id"] != key or not digest(row["sha256"]):
            refuse()

    if not fields(value, set(SupportingProvenance.__annotations__)):
        refuse()
    assert isinstance(value, dict)
    if (
        value["schema"] != "pub67-support.v1"
        or value["classifier_version"] != METHOD_VERSION
    ):
        refuse()
    source(value["classification"], "cls_isic4")
    frame = value["frame"]
    if not fields(frame, set(FrameSupport.__annotations__)):
        refuse()
    assert isinstance(frame, dict)
    if (
        frame["output"] != "frame_s2_t02/municipalities.json"
        or frame["method"] != "frame.v1"
        or not digest(frame["sha256"])
    ):
        refuse()
    upstream = frame["upstream"]
    if not isinstance(upstream, list) or len(upstream) != len(SUPPORT_KEYS[1:]):
        refuse()
    for row, key in zip(upstream, SUPPORT_KEYS[1:], strict=True):
        source(row, key)
    reviews = frame["review_sha256"]
    if not fields(reviews, set(REVIEW_FILES)):
        refuse()
    if not all(digest(item) for item in reviews.values()):
        refuse()
