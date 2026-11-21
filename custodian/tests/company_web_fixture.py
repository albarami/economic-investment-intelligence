"""Invented company-web inputs only; never a captured page or register value."""

import json

import pytest

from eii_custodian.publicdata.fetch.receipts import sha256_hex

NAME = "Zorvella Fabrication"
URL = "https://zorvella.example.test/about"
OTHER = "https://other.example.test/about"
STAMP = "2026-11-20T12:00:00Z"
IDENTITY = {
    "maker": "Builder",
    "tool": "shell",
    "model": "deterministic",
    "run_id": "syn-build",
}
REVIEWER = {
    "maker": "OtherMaker",
    "tool": "review-tool",
    "model": "review-model",
    "run_id": "syn-review",
}


def body(**updates: object) -> bytes:
    block = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": NAME,
        "address": {"@type": "PostalAddress", "streetAddress": "SYN lane"},
        "url": URL,
        "description": "Fabrication",
    }
    block.update(updates)
    return (
        '<html><body><script type="application/ld+json">'
        + json.dumps(block)
        + "</script><aside>Unrelated mixed content</aside></body></html>"
    ).encode()


def receipt(data: bytes) -> dict[str, object]:
    return {
        "source_id": "company_web",
        "key": "company_web/syn",
        "sha256": sha256_hex(data),
        "bytes": len(data),
        "retrieved_utc": STAMP,
        "fetch_url": URL,
        "original_url": URL,
        "publisher": "Invented publisher",
        "licence_basis": "owner_decision",
        "licence_id": "not_stated",
        "decision_record": "0026",
        "method": "company_web@v1",
        "extractor": IDENTITY,
    }


def manifest() -> dict[str, object]:
    return {
        "version": 1,
        "reviewed_by": IDENTITY,
        "reviewed_utc": STAMP,
        "provider": {
            "host": "search.example.test",
            "path": "/search",
            "result_selector": "a.result",
            "attribute": "href",
            "visitor_readable": True,
            "keyless": True,
        },
        "companies": {"syn-a": [URL], "syn-b": [OTHER]},
        "access": {
            host: {"terms_url": "", "robots_url": "", "delay_seconds": 2}
            for host in (
                "search.example.test",
                "zorvella.example.test",
                "other.example.test",
            )
        },
        "selectors": {},
    }


# Import this autouse fixture in each company-web test module. A regression cannot
# turn an invented transport test into a live request.


@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network_refused")

    monkeypatch.setattr("socket.create_connection", refused)
    monkeypatch.setattr("socket.socket.connect", refused)
    monkeypatch.setattr("socket.socket.connect_ex", refused)
