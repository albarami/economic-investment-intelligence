"""MTH-126 invented examples, refusal plants and whole-domain properties."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_core.calc.firms_per_tower import CLASS_KEYS, TowerCount, _breaks
from eii_core.calc.layer_classes import ClassInputError, equal_count_classes


@pytest.mark.parametrize(
    "pairs,expected",
    [
        (
            list(zip("abcdefghij", [1, 2, 2, 3, 5, 8, 8, 8, 13, 21], strict=True)),
            [(1, 3, "d"), (5, 8, "h"), (13, 21, "j")],
        ),
        (list(zip("pqrst", [4, 4, 4, 7, 7], strict=True)), [(4, 4, "r"), (7, 7, "t")]),
        ([("u", 9)], [(9, 9, "u")]),
    ],
)
def test_ruled_fixtures(pairs, expected):
    result = equal_count_classes(pairs)
    assert [(b.low, b.high, b.boundary_key) for b in result.breaks] == expected
    assert [b.class_key for b in result.breaks] == list(CLASS_KEYS[: len(expected)])
    assert result == equal_count_classes(list(reversed(pairs)))


@pytest.mark.parametrize(
    "pairs,reason",
    [
        ([], "class_input_empty"),
        ([("a", 1), ("a", 2)], "class_key_duplicate"),
        ([("a", True)], "class_value_type"),
        ([("a", 1.0)], "class_value_type"),
        ([("a", "1")], "class_value_type"),
        ([("a", Decimal("NaN"))], "class_value_nonfinite"),
        ([("a", Decimal("Infinity"))], "class_value_nonfinite"),
        ([("a", Decimal("-Infinity"))], "class_value_nonfinite"),
    ],
)
def test_guard_plants(pairs, reason):
    with pytest.raises(ClassInputError, match=reason):
        equal_count_classes(pairs)


@given(st.lists(st.integers(-100, 100), min_size=1, max_size=80))
def test_partition_ties_permutation_and_existing_method(values):
    pairs = [(f"k{i:03}", value) for i, value in enumerate(values)]
    result = equal_count_classes(pairs)
    assert result == equal_count_classes(list(reversed(pairs)))
    assert result == equal_count_classes([(k, Decimal(v)) for k, v in pairs])
    assert set(result.classes) == {k for k, _ in pairs}
    for key, value in pairs:
        matching = [b for b in result.breaks if b.low <= value <= b.high]
        assert len(matching) == 1
        assert result.classes[key] == matching[0].class_key
    for left, right in zip(result.breaks, result.breaks[1:], strict=False):
        assert left.high < right.low
    old = _breaks([TowerCount(k, v, "", None, "none", ()) for k, v in pairs])
    assert [(b.class_key, b.low, b.high, b.boundary_key) for b in result.breaks] == [
        (b.class_key, b.low, b.high, b.boundary_tower) for b in old
    ]
