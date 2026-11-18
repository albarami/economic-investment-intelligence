"""Every listed real reader selects an older archive and refuses substitution.

Bodies, companies and source values in this file are invented.
"""

import json
from dataclasses import replace

import pytest

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.cache_fixture import select_fixture, write_cached

READERS = ("frame", "spine", "series", "grids", "places", "additions", "heights")


def entry_for(reader):
    extension = "parquet" if reader == "places" else "json"
    return replace(
        load_registry()[0],
        key="syn_source",
        source_id="syn_source",
        extension=extension,
    )


def read(reader, cache, entry, identity):
    if reader == "frame":
        from eii_custodian.publicdata.frame.build import read_cached

        rows, side = read_cached(cache, entry, digest=identity)
        return json.dumps(rows).encode(), side["sha256"]
    if reader == "spine":
        from eii_custodian.publicdata.review.cache_fixture import read_cached

        result = read_cached(cache, entry, digest=identity)
        return result.body, result.sidecar["sha256"]
    if reader == "series":
        from eii_custodian.publicdata.series.parse import selected_body

        body, side = selected_body(cache, entry, identity)
        return body, side["sha256"]
    if reader == "grids":
        from eii_custodian.publicdata.grids.build import cached_bytes

        body, side = cached_bytes(cache, entry)
        return body, side["sha256"]
    if reader == "places":
        from eii_custodian.publicdata.places.integrate import _receipt_of

        result = _receipt_of(cache, entry)
        if result is None:
            raise ValueError("syn-refused")
        path, side = result
        return path.read_bytes(), side.sha256
    if reader == "additions":
        from eii_custodian.publicdata.additions.build import _cached_export

        rows, side = _cached_export(cache, entry, identity)
        return json.dumps(rows).encode(), side["sha256"]
    from eii_custodian.publicdata.heights.read import _verified_body

    result = _verified_body(cache, entry)
    if result is None:
        raise ValueError("syn-refused")
    path, side = result
    return path.read_bytes(), side["sha256"]


def archives(tmp_path, reader):
    entry = entry_for(reader)
    old = write_cached(
        tmp_path, entry, b'[{"syn": "older"}]', retrieved_utc="2024-01-01T00:00:00Z"
    )
    new = write_cached(
        tmp_path, entry, b'[{"syn": "newer"}]', retrieved_utc="2024-02-01T00:00:00Z"
    )
    select_fixture(tmp_path, entry.key, old.stem)
    return entry, old, new


@pytest.mark.parametrize("reader", READERS)
def test_actual_reader_selects_referenced_older_of_two_without_aliases(
    tmp_path, reader
):
    entry, old, new = archives(tmp_path, reader)
    # An archive consumer must not need the compatibility copies at the root.
    for path in (tmp_path / entry.key).glob("*.*"):
        if path.is_file():
            path.unlink()
    body, digest = read(reader, tmp_path, entry, old.stem)
    assert json.loads(body) == [{"syn": "older"}]
    assert digest == old.stem
    assert new.is_file()


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("target", ["body", "receipt"])
def test_actual_reader_refuses_substituted_selected_hash(tmp_path, reader, target):
    entry, old, new = archives(tmp_path, reader)
    if target == "body":
        old.write_bytes(new.read_bytes())
    else:
        receipt = old.with_suffix(".meta.json")
        side = json.loads(receipt.read_text())
        side["publisher"] = "SYN-substituted-publisher"
        receipt.write_text(json.dumps(side))
    with pytest.raises((ValueError, AdditionError)):
        read(reader, tmp_path, entry, old.stem)


@pytest.mark.parametrize("reader", READERS)
def test_actual_reader_does_not_fall_back_when_selected_older_is_missing(
    tmp_path, reader
):
    entry, old, new = archives(tmp_path, reader)
    old.unlink()
    with pytest.raises((ValueError, AdditionError)):
        read(reader, tmp_path, entry, old.stem)
    assert new.is_file()


@pytest.mark.parametrize("reader", ["grids", "heights"])
def test_implicit_reader_requires_reviewed_pin_even_with_one_compatibility_copy(
    tmp_path, reader
):
    entry = entry_for(reader)
    path = write_cached(tmp_path, entry, b"[]")
    (tmp_path / "snapshot_pins.json").unlink()
    with pytest.raises((ValueError, AdditionError)):
        read(reader, tmp_path, entry, path.stem)


@pytest.mark.parametrize("reader", ["additions", "heights"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "syn_other"),
        ("key", "syn_other"),
        ("licence_id", "syn_other"),
        ("licence_basis", "syn_other"),
        ("switched_off", True),
    ],
)
def test_selected_receipt_must_still_match_the_registered_reader(
    tmp_path, reader, field, value
):
    from custodian.tests.snapshot_fixture import update_receipt

    entry = entry_for(reader)
    path = write_cached(tmp_path, entry, b"[]")
    update_receipt(tmp_path, entry.key, path.stem, {field: value})
    with pytest.raises((ValueError, AdditionError)):
        read(reader, tmp_path, entry, path.stem)


@pytest.mark.parametrize("reader", ["additions", "heights"])
def test_archived_extension_must_match_the_reader(tmp_path, reader):
    entry = entry_for(reader)
    path = write_cached(tmp_path, entry, b"[]")
    with pytest.raises((ValueError, AdditionError)):
        read(reader, tmp_path, replace(entry, extension="csv"), path.stem)


def test_height_reader_retains_duplicate_receipt_field_refusal(tmp_path):
    import hashlib

    from eii_custodian.publicdata.heights.model import HeightError

    entry = entry_for("heights")
    path = write_cached(tmp_path, entry, b"[]")
    receipt = path.with_suffix(".meta.json")
    text = receipt.read_text()
    receipt.write_text(text.rstrip()[:-1] + ', "publisher": "syn-duplicate"}')
    index = tmp_path / entry.key / "index" / (path.stem + ".json")
    record = json.loads(index.read_text())
    record["receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    index.write_text(json.dumps(record))
    with pytest.raises(HeightError) as error:
        read("heights", tmp_path, entry, path.stem)
    assert error.value.name == "cache_receipt"
    assert error.value.detail == "publisher"


def test_height_duplicate_scan_cannot_replace_verified_receipt_metadata(
    tmp_path, monkeypatch
):
    from pathlib import Path

    from eii_custodian.publicdata.heights.model import HeightError

    entry = entry_for("heights")
    path = write_cached(tmp_path, entry, b"[]")
    receipt = path.with_suffix(".meta.json")
    alternate = json.loads(receipt.read_text())
    alternate["publisher"] = "SYN-unverified-reread"
    original = Path.read_text

    def changed_read(target, *args, **kwargs):
        if target == receipt:
            return json.dumps(alternate)
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", changed_read)
    with pytest.raises(HeightError) as error:
        read("heights", tmp_path, entry, path.stem)
    assert error.value.name == "selected_input_refused"
