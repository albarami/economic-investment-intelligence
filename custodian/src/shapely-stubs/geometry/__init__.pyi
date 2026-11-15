from collections.abc import Iterable
from typing import Protocol

from .base import BaseGeometry

class _GeoInterface(Protocol):
    @property
    def __geo_interface__(self) -> dict[str, object]: ...

class Point(BaseGeometry):
    def __init__(self, x: float, y: float) -> None: ...
    @property
    def x(self) -> float: ...
    @property
    def y(self) -> float: ...

class Polygon(BaseGeometry):
    def __init__(self, shell: Iterable[tuple[float, float]]) -> None: ...

def shape(context: dict[str, object] | _GeoInterface) -> BaseGeometry: ...
