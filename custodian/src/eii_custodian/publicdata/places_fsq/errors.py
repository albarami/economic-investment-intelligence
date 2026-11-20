"""Named refusals of the further places source. The reason is the check name."""

from __future__ import annotations

from enum import StrEnum


class ReleaseListingReason(StrEnum):
    """Closed refusals for discovery; no source-supplied text becomes a reason."""

    XML = "release_listing"
    PREFIX = "release_prefix"
    TRUNCATED = "release_truncated"
    KEY = "release_key"
    DUPLICATE = "release_duplicate"
    MISSING = "release_missing"
    INVALID = "release_invalid"


class PlacesFsqError(Exception):
    """A places-source check failed. reason is the name the build reports."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
