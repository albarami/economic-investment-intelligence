"""Select and validate dated releases of the anonymous public copy."""

from __future__ import annotations

import re
from datetime import date
from typing import NoReturn
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from eii_custodian.publicdata.places_fsq.constants import COPY_ROOT
from eii_custodian.publicdata.places_fsq.errors import (
    PlacesFsqError,
    ReleaseListingReason,
)

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class _ListingTreeBuilder(ET.TreeBuilder):
    """Reject DTDs (including entity declarations) and PIs in the XML parser."""

    def doctype(self, name: str, pubid: str | None, system: str | None) -> NoReturn:
        raise PlacesFsqError(ReleaseListingReason.XML)

    def pi(self, target: str, text: str | None = None) -> NoReturn:
        raise PlacesFsqError(ReleaseListingReason.XML)


def _scalar(element: ET.Element, name: str) -> str:
    children = element.findall(_NS + name)
    if len(children) != 1 or len(children[0]) or children[0].text is None:
        raise PlacesFsqError(ReleaseListingReason.XML)
    return children[0].text


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
    for match in _DATE.finditer(file_path):
        if match.group(0) != release:
            raise PlacesFsqError("release_mismatch")


def select_release(body: bytes, root: str = COPY_ROOT) -> str:
    """Select the greatest metadata-backed date from a complete bucket listing."""
    try:
        document = ET.fromstring(
            body, parser=ET.XMLParser(target=_ListingTreeBuilder())
        )
    except ET.ParseError:
        raise PlacesFsqError(ReleaseListingReason.XML) from None
    if document.tag != _NS + "ListBucketResult":
        raise PlacesFsqError(ReleaseListingReason.XML)
    prefix = urlsplit(root).path.rstrip("/").rsplit("/", 1)[-1] + "/"
    if _scalar(document, "Prefix") != prefix:
        raise PlacesFsqError(ReleaseListingReason.PREFIX)
    truncated = _scalar(document, "IsTruncated")
    if truncated == "true":
        raise PlacesFsqError(ReleaseListingReason.TRUNCATED)
    if truncated != "false":
        raise PlacesFsqError(ReleaseListingReason.XML)
    keys: set[str] = set()
    found: set[str] = set()
    for item in document:
        if not item.tag.startswith(_NS):
            raise PlacesFsqError(ReleaseListingReason.XML)
        if item.tag != _NS + "Contents":
            continue
        key = _scalar(item, "Key")
        if not key.startswith(prefix):
            raise PlacesFsqError(ReleaseListingReason.PREFIX)
        if key in keys:
            raise PlacesFsqError(ReleaseListingReason.DUPLICATE)
        keys.add(key)
        relative = key[len(prefix) :]
        if "/" not in relative and relative:
            continue  # Root files such as README.md are not releases.
        parts = relative.split("/", 2)
        if len(parts) != 3 or parts[1] != "places":
            raise PlacesFsqError(ReleaseListingReason.KEY)
        release = validate_release(parts[0])
        if parts[2] == "_metadata":
            found.add(release)
    if not found:
        raise PlacesFsqError(ReleaseListingReason.MISSING)
    return max(found)
