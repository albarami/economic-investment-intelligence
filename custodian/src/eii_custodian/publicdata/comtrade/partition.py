"""Deterministic disjoint partitions. The selection is a closed registry value."""

from __future__ import annotations

from dataclasses import dataclass

from eii_custodian.publicdata.comtrade.policy import Descriptor, Policy

ROLE_REPORTER = "reporter"
ROLE_MIRROR = "mirror"


@dataclass(frozen=True)
class Partition:
    """One leaf or internal cell of the split tree."""

    series_role: str
    partner_code: str
    frequency: str
    period: str
    flow_code: str
    chapter: str
    subdivision: tuple[tuple[str, str], ...] = ()
    parent_key: str = ""

    def key(self) -> str:
        """Return the canonical key. Order is fixed, so the same cell hashes once."""
        extra = ",".join(f"{name}={value}" for name, value in self.subdivision)
        return (
            f"role={self.series_role}|partner={self.partner_code}|"
            f"frequency={self.frequency}|period={self.period}|"
            f"flow={self.flow_code}|chapter={self.chapter}|sub={extra}"
        )

    def descriptor(self, policy: Policy, api_class: str) -> Descriptor:
        """Build the transport descriptor. Reporter and mirror directions stay distinct."""
        if self.series_role == ROLE_MIRROR:
            reporter = self.partner_code
            partner = policy.reporter_key
        else:
            reporter = policy.reporter_key
            partner = self.partner_code
        return Descriptor(
            api_class=api_class,
            endpoint_family="data",
            series_role=self.series_role,
            reporter_code=reporter,
            partner_code=partner,
            frequency=self.frequency,
            period=self.period,
            flow_code=self.flow_code,
            chapter=self.chapter,
            classification_revision=policy.classification_revision,
            subdivision=self.subdivision,
        )


def closed_partitions(policy: Policy) -> tuple[Partition, ...]:
    """Return every cell the closed subdivision tree can name, at every depth."""
    found: dict[str, Partition] = {}
    queue = list(initial_partitions(policy))
    while queue:
        partition = queue.pop(0)
        if partition.key() in found:
            continue
        found[partition.key()] = partition
        field = next_subdivision(policy, partition)
        if field is None:
            continue
        queue.extend(subdivide(policy, partition, field))
    return tuple(found[key] for key in sorted(found))


def covered_leaves(
    policy: Policy, partition: Partition, present: set[str]
) -> tuple[str, ...] | None:
    """Return the disjoint leaves that cover one cell, or None when the cover is partial."""
    field = next_subdivision(policy, partition)
    children = subdivide(policy, partition, field) if field is not None else ()
    if partition.key() in present:
        if _descendant_present(policy, children, present):
            return None
        return (partition.key(),)
    if not children:
        return None
    leaves: list[str] = []
    for child in children:
        found = covered_leaves(policy, child, present)
        if found is None:
            return None
        leaves.extend(found)
    return tuple(leaves)


def _descendant_present(
    policy: Policy, children: tuple[Partition, ...], present: set[str]
) -> bool:
    for child in children:
        if child.key() in present:
            return True
        field = next_subdivision(policy, child)
        if field is None:
            continue
        if _descendant_present(policy, subdivide(policy, child, field), present):
            return True
    return False


def initial_partitions(policy: Policy) -> tuple[Partition, ...]:
    """Expand the closed selection. Nothing is chosen from a fetched ranking."""
    found: list[Partition] = []
    for partner in policy.mirror_partner_keys:
        for frequency in policy.frequencies:
            for period in _periods_for(policy, frequency):
                for flow in policy.flows:
                    for chapter in policy.chapters:
                        for role in (ROLE_REPORTER, ROLE_MIRROR):
                            found.append(
                                Partition(
                                    role, partner, frequency, period, flow, chapter
                                )
                            )
    return tuple(sorted(found, key=lambda item: item.key()))


def next_subdivision(policy: Policy, partition: Partition) -> str | None:
    """Return the next unused subdivision field, or None when the leaf is indivisible."""
    used = {name for name, _value in partition.subdivision}
    for name in policy.subdivision_fields:
        if name not in used:
            return name
    return None


def subdivide(
    policy: Policy, partition: Partition, field: str
) -> tuple[Partition, ...]:
    """Split one cell into disjoint values of one field. The parent is not a leaf."""
    values = dict(policy.subdivision_values).get(field)
    if values is None:
        return ()
    parent = partition.key()
    children: list[Partition] = []
    for value in values:
        children.append(
            Partition(
                series_role=partition.series_role,
                partner_code=partition.partner_code,
                frequency=partition.frequency,
                period=partition.period,
                flow_code=partition.flow_code,
                chapter=partition.chapter,
                subdivision=(*partition.subdivision, (field, value)),
                parent_key=parent,
            )
        )
    return tuple(children)


def cell_prefix(key: str) -> str:
    """Return the year/flow/chapter identity of a key, without subdivision."""
    return key.split("|sub=", 1)[0]


def missing_cells(
    initial: tuple[Partition, ...],
    pending: tuple[str, ...],
    completed: tuple[str, ...],
) -> tuple[str, ...]:
    """Return requested cells that are not fully accepted. Gap size is this length."""
    pending_set = set(pending)
    completed_set = set(completed)
    missing: list[str] = []
    for cell in initial:
        prefix = cell_prefix(cell.key())
        if cell.key() in completed_set:
            continue
        done = [
            key
            for key in completed_set
            if cell_prefix(key) == prefix and key != cell.key()
        ]
        still = [key for key in pending_set if cell_prefix(key) == prefix]
        if done and not still:
            continue
        missing.append(cell.key())
    return tuple(missing)


def gap_size(requested: int, present: int) -> int:
    """Return the number of requested cells that are absent. Present cannot exceed requested."""
    if present < 0 or requested < 0 or present > requested:
        raise ValueError("gap")
    return requested - present


def _periods_for(policy: Policy, frequency: str) -> tuple[str, ...]:
    if frequency == "annual":
        return tuple(item for item in policy.periods if len(item) == 4)
    return tuple(item for item in policy.periods if len(item) == 7)
