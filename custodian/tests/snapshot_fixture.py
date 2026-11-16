"""Publish invented cache inputs and record the fixture's reviewed selection."""

import os
from dataclasses import replace
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.cache_fixture import write_cached


def road(cache: Path, body: bytes) -> str:
    entry = next(row for row in load_registry() if row.key == "roads_osm")
    return write_cached(cache, entry, body).stem


def place(
    path: Path, *, publisher: str = "SYN", retrieved: str = "2026-11-14T00:00:00Z"
) -> Path:
    cache = path.parents[2]
    key = path.parent.relative_to(cache).as_posix()
    source = key.split("/")[0]
    entry = replace(
        next(row for row in load_registry() if row.source_id == source),
        key=key,
        extension=path.suffix.lstrip("."),
        publisher=publisher,
    )
    selected = write_cached(cache, entry, path.read_bytes(), retrieved_utc=retrieved)
    path.unlink()
    os.link(selected, path)
    alias = path.with_suffix(".meta.json")
    alias.unlink(missing_ok=True)
    os.link(selected.with_suffix(".meta.json"), alias)
    return selected


def manifest(folder: Path, body: bytes) -> str:
    from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex

    digest = sha256_hex(body)
    commit_pair(
        folder / "manifests",
        digest,
        "json",
        body,
        {
            "source_id": "un_comtrade",
            "key": "un_comtrade",
            "retrieved_utc": "2026-11-16T08:00:00Z",
            "sha256": digest,
            "bytes": len(body),
        },
    )
    return digest
