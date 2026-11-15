"""Overture places pipeline. An area comes only from AreaProvider."""


class PlacesError(Exception):
    """A places check failed. reason is the name the build reports."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
