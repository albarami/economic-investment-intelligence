"""Scoped transport plants with invented certificates and no sockets."""

import hashlib
import html
import json
import ssl

import pytest
from custodian.tests.test_page_acquire_survivors_1 import refused, run
from custodian.tests.test_s2_t29_fix10 import config_file
from custodian.tests.test_s2_t29_fix10 import invented_certs as invented_certs
from custodian.tests.test_s2_t29_live_shapes import (
    URL,
    embedded,
    entry,
    schema,
    tariff,
    tariffs,
)

from eii_custodian.publicdata.fetch import page_acquire as acquire
from eii_custodian.publicdata.fetch import page_requests, transport
from eii_custodian.publicdata.fetch.certificate_pins import Pin, PinError


@pytest.fixture(autouse=True)
def isolated_ca_store(tmp_path, monkeypatch):
    """Keep default contexts independent of the machine's certificate store."""
    ca_file = tmp_path / "SYN-empty-ca.pem"
    ca_file.write_bytes(b"")
    ca_dir = tmp_path / "SYN-empty-ca-dir"
    ca_dir.mkdir()
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
    monkeypatch.setenv("SSL_CERT_DIR", str(ca_dir))
    assert ssl.create_default_context().get_ca_certs() == []


def test_default_context_has_no_ambient_certificates():
    assert ssl.create_default_context().get_ca_certs() == []


@pytest.mark.parametrize("plant", ["valid", "duplicate", "malformed"])
def test_pin_scope(tmp_path, invented_certs, plant):
    dec, body, record = embedded()
    pinned = "https://www.edu.gov.qa/SYN-page"
    dec["url"] = pinned
    dec["reviewed_urls"] = [pinned]
    row = entry(dec)
    spec = config_file(tmp_path, invented_certs["intermediate"], source=row.source_id)
    dec["pins"] = [spec]
    if plant == "duplicate":
        dec["pins"].append(spec.copy())
    if plant == "malformed":
        dec["pins"].append("SYN-not-a-mapping")
    calls = []
    der = invented_certs["intermediate"]
    expected_pin = Pin("www.edu.gov.qa", hashlib.sha256(der).hexdigest(), der, True)

    def send(url):
        calls.append(url)
        assert page_requests.active()
        assert page_requests._PINS.get() == {"www.edu.gov.qa": expected_pin}
        return transport.Response(url, body, ())

    if plant == "valid":
        assert json.loads(run(tmp_path, dec, body, row=row, send=send).body)[
            "rows"
        ] == [
            {
                "title": "SYN > event",
                "start": "2031-02-03",
                "end": "2031-02-04",
                "published_record": record,
            }
        ]
        assert calls == [pinned]
    else:
        refused("schema_missing", lambda: run(tmp_path, dec, body, row=row, send=send))
        assert calls == []


def test_pinned_redirect_rechecks_context(tmp_path, invented_certs, monkeypatch):
    dec, body, record = embedded()
    target = "https://www.edu.gov.qa/SYN-page"
    dec["reviewed_urls"].append(target)
    row = entry(dec)
    dec["pins"] = [
        config_file(tmp_path, invented_certs["intermediate"], source=row.source_id)
    ]
    original = acquire.page_context
    calls = []

    def context(host):
        calls.append(host)
        result = original(host)
        assert result.get_ca_certs(binary_form=True) == [invented_certs["intermediate"]]
        return result

    monkeypatch.setattr(acquire, "page_context", context)
    result = run(
        tmp_path,
        dec,
        body,
        row=row,
        send=lambda u: transport.Response(target, body, (target,)),
    )
    assert json.loads(result.body)["rows"] == [
        {
            "title": "SYN > event",
            "start": "2031-02-03",
            "end": "2031-02-04",
            "published_record": record,
        }
    ]
    assert calls == ["www.edu.gov.qa", "www.edu.gov.qa"]


def test_unreviewed_page_is_typed_refusal(tmp_path):
    dec = tariffs()
    dec["shape"]["discovery"] = {
        "url": URL + "/SYN-unreviewed",
        "record_path": [],
        "link_path": ["url"],
        "length_path": None,
        "modified_path": None,
        "count_header": None,
        "pages_header": None,
    }
    calls = []
    refused(
        "blocked_host",
        lambda: run(
            tmp_path,
            dec,
            tariff(),
            row=entry(dec, "manateq_tariffs"),
            send=lambda u: calls.append(u),
        ),
    )
    assert calls == []


def test_metadata_limit_scoped_to_read(tmp_path):
    dec, body, record = embedded()

    def send(url):
        assert transport._METADATA_LIMIT.get() == dec["max_bytes"]
        return transport.Response(url, body, ())

    assert json.loads(run(tmp_path, dec, body, send=send).body)["rows"] == [
        {
            "title": "SYN > event",
            "start": "2031-02-03",
            "end": "2031-02-04",
            "published_record": record,
        }
    ]
    assert transport._METADATA_LIMIT.get() is None


def test_decimal_published_record_json_default(tmp_path):
    dec, _, rec = embedded()
    dec["shape"]["record_schema"]["fields"]["SYN-measure"] = schema("number")
    rec["SYN-measure"] = 1.5
    one = (
        '<vq-event-listing :events="'
        + html.escape(json.dumps([rec]), quote=True)
        + '"></vq-event-listing>'
    )
    result = run(tmp_path, dec, (one * 2).encode())
    assert (
        json.loads(result.body)["rows"][0]["published_record"]["SYN-measure"] == "1.5"
    )


def test_unpinned_redirect_refuses(tmp_path):
    dec, body, _ = embedded()
    target = "https://www.edu.gov.qa/SYN-page"
    dec["reviewed_urls"].append(target)
    with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
        run(tmp_path, dec, body, send=lambda u: transport.Response(target, body, ()))


def test_metadata_bound_is_rechecked_after_transport(tmp_path):
    from custodian.tests.test_s2_t29_live_acquire import school, school_transport

    dec, attrs = school()
    base = school_transport(attrs, [])

    def send(url):
        if url == dec["url"]:
            obj = json.loads(base(url).body)
            # A callback can mutate its shared declaration after entry validation.
            dec["shape"]["page_size"] = 0
            obj["maxRecordCount"] = 0
        else:
            obj = {"count": 0}
        return transport.Response(url, json.dumps(obj).encode(), ())

    refused(
        "schema_missing",
        lambda: run(
            tmp_path, dec, b"", row=entry(dec, "schools_private_directory"), send=send
        ),
    )
    assert not list(tmp_path.rglob("index/*.json"))


def test_classified_first_address_rechecked_after_transport(tmp_path):
    from custodian.tests.test_s2_t29_live_shapes import classified

    dec, body = classified()
    row = entry(dec, "monaqasat_classified")

    def send(url):
        # Keep the parsed page/end template valid but change the shared URL.
        dec["url"] = URL + "/SYN-other"
        return transport.Response(url, body, ())

    refused("blocked_host", lambda: run(tmp_path, dec, body, row=row, send=send))
    assert not list(tmp_path.rglob("index/*.json"))
