# Scalar subset used by frame and the GIS layer rows; Shapely 2.2 manual, read 2026-11-14.
from .geometry import Point
from .geometry.base import BaseGeometry

def point_on_surface(geometry: BaseGeometry) -> Point: ...

# Scalar WKB read used by the fixed Public layer reader.
def from_wkb(geometry: bytes) -> BaseGeometry: ...
