"""S2-T47 AC3/5, F1/2/3/4: classification association, never allocation."""

from dataclasses import fields, replace
from typing import get_args, get_type_hints

import pytest
from custodian.tests.fixtures.classification import (
    declare,
    documents,
    family_documents,
    group,
    industry,
    isic,
    link,
    occupation,
    parse,
    product,
    weight,
)

from eii_core.classification import (
    c13_selection,
    endpoint_from_parts,
    resolve_occupations,
)


def endpoint(raw):
    return endpoint_from_parts(**raw)


def test_ac3_two_hop_trace_and_missing_link():
    review, context = documents()
    review["evidence"].append(
        {
            "evidence_id": "syn-occupation-basis",
            "registry_key": "mfg_industry/syn-a",
            "snapshot_sha256": "a" * 64,
            "locator": "syn-occupation-table/syn-row",
        }
    )
    review["groups"][1]["links"][0].update(
        basis_ref="syn-occupation-basis", source_refs=["syn-occupation-basis"]
    )
    result = resolve_occupations(parse(review, context), endpoint(product()))
    assert result.status == "mapped"
    assert result.occupations == (endpoint(occupation()),)
    assert result.paths[0].product_link.evidence[0].locator == "syn-table/syn-row"
    assert (
        result.paths[0].occupation_link.evidence[0].snapshot.snapshot_sha256 == "a" * 64
    )
    assert (
        result.paths[0].occupation_link.evidence[0].locator
        == "syn-occupation-table/syn-row"
    )
    assert (
        result.paths[0].occupation_link.evidence[0].snapshot.registry_key
        == "mfg_industry/syn-a"
    )
    assert result.method_version == "classification_resolver.v1"
    assert result.mapping_revision == "syn-review-a"
    review["groups"].pop()
    missing = resolve_occupations(parse(review, context), endpoint(product()))
    assert missing.status == "unreviewed"
    assert missing.reason == "outside_review_scope"
    assert missing.occupations == ()
    assert missing.paths == ()


def test_f1_absent_endpoint_is_unreviewed_not_unmapped():
    review, context = documents()
    missing = endpoint(product("1000.0001.0002"))
    result = resolve_occupations(parse(review, context), missing)
    assert (result.status, result.reason, result.occupations) == (
        "unreviewed",
        "outside_review_scope",
        (),
    )


@pytest.mark.parametrize("status", ["unreviewed", "unmapped", "ambiguous", "mapped"])
def test_f2_composition_cannot_upgrade_worse_hop(status):
    review, context = documents()
    review["groups"][1] = group(
        industry(),
        [link(occupation(), "syn-link-b")] if status == "mapped" else [],
        kind="activity_to_occupation",
        status=status,
    )
    result = resolve_occupations(parse(review, context), endpoint(product()))
    assert result.status == status
    assert bool(result.occupations) == (status == "mapped")


@pytest.mark.parametrize("dimension", ["system", "version", "level", "code"])
def test_f4_middle_endpoint_identity_has_no_bridge(dimension):
    review, context = documents()
    if dimension == "system":
        other = isic()
    elif dimension == "version":
        other = industry()
        other["version"] = "mfg_industry/syn-a:" + "e" * 64
        context["snapshots"].append(
            {**context["snapshots"][2], "snapshot_sha256": "e" * 64}
        )
    elif dimension == "level":
        # A wrong level is refused before composition, never fuzzily matched.
        other = industry()
        other["level"] = "class"
    else:
        other = industry("b")
    declare(context, other)
    review["groups"][1]["source"] = other
    if dimension == "level":
        from eii_custodian.publicdata.review.classification import CrosswalkError

        with pytest.raises(CrosswalkError):
            parse(review, context)
    else:
        result = resolve_occupations(parse(review, context), endpoint(product()))
        assert result.status == "unreviewed"
        assert result.occupations == ()


def test_f2_two_hop_weights_stay_side_by_side_never_multiplied():
    review, context = documents()
    for decision in review["groups"]:
        decision["links"][0].update(
            basis_kind="official",
            rationale=None,
            configuration_sha256=None,
            weight=weight(),
        )
    result = resolve_occupations(parse(review, context), endpoint(product()))
    path = result.paths[0]
    assert path.product_link.weight.value == "0.4"
    assert path.occupation_link.weight.value == "0.4"
    assert {field.name for field in fields(path)} == {"product_link", "occupation_link"}
    with pytest.raises(TypeError):
        replace(path, weight="0.16")


def test_ac3_many_to_many_keeps_paths_without_numeric_input_duplication():
    review, context = documents()
    review["groups"][0]["links"] = [
        link(industry(), "syn-left", official=True, split=weight()),
        link(industry("b"), "syn-right", official=True, split=weight("0.6")),
    ]
    review["groups"].append(
        group(
            industry("b"),
            [link(occupation(), "syn-second")],
            kind="activity_to_occupation",
        )
    )
    result = resolve_occupations(parse(review, context), endpoint(product()))
    assert len(result.paths) == 2
    assert result.occupations == (endpoint(occupation()),)
    assert "value" not in {field.name for field in fields(result)}
    # Losing one branch cannot silently preserve the other branch as a mapped result.
    review["groups"].pop()
    result = resolve_occupations(parse(review, context), endpoint(product()))
    assert result.occupations == ()
    assert result.paths == ()


def test_ac5_stable_order_from_shuffled_inputs():
    review, context = documents()
    baseline = resolve_occupations(parse(review, context), endpoint(product()))
    review["groups"].reverse()
    result = resolve_occupations(parse(review, context), endpoint(product()))
    assert result.paths == baseline.paths
    assert result.occupations == baseline.occupations
    assert result.status == baseline.status


@pytest.mark.parametrize(
    "plant",
    [
        "split_parent",
        "partly_mapped_parent",
        "missing_child",
        "unreviewed_child",
        "ambiguous_child",
        "all_children_agree",
        "missing_family",
        "all_children_absent",
        "all_children_unreviewed",
        "all_children_unmapped",
    ],
)
def test_f3_c13_parent_requires_every_bound_child(plant):
    review, context, parent = family_documents()
    if plant == "split_parent":
        review["groups"][-1]["links"][0]["target"] = industry("b")
        review["groups"].append(
            group(
                industry("b"),
                [link(occupation(), "syn-split-second")],
                kind="activity_to_occupation",
            )
        )
    elif plant == "partly_mapped_parent":
        review["groups"][-1] = group(product("1000.0001.0002"), status="unmapped")
    elif plant == "missing_child":
        review["groups"].pop()
    elif plant == "unreviewed_child":
        review["groups"][-1] = group(product("1000.0001.0002"), status="unreviewed")
    elif plant == "ambiguous_child":
        review["groups"][-1] = group(product("1000.0001.0002"), status="ambiguous")
    elif plant == "missing_family":
        context["tariff_families"] = []
    elif plant == "all_children_absent":
        review["groups"] = [review["groups"][1]]
    elif plant in {"all_children_unreviewed", "all_children_unmapped"}:
        status = plant.removeprefix("all_children_")
        for index in (0, 2):
            review["groups"][index] = group(
                review["groups"][index]["source"], status=status
            )
    result = c13_selection(parse(review, context), endpoint(parent))
    assert result.bucket == (
        "mapped" if plant == "all_children_agree" else "not_mapped"
    )
    assert result.industry == (
        endpoint(industry()) if plant == "all_children_agree" else None
    )
    expected = {
        "split_parent": ("ambiguous", "bound_children_not_unanimous"),
        "partly_mapped_parent": ("unmapped", "reviewer_rejected_no_target"),
        "missing_child": ("unreviewed", "outside_review_scope"),
        "unreviewed_child": ("unreviewed", "awaiting_human_review"),
        "ambiguous_child": ("ambiguous", "reviewer_undecided"),
        "all_children_agree": ("mapped", "all_bound_children_agree"),
        "missing_family": ("unreviewed", "missing_bound_tariff_family"),
        "all_children_absent": ("unreviewed", "outside_review_scope"),
        "all_children_unreviewed": ("unreviewed", "awaiting_human_review"),
        "all_children_unmapped": ("unmapped", "reviewer_rejected_no_target"),
    }[plant]
    assert (result.status, result.reason) == expected
    resolved = resolve_occupations(parse(review, context), endpoint(parent))
    assert (resolved.status, resolved.reason) == expected
    assert resolved.occupations == (
        (endpoint(occupation()),) if plant == "all_children_agree" else ()
    )


@pytest.mark.parametrize("status", ["mapped", "unmapped", "ambiguous", "unreviewed"])
def test_f3_c13_has_only_mapped_and_not_mapped_buckets(status):
    review, context = documents()
    review["groups"][0] = group(
        product(), [link(industry())] if status == "mapped" else [], status=status
    )
    result = c13_selection(parse(review, context), endpoint(product()))
    assert result.bucket == ("mapped" if status == "mapped" else "not_mapped")


def test_f3_c13_multi_target_has_no_allocation_rule():
    review, context = documents()
    review["groups"][0]["links"] = [
        link(industry(), "syn-left", official=True, split=weight()),
        link(industry("b"), "syn-right", official=True, split=weight("0.6")),
    ]
    result = c13_selection(parse(review, context), endpoint(product()))
    assert (result.bucket, result.industry) == ("not_mapped", None)


@pytest.mark.parametrize("parent", [False, True])
def test_f3_c13_single_published_weight_has_no_allocation_rule(parent):
    if parent:
        review, context, source = family_documents()
    else:
        review, context = documents()
        source = product()
    review["groups"][0]["links"][0] = link(industry(), official=True, split=weight())
    result = c13_selection(parse(review, context), endpoint(source))
    assert (result.status, result.reason, result.bucket, result.industry) == (
        "ambiguous",
        "no_single_manufacturing_industry",
        "not_mapped",
        None,
    )


def test_b_c13_requires_a_manufacturing_industry():
    review, context = documents()
    review["groups"][0]["links"][0]["target"] = isic()
    result = c13_selection(parse(review, context), endpoint(product()))
    assert (result.status, result.reason, result.bucket, result.industry) == (
        "ambiguous",
        "no_single_manufacturing_industry",
        "not_mapped",
        None,
    )


def test_b_direct_tariff8_requires_a_bound_family():
    review, context, parent = family_documents()
    context["tariff_families"] = []
    review["groups"].append(group(parent, [link(industry(), "syn-parent")]))
    crosswalk = parse(review, context)
    selected = c13_selection(crosswalk, endpoint(parent))
    resolved = resolve_occupations(crosswalk, endpoint(parent))
    assert (selected.status, selected.reason, selected.bucket) == (
        "unreviewed",
        "missing_bound_tariff_family",
        "not_mapped",
    )
    assert selected.industry is None
    assert (resolved.status, resolved.reason) == (
        "unreviewed",
        "missing_bound_tariff_family",
    )
    assert resolved.occupations == resolved.paths == ()


def test_b_resolver_refuses_a_non_tariff_source():
    review, context = documents()
    with pytest.raises(
        ValueError,
        match="resolver requires a validated crosswalk and a tariff identity",
    ):
        resolve_occupations(parse(review, context), endpoint(industry()))


def test_d_reason_types_and_selection_contract_are_closed():
    from pathlib import Path

    import eii_core.classification as module

    reasons = {
        "reviewer_approved",
        "reviewer_rejected_no_target",
        "reviewer_undecided",
        "multi_link_no_published_weight",
        "awaiting_human_review",
        "outside_review_scope",
    }
    selection_reasons = {
        "all_bound_children_agree",
        "bound_children_not_unanimous",
        "missing_bound_tariff_family",
        "no_single_manufacturing_industry",
    }
    assert set(get_args(getattr(module, "Reason", None))) == reasons
    assert set(get_args(getattr(module, "SelectionReason", None))) == selection_reasons
    for shape in (
        module.GroupDecision,
        module.OccupationResolution,
        module.C13Selection,
    ):
        assert get_type_hints(shape)["reason"] == module.Reason | module.SelectionReason
    contract = (
        Path("docs/03_DATA_CONTRACTS.md")
        .read_text()
        .split("### Reviewed classification crosswalk (S2-T47)", 1)[1]
        .split("\n### ", 1)[0]
    )
    paragraph = contract.split("`C13Selection` is a typed input shape", 1)[1]
    assert all(f"`{reason}`" in paragraph for reason in selection_reasons)


@pytest.mark.parametrize(
    "field", ["worker_attribute", "qualification", "person_id", "protected_statistic"]
)
def test_ac4_typed_consumer_rejects_prohibited_output(field):
    review, context = documents()
    result = resolve_occupations(parse(review, context), endpoint(product()))
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        replace(result, **{field: "syn-forbidden"})


def test_ac5_consumer_imports_no_custodian_and_uses_no_arithmetic():
    import ast
    from pathlib import Path

    import eii_core.classification as module

    tree = ast.parse(Path(module.__file__).read_text())
    assert not any(
        isinstance(node, ast.AugAssign)
        or (isinstance(node, ast.BinOp) and not isinstance(node.op, ast.BitOr))
        for node in ast.walk(tree)
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("eii_custodian")
    assert "eii_custodian" not in module.__dict__


def test_f3_c13_t1_t2_t3_worked_example_selection_inputs():
    review, context = documents()
    second, third = product("1000.0001.0002"), product("1000.0001.0003")
    declare(context, second)
    declare(context, third)
    review["groups"].extend(
        [
            group(second, [link(industry(), "syn-t2")]),
            group(third, status="unmapped"),
        ]
    )
    crosswalk = parse(review, context)
    first_two = [
        c13_selection(crosswalk, endpoint(item)) for item in [product(), second]
    ]
    assert all(
        item.industry == endpoint(industry()) and item.bucket == "mapped"
        for item in first_two
    )
    assert c13_selection(crosswalk, endpoint(third)).bucket == "not_mapped"
    # S7-T11 owns the QAR arithmetic; no quantities enter this contract.
    assert all(
        "value" not in {field.name for field in fields(item)} for item in first_two
    )


@pytest.mark.parametrize("first_status", ["mapped", "ambiguous"])
@pytest.mark.parametrize(
    "second_status", ["mapped", "ambiguous", "unmapped", "unreviewed"]
)
def test_f2_worst_status_over_multiple_branches(first_status, second_status):
    review, context = documents()
    weighted = first_status == "mapped"
    review["groups"][0] = group(
        product(),
        [
            link(
                industry(),
                "syn-left",
                official=weighted,
                split=weight() if weighted else None,
            ),
            link(
                industry("b"),
                "syn-right",
                official=weighted,
                split=weight("0.6") if weighted else None,
            ),
        ],
        status=first_status,
        reason="reviewer_approved" if weighted else "multi_link_no_published_weight",
    )
    review["groups"].append(
        group(
            industry("b"),
            [link(occupation(), "syn-second")] if second_status == "mapped" else [],
            kind="activity_to_occupation",
            status=second_status,
        )
    )
    result = resolve_occupations(parse(review, context), endpoint(product()))
    expected = second_status if second_status != "mapped" else first_status
    assert result.status == expected
    assert bool(result.occupations) == (expected == "mapped")


def test_f3_direct_parent_mapping_cannot_bypass_complete_family():
    review, context, parent = family_documents()
    review["groups"].append(group(parent, [link(industry(), "syn-parent")]))
    review["groups"].pop(2)
    result = c13_selection(parse(review, context), endpoint(parent))
    assert result.bucket == "not_mapped"
    assert result.industry is None
    resolved = resolve_occupations(parse(review, context), endpoint(parent))
    assert resolved.occupations == ()
    assert resolved.status == "unreviewed"
    assert resolved.paths == ()


def test_h_c13_refuses_a_non_tariff_source():
    review, context = documents()
    with pytest.raises(
        ValueError, match="C13 requires a validated crosswalk and a tariff identity"
    ):
        c13_selection(parse(review, context), endpoint(industry()))


def test_h_resolver_requires_a_crosswalk():
    with pytest.raises(
        ValueError,
        match="resolver requires a validated crosswalk and a tariff identity",
    ):
        resolve_occupations({}, endpoint(product()))


def test_h_c13_requires_a_crosswalk():
    with pytest.raises(
        ValueError, match="C13 requires a validated crosswalk and a tariff identity"
    ):
        c13_selection({}, endpoint(product()))


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"system": "hs"}, "unknown classification system"),
        ({"level": "heading"}, "unknown classification level"),
        ({"version": ""}, "classification identity is empty"),
    ],
    ids=["system", "level", "empty_identity"],
)
def test_h_endpoint_identity_guards(changes, message):
    parts = {
        "system": "customs_tariff",
        "version": "v",
        "level": "tariff8",
        "code": "c",
    }
    parts.update(changes)
    with pytest.raises(ValueError, match=message):
        endpoint_from_parts(**parts)
