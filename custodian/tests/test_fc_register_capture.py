"""Projection-before-write producer and closed capture-transition plants."""

import hashlib
import json
import ssl
from dataclasses import replace
from unittest.mock import patch

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem
from custodian.tests.test_fc_register import (
    STAMP,
    no_private_outputs,
    page,
    review,
    row,
)

from eii_custodian.publicdata.fc_register.capture import produce
from eii_custodian.publicdata.fc_register.constants import URL
from eii_custodian.publicdata.fetch import certificate_pins as certs
from eii_custodian.publicdata.fetch.page_records import PageError, fetch_page
from eii_custodian.publicdata.fetch.transport import Response, TransportFault


def pin():
    der = ssl.PEM_cert_to_DER_cert(intermediate_pem().decode())
    return certs.Pin("eservices.qfc.qa", hashlib.sha256(der).hexdigest(), der, True)


def prepared(tmp_path):
    p = pin()
    bodies = [page(1), page(2), page(3, True)]
    sent = []

    def visitor(request):
        sent.append(request)
        return Response(str(request), bodies[len(sent) - 1], ())

    produce(
        tmp_path,
        visitor,
        p,
        review(),
        tool="SYN-browser",
        clock=lambda: STAMP,
        sleep=lambda _: None,
    )
    assert len(sent) == 3
    no_private_outputs(tmp_path)
    return p, bodies


def replay(tmp_path, p, send):
    dec = review()
    dec["pins"] = [{"host": p.host}]
    with (
        patch.object(certs, "load_pin", return_value=p),
        patch("eii_custodian.publicdata.fetch.page_acquire.load_pin", return_value=p),
    ):
        return fetch_page(
            row(), send, tmp_path, lambda: STAMP, lambda _: None, declaration=dec
        )


def failure(kind="unreachable", status=None):
    def send(_):
        raise TransportFault(kind, URL, status)

    return send


@pytest.mark.parametrize("prefix", [False, True])
def test_end_to_end_initial_capture_and_live_prefix(tmp_path, prefix):
    p, bodies = prepared(tmp_path)
    sent = []
    if prefix:
        folder = tmp_path / "intake/fc_register"
        (folder / "capture-1.json").unlink()
        (folder / "fragment-1.json").unlink()

    def send(request):
        sent.append(request)
        if prefix and len(sent) == 1:
            return Response(str(request), bodies[0], ())
        raise TransportFault("unreachable", URL)

    result = replay(tmp_path, p, send)
    value = json.loads(result.body)
    assert len(value["rows"]) == 3 and len(sent) == (2 if prefix else 1)
    for item in value["inputs"][1:]:
        assert item["upstream_evidence"] == "producer-attested"
    no_private_outputs(tmp_path)


@pytest.mark.parametrize(
    "kind,status",
    [
        ("unreachable", None),
        ("http", 403),
        ("http", 429),
        ("http", 503),
        ("obstacle", None),
    ],
)
def test_every_eligible_transition_attempts_capture(tmp_path, kind, status):
    p, _ = prepared(tmp_path)
    send = (
        (lambda request: Response(str(request), b"robot check SYN-UPSTREAM", ()))
        if kind == "obstacle"
        else failure(kind, status)
    )
    result = replay(tmp_path, p, send)
    assert json.loads(result.body)["inputs"][0]["capture"]["access"] == "visitor"
    no_private_outputs(tmp_path)


@pytest.mark.parametrize(
    "plant",
    [
        "digest",
        "version",
        "identity",
        "evidence",
        "time",
        "progress",
        "missing_progress",
        "false_terminal",
        "wrong_page",
        "replay",
        "duplicate",
        "missing",
        "reordered",
        "predecessor",
        "non_progress",
        "extra_property",
        "raw_body",
        "oversize",
    ],
)
def test_capture_plants_refuse_without_copy_or_publication(tmp_path, plant):
    p, _ = prepared(tmp_path)
    folder = tmp_path / "intake/fc_register"
    receipt = folder / "capture-2.json"
    meta = json.loads(receipt.read_bytes())
    bodypath = folder / meta["file"]
    value = json.loads(bodypath.read_bytes())
    if plant == "digest":
        meta["sha256"] = "a" * 64
    elif plant == "version":
        meta["projection"] = "SYN-wrong-version"
    elif plant == "identity":
        meta["request_identity"]["argument"] = "SYN-argument"
    elif plant == "evidence":
        meta["tls_verified"] = False
    elif plant == "time":
        meta["captured_utc"] = "SYN-invalid-time"
    elif plant in {
        "progress",
        "missing_progress",
        "false_terminal",
        "wrong_page",
        "extra_property",
        "raw_body",
        "oversize",
    }:
        if plant == "progress":
            value["progress"]["continuation"] = "SYN-bad"
        elif plant == "missing_progress":
            del value["progress"]
        elif plant == "false_terminal":
            value["progress"]["continuation"] = "terminal"
        elif plant == "wrong_page":
            value["progress"]["shown_page"] = 1
        elif plant == "extra_property":
            value["person"] = "SYN-REFUSED-BYTES"
        body = json.dumps(
            value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        ).encode()
        if plant == "raw_body":
            body = page(2)
        if plant == "oversize":
            body = b"SYN-REFUSED-BYTES" * 7000
        bodypath.write_bytes(body)
        meta["sha256"] = hashlib.sha256(body).hexdigest()
    elif plant == "missing":
        receipt.unlink()
    elif plant in {"replay", "duplicate"}:
        meta = json.loads((folder / "capture-1.json").read_bytes())
    elif plant == "reordered":
        meta = json.loads((folder / "capture-3.json").read_bytes())
    elif plant == "non_progress":
        meta["upstream_sha256"] = meta["request_identity"]["preceding_sha256"]
    else:
        meta["request_identity"]["preceding_sha256"] = "a" * 64
    if plant != "missing":
        receipt.write_text(json.dumps(meta))
    expected_reason = {
        "digest": "capture_hash_mismatch",
        "version": "capture_evidence_missing",
        "identity": "capture_evidence_missing",
        "evidence": "tls_verification_disabled",
        "time": "snapshot_date_missing",
        "progress": "capture_evidence_missing",
        "missing_progress": "capture_evidence_missing",
        "false_terminal": "paging_incomplete",
        "wrong_page": "capture_progress_invalid",
        "replay": "capture_identity_mismatch",
        "duplicate": "capture_identity_mismatch",
        "missing": "access_failed",
        "reordered": "capture_identity_mismatch",
        "predecessor": "capture_identity_mismatch",
        "non_progress": "paging_incomplete",
        "extra_property": "capture_evidence_missing",
        "raw_body": "capture_evidence_missing",
        "oversize": "metadata_bytes",
    }[plant]
    with pytest.raises((PageError, certs.PinError), match=expected_reason):
        replay(tmp_path, p, failure())
    assert list((tmp_path / "fc_register/failures").rglob("*.meta.json"))
    assert not (tmp_path / "fc_register/inputs").exists()
    assert not (tmp_path / "fc_register/index").exists()
    # Inspect all outputs, excluding the planted refused intake itself.
    no_private_outputs(tmp_path / "fc_register")
    for f in (tmp_path / "fc_register").rglob("*"):
        if f.is_file():
            assert b"SYN-REFUSED-BYTES" not in f.read_bytes()


@pytest.mark.parametrize(
    "kind,status",
    [
        ("http", 404),
        ("http", 500),
        ("blocked_host", None),
        ("credentials", None),
        ("body_bytes", None),
        ("schema_missing", None),
    ],
)
def test_terminal_failure_never_loads_capture(tmp_path, kind, status):
    p, _ = prepared(tmp_path)
    with patch("eii_custodian.publicdata.fc_register.acquire.load_capture") as load:
        with pytest.raises(PageError):
            replay(tmp_path, p, failure(kind, status))
        load.assert_not_called()
    no_private_outputs(tmp_path)


def test_sign_in_pin_and_size_are_terminal(tmp_path):
    p, _ = prepared(tmp_path)
    for send in [
        lambda r: Response(str(r), b"sign in SYN-PRIVATE", ()),
        lambda r: Response(str(r), b"x" * 70000, ()),
    ]:
        with patch("eii_custodian.publicdata.fc_register.acquire.load_capture") as load:
            with pytest.raises(PageError):
                replay(tmp_path, p, send)
            load.assert_not_called()
    with (
        patch(
            "eii_custodian.publicdata.fc_register.acquire.page_context",
            side_effect=certs.PinError("tls_verification_disabled"),
        ),
        patch("eii_custodian.publicdata.fc_register.acquire.load_capture") as load,
    ):
        with pytest.raises(certs.PinError, match="tls_verification_disabled"):
            replay(tmp_path, p, failure())
        load.assert_not_called()


def test_missing_capture_records_dated_refusal(tmp_path):
    p = pin()
    with pytest.raises(PageError, match="access_failed"):
        replay(tmp_path, p, failure())
    failures = list((tmp_path / "fc_register/failures").rglob("*.meta.json"))
    assert failures and all(
        json.loads(f.read_bytes())["retrieved_utc"] == STAMP for f in failures
    )


def test_producer_failure_writes_no_form_or_person_state(tmp_path):
    p = pin()
    bodies = iter([page(1), page(1)])
    with pytest.raises(ValueError, match="paging_incomplete"):
        produce(
            tmp_path,
            lambda r: Response(str(r), next(bodies), ()),
            p,
            review(),
            tool="SYN-browser",
            clock=lambda: STAMP,
            sleep=lambda _: None,
        )
    assert not list(tmp_path.rglob("capture-*.json"))
    no_private_outputs(tmp_path)


@pytest.mark.parametrize(
    "kind,status",
    [
        ("unreachable", None),
        ("http", 403),
        ("http", 429),
        ("http", 503),
        ("obstacle", None),
    ],
)
def test_v2_school_eligible_failure_uses_single_capture(tmp_path, kind, status):
    from custodian.tests.test_s2_t29_live_acquire import school, school_transport
    from custodian.tests.test_s2_t29_live_shapes import entry

    dec, attrs = school()
    p = replace(pin(), host="www.data.gov.qa")
    dec["pins"] = [{"host": p.host}]
    normal = school_transport(attrs, [])
    metadata = normal(dec["url"])
    capture = certs.Capture(
        metadata.body,
        dec["url"],
        dec["url"],
        (),
        "SYN-browser",
        STAMP,
        hashlib.sha256(metadata.body).hexdigest(),
        p,
        True,
        "visitor",
    )

    def send(url):
        if url != dec["url"]:
            return normal(url)
        if kind == "obstacle":
            return Response(url, b"robot check", ())
        raise TransportFault(kind, url, status)

    with (
        patch("eii_custodian.publicdata.fetch.page_acquire.load_pin", return_value=p),
        patch.object(certs, "load_capture", return_value=capture) as load,
    ):
        result = fetch_page(
            entry(dec, "schools_private_directory"),
            send,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert json.loads(result.body)["rows"]
    assert load.call_count == 1
    assert json.loads(result.body)["inputs"][0]["capture"]["access"] == "visitor"


def test_direct_fc_admission_cannot_use_legacy_raw_capture():
    p = pin()
    raw = page(1, True)
    capture = certs.Capture(
        raw,
        URL,
        URL,
        (),
        "SYN-browser",
        STAMP,
        hashlib.sha256(raw).hexdigest(),
        p,
        True,
        "visitor",
    )
    with pytest.raises(certs.PinError, match="capture_evidence_missing"):
        certs.admit_capture(capture, URL)
