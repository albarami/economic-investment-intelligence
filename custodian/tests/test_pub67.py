"""PUB-67 calculations and corruptions over invented, selected inputs only."""

import copy
import json
from dataclasses import replace

import pytest

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import parse_isic_rows
from eii_custodian.publicdata.review.cache_fixture import class_csv, write_cached
from eii_custodian.publicdata.series.figures import (
    build_series,
    compute_checks,
    finish_build,
)
from eii_custodian.publicdata.series.parse import Municipality
from eii_custodian.publicdata.stage import run_stage

FRAME = (
    Municipality("SYN-TARGET", "بلدية الظعاين"),
    Municipality("SYN-OTHER", "بلدية الدوحة"),
)
LOCAL = {
    "rows": "9",
    "sum_count": "45",
    "distinct_codes": "7",
    "isic_prefix": "15",
    "other_seven": "6",
    "legacy_six": "7",
    "other_lengths": "17",
    "al_daayen_5610101": "3",
    "national_5610101": "6",
}


def active_rows():
    specs = [
        ("5610101", 1),
        ("5610101", 2),
        ("5610101", 3),
        ("1234001", 9),
        ("9999001", 6),
        ("561010", 7),
        ("12345", 4),
        ("1234" + "5678", 5),
        ("123", 8),
    ]
    return [
        {
            "lbldy": FRAME[1 if index == 2 else 0].name_ar,
            "rmz_lnsht_ltjry": code,
            "lnsht_ltjry": "SYN activity " + code,
            "dd_lrkhs_lnsht": count,
        }
        for index, (code, count) in enumerate(specs)
    ]


def classes():
    return parse_isic_rows(
        [{"Code": code, "Description": "SYN class"} for code in ("5610", "1234")]
    ).classes


def calculated(rows=None, frame=FRAME):
    return compute_checks(
        {"lic_active": active_rows() if rows is None else rows},
        isic_classes=classes(),
        municipalities=frame,
    )["PUB-67"]


def selected_fixture(cache):
    keys = ("lic_active", "cls_isic4", "bnd_hdx", "bnd_zone_2020")
    entries = [
        replace(next(e for e in load_registry() if e.key == key), skip_reason="")
        for key in keys
    ]
    bodies = [
        json.dumps(active_rows()).encode(),
        class_csv([("5610", "SYN"), ("1234", "SYN")]),
        b"SYN boundary",
        b"SYN zone",
    ]
    selected = {}
    for entry, body in zip(entries, bodies, strict=True):
        write_cached(cache, entry, body)
        selected[entry.key] = sha256_hex(body)
    path = cache / "frame_s2_t02/municipalities.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "count": 2,
                "upstream_sha256": {
                    k: selected[k] for k in ("bnd_hdx", "bnd_zone_2020")
                },
                "municipalities": [
                    {"municipality_code": m.code, "name_ar": m.name_ar} for m in FRAME
                ],
            }
        )
    )
    return entries, selected


def build(cache, entries, selected):
    return build_series(
        cache,
        entries,
        {"lic_active": selected["lic_active"]},
        municipalities=FRAME,
        supporting_selected={k: v for k, v in selected.items() if k != "lic_active"},
    )


def test_pub67_all_nine_values_structural_unreviewed_and_frame_key():
    assert calculated() == LOCAL
    assert calculated([]) == {**LOCAL, **dict.fromkeys(LOCAL, "0")}


def test_pub67_municipal_count_plant_keeps_national_total():
    rows = active_rows()
    rows[0]["dd_lrkhs_lnsht"] = 0
    rows[2]["dd_lrkhs_lnsht"] = 4
    observed = calculated(rows)
    assert observed == {**LOCAL, "al_daayen_5610101": "2"}


@pytest.mark.parametrize(
    "frame",
    [
        (),
        (FRAME[1],),
        (Municipality("SYN-A", "الظعاين"), FRAME[0]),
        (Municipality("SYN-A", "unreviewed"),),
    ],
)
def test_pub67_absent_ambiguous_unreviewed_target_refused(frame):
    with pytest.raises(ValueError, match="target municipality"):
        calculated(frame=frame)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rmz_lnsht_ltjry", "bad-code"),
        ("dd_lrkhs_lnsht", -1),
        ("dd_lrkhs_lnsht", True),
        ("lbldy", "unreviewed"),
    ],
)
def test_pub67_bad_source_refused(field, value):
    rows = active_rows()
    rows[0][field] = value
    with pytest.raises(ValueError):
        calculated(rows)


def test_pub67_selected_support_and_stage_admission(tmp_path, monkeypatch):
    entries, selected = selected_fixture(tmp_path)
    # An old, valid classification alongside the selected one is never chosen.
    write_cached(tmp_path, entries[1], class_csv([("9999", "SYN old")]))
    result = build(tmp_path, entries, selected)
    assert result["checks"]["PUB-67"] == LOCAL
    assert result["blocked"] == {}
    path = tmp_path / "series/regression/PUB-67.json"
    envelope = json.loads(path.read_text())
    support = envelope["supporting_provenance"]
    assert support["classification"]["sha256"] == selected["cls_isic4"]
    assert support["classification"]["source_id"] == "cls_isic4"
    assert "slug" not in support["classification"]
    assert support["frame"]["sha256"] == sha256_hex(
        (tmp_path / "frame_s2_t02/municipalities.json").read_bytes()
    )
    monkeypatch.setitem(
        __import__("eii_custodian.publicdata.stage", fromlist=["EXPECTED"]).EXPECTED,
        "PUB-67",
        LOCAL,
    )
    assert run_stage(tmp_path, required=("PUB-67",)).mismatch == ""
    for key in LOCAL:
        for missing in (False, True):
            planted = copy.deepcopy(envelope)
            if missing:
                del planted["values"][key]
            else:
                planted["values"][key] = "wrong"
            path.write_text(json.dumps(planted))
            assert run_stage(tmp_path, required=("PUB-67",)).mismatch == "PUB-67"
    path.write_text(json.dumps(envelope))
    for key in support:
        planted = copy.deepcopy(envelope)
        del planted["supporting_provenance"][key]
        path.write_text(json.dumps(planted))
        with pytest.raises(ValueError, match="supporting provenance"):
            run_stage(tmp_path, required=("PUB-67",))


@pytest.mark.parametrize(
    "plant",
    [
        "missing_support",
        "missing_receipt",
        "body",
        "receipt",
        "missing_frame",
        "frame_disagrees",
        "no_classes",
    ],
)
def test_pub67_selected_support_plants(tmp_path, plant):
    entries, selected = selected_fixture(tmp_path)
    if plant == "missing_support":
        del selected["cls_isic4"]
    elif plant == "missing_receipt":
        (tmp_path / "cls_isic4" / (selected["cls_isic4"] + ".meta.json")).unlink()
    elif plant == "body":
        (tmp_path / "cls_isic4" / (selected["cls_isic4"] + ".csv")).write_bytes(
            b"wrong"
        )
    elif plant == "receipt":
        path = tmp_path / "cls_isic4" / (selected["cls_isic4"] + ".meta.json")
        meta = json.loads(path.read_text())
        meta["source_id"] = "wrong"
        path.write_text(json.dumps(meta))
    elif plant == "missing_frame":
        (tmp_path / "frame_s2_t02/municipalities.json").unlink()
    elif plant == "frame_disagrees":
        (tmp_path / "frame_s2_t02/municipalities.json").write_text("{}")
    else:
        body = class_csv([("A", "SYN section")])
        write_cached(tmp_path, entries[1], body)
        selected["cls_isic4"] = sha256_hex(body)
    result = build(tmp_path, entries, selected)
    assert "lic_active" in result["blocked"]
    assert "PUB-67" not in result["checks"]
    assert not (tmp_path / "series/regression/PUB-67.json").exists()


@pytest.mark.parametrize("plant", ["missing", "duplicate", "entry_duplicate", "valid"])
def test_finish_build_selects_exact_support(tmp_path, plant):
    entries, selected = selected_fixture(tmp_path)
    lines = [
        f"PASS {key} sha256={digest} host=invented" for key, digest in selected.items()
    ]
    if plant == "missing":
        lines = [line for line in lines if not line.startswith("PASS cls_isic4 ")]
    elif plant == "duplicate":
        lines.append(lines[1])
    elif plant == "entry_duplicate":
        entries.append(entries[1])
    result = finish_build(entries, tmp_path, lines)
    assert result is not None
    if plant == "valid":
        assert result.source_id == "PUB-67"  # invented values differ from pack anchors
        assert (
            json.loads((tmp_path / "series/regression/PUB-67.json").read_text())[
                "values"
            ]
            == LOCAL
        )
    else:
        assert not (tmp_path / "series/regression/PUB-67.json").exists()


@pytest.mark.parametrize(
    "path,value",
    [
        (("classification", "dataset"), ""),
        (("classification", "publisher"), 3),
        (("classification", "licence_basis"), ""),
        (("classification", "retrieved_utc"), "bad"),
        (("classification", "sha256"), "bad"),
        (("classification", "source_id"), "wrong"),
        (("classification", "slug"), "invented"),
        (("schema",), "wrong"),
        (("classifier_version",), "wrong"),
        (("frame", "output"), "wrong"),
        (("frame", "sha256"), "bad"),
        (("frame", "method"), "wrong"),
        (("frame", "upstream"), []),
        (("frame", "review_sha256"), {}),
        (("frame", "review_sha256", "municipality_names.csv"), "bad"),
    ],
)
def test_pub67_nested_lineage_plants(tmp_path, path, value):
    from eii_custodian.publicdata.series.support import validate_support

    entries, selected = selected_fixture(tmp_path)
    build(tmp_path, entries, selected)
    support = json.loads((tmp_path / "series/regression/PUB-67.json").read_text())[
        "supporting_provenance"
    ]
    row = support
    for key in path[:-1]:
        row = row[key]
    row[path[-1]] = value
    with pytest.raises(ValueError, match="supporting provenance"):
        validate_support(support)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title_en", ""),
        ("title_en", 3),
        ("publisher", ""),
        ("retrieved_utc", "bad"),
        ("licence_basis", "wrong"),
        ("key", "wrong"),
        ("release_tables", ["invented"]),
    ],
)
def test_pub67_support_receipt_lineage_plants(tmp_path, field, value):
    entries, selected = selected_fixture(tmp_path)
    path = tmp_path / "cls_isic4" / (selected["cls_isic4"] + ".meta.json")
    receipt = json.loads(path.read_text())
    receipt[field] = value
    path.write_text(json.dumps(receipt))
    result = build(tmp_path, entries, selected)
    assert "lic_active" in result["blocked"]
    assert "PUB-67" not in result["checks"]


def test_pub67_upstream_frame_binding_plant(tmp_path):
    entries, selected = selected_fixture(tmp_path)
    path = tmp_path / "frame_s2_t02/municipalities.json"
    frame = json.loads(path.read_text())
    frame["upstream_sha256"]["bnd_hdx"] = "a" * 64
    path.write_text(json.dumps(frame))
    result = build(tmp_path, entries, selected)
    assert "lic_active" in result["blocked"]
    assert "PUB-67" not in result["checks"]


@pytest.mark.parametrize("field", ["total_active", "seven_valid_prefix"])
def test_pub67_bucket_reconciliation_plant(monkeypatch, field):
    from eii_custodian.publicdata.series import figures

    original = figures.class_bucket_counts

    def planted(*args):
        buckets = original(*args)
        return replace(buckets, **{field: getattr(buckets, field) + 1})

    monkeypatch.setattr(figures, "class_bucket_counts", planted)
    with pytest.raises(ValueError, match="bucket reconciliation"):
        calculated()


@pytest.mark.parametrize(
    "plant",
    [
        "invalid_hash",
        "non_object_receipt",
        "extra_selection",
        "duplicate_registry",
        "missing_registry",
    ],
)
def test_pub67_selected_support_shape_plants(tmp_path, plant):
    entries, selected = selected_fixture(tmp_path)
    if plant == "invalid_hash":
        selected["cls_isic4"] = "invalid"
    elif plant == "non_object_receipt":
        (tmp_path / "cls_isic4" / (selected["cls_isic4"] + ".meta.json")).write_text(
            "[]"
        )
    elif plant == "extra_selection":
        selected["unknown"] = "a" * 64
    elif plant == "duplicate_registry":
        entries.append(entries[1])
    else:
        entries = [entry for entry in entries if entry.key != "cls_isic4"]
    result = build(tmp_path, entries, selected)
    assert "lic_active" in result["blocked"]
    assert "PUB-67" not in result["checks"]
