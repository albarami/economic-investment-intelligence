"""Invented records, no fetched terms and no actual source confirmation."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from eii_custodian.publicdata.confirm_s2_t13 import (
    Confirmation,
    Tender,
    WeightConfirmation,
    completion_evidence,
    load_confirmation,
    tender_disposition,
)
from eii_custodian.publicdata.fetch.cadence import Cadence
from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry

RECORD = (
    Path(__file__).resolve().parents[1] / "publicdata/review/s2_t13_confirmation.yaml"
)


REGISTRY_FIXTURE_BASE = Entry(
    refetch=Cadence("none", "frequency_unconfirmed", ""),
    key="tenders_pub",
    source_id="tenders_pub",
    slug="",
    kind="terms_page",
    title_en="Invented tenders",
    publisher="Invented tender publisher",
    licence_id="invented-terms",
    licence_basis="portal_terms",
    decision_record="",
    fetch_host="invented.invalid",
    url="https://invented.invalid/tenders",
    terms_url="https://invented.invalid/terms",
    nightly_live_fetch=False,
    public_splits=(),
    commit_allowed=False,
    release_tables=("pub_tenders",),
    caveat_keys=(),
    columns=(),
    row_count_min=None,
    row_count_max=None,
    period_first="2026-01",
    period_last="2026-10",
    period_field="",
    reconciliation="none",
    skip_reason="",
    extension="json",
    landing_url="https://invented.invalid/",
    terms_words="Invented terms words",
    terms_read_on="2026-01-15",
    licence_url="",
)


def tender(**changes):
    return replace(
        Tender(
            outcome="terms_cover",
            source_id="tenders_pub",
            publisher="Invented tender publisher",
            page="https://invented.invalid/tenders",
            terms_url="https://invented.invalid/terms",
            retrieved_utc="2026-11-14T00:00:00Z",
            terms_sha256="b" * 64,
            page_sha256="a" * 64,
            licence_id="invented-terms",
            licence_basis="portal_terms",
            period_first="2026-01",
            period_last="2026-10",
            review_ref="invented-review",
            review_reason="Invented covering terms for the intended use",
            intended_use="Public tenders by buying entity and category",
            release_tables=("pub_tenders",),
            shown=True,
            search_note="",
            read_as_visitor=True,
            basis_of_use="portal_terms",
            decision_record="",
            terms_words="Invented covering permission.",
            terms_read_on="2026-11-14",
            go_live_permission_needed=False,
        ),
        **changes,
    )


def registry_record(t):
    return replace(
        REGISTRY_FIXTURE_BASE,
        key="tenders_pub",
        source_id="tenders_pub",
        slug="",
        kind="terms_page",
        publisher=t.publisher,
        url=t.page,
        terms_url=t.terms_url,
        licence_id=t.licence_id,
        licence_basis=t.basis_of_use,
        decision_record=t.decision_record,
        period_first=t.period_first,
        period_last=t.period_last,
        basis_note=t.review_reason,
        skip_reason="",
        release_tables=t.release_tables,
    )


def receipt(t, entry):
    return sidecar_for(
        entry,
        digest=t.page_sha256,
        nbytes=1,
        fetch_url=t.page,
        fetch_host="invented.invalid",
        retrieved_utc=t.retrieved_utc,
        publisher=t.publisher,
        source_modified="",
        row_count=None,
        terms_sha256=t.terms_sha256,
    )


def test_cover_requires_matching_registry_and_receipt():
    t = tender()
    entry = registry_record(t)
    assert tender_disposition(t, entry, receipt(t, entry)).shown is True
    evidence = completion_evidence(
        Confirmation(t, WeightConfirmation()), entry, receipt(t, entry)
    )
    assert evidence.tender == t
    assert evidence.weight.people_method == "area"


@pytest.mark.parametrize("which", ["registry", "receipt"])
def test_missing_registry_or_receipt_withholds(which):
    t = tender()
    e = registry_record(t)
    assert not tender_disposition(
        t,
        None if which == "registry" else e,
        None if which == "receipt" else receipt(t, e),
    ).shown


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": "wrong"},
        {"period_first": ""},
        {"period_last": ""},
        {"publisher": "wrong"},
        {"terms_url": "wrong"},
        {"licence_basis": "owner_decision"},
        {"licence_id": "wrong"},
        {"url": "wrong"},
        {"basis_note": ""},
        {"skip_reason": "terms_forbid"},
        {"release_tables": ()},
    ],
)
def test_registry_disagreements_withhold(changes):
    t = tender()
    e = registry_record(t)
    assert not tender_disposition(t, replace(e, **changes), receipt(t, e)).shown


@pytest.mark.parametrize(
    "field",
    [
        "source_id",
        "publisher",
        "terms_sha256",
        "retrieved_utc",
        "sha256",
        "licence_basis",
        "licence_id",
        "period_first",
        "period_last",
        "fetch_url",
        "release_tables",
    ],
)
def test_receipt_disagreements_withhold(field):
    t = tender()
    e = registry_record(t)
    s = receipt(t, e)
    s[field] = "wrong"
    assert not tender_disposition(t, e, s).shown


def test_switched_off_receipt_withholds():
    t = tender()
    e = registry_record(t)
    s = receipt(t, e)
    s["switched_off"] = True
    assert not tender_disposition(t, e, s).shown


def test_none_found_requires_search_evidence_and_registry_handoff():
    t = tender(
        outcome="none_found",
        source_id="",
        shown=False,
        release_tables=(),
        search_note="Invented search record: no source found",
    )
    e = replace(registry_record(t), skip_reason="none_found")
    assert not tender_disposition(t, e, None).shown
    assert (
        completion_evidence(Confirmation(t, WeightConfirmation()), e, None).tender == t
    )
    with pytest.raises(ValueError):
        completion_evidence(
            Confirmation(replace(t, search_note=""), WeightConfirmation()), e, None
        )
    with pytest.raises(ValueError):
        completion_evidence(Confirmation(t, WeightConfirmation()), None, None)


def test_committed_pending_is_incomplete():
    c = load_confirmation(RECORD)
    assert c.tender.outcome == "not_yet_recorded"
    assert c.weight == WeightConfirmation()
    assert tender_disposition(c.tender, None, None).status == "NO_DATA"
    with pytest.raises(ValueError, match="incomplete"):
        completion_evidence(c, None, None)


@pytest.mark.parametrize("missing", ["tender", "weight"])
def test_missing_confirmation_block_rejected(tmp_path, missing):
    data = json.loads(RECORD.read_text())
    del data[missing]
    p = tmp_path / "invented.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_confirmation(p)


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "unknown"},
        {"licence_basis": "owner_decision"},
        {"publisher": ""},
        {"terms_sha256": ""},
        {"terms_url": ""},
        {"retrieved_utc": ""},
        {"review_ref": ""},
        {"review_reason": ""},
        {"intended_use": ""},
        {"period_first": ""},
        {"period_last": ""},
        {"page_sha256": ""},
        {"page": ""},
        {"licence_id": ""},
        {"source_id": "wrong"},
        {"release_tables": ()},
        {"shown": False},
        {
            "outcome": "none_found",
            "shown": False,
            "source_id": "",
            "search_note": "invented",
        },
        {"outcome": "terms_absent"},
    ],
)
def test_invalid_tender_record_rejected(tmp_path, changes):
    data = asdict(Confirmation(tender(**changes), WeightConfirmation()))
    p = tmp_path / "invented.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_confirmation(p)


@pytest.mark.parametrize(
    "field,value",
    [
        ("grid_admitted", True),
        ("people_method", "worldpop_qat_2020"),
        ("agesex_is_weight", True),
        ("reason", ""),
    ],
)
def test_grid_stays_disabled_in_confirmation(tmp_path, field, value):
    data = json.loads(RECORD.read_text())
    data["weight"][field] = value
    p = tmp_path / "invented.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_confirmation(p)


@pytest.mark.parametrize("outcome", ["terms_do_not_cover", "terms_forbid"])
@pytest.mark.parametrize("field", ["terms_url", "terms_sha256"])
def test_adverse_terms_still_need_terms_evidence(outcome, field):
    t = tender(
        outcome=outcome,
        basis_of_use="owner_decision",
        decision_record="0026",
        go_live_permission_needed=True,
        **{field: ""},
    )
    with pytest.raises(ValueError, match="missing terms evidence"):
        completion_evidence(
            Confirmation(t, WeightConfirmation()),
            replace(registry_record(t), skip_reason=outcome),
            None,
        )


def test_pending_must_not_name_release_tables():
    c = load_confirmation(RECORD)
    with pytest.raises(ValueError, match="pending"):
        tender_disposition(
            replace(c.tender, release_tables=("pub_tenders",)), None, None
        )


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("tender", "publisher", 1),
        ("tender", "shown", "true"),
        ("tender", "release_tables", "pub_tenders"),
        ("tender", "release_tables", [1]),
        ("weight", "grid_admitted", 0),
        ("weight", "agesex_is_weight", 0),
        ("weight", "grid_source_id", "worldpop_qat_agesex"),
        ("weight", "agesex_source_id", "worldpop_qat_2020"),
    ],
)
def test_closed_confirmation_types(tmp_path, section, field, value):
    data = json.loads(RECORD.read_text())
    data[section][field] = value
    p = tmp_path / "invented.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_confirmation(p)


@pytest.mark.parametrize("section", [None, "tender", "weight"])
def test_unknown_fields_rejected(tmp_path, section):
    data = json.loads(RECORD.read_text())
    target = data if section is None else data[section]
    target["invented_extra"] = "invented"
    p = tmp_path / "invented.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_confirmation(p)


def test_nonobject_confirmation_rejected(tmp_path):
    p = tmp_path / "invented.json"
    p.write_text("[]")
    with pytest.raises(ValueError, match="confirmation block is not an object"):
        load_confirmation(p)


@pytest.mark.parametrize("basis", ["dataset", "provider_terms"])
def test_other_covering_bases(basis):
    t = tender(licence_basis=basis, basis_of_use=basis)
    e = registry_record(t)
    assert tender_disposition(t, e, receipt(t, e)).shown


@pytest.mark.parametrize("basis", ["", "none_stated"])
def test_unstated_covering_basis_refused(basis):
    with pytest.raises(ValueError, match="missing covering terms evidence"):
        tender_disposition(tender(licence_basis=basis, basis_of_use=basis), None, None)


def test_absent_terms_can_be_recorded_without_a_terms_page():
    t = tender(
        outcome="terms_absent",
        basis_of_use="owner_decision",
        decision_record="0026",
        go_live_permission_needed=True,
        terms_words="",
        terms_url="",
        terms_sha256="",
        licence_basis="none_stated",
    )
    e = registry_record(t)
    assert (
        completion_evidence(
            Confirmation(t, WeightConfirmation()), e, receipt(t, e)
        ).tender
        == t
    )


def test_covering_completion_refuses_missing_registry():
    with pytest.raises(ValueError, match="registry"):
        completion_evidence(Confirmation(tender(), WeightConfirmation()), None, None)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": "wrong"},
        {"skip_reason": "wrong"},
        {"release_tables": ("pub_tenders",)},
    ],
)
def test_absence_registry_handoff_must_match(changes):
    t = tender(
        outcome="none_found",
        source_id="",
        shown=False,
        release_tables=(),
        search_note="Invented search evidence",
    )
    e = replace(registry_record(t), skip_reason=t.outcome)
    with pytest.raises(ValueError, match="registry"):
        completion_evidence(
            Confirmation(t, WeightConfirmation()), replace(e, **changes), None
        )


def test_direct_completion_refuses_wrong_weight():
    with pytest.raises(ValueError, match="weight"):
        completion_evidence(
            Confirmation(tender(), WeightConfirmation(grid_admitted=True)), None, None
        )


def test_forbidding_registry_terms_do_not_block_completion():
    t = tender(
        outcome="terms_forbid",
        basis_of_use="owner_decision",
        decision_record="0026",
        go_live_permission_needed=True,
    )
    e = replace(registry_record(t), terms_words="Invented forbidding phrase")
    assert (
        completion_evidence(
            Confirmation(t, WeightConfirmation()), e, receipt(t, e)
        ).tender
        == t
    )


def test_watched_terms_with_covering_review_are_allowed():
    t = tender()
    e = replace(registry_record(t), terms_watch=True)
    assert tender_disposition(t, e, receipt(t, e)).shown


@pytest.mark.parametrize(
    "t,message",
    [
        (
            tender(outcome="approved", shown=False, release_tables=()),
            "unknown outcome or forbidden licence basis",
        ),
        (
            tender(
                outcome="terms_forbid",
                shown=False,
                release_tables=(),
                licence_basis="owner_decision",
            ),
            "unknown outcome or forbidden licence basis",
        ),
        (
            tender(
                outcome="none_found",
                shown=False,
                release_tables=(),
                search_note="Invented search record",
            ),
            "none_found requires search evidence",
        ),
        (
            tender(outcome="terms_forbid", shown=False),
            "shown does not match recorded visitor source",
        ),
    ],
)
def test_guards_refuse_for_the_named_reason(t, message):
    e = replace(registry_record(t), skip_reason=t.outcome, release_tables=())
    with pytest.raises(ValueError, match=message):
        completion_evidence(Confirmation(t, WeightConfirmation()), e, None)


def test_tender_registry_fixture_is_wholly_invented():
    from urllib.parse import urlsplit

    e = registry_record(tender())
    assert e.title_en == "Invented tenders"
    assert e.fetch_host.endswith(".invalid")
    for address in (e.url, e.terms_url, e.landing_url, e.licence_url):
        if address:
            assert urlsplit(address).hostname.endswith(".invalid")
    assert (e.row_count_min, e.row_count_max) == (None, None)


def recorded_data(outcome="terms_forbid"):
    data = asdict(Confirmation(tender(), WeightConfirmation()))
    data["tender"].update(
        outcome=outcome,
        read_as_visitor=True,
        basis_of_use="portal_terms" if outcome == "terms_cover" else "owner_decision",
        decision_record="" if outcome == "terms_cover" else "0026",
        terms_words="Invented publisher: prior permission required.",
        terms_read_on="2026-11-14",
        go_live_permission_needed=outcome != "terms_cover",
    )
    return data


def read_invented(tmp_path, data):
    p = tmp_path / "invented.json"
    p.write_text(json.dumps(data))
    return load_confirmation(p)


@pytest.mark.parametrize(
    "outcome", ["terms_cover", "terms_absent", "terms_do_not_cover", "terms_forbid"]
)
def test_visitor_source_shown_for_every_terms_reading(tmp_path, outcome):
    c = read_invented(tmp_path, recorded_data(outcome))
    e = replace(
        registry_record(c.tender),
        licence_basis=c.tender.basis_of_use,
        decision_record=c.tender.decision_record,
        terms_words="Invented restriction",
    )
    assert c.tender.shown is True
    assert tender_disposition(c.tender, e, receipt(c.tender, e)).shown
    assert completion_evidence(c, e, receipt(c.tender, e)) == c


@pytest.mark.parametrize(
    "field",
    [
        "read_as_visitor",
        "basis_of_use",
        "decision_record",
        "terms_words",
        "terms_read_on",
        "go_live_permission_needed",
    ],
)
def test_new_field_missing_refused_by_name(tmp_path, field):
    data = recorded_data()
    del data["tender"][field]
    with pytest.raises(ValueError, match=field):
        read_invented(tmp_path, data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("read_as_visitor", False),
        ("read_as_visitor", 1),
        ("read_as_visitor", "true"),
        ("basis_of_use", "portal_terms"),
        ("basis_of_use", ""),
        ("decision_record", "0023"),
        ("decision_record", ""),
        ("terms_words", " "),
        ("terms_words", None),
        ("terms_read_on", "2026-02-30"),
        ("terms_read_on", ""),
        ("terms_read_on", "2026-W46-6"),
        ("go_live_permission_needed", False),
        ("go_live_permission_needed", 1),
        ("go_live_permission_needed", "true"),
    ],
)
def test_new_field_invalid_refused_by_name(tmp_path, field, value):
    data = recorded_data()
    data["tender"][field] = value
    with pytest.raises(ValueError, match=field):
        read_invented(tmp_path, data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("basis_of_use", "owner_decision"),
        ("decision_record", "0026"),
        ("go_live_permission_needed", True),
    ],
)
def test_cover_keeps_licence_basis_and_no_permission(tmp_path, field, value):
    data = recorded_data("terms_cover")
    data["tender"][field] = value
    with pytest.raises(ValueError, match=field):
        read_invented(tmp_path, data)


@pytest.mark.parametrize("target", ["registry", "receipt"])
def test_owner_decision_must_match_handoff(tmp_path, target):
    c = read_invented(tmp_path, recorded_data())
    e = registry_record(c.tender)
    r = receipt(c.tender, e)
    if target == "registry":
        e = replace(e, decision_record="0023")
    else:
        r["decision_record"] = "0023"
    assert not tender_disposition(c.tender, e, r).shown


def test_source_confirmation_does_not_invent_period(tmp_path):
    data = recorded_data()
    data["tender"].update(period_first="", period_last="")
    c = read_invented(tmp_path, data)
    e = registry_record(c.tender)
    assert completion_evidence(c, e, receipt(c.tender, e)) == c


@pytest.mark.parametrize(
    "outcome", ["terms_cover", "terms_do_not_cover", "terms_forbid"]
)
def test_recorded_terms_need_words_for_each_reading(tmp_path, outcome):
    data = recorded_data(outcome)
    data["tender"]["terms_words"] = ""
    with pytest.raises(ValueError, match="terms_words"):
        read_invented(tmp_path, data)


@pytest.mark.parametrize(
    "outcome", ["terms_cover", "terms_absent", "terms_do_not_cover", "terms_forbid"]
)
def test_recorded_source_requires_release_table_by_name(tmp_path, outcome):
    data = recorded_data(outcome)
    data["tender"]["release_tables"] = []
    with pytest.raises(ValueError, match="release_tables"):
        read_invented(tmp_path, data)


def test_direct_visitor_flag_cannot_be_numeric():
    with pytest.raises(ValueError, match="read_as_visitor"):
        tender_disposition(tender(read_as_visitor=1), None, None)


@pytest.mark.parametrize(
    "field,value",
    [("shown", "true"), ("release_tables", "pub_tenders"), ("release_tables", [1])],
)
def test_flags_and_tables_refused_by_named_guard(tmp_path, field, value):
    data = recorded_data()
    data["tender"][field] = value
    with pytest.raises(ValueError, match="invalid tender flags or tables"):
        read_invented(tmp_path, data)


def test_pending_stays_hidden_even_with_matching_fetch_metadata():
    t = load_confirmation(RECORD).tender
    e = registry_record(t)
    assert not tender_disposition(t, e, receipt(t, e)).shown


@pytest.mark.parametrize("field", ["read_as_visitor", "go_live_permission_needed"])
def test_loader_flags_refused_as_non_booleans(tmp_path, field):
    data = recorded_data()
    data["tender"][field] = 1
    with pytest.raises(ValueError, match=f"{field} is not a boolean"):
        read_invented(tmp_path, data)
