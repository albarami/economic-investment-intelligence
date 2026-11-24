"""Stage the built heights asset as release artefacts (S3-T16).

The assembly's ``heights`` phase record binds the four files of the S2-T20
asset by hash: ``heights.json``, ``manifest.heights.json``, the building table
and the building inventory's manifest. Each is read through the producer's
pinned ``_load`` and, only when its bytes still match that record, placed
under ``artefacts/heights/`` of the cache by decision 0096's single writer
``place_artefact``, which records it in ``assembly/artefacts.json``; the heights
manifest is placed as ``<sha256>.json``, so the release manifest's artefact
entry for it is the trusted pin the product's startup reads. No record means
no heights; a record that is not ``built`` or a changed file refuses.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from eii_custodian.publicdata.building_inputs import BUILDING_MANIFEST_RELATIVE
from eii_custodian.publicdata.heights.model import (
    BUILDINGS_RELATIVE,
    HEIGHTS_FILE,
    HEIGHTS_RELATIVE,
    MANIFEST_FILE,
)
from eii_custodian.release.artefacts import place_artefact
from eii_custodian.release.producer import _decode, _load, _path

RECORD = "assembly/heights.json"
FOLDER = "artefacts/heights/"
REFUSED = "assembly_heights_incomplete"


def _verified(cache: Path, relative: str, digest: object) -> Path:
    """The source path of one recorded file whose bytes match ``digest``."""
    try:
        body = _load(cache.parent, relative)
    except ValueError:
        raise ValueError(REFUSED) from None
    if body is None or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError(REFUSED)
    return _path(cache.parent, relative)


def stage_heights(cache: Path) -> list[dict[str, str]]:
    """Place the recorded heights files through ``place_artefact``; return
    their artefact references, or none."""
    body = _load(cache, RECORD)
    if body is None:
        return []
    record = _decode(body)
    files, building = record.get("files"), record.get("building_files")
    if (
        record.get("state") != "built"
        or not isinstance(files, dict)
        or set(files) != {HEIGHTS_FILE, MANIFEST_FILE}
        or not isinstance(building, dict)
        or set(building) != {BUILDINGS_RELATIVE, BUILDING_MANIFEST_RELATIVE}
    ):
        raise ValueError(REFUSED)
    sources = {
        HEIGHTS_FILE: (f"{HEIGHTS_RELATIVE}/{HEIGHTS_FILE}", files[HEIGHTS_FILE]),
        MANIFEST_FILE: (f"{HEIGHTS_RELATIVE}/{MANIFEST_FILE}", files[MANIFEST_FILE]),
        **{
            Path(name).name: (name, building[name])
            for name in (BUILDINGS_RELATIVE, BUILDING_MANIFEST_RELATIVE)
        },
    }
    # Every file is checked before any is placed, so a refusal places none.
    checked = {
        name: (_verified(cache, relative, digest), digest)
        for name, (relative, digest) in sorted(sources.items())
    }
    refs = []
    for name, (source, digest) in checked.items():
        target = FOLDER + (f"{digest}.json" if name == MANIFEST_FILE else name)
        try:
            placed = place_artefact(cache, target, source)
        except ValueError:
            raise ValueError(REFUSED) from None
        # The copied bytes are hashed again; a file changed since the check
        # refuses, and the draft is never written.
        if placed["sha256"] != digest:
            raise ValueError(REFUSED)
        refs.append(placed)
    return sorted(refs, key=lambda ref: ref["path"])


__all__ = ["FOLDER", "stage_heights"]
