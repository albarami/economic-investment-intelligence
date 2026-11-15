from collections.abc import Sequence

from .geometry.base import BaseGeometry

def unary_union(geoms: Sequence[BaseGeometry]) -> BaseGeometry: ...
