"""Exact free-flow shortest paths with C25's two deterministic tie rules."""

from fractions import Fraction
from heapq import heappop, heappush
from math import atan2, cos, radians, sin, sqrt

from .inputs import Roads


def spherical_distance(
    lat: Fraction, lon: Fraction, other_lat: Fraction, other_lon: Fraction
) -> float:
    """Great-circle metres; L-74 fallback sphere, radius cancels in ordering."""
    a, b = radians(float(lat)), radians(float(other_lat))
    dlat = radians(float(other_lat - lat))
    dlon = radians(float(other_lon - lon))
    h = sin(dlat / 2) ** 2 + cos(a) * cos(b) * sin(dlon / 2) ** 2
    return 6371008.8 * 2 * atan2(sqrt(h), sqrt(max(0.0, 1 - h)))


def loading_nodes(roads: Roads) -> dict[str, str]:
    drivable = {end for link in roads.links for end in (link.source, link.target)}
    return {
        unit: min(
            (node for node in roads.nodes if node.id in drivable),
            key=lambda node: (
                spherical_distance(lat, lon, node.lat, node.lon),
                node.id,
            ),
        ).id
        for unit, (lat, lon) in roads.units.items()
    }


def shortest(
    roads: Roads, times: dict[str, Fraction], origin: str, destination: str
) -> tuple[Fraction, tuple[str, ...], tuple[str, ...]]:
    queue: list[tuple[Fraction, tuple[str, ...], tuple[str, ...]]] = [
        (Fraction(0), (origin,), ())
    ]
    visited = set()
    while queue:
        cost, nodes, links = heappop(queue)
        node = nodes[-1]
        if node in visited:
            continue
        visited.add(node)
        if node == destination:
            return cost, nodes, links
        for link in sorted(roads.links, key=lambda edge: edge.id):
            if link.source == node and link.target not in visited:
                heappush(
                    queue,
                    (cost + times[link.id], (*nodes, link.target), (*links, link.id)),
                )
    raise ValueError("NO_DATA: disconnected origin and destination")
