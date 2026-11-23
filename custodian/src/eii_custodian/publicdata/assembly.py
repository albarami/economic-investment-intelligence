"""Ordered execution and output checks for the public assembly adapters.

This runner does not fetch, select sources or assert release completeness. The
production inventory and adapters supply the steps and their required outputs;
an execution trace alone is never release evidence. A frame step owns its nested
grids and places calls, so they must not be supplied as extra steps.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.fetch.bounded import file_hash

# Approved plan r3, section 4 item 2. Each adapter is invoked exactly once.
PHASES = (
    "intake_evidence",
    "fetch_archive",
    "investment_capture",
    "reviewed_selections",
    "frame",
    "register_tables",
    "spine_graph",
    "additions",
    "gis_property_singles",
    "fsq",
    "series_stage",
    "heights",
    "trade_reconciliation",
    "busyness",
    "method_pins",
    "final_audit",
    "draw",
    "reports",
)


class AssemblyError(ValueError):
    """A fixed assembly refusal, without a path, value or upstream diagnostic."""


@dataclass(frozen=True)
class Step:
    """One adapter and its independently declared output paths under the root.

    The adapter returns a relative path-to-hash mapping after completing its own
    source, schema and method checks. Read-only phases may declare no files.
    """

    name: str
    run: Callable[[], Mapping[str, str]]
    outputs: tuple[str, ...]


def _output_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if (
        not name
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != name
        or name == "."
    ):
        raise AssemblyError("assembly_output_invalid")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise AssemblyError("assembly_output_invalid")
    return path


def run_steps(
    root: Path, steps: tuple[Step, ...], *, lines: list[str] | None = None
) -> tuple[str, ...]:
    """Run the closed plan in order; stop on a refusal or an incorrect output.

    Validate the whole plan before invoking an adapter. Verify each adapter's
    complete declared output set and streamed hashes before invoking the next.
    Producers retain their own failure types; this function cannot turn a
    refused producer into a successful trace. No report writer runs early.
    """
    from .assembly_refusals import stage_refusals

    with stage_refusals(lines, "require_complete"):
        if tuple(step.name for step in steps) != PHASES:
            raise AssemblyError("assembly_order_invalid")
        owned: set[str] = set()
        for step in steps:
            for name in step.outputs:
                _output_path(root, name)
                if name in owned:
                    raise AssemblyError("assembly_output_invalid")
                owned.add(name)
    completed: list[str] = []
    for step in steps:
        with stage_refusals(lines, step.name):
            result = step.run()
            if not isinstance(result, Mapping) or set(result) != set(step.outputs):
                raise AssemblyError("assembly_output_invalid")
            for name in step.outputs:
                path = _output_path(root, name)
                digest = result[name]
                try:
                    if not path.is_file() or file_hash(path) != digest:
                        raise AssemblyError("assembly_output_invalid")
                except OSError:
                    raise AssemblyError("assembly_output_invalid") from None
        completed.append(step.name)
    return tuple(completed)
