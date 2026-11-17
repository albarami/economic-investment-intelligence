"""Read back the municipalities the same build's frame wrote into the cache."""

import json
from pathlib import Path

from eii_custodian.publicdata.frame.municipality_output import MUNICIPALITY_OUTPUT

from .parse import Municipality

FRAME_ABSENT = "municipality_frame_absent"
CODE_REPEATED = "municipality_code_repeated"
NAME_REPEATED = "municipality_name_repeated"
FIELD_EMPTY = "municipality_field_empty"
COUNT_MISMATCH = "municipality_count_mismatch"


class MunicipalityFrameRefused(ValueError):
    """The written frame output is absent or fails the read-back checks."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def frame_municipalities(cache: Path) -> tuple[Municipality, ...]:
    """Return ``Municipality(code, name_ar)`` rows from the frame output."""
    path = cache / MUNICIPALITY_OUTPUT
    if not path.is_file():
        raise MunicipalityFrameRefused(FRAME_ABSENT)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MunicipalityFrameRefused(FRAME_ABSENT) from exc
    return parse_frame_municipalities(payload)


def parse_frame_municipalities(payload: object) -> tuple[Municipality, ...]:
    """Validate already-read frame rows so lineage can hash the same bytes."""
    if not isinstance(payload, dict):
        raise MunicipalityFrameRefused(FRAME_ABSENT)
    rows = payload.get("municipalities")
    if (
        not isinstance(rows, list)
        or not rows
        or not all(
            isinstance(row, dict)
            and isinstance(row.get("municipality_code"), str)
            and isinstance(row.get("name_ar"), str)
            for row in rows
        )
    ):
        raise MunicipalityFrameRefused(FRAME_ABSENT)
    if any(not row["municipality_code"] or not row["name_ar"] for row in rows):
        raise MunicipalityFrameRefused(FIELD_EMPTY)
    codes = [row["municipality_code"] for row in rows]
    if len(set(codes)) != len(codes):
        raise MunicipalityFrameRefused(CODE_REPEATED)
    names = [row["name_ar"] for row in rows]
    if len(set(names)) != len(names):
        raise MunicipalityFrameRefused(NAME_REPEATED)
    count = payload.get("count")
    if type(count) is not int or count != len(rows):
        raise MunicipalityFrameRefused(COUNT_MISMATCH)
    return tuple(Municipality(row["municipality_code"], row["name_ar"]) for row in rows)
