"""Exact pin, capture and intake refusals with invented certificates only."""

import hashlib
import json
import ssl
import warnings
from dataclasses import replace

import pytest
from custodian.tests import test_s2_t29_fix10 as fix10

from eii_custodian.publicdata.fetch import certificate_pins as certificates

HOST = "www.edu.gov.qa"
URL = "https://" + HOST + "/SYN-page"
STAMP = "2024-02-03T00:00:00Z"
SOURCE = "SYN-source"

# The shared module fixture generates one disposable chain, never a host certificate.
invented_certs = fix10.invented_certs
capture_receipt = fix10.capture_receipt
config_file = fix10.config_file
make_pin = fix10.make_pin


def exact(reason):
    return "^" + reason + "$"


@pytest.mark.parametrize("host", ["", "WWW.EDU.GOV.QA"])
def test_bound_pin_host_must_be_present_and_lower_case(invented_certs, host):
    pin = make_pin(invented_certs["intermediate"], host)
    with pytest.raises(certificates.PinError, match=exact("certificate_host_mismatch")):
        certificates.validate_pin(host, pin)


def test_verified_context_only_clears_partial_chain(invented_certs):
    expected = ssl.create_default_context().verify_flags
    expected &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    context = certificates.verified_context(
        HOST, make_pin(invented_certs["intermediate"])
    )
    assert context.verify_flags == expected
    assert not context.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF
    assert invented_certs["intermediate"] in context.get_ca_certs(binary_form=True)


def test_verified_context_unreadable_der_is_closed():
    der = b"SYN not a certificate"
    pin = certificates.Pin(HOST, hashlib.sha256(der).hexdigest(), der, True)
    with pytest.raises(
        certificates.PinError, match=exact("certificate_chain_incomplete")
    ):
        certificates.verified_context(HOST, pin)


def capture(pin, *, hops=(), final=None, body=b"SYN capture", **changes):
    value = certificates.Capture(
        body,
        URL,
        final if final is not None else (hops[-1] if hops else URL),
        tuple(hops),
        "SYN browser",
        STAMP,
        hashlib.sha256(body).hexdigest(),
        pin,
        True,
        "visitor",
    )
    return replace(value, **changes)


def test_admit_capture_three_hops_full_evidence(invented_certs):
    pin = make_pin(invented_certs["intermediate"])
    hops = (URL + "-SYN-a", URL + "-SYN-b", URL + "-SYN-c")
    response, evidence = certificates.admit_capture(capture(pin, hops=hops), URL)
    assert response.final_url == URL + "-SYN-c"
    assert response.body == b"SYN capture"
    assert response.hops == hops
    assert evidence == {
        "initial_url": URL,
        "final_url": URL + "-SYN-c",
        "redirect_urls": list(hops),
        "tool": "SYN browser",
        "captured_utc": STAMP,
        "sha256": hashlib.sha256(b"SYN capture").hexdigest(),
        "intermediate_host": HOST,
        "intermediate_sha256": pin.sha256,
        "tls_verified": True,
        "access": "visitor",
    }


def test_admit_capture_without_hops_ends_at_initial(invented_certs):
    pin = make_pin(invented_certs["intermediate"])
    response, evidence = certificates.admit_capture(capture(pin), URL)
    assert (response.final_url, response.hops) == (URL, ())
    assert evidence["redirect_urls"] == [] and evidence["final_url"] == URL


@pytest.mark.parametrize(
    "hops,final",
    [
        ((URL + "-SYN-a",), URL + "-SYN-z"),
        ((URL + "-SYN-a", URL + "-SYN-b", URL + "-SYN-c"), URL + "-SYN-b"),
        ((), URL + "-SYN-z"),
    ],
)
def test_admit_capture_final_must_be_last_hop(invented_certs, hops, final):
    pin = make_pin(invented_certs["intermediate"])
    with pytest.raises(certificates.PinError, match=exact("capture_evidence_missing")):
        certificates.admit_capture(capture(pin, hops=hops, final=final), URL)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"tool": " "}, "capture_evidence_missing"),
        ({"initial_url": URL + "-SYN-other"}, "capture_evidence_missing"),
        ({"hops": ("https://example.invalid/SYN",)}, "blocked_host"),
    ],
)
def test_admit_capture_closed_reasons(invented_certs, changes, reason):
    pin = make_pin(invented_certs["intermediate"])
    value = capture(pin)
    if "hops" in changes:
        value = replace(value, final_url=changes["hops"][-1], **changes)
    else:
        value = replace(value, **changes)
    with pytest.raises(certificates.PinError, match=exact(reason)):
        certificates.admit_capture(value, URL)


@pytest.mark.parametrize(
    "source,name",
    [
        (SOURCE, "SYN-sub/../SYN.der"),
        (SOURCE, "../SYN.der"),
        ("SYN/inner", "SYN.der"),
        (SOURCE, ""),
    ],
)
def test_intake_relative_rules(tmp_path, source, name):
    (tmp_path / "intake" / SOURCE / "SYN-sub").mkdir(parents=True)
    with pytest.raises(certificates.PinError, match=exact("intake_path_refused")):
        certificates.intake_file(tmp_path, source, name)


def test_intake_absolute_name_inside_folder_refused(tmp_path):
    folder = tmp_path / "intake" / SOURCE
    folder.mkdir(parents=True)
    (folder / "SYN.der").write_bytes(b"SYN")
    with pytest.raises(certificates.PinError, match=exact("intake_path_refused")):
        certificates.intake_file(tmp_path, SOURCE, str(folder / "SYN.der"))


def test_intake_name_link_leaving_folder_refused(tmp_path):
    folder = tmp_path / "intake" / SOURCE
    folder.mkdir(parents=True)
    outside = tmp_path / "SYN-outside"
    outside.mkdir()
    (folder / "SYN-link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(certificates.PinError, match=exact("intake_path_refused")):
        certificates.intake_file(tmp_path, SOURCE, "SYN-link/SYN.der")


def test_intake_plain_name_returned(tmp_path):
    assert (
        certificates.intake_file(tmp_path, SOURCE, "SYN.der")
        == tmp_path / "intake" / SOURCE / "SYN.der"
    )


@pytest.mark.parametrize("plant", ["extra", "none", "number"])
def test_load_pin_config_shape_is_closed(tmp_path, invented_certs, plant):
    config = config_file(tmp_path, invented_certs["intermediate"], HOST, SOURCE)
    if plant == "extra":
        config = dict(config, note="SYN")
    if plant == "none":
        config = None
    if plant == "number":
        config["security_review"] = 1
    with pytest.raises(
        certificates.PinError, match=exact("certificate_chain_incomplete")
    ):
        certificates.load_pin(tmp_path, SOURCE, config)


def test_load_pin_review_pending_reason(tmp_path, invented_certs):
    config = config_file(tmp_path, invented_certs["intermediate"], HOST, SOURCE)
    config["security_review"] = "PENDING"
    with pytest.raises(
        certificates.PinError, match=exact("certificate_review_pending")
    ):
        certificates.load_pin(tmp_path, SOURCE, config)


def test_load_pin_missing_file_reason(tmp_path, invented_certs):
    config = config_file(tmp_path, invented_certs["intermediate"], HOST, SOURCE)
    config["file"] = "SYN-missing.der"
    with pytest.raises(
        certificates.PinError, match=exact("certificate_chain_incomplete")
    ):
        certificates.load_pin(tmp_path, SOURCE, config)


def test_load_pin_inspection_raises_no_warning(tmp_path, invented_certs):
    config = config_file(tmp_path, invented_certs["intermediate"], HOST, SOURCE)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pin = certificates.load_pin(tmp_path, SOURCE, config)
    assert pin == make_pin(invented_certs["intermediate"])


def receipt(tmp_path, invented_certs):
    pin = make_pin(invented_certs["intermediate"])
    path, record = capture_receipt(tmp_path, pin)
    record["initial_url"] = record["final_url"] = URL
    return pin, path, record


@pytest.mark.parametrize("plant", ["extra", "text", "hop", "hops-text", "json"])
def test_load_capture_closed_reason(tmp_path, invented_certs, plant):
    pin, path, record = receipt(tmp_path, invented_certs)
    if plant == "extra":
        record["note"] = "SYN"
    if plant == "text":
        record["tool"] = 5
    if plant == "hop":
        record["hops"] = [URL, 5]
    if plant == "hops-text":
        record["hops"] = URL
    path.write_text("{SYN" if plant == "json" else json.dumps(record))
    with pytest.raises(certificates.PinError, match=exact("capture_evidence_missing")):
        certificates.load_capture(tmp_path, SOURCE, pin)


def test_load_capture_keeps_string_hops(tmp_path, invented_certs):
    pin, path, record = receipt(tmp_path, invented_certs)
    record["hops"] = [URL + "-SYN-a"]
    record["final_url"] = URL + "-SYN-a"
    path.write_text(json.dumps(record))
    value = certificates.load_capture(tmp_path, SOURCE, pin)
    assert value is not None
    assert value.hops == (URL + "-SYN-a",)
    assert value.final_url == URL + "-SYN-a" and value.pin is pin
