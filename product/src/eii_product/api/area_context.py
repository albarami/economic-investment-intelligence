"""Trusted, local routing dependency. The API's only area-context constructor."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import Depends, Request

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
    def from_tiles(cls, folder: Path) -> RoutingSource:
        return cls(tile_folder=folder)

    @classmethod
    def from_call(cls, call: RoutingCall) -> RoutingSource:
        return cls(call=call)


def routing_from_release(checked: CheckedRelease) -> RoutingSource:
    """ARC-119 path checks only; no folder content-digest rule exists yet."""
    artefacts = checked.document.get("artefacts")
    if type(artefacts) is not list:
        raise ConfigError("routing_tiles")
    entries = [
        entry
        for entry in artefacts
        if type(entry) is dict and entry.get("path") == "artefacts/routing/"
    ]
    if len(entries) != 1:
        raise ConfigError("routing_tiles")
    relative = PurePosixPath(entries[0]["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ConfigError("routing_tiles")
    candidate = checked.folder
    try:
        for part in relative.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ConfigError("routing_tiles")
        resolved = candidate.resolve()
        resolved.relative_to((checked.folder / "artefacts").resolve())
        return RoutingSource.from_tiles(resolved)
    except (OSError, ValueError, RuntimeError):
        raise ConfigError("routing_tiles") from None


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
    ) -> None:
        if routing is not None and not isinstance(routing, RoutingSource):
            raise ConfigError("routing_tiles")
        self.release_id = release_id
        self.routing = routing
        self.point_snapshot = point_snapshot

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
        )

    def for_session(self, shapes: SessionShapes) -> MakeAreaContext:
        return self._build(shapes, "site_check")

    def for_playbook(self, name: str) -> MakeAreaContext:
        return self._build(UnregisteredShapes(), name)

    def dependency(self, request: Request, seat: str | None = _SEAT) -> MakeAreaContext:
        verified = trusted_seat(request) if seat is _SEAT else seat
        return self.for_session(trusted_shapes(request, verified))
