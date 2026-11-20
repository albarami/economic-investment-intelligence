"""Threshold/membership plants against the committed fixture registration."""

import json
from pathlib import Path

import pytest
from evals.forecast_spike.fixture import fixture_specs


def document() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parents[2]
        / "evals/forecast_spike/preregistration.json"
    )
    value: dict[str, object] = json.loads(path.read_text())
    return value


@pytest.mark.parametrize(
    "key,value",
    [
        ("minimum", 0),
        ("minimum", 11),
        ("seed", True),
        ("levels", {"year": [3, 4], "quarter": [4, 5], "month": [9, 10]}),
        ("candidates", ["seasonal_naive"]),
        ("fixture_only", False),
        ("adapter_kind", "real-models"),
        ("unknown", "unregistered"),
        ("selection", "retrospective_winner"),
        ("zero_scale", "pool_mae_with_mase"),
    ],
)
def test_registration_plants_cannot_be_silently_ignored(
    key: str, value: object
) -> None:
    changed = document()
    changed[key] = value
    with pytest.raises(ValueError):
        fixture_specs(changed)


def test_committed_registration_is_valid() -> None:
    rows = fixture_specs(document())
    assert len(rows) == 4
    assert {row.family.frequency for row in rows} == {"year", "quarter", "month"}
