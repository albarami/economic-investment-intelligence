"""Declared structured blocks only; source text is never mapped to a spine."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..fetch.award_checks import normalise_name
from ..fetch.page_html import Node, ShapeError, Tree
from ..fetch.receipts import sha256_hex
from .contracts import (
    VERSION,
    Candidate,
    Company,
    Extraction,
    WebError,
    digest,
    dump,
    lineage,
    loads,
    safe_text,
)

ORGANIZATIONS = frozenset({"Organization", "LocalBusiness"})
PERSONAL = frozenset(
    {
        "Person",
        "Employee",
        "employee",
        "employees",
        "founder",
        "founders",
        "member",
        "members",
        "salary",
        "jobTitle",
    }
)
ADDRESS_FIELDS = (
    "streetAddress",
    "postOfficeBoxNumber",
    "addressLocality",
    "addressRegion",
    "postalCode",
    "addressCountry",
)


def _types(value: object) -> set[str]:
    values = value if isinstance(value, list) else [value]
    return {str(v).rsplit("/", 1)[-1] for v in values}


def _blocks(
    value: object, personal: bool = False, schema: bool = False
) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [block for v in value for block in _blocks(v, personal, schema)]
    if not isinstance(value, dict):
        return []
    if "@context" in value:
        schema = value["@context"] in (
            "https://schema.org",
            "https://schema.org/",
            "http://schema.org",
            "http://schema.org/",
        )
    kinds = _types(value.get("@type"))
    current_personal = personal or bool(kinds & PERSONAL)
    result = []
    if kinds & ORGANIZATIONS:
        if current_personal or kinds - ORGANIZATIONS or set(value) & PERSONAL:
            raise WebError("personal_context_refused")
        if schema or value.get("@type") in (
            "https://schema.org/Organization",
            "https://schema.org/LocalBusiness",
            "http://schema.org/Organization",
            "http://schema.org/LocalBusiness",
        ):
            result.append(value)
    for key, child in value.items():
        if isinstance(child, (dict, list)):
            result.extend(_blocks(child, current_personal or key in PERSONAL, schema))
    return result


def _ancestors(node: Node) -> list[Node]:
    result = []
    parent = node.parent
    while parent:
        result.append(parent)
        parent = parent.parent
    return result


def _personal_html(node: Node) -> bool:
    return any(
        _types(n.attrs.get("itemtype")) & PERSONAL
        or n.attrs.get("itemprop") in PERSONAL
        for n in (node, *_ancestors(node))
    )


def _micro(node: Node) -> dict[str, Any]:
    if _personal_html(node):
        raise WebError("personal_context_refused")
    block: dict[str, Any] = {
        "@type": (node.attrs.get("itemtype") or "").rsplit("/", 1)[-1]
    }
    for child in node.descendants():
        prop = child.attrs.get("itemprop")
        if prop in PERSONAL:
            raise WebError("personal_context_refused")
        if prop not in {"name", "address", "url", "description", "isicV4", "naics"}:
            continue
        # Do not read a descendant field from a nested item scope.
        if any(
            p is not node and "itemscope" in p.attrs
            for p in _ancestors(child)
            if p in node.descendants()
        ):
            continue
        if prop in block:
            raise WebError("ambiguous_field")
        if prop == "address":
            if (child.attrs.get("itemtype") or "").rsplit("/", 1)[
                -1
            ] != "PostalAddress":
                raise WebError("address_refused")
            address: dict[str, Any] = {"@type": "PostalAddress"}
            for part in child.descendants():
                name = part.attrs.get("itemprop")
                if name in ADDRESS_FIELDS:
                    if name in address:
                        raise WebError("ambiguous_field")
                    address[str(name)] = part.attrs.get("content") or part.text()
            block[prop] = address
        else:
            block[str(prop)] = (
                child.attrs.get("href")
                if prop == "url"
                else child.attrs.get("content") or child.text()
            )
    return block


def _fields(block: Mapping[str, Any]) -> dict[str, str]:
    values = {"name": safe_text("name", block.get("name"))}
    address = block.get("address")
    if address is not None:
        if (
            not isinstance(address, dict)
            or _types(address.get("@type")) != {"PostalAddress"}
            or set(address) - {"@type", *ADDRESS_FIELDS}
        ):
            raise WebError("address_refused")
        parts = [
            safe_text("address", address[k]) for k in ADDRESS_FIELDS if address.get(k)
        ]
        if parts:
            values["address"] = ", ".join(parts)
    if block.get("url"):
        values["website"] = safe_text("website", block["url"])
    activities = [
        safe_text("activity", block[k])
        for k in ("isicV4", "naics", "description")
        if block.get(k)
    ]
    if activities:
        values["activity"] = "; ".join(activities)
    return values


def extract(
    body: bytes,
    company: Company,
    meta: Mapping[str, Any],
    *,
    selectors: Mapping[str, Any] | None = None,
    selectors_reviewed: bool = False,
) -> Extraction:
    lineage(body, meta)
    try:
        root = Tree(body).root
        blocks = []
        for node in root.find('script[type="application/ld+json"]'):
            selected = _blocks(loads(node.text()))
            if selected and _personal_html(node):
                raise WebError("personal_context_refused")
            blocks.extend(selected)
        for node in root.descendants():
            if node.attrs.get("itemtype") in {
                "https://schema.org/Organization",
                "https://schema.org/LocalBusiness",
                "http://schema.org/Organization",
                "http://schema.org/LocalBusiness",
            }:
                blocks.append(_micro(node))
        if selectors is not None:
            if not selectors_reviewed or set(selectors) != {"block", "fields"}:
                raise WebError("selector_refused")
            selected_node = root.one(selectors["block"])
            if _personal_html(selected_node) or any(
                _personal_html(n) for n in selected_node.descendants()
            ):
                raise WebError("personal_context_refused")
            if set(selectors["fields"]) - {"name", "address", "website", "activity"}:
                raise WebError("field_refused")
            selected_fields = {
                k: safe_text(
                    k,
                    selected_node.one(v).attrs.get("href")
                    if k == "website"
                    else selected_node.one(v).text(),
                )
                for k, v in selectors["fields"].items()
            }
            if "name" not in selected_fields:
                raise WebError("selector_refused")
            if blocks:
                raise WebError("ambiguous_field")
            fields = selected_fields
        else:
            if len(blocks) != 1:
                return Extraction(
                    "ambiguous" if blocks else "no_declared_block",
                    (),
                    b"",
                    str(meta["sha256"]),
                    str(meta["fetch_url"]),
                )
            fields = _fields(blocks[0])
    except (ShapeError, json.JSONDecodeError, TypeError, KeyError, RecursionError):
        raise WebError("schema_refused") from None
    expected, observed = normalise_name(company.name), normalise_name(fields["name"])
    if observed != expected:
        # Suffix differences are ambiguous only; never an admission or alias.
        suffixes = (" llc", " wll", " w l l", " ltd", " limited")

        def base(value: str) -> str:
            return next(
                (value[: -len(s)] for s in suffixes if value.endswith(s)), value
            )

        status = "ambiguous" if base(expected) == base(observed) else "name_mismatch"
        return Extraction(status, (), b"", str(meta["sha256"]), str(meta["fetch_url"]))
    fragment = dump(fields)
    candidates = tuple(
        Candidate(
            company.key,
            key,
            value,
            str(meta["sha256"]),
            sha256_hex(fragment),
            VERSION,
            str(meta["fetch_url"]),
            str(meta["retrieved_utc"]),
            str(meta["publisher"]),
            str(meta["licence_basis"]),
            digest(meta["extractor"]),
            key in company.register_fields and company.register_fields[key] != value,
        )
        for key, value in fields.items()
    )
    for candidate in candidates:
        candidate.validate()
    return Extraction(
        "matched", candidates, fragment, str(meta["sha256"]), str(meta["fetch_url"])
    )
