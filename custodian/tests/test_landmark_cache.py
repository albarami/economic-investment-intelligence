"""Cache placement, kinds, and snapshot excerpt guards with invented records."""

from dataclasses import replace

import pytest
import yaml
from custodian.tests.test_publicdata_heights import (
    _cited_page,
    _fixture_registry,
    _landmark_document,
)

from eii_custodian.publicdata.heights import landmarks
from eii_custodian.publicdata.heights.calibration import landmark_calibration
from eii_custodian.publicdata.heights.model import HeightError


def test_cache_record_is_the_only_list(tmp_path, monkeypatch):
    _fixture_registry(monkeypatch)
    path = tmp_path / "review/landmark_heights.yaml"
    path.parent.mkdir()
    document = _landmark_document()
    document["entries"][0]["height_kind"] = "roof"
    path.write_text(yaml.safe_dump(document))
    assert landmarks.landmark_heights_path(tmp_path) == path
    assert landmarks.load_landmark_heights(path)[0].height_kind == "roof"


@pytest.mark.parametrize("kind", ["tip", "Roof", None, ["roof"]])
def test_kind_is_required_closed_value(tmp_path, monkeypatch, kind):
    _fixture_registry(monkeypatch)
    document = _landmark_document()
    document["entries"][0]["height_kind"] = kind
    path = tmp_path / "hand.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(HeightError) as error:
        landmarks.load_landmark_heights(path)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_entry",
        "height_kind",
    )


def test_empty_without_pending_stays_pending(tmp_path):
    path = tmp_path / "hand.yaml"
    path.write_text("version: 1\nentries: []\n")
    rows = landmarks.load_landmark_heights(path)
    assert landmark_calibration(rows, "")["pending"] == "landmark_list_empty"
    assert (
        landmark_calibration(rows, "basemap_building_ids_unconfirmed")["pending"]
        == "basemap_building_ids_unconfirmed"
    )


def test_nonempty_verified_list_has_kind_counts(tmp_path, monkeypatch):
    _cache, _, _, rows, verify = _cited_page(tmp_path, monkeypatch)
    verify()
    assert landmark_calibration(rows, "") == {
        "landmark_count": 1,
        "pending": "",
        "by_kind": {"roof": 1, "architectural": 0},
    }


def test_excerpt_absent_is_specific_refusal(tmp_path, monkeypatch):
    cache, _, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    changed = (
        replace(
            rows[0],
            citation=replace(rows[0].citation, height_excerpt="SYN absent excerpt"),
        ),
    )
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, changed)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "excerpt_absent",
    )


def test_cache_symlink_is_refused(tmp_path):
    (tmp_path / "review").mkdir()
    (tmp_path / "review/landmark_heights.yaml").symlink_to(
        landmarks.LANDMARK_HEIGHTS_PATH
    )
    with pytest.raises(HeightError) as error:
        landmarks.landmark_heights_path(tmp_path)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights",
        "cache_path_refused",
    )


def test_height_token_must_belong_to_present_excerpt(tmp_path, monkeypatch):
    cache, _, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    from decimal import Decimal

    changed = (replace(rows[0], height_m=Decimal("201.00")),)
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, changed)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "height_excerpt_mismatch",
    )


def test_duplicate_yaml_key_cannot_replace_a_height(tmp_path, monkeypatch):
    _fixture_registry(monkeypatch)
    document = _landmark_document()
    body = yaml.safe_dump(document, sort_keys=False)
    body = body.replace("  height_m:", "  height_m: '201.00'\n  height_m:")
    path = tmp_path / "hand.yaml"
    path.write_text(body)
    with pytest.raises(HeightError) as error:
        landmarks.load_landmark_heights(path)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights",
        "duplicate_key",
    )


@pytest.mark.parametrize(
    "body",
    [
        b"<p>Roof: <span>200.</span><b>00</b> m</p>",
        b"<p>Roof:\n 200.00\t m</p>",
    ],
)
def test_split_and_fused_inline_text_preserves_the_excerpt(tmp_path, monkeypatch, body):
    cache, row, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    from custodian.tests.fixtures.heights import invented

    digest = invented.store(cache, row, body, publisher=row.publisher)
    changed = (
        replace(rows[0], citation=replace(rows[0].citation, page_sha256=digest)),
    )
    assert landmarks.verify_landmark_receipts(cache, changed) is None


def test_nonbreaking_space_stays_significant(tmp_path, monkeypatch):
    cache, row, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    from custodian.tests.fixtures.heights import invented

    digest = invented.store(
        cache, row, b"<p>Roof: 200.00&nbsp;m</p>", publisher=row.publisher
    )
    changed = (
        replace(
            rows[0],
            citation=replace(
                rows[0].citation,
                page_sha256=digest,
                height_excerpt="Roof: 200.00\u00a0m",
            ),
        ),
    )
    assert landmarks.verify_landmark_receipts(cache, changed) is None
    absent = (
        replace(
            changed[0],
            citation=replace(changed[0].citation, height_excerpt="Roof: 200.00 m"),
        ),
    )
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, absent)
    assert error.value.detail == "excerpt_absent"


def test_height_step_reads_and_hashes_the_local_record(tmp_path, monkeypatch):
    import json

    from custodian.tests.fixtures.heights import invented
    from custodian.tests.test_publicdata_heights import fixture_heights

    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.heights.landmark_tie import (
        Ties,
        write_landmark_heights,
    )

    cache, row, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    document = {"version": 1, "entries": [landmarks.landmark_record(rows[0])]}
    target = write_landmark_heights(
        cache, Ties(document, ((rows[0].landmark_id, "tied"),))
    )
    buildings = tmp_path / "buildings.geojson"
    buildings.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    rows[0].building_id, invented.square(0, 0, 1), None, None
                )
            ]
        )
    )
    output = tmp_path / "out"
    fixture_heights(
        cache,
        (row,),
        buildings,
        output,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    manifest = json.loads((output / "manifest.heights.json").read_bytes())
    assert manifest["landmark_heights"][0]["height_kind"] == "roof"
    assert manifest["gba_calibration"]["pending"] == ""
    assert manifest["gba_calibration"]["landmark_count"] == 1
    record = next(f for f in manifest["files"] if f["key"] == "landmark_heights")
    assert record["path"] == "review/landmark_heights.yaml"
    assert record["sha256"] == sha256_hex(target.read_bytes())


def test_kind_must_belong_to_present_excerpt(tmp_path, monkeypatch):
    cache, _, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    changed = (replace(rows[0], height_kind="architectural"),)
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, changed)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "height_excerpt_mismatch",
    )


def test_symlink_review_directory_is_refused_even_inside_cache(tmp_path):
    (tmp_path / "SYN-local").mkdir()
    (tmp_path / "review").symlink_to(tmp_path / "SYN-local", target_is_directory=True)
    with pytest.raises(HeightError) as error:
        landmarks.landmark_heights_path(tmp_path)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights",
        "cache_path_refused",
    )


def test_loaded_record_keeps_the_exact_validated_bytes(tmp_path, monkeypatch):
    _fixture_registry(monkeypatch)
    document = _landmark_document()
    path = tmp_path / "hand.yaml"
    before = yaml.safe_dump(document, sort_keys=False).encode()
    path.write_bytes(before)
    record = landmarks.load_landmark_record(path)
    path.write_text("version: 1\nentries: []\n")
    assert record.body == before
    assert record.rows[0].height_kind == "roof"
    assert record.pending == ""


@pytest.mark.parametrize("plant", ["absolute", "parent", "symlink"])
def test_citation_cache_boundary_has_closed_refusal(tmp_path, monkeypatch, plant):
    from custodian.tests.test_publicdata_heights import _rewrite_receipt

    cache, row, digest, rows, verify = _cited_page(tmp_path, monkeypatch)
    verify()
    directory = cache / row.key
    if plant == "symlink":
        relocated = tmp_path / "SYN-relocated-entry"
        directory.rename(relocated)
        directory.symlink_to(relocated, target_is_directory=True)
    else:
        key = str(directory) if plant == "absolute" else "../cache/" + row.key
        row = replace(row, key=key)
        _rewrite_receipt(cache, row.key, digest, {"key": row.key})
        monkeypatch.setattr(landmarks, "_registry_by_url", lambda: {row.url: row})
    with pytest.raises(HeightError) as error:
        landmarks.verify_landmark_receipts(cache, rows)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "page_snapshot",
    )
