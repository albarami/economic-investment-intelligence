"""AI-14 predicate and fallback plants on invented facts and local catalogues."""

import asyncio
from copy import deepcopy
from datetime import date

import pytest
from product.tests.test_catalogue_foundations import _claim, _claims, _load, _slot
from product.tests.test_public_playbook import catalogue
from public_release_fixture import _source_record

from eii_core.facts import Fact
from eii_product.api.answers import Answer
from eii_product.assistant.accounting import CHECKS, account
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.models import Bundle, Evidence
from eii_product.assistant.playbooks.registry import Selection, load_playbook
from eii_product.assistant.templates.writer import compose


def invented_bundle():
    identity = "f_" + "ab" * 16
    fact = Fact(
        fact_id=identity,
        value=9,
        unit="count",
        period="2025",
        geography={"kind": "national"},
        provenance="public",
        input_classes=["public"],
        evidence_status="observed",
        reliability="standard",
        coverage_keys=[],
        caveat_keys=["invented_caveat"],
        label_en="Invented count",
        label_ar="عدد تجريبي",
        lineage_ref="lin_pub_sector_accounts",
        release_id="ab" * 32,
    )
    evidence = Evidence(
        fact,
        "price_deal_count",
        [
            dict(
                lineage_id="lin_pub_sector_accounts",
                table_name="pub_sector_accounts",
                source_id="src-invented",
                input_class="public",
                transform="invented.method@v1",
            )
        ],
        [dict(_source_record(), retrieved_on=date(2026, 1, 2))],
    )
    assert evidence.valid(fact.release_id)
    return Bundle(
        fact.release_id,
        {},
        cards=[{"kind": "invented", "fact_ids": [identity]}],
        facts={identity: evidence},
    )


@pytest.mark.parametrize(
    "plant",
    ["inferred", "subject_provenance", "caveat", "companion", "application_key"],
)
def test_accounting_claim_predicates(tmp_path, plant):
    section = "inferred" if plant == "inferred" else "observed"
    _, cat = _load(
        tmp_path,
        _claims(
            _claim(
                subject="national",
                section=section,
                strengths="[strong]" if section == "inferred" else "[]",
                slots=_slot(geo="national"),
                caveats="[invented_caveat]",
            )
        ),
    )
    assert isinstance(cat, Catalogue)
    bundle = invented_bundle()
    evidence = next(iter(bundle.facts.values()))
    if section == "inferred":
        evidence.fact = evidence.fact.model_copy(update={"evidence_status": "inferred"})
    definition = load_playbook("site_check", cat)
    definition.claims = [
        Selection(claim_key="area_note", slots={"reading": evidence.fact.fact_id})
    ]
    draft = compose(bundle, definition, cat)
    assert all(account(draft, bundle, definition, cat).values())
    check = "Limits stated"
    if plant == "inferred":
        draft.assumptions = []
        check = "Assumptions"
    elif plant == "subject_provenance":
        evidence.fact = evidence.fact.model_copy(
            update={"provenance": "synthetic", "input_classes": ["synthetic"]}
        )
        check = "Scope"
    elif plant == "caveat":
        draft.caveat_keys = []
    elif plant == "application_key":
        draft.coverage_keys.append("invented_unselected")
    else:
        from dataclasses import replace

        cat = replace(
            cat,
            claims=(replace(cat.claims[0], required_companions=("invented_missing",)),),
        )
    assert account(draft, bundle, definition, cat)[check] is False


@pytest.mark.parametrize("check", CHECKS)
def test_fallback_runs_every_check_and_refuses_failure(check, monkeypatch):
    async def run():
        bundle = invented_bundle()
        cat = catalogue()
        definition = load_playbook("site_check", cat)
        bundle.inputs = {"activity": "INVENTED-activity"}
        fallback = compose(bundle, definition, cat)
        candidate = deepcopy(fallback)
        candidate.brief["layout"] = [{"component": "invented", "props": {}}]
        if check == "Sources":
            fallback.brief["layout"] = [
                {"component": "invented", "props": {"fact_id": "f_" + "cd" * 16}}
            ]
        elif check == "Assumptions":
            fallback.assumptions = []
        elif check == "Nothing invented":
            fallback.brief["layout"] = candidate.brief["layout"]
        elif check == "Scope":
            fallback.playbook = "invented"
        else:
            fallback.caveat_keys = []
        monkeypatch.setattr("eii_product.api.answers.compose", lambda *args: fallback)
        calls = []

        async def gate(draft, bundle, definition, cat):
            result = account(draft, bundle, definition, cat)
            assert set(result) == set(CHECKS)
            calls.append(deepcopy(result))
            return result

        answer = Answer(
            "INVENTED-answer", bundle, definition, cat, gate=gate, candidate=candidate
        )
        events = [event async for event in answer.events()]
        assert len(calls) == 2
        assert calls[-1][check] is False
        assert events[-1].kind == "error"
        assert not any(event.kind in {"narrative", "done"} for event in events)
        assert len(answer.failures) == 1

    asyncio.run(run())


def test_incomplete_lineage_is_never_evidence():
    async def run():
        bundle = invented_bundle()
        next(iter(bundle.facts.values())).sources.clear()
        cat = catalogue()
        answer = Answer(
            "INVENTED-answer", bundle, load_playbook("site_check", cat), cat
        )
        events = [event async for event in answer.events()]
        assert [event.kind for event in events] == ["error"]

    asyncio.run(run())


@pytest.mark.parametrize(
    "requested,classes,expected",
    [
        ("strong", ["public"], "strong"),
        ("strong", ["public", "synthetic"], "indicative"),
        ("strong", ["public", "synthetic", "simulated"], "illustrative"),
        ("indicative", ["public", "simulated"], "illustrative"),
        ("illustrative", ["synthetic"], "illustrative"),
    ],
)
def test_template_strength_cap(requested, classes, expected):
    from eii_product.assistant.templates.writer import cap_strength

    assert cap_strength(requested, classes) == expected


def test_catalogue_template_numeral_plant(tmp_path):
    from eii_product.assistant.catalogue.schema import Refusal

    _, valid = _load(tmp_path, _claims(_claim()), name="valid")
    assert isinstance(valid, Catalogue)
    _, planted = _load(tmp_path, _claims(_claim(en="Invented 7.")), name="planted")
    assert isinstance(planted, Refusal)


def test_application_status_templates_are_closed_and_numeral_free():
    from eii_product.assistant.catalogue.scan import find_numeral
    from eii_product.assistant.templates.status import (
        STATUS_KEYS,
        STEP_LABELS,
        status_key,
    )

    for labels in STEP_LABELS.values():
        for text in labels:
            assert find_numeral(text) is None
            assert find_numeral(text + " 7") is not None
    for key, value in STATUS_KEYS.items():
        assert status_key(key) == value
    with pytest.raises(ValueError, match="status_invalid"):
        status_key("invented")


def test_nonpublic_fact_never_enters_public_evidence():
    async def run():
        bundle = invented_bundle()
        evidence = next(iter(bundle.facts.values()))
        evidence.fact = evidence.fact.model_copy(
            update={"provenance": "synthetic", "input_classes": ["synthetic"]}
        )
        cat = catalogue()
        answer = Answer(
            "INVENTED-answer", bundle, load_playbook("site_check", cat), cat
        )
        events = [event async for event in answer.events()]
        assert [event.kind for event in events] == ["error"]

    asyncio.run(run())


@pytest.mark.parametrize("plant", ["unknown", "mixed"])
def test_writer_direct_refusals(tmp_path, plant):
    _, cat = _load(
        tmp_path, _claims(_claim(subject="national", slots=_slot(geo="national")))
    )
    assert isinstance(cat, Catalogue)
    bundle = invented_bundle()
    evidence = next(iter(bundle.facts.values()))
    definition = load_playbook("site_check", cat)
    definition.claims = [
        Selection(claim_key="area_note", slots={"reading": evidence.fact.fact_id})
    ]
    other = deepcopy(evidence)
    other.fact = other.fact.model_copy(update={"fact_id": "f_" + "cd" * 16})
    bundle.facts[other.fact.fact_id] = other
    definition.claims[0].slots["other"] = other.fact.fact_id
    compose(bundle, definition, cat)
    if plant == "unknown":
        definition.claims[0].claim_key = "invented"
        reason = "unknown_claim"
    else:
        other.fact = other.fact.model_copy(update={"evidence_status": "inferred"})
        reason = "evidence_status_mismatch"
    with pytest.raises(ValueError, match="^" + reason + "$"):
        compose(bundle, definition, cat)
