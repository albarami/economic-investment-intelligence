"""BE-109 memory-only shapes behind a bounded, locked session-key port."""

import secrets
import threading
from dataclasses import dataclass

from starlette.responses import Response

from eii_core.shapes import Ring, ring_sha256
from eii_product.config import ConfigError
from eii_product.tools.make_area import RegisteredShape, ShapeMiss

SESSION_CAP = 1_000
SHAPES_PER_SESSION = 50


class ShapeLimit(ValueError):
    """No new shape fits; no existing shape is removed."""


class SessionShapes:
    def __init__(self, seat: str | None = None) -> None:
        self.seat = seat
        self._rings: dict[str, Ring] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._rings)

    def find(self, shape_id: str) -> RegisteredShape | ShapeMiss:
        with self._lock:
            ring = self._rings.get(shape_id)
            return ShapeMiss("unknown") if ring is None else RegisteredShape(ring)

    def add(self, ring: Ring) -> str:
        identity = ring_sha256(ring)
        with self._lock:
            if identity in self._rings:
                return identity
            if len(self._rings) >= SHAPES_PER_SESSION:
                raise ShapeLimit("shape_limit")
            self._rings[identity] = ring
        return identity


@dataclass(frozen=True)
class CapReached:
    """Admission refused before token generation or allocation."""


@dataclass(frozen=True)
class SessionKey:
    key: str
    shapes: SessionShapes
    created: bool

    def keep(self, response: Response) -> None:
        """Hand a newly admitted session's key to its client."""
        if self.created:
            response.set_cookie(
                "eii_session", self.key, httponly=True, samesite="strict", path="/"
            )


class SessionStore:
    def __init__(self, cap: int = SESSION_CAP) -> None:
        if type(cap) is not int or cap <= 0:
            raise ConfigError("session_cap")
        self._cap = cap
        self._sessions: dict[str, SessionShapes] = {}
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def shapes(self, value: str | None, seat: str | None = None) -> SessionShapes:
        """Read only; an unknown cookie never allocates or admits."""
        with self._lock:
            found = self._sessions.get(value) if value is not None else None
            if found is None or found.seat != (seat if seat is not None else value):
                return SessionShapes()
            return found

    def admit(self, value: str | None) -> SessionKey | CapReached:
        with self._lock:
            if value is not None and value in self._sessions:
                return SessionKey(value, self._sessions[value], False)
            if len(self._sessions) >= self._cap:
                return CapReached()
            key = secrets.token_urlsafe(32)
            while key in self._sessions or key == value:
                key = secrets.token_urlsafe(32)
            shapes = SessionShapes(key)
            self._sessions[key] = shapes
            return SessionKey(key, shapes, True)

    def release(self, found: SessionKey) -> None:
        """Undo one request's own new allocation; an existing session stays."""
        with self._lock:
            if found.created and self._sessions.get(found.key) is found.shapes:
                del self._sessions[found.key]
