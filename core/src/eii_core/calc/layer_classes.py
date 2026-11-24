"""MTH-126 equal-count layer classes. Exact values; no IO or rounding."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from eii_core.calc.firms_per_tower import CLASS_KEYS

CLASS_COUNT = 5


class ClassInputError(ValueError):
    """A closed input refusal, never a value-bearing message."""


@dataclass(frozen=True)
class ClassBreak:
    class_key: str
    low: Decimal | int
    high: Decimal | int
    boundary_key: str


@dataclass(frozen=True)
class LayerClasses:
    breaks: tuple[ClassBreak, ...]
    classes: Mapping[str, str]


def equal_count_classes(pairs: Sequence[tuple[str, Decimal | int]]) -> LayerClasses:
    """Sort value/key, slice five ways, merge touching ties and drop empties."""
    if not pairs:
        raise ClassInputError("class_input_empty")
    seen: set[str] = set()
    for key, value in pairs:
        if key in seen:
            raise ClassInputError("class_key_duplicate")
        seen.add(key)
        if type(value) not in (Decimal, int):
            raise ClassInputError("class_value_type")
        if isinstance(value, Decimal) and not value.is_finite():
            raise ClassInputError("class_value_nonfinite")
    ordered = sorted(pairs, key=lambda item: (item[1], item[0]))
    count = len(ordered)
    merged: list[list[tuple[str, Decimal | int]]] = []
    for index in range(CLASS_COUNT):
        group = ordered[
            index * count // CLASS_COUNT : (index + 1) * count // CLASS_COUNT
        ]
        if not group:
            continue
        if merged and merged[-1][-1][1] == group[0][1]:
            merged[-1].extend(group)
        else:
            merged.append(list(group))
    bands = []
    classes: dict[str, str] = {}
    for index, group in enumerate(merged):
        class_key = CLASS_KEYS[index]
        bands.append(ClassBreak(class_key, group[0][1], group[-1][1], group[-1][0]))
        for key, _value in group:
            classes[key] = class_key
    return LayerClasses(tuple(bands), classes)
