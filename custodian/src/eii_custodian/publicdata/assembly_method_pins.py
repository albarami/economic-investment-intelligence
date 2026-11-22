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

from .assembly import AssemblyError
from .assembly_io import local, write_record
from .method_card_producer import produce_pin_artifact

PIN_ARTIFACT_NAME = "assembly/s2_t09_pin_artifact.json"
PIN_CONFIG_NAME = "assembly/s2_t09_pin_generation_config.json"


def _drop_half_pair(cache: Path) -> None:
    """Remove an unwritten pair's other half; best effort, the refusal stands."""
    for name in (PIN_ARTIFACT_NAME, PIN_CONFIG_NAME):
        try:
            local(cache, name).unlink()
        except OSError:
            pass
        except AssemblyError:
            # A symlinked half never resolves inside the cache: remove the
            # link itself, never its target, so no half pair survives.
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
    if not isinstance(generation_config, Mapping) or not pin_rows:
        raise AssemblyError("pin_inputs_missing")
    artifact = produce_pin_artifact(generation_config, pin_rows)
    try:
        outputs = write_record(cache, PIN_ARTIFACT_NAME, artifact)
        outputs.update(write_record(cache, PIN_CONFIG_NAME, generation_config))
    except (OSError, AssemblyError, ValueError, TypeError):
        _drop_half_pair(cache)
        raise AssemblyError("pin_output_pair_unwritten") from None
    return outputs
