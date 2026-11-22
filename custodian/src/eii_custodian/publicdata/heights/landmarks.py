"""The reviewed cache hand list of landmark heights and its citations."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from yaml.nodes import MappingNode

from eii_core.calc.building_heights import height_value
from eii_custodian.publicdata.fetch.terms_text import visible_text

from .landmark_select import KINDS, UNITS, excerpt_matches
from .model import Building, HeightError

if TYPE_CHECKING:
    from eii_custodian.publicdata.fetch.registry import Entry

_PENDING = "basemap_building_ids_unconfirmed"
_CITATION_KEYS = frozenset(
    {
        "page_url",
        "publisher",
        "retrieved_on",
        "licence_basis",
        "page_sha256",
        "height_excerpt",
    }
)
_ENTRY_KEYS = frozenset(
    {"landmark_id", "building_id", "name_en", "height_m", "height_kind", "citation"}
)


@dataclass(frozen=True)
class LandmarkCitation:
    """One height's public citation chain."""

    page_url: str
    publisher: str
    retrieved_on: str
    licence_basis: str
    page_sha256: str
    height_excerpt: str


@dataclass(frozen=True)
class LandmarkHeight:
    """One landmark row of the hand list."""

    landmark_id: str
    building_id: str
    name_en: str
    height_m: Decimal
    height_kind: str
    citation: LandmarkCitation


@dataclass(frozen=True)
class LandmarkRecord:
    """Keep the validated rows, readiness and bytes in one immutable read."""

    rows: tuple[LandmarkHeight, ...]
    pending: str
    body: bytes


LANDMARK_HEIGHTS_PATH = (
    Path(__file__).resolve().parents[4]
    / "publicdata"
    / "review"
    / "landmark_heights.yaml"
)
LANDMARK_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "heights"
    / "landmark_hand_list.yaml"
)


def landmark_heights_path(cache: Path) -> Path:
    """One local record; the committed empty format sample supplies pending only."""
    local = cache / "review" / "landmark_heights.yaml"
    if (
        local.is_symlink()
        or local.parent.is_symlink()
        or not local.resolve().is_relative_to(cache.resolve())
    ):
        raise HeightError("landmark_heights", "cache_path_refused")
    return local if local.is_file() else LANDMARK_HEIGHTS_PATH


def _valid_sha256(text: str) -> bool:
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _registry_by_url() -> dict[str, Entry]:
    from eii_custodian.publicdata.fetch.registry import load_registry

    found: dict[str, Entry] = {}
    for entry in load_registry():
        if entry.url:
            found[entry.url] = entry
        if entry.landing_url:
            found[entry.landing_url] = entry
    return found


def _refuse_citation(detail: str) -> HeightError:
    return HeightError("landmark_heights_citation", detail)


def _registry_entry(row: LandmarkHeight) -> Entry:
    """The registry row the citation names, with matching publisher and licence."""
    entry = _registry_by_url().get(row.citation.page_url)
    if entry is None:
        raise _refuse_citation("registry_row")
    if entry.publisher != row.citation.publisher:
        raise _refuse_citation("registry_publisher")
    if entry.licence_basis != row.citation.licence_basis:
        raise _refuse_citation("registry_licence")
    return entry


def _bind_citation_registry(row: LandmarkHeight) -> None:
    """Require the citation page to name a registry row with matching evidence."""
    _registry_entry(row)


def _page_directory(cache: Path, entry: Entry) -> Path:
    """A public page's bytes are its raw snapshot; a file's are the row's own."""
    from eii_custodian.publicdata.fetch.receipts import cache_directory

    directory = cache_directory(cache, entry.key)
    if entry.kind == "public_page":
        return directory / ("inputs/input-0" if not entry.columns else "raw")
    return directory


def verify_landmark_receipts(
    cache: Path, landmarks: tuple[LandmarkHeight, ...]
) -> None:
    """Resolve each cited page through its verified snapshot and receipt.

    The snapshot verifier rechecks the index, the receipt's own hash and the
    page bytes; the receipt must then name the registry row's source and key,
    the cited URL, publisher, licence basis, retrieval day and page hash.
    """
    from eii_custodian.publicdata.fetch.snapshots import (
        SnapshotError,
        read_snapshot,
        utc,
    )

    for row in landmarks:
        entry = _registry_entry(row)
        citation = row.citation
        try:
            snapshot = read_snapshot(
                _page_directory(cache, entry), citation.page_sha256
            )
            retrieved_day = utc(snapshot.sidecar["retrieved_utc"]).date().isoformat()
        except SnapshotError:
            raise _refuse_citation("page_snapshot") from None
        side = snapshot.sidecar
        if snapshot.sha256 != citation.page_sha256:
            raise _refuse_citation("receipt_hash")
        if side.get("source_id") != entry.source_id or side.get("key") != entry.key:
            raise _refuse_citation("receipt_source")
        if citation.page_url not in {side.get("fetch_url"), side.get("landing_url")}:
            raise _refuse_citation("receipt_url")
        if side.get("publisher") != citation.publisher:
            raise _refuse_citation("receipt_publisher")
        if side.get("licence_basis") != citation.licence_basis:
            raise _refuse_citation("receipt_licence")
        if retrieved_day != citation.retrieved_on:
            raise _refuse_citation("receipt_date")
        _verify_excerpt(row, snapshot.body)


def _normalise_excerpt(text: str) -> str:
    return re.sub(r"[ \t\r\n\f\v]+", " ", text).strip()


def _verify_excerpt(row: LandmarkHeight, body: bytes) -> None:
    excerpt = row.citation.height_excerpt
    if _normalise_excerpt(excerpt) not in _normalise_excerpt(visible_text(body)):
        raise _refuse_citation("excerpt_absent")
    if (
        not any(
            excerpt_matches(
                {
                    "height_m": str(row.height_m),
                    "unit_as_written": unit,
                    "height_excerpt": excerpt,
                }
            )
            for unit in UNITS
        )
        or re.search(r"\b" + row.height_kind + r"\b", excerpt, re.IGNORECASE) is None
    ):
        raise _refuse_citation("height_excerpt_mismatch")


class _LandmarkLoader(yaml.CSafeLoader):
    """A repeated YAML field cannot silently replace a cited value."""

    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[Any, Any]:
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise HeightError("landmark_heights", "duplicate_key")
        return mapping


def load_landmark_record(path: Path | None = None) -> LandmarkRecord:
    """Read the single reviewed hand list; every refusal is named."""
    target = path if path is not None else LANDMARK_HEIGHTS_PATH
    try:
        body = target.read_bytes()
        document = yaml.load(body, Loader=_LandmarkLoader)
    except (OSError, yaml.YAMLError):
        raise HeightError("landmark_heights", "document") from None
    if not isinstance(document, dict):
        raise HeightError("landmark_heights", "document")
    if document.get("version") != 1:
        raise HeightError("landmark_heights", "version")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise HeightError("landmark_heights", "entries")
    pending = document.get("pending", "")
    if not entries:
        if pending not in ("", _PENDING, "landmark_list_empty"):
            raise HeightError("landmark_heights", "pending")
        return LandmarkRecord((), pending, body)
    if pending:
        raise HeightError("landmark_heights_entry", "pending")
    seen_buildings: set[str] = set()
    seen_landmarks: set[str] = set()
    rows: list[LandmarkHeight] = []
    for entry in entries:
        loaded = _landmark_entry(entry)
        if loaded.landmark_id in seen_landmarks:
            raise HeightError("landmark_heights_duplicate", "landmark_id")
        if loaded.building_id in seen_buildings:
            raise HeightError("landmark_heights_duplicate", "building_id")
        seen_landmarks.add(loaded.landmark_id)
        seen_buildings.add(loaded.building_id)
        rows.append(loaded)
    if rows:
        try:
            skip_registry = target.resolve().is_relative_to(
                LANDMARK_FIXTURE_PATH.parent.resolve()
            )
        except (OSError, ValueError):
            skip_registry = False
        if not skip_registry:
            for loaded in rows:
                _bind_citation_registry(loaded)
    return LandmarkRecord(tuple(rows), pending, body)


def load_landmark_heights(path: Path | None = None) -> tuple[LandmarkHeight, ...]:
    """Compatibility row view of the single validated cache record."""
    return load_landmark_record(path).rows


def _landmark_entry(entry: object) -> LandmarkHeight:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
        raise HeightError("landmark_heights_entry", "keys")
    if not isinstance(entry["height_kind"], str) or entry["height_kind"] not in KINDS:
        raise HeightError("landmark_heights_entry", "height_kind")
    citation = entry["citation"]
    if not isinstance(citation, dict) or set(citation) != _CITATION_KEYS:
        raise _refuse_citation("citation_keys")
    for field in ("landmark_id", "building_id", "name_en"):
        text = entry[field]
        if not isinstance(text, str) or not text.strip():
            raise HeightError("landmark_heights_entry", "field")
    for field in _CITATION_KEYS:
        text = citation[field]
        if not isinstance(text, str) or not text.strip():
            raise _refuse_citation("citation_field")
    if not _valid_sha256(citation["page_sha256"]):
        raise _refuse_citation("page_sha256")
    height_text = entry["height_m"]
    if not isinstance(height_text, str):
        raise HeightError("landmark_heights_height", "text")
    try:
        height = Decimal(height_text)
    except ArithmeticError:
        raise HeightError("landmark_heights_height", "text") from None
    if height_value(height) is None:
        raise HeightError("landmark_heights_height", "unusable")
    return LandmarkHeight(
        landmark_id=entry["landmark_id"],
        building_id=entry["building_id"],
        name_en=entry["name_en"],
        height_m=height,
        height_kind=entry["height_kind"],
        citation=LandmarkCitation(
            page_url=citation["page_url"],
            publisher=citation["publisher"],
            retrieved_on=citation["retrieved_on"],
            licence_basis=citation["licence_basis"],
            page_sha256=citation["page_sha256"],
            height_excerpt=citation["height_excerpt"],
        ),
    )


def apply_landmark_heights(
    buildings: list[Building],
    landmarks: tuple[LandmarkHeight, ...],
) -> tuple[list[Building], list[dict[str, object]]]:
    """Attach each landmark height where its building_id matches."""
    by_id = {row.building_id: row for row in landmarks}
    building_ids = {building.building_id for building in buildings}
    for landmark in landmarks:
        if landmark.building_id not in building_ids:
            raise HeightError("landmark_building_absent", landmark.landmark_id)
    citations: list[dict[str, object]] = []
    out: list[Building] = []
    for building in buildings:
        row = by_id.get(building.building_id)
        if row is None:
            out.append(building)
            continue
        if building.recorded is not None:
            raise HeightError("landmark_height_conflict")
        out.append(replace(building, recorded=row.height_m))
        citations.append(landmark_record(row))
    return out, citations


def landmark_record(row: LandmarkHeight) -> dict[str, object]:
    """The single serializer shared by the tie and the height manifest."""
    return {
        "landmark_id": row.landmark_id,
        "building_id": row.building_id,
        "name_en": row.name_en,
        "height_m": str(row.height_m),
        "height_kind": row.height_kind,
        "citation": {
            "page_url": row.citation.page_url,
            "publisher": row.citation.publisher,
            "retrieved_on": row.citation.retrieved_on,
            "licence_basis": row.citation.licence_basis,
            "page_sha256": row.citation.page_sha256,
            "height_excerpt": row.citation.height_excerpt,
        },
    }


__all__ = [
    "LANDMARK_FIXTURE_PATH",
    "LANDMARK_HEIGHTS_PATH",
    "LandmarkCitation",
    "LandmarkHeight",
    "LandmarkRecord",
    "apply_landmark_heights",
    "landmark_heights_path",
    "landmark_record",
    "load_landmark_heights",
    "load_landmark_record",
    "verify_landmark_receipts",
]
