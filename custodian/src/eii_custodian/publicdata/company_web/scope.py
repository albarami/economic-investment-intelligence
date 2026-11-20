"""Run manifest and exact request frame; never mutates the static allow-list."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..fetch.allowlist import approve_closed, canonical_https, host_of
from ..fetch.receipts import sha256_hex
from ..fetch.snapshots import utc
from .contracts import WebError, checked_url, digest, dump, loads

_FRAME: ContextVar[tuple[str, ...] | None] = ContextVar(
    "company_web_frame", default=None
)


def identity(value: Mapping[str, Any]) -> dict[str, str]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"maker", "tool", "model", "run_id"}
        or any(not isinstance(v, str) or not v.strip() for v in value.values())
    ):
        raise WebError("identity_refused")
    return {key: str(value[key]) for key in value}


@dataclass(frozen=True)
class Manifest:
    data: dict[str, Any]
    sha256: str
    content_sha256: str
    raw: bytes = field(repr=False)

    @classmethod
    def from_data(cls, value: Mapping[str, Any]) -> Manifest:
        # Copy through canonical JSON: the caller cannot mutate the reviewed input.
        data = json.loads(json.dumps(value))
        try:
            if (
                set(data)
                != {
                    "version",
                    "reviewed_by",
                    "reviewed_utc",
                    "provider",
                    "companies",
                    "access",
                    "selectors",
                }
                or type(data["version"]) is not int
                or data["version"] != 1
            ):
                raise WebError("manifest_refused")
            identity(data["reviewed_by"])
            utc(data["reviewed_utc"])
            provider = data["provider"]
            if (
                set(provider)
                != {
                    "host",
                    "path",
                    "result_selector",
                    "attribute",
                    "visitor_readable",
                    "keyless",
                }
                or provider["keyless"] is not True
                or provider["visitor_readable"] is not True
                or provider["attribute"] != "href"
            ):
                raise WebError("provider_refused")
            checked_url(canonical_https(provider["host"], provider["path"], ()))
            from ..fetch.page_html import Node

            Node("a").matches(provider["result_selector"])
            if (
                not isinstance(data["companies"], dict)
                or not 1 <= len(data["companies"]) <= 10
            ):
                raise WebError("batch_refused")
            hosts = {provider["host"]}
            for key, urls in data["companies"].items():
                if (
                    not key
                    or not isinstance(urls, list)
                    or len(urls) > 3
                    or len(set(urls)) != len(urls)
                ):
                    raise WebError("batch_refused")
                for url in urls:
                    checked_url(url)
                    hosts.add(host_of(url))
            if set(data["access"]) != hosts:
                raise WebError("access_record_missing")
            for host, access in data["access"].items():
                if (
                    set(access) != {"terms_url", "robots_url", "delay_seconds"}
                    or type(access["delay_seconds"]) not in (int, float)
                    or not 2 <= access["delay_seconds"] <= 3600
                ):
                    raise WebError("access_record_refused")
                for name in ("terms_url", "robots_url"):
                    url = access[name]
                    if not isinstance(url, str) or (
                        url and (checked_url(url) != url or host_of(url) != host)
                    ):
                        raise WebError("access_record_refused")
                if (
                    access["robots_url"]
                    and urlsplit(access["robots_url"]).path != "/robots.txt"
                ):
                    raise WebError("access_record_refused")
            if set(data["selectors"]) - hosts:
                raise WebError("selector_refused")
            for selectors in data["selectors"].values():
                if (
                    set(selectors) != {"block", "fields"}
                    or set(selectors["fields"])
                    - {"name", "address", "website", "activity"}
                    or "name" not in selectors["fields"]
                ):
                    raise WebError("selector_refused")
                for selector in (selectors["block"], *selectors["fields"].values()):
                    Node("a").matches(selector)
        except (KeyError, TypeError, ValueError):
            raise WebError("manifest_refused") from None
        return cls(data, digest(data), digest(data), dump(data))

    @classmethod
    def load(cls, path: Path, expected_sha256: str) -> Manifest:
        try:
            body = path.read_bytes()
            if sha256_hex(body) != expected_sha256:
                raise WebError("manifest_hash_mismatch")
            plan = cls.from_data(loads(body))
            return cls(plan.data, expected_sha256, plan.content_sha256, body)
        except (OSError, TypeError, ValueError):
            raise WebError("manifest_refused") from None

    def verify(self) -> None:
        if (
            digest(self.data) != self.content_sha256
            or sha256_hex(self.raw) != self.sha256
        ):
            raise WebError("manifest_hash_mismatch")

    def search_allowed(self, url: str, name: str) -> bool:
        self.verify()
        provider = self.data["provider"]
        try:
            return (
                checked_url(url, query=True) == url
                and urlsplit(url).path == provider["path"]
                and approve_closed(
                    url,
                    hosts=frozenset({provider["host"]}),
                    selectors=(("q", name + " Qatar"),),
                ).ok
            )
        except WebError:
            return False

    def urls(self, company_key: str) -> tuple[str, ...]:
        self.verify()
        if company_key not in self.data["companies"]:
            raise WebError("company_binding_refused")
        return tuple(self.data["companies"][company_key])


def active() -> bool:
    return _FRAME.get() is not None


def allowed(url: str) -> bool:
    frame = _FRAME.get()
    return frame is not None and str(url) in frame


@contextmanager
def company_requests(
    manifest: Manifest,
    company_key: str,
    *,
    search_url: str = "",
    company_name: str = "",
    access_host: str = "",
) -> Iterator[tuple[str, ...]]:
    urls = manifest.urls(company_key)
    if search_url:
        if not manifest.search_allowed(search_url, company_name):
            raise WebError("query_refused")
        urls = (search_url,)
    if access_host:
        if access_host not in {host_of(u) for u in urls}:
            raise WebError("host_refused")
        access = manifest.data["access"][access_host]
        urls = tuple(access[k] for k in ("terms_url", "robots_url") if access[k])
    previous = _FRAME.get()
    if previous is not None and not set(urls) <= set(previous):
        raise WebError("scope_widening_refused")
    token = _FRAME.set(urls)
    try:
        yield urls
    finally:
        _FRAME.reset(token)


def query_name(value: str) -> str:
    if re.search(r"[;$`|&<>\\\r\n]", value):
        raise WebError("query_refused")
    return value
