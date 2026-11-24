"""Stop only owned API/entry processes and retain every data surface."""

from collections.abc import Mapping, Sequence

from operations.common import Refusal
from operations.deploy import down

from . import exits, table


def run(environ: Mapping[str, str], args: Sequence[str]) -> int:
    previous_boot = list(args) == ["--previous-boot"]
    if args and not previous_boot:
        table.write_usage()
        return 2
    try:
        down(environ, previous_boot=previous_boot)
    except Refusal as error:
        return exits.finish(error.code, "down", error.reason)
    except Exception:
        return exits.finish(4, "down", "process_shutdown_failed")
    if previous_boot:
        print("PASS down: previous-boot process records retired; data retained")
        return 0
    print("PASS down: owned application processes stopped; data retained")
    return 0
