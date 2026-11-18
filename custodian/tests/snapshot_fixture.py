"""Publish invented cache inputs and record the fixture's reviewed selection."""

import json
import os
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
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


def update_receipt(
    cache: Path, key: str, digest: str, changes: Mapping[str, object]
) -> None:
    """Plant semantic receipt fields inside a consistent invented snapshot.

    Snapshot integrity tests must corrupt files directly. This helper keeps the
    envelope consistent so downstream receipt and lineage guards are reached.
    """
    directory = cache / key
    selected = read_snapshot(directory, digest)
    receipt = dict(selected.sidecar, **changes)
    selected.receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False), encoding="utf-8"
    )
    index = directory / "index" / (digest + ".json")
    row = json.loads(index.read_text(encoding="utf-8"))
    row["receipt_sha256"] = sha256_hex(selected.receipt_path.read_bytes())
    for field in ("source_id", "key", "retrieved_utc", "sha256", "bytes"):
        row[field] = receipt[field]
    index.write_text(json.dumps(row), encoding="utf-8")
