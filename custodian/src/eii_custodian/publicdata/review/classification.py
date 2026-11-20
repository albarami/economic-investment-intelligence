"""Closed, offline review admission beside the activity spine.

The context is supplied by the custodian's verified snapshot/spine readers:
complete endpoint meanings, selected receipt metadata and complete tariff
families. This module never fetches or reads a cache. Binding a review cannot
turn an unverified caller context into verified source evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from eii_core.classification import (
    Basis,
    Crosswalk,
    Endpoint,
    Evidence,
    GroupDecision,
    Link,
    LinkKind,
    Mode,
    PublishedWeight,
    Snapshot,
    Status,
    TariffFamily,
    endpoint_from_parts,
)
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import CODE_SYSTEM_VERSION, binding_path

_REVIEW = Path(__file__).resolve().parents[4] / "publicdata" / "review"
_STEM = "product_activity_occupation.v1"
_SCHEMA = _REVIEW / (_STEM + ".schema.json")
_BARE_RUN = re.compile(r"(?<![0-9A-Za-z])(?:[0-9]{8}|[0-9]{11})(?![0-9A-Za-z])")
_ROLE = re.compile(r"[a-z][a-z0-9_]*")


class CrosswalkError(ValueError):
    """Fixed diagnostics only: source text and identifiers never enter errors."""


def _json(body: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        found: dict[str, Any] = {}
        for key, value in pairs:
            if key in found:
                raise CrosswalkError("duplicate JSON property")
            found[key] = value
        return found

    try:
        result = json.loads(body, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as error:
        raise CrosswalkError("unreadable crosswalk JSON") from error
    if not isinstance(result, dict):
        raise CrosswalkError("crosswalk JSON must be an object")
    return result


def _shape(value: Any, rule: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Validate the closed schema's deliberately small JSON Schema vocabulary.

    Every keyword used below is exercised by a refusal plant. Semantic code
    then checks endpoint combinations, signs, evidence identity and status.
    """
    if "$ref" in rule:
        _shape(value, schema["$defs"][rule["$ref"].removeprefix("#/$defs/")], schema)
        return
    if "anyOf" in rule:
        for option in rule["anyOf"]:
            try:
                _shape(value, option, schema)
            except CrosswalkError:
                pass
            else:
                return
        raise CrosswalkError("value is not an allowed nullable shape")
    if "const" in rule and value != rule["const"]:
        raise CrosswalkError("schema literal differs")
    if "enum" in rule and value not in rule["enum"]:
        raise CrosswalkError("value is outside the closed enumeration")
    kind = rule.get("type")
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(rule["required"]):
            raise CrosswalkError("object fields differ from the closed schema")
        for key, child in rule["properties"].items():
            _shape(value[key], child, schema)
    elif kind == "array":
        if not isinstance(value, list) or len(value) < rule.get("minItems", 0):
            raise CrosswalkError("invalid crosswalk array")
        for item in value:
            _shape(item, rule["items"], schema)
    elif kind == "string":
        if not isinstance(value, str):
            raise CrosswalkError("crosswalk value is not text")
        if len(value.strip()) < rule.get("minLength", 0):
            raise CrosswalkError("required crosswalk text is empty")
        if "pattern" in rule and re.fullmatch(rule["pattern"], value) is None:
            raise CrosswalkError("crosswalk text pattern differs")
    elif kind == "null" and value is not None:
        raise CrosswalkError("crosswalk value must be null")


def _safe_text(value: Any) -> None:
    if isinstance(value, str) and _BARE_RUN.search(value):
        raise CrosswalkError("prohibited bare digit run")
    if isinstance(value, dict):
        for key, item in value.items():
            _safe_text(key)
            _safe_text(item)
    if isinstance(value, list):
        for item in value:
            _safe_text(item)


def _calendar(value: str) -> None:
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise CrosswalkError("review or retrieval date is not ISO")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise CrosswalkError(
            "review or retrieval date is not a calendar date"
        ) from error


def _signoff(row: Mapping[str, Any]) -> None:
    if _ROLE.fullmatch(row["reviewed_by_role"]) is None:
        raise CrosswalkError("decision has no reviewer role key")
    _calendar(row["reviewed_on"])


def _snapshots(
    context: Mapping[str, Any], *, invented: bool
) -> dict[tuple[str, str], Snapshot]:
    result: dict[tuple[str, str], Snapshot] = {}
    registry = (
        {entry.key: entry for entry in load_registry()}
        if not invented and context["snapshots"]
        else {}
    )
    for row in context["snapshots"]:
        _calendar(row["retrieved_on"])
        try:
            url = urlsplit(row["url"])
        except ValueError as error:
            raise CrosswalkError("source URL is malformed") from error
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise CrosswalkError("source URL is not a public uncredentialed address")
        if not invented:
            entry = registry.get(row["registry_key"])
            if entry is None or (entry.publisher, entry.title_en, entry.licence_id) != (
                row["publisher"],
                row["title"],
                row["licence"],
            ):
                raise CrosswalkError(
                    "source metadata differs from the existing registry"
                )
        snapshot = Snapshot(**row)
        key = (snapshot.registry_key, snapshot.snapshot_sha256)
        if key in result:
            raise CrosswalkError("duplicate snapshot identity")
        result[key] = snapshot
    return result


def _endpoint(
    row: Mapping[str, Any],
    snapshots: Mapping[tuple[str, str], Snapshot],
    *,
    invented: bool,
) -> Endpoint:
    endpoint = endpoint_from_parts(**row)
    if endpoint.system == "customs_tariff":
        if endpoint.level not in {"tariff8", "tariff12"}:
            raise CrosswalkError("tariff endpoint has an incompatible level")
        code = endpoint.code
        if invented:
            if not code.startswith("SYN-TARIFF-"):
                raise CrosswalkError("fixture tariff code is not visibly synthetic")
            code = code.removeprefix("SYN-TARIFF-")
        pattern = (
            r"[0-9]{4}\.[0-9]{4}"
            if endpoint.level == "tariff8"
            else r"[0-9]{4}\.[0-9]{4}\.[0-9]{4}"
        )
        if re.fullmatch(pattern, code) is None:
            raise CrosswalkError("tariff code is not canonical dotted source grain")
        key = "cus_imp_2019" if endpoint.level == "tariff8" else "cus_imp_2025"
        if not any(
            endpoint.version == key + ":" + digest
            for source, digest in snapshots
            if source == key
        ):
            raise CrosswalkError("tariff version is not the reviewed registry snapshot")
    elif endpoint.system == "manufacturing_industry":
        if endpoint.level != "industry" or not re.fullmatch(
            r"mfg_industry/[a-z][a-z0-9-]*", endpoint.code
        ):
            raise CrosswalkError("manufacturing endpoint is not its source industry")
        if invented and not endpoint.code.startswith("mfg_industry/syn-"):
            raise CrosswalkError("fixture industry is not visibly synthetic")
        if not any(
            endpoint.version == source + ":" + digest
            for source, digest in snapshots
            if source == endpoint.code
        ):
            raise CrosswalkError(
                "industry version is not the reviewed registry snapshot"
            )
    elif endpoint.system == "isic_class":
        code = endpoint.code
        if invented:
            if not code.startswith("SYN-ISIC-"):
                raise CrosswalkError("fixture ISIC code is not visibly synthetic")
            code = code.removeprefix("SYN-ISIC-")
        if (
            endpoint.level != "class"
            or endpoint.version != CODE_SYSTEM_VERSION
            or not re.fullmatch(r"[0-9]{4}", code)
        ):
            raise CrosswalkError("ISIC endpoint differs from the pinned spine class")
    elif (
        endpoint.level != "major_group"
        or endpoint.version != "occupation_group.v1"
        or endpoint.code not in tuple("0123456789")
    ):
        raise CrosswalkError("occupation endpoint is not a released major group")
    return endpoint


def _evidence(
    document: Mapping[str, Any], snapshots: Mapping[tuple[str, str], Snapshot]
) -> dict[str, Evidence]:
    result: dict[str, Evidence] = {}
    for row in document["evidence"]:
        snapshot = snapshots.get((row["registry_key"], row["snapshot_sha256"]))
        if snapshot is None or row["evidence_id"] in result:
            raise CrosswalkError("missing or duplicate evidence snapshot identity")
        result[row["evidence_id"]] = Evidence(
            row["evidence_id"], snapshot, row["locator"]
        )
    return result


def _link(
    row: Mapping[str, Any],
    evidence: Mapping[str, Evidence],
    target: Endpoint,
    *,
    invented: bool,
) -> Link:
    _signoff(row)
    refs = row["source_refs"]
    if (
        len(set(refs)) != len(refs)
        or row["basis_ref"] not in refs
        or not all(ref in evidence for ref in refs)
    ):
        raise CrosswalkError("link basis or source chain is unresolved")
    official = row["basis_kind"] == "official"
    if official:
        if not invented:
            raise CrosswalkError(
                "official correspondences require a separate source decision"
            )
        if row["rationale"] is not None or row["configuration_sha256"] is not None:
            raise CrosswalkError("official basis cannot carry editorial configuration")
    elif not row["rationale"] or row["configuration_sha256"] is None:
        raise CrosswalkError("editorial basis lacks rationale or configuration hash")
    weight = None
    if row["weight"] is not None:
        raw = row["weight"]
        if not official or raw["evidence_ref"] != row["basis_ref"]:
            raise CrosswalkError("weight is not published in the link basis")
        weight = PublishedWeight(
            raw["value"],
            raw["scope"],
            raw["denominator"],
            evidence[raw["evidence_ref"]],
        )
    return Link(
        row["link_id"],
        target,
        cast(Basis, row["basis_kind"]),
        evidence[row["basis_ref"]],
        tuple(evidence[ref] for ref in sorted(refs)),
        row["rationale"],
        row["configuration_sha256"],
        row["reviewed_by_role"],
        row["reviewed_on"],
        weight,
    )


def _derive(row: Mapping[str, Any], links: tuple[Link, ...]) -> tuple[Status, str]:
    if not links:
        if row["reason"] == "reviewer_rejected_no_target":
            _signoff(row)
            return "unmapped", "reviewer_rejected_no_target"
        if row["reason"] == "reviewer_undecided":
            _signoff(row)
            return "ambiguous", "reviewer_undecided"
        if row["reason"] == "awaiting_human_review":
            if row["reviewed_by_role"] or row["reviewed_on"]:
                raise CrosswalkError("unreviewed decision cannot carry a signature")
            return "unreviewed", "awaiting_human_review"
        raise CrosswalkError("empty decision cannot claim a mapping")
    _signoff(row)
    if len(links) == 1:
        return "mapped", "reviewer_approved"
    weights = tuple(link.weight for link in links)
    if all(weight is None for weight in weights):
        return "ambiguous", "multi_link_no_published_weight"
    if any(weight is None for weight in weights):
        raise CrosswalkError("mixed null and published weights")
    identities = {
        (weight.evidence, weight.scope, weight.denominator)
        for weight in weights
        if weight is not None
    }
    if len(identities) != 1:
        raise CrosswalkError(
            "published weights do not share evidence scope and denominator"
        )
    return "mapped", "reviewer_approved"


def parse_crosswalk(
    review_body: bytes,
    binding_body: bytes,
    *,
    context: object,
    allow_invented: bool = False,
) -> Crosswalk:
    """Validate exact bytes and context, then expose only immutable typed data."""
    try:
        schema_body = _SCHEMA.read_bytes()
    except OSError as error:
        raise CrosswalkError("crosswalk schema is missing") from error
    schema = _json(schema_body)
    document, binding = _json(review_body), _json(binding_body)
    _shape(document, schema, schema)
    _shape(context, schema["$defs"]["context"], schema)
    _shape(binding, schema["$defs"]["binding"], schema)
    context = cast(dict[str, Any], context)
    _safe_text(document)
    _safe_text(context)
    review_hash = hashlib.sha256(review_body).hexdigest()
    schema_hash = hashlib.sha256(schema_body).hexdigest()
    context_hash = hashlib.sha256(
        json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        binding["review_sha256"],
        binding["schema_sha256"],
        binding["context_sha256"],
    ) != (review_hash, schema_hash, context_hash):
        raise CrosswalkError("review binding is stale")
    invented = document["mode"] == "invented_fixture"
    if document["mode"] != context["mode"] or (invented and not allow_invented):
        raise CrosswalkError("fixture evidence is not production admission")
    snapshots = _snapshots(context, invented=invented)
    meanings: set[Endpoint] = set()
    for row in context["endpoint_meanings"]:
        endpoint = _endpoint(row["endpoint"], snapshots, invented=invented)
        if endpoint in meanings:
            raise CrosswalkError("duplicate endpoint meaning")
        meanings.add(endpoint)

    def declared(raw: Mapping[str, Any]) -> Endpoint:
        endpoint = _endpoint(raw, snapshots, invented=invented)
        if endpoint not in meanings:
            raise CrosswalkError("endpoint meaning is absent from the bound inventory")
        return endpoint

    evidence = _evidence(document, snapshots)
    groups: list[GroupDecision] = []
    seen_groups: set[tuple[str, Endpoint]] = set()
    seen_links: set[str] = set()
    for row in document["groups"]:
        source = declared(row["source"])
        product_hop = row["link_kind"] == "product_to_activity"
        if source.system not in (
            {"customs_tariff"}
            if product_hop
            else {"manufacturing_industry", "isic_class"}
        ):
            raise CrosswalkError("link source is outside its closed direction")
        group_key = (row["link_kind"], source)
        if group_key in seen_groups:
            raise CrosswalkError("duplicate source decision")
        seen_groups.add(group_key)
        links: list[Link] = []
        seen_targets: set[Endpoint] = set()
        for edge in row["links"]:
            target = declared(edge["target"])
            if target.system not in (
                {"manufacturing_industry", "isic_class"}
                if product_hop
                else {"occupation_group"}
            ):
                raise CrosswalkError("link target is outside its closed direction")
            if edge["link_id"] in seen_links or target in seen_targets:
                raise CrosswalkError("duplicate link or target identity")
            seen_links.add(edge["link_id"])
            seen_targets.add(target)
            links.append(_link(edge, evidence, target, invented=invented))
        ordered = tuple(sorted(links, key=lambda item: (item.target, item.link_id)))
        status, reason = _derive(row, ordered)
        if (row["status"], row["reason"]) != (status, reason):
            raise CrosswalkError(
                "claimed status or reason differs from recomputed decision"
            )
        groups.append(
            GroupDecision(
                cast(LinkKind, row["link_kind"]),
                source,
                status,
                reason,
                row["reviewed_by_role"],
                row["reviewed_on"],
                ordered,
            )
        )
    families: list[TariffFamily] = []
    seen_parents: set[Endpoint] = set()
    seen_children: set[Endpoint] = set()
    for row in context["tariff_families"]:
        parent = declared(row["parent"])
        children = tuple(declared(raw) for raw in row["children"])
        snapshot = snapshots.get((row["registry_key"], row["snapshot_sha256"]))
        if (
            snapshot is None
            or parent.system != "customs_tariff"
            or parent.level != "tariff8"
            or parent in seen_parents
        ):
            raise CrosswalkError("tariff family has no unique bound parent")
        if len(set(children)) != len(children) or seen_children.intersection(children):
            raise CrosswalkError("tariff child is duplicated")
        if any(
            child.system != "customs_tariff"
            or child.level != "tariff12"
            or child.version != snapshot.registry_key + ":" + snapshot.snapshot_sha256
            for child in children
        ):
            raise CrosswalkError("tariff children differ from the bound snapshot")
        seen_parents.add(parent)
        seen_children.update(children)
        families.append(TariffFamily(parent, tuple(sorted(children)), snapshot))
    return Crosswalk(
        document["schema_version"],
        document["mapping_revision"],
        cast(Mode, document["mode"]),
        review_hash,
        schema_hash,
        context_hash,
        tuple(sorted(groups, key=lambda item: (item.link_kind, item.source))),
        tuple(sorted(families, key=lambda item: item.parent)),
    )


def load_crosswalk(
    path: Path | None = None, *, context: object, allow_invented: bool = False
) -> Crosswalk:
    """Read only the explicit review and its binding; never select a cache file."""
    review_path = path if path is not None else _REVIEW / (_STEM + ".json")
    try:
        body = review_path.read_bytes()
        binding = binding_path(review_path).read_bytes()
    except OSError as error:
        raise CrosswalkError("crosswalk review or binding is missing") from error
    return parse_crosswalk(
        body, binding, context=context, allow_invented=allow_invented
    )
