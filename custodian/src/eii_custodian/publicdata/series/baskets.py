"""PUB-41 editorial review guards and MTH-30 historical parent selection."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

ACTIVITIES = frozenset({"5610", "5630", "5510"})
REVIEW_FIELDS = frozenset(
    {
        "name",
        "lines",
        "inclusion_reason",
        "excluded_lines",
        "supplier_isic",
        "reviewer_role",
        "review_date",
        "source_sha256",
    }
)


def tariff_digits(code: str) -> str:
    """Committed codes are dotted; basket lines are eight digits or finer."""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", code):
        raise ValueError("tariff code must be dotted")
    digits = code.replace(".", "")
    if len(digits) < 8:
        raise ValueError("coarse tariff line")
    return digits


def reviewed_inputs(
    document: dict[str, object], activity: str
) -> list[dict[str, object]]:
    """Refuse incomplete editorial reviews; empty baskets stay withheld."""
    rows = document.get("activities")
    if not isinstance(rows, list):
        raise ValueError("missing activities")
    if len(rows) != 3 or {row["activity"] for row in rows} != ACTIVITIES:
        raise ValueError("wrong playbook activities")
    selected: list[dict[str, object]] = []
    for row in rows:
        inputs = row["inputs"]
        if len(inputs) > 8:
            raise ValueError("basket exceeds eight inputs")
        for item in inputs:
            _validate_review(item)
        if row["activity"] == activity:
            selected = inputs
    return selected


def _validate_review(item: dict[str, object]) -> None:
    if set(item) != REVIEW_FIELDS:
        raise ValueError("incomplete review fields")
    for field in REVIEW_FIELDS - {"lines", "excluded_lines"}:
        if not isinstance(item[field], str) or not str(item[field]).strip():
            raise ValueError("missing review metadata")
    date.fromisoformat(str(item["review_date"]))
    if re.fullmatch(r"[a-f0-9]{64}", str(item["source_sha256"])) is None:
        raise ValueError("review source hash missing")
    lines, excluded = item["lines"], item["excluded_lines"]
    if not isinstance(lines, list) or not lines or not isinstance(excluded, list):
        raise ValueError("review lines missing")
    for line in lines:
        if not line.get("description_en") or not line.get("description_ar"):
            raise ValueError("review needs bilingual descriptions")
        tariff_digits(line["code"])
    for line in excluded:
        if not line.get("reason"):
            raise ValueError("review exclusion reason missing")
        tariff_digits(line["code"])


def validate_source_review(
    document: dict[str, object], rows: Sequence[dict[str, object]]
) -> None:
    """L-222: source membership, paired descriptions and complete used parents."""
    from eii_custodian.publicdata.series.parse import customs_code

    descriptions: dict[str, set[tuple[str, str]]] = {}
    parents: dict[str, set[str]] = {}
    for row in rows:
        code = customs_code("cus_imp_2025", row["harmonized_system_code"])
        if code is None:
            continue
        descriptions.setdefault(code, set()).add(
            (str(row["details"]).strip(), str(row["ltfsyl"]).strip())
        )
        parents.setdefault(code[:8], set()).add(code)
    for activity in ("5610", "5630", "5510"):
        items = reviewed_inputs(document, activity)
        seen: set[str] = set()
        for item in items:
            included = item["lines"]
            excluded = item["excluded_lines"]
            assert isinstance(included, list) and isinstance(excluded, list)
            listed: set[str] = set()
            used: set[str] = set()
            for line in included + excluded:
                code = tariff_digits(line["code"])
                context = f"{activity} {item['name']} {line['code']}"
                if code in seen:
                    raise ValueError("basket_line_duplicate: " + context)
                seen.add(code)
                listed.add(code)
                if code not in descriptions:
                    raise ValueError("basket_line_source_mismatch: " + context)
            for line in included:
                code = tariff_digits(line["code"])
                pair = (line["description_en"].strip(), line["description_ar"].strip())
                if pair not in descriptions[code]:
                    raise ValueError(
                        f"basket_line_source_mismatch: {activity} {item['name']} {line['code']}"
                    )
                used.add(code[:8])
            for parent in sorted(used):
                for code in sorted(parents[parent] - listed):
                    raise ValueError(
                        f"basket_line_unreviewed: {activity} {item['name']} {code}"
                    )


def historical_selection(
    rows: Sequence[dict[str, str]], included: Sequence[str], excluded: Sequence[str]
) -> list[dict[str, str]]:
    """Copy each selected parent row once, explicitly marking excluded children."""
    parents = {tariff_digits(code)[:8] for code in included}
    contaminated = {tariff_digits(code)[:8] for code in excluded}
    result = []
    for row in rows:
        code = tariff_digits(row["tariff_code"])
        if code in parents:
            result.append(
                {
                    **row,
                    "rollup_note": "includes excluded lines"
                    if code in contaminated
                    else "",
                }
            )
    return result
