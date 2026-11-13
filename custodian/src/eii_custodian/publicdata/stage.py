"""Section 10 regression stage. A present figure that disagrees fails the build.

Parsers that read the cached files belong to later tasks. Until a figure file
is written into the cache, the stage records coverage not_measured and does
not invent a value. A planted figure that differs from the published anchor
fails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Anchors copied from docs/04_PUBLIC_DATA_PACK.md section 10. They are the
# published figures the stage compares; this module does not compute them.
EXPECTED: dict[str, dict[str, str]] = {
    "PUB-62": {
        "zone_69_2021": "429964072",
        "zone_69_2025": "1436402796",
        "ratio_2dp": "3.34",
        "sum_ratio_2dp": "1.34",
    },
    "PUB-63": {
        "mean_2020": "10084",
        "mean_2025": "11855",
        "rise": "1771",
        "rise_percent_1dp": "17.6",
        "within_groups": "38",
        "mix": "1733",
        "mix_share_1dp": "97.8",
    },
    "PUB-64": {
        "production_value": "6337897",
        "establishments": "2086",
        "employees": "41458",
        "compensation": "1308140",
        "operating_surplus": "1247422",
        "average_annual_wage": "31579",
        "goods_share_1dp": "40.6",
        "services_share_1dp": "16.5",
    },
    "PUB-65": {"italy_2dp": "8.69", "saudi_arabia_2dp": "11.45"},
    "PUB-66": {"rows_2025": "216073", "value_bn_2dp": "138.53"},
    "PUB-67": {
        "rows": "13189",
        "sum_count": "249622",
        "distinct_codes": "4755",
        "isic_prefix": "211277",
        "other_seven": "11276",
        "legacy_six": "26844",
        "other_lengths": "225",
        "al_daayen_5610101": "361",
        "national_5610101": "4782",
    },
    "PUB-68": {
        "sum_count": "161055",
        "undated": "7386",
        "july_2020": "40791",
        "june_2022": "14212",
        "september_2024": "11232",
        "dated_total": "153669",
    },
    "PUB-69": {"sum_count": "12533", "distinct_codes": "610"},
    "PUB-70": {
        "metro_2025_12": "7375367",
        "metro_2024_12": "5529167",
        "growth_0dp": "33",
    },
    "PUB-71": {
        "national_private": "1617208",
        "national_all": "2050252",
        "national_1dp": "78.9",
        "zone_69_0dp": "72",
        "zone_70_0dp": "45",
    },
    "PUB-72": {
        "al_daayen_residents": "111282",
        "national_residents": "3219982",
        "al_daayen_0dp": "32",
        "national_0dp": "15",
    },
    "PUB-73": {"places_qa": "26383", "establishments_2020": "71203"},
}

SECTION_10_IDS = tuple(EXPECTED)


@dataclass(frozen=True)
class StageResult:
    """Coverage notes, and the first figure id that disagreed, if any."""

    missing: tuple[str, ...]
    mismatch: str


def run_stage(cache: Path) -> StageResult:
    """Compare figure files under cache/figures with the section 10 anchors."""
    missing: list[str] = []
    for figure_id in SECTION_10_IDS:
        path = cache / "figures" / f"{figure_id}.json"
        if not path.is_file():
            missing.append(figure_id)
            continue
        got = json.loads(path.read_text(encoding="utf-8"))
        if got != EXPECTED[figure_id]:
            return StageResult(tuple(missing), figure_id)
    return StageResult(tuple(missing), "")
