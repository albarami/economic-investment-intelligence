"""Serial public paging and capture replay, bound to full-response predecessors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..fetch.allowlist import approve, host_of
from ..fetch.certificate_pins import Pin, admit_capture, load_capture
from ..fetch.page_html import ShapeError
from ..fetch.page_identity import RequestIdentity, digest
from ..fetch.page_requests import (
    PagePostback,
    check_target,
    delivered_state,
    page_context,
    page_requests,
)
from ..fetch.receipts import sha256_hex
from ..fetch.transport import Response, Transport, TransportFault, metadata_limit
from .constants import TARGETS, URL
from .parse import fragment, project


def eligible(reason: str, status: int | None = None) -> bool:
    """L-1049 item 3: everything outside this closed set is terminal."""
    return (
        reason == "unreachable"
        or reason == "refusal_body"
        or (reason == "http" and status in {403, 429, 503})
    )


def obstacle(body: bytes) -> str | None:
    lower = body.lower()
    # Credentials never become an eligible obstacle response.
    if any(word in lower for word in (b"sign in", b"sign-in")):
        return "credentials"
    if any(word in lower for word in (b"robot check", b"paywall")):
        return "refusal_body"
    return None


def checked_response(response: Response, maximum: int) -> None:
    for url in (*response.hops, response.final_url):
        check_target(url)
        if not approve(url).ok:
            raise ShapeError("blocked_host")
        if host_of(url) == "eservices.qfc.qa":
            page_context(host_of(url))
    if len(response.body) > maximum:
        raise ShapeError("metadata_bytes")
    reason = obstacle(response.body)
    if reason:
        raise ShapeError(reason)


def pages(
    transport: Transport,
    cache: Path,
    pins: Mapping[str, Pin],
    shape: Mapping[str, Any],
    maximum: int,
    sleep: Callable[[float], None],
    *,
    captures: bool = True,
) -> list[Response]:
    """Complete the entire chain in memory before publishing any inventory."""
    expected = RequestIdentity("GET", URL, None, None, 1, None)
    fields: Mapping[str, str] = {}
    target = TARGETS[0]
    replay = False
    seen_responses: set[str] = set()
    seen_requests: set[RequestIdentity] = set()
    result = []
    captured_ordinals: set[int] = set()
    with page_requests((URL,), pins):
        while True:
            if expected in seen_requests:
                raise ShapeError("paging_incomplete")
            seen_requests.add(expected)
            response = None
            reason = "access_failed"
            if not replay:
                request = (
                    URL if expected.ordinal == 1 else PagePostback(URL, fields, target)
                )
                if expected.ordinal > 1:
                    sleep(1.0)
                try:
                    with delivered_state(fields, target), metadata_limit(maximum):
                        check_target(request)
                        page_context(host_of(URL))
                        response = transport(request)
                    checked_response(response, maximum)
                except TransportFault as exc:
                    if not eligible(exc.kind, exc.status):
                        raise ShapeError(exc.kind) from None
                    reason = "http_status" if exc.kind == "http" else exc.kind
                    response = None
                except ShapeError as exc:
                    if not eligible(str(exc)):
                        raise
                    reason = str(exc)
                    response = None
            if response is None:
                if not captures:
                    raise ShapeError(reason)
                pin = pins.get(host_of(URL))
                if pin is None:
                    raise ShapeError("certificate_chain_incomplete")
                capture = load_capture(
                    cache, "fc_register", pin, identity=expected, max_bytes=maximum
                )
                if capture is None:
                    raise ShapeError("access_failed")
                response, evidence = admit_capture(capture, URL, identity=expected)
                checked_response(response, maximum)
                body = response.body
                upstream = str(evidence["upstream_sha256"])
                provenance = "producer-attested"
                replay = True
                captured_ordinals.add(expected.ordinal)
                fields = {}
                target = TARGETS[0]
            else:
                projected = project(response.body, shape)
                body = projected.body
                fields, target = projected.fields, projected.target or TARGETS[0]
                upstream = sha256_hex(response.body)
                evidence = {}
                provenance = "computed-full-response"
            value = fragment(body)
            if (
                not digest(upstream)
                or upstream in seen_responses
                or value["progress"]["shown_page"] != expected.ordinal
            ):
                raise ShapeError("paging_incomplete")
            seen_responses.add(upstream)
            result.append(
                Response(
                    response.final_url,
                    body,
                    response.hops,
                    body_sha256=upstream,
                    evidence={
                        "request_identity": expected.data(),
                        "upstream_evidence": provenance,
                        "capture": evidence,
                    },
                )
            )
            if value["progress"]["continuation"] == "terminal":
                if replay:
                    from ..fetch.certificate_pins import capture_files

                    # Terminal replay requires the intake folder to hold exactly
                    # the continuation receipts (ordinals after any live prefix),
                    # not a full producer 1..N set left beside a live first page.
                    if capture_files(cache, "fc_register") != captured_ordinals:
                        raise ShapeError("paging_incomplete")
                return result
            expected = RequestIdentity(
                "POST", URL, target, "", expected.ordinal + 1, upstream
            )
