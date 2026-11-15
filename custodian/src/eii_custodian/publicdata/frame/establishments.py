"""PUB-83 national establishment totals from the reviewed wide activity rows."""

from decimal import Decimal
from typing import Any

from .checks import FrameError
from .mapping import fields

COUNT_YEARS = {"census_2020": "2020", "census_2010_2010": "2010"}
PERCENT_FIELDS = ("percent_census_2020", "percent_census_2010", "percent_change")


def establishment_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise FrameError("est_census: expected list")
    if not payload:
        raise FrameError("est_census: empty_records")
    seen = set()
    for row in payload:
        # JSON decimals are read as Decimal; integral JSON percentages are numbers too.
        expected: dict[str, type] = {
            "economic_activity": str,
            "economic_activity_ar": str,
        }
        expected.update(dict.fromkeys(COUNT_YEARS, int))
        expected.update(
            {
                name: type(row.get(name))
                if isinstance(row, dict)
                and type(row.get(name)) in {int, float, Decimal}
                else Decimal
                for name in PERCENT_FIELDS
            }
        )
        fields(row, expected, "est_census")
        if any(row[column] < 0 for column in COUNT_YEARS):
            raise FrameError("est_census: negative_count")
        if row["economic_activity"] in seen:
            raise FrameError("est_census: duplicate_activity")
        seen.add(row["economic_activity"])
    return [
        {
            "period": year,
            "indicator": "establishments",
            "unit": "establishments",
            "value": sum(row[column] for row in payload),
        }
        for column, year in COUNT_YEARS.items()
    ]
