"""Closed Process contract from the official readings in this package's README.

This builds requests and decodes injected replies only. Live admission, remaining
balance, sample-count reservation and billing quantization are still pending.
"""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.cdse.contracts import (
    CRS,
    EDGE_CAP,
    RESOLUTION_M,
    Metadata,
    Tile,
    validate_metadata,
)
from eii_custodian.publicdata.cdse.transport import CdseError
from eii_custodian.publicdata.fetch.snapshots import utc

# Read 2026-11-20: official Authentication and OpenAPI pages; README records hashes.
# These are documentary identities, not live allow-list admission.
DOCUMENTED_ENDPOINTS = {
    "token": "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    "process": "https://sh.dataspace.copernicus.eu/process/v1",
}
CRS_URL = "http://www.opengis.net/def/crs/EPSG/0/32639"
INPUT_BANDS = ("B04", "B03", "B02", "SCL", "dataMask")

# Local masking policy over the documented SCL categories. TILE exposes dates;
# SIMPLE's empty scenes object cannot establish contributing acquisitions.
# AUTO maps reflectance in [0, 1] to uint8, including the alpha channel.
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: INPUT_BANDS,
    mosaicking: "TILE",
    output: {id: "default", bands: 4, sampleType: "AUTO"}
  };
}
var contributors = {};
function evaluatePixel(samples, scenes) {
  for (var i = 0; i < samples.length; i++) {
    var s = samples[i];
    if (s.dataMask === 1 && [0, 1, 3, 7, 8, 9, 10].indexOf(s.SCL) === -1) {
      contributors[scenes.tiles[i].date] = true;
      return [2.5 * s.B04, 2.5 * s.B03, 2.5 * s.B02, 1];
    }
  }
  return [0, 0, 0, 0];
}
function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = {dates: Object.keys(contributors).sort()};
}
""".replace("INPUT_BANDS", json.dumps(INPUT_BANDS))


@dataclass(frozen=True)
class ProcessSpec:
    tile: Tile
    start: str
    end: str  # Internal exclusive end; wire endpoint is inclusive.

    def validate(self) -> None:
        """Require the owner grid and second-precision, explicit UTC window."""
        tile = self.tile
        if (
            tile.crs != CRS
            or tile.resolution_m != RESOLUTION_M
            or len(tile.bounds) != 4
            or any(type(v) is not int or v % RESOLUTION_M for v in tile.bounds)
            or type(tile.width) is not int
            or type(tile.height) is not int
            or not 0 < tile.width <= EDGE_CAP
            or not 0 < tile.height <= EDGE_CAP
            or tile.bounds[2] - tile.bounds[0] != tile.width * RESOLUTION_M
            or tile.bounds[3] - tile.bounds[1] != tile.height * RESOLUTION_M
            or tile.tile_id != f"tile-{tile.bounds[0]}-{tile.bounds[1]}"
        ):
            raise CdseError("request_schema_refused")
        start, end = utc(self.start), utc(self.end)
        if start >= end or start.microsecond or end.microsecond:
            raise CdseError("request_schema_refused")


def process_body(spec: ProcessSpec) -> dict[str, Any]:
    """No caller-controlled URL, script, collection, band or extra property."""
    spec.validate()
    # Official TimeRange is inclusive at both ends; internal windows are half-open.
    inclusive_end = (
        (utc(spec.end) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    )
    return {
        "input": {
            "bounds": {"bbox": list(spec.tile.bounds), "properties": {"crs": CRS_URL}},
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": spec.start, "to": inclusive_end},
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": spec.tile.width,
            "height": spec.tile.height,
            "responses": [
                {"identifier": "default", "format": {"type": "image/tiff"}},
                {"identifier": "userdata", "format": {"type": "application/json"}},
            ],
        },
        "evalscript": EVALSCRIPT,
    }


def validate_process_body(body: dict[str, Any]) -> None:
    """Reconstruct the closed request, rejecting additions at every depth."""
    try:
        bounds = body["input"]["bounds"]["bbox"]
        window = body["input"]["data"][0]["dataFilter"]["timeRange"]
        tile = Tile(
            f"tile-{bounds[0]}-{bounds[1]}",
            tuple(bounds),
            CRS,
            body["output"]["width"],
            body["output"]["height"],
        )
        end = (
            (utc(window["to"]) + timedelta(seconds=1))
            .isoformat()
            .replace("+00:00", "Z")
        )
        expected = process_body(ProcessSpec(tile, window["from"], end))
        # JSON comparison distinguishes boolean and integer as well as structure.
        if json.dumps(body, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        raise CdseError("request_schema_refused") from None


def unpack_process(
    body: bytes, spec: ProcessSpec, boundary: BaseGeometry
) -> tuple[bytes, Metadata]:
    """Bind raster and used dates from one response; never extract archive paths."""
    spec.validate()
    try:
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:") as archive:
            members = archive.getmembers()
            if (
                len(members) != 2
                or {member.name for member in members}
                != {"default.tif", "userdata.json"}
                or any(not m.isfile() or not 0 < m.size <= len(body) for m in members)
            ):
                raise ValueError
            payloads: dict[str, bytes] = {}
            for member in members:
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError
                payloads[member.name] = stream.read()
        data = json.loads(payloads["userdata.json"])
        if (
            not isinstance(data, dict)
            or set(data) != {"dates"}
            or not isinstance(data["dates"], list)
            or any(not isinstance(value, str) for value in data["dates"])
        ):
            raise ValueError
        meta = Metadata(
            spec.tile,
            spec.start,
            spec.end,
            tuple(data["dates"]),
            "least_cloudy",
            "cloud_and_nodata_transparent",
            "partial",
            "sentinel-2-l2a",
            ("B04", "B03", "B02"),
            Decimal("2.5"),
            "cdse-process.v1",
            ("SCL", "dataMask"),
        )
        validate_metadata(meta, boundary)
        from eii_custodian.publicdata.cdse.cache import validate_raster

        raster = payloads["default.tif"]
        validate_raster(raster, meta)
        return raster, meta
    except (tarfile.TarError, OSError, ValueError, TypeError):
        raise CdseError("process_response_refused") from None
