"""Complete source contributions for S4-T05; reuse the SYN-20 normaliser unchanged."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .places_fsq.names import NameCheck, check_labels


@dataclass(frozen=True)
class Contribution:
    source_id: str
    names: tuple[str, ...]
    lineage: Mapping[str, object]


def check_inventory(
    labels: Sequence[str],
    contributions: Sequence[Contribution],
    min_edit_distance: int,
) -> NameCheck:
    """Compose all names before any display filter or deduplication."""
    return check_labels(
        labels,
        tuple(name for source in contributions for name in source.names),
        min_edit_distance,
    )
