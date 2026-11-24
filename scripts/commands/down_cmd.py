"""Stop only owned API/entry processes and retain every data surface."""

from collections.abc import Mapping, Sequence

from operations.common import Refusal
from operations.deploy import down

from . import exits, table


def run(environ: Mapping[str, str], args: Sequence[str]) -> int:
    if args:
        table.write_usage()
        return 2
    try:
        down(environ)
    except Refusal as error:
        return exits.finish(error.code, "down", error.reason)
    except Exception:
        return exits.finish(4, "down", "process_shutdown_failed")
    print("PASS down: owned application processes stopped; data retained")
    return 0
