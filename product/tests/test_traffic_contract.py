"""Reject incomplete or mismatched release artefacts before calling the engine."""

import json
from pathlib import Path

import pytest

from eii_product.areas_spike.traffic import Traffic

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike" / "assignment"


def load_changed(tmp_path, payload):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(payload))
    return Traffic.load(
        path, FIXTURES / "hourly_roads.json", FIXTURES / "hourly_parameters.json"
    )


@pytest.mark.parametrize(
    "section,field",
    [
        ("header", field)
        for field in [
            "method",
            "sources",
            "provenance",
            "evidence_status",
            "caveat",
            "withheld_note",
        ]
    ]
    + [
        ("method", "id"),
        ("method", "parameters_sha256"),
        ("sources", "flow_hourly"),
        ("sources", "road_link"),
    ]
    + [
        ("row", field)
        for field in [
            "link_id",
            "day_type",
            "hour",
            "summer",
            "speed_ratio",
            "volume_band",
        ]
    ],
)
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_closed_header_and_row_shapes(tmp_path, section, field, operation):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    target = (
        payload["rows"][0]
        if section == "row"
        else payload["header"]
        if section == "header"
        else payload["header"][section]
    )
    if operation == "missing":
        del target[field]
    else:
        target[field + "_extra"] = "invented"
    with pytest.raises(ValueError, match="missing or unknown"):
        load_changed(tmp_path, payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("provenance", "Public"),
        ("evidence_status", "inferred"),
        ("caveat", "invented"),
        ("withheld_note", ""),
    ],
)
def test_header_values_refused(tmp_path, field, value):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    payload["header"][field] = value
    with pytest.raises(ValueError, match=field):
        load_changed(tmp_path, payload)


@pytest.mark.parametrize(
    "section,field,value,message",
    [
        ("method", "id", "C26", "method: expected C25"),
        ("method", "parameters_sha256", "0" * 64, "parameters_sha256: digest mismatch"),
        ("sources", "road_link", "0" * 64, "road_link: digest mismatch"),
        ("sources", "flow_hourly", "invented", "flow_hourly: expected SHA-256"),
    ],
)
def test_method_and_hashes_refused(tmp_path, section, field, value, message):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    payload["header"][section][field] = value
    with pytest.raises(ValueError, match=message):
        load_changed(tmp_path, payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("link_id", "SYN-L-999"),
        ("day_type", "weekend"),
        ("hour", "24"),
        ("hour", "-1"),
        ("hour", "8"),
        ("hour", 8.0),
        ("hour", True),
        ("hour", False),
        ("hour", -1),
        ("hour", 24),
        ("summer", "false"),
        ("summer", 0),
        ("speed_ratio", "0.000"),
        ("speed_ratio", "1.001"),
        ("speed_ratio", "0.8"),
        ("speed_ratio", 0.7),
        ("volume_band", "vb99"),
    ],
    ids=lambda value: f"{type(value).__name__}-{value}",
)
def test_row_values_refused(tmp_path, field, value):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    payload["rows"][0][field] = value
    with pytest.raises(ValueError):
        load_changed(tmp_path, payload)


def test_duplicate_key_refused(tmp_path):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    payload["rows"].append(payload["rows"][0])
    with pytest.raises(ValueError, match="duplicate"):
        load_changed(tmp_path, payload)


@pytest.mark.parametrize(
    "day_type,hour,summer",
    [("weekend", 8, False), ("weekday", "24", False), ("weekday", 8, "false")],
)
def test_area_lookup_uses_all_situation_keys(day_type, hour, summer):
    traffic = Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )
    with pytest.raises(ValueError, match="Unknown"):
        traffic.speed_vector(hour, day_type, summer)
