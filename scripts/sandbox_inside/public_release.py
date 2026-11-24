"""Sandbox-only Public assembly writer; no product import or network."""

from __future__ import annotations

import sys
from pathlib import Path


def main(args: list[str]) -> int:
    if len(args) != 3:
        return 2
    code, cache, stage = map(Path, args)
    sys.path[:0] = [str(code / "core/src"), str(code / "custodian/src")]
    from eii_core.reasons import reason
    from eii_custodian.release.assembly import build, read_assembly

    try:
        if (
            read_assembly(cache)["scalars"].get("release_kind", "public_only")
            != "public_only"
        ):
            print("protected_release_not_built", file=sys.stderr)
            return 1
        build(cache, stage)
    except Exception as error:
        print(reason(error), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
