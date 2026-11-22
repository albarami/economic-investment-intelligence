"""INVENTED closed exchanges against the documented schema; no live calls."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import pytest
from shapely.geometry import box

from eii_custodian.publicdata.cdse import transport as t
from eii_custodian.publicdata.cdse.contracts import tiles_for
from eii_custodian.publicdata.cdse.wire import ProcessSpec, process_body

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


def spec():
    """INVENTED boundary and explicit window, never a reviewed Qatar boundary."""
    return ProcessSpec(
        tiles_for(box(0, 0, 20, 20), "EPSG:32639")[0],
        "2026-10-19T00:00:00Z",
        "2026-11-19T00:00:00Z",
    )


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
                        {"Content-Type": "application/x-www-form-urlencoded"},
                    )
                )
        for body in (
            {"arbitrary": "payload"},
            {"evalscript": "arbitrary"},
            {"url": "https://other.invalid"},
        ):
            with pytest.raises(t.CdseError):
                t.validate_request(
                    t.Request(
                        "process",
                        ENDPOINTS["process"],
                        body,
                        {
                            "Authorization": "Bearer FAKE-CDSE-TOKEN",
                            "Content-Type": "application/json",
                            "Accept": "application/x-tar",
                        },
                    )
                )


def test_pending_envelope_is_not_a_provider_request():
    """INVENTED legacy envelope must be refused even with a budget and token."""
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        with pytest.raises(t.CdseError, match="schema"):
            t.validate_request(
                t.Request(
                    "process",
                    ENDPOINTS["process"],
                    {"request_sha256": "a" * 64, "contract": "pending.v1"},
                    {
                        "Authorization": "Bearer FAKE-CDSE-TOKEN",
                        "Content-Type": "application/json",
                        "Accept": "application/x-tar",
                    },
                )
            )


def test_documented_process_shape_and_nested_plants():
    inputs = spec()
    body = process_body(inputs)
    assert body["input"]["data"][0]["dataFilter"] == {
        "timeRange": {"from": inputs.start, "to": "2026-11-18T23:59:59Z"},
        "mosaickingOrder": "leastCC",
    }
    assert body["output"]["width"] == 2
    assert body["output"]["height"] == 2
    headers = {
        "Authorization": "Bearer FAKE-CDSE-TOKEN",
        "Content-Type": "application/json",
        "Accept": "application/x-tar",
    }
    request = t.Request("process", ENDPOINTS["process"], body, headers)
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        t.validate_request(request)
        for path, value in (
            (("evalscript",), "arbitrary"),
            (("input", "extra"), True),
            (("input", "data", 0, "type"), "other"),
            (("input", "data", 0, "dataFilter", "mosaickingOrder"), "mostRecent"),
            (("input", "bounds", "properties", "crs"), "EPSG:32639"),
            (("output", "width"), 2501),
            (("output", "width"), 0),
            (("output", "width"), 1),
            (("output", "height"), True),
            (("output", "resx"), 10),
            (("output", "responses", 1, "identifier"), "other"),
        ):
            planted = deepcopy(body)
            target = planted
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with pytest.raises(t.CdseError, match="schema"):
                t.validate_request(replace(request, body=planted))


def test_typed_process_input_plants_stop_before_send():
    inputs = spec()
    for poisoned in (
        replace(inputs, start=inputs.end),
        replace(inputs, start="2026-10-19"),
        replace(inputs, start="2026-10-19T00:00:00.5Z"),
        replace(inputs, end="2026-11-19T00:00:00.5Z"),
        replace(inputs, tile=replace(inputs.tile, crs="EPSG:4326")),
        replace(inputs, tile=replace(inputs.tile, resolution_m=20)),
        replace(inputs, tile=replace(inputs.tile, bounds=(1, 0, 21, 20))),
        replace(inputs, tile=replace(inputs.tile, bounds=(0, 0, 20))),
        replace(inputs, tile=replace(inputs.tile, tile_id="other")),
        replace(inputs, tile=replace(inputs.tile, height=False)),
    ):
        with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
            s, sent = session([])
            with pytest.raises(ValueError):
                s.picture(poisoned)
            with pytest.raises(t.CdseError, match="stopped"):
                s.token()
            assert sent == []


def test_token_picture_third_request_refused_before_send():
    replies = [
        t.Reply(200, b'{"access_token":"FAKE-CDSE-TOKEN","token_type":"Bearer"}'),
        t.Reply(200, b"FAKE-PICTURE"),
    ]
    with patch.object(t, "REVIEWED_ENDPOINTS", ENDPOINTS):
        s, sent = session(replies)
        s.token()
        assert s.picture(spec()) == b"FAKE-PICTURE"
        with pytest.raises(t.CdseError, match="budget"):
            s.picture(spec())
    assert len(sent) == 2
    assert sent[0].headers == {"Content-Type": "application/x-www-form-urlencoded"}
    assert sent[0].body["client_id"] == FAKE.client
    assert sent[1].headers == {
        "Authorization": "Bearer FAKE-CDSE-TOKEN",
        "Content-Type": "application/json",
        "Accept": "application/x-tar",
    }
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
                s.picture(spec())
            assert (
                str(error.value)
                == "denied: [redacted] / [redacted] / [redacted]; quota exhausted"
            )
            with pytest.raises(t.CdseError, match="stopped"):
                s.picture(spec())
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
            t.Reply(200, b"FAKE-PICTURE"),
        ]
        s, sent = session(replies, ("token", "process"))
        s.token()
        s.picture(spec())
        # No documented extra metadata endpoint is admitted, even if budgeted.
        with pytest.raises(t.CdseError, match="metadata_endpoint_pending"):
            s.metadata(spec())
        with pytest.raises(t.CdseError, match="stopped"):
            s.picture(spec())
        assert len(sent) == 2
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
        read_yaml,
        registry_path,
    )

    document = read_yaml(registry_path())
    row = next(r for r in document["sources"] if r["key"] == "satellite_cdse_backup")
    # The transport fixture intentionally admits only its invented endpoint.
    # Validate this CDSE declaration without loading unrelated public sources.
    entry = _entry(row)
    assert entry.source_id == "satellite_cdse_backup"
    assert _entry(row) == entry
    for change in (
        {"kind": "https_file"},
        {"release_tables": ["facts"]},
        {"nightly_live_fetch": True},
        {"source_id": "other"},
    ):
        with pytest.raises(
            RegistryError, match="CDSE backup must remain optional and unread"
        ):
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
            s.picture(spec())
        assert str(error.value) == "quota refusal [redacted] / [redacted]"
        assert len(sent) == 3
