"""The committed hand list of landmark heights and its citations."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from eii_core.calc.building_heights import height_value

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
    {"landmark_id", "building_id", "name_en", "height_m", "citation"}
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
    citation: LandmarkCitation


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


def _valid_sha256(text: str) -> bool:
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _registry_by_url() -> dict[str, Entry]:
    from eii_custodian.publicdata.fetch.registry import Entry, load_registry

    found: dict[str, Entry] = {}
    for entry in load_registry():
        if entry.url:
            found[entry.url] = entry
        if entry.landing_url:
            found[entry.landing_url] = entry
    return found


def _bind_citation_registry(row: LandmarkHeight) -> None:
    """Require the citation page to name a registry row with matching evidence."""
    by_url = _registry_by_url()
    entry = by_url.get(row.citation.page_url)
    if entry is None:
        raise HeightError("landmark_heights_citation")
    if entry.publisher != row.citation.publisher:
        raise HeightError("landmark_heights_citation")
    if entry.licence_basis != row.citation.licence_basis:
        raise HeightError("landmark_heights_citation")


def verify_landmark_receipts(
    cache: Path, landmarks: tuple[LandmarkHeight, ...]
) -> None:
    """Each cited page must name the digest of its cache receipt."""
    if not landmarks:
        return
    from eii_custodian.publicdata.fetch.receipts import cache_directory
    from eii_custodian.publicdata.fetch.registry import Entry

    by_url = _registry_by_url()
    for row in landmarks:
        entry = by_url.get(row.citation.page_url)
        if not isinstance(entry, Entry):
            raise HeightError("landmark_heights_citation")
        directory = cache_directory(cache, entry.key)
        digest = row.citation.page_sha256
        found = False
        for meta in directory.rglob("*.meta.json"):
            try:
                receipt = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if receipt.get("sha256") == digest:
                found = True
                break
        citation = directory / "citation.json"
        if not found and citation.is_file():
            try:
                receipt = json.loads(citation.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise HeightError("landmark_heights_citation") from None
            if receipt.get("sha256") == digest:
                found = True
        if not found:
            raise HeightError("landmark_heights_citation")


def load_landmark_heights(path: Path | None = None) -> tuple[LandmarkHeight, ...]:
    """Read the committed hand list; every refusal is named."""
    target = path if path is not None else LANDMARK_HEIGHTS_PATH
    try:
        document = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise HeightError("landmark_heights") from None
    if not isinstance(document, dict) or document.get("version") != 1:
        raise HeightError("landmark_heights")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise HeightError("landmark_heights")
    pending = document.get("pending", "")
    if not entries:
        if pending != _PENDING:
            raise HeightError("landmark_heights")
        return ()
    if pending:
        raise HeightError("landmark_heights_entry")
    seen_buildings: set[str] = set()
    seen_landmarks: set[str] = set()
    rows: list[LandmarkHeight] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise HeightError("landmark_heights_entry")
        citation = entry["citation"]
        if not isinstance(citation, dict) or set(citation) != _CITATION_KEYS:
            raise HeightError("landmark_heights_citation")
        for field in ("landmark_id", "building_id", "name_en"):
            text = entry[field]
            if not isinstance(text, str) or not text.strip():
                raise HeightError("landmark_heights_entry")
        if entry["landmark_id"] in seen_landmarks:
            raise HeightError("landmark_heights_duplicate")
        if entry["building_id"] in seen_buildings:
            raise HeightError("landmark_heights_duplicate")
        seen_landmarks.add(entry["landmark_id"])
        seen_buildings.add(entry["building_id"])
        for field in _CITATION_KEYS:
            text = citation[field]
            if not isinstance(text, str) or not text.strip():
                raise HeightError("landmark_heights_citation")
        if not _valid_sha256(citation["page_sha256"]):
            raise HeightError("landmark_heights_citation")
        height_text = entry["height_m"]
        if not isinstance(height_text, str):
            raise HeightError("landmark_heights_height")
        try:
            height = Decimal(height_text)
        except ArithmeticError:
            raise HeightError("landmark_heights_height") from None
        if height_value(height) is None:
            raise HeightError("landmark_heights_height")
        rows.append(
            LandmarkHeight(
                landmark_id=entry["landmark_id"],
                building_id=entry["building_id"],
                name_en=entry["name_en"],
                height_m=height,
                citation=LandmarkCitation(
                    page_url=citation["page_url"],
                    publisher=citation["publisher"],
                    retrieved_on=citation["retrieved_on"],
                    licence_basis=citation["licence_basis"],
                    page_sha256=citation["page_sha256"],
                    height_excerpt=citation["height_excerpt"],
                ),
            )
        )
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
    return tuple(rows)


def apply_landmark_heights(
    buildings: list[Building],
    landmarks: tuple[LandmarkHeight, ...],
) -> tuple[list[Building], list[dict[str, object]]]:
    """Attach each landmark height where its building_id matches."""
    by_id = {row.building_id: row for row in landmarks}
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
        citations.append(
            {
                "landmark_id": row.landmark_id,
                "building_id": row.building_id,
                "name_en": row.name_en,
                "height_m": str(row.height_m),
                "citation": {
                    "page_url": row.citation.page_url,
                    "publisher": row.citation.publisher,
                    "retrieved_on": row.citation.retrieved_on,
                    "licence_basis": row.citation.licence_basis,
                    "page_sha256": row.citation.page_sha256,
                    "height_excerpt": row.citation.height_excerpt,
                },
            }
        )
    return out, citations


__all__ = [
    "LANDMARK_FIXTURE_PATH",
    "LANDMARK_HEIGHTS_PATH",
    "LandmarkCitation",
    "LandmarkHeight",
    "apply_landmark_heights",
    "load_landmark_heights",
    "verify_landmark_receipts",
]
