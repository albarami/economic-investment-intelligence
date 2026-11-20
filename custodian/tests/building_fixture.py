"""Invented national inventory inputs; no fetched file or network."""

import json
from dataclasses import dataclass, replace
from pathlib import Path

from shapely.geometry import box

from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.review.cache_fixture import write_cached

PARTS = tuple(f"bldg_ovt/part-{part}" for part in ("00288", "00384", "00385"))
COLLECTION = "bldg_ovt/stac-collection"


def footprint(building_id="SYN-B-A", geometry=None, **values):
    return {
        "id": building_id,
        "geometry": box(51.1, 25.1, 51.11, 25.11).wkb if geometry is None else geometry,
        "height": None,
        "num_floors": None,
        "is_underground": None,
        "sources": [
            {"property": "", "dataset": "SYN contributor", "license": "SYN licence"}
        ],
        **values,
    }


def parquet(
    path, rows, *, schema="2.0.0", crs="absent", drop=(), geo=None, kinds_override=None
):
    import duckdb

    kinds = {
        "id": "VARCHAR",
        "geometry": "BLOB",
        "height": "DOUBLE",
        "num_floors": "INTEGER",
        "is_underground": "BOOLEAN",
        "sources": "STRUCT(property VARCHAR, dataset VARCHAR, license VARCHAR)[]",
    }
    kinds.update(kinds_override or {})
    kinds = {key: value for key, value in kinds.items() if key not in drop}
    connection = duckdb.connect()
    try:
        connection.execute(
            "CREATE TABLE buildings ("
            + ",".join(f"{k} {v}" for k, v in kinds.items())
            + ")"
        )
        for row in rows:
            connection.execute(
                "INSERT INTO buildings VALUES (" + ",".join("?" for _ in kinds) + ")",
                [row.get(key) for key in kinds],
            )
        metadata = {
            "primary_column": "geometry",
            "columns": {
                "geometry": {
                    "encoding": "WKB",
                    "geometry_types": ["Polygon", "MultiPolygon"],
                }
            },
        }
        if crs != "absent":
            metadata["columns"]["geometry"]["crs"] = crs
        if geo is not None:
            metadata = geo
        connection.execute(
            "COPY buildings TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: ?, geo: ?})",
            [
                str(path),
                json.dumps({"overture-schema-pyspark": schema}),
                json.dumps(metadata),
            ],
        )
    finally:
        connection.close()
    return path.read_bytes()


@dataclass
class World:
    cache: Path
    entries: tuple[Entry, ...]
    selected: dict[str, str]
    boundary: object
    output: Path

    def produce(self, **overrides):
        from eii_custodian.publicdata.buildings import build_buildings

        args = {
            "cache": self.cache,
            "entries": self.entries,
            "selections": self.selected,
            "boundary": self.boundary,
        }
        args.update(overrides)
        return build_buildings(**args)


def world(tmp_path, rows=None, **parquet_options):
    tmp_path.mkdir(parents=True, exist_ok=True)
    base = load_registry()[0]
    keys = (
        *PARTS,
        COLLECTION,
        *(f"bldg_ovt/stac-{part.rsplit('/', 1)[-1]}" for part in PARTS),
        "bnd_hdx",
    )
    entries = tuple(
        replace(
            base,
            key=key,
            source_id=key.split("/")[0],
            url=f"https://syn.invalid/{key}",
            publisher="SYN Publisher",
            title_en="SYN building input",
            licence_id="SYN licence",
            licence_basis="dataset",
            skip_reason="",
            kind="https_file",
            extension="parquet" if key in PARTS else "json",
            basis_note="SYN contributor notice",
            landing_url="https://syn.invalid/schema",
        )
        for key in keys
    )
    by_key = {entry.key: entry for entry in entries}
    cache = tmp_path / "data/public_cache"
    selected = {}

    def store(key, body):
        path = write_cached(cache, by_key[key], body)
        selected[key] = path.stem

    for index, key in enumerate(PARTS):
        content = rows[index] if rows is not None else [footprint(f"SYN-B-{index}")]
        store(
            key, parquet(tmp_path / f"part-{index}.parquet", content, **parquet_options)
        )
    links = []
    for key in keys[4:7]:
        part = "bldg_ovt/" + key.split("stac-", 1)[-1]
        links.append({"rel": "item", "href": by_key[key].url})
        store(
            key,
            json.dumps(
                {
                    "type": "Feature",
                    "stac_version": "1.0.0",
                    "id": key,
                    "bbox": [50.7, 24.4, 51.7, 26.2],
                    "assets": {"data": {"href": by_key[part].url}},
                    "links": [],
                }
            ).encode(),
        )
    store(
        COLLECTION,
        json.dumps(
            {"type": "Collection", "id": "SYN-building", "links": links}
        ).encode(),
    )
    store("bnd_hdx", b"SYN boundary archive")
    return World(
        cache,
        entries,
        selected,
        box(51, 25, 51.4, 25.5),
        cache.parent / "assets/buildings",
    )


def manifest(prepared):
    return json.loads((prepared.output / "manifest.buildings.json").read_text())


def table(prepared):
    return json.loads((prepared.output / "buildings.geojson").read_text())


def bind_height_table(cache, entries, path, *, write_manifest=True):
    """Hand-written lineage prerequisite for isolated C47 hierarchy fixtures.

    These dummy input bodies are invented, not producer output. Full producer
    integration and manifest tamper plants live in test_publicdata_buildings.
    ``write_manifest=False`` supplies registrations without repairing the
    manifest, so missing-manifest and altered-hash plants remain deciding.
    """
    from eii_custodian.publicdata.building_inputs import (
        BUILDING_METHOD,
        dump,
        fingerprint,
    )
    from eii_custodian.publicdata.fetch.bounded import file_hash
    from eii_custodian.publicdata.fetch.snapshots import (
        read_snapshot,
        reviewed_selections,
    )
    from eii_custodian.publicdata.places.read import SOURCE_RELEASE

    if not path.is_file():
        return tuple(entries)
    base = load_registry()[0]
    keys = (*PARTS, "bnd_hdx", COLLECTION)
    added = tuple(
        replace(
            base,
            key=key,
            source_id=key.split("/")[0],
            url=f"https://syn.invalid/{key}",
            publisher="SYN Publisher",
            title_en="SYN inventory dependency",
            licence_id="SYN licence",
            licence_basis="dataset",
            skip_reason="",
            kind="https_file",
            extension="json",
        )
        for key in keys
    )
    chain = {}
    for row in added:
        body = ("SYN isolated hierarchy dependency: " + row.key).encode()
        snapshot = write_cached(cache, row, body)
        chain[row.key] = fingerprint(
            read_snapshot(cache / row.key, snapshot.stem), snapshot.stem
        )
    if write_manifest:
        path.with_name("manifest.buildings.json").write_bytes(
            dump(
                {
                    "method": BUILDING_METHOD,
                    "source_release": SOURCE_RELEASE,
                    "output_sha256": file_hash(path),
                    "national_completeness": True,
                    "source_chain": chain,
                }
            )
        )
    assert set(keys) <= set(reviewed_selections(cache))
    return (*tuple(entries), *added)
