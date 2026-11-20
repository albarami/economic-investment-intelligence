"""S2-T47 AC1/2/4/5 and F1/2/4/5/6/7/8: invented offline refusal plants."""

import json
from copy import deepcopy
from dataclasses import fields
from hashlib import sha256

import pytest
from custodian.tests.fixtures.classification import (
    REVIEW,
    SCHEMA,
    binding,
    declare,
    documents,
    encoded,
    family_documents,
    group,
    industry,
    isic,
    link,
    parse,
    product,
    weight,
)

from eii_custodian.publicdata.review.classification import (
    CrosswalkError,
    load_crosswalk,
)


def test_ac1_review_basis_and_binding():
    review, context = documents()
    result = parse(review, context)
    assert len(result.groups) == 2
    for decision in result.groups:
        edge = decision.links[0]
        assert edge.reviewed_by_role == "classification_reviewer"
        assert edge.reviewed_on == "2026-11-20"
        assert edge.evidence[0].snapshot.publisher == "SYN-PUBLISHER"
        assert edge.evidence[0].locator == "syn-table/syn-row"
        assert edge.configuration_sha256 == "c" * 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("basis_ref", ""),
        ("basis_kind", "model_suggested"),
        ("basis_kind", "prefix_match"),
        ("basis_kind", "name_match"),
        ("basis_kind", "published"),
        ("rationale", ""),
        ("configuration_sha256", None),
        ("reviewed_by_role", ""),
        ("reviewed_on", ""),
        ("reviewed_on", "2026-02-30"),
        ("source_refs", []),
        ("source_refs", ["missing-evidence"]),
    ],
)
def test_ac1_absent_basis_or_review_plant(field, value):
    review, context = documents()
    review["groups"][0]["links"][0][field] = value
    with pytest.raises(CrosswalkError):
        parse(review, context)


@pytest.mark.parametrize(
    "field",
    [
        "publisher",
        "title",
        "licence",
        "retrieved_on",
        "snapshot_sha256",
        "url",
        "registry_key",
    ],
)
def test_ac1_source_chain_plant(field):
    review, context = documents()
    context["snapshots"][0][field] = ""
    with pytest.raises(CrosswalkError):
        parse(review, context)


@pytest.mark.parametrize(
    "change", ["meaning", "version", "evidence", "review", "schema", "binding"]
)
def test_ac1_stale_binding_plant(change):
    review, context = documents()
    sidecar = json.loads(binding(encoded(review), context))
    if change == "meaning":
        context["endpoint_meanings"][0]["meaning_sha256"] = "e" * 64
    elif change == "version":
        context["endpoint_meanings"][0]["endpoint"]["version"] = "syn-other-version"
    elif change == "evidence":
        context["snapshots"][0]["snapshot_sha256"] = "e" * 64
    elif change == "review":
        review["mapping_revision"] = "syn-review-b"
    elif change == "schema":
        sidecar["schema_sha256"] = "e" * 64
    else:
        sidecar["unexpected"] = "syn"
    with pytest.raises(CrosswalkError):
        parse(review, context, binding_body=encoded(sidecar))


@pytest.mark.parametrize("status", ["mapped", "unmapped", "ambiguous", "unreviewed"])
def test_ac2_mapping_status_and_multiplicity(status):
    review, context = documents()
    review["groups"] = [
        group(
            product(), [link(industry())] if status == "mapped" else [], status=status
        )
    ]
    assert parse(review, context).groups[0].status == status


@pytest.mark.parametrize(
    "status,field",
    [
        (s, f)
        for s in ["unmapped", "ambiguous", "mapped"]
        for f in ["reviewed_by_role", "reviewed_on"]
    ],
)
def test_f1_unsigned_group_decision_plant(status, field):
    review, context = documents()
    decision = group(
        product(), [link(industry())] if status == "mapped" else [], status=status
    )
    decision[field] = ""
    review["groups"] = [decision]
    with pytest.raises(CrosswalkError):
        parse(review, context)


@pytest.mark.parametrize(
    "status,reason,links",
    [
        ("mapped", "unknown_reason", [link(industry())]),
        ("mapped", "awaiting_human_review", [link(industry())]),
        ("mapped", "reviewer_approved", []),
        ("unmapped", "reviewer_rejected_no_target", [link(industry())]),
        ("unreviewed", "awaiting_human_review", [link(industry())]),
        ("ambiguous", "reviewer_undecided", [link(industry())]),
    ],
)
def test_ac2_silent_status_upgrade_plant(status, reason, links):
    review, context = documents()
    review["groups"] = [group(product(), links, status=status, reason=reason)]
    with pytest.raises(CrosswalkError):
        parse(review, context)


def test_f2_unweighted_and_published_multi_link_controls():
    review, context = documents()
    edges = [link(industry(), "syn-left"), link(industry("b"), "syn-right")]
    review["groups"] = [
        group(
            product(),
            edges,
            status="ambiguous",
            reason="multi_link_no_published_weight",
        )
    ]
    assert len(parse(review, context).groups[0].links) == 2
    for edge, value in zip(edges, ["0.4", "0.6"], strict=True):
        edge.update(
            basis_kind="official",
            rationale=None,
            configuration_sha256=None,
            weight=weight(value),
        )
    review["groups"][0].update(status="mapped", reason="reviewer_approved")
    assert [edge.weight.value for edge in parse(review, context).groups[0].links] == [
        "0.4",
        "0.6",
    ]


@pytest.mark.parametrize(
    "plant",
    [
        "editorial_weight",
        "mixed_weights",
        "invented_equal_split",
        "different_scope",
        "different_denominator",
        "different_evidence",
        "different_basis_evidence",
        "weight_not_basis",
        "missing_weight_evidence",
        "weight_outside_unit",
        "weight_nan",
        "weight_exponent",
        "weight_number",
        "weighted_ambiguous",
    ],
)
def test_f2_weight_guard_plants(plant):
    review, context = documents()
    edges = [
        link(industry(), "syn-left", official=True, split=weight()),
        link(industry("b"), "syn-right", official=True, split=weight("0.6")),
    ]
    review["groups"] = [group(product(), edges)]
    first, second = edges
    if plant in {"editorial_weight", "invented_equal_split"}:
        first.update(
            basis_kind="editorial_reviewed",
            rationale="Invented split.",
            configuration_sha256="c" * 64,
        )
        if plant == "invented_equal_split":
            first["weight"]["value"] = second["weight"]["value"] = "0.5"
    elif plant == "mixed_weights":
        second["weight"] = None
    elif plant == "different_basis_evidence":
        review["evidence"].append({**review["evidence"][0], "evidence_id": "syn-other"})
        second.update(basis_ref="syn-other", source_refs=["syn-other"])
        second["weight"]["evidence_ref"] = "syn-other"
    elif plant.startswith("different_"):
        key = plant.removeprefix("different_")
        second["weight"]["evidence_ref" if key == "evidence" else key] = "syn-other"
    elif plant == "weight_not_basis":
        review["evidence"].append({**review["evidence"][0], "evidence_id": "syn-other"})
        second["weight"]["evidence_ref"] = "syn-other"
    elif plant == "missing_weight_evidence":
        first["weight"]["evidence_ref"] = "missing"
    elif plant == "weighted_ambiguous":
        review["groups"][0].update(
            status="ambiguous", reason="multi_link_no_published_weight"
        )
    else:
        first["weight"]["value"] = {
            "weight_outside_unit": "1.1",
            "weight_nan": "NaN",
            "weight_exponent": "1e-1",
            "weight_number": 0.4,
        }[plant]
    with pytest.raises(CrosswalkError):
        parse(review, context)


@pytest.mark.parametrize(
    "field", ["worker_attribute", "qualification", "person_id", "protected_statistic"]
)
@pytest.mark.parametrize(
    "location", ["root", "group", "link", "endpoint", "evidence", "context"]
)
def test_ac4_classification_only_boundary_plant(field, location):
    review, context = documents()
    locations = {
        "root": review,
        "group": review["groups"][0],
        "link": review["groups"][0]["links"][0],
        "endpoint": review["groups"][0]["source"],
        "evidence": review["evidence"][0],
        "context": context,
    }
    locations[location][field] = "syn-prohibited"
    with pytest.raises(CrosswalkError):
        parse(review, context)


@pytest.mark.parametrize(
    "plant",
    [
        "system",
        "level",
        "hs_revision",
        "occupation_other",
        "occupation_unmapped",
        "dotted_collision",
        "bare_code",
        "wrong_tariff_version",
        "undeclared_endpoint",
        "isic_version",
        "bridge_kind",
        "duplicate_group",
        "duplicate_target",
        "duplicate_link_id",
        "duplicate_evidence",
        "duplicate_meaning",
        "schema_major",
        "unknown_field",
        "unknown_status",
    ],
)
def test_ac5_closed_schema_and_endpoint_plants(plant):
    review, context = documents()
    first = review["groups"][0]
    if plant == "system":
        first["source"]["system"] = "hs"
    elif plant == "level":
        first["source"]["level"] = "heading"
    elif plant == "hs_revision":
        first["source"]["version"] = "HS-2022"
    elif plant.startswith("occupation_"):
        review["groups"][1]["links"][0]["target"]["code"] = plant.removeprefix(
            "occupation_"
        )
    elif plant == "dotted_collision":
        first["source"]["code"] = "SYN-TARIFF-10.0000.010001"
    elif plant == "bare_code":
        first["source"]["code"] = "1" * 8
    elif plant == "wrong_tariff_version":
        first["source"]["version"] = "cus_imp_2019:" + "b" * 64
    elif plant == "undeclared_endpoint":
        first["links"][0]["target"] = industry("c")
    elif plant == "isic_version":
        endpoint = isic()
        endpoint["version"] = "syn-new-version"
        declare(context, endpoint)
        first["links"][0]["target"] = endpoint
    elif plant == "bridge_kind":
        first["link_kind"] = "industry_to_isic"
    elif plant == "duplicate_group":
        review["groups"].append(deepcopy(first))
    elif plant == "duplicate_target":
        first["links"].append(link(industry(), "syn-other-id"))
    elif plant == "duplicate_link_id":
        review["groups"][1]["links"][0]["link_id"] = "syn-link-a"
    elif plant == "duplicate_evidence":
        review["evidence"].append(deepcopy(review["evidence"][0]))
    elif plant == "duplicate_meaning":
        context["endpoint_meanings"].append(deepcopy(context["endpoint_meanings"][0]))
    elif plant == "schema_major":
        review["schema_version"] = "product_activity_occupation.v2"
    elif plant == "unknown_field":
        review["unexpected"] = "syn"
    elif plant == "unknown_status":
        first["status"] = "inferred"
    with pytest.raises(CrosswalkError):
        parse(review, context)


def test_f4_isic_endpoint_control_and_no_implicit_bridge():
    review, context = documents()
    review["groups"][0]["links"][0]["target"] = isic()
    review["groups"][1]["source"] = isic()
    assert parse(review, context).groups[0].source.system in {
        "customs_tariff",
        "isic_class",
    }


def test_f5_fixture_mode_cannot_be_admitted_as_production():
    review, context = documents()
    with pytest.raises(CrosswalkError):
        parse(review, context, allow_invented=False)
    review["mode"] = "production"
    with pytest.raises(CrosswalkError):
        parse(review, context)


def test_ac5_missing_binding(tmp_path):
    review, context = documents()
    path = tmp_path / "syn-review.json"
    path.write_bytes(encoded(review))
    with pytest.raises(CrosswalkError):
        load_crosswalk(path, context=context, allow_invented=True)


@pytest.mark.parametrize(
    "bad", [b"{", b"[]", b'{"schema_version": "x", "schema_version": "y"}']
)
def test_ac5_malformed_json_or_duplicate_property(bad):
    from eii_custodian.publicdata.review.classification import parse_crosswalk

    _, context = documents()
    with pytest.raises(CrosswalkError):
        parse_crosswalk(bad, b"{}", context=context, allow_invented=True)


def test_f6_empty_committed_review_has_no_approval_or_carriage():
    context = {
        "mode": "production",
        "snapshots": [],
        "endpoint_meanings": [],
        "tariff_families": [],
    }
    result = load_crosswalk(REVIEW, context=context)
    assert result.groups == ()
    assert result.mode == "production"
    assert result.review_sha256 == sha256(REVIEW.read_bytes()).hexdigest()
    assert "release_table" not in {field.name for field in fields(result)}
    schema = json.loads(SCHEMA.read_text())
    assert schema["additionalProperties"] is False
    assert (
        schema["properties"]["schema_version"]["const"]
        == "product_activity_occupation.v1"
    )


def test_f6_f8_contract_names_task_modules_and_deferred_carriage():
    from pathlib import Path

    contract = (
        Path("docs/03_DATA_CONTRACTS.md")
        .read_text()
        .split("### Reviewed classification crosswalk (S2-T47)", 1)[1]
        .split("\n### ", 1)[0]
    )
    for required in [
        "product_activity_occupation.v1",
        "S7-T11",
        "custodian/src/eii_custodian/publicdata/review/classification.py",
        "core/src/eii_core/classification.py",
        "core/tests/test_calculation_purity.py",
        "mfg_industry/main-manufacturing-products",
        "Manufacturing industries and main manufacturing products",
    ]:
        assert required in contract
    assert "S2-T45" not in contract


def test_f3_method_contract_keeps_every_nonmapped_status_in_one_bucket():
    from pathlib import Path

    card = (
        Path("docs/07_ECONOMIC_METHODS.md")
        .read_text()
        .split("### C13 Imports against local production", 1)[1]
        .split("### C16", 1)[0]
    )
    assert "every non-`mapped` status" in card
    assert "every twelve-digit child" in card
    assert "bound `cus_imp_2025` snapshot" in card


@pytest.mark.parametrize(
    "plant",
    [
        "evidence_snapshot",
        "evidence_missing_locator",
        "duplicate_source_ref",
        "basis_not_a_source_ref",
        "official_editorial_config",
        "official_editorial_rationale",
        "signed_unreviewed",
        "invalid_role",
        "invalid_group_date",
        "retrieval_date",
        "credential_url",
        "token_url",
        "malformed_url",
        "duplicate_snapshot",
        "source_direction",
        "target_direction",
        "context_extra",
        "context_type",
        "meaning_hash",
        "binding_missing_field",
    ],
)
def test_ac5_additional_closed_admission_guards(plant):
    review, context = documents()
    decision = review["groups"][0]
    edge = decision["links"][0]
    sidecar = None
    if plant == "evidence_snapshot":
        review["evidence"][0]["snapshot_sha256"] = "f" * 64
    elif plant == "evidence_missing_locator":
        del review["evidence"][0]["locator"]
    elif plant == "duplicate_source_ref":
        edge["source_refs"].append("syn-basis")
    elif plant == "basis_not_a_source_ref":
        review["evidence"].append({**review["evidence"][0], "evidence_id": "syn-other"})
        edge["basis_ref"] = "syn-other"
    elif plant.startswith("official_editorial_"):
        edge["basis_kind"] = "official"
        if plant.endswith("config"):
            edge["rationale"] = None
        else:
            edge["configuration_sha256"] = None
    elif plant == "signed_unreviewed":
        review["groups"] = [group(product(), status="unreviewed")]
        review["groups"][0]["reviewed_by_role"] = "classification_reviewer"
    elif plant == "invalid_role":
        edge["reviewed_by_role"] = "SYN invalid role"
    elif plant == "invalid_group_date":
        decision["reviewed_on"] = "2026-02-30"
    elif plant == "retrieval_date":
        context["snapshots"][0]["retrieved_on"] = "2026-02-30"
    elif plant in {"credential_url", "token_url", "malformed_url"}:
        context["snapshots"][0]["url"] = {
            "credential_url": "https://syn-user:syn-password"
            + chr(64)
            + "example.invalid/source",
            "token_url": "https://example.invalid/source?token=syn-token",
            "malformed_url": "https://[invalid",
        }[plant]
    elif plant == "duplicate_snapshot":
        context["snapshots"].append(deepcopy(context["snapshots"][0]))
    elif plant == "source_direction":
        decision["source"] = industry()
    elif plant == "target_direction":
        edge["target"] = product()
    elif plant == "context_extra":
        context["unexpected"] = "syn"
    elif plant == "context_type":
        context["snapshots"] = "syn-not-an-array"
    elif plant == "meaning_hash":
        context["endpoint_meanings"][0]["meaning_sha256"] = "not-a-hash"
    elif plant == "binding_missing_field":
        raw = json.loads(binding(encoded(review), context))
        del raw["review_sha256"]
        sidecar = encoded(raw)
    with pytest.raises(CrosswalkError):
        parse(review, context, binding_body=sidecar)


@pytest.mark.parametrize(
    "plant",
    [
        "duplicate_parent",
        "empty_children",
        "duplicate_child",
        "wrong_child_grain",
        "wrong_snapshot",
        "missing_snapshot",
        "undeclared_child",
        "wrong_parent_grain",
    ],
)
def test_f3_bound_tariff_inventory_guards(plant):
    review, context, _ = family_documents()
    family = context["tariff_families"][0]
    if plant == "duplicate_parent":
        context["tariff_families"].append(deepcopy(family))
    elif plant == "empty_children":
        family["children"] = []
    elif plant == "duplicate_child":
        family["children"].append(deepcopy(family["children"][0]))
    elif plant == "wrong_child_grain":
        family["children"][0] = deepcopy(family["parent"])
    elif plant == "wrong_snapshot":
        context["snapshots"].append(
            {**context["snapshots"][0], "snapshot_sha256": "e" * 64}
        )
        family["snapshot_sha256"] = "e" * 64
    elif plant == "missing_snapshot":
        family["snapshot_sha256"] = "e" * 64
    elif plant == "undeclared_child":
        family["children"].append(product("1000.0001.0003"))
    elif plant == "wrong_parent_grain":
        family["parent"] = product()
    with pytest.raises(CrosswalkError):
        parse(review, context)


def test_ac1_valid_sha256_is_not_a_bare_identifier():
    review, context = documents()
    digest = "1" * 8 + "a" * 56
    review = json.loads(encoded(review).replace(("a" * 64).encode(), digest.encode()))
    context = json.loads(encoded(context).replace(("a" * 64).encode(), digest.encode()))
    assert len(parse(review, context).groups) == 2


def test_f2_changed_published_weight_requires_renewed_review():
    review, context = documents()
    review["groups"] = [
        group(
            product(),
            [
                link(industry(), "syn-left", official=True, split=weight("0.400")),
                link(industry("b"), "syn-right", official=True, split=weight("0.600")),
            ],
        )
    ]
    recorded_binding = binding(encoded(review), context)
    admitted = parse(review, context, binding_body=recorded_binding)
    assert [edge.weight.value for edge in admitted.groups[0].links] == [
        "0.400",
        "0.600",
    ]
    review["groups"][0]["links"][0]["weight"]["value"] = "0.500"
    with pytest.raises(CrosswalkError, match="binding is stale"):
        parse(review, context, binding_body=recorded_binding)
