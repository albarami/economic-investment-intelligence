"""Local cache boundary shared by the two raster readers."""

from pathlib import Path
from urllib.parse import urlsplit


class GridError(ValueError):
    """A named grid input is not acceptable."""


def local_file(cache: Path, path: str | Path) -> Path:
    """Reject schemes, GDAL virtual paths and cache escapes before decoding."""
    name = str(path)
    if urlsplit(name).scheme or name.startswith("/vsi"):
        raise GridError("local_file: remote or virtual path refused")
    candidate = Path(path).resolve()
    if not candidate.is_relative_to(cache.resolve()):
        raise GridError("local_file: outside cache")
    if not candidate.is_file():
        raise GridError("local_file: regular file required")
    return candidate
