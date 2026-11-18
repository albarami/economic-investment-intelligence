"""The frame's own written municipality output, read back by the series stage."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MUNICIPALITY_OUTPUT = Path("frame_s2_t02") / "municipalities.json"


def write_municipality_output(
    cache: Path,
    rows: list[dict[str, Any]],
    sources: Mapping[str, Mapping[str, object]] | None = None,
) -> None:
    """Persist the frame's municipality table rows the same build produced."""
    directory = cache / MUNICIPALITY_OUTPUT.parent
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(rows),
        "municipalities": [
            {
                "municipality_code": row["municipality_code"],
                "name_en": row["name_en"],
                "name_ar": row["name_ar"],
            }
            for row in rows
        ],
    }
    if sources is not None:
        payload["upstream_sha256"] = {
            key: sources[key]["sha256"] for key in ("bnd_hdx", "bnd_zone_2020")
        }
    (cache / MUNICIPALITY_OUTPUT).write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
