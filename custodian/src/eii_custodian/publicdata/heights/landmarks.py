"""The committed hand list of landmark heights and its citations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

import yaml

from .model import Building, HeightError


@dataclass(frozen=True)
class LandmarkCitation:
    """One height's public citation chain."""

    page_url: str
    publisher: str
    retrieved_on: str


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
_CITATION_KEYS = frozenset({"page_url", "publisher", "retrieved_on"})
_ENTRY_KEYS = frozenset(
    {"landmark_id", "building_id", "name_en", "height_m", "citation"}
)


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
    if not isinstance(entries, list) or not entries:
        raise HeightError("landmark_heights")
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
        for field in _CITATION_KEYS:
            text = citation[field]
            if not isinstance(text, str) or not text.strip():
                raise HeightError("landmark_heights_citation")
        height_text = entry["height_m"]
        if not isinstance(height_text, str):
            raise HeightError("landmark_heights_height")
        try:
            height = Decimal(height_text)
        except ArithmeticError:
            raise HeightError("landmark_heights_height") from None
        if height <= 0:
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
                ),
            )
        )
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
                },
            }
        )
    return out, citations


__all__ = [
    "LANDMARK_HEIGHTS_PATH",
    "LandmarkCitation",
    "LandmarkHeight",
    "apply_landmark_heights",
    "load_landmark_heights",
]
