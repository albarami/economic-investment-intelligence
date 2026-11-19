"""Inventory build boundary called by S4-T05; collisions refuse the build."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..fetch.registry import Entry
from ..name_inventory import Contribution, check_inventory
from ..places_fsq.names import NameCheck
from .errors import RegisterError
from .names import contribution


def build_inventory(
    cache: Path,
    entry: Entry,
    labels: Sequence[str],
    contributions: Sequence[Contribution],
    min_edit_distance: int,
) -> NameCheck:
    result = check_inventory(
        labels, (*contributions, contribution(cache, entry)), min_edit_distance
    )
    if not result.ok:
        raise RegisterError("name_collision")
    return result
