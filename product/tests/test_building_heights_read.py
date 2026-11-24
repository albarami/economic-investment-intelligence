"""The fixed heights read of S3-T16 on an invented released asset (SYN-B-*).

Every building, file and source here is invented; hosts are ``.invalid``.
The read's output is the committed web fixture, so the browser reader is
tested against the exact shape this route serves.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import tempfile
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from product.tests.public_http_support import Client

from eii_product.api.app import create_app
from eii_product.api.building_heights import HeightsRefusal, ReleasedBuildingHeights

WEB_FIXTURE = (
    Path(__file__).resolve().parents[2] / "web/tests/fixtures/building-heights.json"
)


def _square(lon: float, lat: float) -> list[list[float]]:
    side = 0.0005
    return [
        [lon, lat],
        [lon + side, lat],
        [lon + side, lat + side],
        [lon, lat + side],
        [lon, lat],
    ]


BUILDINGS = {
    "SYN-B-0001": (_square(51.5, 25.3), "30.00", "recorded"),
    "SYN-B-0004": (_square(51.501, 25.3), "20.00", "floor_count"),
    "SYN-B-0005": (_square(51.502, 25.3), "6.00", "wsf3d"),
    "SYN-B-0006": (_square(51.503, 25.3), None, "none"),
}
ERRORS: dict[str, dict[str, Any]] = {
    "floor_count": {
        "count": 2,
        "mean_absolute_error_m": "1.00",
        "mean_signed_error_m": "1.00",
        "median_absolute_error_m": "1.00",
        "reason": "",
    },
    "3dglobfp": {
        "count": 0,
        "mean_absolute_error_m": None,
        "mean_signed_error_m": None,
        "median_absolute_error_m": None,
        "reason": "no_pairs",
    },
    "wsf3d": {
        "count": 2,
        "mean_absolute_error_m": "10.00",
        "mean_signed_error_m": "-10.00",
        "median_absolute_error_m": "10.00",
        "reason": "",
    },
}
# The producer's own ``_file_record`` fields (S2-T20), publisher included.
FETCHED = [
    {
        "key": "bldg_3dglobfp/invented-part",
        "licence_basis": "open_licence",
        "licence_id": "CC-BY-4.0",
        "publisher": "Invented heights publisher",
        "retrieved_utc": "2026-11-01T08:00:00Z",
        "role": "read",
        "sha256": "1" * 64,
        "terms_read_on": "2026-11-01",
        "terms_words": "invented terms words",
        "url": "https://heights.invalid/globfp/part.zip",
    },
    {
        "key": "bldg_wsf3d/invented-cell",
        "licence_basis": "terms_recorded",
        "licence_id": "invented-terms",
        "publisher": "Invented settlement publisher",
        "retrieved_utc": "2026-11-02T08:00:00Z",
        "role": "read",
        "sha256": "2" * 64,
        "terms_read_on": "2026-11-02",
        "terms_words": "invented terms words",
        "url": "https://settlement.invalid/wsf/cell.tif",
    },
]
# The building inventory's chain (S2 ``fingerprint``), one invented part.
INVENTORY_LINK = {
    "fetch_url": "https://inventory.invalid/part-0.json",
    "identity": "invented-identity",
    "key": "bldg_ovt/invented-part-0",
    "landing_url": "https://inventory.invalid/",
    "licence_basis": "dataset",
    "licence_id": "ODbL-1.0",
    "licence_url": "https://inventory.invalid/licence",
    "publisher": "Invented inventory publisher",
    "receipt_sha256": "3" * 64,
    "retrieved_utc": "2026-10-30T08:00:00Z",
    "sha256": "4" * 64,
    "source_id": "bldg_ovt",
    "terms_read_on": "2026-10-30",
    "terms_words": "invented terms words",
    "title_en": "Invented inventory part",
}
# A landmark citation (S2-T20 ``apply_landmark_heights``) of SYN-B-0001.
LANDMARK = {
    "building_id": "SYN-B-0001",
    "citation": {
        "height_excerpt": "Height 30.00 m on the invented page.",
        "licence_basis": "pending",
        "page_sha256": "5" * 64,
        "page_url": "https://landmark.invalid/SYN/page",
        "publisher": "Invented landmark publisher",
        "retrieved_on": "2026-10-29",
    },
    "height_m": "30.00",
    "landmark_id": "SYN-LM-0001",
    "name_en": "SYN invented tower",
}


RAW = re.compile(r'"RAW:([^"]*)"')
RAW_OVERFLOW = "RAW:1e999"


def _dump(value: object) -> bytes:
    """Sorted JSON; a ``RAW:<token>`` string is written as the bare token."""
    text = RAW.sub(lambda match: match.group(1), json.dumps(value, sort_keys=True))
    return (text + "\n").encode()


def _parts() -> dict[str, Any]:
    heights = [
        {
            "building_id": key,
            "footprint_source_id": "invented",
            "height_m": height,
            "height_source": source,
            "reason": "" if height else "order_exhausted",
        }
        for key, (_ring, height, source) in sorted(BUILDINGS.items())
    ]
    table = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"building_id": key},
                "geometry": {"type": "Polygon", "coordinates": [copy.deepcopy(ring)]},
            }
            for key, (ring, _height, _source) in sorted(BUILDINGS.items())
        ],
    }
    manifest = {
        "card": "C47",
        "method": "MTH-125",
        "errors": copy.deepcopy(ERRORS),
        "estimate_label": "Heights are estimates.",
        "files": [*copy.deepcopy(FETCHED)],
        "landmark_heights": [copy.deepcopy(LANDMARK)],
    }
    inventory = {
        "method": "national-buildings.v1",
        "national_completeness": True,
        "source_chain": {INVENTORY_LINK["key"]: copy.deepcopy(INVENTORY_LINK)},
    }
    return {
        "heights": heights,
        "table": table,
        "manifest": manifest,
        "inventory": inventory,
    }


def write_asset(
    folder: Path, change: Callable[[dict[str, Any]], None] | None = None
) -> str:
    """Write the invented asset into ``folder``; ``change`` alters one part.

    Every hash is taken after the change, so a plant meets the guard it names
    rather than an integrity check. Returns the manifest's own hash, the pin.
    """
    parts = _parts()
    if change is not None:
        change(parts)
    heights, table = _dump(parts["heights"]), _dump(parts["table"])
    parts["inventory"].setdefault("output_sha256", hashlib.sha256(table).hexdigest())
    inventory = _dump(parts["inventory"])
    parts["manifest"]["files"] += [
        {
            "key": "building_table",
            "path": "assets/buildings/buildings.geojson",
            "role": "read",
            "sha256": hashlib.sha256(table).hexdigest(),
            "source_chain": {
                "path": "assets/buildings/manifest.buildings.json",
                "sha256": hashlib.sha256(inventory).hexdigest(),
            },
        },
        {
            "key": "landmark_heights",
            "path": "publicdata/review/landmark_heights.yaml",
            "role": "read",
            "sha256": "6" * 64,
        },
        {
            "key": "heights",
            "path": "assets/heights/heights.json",
            "role": "written",
            "sha256": hashlib.sha256(heights).hexdigest(),
        },
    ]
    for plant in parts.get("after", ()):
        plant(parts)
    manifest = _dump(parts["manifest"])
    identity = hashlib.sha256(manifest).hexdigest()
    folder.mkdir(parents=True)
    (folder / "heights.json").write_bytes(heights)
    (folder / "buildings.geojson").write_bytes(table)
    (folder / "manifest.buildings.json").write_bytes(inventory)
    (folder / f"{identity}.json").write_bytes(manifest)
    return identity


def released(
    root: Path, change: Callable[[dict[str, Any]], None] | None = None
) -> tuple[Path, str]:
    """The invented asset in its own folder, with its pin."""
    folder = root.resolve() / "heights"
    return folder, write_asset(folder, change)


def test_route_serves_the_committed_web_fixture(tmp_path: Path) -> None:
    folder, identity = released(tmp_path)
    app = create_app(tmp_path, heights=ReleasedBuildingHeights(folder, identity))
    response = Client(app).get("/api/building-heights")
    assert response.status_code == 200
    assert response.json() == json.loads(WEB_FIXTURE.read_text())


def test_route_refuses_an_argument_and_says_absent(tmp_path: Path) -> None:
    folder, identity = released(tmp_path)
    served = Client(
        create_app(tmp_path, heights=ReleasedBuildingHeights(folder, identity))
    )
    assert served.get("/api/building-heights?zoom=1").status_code == 422
    absent = Client(create_app(tmp_path)).get("/api/building-heights")
    assert absent.status_code == 404
    assert absent.json() == {"status": "NO_DATA", "reason": "heights_absent"}


def test_each_statistic_is_bound_to_its_metric_unit_and_fallback(
    tmp_path: Path,
) -> None:
    body = ReleasedBuildingHeights(*released(tmp_path)).read()
    bound = {
        (
            item["binding"]["metricKey"],
            item["binding"]["qualifiers"]["height_source"],
        ): item["fact"]
        for item in body["facts"]
    }
    assert bound[("building_height_pairs", "floor_count")]["unit"] == "count"
    assert bound[("building_height_pairs", "floor_count")]["value"] == 2
    assert bound[("building_height_mean_signed_error", "wsf3d")]["value"] == -10.0
    assert bound[("building_height_mean_abs_error", "wsf3d")]["unit"] == "metres"
    assert not any(source == "3dglobfp" for _metric, source in bound)
    assert body["fallback_errors"][1] == {"source": "3dglobfp", "reason": "no_pairs"}


def _drop_publisher(parts: dict[str, Any]) -> None:
    del parts["manifest"]["files"][0]["publisher"]


def _bad_height(parts: dict[str, Any]) -> None:
    parts["heights"][0]["height_m"] = "9" * 400


def _zero_height(parts: dict[str, Any]) -> None:
    parts["heights"][0]["height_m"] = "0.00"


def _none_with_height(parts: dict[str, Any]) -> None:
    parts["heights"][3]["height_m"] = "4.00"


def _unknown_source(parts: dict[str, Any]) -> None:
    parts["heights"][0]["height_source"] = "statistic"


def _orphan_row(parts: dict[str, Any]) -> None:
    parts["table"]["features"].pop()


def _orphan_footprint(parts: dict[str, Any]) -> None:
    extra = copy.deepcopy(parts["table"]["features"][0])
    extra["properties"]["building_id"] = "SYN-B-0099"
    parts["table"]["features"].append(extra)


def _multipolygon(parts: dict[str, Any]) -> None:
    parts["table"]["features"][0]["geometry"]["type"] = "MultiPolygon"


def _zero_count(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["floor_count"]["count"] = 0


def _float_error(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["wsf3d"]["mean_signed_error_m"] = -10.0


def _wrong_method(parts: dict[str, Any]) -> None:
    parts["manifest"]["method"] = "MTH-001"


def _missing_fallback(parts: dict[str, Any]) -> None:
    del parts["manifest"]["errors"]["wsf3d"]


def _no_pairs_value(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["3dglobfp"]["mean_signed_error_m"] = "10.00"


def _no_pairs_count_false(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["3dglobfp"]["count"] = False


def _no_pairs_count_one(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["3dglobfp"]["count"] = 1


def _no_pairs_extra(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["3dglobfp"]["note"] = None


def _statistics_extra(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["wsf3d"]["note"] = ""


def _statistics_field_missing(parts: dict[str, Any]) -> None:
    del parts["manifest"]["errors"]["wsf3d"]["median_absolute_error_m"]


def _statistics_reason_null(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["wsf3d"]["reason"] = None


def _statistics_count_true(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["wsf3d"]["count"] = True


def _statistics_count_huge(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["wsf3d"]["count"] = 2**53 + 1


def _statistics_error_huge(parts: dict[str, Any]) -> None:
    parts["manifest"]["errors"]["wsf3d"]["mean_absolute_error_m"] = "9" * 400


def _coordinate(value: object) -> Callable[[dict[str, Any]], None]:
    def change(parts: dict[str, Any]) -> None:
        geometry = parts["table"]["features"][0]["geometry"]
        geometry["coordinates"][0][1][0] = value

    change.__name__ = f"_coordinate_{value!r}"
    return change


def _on_axis(axis: int, token: str) -> Callable[[dict[str, Any]], None]:
    """One vertex coordinate as exact JSON text.

    Axis 0 is longitude in degrees. Axis 1 is latitude in degrees.
    """

    def change(parts: dict[str, Any]) -> None:
        ring = parts["table"]["features"][0]["geometry"]["coordinates"][0]
        ring[1][axis] = "RAW:" + token

    change.__name__ = f"_on_axis_{axis}_{token}"
    return change


# Just outside a signed degree bound, but float() rounds onto that bound.
_ROUNDS_ONTO_BOUND = (
    (0, "180.00000000000001"),
    (0, "-180.00000000000001"),
    (1, "90.000000000000007"),
    (1, "-90.000000000000007"),
)


def _coordinate_text(parts: dict[str, Any]) -> None:
    # The bare number 1e999 parses to a Decimal that overflows to infinity.
    _coordinate(RAW_OVERFLOW)(parts)


def _third_dimension(parts: dict[str, Any]) -> None:
    parts["table"]["features"][0]["geometry"]["coordinates"][0][1].append(4.0)


def _ring_not_list(parts: dict[str, Any]) -> None:
    parts["table"]["features"][0]["geometry"]["coordinates"][0] = {"a": [1, 2]}


def _inventory_publisher(parts: dict[str, Any]) -> None:
    del parts["inventory"]["source_chain"][INVENTORY_LINK["key"]]["publisher"]


def _inventory_url(parts: dict[str, Any]) -> None:
    parts["inventory"]["source_chain"][INVENTORY_LINK["key"]]["fetch_url"] = ""


def _inventory_empty(parts: dict[str, Any]) -> None:
    parts["inventory"]["source_chain"] = {}


def _inventory_other_table(parts: dict[str, Any]) -> None:
    parts["inventory"]["output_sha256"] = "0" * 64


def _landmark_publisher(parts: dict[str, Any]) -> None:
    del parts["manifest"]["landmark_heights"][0]["citation"]["publisher"]


def _landmark_hash(parts: dict[str, Any]) -> None:
    parts["manifest"]["landmark_heights"][0]["citation"]["page_sha256"] = "x"


def _landmarks_absent(parts: dict[str, Any]) -> None:
    del parts["manifest"]["landmark_heights"]


def _duplicate_source(parts: dict[str, Any]) -> None:
    parts["inventory"]["source_chain"][INVENTORY_LINK["key"]]["key"] = FETCHED[0]["key"]


def _after(plant: Callable[[dict[str, Any]], None]) -> Callable[..., None]:
    def change(parts: dict[str, Any]) -> None:
        parts["after"] = [plant]

    change.__name__ = "_after" + plant.__name__
    return change


def _record(parts: dict[str, Any], key: str) -> dict[str, Any]:
    return next(r for r in parts["manifest"]["files"] if r.get("key") == key)


def _chain_absent(parts: dict[str, Any]) -> None:
    del _record(parts, "building_table")["source_chain"]


def _chain_path(parts: dict[str, Any]) -> None:
    _record(parts, "building_table")["source_chain"]["path"] = "other.json"


def _landmark_record_absent(parts: dict[str, Any]) -> None:
    parts["manifest"]["files"].remove(_record(parts, "landmark_heights"))


def _repeated_read_key(parts: dict[str, Any]) -> None:
    parts["manifest"]["files"].append(copy.deepcopy(FETCHED[0]))


def _inventory_link_not_object(parts: dict[str, Any]) -> None:
    parts["inventory"]["source_chain"][INVENTORY_LINK["key"]] = "not-an-object"


def _landmark_citation_not_object(parts: dict[str, Any]) -> None:
    parts["manifest"]["landmark_heights"][0]["citation"] = "not-an-object"


def _fetched_date(parts: dict[str, Any]) -> None:
    parts["manifest"]["files"][0]["retrieved_utc"] = "not-a-date"


def _heights_role_read(parts: dict[str, Any]) -> None:
    _record(parts, "heights")["role"] = "read"


def _heights_digest(parts: dict[str, Any]) -> None:
    _record(parts, "heights")["sha256"] = "not-a-hash"


def _record_not_object(parts: dict[str, Any]) -> None:
    parts["manifest"]["files"].append("not-a-record")


def _features_not_list(parts: dict[str, Any]) -> None:
    parts["table"]["features"] = None


def _short_ring(parts: dict[str, Any]) -> None:
    del parts["table"]["features"][0]["geometry"]["coordinates"][0][2:]


def _row_not_object(parts: dict[str, Any]) -> None:
    parts["heights"][0] = "not-a-row"


def _rows_not_list(parts: dict[str, Any]) -> None:
    parts["heights"] = None


def _heights_not_json(parts: dict[str, Any]) -> None:
    parts["heights"] = "RAW:["


def _files_not_list(parts: dict[str, Any]) -> None:
    parts["manifest"]["files"] = None


def _coordinate_constant(parts: dict[str, Any]) -> None:
    _coordinate("RAW:NaN")(parts)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (_drop_publisher, "heights_lineage"),
        (_bad_height, "heights_row"),
        (_zero_height, "heights_row"),
        (_none_with_height, "heights_row"),
        (_unknown_source, "heights_row"),
        (_orphan_row, "heights_join"),
        (_orphan_footprint, "heights_join"),
        (_multipolygon, "heights_geometry"),
        (_zero_count, "heights_error_block"),
        (_float_error, "heights_error_block"),
        (_wrong_method, "heights_manifest_shape"),
        (_missing_fallback, "heights_error_block"),
        (_no_pairs_value, "heights_error_block"),
        (_no_pairs_count_false, "heights_error_block"),
        (_no_pairs_count_one, "heights_error_block"),
        (_no_pairs_extra, "heights_error_block"),
        (_statistics_extra, "heights_error_block"),
        (_statistics_field_missing, "heights_error_block"),
        (_statistics_reason_null, "heights_error_block"),
        (_statistics_count_true, "heights_error_block"),
        (_statistics_count_huge, "heights_error_block"),
        (_statistics_error_huge, "heights_error_block"),
        (_coordinate_text, "heights_geometry"),
        (_coordinate(True), "heights_geometry"),
        (_coordinate("51.5"), "heights_geometry"),
        (_coordinate(None), "heights_geometry"),
        (_coordinate(181), "heights_geometry"),
        (_coordinate(10**400), "heights_geometry"),
        *[
            (_on_axis(axis, token), "heights_geometry")
            for axis, token in _ROUNDS_ONTO_BOUND
        ],
        (_third_dimension, "heights_geometry"),
        (_ring_not_list, "heights_geometry"),
        (_coordinate_constant, "heights_file_integrity"),
        (_heights_not_json, "heights_file_integrity"),
        (_features_not_list, "heights_geometry"),
        (_short_ring, "heights_geometry"),
        (_row_not_object, "heights_row"),
        (_rows_not_list, "heights_row"),
        (_inventory_link_not_object, "heights_lineage"),
        (_inventory_publisher, "heights_lineage"),
        (_inventory_url, "heights_lineage"),
        (_inventory_empty, "heights_lineage"),
        (_inventory_other_table, "heights_lineage"),
        (_landmark_citation_not_object, "heights_lineage"),
        (_landmark_publisher, "heights_lineage"),
        (_landmark_hash, "heights_lineage"),
        (_fetched_date, "heights_lineage"),
        (_landmarks_absent, "heights_lineage"),
        (_duplicate_source, "heights_lineage"),
        (_after(_chain_absent), "heights_lineage"),
        (_after(_chain_path), "heights_lineage"),
        (_after(_landmark_record_absent), "heights_lineage"),
        (_after(_repeated_read_key), "heights_lineage"),
        (_after(_heights_role_read), "heights_manifest_shape"),
        (_after(_heights_digest), "heights_manifest_shape"),
        (_after(_record_not_object), "heights_manifest_shape"),
        (_after(_files_not_list), "heights_manifest_shape"),
    ],
)
def test_one_changed_input_refuses_with_its_reason(
    tmp_path: Path, change: Callable[[dict[str, Any]], None], reason: str
) -> None:
    folder, identity = released(tmp_path, change)
    with pytest.raises(HeightsRefusal, match=f"^{reason}$"):
        ReleasedBuildingHeights(folder, identity)


def test_altered_bytes_and_a_wrong_pin_are_refused(tmp_path: Path) -> None:
    folder, identity = released(tmp_path)
    with pytest.raises(HeightsRefusal, match=r"^heights_manifest_integrity$"):
        ReleasedBuildingHeights(folder, "../" + identity)
    with pytest.raises(HeightsRefusal, match=r"^heights_manifest_integrity$"):
        ReleasedBuildingHeights(folder, "a" * 64)
    manifest = folder / f"{identity}.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(HeightsRefusal, match=r"^heights_manifest_integrity$"):
        ReleasedBuildingHeights(folder, identity)
    manifest.write_bytes(manifest.read_bytes()[:-1])
    (folder / "heights.json").write_bytes(b"[]\n")
    with pytest.raises(HeightsRefusal, match=r"^heights_file_integrity$"):
        ReleasedBuildingHeights(folder, identity)


def test_a_linked_heights_file_refuses_the_path(tmp_path: Path) -> None:
    folder, identity = released(tmp_path)
    outside = tmp_path / "outside-heights.json"
    heights = folder / "heights.json"
    outside.write_bytes(heights.read_bytes())
    heights.unlink()
    heights.symlink_to(outside)
    with pytest.raises(HeightsRefusal, match=r"^heights_path_integrity$"):
        ReleasedBuildingHeights(folder, identity)


def _refusal(change: Callable[[dict[str, Any]], None]) -> str | None:
    """The read's closed refusal for one changed input, or None when it reads."""
    with tempfile.TemporaryDirectory(dir=Path.cwd() / ".overnight/tmp") as root:
        try:
            ReleasedBuildingHeights(*released(Path(root), change))
        except HeightsRefusal as refusal:
            return str(refusal)
    return None


_TOKENS = st.one_of(
    st.integers(min_value=-(10**400), max_value=10**400).map(str),
    st.decimals(allow_nan=False, allow_infinity=False).map(str),
    st.sampled_from(["1e999", "-1e999", "1e-999", "true", "false", "null"]),
    st.sampled_from(
        [
            '"51.5"',
            "[51.5]",
            "180",
            "-90.0",
            "180.0000001",
            *(token for _axis, token in _ROUNDS_ONTO_BOUND),
        ]
    ),
)


def _coordinate_accepted(token: str, limit: int) -> bool:
    """Independent oracle: a finite JSON number inside its range."""
    value = json.loads(token, parse_float=Decimal)
    if type(value) not in (int, Decimal):
        return False
    try:
        return Decimal(-limit) <= Decimal(value) <= Decimal(limit) and math.isfinite(
            float(value)
        )
    except OverflowError:
        return False


@settings(max_examples=60, deadline=None)
@given(token=_TOKENS, axis=st.sampled_from([0, 1]))
@example(token="180.00000000000001", axis=0)
@example(token="-180.00000000000001", axis=0)
@example(token="90.000000000000007", axis=1)
@example(token="-90.000000000000007", axis=1)
def test_any_coordinate_token_reads_only_as_a_finite_number(
    token: str, axis: int
) -> None:
    def change(parts: dict[str, Any]) -> None:
        ring = parts["table"]["features"][0]["geometry"]["coordinates"][0]
        # A JSON text token is set as text; any other is written bare.
        ring[1][axis] = json.loads(token) if token[0] == '"' else "RAW:" + token

    expected = (
        None if _coordinate_accepted(token, (180, 90)[axis]) else ("heights_geometry")
    )
    assert _refusal(change) == expected


_VALUES = st.sampled_from(
    [
        *(0, 1, 2, -1, 2**53, 2**53 + 1, True, False, None, 1.5),
        *("", "no_pairs", "other", "10.00", "-1.5", "0", "9" * 30, "1.234", "1e3"),
    ]
)
_FIELDS = [*sorted(ERRORS["wsf3d"]), "note"]


def _block_accepted(block: dict[str, Any]) -> bool:
    """Independent oracle of the producer's two closed error-block variants."""
    statistics = (
        "mean_absolute_error_m",
        "mean_signed_error_m",
        "median_absolute_error_m",
    )
    if sorted(block) != sorted(ERRORS["wsf3d"]):
        return False
    count = block["count"]
    if block["reason"] == "no_pairs":
        return (
            type(count) is int
            and count == 0
            and all(block[name] is None for name in statistics)
        )
    if block["reason"] != "" or type(count) is not int or not 0 < count <= 2**53:
        return False
    return all(
        isinstance(block[name], str)
        and re.fullmatch(r"-?[0-9]+(\.[0-9]{1,2})?", block[name]) is not None
        and float(block[name]) == float(Decimal(block[name]))
        and Decimal(repr(float(block[name]))) == Decimal(block[name])
        for name in statistics
    )


@settings(max_examples=80, deadline=None)
@given(block=st.dictionaries(st.sampled_from(_FIELDS), _VALUES, min_size=4))
def test_any_error_block_reads_only_as_a_closed_variant(
    block: dict[str, Any],
) -> None:
    def change(parts: dict[str, Any]) -> None:
        parts["manifest"]["errors"]["wsf3d"] = block

    expected = None if _block_accepted(block) else "heights_error_block"
    assert _refusal(change) == expected
