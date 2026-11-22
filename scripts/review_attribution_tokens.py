"""List the attribution tokens of the receipted open places; lead-shell only, offline.

``review_attribution_tokens.py CACHE OUTPUT_WORKSHEET`` writes a local
worksheet (token, count) of the distinct ``dataset`` tokens of the record-level
``sources[]`` entry, the token ``_keep`` of the places build looks up, of the
places inside the frame box. An empty token and an OpenStreetMap token are not
listed (the build never looks them up). It prints the number of tokens only and
never writes ``places_ovt_attribution.csv``; the reviewer does, before H1 runs.
An expected failure prints one closed reason and no text of the failure.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.build import _OSM, _dataset
from eii_custodian.publicdata.places.integrate import _place_from_registry, _tag
from eii_custodian.publicdata.places.read import (
    ReadPlace,
    _in_box,
    read_place_file,
    require_receipt,
)
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX
from review_place_keys import EXPECTED, refusal

REVIEW = Path(__file__).resolve().parents[1] / "custodian" / "publicdata" / "review"
REVIEW_FILE = "places_ovt_attribution.csv"
BOX = (FRAME_BOX.west, FRAME_BOX.south, FRAME_BOX.east, FRAME_BOX.north)


def tokens(places: Sequence[ReadPlace]) -> Counter[str]:
    """Count the looked-up token of each place inside the frame box."""
    counted: Counter[str] = Counter()
    for place in places:
        if not _in_box(float(place.lon), float(place.lat), BOX):
            continue
        token = _dataset(place.source.entry)
        if token is None or token.casefold() in _OSM:
            continue
        counted[token] += 1
    return counted


def write_worksheet(output: Path, counted: Counter[str]) -> None:
    """Write token and count, sorted by token; refuse the review file and overwrites."""
    if output.name == REVIEW_FILE:
        raise PlacesError("output_is_review_file")
    with output.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("token", "count"))
        for token in sorted(counted):
            writer.writerow((token, counted[token]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        located = _place_from_registry(args.cache, load_registry())
        if located is None:
            raise PlacesError("places_file_unreceipted")
        path, receipt = located
        require_receipt(path, receipt)
        counted = tokens(read_place_file(path, _tag(REVIEW), frame_box=BOX))
        write_worksheet(args.output, counted)
    except EXPECTED as exc:
        print(f"REFUSED {refusal(exc)}")
        return 2
    print(f"tokens={len(counted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
