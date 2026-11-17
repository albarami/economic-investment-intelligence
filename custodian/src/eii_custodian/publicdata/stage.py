"""Section 10 regression stage. A present figure that disagrees fails the build.

Parsers that read the cached files belong to later tasks. Until a figure file
is written into the cache, the stage records coverage not_measured and does
not invent a value. A planted figure that differs from the published anchor
fails. PUB-71's expected figures are never committed: the stage reads them
from one local record inside the uncommitted cache. A produced figure whose
local record is absent still fails the build: the row keeps its not-measured
coverage and is named so the build cannot succeed on missing evidence.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from eii_custodian.publicdata.fetch.registry import Entry

if TYPE_CHECKING:
    from eii_custodian.publicdata.fetch.build import FetchFailure

# Anchors of the openly licensed rows, copied from docs/04_PUBLIC_DATA_PACK.md
# section 10. They are the published figures the stage compares; this module
# does not compute them. PUB-71's source has no open licence (decision 0026
# item 5): its expected rounded results stay in one local record inside the
# uncommitted public cache, and no value of it is committed.
EXPECTED: dict[str, dict[str, str]] = {
    "PUB-62": {
        "zone_69_2021": "429964072",
        "zone_69_2025": "1436402796",
        "ratio_2dp": "3.34",
        "sum_ratio_2dp": "1.34",
    },
    "PUB-63": {
        "populated_groups": "17",
        "mean_2020": "10084",
        "mean_2025": "11855",
        "rise": "1771",
        "rise_percent_1dp": "17.6",
        "within_groups": "38",
        "mix": "1733",
        "mix_share_1dp": "97.8",
    },
    "PUB-64": {
        "establishments": "2086",
        "employees": "41458",
        "compensation": "1308140",
        "operating_surplus": "1247422",
        "average_annual_wage": "31579",
        "goods_share_1dp": "40.6",
        "services_share_1dp": "16.5",
    },
    "PUB-65": {
        "italy_2dp": "8.69",
        "saudi_arabia_2dp": "11.45",
        "basket_excludes_noodles": "true",
        "valuation_basis_present": "true",
    },
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
        "combined_share_0dp": "43",
        "july_2020_bulk": "true",
        "june_2022_bulk": "true",
        "september_2024_bulk": "true",
    },
    "PUB-69": {
        "sum_count": "12533",
        "distinct_codes": "610",
        "restaurant_source_rows": "0",
        "restaurant_contract_rows": "0",
        "incompleteness_note": "openings_incomplete",
        "net_formation_built": "false",
    },
    "PUB-70": {
        "metro_2025_12": "7375367",
        "metro_2024_12": "5529167",
        "growth_0dp": "33",
    },
    "PUB-72": {
        "al_daayen_residents": "111282",
        "national_residents": "3219982",
        "al_daayen_0dp": "32",
        "national_0dp": "15",
    },
    "PUB-73": {"places_qa": "26383", "establishments_2020": "71203"},
}

SECTION_10_IDS: tuple[str, ...] = tuple(f"PUB-{number}" for number in range(62, 74))

LOCAL_EXPECTATIONS_DIR = "local_expectations"
LOCAL_RECORD_REFUSED = "local expectations record refused"
_DECIMAL_TEXT = re.compile(r"-?\d+(?:\.\d+)?")
# Field names of each regression row whose expected figures are kept only in
# the uncommitted cache; a record of another shape is refused.
_LOCAL_FIELDS: dict[str, tuple[str, ...]] = {
    "PUB-71": (
        "national_private",
        "national_all",
        "national_1dp",
        "zone_69_0dp",
        "zone_70_0dp",
    ),
}


@dataclass(frozen=True)
class StageResult:
    """Coverage notes, and the first figure id that disagreed, if any.

    ``unrecorded`` names the first figure that was produced while its local
    expectations record is absent; the row stays not measured and the build
    must fail on it.
    """

    missing: tuple[str, ...]
    mismatch: str
    failure: FetchFailure | None = None
    unrecorded: str = ""


def _local_expected(cache: Path, figure_id: str) -> dict[str, str] | None:
    """Return the uncommitted expectations record, or None when absent.

    The record lives at cache/LOCAL_EXPECTATIONS_DIR/<figure_id>.json. A
    record of another shape — a missing or extra field, or a value that is
    not decimal text — is refused by one fixed reason.
    """
    fields = _LOCAL_FIELDS.get(figure_id)
    if fields is None:
        return None
    path = cache / LOCAL_EXPECTATIONS_DIR / f"{figure_id}.json"
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError(f"{figure_id}: {LOCAL_RECORD_REFUSED}") from None
    if (
        not isinstance(record, dict)
        or set(record) != set(fields)
        or any(
            not isinstance(value, str) or _DECIMAL_TEXT.fullmatch(value) is None
            for value in record.values()
        )
    ):
        raise ValueError(f"{figure_id}: {LOCAL_RECORD_REFUSED}")
    return {name: record[name] for name in fields}


def run_stage(
    cache: Path,
    *,
    required: tuple[str, ...] = (),
    evidence: bool = False,
    build_entries: Sequence[Entry] | None = None,
    build_lines: list[str] | None = None,
) -> StageResult:
    """Compare figure files under cache/figures with the section 10 anchors.

    A figure with no committed anchor and no local record is reported like a
    figure that cannot be measured today, never as a pass. A produced figure
    whose local record is absent is named in ``unrecorded`` as well: its row
    stays not measured and the build fails on the missing record.
    """
    if build_entries is not None:
        from eii_custodian.publicdata.series.figures import finish_build

        if build_lines is None:
            raise ValueError("selected fetch lines required")
        return StageResult((), "", finish_build(build_entries, cache, build_lines))
    missing: list[str] = []
    unrecorded = ""
    if set(required) - set(SECTION_10_IDS):
        raise ValueError("unknown required regression")
    for figure_id in SECTION_10_IDS:
        expected = EXPECTED.get(figure_id) or _local_expected(cache, figure_id)
        internal = cache / "series" / "regression" / f"{figure_id}.json"
        use_evidence = evidence or internal.is_file()
        path = internal if use_evidence else cache / "figures" / f"{figure_id}.json"
        if expected is None or not path.is_file():
            missing.append(figure_id)
            if figure_id in required:
                return StageResult(tuple(missing), figure_id)
            if expected is None and path.is_file() and not unrecorded:
                unrecorded = figure_id
            continue
        got = json.loads(path.read_text(encoding="utf-8"))
        if use_evidence:
            from eii_custodian.publicdata.series.figures import validate_figure

            validate_figure(got)
            if figure_id == "PUB-67":
                from eii_custodian.publicdata.series.support import validate_support

                validate_support(got.get("supporting_provenance"))
            got = got["values"]
        if got != expected:
            return StageResult(tuple(missing), figure_id)
    return StageResult(tuple(missing), "", unrecorded=unrecorded)
