"""Kills for account(). Each expected boolean is worked by hand."""

import pytest
from product.tests.test_playbook_accounting import invented_bundle

from eii_core.facts import Fact
from eii_product.assistant.accounting import account, referenced
from eii_product.assistant.catalogue.schema import Catalogue, Claim, Question
from eii_product.assistant.playbooks.models import Bundle
from eii_product.assistant.playbooks.registry import Definition
from eii_product.assistant.templates.writer import Draft

RELEASE = "ab" * 32
FACT_ID = "f_" + "ab" * 16
OTHER_ID = "f_" + "cd" * 16
MISSING_ID = "f_" + "ee" * 16
ACTIVITY = "INVENTED-activity"


def _definition() -> Definition:
    return Definition(
        name="site_check",
        calls=[],
        caveat_keys=[],
        still_to_test=[],
        not_measured=[],
        headline_key="invented_headline",
        decision_template_key="invented_decision",
        claims=[],
        layout=[],
        questions=[],
    )


def _brief(**overrides: object) -> dict[str, object]:
    brief: dict[str, object] = {
        "catalogue_version": "invented",
        "headline_key": "invented_headline",
        "decision_template_key": "invented_decision",
        "observed": [],
        "inferred": [],
        "still_to_test": [],
        "not_measured": [],
        "next_questions": [],
        "layout": [],
        "stage": [],
    }
    brief.update(overrides)
    return brief


def _draft(
    brief: dict[str, object],
    *,
    playbook: str = "site_check",
    assumptions: list[str] | None = None,
) -> Draft:
    return Draft(
        brief,
        playbook,
        [] if assumptions is None else assumptions,
        [],
        [],
        [],
        [],
    )


def _claim(
    key: str,
    companions: tuple[str, ...] = (),
    subject: str = "national",
) -> Claim:
    return Claim(key, "observed", subject, (), (), companions, (), ())


def _question(key: str, playbook: str = "site_check") -> Question:
    return Question(key, playbook, (), (), ())


def _cat(*claims: Claim, questions: tuple[Question, ...] = ()) -> Catalogue:
    return Catalogue("invented", claims, (), (), questions, ())


def _empty_bundle() -> Bundle:
    return Bundle(RELEASE, {})


def _retarget(
    *,
    status: str,
    provenance: str,
    classes: list[str],
    fact_id: str = FACT_ID,
) -> Bundle:
    bundle = invented_bundle()
    evidence = next(iter(bundle.facts.values()))
    evidence.fact = evidence.fact.model_copy(
        update={
            "fact_id": fact_id,
            "evidence_status": status,
            "provenance": provenance,
            "input_classes": classes,
        }
    )
    bundle.facts = {fact_id: evidence}
    bundle.cards = [{"kind": "invented", "fact_ids": [fact_id]}]
    return bundle


def _check(
    draft: Draft,
    bundle: Bundle,
    cat: Catalogue | None = None,
) -> dict[str, bool]:
    return account(draft, bundle, _definition(), cat if cat is not None else _cat())


def test_card_without_fact_ids_adds_no_evidence() -> None:
    bundle = invented_bundle()
    bundle.cards = [{"kind": "invented"}]
    draft = _draft(_brief())
    # The card has no fact list, and the brief names no fact, so sources hold.
    assert _check(draft, bundle)["Sources"] is True


def test_equal_companions_count_as_selected() -> None:
    brief = _brief(
        observed=[{"claim_key": "observed_note"}],
        inferred=[{"claim_key": "inferred_note"}],
    )
    cat = _cat(
        _claim("observed_note", ("inferred_note",)),
        _claim("inferred_note", ("observed_note",)),
    )
    # Each claim names the other, so the companion set equals the selection.
    assert _check(_draft(brief), _empty_bundle(), cat)["Limits stated"] is True


def test_missing_inferred_section_stays_inside_the_gate() -> None:
    brief = _brief(observed=[{"claim_key": "observed_note"}])
    del brief["inferred"]
    cat = _cat(_claim("observed_note", ("observed_note",)))
    result = _check(_draft(brief), _empty_bundle(), cat)
    assert result["Scope"] is True
    assert result["Limits stated"] is True


def test_layout_component_can_carry_a_companion() -> None:
    brief = _brief(
        observed=[{"claim_key": "invented_claim"}],
        layout=[{"component": "invented_panel", "props": {}}],
    )
    cat = _cat(_claim("invented_claim", ("invented_panel",)))
    assert _check(_draft(brief), _empty_bundle(), cat)["Limits stated"] is True


def test_missing_layout_adds_no_companion() -> None:
    brief = _brief(observed=[{"claim_key": "invented_claim"}])
    del brief["layout"]
    cat = _cat(_claim("invented_claim", ("invented_claim",)))
    assert _check(_draft(brief), _empty_bundle(), cat)["Limits stated"] is True


def test_missing_evidence_does_not_hide_a_later_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MissingFirst(set[str]):
        def __iter__(self) -> object:
            items = list(super().__iter__())
            head = [item for item in items if item == MISSING_ID]
            tail = [item for item in items if item != MISSING_ID]
            return iter([*head, *tail])

    def _ordered(value: object) -> set[str]:
        return _MissingFirst(referenced(value))

    # A set does not promise order, so the missing id is yielded before the fact.
    monkeypatch.setattr("eii_product.assistant.accounting.referenced", _ordered)
    bundle = _retarget(
        status="observed",
        provenance="synthetic",
        classes=["synthetic"],
        fact_id=OTHER_ID,
    )
    brief = _brief(
        observed=[{"claim_key": "invented_claim", "slots": {"reading": MISSING_ID}}]
    )
    assert _check(_draft(brief), bundle)["Scope"] is False


def test_user_input_on_an_observed_fact_is_an_assumption() -> None:
    bundle = invented_bundle()
    evidence = next(iter(bundle.facts.values()))
    raw = evidence.fact.model_dump()
    raw["evidence_status"] = "observed"
    raw["input_classes"] = ["public", "user_input"]
    evidence.fact = Fact.model_construct(**raw)
    draft = _draft(
        _brief(
            observed=[{"claim_key": "invented_claim", "slots": {"reading": FACT_ID}}]
        )
    )
    assert _check(draft, bundle)["Assumptions"] is False


def test_a_failed_assumption_stays_failed() -> None:
    bundle = _retarget(status="inferred", provenance="public", classes=["public"])
    bundle.inputs = {"activity": ACTIVITY}
    draft = _draft(
        _brief(
            observed=[{"claim_key": "invented_claim", "slots": {"reading": FACT_ID}}]
        ),
        assumptions=[FACT_ID],
    )
    # The activity is not listed, so a later listed fact must not clear that.
    assert _check(draft, bundle)["Assumptions"] is False


def test_public_scope_requires_only_public_classes() -> None:
    bundle = _retarget(
        status="inferred",
        provenance="public",
        classes=["public", "user_input"],
    )
    draft = _draft(
        _brief(
            observed=[{"claim_key": "invented_claim", "slots": {"reading": FACT_ID}}]
        ),
        assumptions=[FACT_ID],
    )
    assert _check(draft, bundle)["Scope"] is False


def test_inferred_strength_must_match_its_cap() -> None:
    bundle = _retarget(status="inferred", provenance="simulated", classes=["simulated"])
    brief = _brief(
        inferred=[
            {
                "claim_key": "invented_claim",
                "strength": "strong",
                "slots": {"reading": FACT_ID},
            }
        ]
    )
    draft = _draft(brief, assumptions=[FACT_ID])
    cat = _cat(_claim("invented_claim"))
    # Simulated input caps strong down to illustrative.
    assert _check(draft, bundle, cat)["Assumptions"] is False


def test_recorded_strength_is_the_one_that_is_capped() -> None:
    bundle = _retarget(status="inferred", provenance="simulated", classes=["simulated"])
    brief = _brief(
        inferred=[
            {
                "claim_key": "invented_claim",
                "strength": "illustrative",
                "slots": {"reading": FACT_ID},
            }
        ]
    )
    draft = _draft(brief, assumptions=[FACT_ID])
    cat = _cat(_claim("invented_claim"))
    assert _check(draft, bundle, cat)["Assumptions"] is True


def test_non_list_section_is_out_of_scope() -> None:
    brief = _brief(observed="invented")
    assert _check(_draft(brief), _empty_bundle())["Scope"] is False


def test_non_list_section_does_not_skip_later_assumptions() -> None:
    bundle = _retarget(status="inferred", provenance="simulated", classes=["simulated"])
    brief = _brief(
        observed="invented",
        inferred=[
            {
                "claim_key": "invented_claim",
                "strength": "strong",
                "slots": {"reading": FACT_ID},
            }
        ],
    )
    draft = _draft(brief, assumptions=[FACT_ID])
    cat = _cat(_claim("invented_claim"))
    assert _check(draft, bundle, cat)["Assumptions"] is False


def test_non_dict_item_is_out_of_scope() -> None:
    brief = _brief(observed=["invented"])
    assert _check(_draft(brief), _empty_bundle())["Scope"] is False


def test_non_dict_item_does_not_skip_a_later_assumption() -> None:
    bundle = _retarget(status="inferred", provenance="simulated", classes=["simulated"])
    brief = _brief(
        inferred=[
            "invented",
            {
                "claim_key": "invented_claim",
                "strength": "strong",
                "slots": {"reading": FACT_ID},
            },
        ]
    )
    draft = _draft(brief, assumptions=[FACT_ID])
    cat = _cat(_claim("invented_claim"))
    assert _check(draft, bundle, cat)["Assumptions"] is False


def test_unknown_claim_does_not_skip_a_later_assumption() -> None:
    bundle = _retarget(status="inferred", provenance="simulated", classes=["simulated"])
    brief = _brief(
        inferred=[
            {"claim_key": "invented_missing", "strength": "strong"},
            {
                "claim_key": "invented_claim",
                "strength": "strong",
                "slots": {"reading": FACT_ID},
            },
        ]
    )
    draft = _draft(brief, assumptions=[FACT_ID])
    cat = _cat(_claim("invented_claim"))
    assert _check(draft, bundle, cat)["Assumptions"] is False


def test_absent_claim_key_reads_the_empty_default() -> None:
    bundle = _retarget(status="inferred", provenance="public", classes=["public"])
    brief = _brief(observed=[{"slots": {"reading": FACT_ID}}])
    draft = _draft(brief, assumptions=[FACT_ID])
    # The empty key is a real claim, so the status mismatch is applied.
    assert _check(draft, bundle, _cat(_claim("")))["Assumptions"] is False


def test_absent_claim_key_does_not_select_the_marker_text() -> None:
    bundle = _retarget(status="inferred", provenance="public", classes=["public"])
    brief = _brief(observed=[{"slots": {"reading": FACT_ID}}])
    draft = _draft(brief, assumptions=[FACT_ID])
    assert _check(draft, bundle, _cat(_claim("XXXX")))["Assumptions"] is True


def test_claim_fact_status_must_match_its_section() -> None:
    bundle = _retarget(status="inferred", provenance="public", classes=["public"])
    brief = _brief(
        observed=[{"claim_key": "invented_claim", "slots": {"reading": FACT_ID}}]
    )
    draft = _draft(brief, assumptions=[FACT_ID])
    cat = _cat(_claim("invented_claim"))
    assert _check(draft, bundle, cat)["Assumptions"] is False


def test_a_public_fact_does_not_restore_scope() -> None:
    bundle = _retarget(status="observed", provenance="public", classes=["public"])
    bundle.playbook = "site_check"
    brief = _brief(
        observed=[{"claim_key": "invented_claim", "slots": {"reading": FACT_ID}}]
    )
    draft = _draft(brief, playbook="invented")
    cat = _cat(_claim("invented_claim", subject="national"))
    # The draft names another playbook, so one public fact must not pass scope.
    assert _check(draft, bundle, cat)["Scope"] is False


def test_unknown_question_is_out_of_scope() -> None:
    brief = _brief(next_questions=[{"question_key": "invented_missing", "slots": {}}])
    assert _check(_draft(brief), _empty_bundle())["Scope"] is False


def test_missing_questions_stay_in_scope() -> None:
    brief = _brief()
    del brief["next_questions"]
    assert _check(_draft(brief), _empty_bundle())["Scope"] is True


def test_absent_question_key_reads_the_empty_default() -> None:
    brief = _brief(next_questions=[{}])
    cat = _cat(questions=(_question(""),))
    assert _check(_draft(brief), _empty_bundle(), cat)["Scope"] is True


def test_absent_question_key_does_not_select_the_marker_text() -> None:
    brief = _brief(next_questions=[{}])
    cat = _cat(questions=(_question("XXXX"),))
    assert _check(_draft(brief), _empty_bundle(), cat)["Scope"] is False


def test_question_playbook_must_match_the_definition() -> None:
    brief = _brief(next_questions=[{"question_key": "invented_ask"}])
    cat = _cat(questions=(_question("invented_ask", "invented"),))
    assert _check(_draft(brief), _empty_bundle(), cat)["Scope"] is False
