"""All-or-nothing assignment reuses free-flow paths across the stored day."""

from fractions import Fraction

from .inputs import Flow, NoPathError, Roads
from .params import Parameters
from .paths import loading_nodes, shortest


def free_times(roads: Roads, parameters: Parameters) -> dict[str, Fraction]:
    return {
        link.id: link.length_m * 60 / (1000 * parameters.speeds[link.road_class])
        for link in roads.links
    }


def volumes(
    roads: Roads, flows: tuple[Flow, ...], parameters: Parameters
) -> dict[tuple[str, str, int, bool], Fraction]:
    loading = loading_nodes(roads)
    times = free_times(roads, parameters)
    paths = {}
    output: dict[tuple[str, str, int, bool], Fraction] = {}
    for flow in flows:
        if flow.origin == flow.destination:
            continue
        pair = (loading[flow.origin], loading[flow.destination])
        if pair not in paths:
            try:
                paths[pair] = shortest(roads, times, *pair)[2]
            except ValueError as error:
                raise NoPathError(f"NO_DATA: no_path {pair[0]} -> {pair[1]}") from error
        for link in paths[pair]:
            key = (link, flow.day_type, flow.hour, flow.summer)
            output[key] = output.get(key, Fraction(0)) + flow.estimate
    return {key: volume for key, volume in output.items() if volume > 0}
