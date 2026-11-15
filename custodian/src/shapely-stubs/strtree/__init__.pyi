# The one member the heights step uses; Shapely 2.2 manual, read 2026-11-15.
from collections.abc import Iterable, Sequence

from shapely.geometry.base import BaseGeometry

class STRtree:
    def __init__(self, geoms: Iterable[BaseGeometry]) -> None: ...
    @property
    def geometries(self) -> Sequence[BaseGeometry]: ...
    def query(self, geometry: BaseGeometry) -> Sequence[int]: ...
