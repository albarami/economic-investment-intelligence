"""Deterministic comparison at stored precision; value-free results (TST-50)."""

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from eii_core.calc.public_series import rounded
from eii_custodian.publicdata.draw import Figure, validate_figure


def compare(
    stored: Sequence[Figure], reviewer_values: Mapping[str, str]
) -> list[dict[str, str]]:
    """Counts/money match exactly; ratios match at the stored decimal precision."""
    ids = [f.figure_id for f in stored]
    if len(set(ids)) != len(ids) or set(ids) != set(reviewer_values):
        raise ValueError("reviewer_ids_mismatch")
    results = []
    for figure in stored:
        validate_figure(figure)
        value = Decimal(figure.value)
        result = "no match"
        try:
            observed = Decimal(reviewer_values[figure.figure_id])
            if observed.is_finite():
                if figure.kind == "ratio":
                    observed = Decimal(
                        rounded(observed, -int(value.as_tuple().exponent))
                    )
                if observed == value:
                    result = "match"
        except (InvalidOperation, ValueError):
            pass
        results.append(
            {"figure_id": figure.figure_id, "url": figure.url, "result": result}
        )
    return results


def validate_record(rows: Sequence[Mapping[str, object]], kind: str) -> None:
    """Closed schemas prevent a value-bearing draw, verdict or stdout payload."""
    schemas = {
        "draw": {"figure_id", "source_id", "url", "filter"},
        "verdict": {"figure_id", "url", "result"},
    }
    if kind not in schemas:
        raise ValueError("review_record_kind_invalid")
    for row in rows:
        if set(row) != schemas[kind] or not all(
            isinstance(v, str) and v.strip() for v in row.values()
        ):
            raise ValueError("committed_source_value")
        if kind == "verdict" and row["result"] not in {"match", "no match"}:
            raise ValueError("review_result_invalid")
