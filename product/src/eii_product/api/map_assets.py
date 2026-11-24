"""Map-serving paths come only from a checked release manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from eii_product.config import ConfigError
from eii_product.store.release_check import CheckedRelease

BASEMAP = "artefacts/tiles/basemap.pmtiles"
FONTS = "artefacts/fonts"


@dataclass(frozen=True)
class MapAssetPaths:
    tile_dir: Path
    font_dir: Path | None
    basemap_name: Literal["basemap.pmtiles"] | None


def _paths(checked: CheckedRelease) -> list[str]:
    entries = cast(list[dict[str, str]], checked.document.get("artefacts", []))
    return [entry["path"] for entry in entries]


def basemap_entry(checked: CheckedRelease) -> str:
    matches = [path for path in _paths(checked) if path == BASEMAP]
    if len(matches) != 1:
        raise ConfigError("basemap_missing")
    return matches[0]


def font_entries(checked: CheckedRelease) -> list[str]:
    matches = [
        path
        for path in _paths(checked)
        if len(PurePosixPath(path).parts) == 4
        and PurePosixPath(path).parts[:2] == ("artefacts", "fonts")
        and path.endswith(".pbf")
    ]
    if not matches:
        raise ConfigError("fonts_missing")
    return matches


def map_asset_paths(checked: CheckedRelease) -> MapAssetPaths:
    basemap_name: Literal["basemap.pmtiles"] | None = None
    if BASEMAP in _paths(checked):
        basemap_entry(checked)
        basemap_name = "basemap.pmtiles"
    font_dir: Path | None = None
    try:
        font_entries(checked)
    except ConfigError:
        pass
    else:
        font_dir = checked.folder / "artefacts/fonts"
    return MapAssetPaths(
        checked.folder / "artefacts/tiles",
        font_dir,
        basemap_name,
    )


__all__ = [
    "BASEMAP",
    "FONTS",
    "MapAssetPaths",
    "basemap_entry",
    "font_entries",
    "map_asset_paths",
]
