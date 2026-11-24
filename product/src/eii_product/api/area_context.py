"""Trusted, local routing dependency. The API's only area-context constructor."""

from __future__ import annotations

import json
import tarfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import Depends, Request

from eii_core.reasons import reason
from eii_product.api.session_store import SessionShapes, SessionStore
from eii_product.assistant.playbooks.engine import UnregisteredShapes
from eii_product.config import ConfigError
from eii_product.store.registry import PACKAGED
from eii_product.store.release_check import CheckedRelease
from eii_product.tools.make_area import (
    PUBLIC_ONLY,
    MakeAreaContext,
    PublicPoint,
    RoutingCall,
    ShapePort,
)
from eii_product.tools.routing import ROUTING_TILES_UNAVAILABLE, RoutingTilesUnavailable


@dataclass(frozen=True)
class RoutingSource:
    tile_folder: Path | None = None
    call: RoutingCall | None = None
    _storage: TemporaryDirectory[str] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if (self.tile_folder is None) == (self.call is None):
            raise ConfigError("routing_tiles")
        if self.tile_folder is not None:
            if (
                not isinstance(self.tile_folder, Path)
                or not self.tile_folder.is_dir()
                or not (self.tile_folder / "config.json").is_file()
            ):
                raise ConfigError("routing_tiles")
        if self.call is not None and not callable(self.call):
            raise ConfigError("routing_tiles")

    @classmethod
    def from_tiles(cls, extract: Path, release_folder: Path) -> RoutingSource:
        """Use only a local extract; never consume a release-supplied config."""
        from valhalla import get_config

        storage = None
        diagnostic = "routing_tiles"
        try:
            if (
                not isinstance(extract, Path)
                or not isinstance(release_folder, Path)
                or not extract.is_file()
            ):
                raise ValueError
            relative = extract.relative_to(release_folder)
            if ".." in relative.parts:
                raise ValueError
            candidate = release_folder
            for part in relative.parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    raise ValueError
            _check_extract(extract)
            storage = TemporaryDirectory(prefix="eii-routing-")
            folder = Path(storage.name)
            config = get_config(tile_extract=extract, tile_dir="")
            # No directory fallback, traffic tar, ancillary database or tile URL.
            config["mjolnir"] = {"tile_extract": str(extract.resolve()), "tile_dir": ""}
            config["additional_data"] = {}
            (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
            return cls(tile_folder=folder, _storage=storage)
        except (OSError, ValueError, RuntimeError, tarfile.TarError) as error:
            diagnostic = reason(error, "routing_tiles")
            if storage is not None:
                storage.cleanup()
        raise ConfigError(diagnostic)

    @classmethod
    def from_call(cls, call: RoutingCall) -> RoutingSource:
        return cls(call=call)


def _check_extract(extract: Path) -> None:
    """Validate the wheel's indexed, uncompressed tar without extracting files."""
    from valhalla.baldr import GraphId
    from valhalla.baldr.utils.tar_index import decode_tar_index

    with tarfile.open(extract, "r:") as archive:
        members = archive.getmembers()
        index = decode_tar_index(extract)
        if not index or any(not member.isfile() for member in members):
            raise ValueError
        tiles = members[1:]
        if len(tiles) != len(index) or len({m.name for m in tiles}) != len(tiles):
            raise ValueError
        for member, entry in zip(tiles, index, strict=True):
            if (
                member.offset_data,
                GraphId.from_tile_path(member.name).value,
                member.size,
            ) != (entry.offset, entry.tile_id.value, entry.size):
                raise ValueError


def routing_from_release(checked: CheckedRelease) -> RoutingSource:
    """Decision 0096: exactly one listed routing extract, never a folder."""
    artefacts = checked.document.get("artefacts")
    if type(artefacts) is not list:
        raise ConfigError("routing_tiles")
    entries = [
        entry
        for entry in artefacts
        if type(entry) is dict
        and type(entry.get("path")) is str
        and entry["path"].startswith("artefacts/routing/")
    ]
    if len(entries) != 1 or entries[0]["path"] != "artefacts/routing/tiles.tar":
        raise ConfigError("routing_tiles")
    return RoutingSource.from_tiles(
        checked.folder / "artefacts/routing/tiles.tar", checked.folder
    )


def _unconfigured(
    mode: str, minutes: int, latitude: object, longitude: object
) -> tuple[tuple[object, object], ...]:
    raise RoutingTilesUnavailable(ROUTING_TILES_UNAVAILABLE)


def trusted_seat(request: Request) -> str | None:
    """Pre-S9-T02 seat binding: one opaque seat per admitted session.

    Only this dependency changes when the signed seat cookie lands; no body or
    header supplies a seat. Tests override it to prove same-session isolation.
    """
    return request.cookies.get("eii_session")


def trusted_shapes(request: Request, seat: str | None) -> SessionShapes:
    """The admitted session whose seat the trusted dependency verified, or none."""
    if seat is None:
        return SessionShapes()
    sessions: SessionStore = request.app.state.sessions
    return sessions.shapes(request.cookies.get("eii_session"), seat)


_SEAT = Depends(trusted_seat)


class AreaContextFactory:
    def __init__(
        self,
        release_id: str,
        routing: RoutingSource | None,
        *,
        point_snapshot: Callable[[], Mapping[str, tuple[PublicPoint, ...]]]
        | None = None,
        hosting_off: frozenset[str] = frozenset(),
    ) -> None:
        if routing is not None and not isinstance(routing, RoutingSource):
            raise ConfigError("routing_tiles")
        self.release_id = release_id
        self.routing = routing
        self.point_snapshot = point_snapshot
        self.hosting_off = hosting_off

    def _build(self, shapes: ShapePort, name: str) -> MakeAreaContext:
        source = self.routing
        return MakeAreaContext(
            self.release_id,
            PUBLIC_ONLY,
            name,
            PACKAGED,
            shapes,
            tile_folder=None if source is None else source.tile_folder,
            routing=_unconfigured if source is None else source.call,
            point_snapshot=self.point_snapshot,
            hosting_off=self.hosting_off,
        )

    def for_session(self, shapes: SessionShapes) -> MakeAreaContext:
        return self._build(shapes, "site_check")

    def for_playbook(self, name: str) -> MakeAreaContext:
        return self._build(UnregisteredShapes(), name)

    def dependency(self, request: Request, seat: str | None = _SEAT) -> MakeAreaContext:
        verified = trusted_seat(request) if seat is _SEAT else seat
        return self.for_session(trusted_shapes(request, verified))
