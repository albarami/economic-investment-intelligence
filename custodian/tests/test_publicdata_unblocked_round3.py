"""L-707 cache compatibility through the real build, with invented responses."""

import base64
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)
from custodian.tests.support.fetch_build import run_build
from custodian.tests.test_activity_graph import (
    _allowlist_csv,
    _binding_beside,
    _places_parquet,
    _review_csv,
)
from custodian.tests.test_places_fetch import _entry as part_entry
from custodian.tests.test_publicdata_behaviour import _clock, _sleep
from custodian.tests.test_publicdata_unblocked_round2 import listing_body

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.places.integrate import (
    _buildings_from_registry,
    _place_from_registry,
    _receipt_of,
)
from eii_custodian.publicdata.places.read import read_building_file, read_place_file
from eii_custodian.publicdata.review.activity import SupplierMembership
from eii_custodian.publicdata.review.cache_fixture import (
    CacheError,
    class_csv,
    read_cached,
    read_rows,
    real_feed_body,
    select_fixture,
    write_cached,
)
from eii_custodian.publicdata.review.graph import build_cached_graph

PARENTS = ("places_ovt", "bldg_ovt")


def _listing_build_fixture(folder):
    entries = load_registry()
    parents = tuple(e for e in entries if e.key in PARENTS)
    bodies = {}
    parts = []
    for parent in parents:
        path = folder / f"{parent.key}.parquet"
        if parent.key == "places_ovt":
            write_places(path, [place_row()])
        else:
            write_buildings(
                path,
                [building_row("SYN-B-A", ((1, 1), (2, 1), (2, 2), (1, 1)))],
            )
        body = path.read_bytes()
        prefix = parent.url.split("prefix=", 1)[1]
        url = "https://" + parent.fetch_host + "/" + prefix + "invented.parquet"
        registered = next(e for e in entries if e.key.startswith(parent.key + "/"))
        part = replace(
            part_entry(len(body), url),
            key=registered.key,
            source_id=parent.source_id,
        )
        parts.append(part)
        bodies[part.url] = body
        bodies[parent.url] = listing_body(
            key=urlsplit(part.url).path.lstrip("/"), size=str(len(body))
        )
    return (*parents, *parts), bodies


def _transport(bodies):
    return lambda url: Response(url, bodies[url], (), '"syn-etag"')


def _parent_files(cache, key):
    return {p.name: p.read_bytes() for p in (cache / key).iterdir() if p.is_file()}


def test_listing_build_preserves_parent_graph(tmp_path: Path) -> None:
    entries, bodies = _listing_build_fixture(tmp_path)
    registry = load_registry()
    old_registry = tuple(
        replace(e, extension="parquet") if e.key in PARENTS else e for e in registry
    )
    by_key = {e.key: e for e in old_registry}
    cache = tmp_path / "cache"
    write_cached(
        cache,
        by_key["lic_active"],
        real_feed_body(
            "lic_active",
            [
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "active_count": 2,
                }
            ],
        ),
    )
    write_cached(cache, by_key["lic_cancelled"], real_feed_body("lic_cancelled", []))
    write_cached(cache, by_key["cls_isic4"], class_csv([("5610", "Invented class")]))
    old_body = _places_parquet(tmp_path, ("restaurant", "cafe"))
    write_cached(cache, by_key["places_ovt"], old_body)
    review = _review_csv(tmp_path)
    _binding_beside(review, titles=(("5610", "Invented class", ""),))
    allowlist = _allowlist_csv(tmp_path)
    suppliers = SupplierMembership(codes=(), complete=True)
    expected = build_cached_graph(
        cache,
        review,
        allowlist,
        (),
        supplier_membership=suppliers,
        registry=old_registry,
    )
    assert any(edge.edge_type == "listed_as" for edge in expected.edges)
    before = _parent_files(cache, "places_ovt")
    outcome = run_build(entries, _transport(bodies), cache, _clock, _sleep)
    assert outcome.failure is None
    actual = build_cached_graph(
        cache, review, allowlist, (), supplier_membership=suppliers
    )
    assert actual == expected
    assert _parent_files(cache, "places_ovt") == before
    # Planted violation (lead ruling L-707 item K2): the listing envelope written at
    # the parent key, the shape round 2 wrote, must fail the same graph build.
    parent = next(e for e in entries if e.key == "places_ovt")
    envelope = json.dumps(
        {"pages": [{"sha256": sha256_hex(bodies[parent.url])}], "etag": '"syn-etag"'}
    ).encode()
    write_cached(cache, parent, envelope, extension="json")
    planted = replace(parent, extension="json")
    with pytest.raises(CacheError, match=r"^cache json body is not a list of rows$"):
        build_cached_graph(
            cache,
            review,
            allowlist,
            (),
            supplier_membership=suppliers,
            registry=tuple(planted if e.key == "places_ovt" else e for e in registry),
        )


@pytest.mark.parametrize("key", PARENTS)
def test_listing_build_preserves_parent_rows_and_receipt(
    tmp_path: Path, key: str
) -> None:
    entries, bodies = _listing_build_fixture(tmp_path)
    parent = next(e for e in entries if e.key == key)
    part = next(e for e in entries if e.key.startswith(key + "/"))
    old_entry = replace(parent, extension="parquet")
    cache = tmp_path / "cache"
    write_cached(cache, old_entry, bodies[part.url])
    expected = read_rows(
        read_cached(cache, old_entry, digest=sha256_hex(bodies[part.url]))
    )
    before = _parent_files(cache, key)
    for suffix in (b"", b"\n"):
        bodies[parent.url] += suffix
        outcome = run_build(entries, _transport(bodies), cache, _clock, _sleep)
        assert outcome.failure is None
        assert (
            read_rows(read_cached(cache, parent, digest=sha256_hex(bodies[part.url])))
            == expected
        )
        located = _receipt_of(cache, parent)
        assert located is not None and located[0].read_bytes() == bodies[part.url]
        assert _parent_files(cache, key) == before
        listing_dir = cache / key / "listing"
        listing_files = list(listing_dir.glob("*.json"))
        envelopes = [p for p in listing_files if not p.name.endswith(".meta.json")]
        assert envelopes
        for path in envelopes:
            side = json.loads(path.with_suffix(".meta.json").read_text())
            assert side["key"] == key + "/listing"
            assert side["source_id"] == key
            assert side["sha256"] == sha256_hex(path.read_bytes())
            raw = base64.b64decode(
                json.loads(path.read_bytes())["listing_pages_base64"][0]
            )
            assert side["requests"][0]["sha256"] == sha256_hex(raw)
            assert side["requests"][0]["url"] == parent.url
            assert b'"syn-etag"' in raw


def test_listing_build_fresh_cache_uses_registered_parts(tmp_path: Path) -> None:
    entries, bodies = _listing_build_fixture(tmp_path)
    cache = tmp_path / "cache"
    outcome = run_build(entries, _transport(bodies), cache, _clock, _sleep)
    assert outcome.failure is None
    for entry in entries:
        if entry.key not in PARENTS:
            select_fixture(cache, entry.key, sha256_hex(bodies[entry.url]))
    placed = _place_from_registry(cache, entries)
    assert placed is not None
    path, receipt = placed
    part = next(e for e in entries if e.key.startswith("places_ovt/"))
    assert receipt.source_key == part.key
    assert path.read_bytes() == bodies[part.url]
    assert read_place_file(path, "ar") == read_place_file(
        tmp_path / "places_ovt.parquet", "ar"
    )
    paths, receipts = _buildings_from_registry(cache, entries)
    part = next(e for e in entries if e.key.startswith("bldg_ovt/"))
    assert len(paths) == len(receipts) == 1
    assert receipts[0].source_key == part.key
    assert paths[0].read_bytes() == bodies[part.url]
    assert read_building_file(paths[0]) == read_building_file(
        tmp_path / "bldg_ovt.parquet"
    )
    assert all(not _parent_files(cache, key) for key in PARENTS)
