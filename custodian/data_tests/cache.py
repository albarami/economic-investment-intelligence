"""Read one explicitly pinned receipt; never fetch or select a latest version."""

import json
from pathlib import Path

from eii_core.calc.facts import SourceChain
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.series.parse import confirmed_rows, selected_source

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/public_cache"


def cached(cache: Path, source: str, digest: str):
    entry = next(row for row in load_registry() if row.key == source)
    body = cache / source / f"{digest}.{entry.extension}"
    receipt_path = cache / source / f"{digest}.meta.json"
    if not body.is_file() or not receipt_path.is_file():
        raise ValueError("public_cache_missing:" + source)
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("sha256") != digest:
        raise ValueError("receipt_hash_mismatch:" + source)
    try:
        rows, receipt = selected_source(cache, entry, digest)
    except ValueError as error:
        if "hash mismatch" in str(error):
            raise ValueError("receipt_hash_mismatch:" + source) from error
        raise
    rows = confirmed_rows(entry, rows)
    chain = SourceChain(
        source,
        entry.release_tables[0],
        "method-card",
        "S2-T07-v1",
        str(receipt["publisher"]),
        entry.slug,
        str(receipt["fetch_url"]),
        entry.licence_id,
        str(receipt["retrieved_utc"])[:10],
        digest,
    )
    return rows, chain


def pinned(source: str):
    """The lead supplies a source-to-SHA map inside the documented public cache."""
    cache = CACHE
    pins = cache / "method_pins.json"
    if not pins.is_file():
        raise ValueError("public_cache_missing:" + source)
    digest = json.loads(pins.read_text()).get(source)
    if not isinstance(digest, str):
        raise ValueError("public_cache_missing:" + source)
    return cached(cache, source, digest)
