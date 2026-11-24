"""Thin Public-only sandbox build command; protected builds stay unimplemented."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from eii_core.reasons import reason
from operations.build import build_release
from operations.common import Refusal

from . import exits, table


def _spec_draft(root: Path, listing: str) -> int:
    """Lead-shell mode: draft the release spec; no build, no approval."""
    from eii_custodian.release.spec_draft import draft

    try:
        paths = json.loads(Path(listing).read_bytes())
        draft(root / "data/public_cache", paths)
    except ValueError as error:
        return exits.finish(
            4, "build-release", reason(error, "producer_schema_refused")
        )
    except OSError:
        return exits.finish(4, "build-release", "producer_receipt_missing")
    print("PASS build-release: release spec draft written for the lead's review")
    return 0


def run(root: Path, environ: Mapping[str, str], args: Sequence[str]) -> int:
    if len(args) == 2 and args[0] == "--spec-draft":
        return _spec_draft(root, args[1])
    if args:
        table.write_usage()
        return 2
    if any(
        environ.get(key)
        for key in ("EII_PARAMETER_SET", "EII_WINDOW_KEY", "EII_WORLD_SEED")
    ):
        return exits.finish(4, "build-release", "public_only_parameter_selection")
    try:
        build_release(root)
    except Refusal as error:
        return exits.finish(error.code, "build-release", error.reason)
    except Exception as error:
        return exits.finish(4, "build-release", reason(error))
    print("PASS build-release: public_only export retained; build vault removed")
    return 0
