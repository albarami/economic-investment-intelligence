"""Immutable classification associations. No I/O, quantities or allocation.

Only the custodian validator (and, later, a verified release reader) supplies
Crosswalk objects. This module selects code identities and preserves evidence;
it does not establish a new fact about a worker or an industry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

Status = Literal["mapped", "unmapped", "ambiguous", "unreviewed"]
Reason = Literal[
    "reviewer_approved",
    "reviewer_rejected_no_target",
    "reviewer_undecided",
    "multi_link_no_published_weight",
    "awaiting_human_review",
    "outside_review_scope",
]
SelectionReason = Literal[
    "all_bound_children_agree",
    "bound_children_not_unanimous",
    "missing_bound_tariff_family",
    "no_single_manufacturing_industry",
]
LinkKind = Literal["product_to_activity", "activity_to_occupation"]
System = Literal[
    "customs_tariff", "manufacturing_industry", "isic_class", "occupation_group"
]
Level = Literal["tariff8", "tariff12", "industry", "class", "major_group"]
Basis = Literal["official", "editorial_reviewed"]
Mode = Literal["production", "invented_fixture"]
METHOD_VERSION = "classification_resolver.v1"


@dataclass(frozen=True, slots=True, order=True)
class Endpoint:
    system: System
    version: str
    level: Level
    code: str


def endpoint_from_parts(
    *, system: str, version: str, level: str, code: str
) -> Endpoint:
    """Construct a typed query identity; it grants no mapping admission."""
    if system not in {
        "customs_tariff",
        "manufacturing_industry",
        "isic_class",
        "occupation_group",
    }:
        raise ValueError("unknown classification system")
    if level not in {"tariff8", "tariff12", "industry", "class", "major_group"}:
        raise ValueError("unknown classification level")
    if not version or not code:
        raise ValueError("classification identity is empty")
    return Endpoint(cast(System, system), version, cast(Level, level), code)


@dataclass(frozen=True, slots=True)
class Snapshot:
    registry_key: str
    snapshot_sha256: str
    publisher: str
    title: str
    licence: str
    retrieved_on: str
    url: str


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    snapshot: Snapshot
    locator: str


@dataclass(frozen=True, slots=True)
class PublishedWeight:
    """Source text retained unchanged; never a composed or applied weight."""

    value: str
    scope: str
    denominator: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class Link:
    link_id: str
    target: Endpoint
    basis_kind: Basis
    basis: Evidence
    evidence: tuple[Evidence, ...]
    rationale: str | None
    configuration_sha256: str | None
    reviewed_by_role: str
    reviewed_on: str
    weight: PublishedWeight | None


@dataclass(frozen=True, slots=True)
class GroupDecision:
    link_kind: LinkKind
    source: Endpoint
    status: Status
    reason: Reason | SelectionReason
    reviewed_by_role: str
    reviewed_on: str
    links: tuple[Link, ...]


@dataclass(frozen=True, slots=True)
class TariffFamily:
    """Every child in the caller's verified, selected snapshot, never a prefix guess."""

    parent: Endpoint
    children: tuple[Endpoint, ...]
    snapshot: Snapshot


@dataclass(frozen=True, slots=True)
class Crosswalk:
    schema_version: str
    mapping_revision: str
    mode: Mode
    review_sha256: str
    schema_sha256: str
    context_sha256: str
    groups: tuple[GroupDecision, ...]
    tariff_families: tuple[TariffFamily, ...]


@dataclass(frozen=True, slots=True)
class ClassificationPath:
    product_link: Link
    occupation_link: Link


@dataclass(frozen=True, slots=True)
class OccupationResolution:
    status: Status
    reason: Reason | SelectionReason
    source: Endpoint
    first_hop: GroupDecision
    second_hops: tuple[GroupDecision, ...]
    paths: tuple[ClassificationPath, ...]
    occupations: tuple[Endpoint, ...]
    method_version: str
    mapping_revision: str
    review_sha256: str
    context_sha256: str


@dataclass(frozen=True, slots=True)
class C13Selection:
    """Typed input shape for S7-T11. There are no amounts or coverage counts."""

    source: Endpoint
    status: Status
    reason: Reason | SelectionReason
    bucket: Literal["mapped", "not_mapped"]
    industry: Endpoint | None
    decisions: tuple[GroupDecision, ...]
    family: TariffFamily | None
    method_version: str
    mapping_revision: str
    review_sha256: str
    context_sha256: str


def _decision(crosswalk: Crosswalk, kind: LinkKind, source: Endpoint) -> GroupDecision:
    for group in crosswalk.groups:
        if group.link_kind == kind and group.source == source:
            return group
    return GroupDecision(kind, source, "unreviewed", "outside_review_scope", "", "", ())


def _worst(
    decisions: tuple[GroupDecision, ...],
) -> tuple[Status, Reason | SelectionReason]:
    for status in ("unreviewed", "unmapped", "ambiguous", "mapped"):
        for decision in decisions:
            if decision.status == status:
                return decision.status, decision.reason
    raise ValueError("no classification decision")


def _first_hop(
    crosswalk: Crosswalk, source: Endpoint
) -> tuple[GroupDecision, tuple[GroupDecision, ...], TariffFamily | None]:
    """Derive a parent only from its complete bound family, for both consumers.

    The derived decision carries the children's original links as evidence.
    Blank sign-off fields distinguish this summary from a signed file group.
    A direct parent decision never substitutes for the inventory or a child.
    """
    if source.level != "tariff8":
        direct = _decision(crosswalk, "product_to_activity", source)
        return direct, (direct,), None
    family = next(
        (item for item in crosswalk.tariff_families if item.parent == source), None
    )
    if family is None:
        return (
            GroupDecision(
                "product_to_activity",
                source,
                "unreviewed",
                "missing_bound_tariff_family",
                "",
                "",
                (),
            ),
            (),
            None,
        )
    decisions = tuple(
        _decision(crosswalk, "product_to_activity", child) for child in family.children
    )
    status, reason = _worst(decisions)
    links = tuple(edge for decision in decisions for edge in decision.links)
    if status == "mapped":
        targets = {edge.target for edge in links}
        if all(decision.links for decision in decisions) and len(targets) == 1:
            reason = "all_bound_children_agree"
        else:
            status, reason = "ambiguous", "bound_children_not_unanimous"
    first = GroupDecision("product_to_activity", source, status, reason, "", "", links)
    return first, decisions, family


def resolve_occupations(crosswalk: Crosswalk, source: Endpoint) -> OccupationResolution:
    """Trace both reviewed hops by exact identity, preserving every route.

    All branches participate in status. A missing branch cannot be discarded
    to promote the remaining route to mapped. Non-mapped results expose no
    occupation as an admitted association, even when candidate paths exist.
    """
    if not isinstance(crosswalk, Crosswalk) or source.system != "customs_tariff":
        raise ValueError(
            "resolver requires a validated crosswalk and a tariff identity"
        )
    first, _, _ = _first_hop(crosswalk, source)
    seconds = tuple(
        _decision(crosswalk, "activity_to_occupation", edge.target)
        for edge in first.links
    )
    decisions = (first, *seconds)
    status, reason = _worst(decisions)
    paths = (
        tuple(
            ClassificationPath(product_edge, occupation_edge)
            for product_edge, second in zip(first.links, seconds, strict=True)
            for occupation_edge in second.links
        )
        if status == "mapped"
        else ()
    )
    occupations = (
        tuple(sorted({path.occupation_link.target for path in paths}))
        if status == "mapped"
        else ()
    )
    return OccupationResolution(
        status,
        reason,
        source,
        first,
        seconds,
        paths,
        occupations,
        METHOD_VERSION,
        crosswalk.mapping_revision,
        crosswalk.review_sha256,
        crosswalk.context_sha256,
    )


def _industry(decision: GroupDecision) -> Endpoint | None:
    if decision.status != "mapped" or any(
        edge.weight is not None for edge in decision.links
    ):
        return None
    targets = {edge.target for edge in decision.links}
    if len(targets) != 1:
        return None
    target = next(iter(targets))
    return target if target.system == "manufacturing_industry" else None


def c13_selection(crosswalk: Crosswalk, source: Endpoint) -> C13Selection:
    """C13 admission only. All non-mapped outcomes use its single gap bucket.

    For tariff8, the complete explicitly bound tariff12 family is mandatory.
    No allocation rule is inferred from source weights or code similarity.
    """
    if not isinstance(crosswalk, Crosswalk) or source.system != "customs_tariff":
        raise ValueError("C13 requires a validated crosswalk and a tariff identity")
    first, decisions, family = _first_hop(crosswalk, source)
    industry = _industry(first)
    status, reason = first.status, first.reason
    if status == "mapped" and industry is None:
        status, reason = "ambiguous", "no_single_manufacturing_industry"
    return C13Selection(
        source,
        status,
        reason,
        "mapped" if industry else "not_mapped",
        industry,
        decisions,
        family,
        METHOD_VERSION,
        crosswalk.mapping_revision,
        crosswalk.review_sha256,
        crosswalk.context_sha256,
    )
