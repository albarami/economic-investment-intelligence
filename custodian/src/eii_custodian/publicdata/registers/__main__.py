"""Offline lead-shell verification entry point. Diagnostics contain reason codes only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import NoReturn

from .build import build
from .contracts import RegisterError, refuse
from .intake import from_environment, read_file
from .provenance import Frame, digest


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        refuse("register_arguments")


def main(argv: list[str]) -> int:
    try:
        parser = _Parser(description=__doc__)
        parser.add_argument("--frame-cells", required=True)
        parser.add_argument("--frame-sha256", required=True)
        parser.add_argument("--biz-index-sha256", required=True)
        parser.add_argument("--fc-index-sha256", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument(
            "--release-kind", choices=("public_only", "protected"), required=True
        )
        args = parser.parse_args(argv)
        body = read_file(Path(args.frame_cells), 32 * 1024 * 1024)
        if digest(body) != args.frame_sha256:
            refuse("frame_hash_mismatch")
        cells = json.loads(body)
        if (
            not isinstance(cells, list)
            or any(type(cell) is not int for cell in cells)
            or len(cells) != len(set(cells))
        ):
            refuse("frame_schema")
        frame = Frame(frozenset(cells))
        current, history = from_environment(
            os.environ,
            index_hashes={
                "biz_register": args.biz_index_sha256,
                "fc_register": args.fc_index_sha256,
            },
        )
        build(Path(args.output), args.release_kind, frame, current, history)
    except RegisterError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("register_verification_failed", file=sys.stderr)
        return 1
    print("register_inputs_validated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
