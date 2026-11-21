"""L-701 offline checks using invented responses and existing fixture builders."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from custodian.tests.test_publicdata_behaviour import (
    _clock,
    _entry,
    _ok,
    _portal_meta,
    _sidecar,
    _sleep,
)
from custodian.tests.test_registry_survivors import invented_row

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry

PORTAL = "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/"
MUNI_PUBLISHER = (
    "National open data portal (dataset publisher field empty, read 2026-11-16)"
)


def test_portal_rows_activated_with_complete_columns() -> None:
    expected = {
        "wage_sector": 7,
        "wage_bands_priv": 5,
        "work_hours_act": 7,
        "cpi_group": 7,
        "zone_population": 7,
        "census_hh_type_2020": 8,
        "accident": 16,
        "bnd_muni_2025": 3,
    }
    entries = {e.key: e for e in load_registry()}
    for key, count in expected.items():
        entry = entries[key]
        assert entry.skip_reason == (
            "partition_byte_bound_unconfirmed" if key == "accident" else ""
        ), key
        assert len(entry.columns) == count, key
        assert entry.row_count_min == entry.row_count_max
        assert not entry.commit_allowed
    assert entries["accident"].public_splits == ("nationality",)
    assert entries["bnd_muni_2025"].row_count_min == 8
    assert entries["bnd_muni_2025"].publisher == MUNI_PUBLISHER


def test_nationality_column_requires_split(tmp_path: Path) -> None:
    row = invented_row(
        columns=[{"name": "nationality_group_of_accident", "type": "string"}],
        public_splits=[],
    )
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    with pytest.raises(RegistryError, match="nationality field requires"):
        load_registry(path)


@pytest.mark.parametrize("kind", ["point_2d", "geojson_geometry", "invented_unknown"])
def test_geometry_registry_closed_types(tmp_path: Path, kind: str) -> None:
    row = invented_row(columns=[{"name": "geometry", "type": kind}])
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": [row]}))
    if kind == "invented_unknown":
        with pytest.raises(RegistryError, match="unknown column type"):
            load_registry(path)
    else:
        assert load_registry(path)[0].columns == (("geometry", kind),)


@pytest.mark.parametrize(
    ("kind", "value", "valid"),
    [
        ("point_2d", {"lon": 1.0, "lat": 2}, True),
        ("point_2d", {"lon": "invented", "lat": 2}, False),
        ("point_2d", {"lon": True, "lat": 2}, False),
        ("geojson_geometry", {"type": "Polygon", "coordinates": []}, True),
        ("geojson_geometry", {"type": "MultiPolygon", "coordinates": []}, True),
        ("geojson_geometry", {"type": "Point", "coordinates": []}, False),
        ("geojson_geometry", {"type": "Polygon", "coordinates": "invented"}, False),
    ],
)
def test_municipality_column_values(
    tmp_path: Path, kind: str, value: object, valid: bool
) -> None:
    entry = replace(
        _entry(),
        key="bnd_muni_2025",
        source_id="bnd_muni_2025",
        kind="portal_dataset",
        publisher=MUNI_PUBLISHER,
        licence_basis="portal_terms",
        url=PORTAL + "municipalities-in-qatar-2025/exports/json",
        columns=(("geometry", kind),),
        row_count_min=1,
        row_count_max=1,
        extension="json",
    )
    meta = json.dumps(_portal_meta("", licence="", licence_url="")).encode()

    def transport(url: str):
        return _ok(
            url,
            json.dumps([{"geometry": value}]).encode()
            if url.endswith("/exports/json")
            else meta,
        )

    failure = fetch_entry(entry, transport, tmp_path, _clock, _sleep)
    if valid:
        assert failure is None
        assert _sidecar(tmp_path)["publisher"] == MUNI_PUBLISHER
    else:
        assert failure is not None and failure.check == "schema_retyped"
        assert not list(tmp_path.rglob("*"))


def accident_fixture():
    entry = replace(
        _entry(),
        key="accident",
        source_id="accident",
        kind="portal_dataset",
        url=PORTAL + "accident/exports/json",
        columns=(("accident_year", "string"),),
        row_count_min=2,
        row_count_max=2,
        extension="json",
    )
    meta = _portal_meta(entry.publisher)
    meta["records_count"] = 2
    plan = {
        "total_count": 2,
        "results": [
            {"year(accident_year)": 2001, "n": 1},
            {"year(accident_year)": 2002, "n": 1},
        ],
    }
    bodies = {
        PORTAL + "accident": json.dumps(meta).encode(),
        PORTAL
        + "accident/records?select=count%28%2A%29+as+n&group_by=year%28accident_year%29&limit=50": json.dumps(
            plan
        ).encode(),
        entry.url
        + "?where=year%28accident_year%29%3D2001": b'[{"accident_year":"2001"}]',
        entry.url
        + "?where=year%28accident_year%29%3D2002": b'[{"accident_year":"2002"}]',
    }
    return entry, bodies


def test_accident_partition_receipt(tmp_path: Path) -> None:
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    entry, bodies = accident_fixture()
    requested = []

    def transport(url: str):
        requested.append(url)
        return _ok(
            url, bodies.get(url, b'[{"accident_year":"2001"},{"accident_year":"2002"}]')
        )

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert set(requested) == set(bodies)
    assert side["row_count"] == 2
    requests = side["requests"]
    assert {r["url"]: r["sha256"] for r in requests} == {
        url: sha256_hex(body) for url, body in bodies.items()
    }
    assert [r["row_count"] for r in requests] == [2, 2, 1, 1]


@pytest.mark.parametrize(
    "plant",
    [
        "short",
        "long",
        "duplicate_hash",
        "duplicate_year",
        "total",
        "noninteger_year",
        "truncated_plan",
    ],
)
def test_accident_partition_refuses(tmp_path: Path, plant: str) -> None:
    entry, bodies = accident_fixture()
    _meta_url, plan_url, page_a, page_b = bodies
    if plant == "short":
        bodies[page_a] = b"[]"
    elif plant == "long":
        bodies[page_a] = b'[{"accident_year":"2001"},{"accident_year":"2001"}]'
    elif plant == "duplicate_hash":
        bodies[page_b] = bodies[page_a]
    else:
        plan = json.loads(bodies[plan_url])
        if plant == "duplicate_year":
            plan["results"][1]["year(accident_year)"] = 2001
        elif plant == "total":
            plan["results"][0]["n"] = 2
        elif plant == "noninteger_year":
            plan["results"][0]["year(accident_year)"] = "invented"
        else:
            plan["total_count"] = 3
        bodies[plan_url] = json.dumps(plan).encode()
    failure = fetch_entry(
        entry,
        lambda url: _ok(
            url, bodies.get(url, b'[{"accident_year":"2001"},{"accident_year":"2002"}]')
        ),
        tmp_path,
        _clock,
        _sleep,
    )
    assert failure is not None
    assert failure.source_id == "accident"
    assert failure.check in {
        "partition_count",
        "partition_duplicate",
        "partition_plan",
        "partition_total",
    }
    assert not list(tmp_path.rglob("*"))


OVT_HOST = "overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
PREFIX = "release/2026-10-21.0/theme=places/type=place/"


def listing_fixture(monkeypatch):
    from custodian.tests.test_places_fetch import _entry as part_entry

    from eii_custodian.publicdata.fetch import registry

    part = part_entry(4, "https://" + OVT_HOST + "/" + PREFIX + "invented.parquet")
    parent = replace(
        _entry(),
        key="places_ovt",
        source_id="places_ovt",
        url="https://" + OVT_HOST + "/?list-type=2&prefix=" + PREFIX,
        fetch_host=OVT_HOST,
        extension="json",
    )
    monkeypatch.setattr(registry, "load_registry", lambda: (parent, part))
    return parent


def listing_body(
    key=PREFIX + "invented.parquet",
    size="4",
    etag="syn-etag",
    truncated=False,
    token="",
):
    return (
        f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>{str(truncated).lower()}</IsTruncated><Contents><Key>{key}</Key><Size>{size}</Size><ETag>"{etag}"</ETag></Contents><NextContinuationToken>{token}</NextContinuationToken></ListBucketResult>'
    ).encode()


def test_listing_all_page_hashes(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    entry = listing_fixture(monkeypatch)
    first = listing_body(
        key=PREFIX + "other.parquet", truncated=True, token="invented-token"
    )
    second = listing_body()
    seen = []

    def transport(url):
        seen.append(url)
        return _ok(url, second if "continuation-token=" in url else first)

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    assert len(seen) == 2
    side = _sidecar(tmp_path)
    assert [r["sha256"] for r in side["requests"]] == [
        sha256_hex(first),
        sha256_hex(second),
    ]
    assert [r["url"] for r in side["requests"]] == seen


@pytest.mark.parametrize(
    "plant",
    ["prefix", "redirect", "missing", "size", "etag", "token", "repeated_token"],
)
def test_listing_refuses(tmp_path, monkeypatch, plant):
    entry = listing_fixture(monkeypatch)
    params = {}
    if plant == "prefix":
        params["key"] = "release/invented/other.parquet"
    if plant == "missing":
        params["key"] = PREFIX + "other.parquet"
    if plant == "size":
        params["size"] = "5"
    if plant == "etag":
        params["etag"] = "syn-other"
    if plant in {"token", "repeated_token"}:
        params["truncated"] = True
    if plant == "repeated_token":
        params["token"] = "invented-token"
    body = listing_body(**params)

    def transport(url):
        # An otherwise allow-listed host must still be refused for this listing.
        hops = ("https://www.data.gov.qa/invented",) if plant == "redirect" else ()
        return _ok(url, body, hops)

    failure = fetch_entry(entry, transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check.startswith("listing_")
    assert not list(tmp_path.rglob("*"))


def test_listing_build_keeps_existing_part_fetch(tmp_path, monkeypatch):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from custodian.tests.support.fetch_build import run_build

    from eii_custodian.publicdata.fetch import registry
    from eii_custodian.publicdata.fetch.transport import Response

    parent = listing_fixture(monkeypatch)
    entries = registry.load_registry()
    seen = []

    def transport(url):
        seen.append(url)
        if url == parent.url:
            return _ok(url, listing_body())
        return Response(url, b"SYN!", (), '"syn-etag"')

    outcome = run_build(entries, transport, fixture_cache, _clock, _sleep)
    assert outcome.failure is None
    assert seen == [parent.url, entries[1].url]
    assert (
        next((fixture_cache / entries[1].key).glob("*.parquet")).read_bytes() == b"SYN!"
    )


def test_municipality_publisher_change_refused(tmp_path):
    entry = replace(
        _entry(),
        key="bnd_muni_2025",
        source_id="bnd_muni_2025",
        kind="portal_dataset",
        publisher=MUNI_PUBLISHER,
        licence_basis="portal_terms",
        url=PORTAL + "municipalities-in-qatar-2025/exports/json",
    )
    body = json.dumps(
        _portal_meta("Invented changed publisher", licence="", licence_url="")
    ).encode()
    failure = fetch_entry(entry, lambda url: _ok(url, body), tmp_path, _clock, _sleep)
    assert failure is not None and failure.check == "publisher_mismatch"
    assert not list(tmp_path.rglob("*"))


@pytest.mark.parametrize(
    "key",
    [
        "wage_sector",
        "wage_bands_priv",
        "work_hours_act",
        "cpi_group",
        "zone_population",
        "census_hh_type_2020",
        "bnd_muni_2025",
    ],
)
def test_activated_portal_fetches_with_declared_schema(tmp_path, key):
    entry = next(e for e in load_registry() if e.key == key)
    values = {
        "string": "invented",
        "integer": 1,
        "number": 1.5,
        "point_2d": {"lon": 1.0, "lat": 2.0},
        "geojson_geometry": {"type": "Polygon", "coordinates": []},
        # S2-T08 part B mismatch 4: an invented Feature wrapping a polygon.
        "geojson_feature_polygon": {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[1.0, 2.0], [1.5, 2.0], [1.5, 2.5], [1.0, 2.0]]]],
            },
            "properties": {},
        },
    }
    row = {name: values[kind] for name, kind in entry.columns}
    body = json.dumps([row] * entry.row_count_min).encode()
    meta = _portal_meta(entry.publisher)
    if key == "bnd_muni_2025":
        meta = _portal_meta("", licence="", licence_url="")

    def transport(url):
        return _ok(url, body if url == entry.url else json.dumps(meta).encode())

    assert fetch_entry(entry, transport, tmp_path, _clock, _sleep) is None
    side = _sidecar(tmp_path)
    assert side["row_count"] == entry.row_count_min
    assert side["columns"] == [{"name": n, "type": t} for n, t in entry.columns]
    assert side["public_splits"] == list(entry.public_splits)


def test_accident_awaits_byte_bound_without_fetching(tmp_path):
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from custodian.tests.support.fetch_build import run_build

    entry = next(e for e in load_registry() if e.key == "accident")

    def transport(url):
        pytest.fail("accident must await the lead's byte bound")

    outcome = run_build((entry,), transport, fixture_cache, _clock, _sleep)
    assert outcome.failure is None
    assert any("partition_byte_bound_unconfirmed" in line for line in outcome.lines)
    assert not (fixture_cache / "accident").exists()


@pytest.mark.parametrize(
    "size,span,reason",
    [(3, (3, 3), ""), (4, (2, 3), "metadata_bytes"), (1, (2, 3), "metadata_bytes")],
)
def test_accident_stream_span(size, span, reason):
    from eii_custodian.publicdata.fetch.partitions import bounded_partition_reader
    from eii_custodian.publicdata.fetch.transport import _METADATA_LIMIT

    seen = []

    def transport(url):
        seen.append(_METADATA_LIMIT.get())
        return _ok(url, b"x" * size)

    url = PORTAL + "syn/exports/json?where=year%28accident_year%29%3D2001"
    reader = bounded_partition_reader(transport, {2001: span}, _sleep)
    if reason:
        with pytest.raises(Exception, match=reason):
            reader(url)
    else:
        assert reader(url).body == b"xxx"
    assert seen == [3]
    assert _METADATA_LIMIT.get() is None


def test_accident_missing_span_before_fetch():
    from eii_custodian.publicdata.fetch.partitions import bounded_partition_reader

    def transport(url):
        pytest.fail("unreviewed partition requested")

    with pytest.raises(Exception, match="partition_byte_bound_unconfirmed"):
        bounded_partition_reader(transport, {}, _sleep)(
            PORTAL + "syn/exports/json?where=year%28accident_year%29%3D2001"
        )
