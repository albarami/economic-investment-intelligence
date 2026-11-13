"""Test-only command: three inputs and one output, never a project command."""

import sys
from pathlib import Path

from .inputs import FlowUnitError, NoPathError
from .run import calculate


def main(arguments: list[str]) -> int:
    if len(arguments) != 4:
        print("Expected flows roads parameters output", file=sys.stderr)
        return 2
    try:
        result = calculate(*(Path(item) for item in arguments[:3]))
    except (FlowUnitError, NoPathError) as error:
        print(str(error), file=sys.stderr)
        return 3
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    Path(arguments[3]).write_bytes(result.to_bytes())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
