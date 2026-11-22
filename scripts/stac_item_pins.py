"""Lead-shell, offline STAC pin proposals; never install or replace a pin."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot, reviewed_selections


def propose(cache: Path, entries: Sequence[Entry]) -> dict[str, str]:
    """Return only new pins, after verifying every selected STAC index."""
    existing = reviewed_selections(cache)
    proposed: dict[str, str] = {}
    for entry in entries:
        if not entry.key.startswith("bldg_ovt/stac-"):
            continue
        identities = []
        for index in sorted((cache / entry.key / "index").glob("*.json")):
            snapshot = read_snapshot(cache / entry.key, index.stem)
            if (
                snapshot.sidecar.get("key") != entry.key
                or snapshot.sidecar.get("source_id") != entry.source_id
            ):
                raise ValueError("stac_pin_snapshot_key")
            identities.append(index.stem)
        if not identities:
            raise ValueError("stac_pin_snapshot_missing")
        if len(identities) != 1:
            raise ValueError("stac_pin_snapshot_ambiguous")
        identity = identities[0]
        if entry.key in existing:
            if existing[entry.key] != identity:
                raise ValueError("stac_pin_conflict")
        else:
            proposed[entry.key] = identity
    return proposed


def write_proposal(cache: Path, entries: Sequence[Entry], output: Path) -> None:
    """Create a new proposal outside the cache, preserving all existing files."""
    if output.resolve().is_relative_to(cache.resolve()):
        raise ValueError("stac_pin_output_in_cache")
    body = json.dumps(propose(cache, entries), indent=2, sort_keys=True) + "\n"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(body)


def main(argv: Sequence[str] | None = None) -> int:
    """Explicit cache and output; a refusal exits nonzero."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--registry", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        write_proposal(args.cache, load_registry(args.registry), args.output)
    except (OSError, ValueError):
        print("stac_item_pins: proposal_refused", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
