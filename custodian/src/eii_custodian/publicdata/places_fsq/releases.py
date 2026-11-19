"""Select and validate dated releases of the anonymous public copy."""

from __future__ import annotations

import re
from datetime import date

from eii_custodian.publicdata.fetch.page_html import ShapeError, Tree
from eii_custodian.publicdata.places_fsq.constants import COPY_ROOT
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LOOSE_DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")


def validate_release(release: str) -> str:
    """Require one real ISO calendar date, with no surrounding text."""
    if not isinstance(release, str) or _DATE.fullmatch(release) is None:
        raise PlacesFsqError("release_invalid")
    try:
        parsed = date.fromisoformat(release)
    except ValueError:
        raise PlacesFsqError("release_invalid") from None
    if parsed.isoformat() != release:
        raise PlacesFsqError("release_invalid")
    return release


def validate_release_path(file_path: str, release: str) -> None:
    """Refuse a dated receipt path that belongs to another release."""
    match = _DATE.search(file_path)
    if match is not None and match.group(0) != release:
        raise PlacesFsqError("release_mismatch")


def select_release(body: bytes, root: str = COPY_ROOT) -> str:
    """Return the greatest date among exact dated-directory links of one root."""
    try:
        anchors = Tree(body).root.find("a")
    except ShapeError:
        raise PlacesFsqError("release_listing") from None
    found: set[str] = set()
    for anchor in anchors:
        href = anchor.attrs.get("href")
        if href is None or _LOOSE_DATE.search(href) is None:
            continue
        relative = _dated_directory(href, root)
        release = relative[:-1]
        validate_release(release)
        if release in found:
            raise PlacesFsqError("release_duplicate")
        found.add(release)
    if not found:
        raise PlacesFsqError("release_missing")
    return max(found)


def _dated_directory(href: str, root: str) -> str:
    if href.startswith(root):
        relative = href[len(root) :]
    else:
        relative = href
    if _LOOSE_DATE.fullmatch(relative[:-1] if relative.endswith("/") else ""):
        return relative
    raise PlacesFsqError("release_link")
