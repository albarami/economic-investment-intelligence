"""Persist the S2-T09 pin artifact and its generation configuration as a pair.

The writer reads only the recorded generation configuration and the exact
producer results bound to the build; it never opens a public snapshot, the
source-check record or the method document. The pair is credited only when
both files persist: a half-pair is removed, never left usable, and files of an
earlier run are never re-credited.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypeGuard

from .assembly import AssemblyError
from .assembly_io import local, write_record
from .method_card_producer import produce_pin_artifact

PIN_ARTIFACT_NAME = "assembly/s2_t09_pin_artifact.json"
PIN_CONFIG_NAME = "assembly/s2_t09_pin_generation_config.json"
PIN_INPUTS_MISSING = "pin_inputs_missing"


def pin_inputs_bound(
    generation_config: object, pin_rows: Sequence[object]
) -> TypeGuard[Mapping[str, object]]:
    """True when a recorded configuration mapping and producer rows are bound."""
    return isinstance(generation_config, Mapping) and bool(pin_rows)


def _drop_half_pair(cache: Path) -> None:
    """Remove an unwritten pair's other half; best effort, the refusal stands."""
    for name in (PIN_ARTIFACT_NAME, PIN_CONFIG_NAME):
        try:
            local(cache, name).unlink()
        except OSError:
            pass
        except AssemblyError:
            # A symlinked half never resolves inside the cache: remove the
            # link itself, never its target, so no half pair survives. A
            # refused parent — the assembly folder, or the cache root, is a
            # symlink — means nothing was written inside the cache envelope,
            # so no half pair exists to remove and nothing is ever deleted
            # through such a link.
            try:
                local(cache, str(Path(name).parent))
            except AssemblyError:
                continue
            (cache / name).unlink(missing_ok=True)


def write_pin_pair(
    cache: Path,
    generation_config: Mapping[str, object] | None,
    pin_rows: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    """Write both named S2-T09 outputs from the recorded inputs, or refuse.

    The artifact is built by ``produce_pin_artifact`` from the configuration
    and the producer rows; the configuration itself is persisted unchanged
    beside it, so the consumer's settings hash binds the producing bytes.
    Any refusal of either write — a refused path, an unserializable value or
    an operating-system error — removes the other half and refuses with the
    one closed reason ``pin_output_pair_unwritten``, never a half pair.
    """
    if not pin_inputs_bound(generation_config, pin_rows):
        raise AssemblyError(PIN_INPUTS_MISSING)
    artifact = produce_pin_artifact(generation_config, pin_rows)
    try:
        outputs = write_record(cache, PIN_ARTIFACT_NAME, artifact)
        outputs.update(write_record(cache, PIN_CONFIG_NAME, generation_config))
    except (OSError, AssemblyError, ValueError, TypeError):
        _drop_half_pair(cache)
        raise AssemblyError("pin_output_pair_unwritten") from None
    return outputs
