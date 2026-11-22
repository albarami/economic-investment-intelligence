"""Lead-shell proof check: explicit live read or strictly offline stored replay."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any, cast

from eii_custodian.publicdata.fetch.awards import (
    SOURCE,
    _proof_report,
    fetch_awards,
    replay_awards,
)
from eii_custodian.publicdata.fetch.registry import load_registry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("replay", "live"))
    parser.add_argument("--cache", required=True, type=Path)
    args = parser.parse_args(argv)
    entry = next(entry for entry in load_registry() if entry.source_id == SOURCE)

    def clock() -> str:
        return datetime.now(UTC).isoformat()

    if args.mode == "replay":
        report = replay_awards(entry, args.cache, clock)
    else:
        from eii_custodian.publicdata.fetch.transport import open_https

        side = fetch_awards(entry, open_https, args.cache, clock, sleep).sidecar
        report = _proof_report(cast(dict[str, Any], side["award_links"]))
        report["award_readers"] = side["award_readers"]
    print(json.dumps(report, sort_keys=True))
    return 1 if report["award_links"]["incomplete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
