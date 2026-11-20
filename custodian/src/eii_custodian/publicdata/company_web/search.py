"""Key-bound name-plus-country searches, addresses only, through shared transport."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from ..fetch.allowlist import canonical_https
from ..fetch.page_html import ShapeError, Tree
from ..fetch.receipts import sha256_hex
from ..fetch.snapshots import utc
from ..fetch.transport import Transport
from .contracts import Company, WebError, checked_url, digest
from .scope import Manifest, company_requests, query_name


@dataclass(frozen=True)
class SearchResult:
    company_key: str = field(repr=False)
    request_sha256: str
    retrieved_utc: str
    urls: tuple[str, ...] = field(repr=False)


def companies(
    register: Sequence[Mapping[str, str]], financial_names: Sequence[str]
) -> tuple[Company, ...]:
    result = []
    seen = set()
    for row in register:
        # No workbook, no guessed registration and no name-only key enrichment.
        if set(row) - {
            "company_name",
            "registration_number",
            "licence_number",
            "address",
            "website",
            "activity",
        }:
            raise WebError("register_field_refused")
        registration, licence = (
            row.get("registration_number", ""),
            row.get("licence_number", ""),
        )
        key = (
            "registration:" + registration
            if registration
            else "licence:" + licence
            if licence
            else ""
        )
        if not key or key in seen:
            raise WebError("register_key_ambiguous")
        seen.add(key)
        public = {k: row[k] for k in ("address", "website", "activity") if row.get(k)}
        result.append(
            Company(digest(key), row.get("company_name", ""), "register", public)
        )
    for name in financial_names:
        key = digest(("fc_register", name))
        if key in seen:
            raise WebError("register_key_ambiguous")
        seen.add(key)
        # This tooling identity is not a registration number or an invented one.
        result.append(Company(key, name, "fc_register", {}))
    return tuple(result)


def request_url(company: Company, manifest: Manifest) -> str:
    manifest.urls(company.key)
    provider = manifest.data["provider"]
    url = canonical_https(
        provider["host"],
        provider["path"],
        (("q", query_name(company.name) + " Qatar"),),
    )
    if not manifest.search_allowed(url, company.name):
        raise WebError("query_refused")
    return url


def search(
    company: Company,
    manifest: Manifest,
    transport: Transport,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> SearchResult:
    from ..fc_register.acquire import obstacle

    url = request_url(company, manifest)
    with company_requests(
        manifest, company.key, search_url=url, company_name=company.name
    ):
        response = transport(url)
        if any(u != url for u in (*response.hops, response.final_url)):
            raise WebError("redirect_refused")
    if obstacle(response.body):
        raise WebError("obstacle")
    try:
        root = Tree(response.body).root
        nodes = root.find(manifest.data["provider"]["result_selector"])
        urls = tuple(
            dict.fromkeys(checked_url(str(n.attrs.get("href", ""))) for n in nodes)
        )[:3]
    except (ShapeError, ValueError):
        raise WebError("search_shape_refused") from None
    stamp = clock()
    utc(stamp)
    return SearchResult(company.key, sha256_hex(url.encode()), stamp, urls)
