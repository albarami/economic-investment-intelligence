"""Invented closed CDSE exchanges: no verified provider contract or live calls."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest

from eii_custodian.publicdata.cdse import transport as t

FAKE = t.Credentials("FAKE-CDSE-CLIENT", "FAKE-CDSE-SECRET")
ENDPOINTS = {
    "token": "https://cdse.invalid/token",
    "metadata": "https://cdse.invalid/metadata",
    "process": "https://cdse.invalid/process",
}


@pytest.fixture(autouse=True)
def no_socket():
    with (
        patch("socket.socket", side_effect=AssertionError("network")),
        patch(
            "eii_custodian.publicdata.fetch.allowlist.ALLOWED_HOSTS",
            frozenset({"cdse.invalid"}),
        ),
    ):
        yield


def session(replies, plan=("token", "process")):
    sends = []

    def sender(request):
        sends.append(request)
        return replies[len(sends) - 1]

    return t.Session(FAKE, sender, plan), sends


def test_pending_contract_and_closed_shapes():
    s, sent = session([])
    with pytest.raises(t.CdseError, match="contract_pending"):
        s.token()
    assert sent == []
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        for url in (
            "http://cdse.invalid/token",
            "https://other.invalid/token",
            "https://cdse.invalid/other",
            "https://cdse.invalid/token?key=FAKE",
            "https://" + "@".join(("user", "cdse.invalid/token")),
            "https://cdse.invalid:444/token",
        ):
            with pytest.raises(t.CdseError):
                t.validate_request(
                    t.Request(
                        "token",
                        url,
                        {
                            "grant_type": "client_credentials",
                            "client_id": FAKE.client,
                            "client_secret": FAKE.secret,
                        },
                        {},
                    )
                )
        for body in (
            {"arbitrary": "payload"},
            {"evalscript": "arbitrary"},
            {"url": "https://other.invalid"},
        ):
            with pytest.raises(t.CdseError):
                t.validate_request(t.Request("process", ENDPOINTS["process"], body, {}))


def test_token_picture_third_request_refused_before_send():
    replies = [
        t.Reply(200, b'{"access_token":"FAKE-CDSE-TOKEN","token_type":"Bearer"}'),
        t.Reply(200, b"FAKE-PICTURE"),
    ]
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        s, sent = session(replies)
        s.token()
        assert s.picture("a" * 64) == b"FAKE-PICTURE"
        with pytest.raises(t.CdseError, match="budget"):
            s.picture("a" * 64)
    assert len(sent) == 2
    assert sent[0].headers == {}
    assert sent[0].body["client_id"] == FAKE.client
    assert sent[1].headers == {"Authorization": "Bearer FAKE-CDSE-TOKEN"}
    assert "FAKE-CDSE" not in repr(s) + repr(sent)


def test_refusal_redacts_echoes_and_stops():
    body = f"denied: {FAKE.client} / {FAKE.secret} / FAKE-CDSE-TOKEN; quota exhausted".encode()
    for status in (400, 401, 403, 429):
        with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
            s, sent = session(
                [
                    t.Reply(
                        200, b'{"access_token":"FAKE-CDSE-TOKEN","token_type":"Bearer"}'
                    ),
                    t.Reply(status, body),
                ]
            )
            s.token()
            with pytest.raises(t.CdseError) as error:
                s.picture("a" * 64)
            assert (
                str(error.value)
                == "denied: [redacted] / [redacted] / [redacted]; quota exhausted"
            )
            with pytest.raises(t.CdseError, match="stopped"):
                s.picture("a" * 64)
            assert len(sent) == 2


def test_auth_and_redirect_refusals_and_exception_values():
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        for reply in (
            t.Reply(302, b"", "https://other.invalid"),
            t.Reply(200, b"{}"),
            t.Reply(200, b'{"access_token":3}'),
        ):
            s, sent = session([reply])
            with pytest.raises(t.CdseError):
                s.token()
            with pytest.raises(t.CdseError):
                s.token()
            assert len(sent) == 1

        def sender(_request):
            raise ValueError(f"refused {FAKE.secret}")

        s = t.Session(FAKE, sender, ("token",))
        with pytest.raises(t.CdseError, match="refused \\[redacted\\]"):
            s.token()


def test_bulk_enumeration_and_unbudgeted_metadata():
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        replies = [
            t.Reply(200, b'{"access_token":"FAKE-CDSE-TOKEN","token_type":"Bearer"}'),
            t.Reply(200, b"{}"),
            t.Reply(200, b"FAKE-PICTURE"),
        ]
        s, sent = session(replies, ("token", "metadata", "process"))
        s.token()
        assert s.metadata("b" * 64) == b"{}"
        s.picture("b" * 64)
        with pytest.raises(t.CdseError):
            s.metadata("b" * 64)
        assert len(sent) == 3
        request = sent[-1]
        for changed in (
            replace(request, headers={"Authorization": "wrong", "extra": "x"}),
            replace(request, body={**request.body, "extra": "x"}),
        ):
            with pytest.raises(t.CdseError):
                t.validate_request(changed)


def test_registry_source_cannot_enter_ordinary_kind_or_release():
    from eii_custodian.publicdata.fetch.registry import (
        RegistryError,
        _entry,
        load_registry,
        read_yaml,
        registry_path,
    )

    entry = next(e for e in load_registry() if e.source_id == "satellite_cdse_backup")
    document = read_yaml(registry_path())
    row = next(r for r in document["sources"] if r["key"] == entry.key)
    assert _entry(row) == entry
    for change in (
        {"kind": "https_file"},
        {"release_tables": ["facts"]},
        {"nightly_live_fetch": True},
        {"source_id": "other"},
    ):
        with pytest.raises(RegistryError):
            _entry({**row, **change})


def test_endpoint_record_does_not_bypass_host_allowlist():
    with (
        patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS),
        patch("eii_custodian.publicdata.fetch.allowlist.ALLOWED_HOSTS", frozenset()),
    ):
        s, sent = session([])
        with pytest.raises(t.CdseError, match="host"):
            s.token()
        assert sent == []


def test_refusal_redacts_every_issued_token_after_refresh():
    replies = [
        t.Reply(200, b'{"access_token":"FAKE-CDSE-OLD-TOKEN","token_type":"Bearer"}'),
        t.Reply(200, b'{"access_token":"FAKE-CDSE-NEW-TOKEN","token_type":"Bearer"}'),
        t.Reply(429, b"quota refusal FAKE-CDSE-OLD-TOKEN / FAKE-CDSE-NEW-TOKEN"),
    ]
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        s, sent = session(replies, ("token", "token", "process"))
        s.token()
        s.token()
        with pytest.raises(t.CdseError) as error:
            s.picture("a" * 64)
        assert str(error.value) == "quota refusal [redacted] / [redacted]"
        assert len(sent) == 3
