"""Deciding invented plants for S2-T36 guard-deletion evidence."""

import json
import ssl
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from custodian.tests.test_fc_register import STAMP, page, review, row
from custodian.tests.test_fc_register_capture import pin

from eii_custodian.publicdata.fc_register import acquire, capture, names
from eii_custodian.publicdata.fc_register.constants import (
    SHAPE,
    STATE_FIELDS,
    TARGETS,
    URL,
)
from eii_custodian.publicdata.fc_register.parse import canonical, fragment, project
from eii_custodian.publicdata.fetch import certificate_pins as certs
from eii_custodian.publicdata.fetch import page_requests as requests
from eii_custodian.publicdata.fetch.page_html import ShapeError
from eii_custodian.publicdata.fetch.page_identity import RequestIdentity
from eii_custodian.publicdata.fetch.page_records import PageError
from eii_custodian.publicdata.fetch.receipts import sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.transport import Response, TransportFault


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("extra_top", "schema_missing"),
        ("projection", "schema_missing"),
        ("progress", "paging_incomplete"),
        ("empty_rows", "schema_missing"),
        ("empty_name", "schema_missing"),
        ("extra_row", "schema_missing"),
        ("non_string", "schema_missing"),
    ],
)
def test_fragment_guards_have_canonical_plants(plant, reason):
    value = fragment(project(page(1, True), SHAPE).body)
    if plant == "extra_top":
        value["SYN-extra"] = "SYN-value"
    elif plant == "projection":
        value["projection"] = "SYN-other-projection"
    elif plant == "progress":
        value["progress"]["continuation"] = "SYN-other"
    elif plant == "empty_rows":
        value["rows"] = []
    elif plant == "empty_name":
        value["rows"][0]["company_name"] = " "
    elif plant == "extra_row":
        value["rows"][0]["SYN-extra"] = "SYN-value"
    else:
        value["rows"][0]["metadata"] = None
    with pytest.raises(ShapeError, match=reason):
        fragment(canonical(value))


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("shape", "schema_missing"),
        ("label", "schema_missing"),
        ("current", "paging_incomplete"),
        ("duplicate_next", "paging_incomplete"),
        ("later_link", "paging_incomplete"),
        ("form_method", "schema_missing"),
        ("duplicate_hidden", "schema_missing"),
        ("missing_hidden", "schema_missing"),
        ("nonempty_event", "schema_missing"),
    ],
)
def test_project_guards_have_otherwise_valid_pages(plant, reason):
    body = page(1, True)
    shape = deepcopy(SHAPE)
    if plant == "shape":
        shape["SYN-extra"] = "SYN-value"
    elif plant == "label":
        body = body.replace(b"Number<", b"SYN-other-label<")
    elif plant == "current":
        body = body.replace(b"<span>1</span>", b"<span>01</span>")
    elif plant == "duplicate_next":
        node = b'<a class="aspNetDisabled">&gt;</a>'
        body = body.replace(node, node + node)
    elif plant == "later_link":
        body = body.replace(
            b"<span>1</span>", b'<span>1</span><a href="SYN-later">2</a>'
        )
    elif plant == "form_method":
        body = body.replace(b'method="post"', b'method="get"')
    elif plant == "duplicate_hidden":
        body = body.replace(
            b"</form>",
            b'<input type="hidden" name="__VIEWSTATE" value="SYN-other"></form>',
        )
    elif plant == "missing_hidden":
        body = body.replace(b'<input type="hidden" name="__EVENTTARGET" value="">', b"")
    else:
        body = body.replace(
            b'name="__EVENTTARGET" value=""', b'name="__EVENTTARGET" value="SYN-other"'
        )
    with pytest.raises(ShapeError, match=reason):
        project(body, shape)


def test_checked_response_checks_allowlist_without_request_frame():
    assert not requests.active()
    with pytest.raises(ShapeError, match="blocked_host"):
        acquire.checked_response(
            Response("https://example.invalid/SYN", page(1, True), ()), 65536
        )


@pytest.mark.parametrize("producer", [False, True])
def test_unavailable_page_cannot_load_capture_without_permission_or_pin(
    tmp_path, monkeypatch, producer
):
    monkeypatch.setattr(acquire, "page_context", lambda *a: None)
    loader = Mock(return_value=None)
    monkeypatch.setattr(acquire, "load_capture", loader)

    def unavailable(_):
        raise TransportFault("unreachable", "")

    with pytest.raises(
        ShapeError, match="unreachable" if producer else "certificate_chain_incomplete"
    ):
        acquire.pages(
            unavailable,
            tmp_path,
            {},
            SHAPE,
            65536,
            lambda _: None,
            captures=not producer,
        )
    loader.assert_not_called()


@pytest.mark.parametrize("plant", ["hold", "bound", "tool"])
def test_producer_missing_evidence_refuses_before_visitor(tmp_path, plant):
    dec = review()
    tool = "SYN-tool"
    if plant == "hold":
        dec["hold"] = "schema_evidence_pending"
    elif plant == "bound":
        dec["max_bytes"] = None
    else:
        tool = " "
    visitor = Mock(return_value=Response(URL, page(1, True), ()))
    with pytest.raises(certs.PinError, match="capture_evidence_missing"):
        capture.produce(
            tmp_path,
            visitor,
            pin(),
            dec,
            tool=tool,
            clock=lambda: STAMP,
            sleep=lambda _: None,
        )
    visitor.assert_not_called()
    assert not list(tmp_path.rglob("fragment-*.json"))


def test_producer_overwrite_refuses_before_any_partial_output(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire, "page_context", lambda *a: None)
    folder = tmp_path / "intake/fc_register"
    folder.mkdir(parents=True)
    # Only the last planned file exists: an exclusive-open failure alone would
    # leave a preceding fragment behind and is not the required pre-write guard.
    existing = folder / "capture-1.json"
    existing.write_bytes(b"SYN-existing")
    caught = None
    try:
        capture.produce(
            tmp_path,
            lambda _: Response(URL, page(1, True), ()),
            pin(),
            review(),
            tool="SYN-tool",
            clock=lambda: STAMP,
            sleep=lambda _: None,
        )
    except Exception as exc:
        caught = exc
    assert isinstance(caught, certs.PinError), "overwrite must refuse before any write"
    assert str(caught) == "capture_overwrite_refused"
    assert existing.read_bytes() == b"SYN-existing"
    assert not (folder / "fragment-1.json").exists()


@pytest.mark.parametrize(
    "plant", ["target", "fields", "missing_delivered", "url", "argument"]
)
def test_postback_closed_contract_with_matching_delivered_state(plant):
    fields = dict(project(page(1), SHAPE).fields)
    target, address, argument = TARGETS[0], URL, ""
    if plant == "target":
        target = "SYN-other-control"
    elif plant == "fields":
        fields.pop(STATE_FIELDS[0])
    elif plant == "url":
        address = URL + "/SYN-other"
    elif plant == "argument":
        argument = "SYN-other"
    with requests.page_requests((address,), {}):
        if plant == "missing_delivered":
            with pytest.raises((TransportFault, TypeError)) as caught:
                requests.check_target(
                    requests.PagePostback(address, fields, target, argument)
                )
            assert isinstance(caught.value, TransportFault)
            assert caught.value.kind == "schema_missing"
        else:
            with (
                requests.delivered_state(fields, target),
                pytest.raises(TransportFault, match="schema_missing"),
            ):
                requests.check_target(
                    requests.PagePostback(address, fields, target, argument)
                )


def test_frame_membership_is_independent_of_register_exact_path():
    with (
        requests.page_requests((), {}),
        pytest.raises(TransportFault, match="blocked_host"),
    ):
        requests.check_target(URL)


def test_page_context_rejects_unverified_supplied_context_with_valid_pin():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    p = pin()
    with (
        requests.page_requests((URL,), {p.host: p}),
        pytest.raises(certs.PinError, match="tls_verification_disabled"),
    ):
        requests.page_context(p.host, context)


def inventory_inputs(monkeypatch):
    """Verified-read stand-ins isolate the inventory reader's own revalidation.

    These are invented in-memory objects, never malformed on-disk receipts or
    patched validation predicates. The reader must independently bind them.
    """
    ent = row()
    inputs, raw = [], {}
    previous = None
    rows = []
    for ordinal in (1, 2):
        body = project(page(ordinal, ordinal == 2), SHAPE).body
        digest = sha256_hex(page(ordinal, ordinal == 2))
        identity = RequestIdentity(
            "GET" if ordinal == 1 else "POST",
            URL,
            None if ordinal == 1 else TARGETS[0],
            None if ordinal == 1 else "",
            ordinal,
            previous,
        )
        item = {
            "key": "SYN-input-" + str(ordinal),
            "identity": sha256_hex(body),
            "representation": "fc_company_pane@v1",
            "upstream_sha256": digest,
            "request_identity": identity.data(),
            "upstream_evidence": "computed-full-response",
            "capture": {},
        }
        # receipt_valid reads these fields; keep its implementation real.
        side = sidecar_for(
            ent,
            digest=sha256_hex(body),
            nbytes=len(body),
            fetch_url=URL,
            fetch_host=ent.fetch_host,
            retrieved_utc=STAMP,
            publisher=ent.publisher,
            source_modified="",
            row_count=1,
            terms_sha256="",
        )
        side.update(
            {
                key: value
                for key, value in item.items()
                if key not in {"key", "identity"}
            }
        )
        inputs.append(item)
        raw[item["identity"]] = SimpleNamespace(body=body, sidecar=side)
        rows.extend(fragment(body)["rows"])
        previous = digest
    payload = {
        "version": 2,
        "inputs": inputs,
        "rows": rows,
        "retrieved_utc": STAMP,
        "method": "SYN-invented",
    }
    selected = SimpleNamespace(
        body=canonical(payload),
        sha256="a" * 64,
        sidecar=deepcopy(next(iter(raw.values())).sidecar),
    )
    monkeypatch.setattr(names, "selected_page", lambda *a: selected)
    monkeypatch.setattr(names, "read_snapshot", lambda folder, identity: raw[identity])
    return ent, payload, raw, selected


@pytest.mark.parametrize(
    "plant",
    [
        "entry",
        "selected_receipt",
        "version",
        "after_terminal",
        "input_receipt",
        "sidecar_binding",
        "representation",
        "digest",
        "identity",
        "repeated_hash",
        "progress",
        "unterminated",
        "rows",
    ],
)
def test_inventory_independent_revalidation(tmp_path, monkeypatch, plant):
    ent, payload, raw, selected = inventory_inputs(monkeypatch)
    # A control first proves these stand-ins are a usable, complete chain.
    assert names.contribution(tmp_path, ent).names == (
        "SYN Glass Orchard 1",
        "SYN بستان زجاج 1",
        "SYN Glass Orchard 2",
        "SYN بستان زجاج 2",
    )
    item = payload["inputs"][0]
    first = raw[item["identity"]]
    last_item = payload["inputs"][1]
    last = raw[last_item["identity"]]
    if plant == "entry":
        ent = replace(ent, url=URL + "/SYN-other")
    elif plant == "selected_receipt":
        selected.sidecar["publisher"] = ""
    elif plant == "version":
        payload["version"] = 1
    elif plant == "after_terminal":
        value = fragment(first.body)
        value["progress"]["continuation"] = "terminal"
        first.body = canonical(value)
    elif plant == "input_receipt":
        first.sidecar["publisher"] = ""
    elif plant == "sidecar_binding":
        first.sidecar["upstream_evidence"] = "SYN-other"
    elif plant in {"representation", "digest"}:
        key = "representation" if plant == "representation" else "upstream_sha256"
        last_item[key] = last.sidecar[key] = "SYN-other"
    elif plant == "identity":
        item["request_identity"]["url"] = "https://example.invalid/SYN"
    elif plant == "repeated_hash":
        last_item["upstream_sha256"] = last.sidecar["upstream_sha256"] = item[
            "upstream_sha256"
        ]
    elif plant == "progress":
        value = fragment(last.body)
        value["progress"]["shown_page"] = 3
        last.body = canonical(value)
    elif plant == "unterminated":
        value = fragment(last.body)
        value["progress"]["continuation"] = "next"
        last.body = canonical(value)
    else:
        payload["rows"] = []
    selected.body = canonical(payload)
    with pytest.raises(PageError, match="receipt_missing"):
        names.contribution(tmp_path, ent)


def direct_capture():
    body = project(page(1, True), SHAPE).body
    identity = RequestIdentity("GET", URL, None, None, 1, None)
    result = certs.Capture(
        body,
        URL,
        URL,
        (),
        "SYN-tool",
        STAMP,
        sha256_hex(body),
        pin(),
        True,
        "visitor",
        identity,
        "fc_company_pane@v1",
        sha256_hex(page(1, True)),
    )
    return result, identity


@pytest.mark.parametrize("plant", ["projection", "digest", "identity", "progress"])
def test_direct_capture_admission_revalidates_projection_evidence(plant):
    value, identity = direct_capture()
    if plant == "projection":
        value = replace(value, projection="SYN-other")
    elif plant == "digest":
        value = replace(value, upstream_sha256="SYN-other")
    elif plant == "identity":
        value = replace(value, identity=replace(identity, url=URL + "/SYN-other"))
    else:
        body = fragment(value.body)
        body["progress"]["shown_page"] = 2
        value = replace(value, body=canonical(body), sha256=sha256_hex(canonical(body)))
    reason = {
        "projection": "capture_evidence_missing",
        "digest": "capture_evidence_missing",
        "identity": "capture_identity_mismatch",
        "progress": "capture_progress_invalid",
    }[plant]
    with pytest.raises(certs.PinError, match=reason):
        certs.admit_capture(value, URL, identity=identity)


def test_paged_capture_requires_identity_even_without_an_intake(tmp_path):
    with pytest.raises(certs.PinError, match="capture_identity_mismatch"):
        certs.load_capture(tmp_path, "fc_register", pin())


def test_capture_filename_is_a_closed_ordinal_contract(tmp_path):
    folder = tmp_path / "intake/fc_register"
    folder.mkdir(parents=True)
    (folder / "capture-SYN.json").write_bytes(b"{}")
    caught = None
    try:
        certs.capture_files(tmp_path, "fc_register")
    except Exception as exc:
        caught = exc
    assert isinstance(caught, certs.PinError), (
        "ordinal locator must return a closed refusal"
    )
    assert str(caught) == "capture_identity_mismatch"


@pytest.mark.parametrize("plant", ["nested", "pager_disagreement"])
def test_projection_refusals_do_not_depend_on_a_later_request(plant):
    body = page(1, True)
    if plant == "nested":
        body = body.replace(b"SYN metadata", b"SYN <span>SYN-hidden</span> metadata")
    else:
        body = body.replace(
            b'id="PrCompanyPager"><span>1', b'id="PrCompanyPager"><span>2'
        )
    with pytest.raises(
        ShapeError, match="schema_missing" if plant == "nested" else "paging_incomplete"
    ):
        project(body, SHAPE)


@pytest.mark.parametrize(
    "reason,status,allowed",
    [
        ("unreachable", None, True),
        ("refusal_body", None, True),
        ("http", 403, True),
        ("http", 429, True),
        ("http", 503, True),
        ("http", 404, False),
        ("http", 500, False),
        ("credentials", None, False),
        ("metadata_bytes", None, False),
        ("blocked_host", None, False),
        ("schema_missing", None, False),
    ],
)
def test_capture_eligibility_is_a_closed_decision(reason, status, allowed):
    assert acquire.eligible(reason, status) is allowed


@pytest.mark.parametrize(
    "body,reason",
    [
        (b"SYN sign in", "credentials"),
        (b"SYN sign-in", "credentials"),
        (b"SYN robot check", "refusal_body"),
        (b"SYN paywall", "refusal_body"),
        (b"SYN ordinary", None),
    ],
)
def test_obstacle_classification_is_independent_of_parser(body, reason):
    assert acquire.obstacle(body) == reason


def test_checked_response_raises_its_classified_obstacle():
    p = pin()
    with (
        requests.page_requests((URL,), {p.host: p}),
        pytest.raises(ShapeError, match="credentials"),
    ):
        acquire.checked_response(
            Response(URL, page(1, True) + b"<!--SYN sign in-->", ()), 65536
        )


def test_missing_capture_has_a_closed_error_before_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire, "page_context", lambda *a: None)
    monkeypatch.setattr(acquire, "load_capture", lambda *a, **k: None)
    caught = None
    try:
        acquire.pages(
            lambda _: (_ for _ in ()).throw(TransportFault("unreachable", "")),
            tmp_path,
            {pin().host: pin()},
            SHAPE,
            65536,
            lambda _: None,
        )
    except Exception as exc:
        caught = exc
    assert isinstance(caught, ShapeError), "missing intake must have a closed refusal"
    assert str(caught) == "access_failed"


def test_reviewed_pin_context_is_available_and_verifying():
    p = pin()
    result, caught = None, None
    with requests.page_requests((URL,), {p.host: p}):
        try:
            result = requests.page_context(p.host)
        except Exception as exc:
            caught = exc
    assert caught is None, (
        "a reviewed invented intermediate must permit a verifying context"
    )
    assert result.verify_mode == ssl.CERT_REQUIRED and result.check_hostname


def test_postback_cannot_switch_to_the_other_valid_delivered_target():
    fields = project(page(1), SHAPE).fields
    with (
        requests.page_requests((URL,), {}),
        requests.delivered_state(fields, TARGETS[0]),
        pytest.raises(TransportFault, match="schema_missing"),
    ):
        requests.check_target(requests.PagePostback(URL, fields, TARGETS[1]))


def test_postback_requires_active_frame_even_with_delivered_state():
    fields = project(page(1), SHAPE).fields
    assert not requests.active()
    with (
        requests.delivered_state(fields, TARGETS[0]),
        pytest.raises(TransportFault, match="schema_missing"),
    ):
        requests.check_target(requests.PagePostback(URL, fields, TARGETS[0]))


def test_required_register_pin_cannot_fall_back_to_system_context():
    with (
        requests.page_requests((URL,), {}),
        pytest.raises(certs.PinError, match="certificate_chain_incomplete"),
    ):
        requests.page_context(pin().host)


@pytest.mark.parametrize("field", ["projection", "upstream_sha256"])
def test_capture_loader_rejects_bad_evidence_before_admission(tmp_path, field):
    p = pin()
    capture.produce(
        tmp_path,
        lambda _: Response(URL, page(1, True), ()),
        p,
        review(),
        tool="SYN-tool",
        clock=lambda: STAMP,
        sleep=lambda _: None,
    )
    receipt = tmp_path / "intake/fc_register/capture-1.json"
    value = json.loads(receipt.read_bytes())
    value[field] = "SYN-other"
    receipt.write_bytes(canonical(value))
    with pytest.raises(certs.PinError, match="capture_evidence_missing"):
        certs.load_capture(
            tmp_path,
            "fc_register",
            p,
            identity=RequestIdentity("GET", URL, None, None, 1, None),
        )


def test_paging_revalidates_the_admitted_upstream_digest(tmp_path, monkeypatch):
    value, _ = direct_capture()
    monkeypatch.setattr(acquire, "load_capture", lambda *a, **k: value)
    # Isolate the paging layer's additional check from admission's own check.
    monkeypatch.setattr(
        acquire,
        "admit_capture",
        lambda *a, **k: (
            Response(URL, value.body, ()),
            {"upstream_sha256": "SYN-other"},
        ),
    )
    folder = tmp_path / "intake/fc_register"
    folder.mkdir(parents=True)
    (folder / "capture-1.json").write_bytes(b"{}")
    with pytest.raises(ShapeError, match="paging_incomplete"):
        acquire.pages(
            lambda _: (_ for _ in ()).throw(TransportFault("unreachable", "")),
            tmp_path,
            {value.pin.host: value.pin},
            SHAPE,
            65536,
            lambda _: None,
        )


@pytest.mark.parametrize("fault", ["body", "http"])
def test_terminal_refusal_is_not_converted_to_capture(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(acquire, "page_context", lambda *a: None)
    loader = Mock(return_value=None)
    monkeypatch.setattr(acquire, "load_capture", loader)

    def send(_):
        if fault == "http":
            raise TransportFault("http", "", 404)
        return Response(URL, page(1, True) + b"<!--SYN sign in-->", ())

    caught = None
    try:
        acquire.pages(send, tmp_path, {pin().host: pin()}, SHAPE, 65536, lambda _: None)
    except Exception as exc:
        caught = exc
    assert isinstance(caught, ShapeError), (
        "terminal refusal must remain in its own layer"
    )
    assert str(caught) == ("http" if fault == "http" else "credentials")
    loader.assert_not_called()


def test_capture_replay_finishes_without_manufacturing_a_live_post(tmp_path):
    from custodian.tests.test_fc_register_capture import prepared, replay

    p, _ = prepared(tmp_path)
    sent = []

    def unavailable(request):
        sent.append(request)
        raise TransportFault("unreachable", "")

    result, caught = None, None
    try:
        result = replay(tmp_path, p, unavailable)
    except Exception as exc:
        caught = exc
    assert caught is None, "an admitted complete capture chain must finish successfully"
    assert len(sent) == 1, "capture admission must stop live requests"
    assert len(json.loads(result.body)["rows"]) == 3


def test_producer_checks_closed_declaration_before_any_visitor_request(tmp_path):
    dec = review()
    dec["SYN-extra"] = "SYN-value"
    visitor = Mock(return_value=Response(URL, page(1, True), ()))
    with pytest.raises(ShapeError, match="schema_missing"):
        capture.produce(
            tmp_path,
            visitor,
            pin(),
            dec,
            tool="SYN-tool",
            clock=lambda: STAMP,
            sleep=lambda _: None,
        )
    visitor.assert_not_called()


def test_producer_checks_timestamp_before_any_visitor_request(tmp_path):
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    visitor = Mock(return_value=Response(URL, page(1, True), ()))
    with pytest.raises(SnapshotError, match="snapshot_date_missing"):
        capture.produce(
            tmp_path,
            visitor,
            pin(),
            review(),
            tool="SYN-tool",
            clock=lambda: "SYN-date",
            sleep=lambda _: None,
        )
    visitor.assert_not_called()


@pytest.mark.parametrize("plant", ["empty_name", "no_cards"])
def test_projection_validates_its_reconstructed_fragment(plant):
    body = page(1, True)
    if plant == "empty_name":
        body = body.replace(b"SYN Glass Orchard 1", b"")
    else:
        body = body.replace(b"pr-result-card", b"SYN-absent-card")
    with pytest.raises(ShapeError, match="schema_missing"):
        project(body, SHAPE)


class OrdinalBlindIdentity(RequestIdentity):
    """Invented defect: an identity whose equality forgets ordinal and predecessor."""

    def _key(self):
        return (self.method, self.url, self.target, self.argument)

    def __eq__(self, other):
        return isinstance(other, RequestIdentity) and self._key() == (
            other.method,
            other.url,
            other.target,
            other.argument,
        )

    def __hash__(self):
        return hash(self._key())


def test_paging_refuses_a_repeated_request_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire, "RequestIdentity", OrdinalBlindIdentity)
    monkeypatch.setattr(acquire, "page_context", lambda *a: None)
    bodies = [page(1), page(2), page(3, True)]
    sent = []

    def send(request):
        sent.append(request)
        return Response(URL, bodies[len(sent) - 1], ())

    p = pin()
    with pytest.raises(ShapeError, match="paging_incomplete"):
        acquire.pages(send, tmp_path, {p.host: p}, SHAPE, 65536, lambda _: None)
    assert len(sent) == 2, "a repeated identity must refuse before its request is sent"


def test_control_the_same_three_page_chain_completes_with_real_identities(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(acquire, "page_context", lambda *a: None)
    bodies = [page(1), page(2), page(3, True)]
    sent = []

    def send(request):
        sent.append(request)
        return Response(URL, bodies[len(sent) - 1], ())

    p = pin()
    result = acquire.pages(send, tmp_path, {p.host: p}, SHAPE, 65536, lambda _: None)
    assert len(result) == 3 and len(sent) == 3
