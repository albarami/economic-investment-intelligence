"""Versioned qualification identity; no live route is verified by replay."""

import hashlib
from collections.abc import Mapping
from typing import TypedDict

from eii_gateway.memo import digest


class Identity(TypedDict):
    provider: str
    model: str
    rubric_sha256: str
    cases_sha256: str
    thresholds: dict[str, float]
    route_sha256: str


MODELS = {"none": "none", "recorded": "synthetic-recorded", "jev": "jev-1.14.0"}
# Digests of the tooling-owned set and request rubrics at S1-T08, not live evidence.
JEV_ROUTE_SHA256 = "d4207e9f26433022974df0ae94512b2846baccef21b1d9e2749bbeba8cc01159"
CASE_SHA256 = "1e728d77bc99e2bfad09efb980a5bf147e7f7c52c0404dfdb747498a8da77d76"
RUBRIC_SHA256 = "032d1563aedb1dad27fae2e444b8bc6780797251750b3015013f955600086ebc"


def identity(
    provider: str,
    model: str,
    rubric: str,
    cases: bytes,
    thresholds: dict[str, float],
    route: str | None = None,
) -> Identity:
    return dict(
        provider=provider,
        model=model,
        rubric_sha256=digest(rubric),
        cases_sha256=hashlib.sha256(cases).hexdigest(),
        thresholds=dict(thresholds),
        route_sha256=digest(provider if route is None else route),
    )


def configured(provider: str) -> Identity:
    return dict(
        provider=provider,
        model=MODELS[provider],
        rubric_sha256=RUBRIC_SHA256,
        cases_sha256=CASE_SHA256,
        thresholds={"high": 0.90, "low": 0.10},
        route_sha256=JEV_ROUTE_SHA256 if provider == "jev" else digest(provider),
    )


def compare(actual: Mapping[str, object], expected: Mapping[str, object]) -> str:
    return "match" if actual == expected else "requalify"
