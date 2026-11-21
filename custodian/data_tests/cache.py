"""Read one explicitly pinned receipt; never fetch or select a latest version."""

import json
from pathlib import Path

from eii_core.calc.facts import SourceChain
from eii_core.calc.public_series import C2_METHOD_VERSION
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.build import read_cached
from eii_custodian.publicdata.frame.mapping import POP_FIELDS, fields
from eii_custodian.publicdata.series.parse import confirmed_rows, selected_source

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/public_cache"


def cached(cache: Path, source: str, digest: str):
    entry = next(row for row in load_registry() if row.key == source)
    try:
        rows, receipt = selected_source(cache, entry, digest)
    except ValueError as error:
        if "hash_mismatch" in str(error) or "hash mismatch" in str(error):
            raise ValueError("receipt_hash_mismatch:" + source) from error
        if str(error) in {
            "snapshot_missing",
            "snapshot_index_invalid",
            "snapshot_path_invalid",
        }:
            raise ValueError("public_cache_missing:" + source) from None
        raise
    if source == "pop_muni":
        # The frame owns this source's confirmed shape, not the series adapter.
        for row in rows:
            fields(row, POP_FIELDS, source)
    else:
        rows = confirmed_rows(entry, rows)
    chain = SourceChain(
        source,
        entry.release_tables[0],
        "method-card",
        C2_METHOD_VERSION if source == "lic_cancelled" else "S2-T07-v1",
        str(receipt["publisher"]),
        entry.slug,
        str(receipt["fetch_url"]),
        entry.licence_id,
        str(receipt["retrieved_utc"])[:10],
        digest,
    )
    return rows, chain


def _pin(source: str):
    """The lead supplies a source-to-SHA map inside the documented public cache."""
    cache = CACHE
    pins = cache / "method_pins.json"
    if not pins.is_file():
        raise ValueError("public_cache_missing:" + source)
    digest = json.loads(pins.read_text()).get(source)
    if not isinstance(digest, str):
        raise ValueError("public_cache_missing:" + source)
    return digest


def pinned(source: str):
    return cached(CACHE, source, _pin(source))


def pinned_body(source: str):
    """Reuse the frame's receipt reader for binary workbooks and layer envelopes."""
    entry = next(row for row in load_registry() if row.key == source)
    digest = _pin(source)
    body, receipt = read_cached(CACHE, entry, digest=digest, decode=lambda body: body)
    chain = SourceChain(
        source,
        entry.release_tables[0],
        "method-card",
        "S2-T07-v1",
        str(receipt["publisher"]),
        entry.title_en,
        str(receipt["fetch_url"]),
        entry.licence_id,
        str(receipt["retrieved_utc"])[:10],
        digest,
    )
    return body, chain
