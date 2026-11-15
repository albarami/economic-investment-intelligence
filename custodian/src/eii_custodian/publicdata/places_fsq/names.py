"""Name-collision check for fictional labels against this source's names.

The check follows SYN-20: case-folding, Arabic letter variants, removal of the
token SYN, equality, whole-word containment and edit distance. The distance
threshold is an argument because the pack has not fixed its number.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError

_ARABIC = str.maketrans(
    {
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0622": "\u0627",
        "\u0671": "\u0627",
        "\u0649": "\u064a",
        "\u0629": "\u0647",
        "\u0624": "\u0648",
        "\u0626": "\u064a",
    }
)
_TOKEN = "syn"


@dataclass(frozen=True)
class NameCheck:
    """Labels that collide, and whether the check passed."""

    ok: bool
    collisions: tuple[str, ...]


def normalise_collision_name(value: str) -> str:
    """Case-fold, unify Arabic letter variants and drop the whole word SYN."""
    folded = value.casefold().translate(_ARABIC)
    words = [word for word in folded.split() if word != _TOKEN]
    return " ".join(words)


def edit_distance(left: str, right: str) -> int:
    """Return the number of single-character edits between two strings."""
    if left == right:
        return 0
    if left == "":
        return len(right)
    if right == "":
        return len(left)
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i]
        for j, b in enumerate(right, start=1):
            cost = 0 if a == b else 1
            current.append(
                min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost)
            )
        previous = current
    return previous[-1]


def check_labels(
    labels: Sequence[str],
    real_names: Sequence[str],
    min_edit_distance: int,
) -> NameCheck:
    """Fail a fictional label that collides with any real name, duplicates included."""
    if isinstance(min_edit_distance, bool) or not isinstance(min_edit_distance, int):
        raise PlacesFsqError("edit_distance")
    if min_edit_distance < 1:
        raise PlacesFsqError("edit_distance")
    real = tuple(normalise_collision_name(name) for name in real_names if name.strip())
    collisions = tuple(
        label
        for label in labels
        if _collides(normalise_collision_name(label), real, min_edit_distance)
    )
    return NameCheck(ok=not collisions, collisions=collisions)


def _collides(label: str, real_names: Sequence[str], limit: int) -> bool:
    if label == "":
        return False
    label_words = tuple(label.split())
    for name in real_names:
        if name == "":
            continue
        if label == name or _contains_words(label_words, tuple(name.split())):
            return True
        if edit_distance(label, name) < limit:
            return True
    return False


def _contains_words(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if not left or not right:
        return False
    return _window(left, right) or _window(right, left)


def _window(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    span = len(needle)
    if span > len(haystack):
        return False
    return any(
        haystack[index : index + span] == needle
        for index in range(len(haystack) - span + 1)
    )
