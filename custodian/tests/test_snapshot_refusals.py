"""Site-specific invented archive violations; exact diagnostics are the contract."""

import hashlib
import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch import snapshots as archive

SIDE = {
    "source_id": "syn_source",
    "key": "syn_source",
    "retrieved_utc": "2024-01-31T00:00:00Z",
}

# Each ID identifies one refusal site, including separate sites sharing a reason.
PLANTS = [
    ("utc_type", "snapshot_date_missing"),
    ("utc_parse", "snapshot_date_missing"),
    ("utc_zone", "snapshot_date_missing"),
    ("object_read", "snapshot_index_invalid"),
    ("object_shape", "snapshot_index_invalid"),
    ("body_hash", "snapshot_hash_mismatch"),
    ("read_identity", "snapshot_path_invalid"),
    ("read_digest", "snapshot_index_invalid"),
    ("read_extension", "snapshot_index_invalid"),
    ("read_path", "snapshot_path_invalid"),
    ("read_receipt_path", "snapshot_path_invalid"),
    ("read_escape", "snapshot_path_invalid"),
    ("read_receipt_hash", "snapshot_hash_mismatch"),
    ("read_missing", "snapshot_missing"),
    ("read_body_hash", "snapshot_hash_mismatch"),
    ("read_size", "snapshot_hash_mismatch"),
    ("read_side_fields", "snapshot_index_invalid"),
    ("publish_outer_write", "syn_source: snapshot_write_failed"),
    ("publish_file_write", "syn_source: snapshot_write_failed"),
    ("publish_path", "snapshot_path_invalid"),
    ("publish_side", "snapshot_index_invalid"),
    ("publish_digest", "snapshot_hash_mismatch"),
    ("publish_conflict_body", "snapshot_conflict"),
    ("publish_conflict_source", "snapshot_conflict"),
    ("publish_inner_write", "snapshot_write_failed"),
    ("selection", "snapshot_selection_invalid"),
    ("check_hash", "snapshot_hash_mismatch"),
    ("check_identity", "snapshot_index_invalid"),
    ("check_fields", "snapshot_index_invalid"),
]


def fail_io(*args, **kwargs):
    raise OSError("syn-diagnostic")


@pytest.mark.parametrize("plant,reason", PLANTS, ids=[p[0] for p in PLANTS])
def test_snapshot_refusal_site(tmp_path, monkeypatch, plant, reason):
    directory = tmp_path / "syn-cache"
    ref = archive.publish_snapshot(directory, "json", b"syn-body", SIDE)
    index = directory / "index" / (ref.sha256 + ".json")
    row = json.loads(index.read_text())
    receipt = directory / row["receipt"]
    staged = tmp_path / "syn-staged"
    staged.write_bytes(b"syn-body")

    def read():
        return archive.read_snapshot(directory, ref.sha256)

    action = read
    if plant.startswith("utc_"):
        value = {
            "utc_type": None,
            "utc_parse": "syn-invalid",
            "utc_zone": "2024-01-31T00:00:00",
        }[plant]

        def action():
            return archive.utc(value)
    elif plant.startswith("object_"):
        target = tmp_path / "syn-object"
        if plant == "object_shape":
            target.write_text("[]")

        def action():
            return archive._object(target)
    elif plant == "body_hash":
        ref.path.write_bytes(b"syn-tamper")

        def action():
            return ref.body
    elif plant == "read_identity":

        def action():
            return archive.read_snapshot(directory, "syn-invalid")
    elif plant in {
        "read_digest",
        "read_extension",
        "read_path",
        "read_receipt_path",
        "read_size",
    }:
        key, value = {
            "read_digest": ("sha256", "syn-invalid"),
            "read_extension": ("extension", "../syn"),
            "read_path": ("path", "../syn"),
            "read_receipt_path": ("receipt", "syn-alternate.meta.json"),
            "read_size": ("bytes", 999),
        }[plant]
        if plant == "read_receipt_path":
            (directory / value).write_bytes(receipt.read_bytes())
        row[key] = value
        index.write_text(json.dumps(row))
    elif plant == "read_escape":
        outside = tmp_path / "syn-outside"
        outside.write_bytes(ref.path.read_bytes())
        ref.path.unlink()
        ref.path.symlink_to(outside)
    elif plant == "read_receipt_hash":
        receipt.write_text("{}")
    elif plant == "read_missing":
        ref.path.unlink()
    elif plant == "read_body_hash":
        ref.path.write_bytes(b"syn-fake")
    elif plant == "read_side_fields":
        side = json.loads(receipt.read_text())
        side["key"] = "syn-other"
        receipt.write_text(json.dumps(side))
        row["receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
        index.write_text(json.dumps(row))
    elif plant == "publish_outer_write":
        monkeypatch.setattr(Path, "write_bytes", fail_io)

        def action():
            return archive.publish_snapshot(directory, "json", b"syn-body", SIDE)
    elif plant == "publish_file_write":
        monkeypatch.setattr(archive, "file_hash", fail_io)

        def action():
            return archive.publish_file(directory, "json", staged, SIDE)
    elif plant in {"publish_path", "publish_side", "publish_digest"}:
        side = dict(SIDE)
        ext = "json"
        if plant == "publish_path":
            ext = "../syn"
        elif plant == "publish_side":
            side["source_id"] = ""
        else:
            side["sha256"] = "a" * 64

        def action():
            return archive.publish_file(directory, ext, staged, side)
    elif plant == "publish_conflict_body":

        def action():
            return archive.publish_snapshot(
                directory, "json", b"syn-other", SIDE, identity=ref.sha256
            )
    elif plant == "publish_conflict_source":

        def action():
            return archive.publish_snapshot(
                directory, "json", b"syn-body", dict(SIDE, key="syn-other")
            )
    elif plant == "publish_inner_write":
        monkeypatch.setattr(archive, "_publish", fail_io)

        def action():
            return archive.publish_file(directory, "json", staged, SIDE)
    elif plant == "selection":
        (directory / "snapshot_pins.json").write_text('{"syn_source": "bad"}')

        def action():
            return archive.reviewed_selections(directory)
    else:
        check = next((directory / "checks").glob("*.json"))
        payload = json.loads(check.read_text())
        if plant == "check_hash":
            check.write_text("{}")
        else:
            payload["identity" if plant == "check_identity" else "key"] = (
                None if plant == "check_identity" else "syn-other"
            )
            check.unlink()
            body = json.dumps(payload).encode()
            (
                directory / "checks" / (hashlib.sha256(body).hexdigest() + ".json")
            ).write_bytes(body)

        def action():
            return archive.checked_times(directory)

    with pytest.raises(archive.SnapshotError, match="^" + reason + "$"):
        action()


@pytest.mark.parametrize(
    "value,reason",
    [
        (None, "cadence_missing"),
        ({"value": "none", "syn": "extra"}, "cadence_unknown"),
        ({"value": "syn-unknown"}, "cadence_unknown"),
        ({"value": "none", "reason": 3}, "cadence_unknown"),
        ({"value": "none"}, "cadence_reason_missing"),
        ({"value": "weekly"}, "cadence_frequency_unconfirmed"),
    ],
)
def test_cadence_refusal_site(value, reason):
    from eii_custodian.publicdata.fetch.cadence import parse_cadence

    with pytest.raises(ValueError, match="^" + reason + "$"):
        parse_cadence(value)


def test_clock_refusal_site():
    from datetime import datetime

    from eii_custodian.publicdata.fetch.cadence import due_source, parse_cadence

    rule = parse_cadence({"value": "none", "reason": "syn"})
    with pytest.raises(ValueError, match=r"^clock_invalid$"):
        due_source(rule, [], clock=lambda: datetime(2024, 1, 1))


@pytest.mark.parametrize(
    "reader,reason",
    [
        ("review", "syn_source: snapshot_index_invalid"),
        ("frame", "syn_source: snapshot_index_invalid"),
        ("method", "public_cache_missing:syn_source"),
        ("method_hash", "receipt_hash_mismatch:syn_source"),
        ("extension", "snapshot extension mismatch"),
        ("road", "road_file_unreceipted"),
        ("road_pin", "road_file_missing"),
        ("road_key", "road_file_unreceipted"),
        ("place", "places_file_unreceipted"),
    ],
)
def test_existing_reader_refusal_site(tmp_path, monkeypatch, reader, reason):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.places.area_files import ROAD_KEY, _load_road
    from eii_custodian.publicdata.places.integrate import _opened_place
    from eii_custodian.publicdata.review.cache_fixture import read_cached, write_cached

    entry = replace(load_registry()[0], key="syn_source", source_id="syn_source")
    digest = "a" * 64

    def action():
        return read_cached(tmp_path, entry, digest=digest)

    if reader == "frame":
        from eii_custodian.publicdata.frame.build import read_cached as read_frame

        def action():
            return read_frame(tmp_path, entry, digest=digest)
    elif reader in {"method", "method_hash"}:
        import custodian.data_tests.cache as module

        monkeypatch.setattr(module, "load_registry", lambda: (entry,))
        if reader == "method_hash":
            path = write_cached(tmp_path, entry, b"[]")
            digest = path.stem
            path.write_bytes(b"syn-tamper")

        def action():
            return module.cached(tmp_path, entry.key, digest)
    elif reader == "extension":
        path = write_cached(tmp_path, entry, b"[]")

        def action():
            return read_cached(tmp_path, entry, digest=path.stem, extension="csv")
    elif reader.startswith("road"):
        source = replace(entry, key=ROAD_KEY, extension="pbf")
        path = write_cached(tmp_path, source, b"syn-road")
        if reader == "road_pin":
            (tmp_path / "snapshot_pins.json").unlink()
        elif reader == "road":
            path.write_bytes(b"syn-tamper")
        else:
            index = tmp_path / ROAD_KEY / "index" / (path.stem + ".json")
            row = json.loads(index.read_text())
            receipt = tmp_path / ROAD_KEY / row["receipt"]
            side = json.loads(receipt.read_text())
            side["key"] = row["key"] = "syn-other"
            receipt.write_text(json.dumps(side))
            row["receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            index.write_text(json.dumps(row))

        def action():
            return _load_road(tmp_path)
    elif reader == "place":
        (tmp_path / entry.key).mkdir()

        def action():
            return _opened_place(tmp_path, entry.key)

    from eii_custodian.publicdata.places.areas import AreaError

    error = (
        AreaError if reader in {"road", "road_pin", "road_key", "place"} else ValueError
    )
    with pytest.raises(error, match="^" + reason + "$"):
        action()


@pytest.mark.parametrize("kind", ["atlas", "baci", "gravity"])
def test_trade_publish_refusal_site(tmp_path, kind):
    from importlib import import_module

    module = import_module("eii_custodian.publicdata." + kind + ".fetch")
    staged = tmp_path / "syn-staged"
    staged.write_bytes(b"syn-body")
    with pytest.raises(
        getattr(module, kind.title() + "Error"), match=r"^cache_integrity$"
    ):
        module._publish(staged, tmp_path / "syn-cache" / "syn.zip", dict(SIDE, key=""))


def test_investment_snapshot_refusal_site(tmp_path):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response
    from eii_custodian.publicdata.investment_build import _fetch_page
    from eii_custodian.publicdata.investment_contracts import InvestmentFailure

    entry = replace(load_registry()[0], key="syn_source", source_id="syn_source")
    result = _fetch_page(
        entry,
        tmp_path,
        entry.url,
        lambda url: Response(url, b"syn-page", ()),
        lambda _: None,
        lambda: "syn-invalid-date",
        "",
    )
    assert isinstance(result, InvestmentFailure)
    assert result.check == "snapshot_invalid"


@pytest.mark.parametrize("plant", ["prepare", "auxiliary"])
def test_build_snapshot_failure_site(tmp_path, monkeypatch, plant):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.kinds import Prepared
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response

    entry = replace(load_registry()[0], key="syn_source", source_id="syn_source")

    def fail(*args, **kwargs):
        raise archive.SnapshotError("syn-diagnostic")

    prepared = Prepared(
        b"[]",
        entry.url,
        entry.fetch_host,
        "syn-publisher",
        "",
        0,
        "",
        None,
        auxiliary=(Response(entry.url, b"syn-meta", ()),),
    )
    monkeypatch.setattr(
        build, "prepare", fail if plant == "prepare" else lambda *args: prepared
    )
    if plant == "auxiliary":
        monkeypatch.setattr(build, "archive_auxiliary", fail)
    result = build.fetch_entry(
        entry,
        lambda url: Response(url, b"[]", ()),
        tmp_path,
        lambda: SIDE["retrieved_utc"],
        lambda _: None,
    )
    assert result is not None
    assert (result.source_id, result.check, result.expected, result.observed) == (
        "syn_source",
        "write_failed",
        "stored file",
        "write failed",
    )


@pytest.mark.parametrize("plant", ["source", "publisher", "snapshot", "pin"])
def test_place_receipt_refusal_site(tmp_path, plant):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.places.integrate import _receipt_of
    from eii_custodian.publicdata.review.cache_fixture import select_fixture

    entry = replace(
        load_registry()[0],
        key="syn_source",
        source_id="syn_source",
        extension="parquet",
    )
    side = dict(SIDE, publisher="syn-publisher")
    if plant == "source":
        side["source_id"] = "syn-other"
    elif plant == "publisher":
        side.pop("publisher")
    ref = archive.publish_snapshot(tmp_path / entry.key, "parquet", b"syn-body", side)
    select_fixture(tmp_path, entry.key, ref.sha256)
    if plant == "pin":
        (tmp_path / "snapshot_pins.json").unlink()
    if plant == "snapshot":
        ref.path.write_bytes(b"syn-tamper")
    assert _receipt_of(tmp_path, entry) is None


def test_registry_cadence_refusal_site(tmp_path):
    import yaml

    from eii_custodian.publicdata.fetch.registry import (
        RegistryError,
        load_registry,
        registry_path,
    )

    doc = yaml.safe_load(registry_path().read_text())
    doc["sources"][0]["refetch"] = {"value": "weekly", "family": "syn-unknown"}
    path = tmp_path / "syn-registry.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(RegistryError, match=r"^cadence_family_unknown$"):
        load_registry(path)


def test_snapshot_refuses_existing_occupant(tmp_path):
    body = b"syn-body"
    digest = hashlib.sha256(body).hexdigest()
    destination = tmp_path / "2024-01-31" / (digest + ".json")
    destination.parent.mkdir()
    destination.write_bytes(b"syn-occupant")
    with pytest.raises(archive.SnapshotError, match=r"^cache_integrity$"):
        archive.publish_snapshot(tmp_path, "json", body, SIDE)
    assert destination.read_bytes() == b"syn-occupant"
