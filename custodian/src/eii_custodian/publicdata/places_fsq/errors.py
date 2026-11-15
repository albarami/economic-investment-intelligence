"""Named refusals of the further places source. The reason is the check name."""

from __future__ import annotations


class PlacesFsqError(Exception):
    """A places-source check failed. reason is the name the build reports."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
