"""Threshold/membership plants against the committed fixture registration."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
        ("adapter_kind", "invented_prefix_stubs"),
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


def test_statsforecast_reference_section_is_registered_and_validated() -> None:
    from check_reference_notes import check_file
    from reference_notes_parse import check_address, load_pins
    from reference_notes_tables import DOCS, LIBRARIES

    root = Path(__file__).resolve().parents[2]
    library = next(
        (lib for lib in LIBRARIES[DOCS] if lib.name == "StatsForecast 2.1"), None
    )
    assert library is not None
    assert library.rows == ("statsforecast",)
    assert library.fields == ("exact pin and written retreat pin",)
    assert (
        check_address(
            "https://nixtlaverse.nixtla.io/statsforecast/src/core/models.html"
        )
        is None
    )
    assert check_address("https://nixtlaverse.nixtla.io/unreviewed/") is not None
    pins, problem = load_pins(root)
    assert not problem
    assert pins is not None and "statsforecast" in pins
    assert check_file(root, DOCS, pins).lines() == []
