"""N3 transient routing metadata. No response body survives a request."""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit


class NativeFailure(ValueError):
    def __init__(self) -> None:
        super().__init__("native-view-unavailable")


@dataclass(frozen=True)
class Target:
    path: str
    session: str | None = None


@dataclass
class View:
    created: float
    started: float | None = None
    aliases: dict[str, Target] = field(default_factory=dict)


class NativeViews:
    """Caller holds the existing route lock for all operations."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.views: dict[str, View] = {}

    def purge(self) -> None:
        now = self.clock()
        for key, view in list(self.views.items()):
            if (
                now - (view.started if view.started is not None else view.created)
                >= 10800
            ):
                self.dispose(key)

    def create(self, identifier: str) -> None:
        self.purge()
        if identifier in self.views:
            raise NativeFailure
        self.views[identifier] = View(self.clock())

    def contains(self, identifier: str) -> bool:
        self.purge()
        return identifier in self.views

    def dispose(self, identifier: str) -> None:
        self.views.pop(identifier, None)

    def target(self, identifier: str, alias: str, base: str) -> Target:
        self.purge()
        view = self.views.get(identifier)
        if view is None:
            raise NativeFailure
        if alias == "3dtiles/root.json" and view.started is None:
            view.started = self.clock()
            return Target(urlsplit(base).path.rstrip("/") + "/v1/3dtiles/root.json")
        if alias not in view.aliases:
            raise NativeFailure
        return view.aliases[alias]

    def refuse_session_echo(self, identifier: str, raw: bytes) -> None:
        view = self.views.get(identifier)
        if view is None:
            raise NativeFailure
        sessions = {
            target.session for target in view.aliases.values() if target.session
        }
        if any(session.encode() in raw for session in sessions):
            raise NativeFailure

    def rewrite(self, identifier: str, parent: Target, raw: bytes, base: str) -> bytes:
        view = self.views.get(identifier)
        if view is None:
            raise NativeFailure
        pending: dict[str, Target] = {}
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or set(body) - {
                "asset",
                "root",
                "geometricError",
            }:
                raise NativeFailure
            asset = body["asset"]
            if not isinstance(asset, dict) or set(asset) - {
                "version",
                "tilesetVersion",
                "generator",
                "copyright",
                "gltfUpAxis",
            }:
                raise NativeFailure
            if asset.get("version") not in {"0.0", "1.0", "1.1"}:
                raise NativeFailure
            asset.pop("tilesetVersion", None)
            self._tile(body["root"], parent, base, pending)
            if len(view.aliases) + len(pending) > 10000:
                raise NativeFailure
            encoded = json.dumps(body, separators=(",", ":")).encode()
            if any(
                target.session and target.session.encode() in encoded
                for target in [parent, *pending.values()]
            ):
                raise NativeFailure
            self.refuse_session_echo(identifier, encoded)
            view.aliases.update(pending)
            return encoded
        except (ValueError, KeyError, TypeError, RecursionError):
            raise NativeFailure from None

    def _tile(
        self, tile: object, parent: Target, base: str, pending: dict[str, Target]
    ) -> None:
        if not isinstance(tile, dict) or set(tile) - {
            "boundingVolume",
            "viewerRequestVolume",
            "geometricError",
            "refine",
            "transform",
            "content",
            "contents",
            "children",
        }:
            raise NativeFailure
        if "content" in tile and "contents" in tile:
            raise NativeFailure
        contents = tile.get("contents", [tile["content"]] if "content" in tile else [])
        if not isinstance(contents, list):
            raise NativeFailure
        for content in contents:
            if not isinstance(content, dict) or set(content) - {
                "uri",
                "url",
                "boundingVolume",
            }:
                raise NativeFailure
            keys = set(content) & {"uri", "url"}
            if len(keys) != 1:
                raise NativeFailure
            key = keys.pop()
            target = reference(content[key], parent, base)
            suffix = ".json" if target.path.endswith(".json") else ".glb"
            alias = "3dtiles/" + uuid.uuid4().hex + suffix
            pending[alias] = target
            content[key] = "/api/photoreal/" + alias
        children = tile.get("children", [])
        if not isinstance(children, list):
            raise NativeFailure
        for child in children:
            self._tile(child, parent, base, pending)


def reference(value: object, parent: Target, base: str) -> Target:
    if (
        not isinstance(value, str)
        or not value
        or any(ord(c) < 33 for c in value)
        or "\\" in value
        or "#" in value
    ):
        raise NativeFailure
    try:
        parsed = urlsplit(value)
        # Reject encoded separators and multi-encoded paths, before resolution can erase traversal.
        decoded = unquote(parsed.path)
        if (
            "%" in decoded
            or any(part in {".", ".."} for part in decoded.split("/"))
            or decoded.count("/") != parsed.path.count("/")
        ):
            raise NativeFailure
        origin = urlsplit(base)
        resolved = urlsplit(
            urljoin(f"{origin.scheme}://{origin.netloc}{parent.path}", value)
        )
        prefix = origin.path.rstrip("/") + "/v1/3dtiles/"
        if (
            (resolved.scheme, resolved.netloc) != (origin.scheme, origin.netloc)
            or resolved.username
            or resolved.password
            or resolved.fragment
            or not resolved.path.startswith(prefix)
            or resolved.path == prefix + "root.json"
        ):
            raise NativeFailure
        if re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+\.(?:json|glb)", resolved.path) is None:
            raise NativeFailure
        query = parse_qsl(resolved.query, keep_blank_values=True, strict_parsing=True)
        session = parent.session
        if query:
            if (
                len(query) != 1
                or query[0][0] != "session"
                or re.fullmatch(r"[A-Za-z0-9_-]{1,512}", query[0][1]) is None
            ):
                raise NativeFailure
            session = query[0][1]
        return Target(resolved.path, session)
    except ValueError:
        raise NativeFailure from None
