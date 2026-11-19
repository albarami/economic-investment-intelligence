"""Fetch refusals and receipt fields on invented responses only."""

import json
from dataclasses import astuple, replace

import pytest
from custodian.tests.fixtures.places_fsq.invented import listing, place, write_places
from custodian.tests.test_places_fsq import _grid, _release_entry

from eii_custodian.publicdata.fetch.snapshots import SnapshotError, read_snapshot
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.places_fsq import fetch as f
from eii_custodian.publicdata.places_fsq.assemble import build_places
from eii_custodian.publicdata.places_fsq.constants import ATTRIBUTION, COPY_ROOT
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import metadata_bytes
from eii_custodian.publicdata.places_fsq.policy import CategoryMapping, PlaceStandIn
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX

URL = "https://data.source.coop/invented"
FOREIGN = "https://invented.invalid/file"
TERMS = b"Copyright 2024 Foursquare Labs, Inc. All rights reserved. Apache License, Version 2.0"
RELEASE = "2025-01-10"


@pytest.mark.parametrize("metadata", [False, True])
@pytest.mark.parametrize("mark", [b"SIGN IN", b"SIGN-IN", b"LOG IN", b"ACCESS TOKEN"])
def test_fsq_body_refusal_full_fields(metadata, mark):
    assert astuple(f._body_refusal(mark, URL, metadata=metadata)) == (
        1,
        URL,
        "sign_in_demand",
        "public file",
        "sign-in",
    )
    assert astuple(f._body_refusal(b"other", URL, metadata=metadata)) == (
        1,
        URL,
        "metadata_unreadable" if metadata else "not_parquet",
        "parquet",
        "other",
    )
    assert f._body_refusal(b"PAR1", URL, metadata=metadata) is None
    assert astuple(f._terms_refusal(mark, URL)) == (
        1,
        URL,
        "sign_in_demand",
        "public file",
        "sign-in",
    )


def test_fsq_terms_refusal_full_fields():
    for body in [
        b"none",
        b"Copyright 2024 Foursquare Labs, Inc. All rights reserved.",
        b"Apache License, Version 2.0",
    ]:
        # Ruling L-1001 (PUB-97): a licence text that differs from the
        # registry's pinned wording is recorded pending a reviewer's record
        # and refuses nothing.
        assert f._terms_refusal(body, URL) is None
        assert f._licence_pending(body) is True
    assert f._terms_refusal(TERMS, URL) is None
    assert f._licence_pending(TERMS) is False


@pytest.mark.parametrize(
    "kind, code, check, expected, observed",
    [
        ("blocked_host", 1, "blocked_host", "allow-listed host", FOREIGN),
        ("unreachable", 6, "unreachable", "reachable host", "unreachable"),
        ("http_status", 1, "http_status", "http success", "http status"),
    ],
)
def test_fsq_transport_refusal_full_fields(kind, code, check, expected, observed):
    def transport(url):
        raise TransportFault(kind, FOREIGN)

    result, failure = f._get(_release_entry(), transport, URL)
    assert result is None
    assert astuple(failure) == (code, FOREIGN, check, expected, observed)


def test_fsq_blocked_before_request_and_redirect_fields(tmp_path):
    entry = _release_entry()
    calls = []

    def transport(url):
        calls.append(url)
        return Response(URL, b"PAR1", (FOREIGN,))

    for altered in [replace(entry, url=FOREIGN), replace(entry, terms_url=FOREIGN)]:
        result, failure = f.fetch_release(
            altered, transport, tmp_path, lambda: "clock", lambda _: None
        )
        assert result is None
        assert astuple(failure) == (
            1,
            FOREIGN,
            "blocked_host",
            "allow-listed host",
            FOREIGN,
        )
        assert calls == []
    assert f._get(entry, transport, FOREIGN) == (
        None,
        f.ReleaseFailure(1, FOREIGN, "blocked_host", "allow-listed host", FOREIGN),
    )
    assert f._get(entry, transport, URL) == (
        None,
        f.ReleaseFailure(1, FOREIGN, "blocked_host", "allow-listed host", FOREIGN),
    )
    assert calls == [URL]
    assert f._blocked(replace(entry, url="", terms_url="")) is None
    assert f.is_release_entry(entry) is True
    assert f.is_release_entry(replace(entry, skip_reason="invented")) is False
    assert f.is_release_entry(replace(entry, key="places_fsq")) is False
    assert (
        f._data_url("a/b/invented.parquet", RELEASE)
        == "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/invented.parquet"
    )


def test_fsq_summary_refusal_fields(tmp_path):
    entry = replace(_release_entry(), terms_url="")
    body = metadata_bytes(
        [
            dict(
                file_path="2024-12-03/places/a.parquet",
                longitude=(51.0, 51.5),
                latitude=(25.0, 25.5),
            )
        ],
        dataset_geo_bbox=None,
    )

    def transport(url):
        response = listing(f"{RELEASE}/") if url == entry.url else body
        return Response(url, response, ())

    result, failure = f.fetch_release(
        entry, transport, tmp_path, lambda: "clock", lambda _: None
    )
    assert result is None
    assert astuple(failure) == (
        1,
        f"{COPY_ROOT}{RELEASE}/places/_metadata",
        "release_mismatch",
        "files for the frame",
        "none",
    )


def test_fsq_store_manifest_and_sidecars(tmp_path):
    import hashlib

    entry = _release_entry()
    metadata = b"metadata"
    data = b"file"
    terms = b"abc"
    meta_hash = hashlib.sha256(metadata).hexdigest()
    data_hash = hashlib.sha256(data).hexdigest()
    listing_hash = hashlib.sha256(b"listing").hexdigest()
    # SHA-256 test vector for ASCII abc.
    terms_hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    for term_body, term_hash, term_url, folder in [
        (terms, terms_hash, URL, "with"),
        (b"", None, "", "without"),
    ]:
        cache = tmp_path / folder
        digest = f._store(
            entry,
            cache,
            metadata,
            [("a.parquet", data, URL)],
            term_body,
            term_url,
            "2091-01-01T00:00:00Z",
            "data.source.coop",
            release=RELEASE,
            listing=(b"listing", COPY_ROOT),
            metadata_url=entry.url,
        )
        directory = cache / "places_fsq" / "copy" / RELEASE
        expected = {
            "attribution": ATTRIBUTION,
            "files": [{"name": "a.parquet", "sha256": data_hash, "bytes": 4}],
            "listing_sha256": listing_hash,
            "metadata_sha256": meta_hash,
            "method": "places_fsq.v1",
            "release": "2025-01-10",
            "retrieved_utc": "2091-01-01T00:00:00Z",
            "terms_sha256": term_hash,
            "terms_url": term_url or None,
        }
        payload = (directory / "manifest.json").read_bytes()
        assert payload == json.dumps(expected, sort_keys=True).encode("utf-8")
        assert digest == hashlib.sha256(payload).hexdigest()
        assert not (directory / ".manifest.json.partial").exists()
        for sub, sha, body, url in [
            ("metadata", meta_hash, metadata, entry.url),
            ("files", data_hash, data, URL),
        ]:
            assert (directory / sub / (sha + ".parquet")).read_bytes() == body
            receipt = json.loads((directory / sub / (sha + ".meta.json")).read_bytes())
            for key, value in {
                "sha256": sha,
                "bytes": 8 if sub == "metadata" else 4,
                "fetch_url": url,
                "fetch_host": "data.source.coop",
                "retrieved_utc": "2091-01-01T00:00:00Z",
                "publisher": "Foursquare",
                "source_modified": "2025-01-10",
                "row_count": None,
                "terms_sha256": term_hash,
                "switched_off": False,
                "key": "places_fsq/copy",
            }.items():
                assert receipt[key] == value


def test_fsq_body_scan_boundary_and_bad_utf8():
    assert astuple(f._body_refusal(b"x" * 3993 + b"sign in", URL, metadata=False)) == (
        1,
        URL,
        "sign_in_demand",
        "public file",
        "sign-in",
    )
    assert astuple(f._body_refusal(b"x" * 3994 + b"sign in", URL, metadata=False)) == (
        1,
        URL,
        "not_parquet",
        "parquet",
        "other",
    )
    assert astuple(f._body_refusal(b"\xffSIGN IN", URL, metadata=False)) == (
        1,
        URL,
        "sign_in_demand",
        "public file",
        "sign-in",
    )
    assert f._terms_refusal(b"\xff" + TERMS, URL) is None


@pytest.mark.parametrize("stage", ["metadata", "terms", "data"])
@pytest.mark.parametrize("mode", ["transport", "signin", "malformed"])
def test_fsq_fetch_failure_at_each_stage_stores_nothing(tmp_path, stage, mode):
    entry = _release_entry()
    data_url = (
        "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/a.parquet"
    )
    metadata_url = f"{COPY_ROOT}{RELEASE}/places/_metadata"
    urls = {"metadata": metadata_url, "terms": entry.terms_url, "data": data_url}
    summary = metadata_bytes(
        [
            dict(
                file_path="2025-01-10/places/a.parquet",
                longitude=(51.0, 51.5),
                latitude=(25.0, 25.5),
            )
        ],
        dataset_geo_bbox=None,
    )
    seen = []

    def transport(url):
        seen.append(url)
        if url == urls[stage]:
            if mode == "transport":
                raise TransportFault("unreachable", url)
            return Response(url, b"SIGN IN" if mode == "signin" else b"other", ())
        if url == entry.url:
            return Response(url, listing(f"{RELEASE}/"), ())
        return Response(url, summary if url == metadata_url else TERMS, ())

    result, failure = f.fetch_release(
        entry, transport, tmp_path / "cache", lambda: "clock", lambda _: None
    )
    assert result is None
    if mode == "transport":
        expected = (6, urls[stage], "unreachable", "reachable host", "unreachable")
    elif mode == "signin":
        expected = (1, urls[stage], "sign_in_demand", "public file", "sign-in")
    elif stage == "metadata":
        expected = (1, urls[stage], "metadata_unreadable", "parquet", "other")
    else:
        # Ruling L-1001 (PUB-97): a differing licence text refuses nothing, so
        # a malformed terms body is recorded pending and the release proceeds
        # to the data file, which refuses the non-Parquet body.
        expected = (1, data_url, "not_parquet", "parquet", "other")
    assert astuple(failure) == expected
    stop = {
        "metadata": 2,
        "terms": 4 if mode == "malformed" else 3,
        "data": 4,
    }[stage]
    assert seen == [entry.url, metadata_url, entry.terms_url, data_url][:stop]
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("with_terms", [False, True])
def test_fsq_fetch_success_manifest_tracks_actual_responses(tmp_path, with_terms):
    import hashlib

    entry = _release_entry()
    if not with_terms:
        entry = replace(entry, terms_url="")
    file_url = (
        "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/a.parquet"
    )
    summary = metadata_bytes(
        [
            dict(
                file_path="2025-01-10/places/a.parquet",
                longitude=(51.0, 51.5),
                latitude=(25.0, 25.5),
            ),
            dict(
                file_path="far.parquet", longitude=(10.0, 11.0), latitude=(20.0, 21.0)
            ),
        ],
        dataset_geo_bbox=None,
    )
    # No external file path: all rows in this hand-made footer belong to this file.
    from eii_custodian.publicdata.places_fsq import footer

    writer = footer._Writer()
    writer.file_metadata(
        (dict(file_path="", longitude=(51.0, 51.5), latitude=(25.0, 25.5)),), None
    )
    payload = bytes(writer.buffer)
    import struct

    data = b"PAR1" + payload + struct.pack("<I", len(payload)) + b"PAR1"
    seen = []
    clocks = []

    def transport(url):
        seen.append(url)
        if url == entry.url:
            body = listing(f"{RELEASE}/")
        elif url.endswith("_metadata"):
            body = summary
        else:
            body = TERMS if url == entry.terms_url else data
        return Response(url + "/served", body, ())

    def clock():
        clocks.append("clock")
        return "2091-01-01T00:00:00Z"

    def sleep(_):
        raise AssertionError("unexpected sleep")

    result, failure = f.fetch_release(
        entry, transport, tmp_path / "cache", clock, sleep
    )
    assert failure is None
    assert result is not None
    assert result.host == "data.source.coop"
    metadata_url = f"{COPY_ROOT}{RELEASE}/places/_metadata"
    assert seen == [
        entry.url,
        metadata_url,
        *([entry.terms_url] if with_terms else []),
        file_url,
    ]
    assert clocks == ["clock"]
    directory = tmp_path / "cache" / "places_fsq" / "copy" / RELEASE
    manifest = (directory / "manifest.json").read_bytes()
    assert result.digest == hashlib.sha256(manifest).hexdigest()
    record = json.loads(manifest)
    assert record["metadata_sha256"] == hashlib.sha256(summary).hexdigest()
    assert record["files"] == [
        {
            "name": "2025-01-10/places/a.parquet",
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    ]
    assert record["terms_url"] == (entry.terms_url + "/served" if with_terms else None)
    assert record["terms_sha256"] == (
        hashlib.sha256(TERMS).hexdigest() if with_terms else None
    )
    assert record["retrieved_utc"] == "2091-01-01T00:00:00Z"
    receipt = json.loads(next((directory / "files").glob("*.meta.json")).read_bytes())
    assert receipt["fetch_url"] == file_url + "/served"
    assert receipt["terms_sha256"] == (
        hashlib.sha256(TERMS).hexdigest() if with_terms else None
    )
    meta_receipt = json.loads(
        next((directory / "metadata").glob("*.meta.json")).read_bytes()
    )
    assert meta_receipt["fetch_host"] == "data.source.coop"


@pytest.mark.parametrize(
    "malformed,reason", [(True, "metadata_unreadable"), (False, "statistics_missing")]
)
def test_fsq_data_footer_failure_named_at_file_address(tmp_path, malformed, reason):
    entry = replace(_release_entry(), terms_url="")
    groups = [
        dict(file_path="a.parquet", longitude=(51.0, 51.5), latitude=(25.0, 25.5))
    ]
    summary = metadata_bytes(groups, dataset_geo_bbox=None)
    data = (
        b"PAR1short"
        if malformed
        else metadata_bytes(groups, dataset_geo_bbox=None, column_orders=None)
    )

    def transport(url):
        if url == entry.url:
            return Response(url, listing(f"{RELEASE}/"), ())
        return Response(url, summary if url.endswith("_metadata") else data, ())

    result, failure = f.fetch_release(
        entry, transport, tmp_path / "cache", lambda: "clock", lambda _: None
    )
    assert result is None
    assert astuple(failure) == (
        1,
        "https://data.source.coop/fused/fsq-os-places/2025-01-10/places/a.parquet",
        reason,
        "summary coordinate bounds",
        "file bounds differ or missing",
    )
    assert not (tmp_path / "cache").exists()


def test_fsq_generated_address_guard_refuses_planted_foreign_host(
    tmp_path, monkeypatch
):
    entry = replace(_release_entry(), terms_url="")
    body = metadata_bytes(
        [dict(file_path="a.parquet", longitude=(51.0, 51.5), latitude=(25.0, 25.5))],
        dataset_geo_bbox=None,
    )
    seen = []

    def transport(url):
        seen.append(url)
        response = listing(f"{RELEASE}/") if url == entry.url else body
        return Response(url, response, ())

    monkeypatch.setattr(f, "_data_url", lambda _name, _release: FOREIGN)
    assert f.fetch_release(
        entry, transport, tmp_path / "cache", lambda: "clock", lambda _: None
    ) == (
        None,
        f.ReleaseFailure(1, FOREIGN, "blocked_host", "allow-listed host", FOREIGN),
    )
    assert seen == [entry.url, f"{COPY_ROOT}{RELEASE}/places/_metadata"]
    assert not (tmp_path / "cache").exists()


def test_fsq_manifest_replace_failure_removes_named_partial(tmp_path, monkeypatch):
    original = f.os.replace

    def replace_file(source, target):
        if target.name == "manifest.json":
            raise OSError("invented manifest rename failure")
        original(source, target)

    monkeypatch.setattr(f.os, "replace", replace_file)
    with pytest.raises(OSError, match="invented manifest rename failure"):
        f._store(
            _release_entry(),
            tmp_path,
            b"meta",
            [],
            b"",
            "",
            "2091-01-01T00:00:00Z",
            "data.source.coop",
            release=RELEASE,
            listing=(b"listing", COPY_ROOT),
            metadata_url=COPY_ROOT,
        )
    directory = tmp_path / "places_fsq" / "copy" / RELEASE
    assert not (directory / ".manifest.json.partial").exists()
    assert not (directory / "manifest.json").exists()


def test_fsq_duplicate_names_fetch_only_summary(tmp_path):
    entry = _release_entry()
    summary = metadata_bytes(
        [
            dict(file_path=path, longitude=(51.0, 51.5), latitude=(25.0, 25.5))
            for path in ("a/one/near.parquet", "b/two/near.parquet")
        ],
        dataset_geo_bbox=None,
    )
    seen = []

    def transport(url):
        seen.append(url)
        response = listing(f"{RELEASE}/") if url == entry.url else summary
        return Response(url, response, ())

    result, failure = f.fetch_release(
        entry, transport, tmp_path / "cache", lambda: "clock", lambda _: None
    )
    assert result is None
    assert astuple(failure) == (
        1,
        f"{COPY_ROOT}{RELEASE}/places/_metadata",
        "file_name_duplicate",
        "files for the frame",
        "none",
    )
    assert seen == [entry.url, f"{COPY_ROOT}{RELEASE}/places/_metadata"]
    assert not (tmp_path / "cache").exists()


def test_two_refreshes_retain_both_releases_and_build_from_new_digest(tmp_path):
    old = "2031-02-03"
    new = "2032-04-05"
    entry = replace(_release_entry(), terms_url="")
    data = tmp_path / "same.parquet"
    write_places(
        data,
        [
            place(
                fsq_place_id="aaaaaaaaaaaaaaaaaaaaaaaa",
                fsq_category_ids=["SYN-food"],
                fsq_category_labels=["Invented food"],
            ),
            place(
                fsq_place_id="bbbbbbbbbbbbbbbbbbbbbbbb",
                name="Invented Hidden",
                longitude=51.500001,
                fsq_category_ids=["SYN-food"],
                fsq_category_labels=["Invented food"],
            ),
        ],
    )
    available = [old]
    cache = tmp_path / "cache"

    def fetch(release, retrieved):
        summary = metadata_bytes(
            [
                dict(
                    file_path=f"{release}/places/same.parquet",
                    longitude=(51.5, 51.500001),
                    latitude=(25.3, 25.3),
                )
            ],
            dataset_geo_bbox=None,
        )
        bodies = {
            COPY_ROOT: listing(*(f"{item}/" for item in reversed(available))),
            f"{COPY_ROOT}{release}/places/_metadata": summary,
            f"{COPY_ROOT}{release}/places/same.parquet": data.read_bytes(),
        }

        def transport(url):
            return Response(url, bodies[url], ())

        result, failure = f.fetch_release(
            entry, transport, cache, lambda: retrieved, lambda _: None
        )
        assert failure is None
        assert result is not None
        return result

    first = fetch(old, "2091-01-01T00:00:00Z")
    available.append(new)
    second = fetch(new, "2091-01-02T00:00:00Z")
    old_dir = cache / "places_fsq" / "copy" / old
    new_dir = cache / "places_fsq" / "copy" / new
    old_manifest = read_snapshot(old_dir / "manifests", first.digest)
    new_manifest = read_snapshot(new_dir / "manifests", second.digest)
    assert json.loads(old_manifest.body)["release"] == old
    record = json.loads(new_manifest.body)
    assert record["release"] == new
    assert first.digest != second.digest
    for directory, release in ((old_dir, old), (new_dir, new)):
        for role in ("listings", "metadata", "files", "manifests"):
            identities = [
                path.stem for path in (directory / role / "index").glob("*.json")
            ]
            assert identities
            for identity in identities:
                snapshot = read_snapshot(directory / role, identity)
                assert snapshot.sidecar["source_modified"] == release
                assert snapshot.body
    row = record["files"][0]
    old_file = read_snapshot(old_dir / "files", row["sha256"])
    new_file = read_snapshot(new_dir / "files", row["sha256"])
    assert old_file.body == new_file.body == data.read_bytes()
    assert old_file.sidecar["source_modified"] == old
    assert new_file.sidecar["source_modified"] == new

    # Both builds read their pinned manifest digest, never a compatibility pointer.
    (old_dir / "manifest.json").write_bytes(b"{}")
    (new_dir / "manifest.json").write_bytes(b"{}")
    mapping = (
        CategoryMapping(
            "SYN-food",
            "food",
            "map-1",
            "approved",
            "reviewer",
            "2030-01-01",
            "invented",
        ),
    )
    places = (
        PlaceStandIn("SYN-P-HIDDEN", "Invented Hidden", None, 51.500001, 25.3, False),
    )

    def build(directory, manifest_digest, file_snapshot, labels=("Zedqun Label",)):
        manifest = json.loads(
            read_snapshot(directory / "manifests", manifest_digest).body
        )
        file_row = manifest["files"][0]
        return build_places(
            files={file_row["name"]: file_snapshot.path},
            expected_sha256={file_row["name"]: file_row["sha256"]},
            frame=FRAME_BOX,
            grid=_grid((51.5, 25.3)),
            places=places,
            mapping=mapping,
            labels=labels,
            min_edit_distance=2,
            release=manifest["release"],
            attribution=ATTRIBUTION,
            receipt_sha256=manifest_digest,
        )

    for directory, release, digest, file_snapshot in (
        (old_dir, old, first.digest, old_file),
        (new_dir, new, second.digest, new_file),
    ):
        built = build(directory, digest, file_snapshot)
        assert built.release == release
        assert {row.source_release for row in built.rows} == {release}
        assert [item.row.fsq_place_id for item in built.eligible] == [
            "aaaaaaaaaaaaaaaaaaaaaaaa"
        ]
        assert built.eligible[0].product_categories == "food"
        assert [link.fsq_place_id for link in built.duplicates] == [
            "bbbbbbbbbbbbbbbbbbbbbbbb"
        ]
        assert built.coverage.duplicate_not_shown == 1
        assert built.names.ok
        with pytest.raises(PlacesFsqError, match=r"^name_collision$"):
            build(directory, digest, file_snapshot, labels=("Invented Hidden",))

    # Tampering with the old body cannot change its index or affect the new build.
    index = old_dir / "files" / "index" / f"{row['sha256']}.json"
    index_before = index.read_bytes()
    old_file.path.write_bytes(b"planted tamper")
    with pytest.raises(SnapshotError, match=r"^snapshot_hash_mismatch$"):
        read_snapshot(old_dir / "files", row["sha256"])
    assert index.read_bytes() == index_before
    old_file.path.write_bytes(data.read_bytes())
    assert read_snapshot(old_dir / "files", row["sha256"]).body == data.read_bytes()
