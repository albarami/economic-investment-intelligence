"""Build one routing artefact from the reviewed, receipted road extract."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from eii_custodian.release.artefacts import RECORD, place_artefact

from .assembly import AssemblyError
from .assembly_io import local
from .fetch.bounded import file_hash
from .fetch.snapshots import read_snapshot
from .places.area_engine import PinnedEngine
from .places.area_files import ENGINE_PIN, ROAD_KEY

if TYPE_CHECKING:
    from .assembly_adapters import Production

TILES = "artefacts/routing/tiles.tar"


def build_routing(build: Production) -> dict[str, str]:
    digest = build.selected.get(ROAD_KEY)
    if digest is None:
        raise AssemblyError("assembly_lineage_missing")
    snapshot = read_snapshot(local(build.cache, ROAD_KEY), digest)
    if (
        snapshot.sidecar.get("key") != ROAD_KEY
        or snapshot.sidecar.get("source_id") != ROAD_KEY
    ):
        raise AssemblyError("assembly_lineage_missing")
    build.receipts[ROAD_KEY] = snapshot.sidecar
    with TemporaryDirectory(prefix="routing-build-", dir=build.cache) as temporary:
        extract = Path(temporary) / "tiles.tar"
        try:
            engine = PinnedEngine()
            if engine.version != ENGINE_PIN:
                raise AssemblyError("assembly_routing_failed")
            engine.write_extract(snapshot.body, extract)
        except (OSError, PackageNotFoundError, RuntimeError, ValueError):
            raise AssemblyError("assembly_routing_failed") from None
        reference = place_artefact(build.cache, TILES, extract)
    files = {TILES: reference["sha256"], RECORD: file_hash(local(build.cache, RECORD))}
    build.files.update(files)
    return build.record(
        "routing",
        dict(tables={}, artefact=reference, engine_version=ENGINE_PIN, files=files),
    )
