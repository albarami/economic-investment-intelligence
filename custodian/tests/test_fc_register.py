"""Invented company cards, state-bound chains and projection-boundary plants."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_s2_t29_live_shapes import declaration, entry

from eii_custodian.publicdata.fc_register.constants import COLUMNS, SHAPE, URL
from eii_custodian.publicdata.fc_register.parse import fragment, project
from eii_custodian.publicdata.fetch.page_records import PageError, fetch_page
from eii_custodian.publicdata.fetch.transport import Response, TransportFault

STAMP = "2026-11-19T01:00:00Z"
FIXTURE = Path(__file__).parent / "fixtures/fc_register/page.html"


def page(n, terminal=False):
    def link(pager):
        if terminal:
            return '<a class="aspNetDisabled">&gt;</a>'
        return (
            "<a href=\"javascript:__doPostBack('"
            + pager
            + "$ctl02$ctl00','')\">&gt;</a>"
        )

    return (
        FIXTURE.read_text()
        .format(
            page=n, next_top=link("PrCompanyPager1"), next_bottom=link("PrCompanyPager")
        )
        .encode()
    )


def review():
    result = declaration("fc_company_cards", dict(SHAPE), [list(c) for c in COLUMNS])
    result.update(url=URL, reviewed_urls=[URL], pins=[{"host": "eservices.qfc.qa"}])
    return result


def row():
    return entry(review(), "fc_register")


@pytest.fixture(autouse=True)
def invented_pin_context(monkeypatch):
    from custodian.tests.test_fc_register_capture import pin

    monkeypatch.setattr(
        "eii_custodian.publicdata.fetch.page_acquire.load_pin", lambda *a: pin()
    )
    # TLS itself is exercised with an invented DER in the transport tests.
    monkeypatch.setattr(
        "eii_custodian.publicdata.fetch.page_acquire.page_context", lambda *a: None
    )
    monkeypatch.setattr(
        "eii_custodian.publicdata.fc_register.acquire.page_context", lambda *a: None
    )


def no_private_outputs(folder):
    for path in folder.rglob("*"):
        if path.is_file():
            body = path.read_bytes()
            for sentinel in (
                b"SYN-IN-CARD",
                b"SYN-OUTSIDE-PERSON",
                b"SYN-state-",
                b"SYN-event-",
                b"__VIEWSTATE",
            ):
                assert sentinel not in body, path.name


def live(folder, pages, ent=None, dec=None):
    sent = []

    def send(request):
        sent.append(request)
        value = pages[len(sent) - 1]
        if isinstance(value, Exception):
            raise value
        return Response(str(request), value, ())

    result = fetch_page(
        ent or row(),
        send,
        folder,
        lambda: STAMP,
        lambda _: None,
        declaration=dec or review(),
    )
    return result, sent


def test_full_capture_set_beside_live_prefix_refuses(tmp_path):
    from custodian.tests.test_fc_register_capture import prepared, replay

    p, bodies = prepared(tmp_path)
    sent = []

    def send(request):
        sent.append(request)
        if len(sent) == 1:
            return Response(str(request), bodies[0], ())
        raise TransportFault("unreachable", URL)

    with pytest.raises(PageError, match="paging_incomplete"):
        replay(tmp_path, p, send)
    no_private_outputs(tmp_path)


def test_live_same_target_empty_argument_advances_and_projects(tmp_path):
    result, sent = live(tmp_path, [page(1), page(2), page(3, True)])
    assert len(sent) == 3
    assert (
        sent[1].target == sent[2].target and sent[1].argument == sent[2].argument == ""
    )
    assert sent[1].fields != sent[2].fields
    value = json.loads(result.body)
    assert len(value["rows"]) == 3
    assert all(i["representation"] == "fc_company_pane@v1" for i in value["inputs"])
    no_private_outputs(tmp_path)


@pytest.mark.parametrize(
    "plant",
    ["replay", "duplicate", "missing", "reordered", "repeated_page", "non_progress"],
)
def test_live_chain_plants_refuse_without_partial_publication(tmp_path, plant):
    bodies = [page(1), page(2), page(3, True)]
    if plant in {"replay", "duplicate", "non_progress"}:
        bodies[1] = bodies[0]
    elif plant == "missing":
        bodies.pop(1)
    elif plant == "reordered":
        bodies[1], bodies[2] = bodies[2], bodies[1]
    else:
        bodies[1] = page(1).replace(b"SYN-state-1", b"SYN-state-OTHER")
    with pytest.raises(PageError, match="paging_incomplete"):
        live(tmp_path, bodies)
    assert not (tmp_path / "fc_register/index.json").exists()
    no_private_outputs(tmp_path)


@pytest.mark.parametrize(
    "plant", ["detail", "field", "nested", "missing_field", "pager_disagreement"]
)
def test_shape_and_request_plants(tmp_path, plant):
    body = page(1)
    if plant == "detail":
        body = body.replace(
            b"PrCompanyPager1$ctl02$ctl00", b"CompanyLists$ctl00$detail"
        )
    elif plant == "field":
        body = body.replace(b"__VIEWSTATE", b"__SYN_UNDELIVERED")
    elif plant == "nested":
        body = body.replace(
            b"SYN Glass Orchard 1", b"SYN Glass <span>SYN-IN-CARD</span> Orchard"
        )
    elif plant == "missing_field":
        body = body.replace(b"pr-result-meta", b"SYN-absent")
    else:
        body = body.replace(
            b'id="PrCompanyPager"><span>1', b'id="PrCompanyPager"><span>2'
        )
    reason = "paging_incomplete" if plant == "pager_disagreement" else "schema_missing"
    with pytest.raises(PageError, match=reason):
        live(tmp_path, [body])
    no_private_outputs(tmp_path)


def test_canonical_fragment_rejects_extra_markup_and_missing_progress():
    projected = project(page(1), SHAPE)
    value = json.loads(projected.body)
    assert value["progress"] == {"shown_page": 1, "continuation": "next"}
    assert fragment(projected.body)["rows"][0]["company_name"] == "SYN Glass Orchard 1"
    for key in ("progress", "rows"):
        bad = dict(value)
        del bad[key]
        with pytest.raises(ValueError, match=r"schema_missing|paging_incomplete"):
            fragment(json.dumps(bad).encode())
    with pytest.raises(ValueError, match="schema_missing"):
        fragment(projected.body + b" ")


@pytest.mark.parametrize("field", ["terms_words", "terms_read_on", "licence_basis"])
def test_pending_terms_are_records_never_a_gate(tmp_path, field):
    result, _ = live(tmp_path, [page(1, True)], replace(row(), **{field: ""}))
    assert field in result.sidecar
    assert result.sidecar["row_count"] == 1
    no_private_outputs(tmp_path)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("publisher", "", "receipt_missing"),
        ("commit_allowed", True, "commit_refused"),
        ("licence_basis", "SYN-unknown", "receipt_missing"),
    ],
)
def test_entry_refusals(tmp_path, field, value, reason):
    with pytest.raises(PageError, match=reason):
        live(tmp_path, [page(1, True)], replace(row(), **{field: value}))


def test_declared_person_column_refused(tmp_path):
    dec = review()
    dec["columns"].append(["director_name", "string"])
    ent = replace(row(), columns=tuple(tuple(c) for c in dec["columns"]))
    with pytest.raises(PageError, match="schema_missing"):
        live(tmp_path, [page(1, True)], ent, dec)


def test_failed_mid_chain_records_date_and_no_partial_inventory(tmp_path):
    with pytest.raises(PageError, match=r"access_failed|unreachable"):
        live(tmp_path, [page(1), TransportFault("unreachable", URL)])
    assert list((tmp_path / "fc_register/failures").rglob("*.json"))
    assert not list((tmp_path / "fc_register").glob("snapshots/*"))
    no_private_outputs(tmp_path)


def test_postback_must_equal_delivered_state_before_send():
    from eii_custodian.publicdata.fc_register.constants import TARGETS
    from eii_custodian.publicdata.fetch.page_requests import (
        PagePostback,
        check_target,
        delivered_state,
        page_requests,
    )

    fields = project(page(1), SHAPE).fields
    with page_requests((URL,), {}), delivered_state(fields, TARGETS[0]):
        check_target(PagePostback(URL, fields, TARGETS[0]))
        plants = [
            PagePostback(URL, {**fields, "__SYN_EXTRA": "SYN-value"}, TARGETS[0]),
            PagePostback(URL, {**fields, "__VIEWSTATE": "SYN-changed"}, TARGETS[0]),
            PagePostback(URL, fields, "CompanyLists$ctl00$detail"),
            PagePostback(URL, fields, TARGETS[0], "SYN-argument"),
        ]
        for request in plants:
            with pytest.raises(TransportFault, match="schema_missing"):
                check_target(request)
    with pytest.raises(TransportFault, match="schema_missing"):
        check_target(PagePostback(URL, fields, TARGETS[0]))


@pytest.mark.parametrize(
    "address",
    [
        "https://example.invalid/SYN",
        "https://eservices.qfc.qa/View/SYN",
        URL + "?token=SYN",
    ],
)
def test_frame_and_path_refusals(address):
    from eii_custodian.publicdata.fetch.page_requests import check_target, page_requests

    with page_requests((URL,), {}), pytest.raises(TransportFault, match="blocked_host"):
        check_target(address)


def test_committed_declaration_matches_kind_and_retains_activation_hold():
    from eii_custodian.publicdata.fetch.page_acquire import validate_entry
    from eii_custodian.publicdata.fetch.page_records import load_declaration
    from eii_custodian.publicdata.fetch.registry import load_registry

    ent = next(r for r in load_registry() if r.source_id == "fc_register")
    dec = load_declaration("fc_register")
    validate_entry(ent, dec)
    assert (
        not ent.nightly_live_fetch and not ent.commit_allowed and not ent.release_tables
    )
    assert ent.skip_reason and dec["hold"] and dec["max_bytes"] is None
    assert dec["shape"] == SHAPE


@pytest.mark.parametrize(
    "field,marker",
    [
        ("terms_words", "terms to be read"),
        ("terms_read_on", "pending"),
        ("licence_basis", "pending"),
    ],
)
def test_loaded_missing_terms_are_pending_and_stay_in_use(tmp_path, field, marker):
    from custodian.tests.test_publicdata_registry import _mutated, _row

    from eii_custodian.publicdata.completeness import in_use
    from eii_custodian.publicdata.fetch.registry import load_registry

    def omit(document):
        target = _row(document, "fc_register")
        del target[field]
        target["skip_reason"] = ""

    ent = next(
        r
        for r in load_registry(_mutated(tmp_path, "SYN-registry.yaml", omit))
        if r.source_id == "fc_register"
    )
    # Use a bound invented declaration; do not open the configured terms page.
    ent = replace(ent, terms_url="")
    result, _ = live(tmp_path, [page(1, True)], ent)
    assert result.sidecar[field] == marker
    assert in_use(ent, {ent.key: result.sidecar})
    assert not ent.commit_allowed


def test_failed_refresh_preserves_previous_complete_snapshot(tmp_path):
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    previous, _ = live(tmp_path, [page(1, True)])
    with pytest.raises(PageError, match="paging_incomplete"):
        live(tmp_path, [page(1), page(1)])
    assert (
        read_snapshot(tmp_path / "fc_register", previous.sha256).body == previous.body
    )
    no_private_outputs(tmp_path)


def test_terminal_pager_without_next_anchor_is_terminal(tmp_path):
    body = page(1, True).replace(b'<a class="aspNetDisabled">&gt;</a>', b"")
    result, sent = live(tmp_path, [body])
    assert len(sent) == 1 and len(json.loads(result.body)["rows"]) == 1
    no_private_outputs(tmp_path)
