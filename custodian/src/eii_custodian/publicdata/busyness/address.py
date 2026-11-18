"""In-memory request addresses from the build's receipted Overture file."""

from __future__ import annotations

from pathlib import Path

from eii_custodian.publicdata.places import read
from eii_custodian.publicdata.places.areas import AreaError
from eii_custodian.publicdata.places.fetch import FILE_KEYS
from eii_custodian.publicdata.places.integrate import _opened_place


def read_addresses(cache: Path) -> dict[str, str]:
    """Reuse the places path and receipt checks before decoding any Parquet."""
    try:
        located = _opened_place(cache, FILE_KEYS[0])
    except AreaError as exc:
        raise ValueError(exc.reason) from None
    if located is None:
        return {}
    path, receipt = located
    read.require_receipt(path, receipt)
    connection = read._connect()
    try:
        rows = connection.execute(
            "SELECT id, addresses FROM read_parquet(?)", [str(path)]
        ).fetchall()
    finally:
        connection.close()
    result = {}
    for identifier, addresses in rows:
        if not addresses:
            continue
        first = addresses[0] or {}
        if not first.get("freeform") and not first.get("locality"):
            continue
        result[identifier] = ", ".join(
            first[field]
            for field in ("freeform", "locality", "country")
            if first.get(field)
        )
    return result
