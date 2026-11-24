"""Place configured basemap and glyph sources as release artefacts."""

from __future__ import annotations

import os
from pathlib import Path

from eii_custodian.release.artefacts import place_artefact

BASEMAP = "artefacts/tiles/basemap.pmtiles"
FONTS = "artefacts/fonts"


def configured_sources(root: Path) -> tuple[Path, Path]:
    """Return the one pinned Qatar extract and the glyph source directory."""
    folder = root / "data/basemap"
    matches = sorted(folder.glob("qatar-*.pmtiles"))
    if len(matches) > 1:
        raise ValueError("basemap_source_ambiguous")
    basemap = matches[0] if matches else folder / "qatar.pmtiles"
    return basemap, folder / "fonts"


def place_map_assets(cache: Path, basemap: Path, fonts: Path) -> dict[str, str]:
    """Place every present source; return missing sources' coverage reasons."""
    coverage: dict[str, str] = {}
    if not os.path.lexists(basemap):
        coverage["basemap"] = "basemap_missing"
    else:
        place_artefact(cache, BASEMAP, basemap)
    if not os.path.lexists(fonts):
        coverage["fonts"] = "fonts_missing"
        return coverage
    if fonts.is_symlink() or not fonts.is_dir():
        raise ValueError("artefact_not_regular")
    sources = sorted(fonts.glob("*/*.pbf"))
    if not sources:
        coverage["fonts"] = "fonts_missing"
        return coverage
    for source in sources:
        if source.parent.is_symlink():
            raise ValueError("artefact_not_regular")
        relative = source.relative_to(fonts).as_posix()
        place_artefact(cache, f"{FONTS}/{relative}", source)
    return coverage


__all__ = ["BASEMAP", "FONTS", "configured_sources", "place_map_assets"]
