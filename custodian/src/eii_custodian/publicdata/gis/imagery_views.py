"""Committed imagery views and the one export request each side allows.

The committed list is empty until a service path is confirmed. The builder
takes a view key and a side, never a box, a size, a year or a layer, and
refuses before any request exists.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import yaml

from eii_custodian.publicdata.fetch.allowlist import host_of

# List bounds, not a reading of an imagery service. No service path was
# confirmed on 2026-11-15. MAX_EDGE_PX is the image edge the one MapServer
# read on this host reported (maxImageWidth and maxImageHeight, QARS,
# the first visitor reading, request 16). MAX_VIEWS is this list's own cap.
WEB_MERCATOR = 3857
MAX_EDGE_PX = 4096
MAX_VIEWS = 8

_FILE = Path("custodian") / "publicdata" / "review" / "gis_imagery_views.yaml"
_KEY = re.compile(r"[a-z0-9_]+")
_FORMATS = frozenset({"png", "jpg"})
_SIDES = frozenset({"before", "after"})
_ROOT_KEYS = frozenset({"version", "image_sr", "views"})
_ROOT_REQUIRED = ("version", "image_sr", "views")
_VIEW_KEYS = frozenset({"key", "bbox_3857", "size", "format", "before", "after"})
_VIEW_REQUIRED = ("key", "bbox_3857", "size", "format", "before", "after")
_SIDE_KEYS = frozenset({"year", "layer"})
_SIDE_REQUIRED = ("year", "layer")


class ImageryViewsError(ValueError):
    """The imagery view list or its export request is refused."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ImagerySide:
    """The year and the layer id of one side of a view."""

    year: int
    layer: int


@dataclass(frozen=True)
class ImageryView:
    """One committed before-and-after view."""

    key: str
    bbox_3857: tuple[int | float, int | float, int | float, int | float]
    width: int
    height: int
    format: str
    before: ImagerySide
    after: ImagerySide


@dataclass(frozen=True)
class ImageryViews:
    """A loaded view list."""

    version: int
    image_sr: int
    views: tuple[ImageryView, ...]


@dataclass(frozen=True)
class ExportRequest:
    """One export operation. Its parameters are the closed set and nothing else."""

    url: str
    parameters: tuple[tuple[str, str], ...]


def views_path() -> Path:
    """Find the committed view list by walking parents."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _FILE
        if candidate.is_file():
            return candidate
    raise ImageryViewsError("views_file")


def load_views(path: Path | None = None) -> ImageryViews:
    """Load the committed list, or the file at path when one is given."""
    return _read(views_path() if path is None else path)


def export_request(
    views: ImageryViews,
    key: str,
    side: str,
    service_address: str,
    fetch_host: str,
) -> ExportRequest:
    """Return the one export request for a listed view and side.

    The box, size, year and layer come from the loaded list. A refusal is
    raised before the request exists.
    """
    if views.image_sr != WEB_MERCATOR:
        raise ImageryViewsError("image_sr")
    _require_service(service_address, fetch_host)
    if side not in _SIDES:
        raise ImageryViewsError("side")
    view = _find(views, key)
    if view is None:
        raise ImageryViewsError("view_absent")
    chosen = view.before if side == "before" else view.after
    parameters = _parameters(view, chosen)
    return ExportRequest(_request_url(service_address, parameters), parameters)


def _read(path: Path) -> ImageryViews:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ImageryViewsError("views_file") from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ImageryViewsError("views_file") from exc
    if not isinstance(loaded, dict):
        raise ImageryViewsError("views_root")
    _unknown(loaded, _ROOT_KEYS)
    _present(loaded, _ROOT_REQUIRED)
    return ImageryViews(
        _exact_int(loaded.get("version"), "version", 1),
        _exact_int(loaded.get("image_sr"), "image_sr", WEB_MERCATOR),
        _view_list(loaded.get("views")),
    )


def _view_list(value: object) -> tuple[ImageryView, ...]:
    if not isinstance(value, list):
        raise ImageryViewsError("views")
    if len(value) > MAX_VIEWS:
        raise ImageryViewsError("view_bound")
    found: list[ImageryView] = []
    seen: set[str] = set()
    for item in value:
        view = _view(item)
        if view.key in seen:
            raise ImageryViewsError("duplicate_key")
        seen.add(view.key)
        found.append(view)
    return tuple(found)


def _view(value: object) -> ImageryView:
    if not isinstance(value, dict):
        raise ImageryViewsError("view")
    _unknown(value, _VIEW_KEYS)
    _present(value, _VIEW_REQUIRED)
    before = _side(value.get("before"))
    after = _side(value.get("after"))
    if not before.year < after.year:
        raise ImageryViewsError("year_order")
    width, height = _size(value.get("size"))
    return ImageryView(
        _key(value.get("key")),
        _bbox(value.get("bbox_3857")),
        width,
        height,
        _image_format(value.get("format")),
        before,
        after,
    )


def _side(value: object) -> ImagerySide:
    if not isinstance(value, dict):
        raise ImageryViewsError("side_fields")
    _unknown(value, _SIDE_KEYS)
    _present(value, _SIDE_REQUIRED)
    return ImagerySide(_year(value.get("year")), _layer_id(value.get("layer")))


def _unknown(body: dict[Any, Any], allowed: frozenset[str]) -> None:
    for key in body:
        if not isinstance(key, str) or key not in allowed:
            shown = key if isinstance(key, str) else "type"
            raise ImageryViewsError(f"unknown_key:{shown}")


def _present(body: dict[Any, Any], required: tuple[str, ...]) -> None:
    for name in required:
        if name not in body:
            raise ImageryViewsError(f"missing_key:{name}")


def _exact_int(value: object, reason: str, expected: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        raise ImageryViewsError(reason)
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise ImageryViewsError("view_key")
    return value


def _bbox(value: object) -> tuple[int | float, int | float, int | float, int | float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ImageryViewsError("bbox")
    xmin = _number(value[0])
    ymin = _number(value[1])
    xmax = _number(value[2])
    ymax = _number(value[3])
    if not xmin < xmax or not ymin < ymax:
        raise ImageryViewsError("bbox")
    return (xmin, ymin, xmax, ymax)


def _number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ImageryViewsError("bbox")
    if isinstance(value, float) and not math.isfinite(value):
        raise ImageryViewsError("bbox")
    return value


def _size(value: object) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ImageryViewsError("size")
    width = _pixel(value[0])
    height = _pixel(value[1])
    if not 0 < width <= MAX_EDGE_PX or not 0 < height <= MAX_EDGE_PX:
        raise ImageryViewsError("size")
    return (width, height)


def _pixel(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ImageryViewsError("size")
    return value


def _image_format(value: object) -> str:
    if not isinstance(value, str) or value not in _FORMATS:
        raise ImageryViewsError("format")
    return value


def _year(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ImageryViewsError("year")
    return value


def _layer_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ImageryViewsError("layer")
    return value


def _find(views: ImageryViews, key: str) -> ImageryView | None:
    for view in views.views:
        if view.key == key:
            return view
    return None


def _parameters(view: ImageryView, chosen: ImagerySide) -> tuple[tuple[str, str], ...]:
    return (
        ("f", "image"),
        ("bbox", ",".join(_number_text(item) for item in view.bbox_3857)),
        ("bboxSR", str(WEB_MERCATOR)),
        ("imageSR", str(WEB_MERCATOR)),
        ("size", f"{view.width},{view.height}"),
        ("format", view.format),
        ("layers", f"show:{chosen.layer}"),
    )


def _number_text(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    rendered = format(value, "f").rstrip("0").rstrip(".")
    if rendered in {"", "-", "-0"}:
        return "0"
    return rendered


def _request_url(service_address: str, parameters: tuple[tuple[str, str], ...]) -> str:
    query = urlencode(parameters)
    return service_address.rstrip("/") + "/export?" + query


def _require_service(service_address: str, fetch_host: str) -> None:
    if service_address.strip() == "":
        raise ImageryViewsError("service_empty")
    parts = urlsplit(service_address)
    if parts.scheme.casefold() != "https":
        raise ImageryViewsError("service_scheme")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ImageryViewsError("service_address")
    host = host_of(service_address)
    if host == "" or host != fetch_host.strip().casefold():
        raise ImageryViewsError("service_host")
