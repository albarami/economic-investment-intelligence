"""Primary-engine adapter checks for the synthetic spike."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest
from product.tests.test_areas_spike import FACTORS, FRAME, ROAD

from eii_product.areas_spike import engine
from eii_product.areas_spike.router import isochrone, routed_area


def test_equal_factors_reuse_tiles() -> None:
    road_json = json.dumps(ROAD, sort_keys=True)
    first = engine.scaled_actor(road_json, FACTORS[0])
    with patch.object(engine.subprocess, "run", side_effect=AssertionError("Rebuilt")):
        assert engine.scaled_actor(road_json, FACTORS[1]) is first


def test_empty_network_refused_before_builder() -> None:
    from eii_product.areas_spike.router import isochrone

    with patch.object(engine.subprocess, "run", side_effect=AssertionError("Built")):
        with pytest.raises(ValueError, match="no polygon"):
            isochrone(
                {**ROAD, "edges": []}, "drive", ROAD["cutoff_seconds"], 0, FACTORS
            )


def test_exact_ring_is_the_engine_polygon() -> None:
    actor, _temporary = engine.scaled_actor(
        json.dumps(ROAD, sort_keys=True), FACTORS[0]
    )
    original = actor.isochrone
    with patch.object(actor, "isochrone", wraps=original) as call:
        area = routed_area(ROAD, "drive", ROAD["cutoff_seconds"], 0, FACTORS, FRAME)
    call.assert_called_once()
    raw = original(call.call_args.args[0])
    assert area.exact == tuple(
        (lat, lon) for lon, lat in raw["features"][0]["geometry"]["coordinates"][0]
    )


def test_walk_always_uses_unscaled_tiles() -> None:
    with patch.object(engine, "scaled_actor", wraps=engine.scaled_actor) as call:
        for hour in range(len(FACTORS)):
            isochrone(ROAD, "walk", ROAD["cutoff_seconds"], hour, FACTORS)
    assert all(item.args[1] == 1.0 for item in call.call_args_list)


def test_builder_failure_is_refused() -> None:
    engine.scaled_actor.cache_clear()
    failure = subprocess.CompletedProcess(args=[], returncode=1)
    with patch.object(engine.subprocess, "run", return_value=failure):
        with pytest.raises(RuntimeError, match="Synthetic tile builder failed"):
            engine.scaled_actor(json.dumps(ROAD, sort_keys=True), FACTORS[0])


@pytest.mark.parametrize(
    ("geometry_type", "ring_count", "message"),
    [
        ("LineString", 1, "Engine geometry must be a Polygon"),
        ("Polygon", 2, "Engine polygon must have one ring"),
    ],
    ids=["geometry-type", "one-ring"],
)
def test_unexpected_engine_geometry_is_refused(
    geometry_type: str, ring_count: int, message: str
) -> None:
    actor = Mock()
    actor.isochrone.return_value = {
        "features": [
            {
                "geometry": {
                    "type": geometry_type,
                    "coordinates": [[(0.0, 0.0)]] * ring_count,
                }
            }
        ]
    }
    with patch.object(engine, "scaled_actor", return_value=(actor, None)):
        with pytest.raises(ValueError, match=f"^{message}$"):
            isochrone(ROAD, "drive", ROAD["cutoff_seconds"], 0, FACTORS)
