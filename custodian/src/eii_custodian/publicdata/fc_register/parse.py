"""Positive reconstruction before any write; state and other markup stay in memory."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..fetch.page_html import ShapeError, Tree
from ..fetch.page_schema import json_body
from .constants import COLUMNS, PAGERS, PROJECTION, SHAPE, TARGETS


def canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode()


@dataclass(frozen=True)
class Projected:
    body: bytes
    fields: Mapping[str, str] = field(repr=False)
    target: str | None


def fragment(body: bytes) -> dict[str, Any]:
    """Accept only the canonical, versioned company fields and closed progress."""
    value = json_body(body)
    if not isinstance(value, dict) or set(value) != {"projection", "rows", "progress"}:
        raise ShapeError("schema_missing")
    if value["projection"] != PROJECTION or canonical(value) != body:
        raise ShapeError("schema_missing")
    progress = value["progress"]
    if (
        not isinstance(progress, dict)
        or set(progress) != {"shown_page", "continuation"}
        or type(progress["shown_page"]) is not int
        or progress["shown_page"] < 1
        or progress["continuation"] not in {"next", "terminal"}
    ):
        raise ShapeError("paging_incomplete")
    if not isinstance(value["rows"], list) or not value["rows"]:
        raise ShapeError("schema_missing")
    for row in value["rows"]:
        if (
            not isinstance(row, dict)
            or set(row) != {c[0] for c in COLUMNS}
            or any(not isinstance(v, str) for v in row.values())
            or not row["company_name"].strip()
            or not row["qfc_number"].strip()
        ):
            raise ShapeError("schema_missing")
    return value


def project(body: bytes, shape: Mapping[str, Any]) -> Projected:
    if dict(shape) != SHAPE:
        raise ShapeError("schema_missing")
    root = Tree(body).root
    pane = root.one(shape["pane"])
    rows = []
    for card in pane.find(shape["card"]):
        row = {}
        if card.one("span.pr-num-label").text().strip() != "QFC Number":
            raise ShapeError("schema_missing")
        for name, selector in shape["fields"].items():
            node = card.one(selector)
            # Never flatten an undeclared nested node into an approved field.
            if node.nodes():
                raise ShapeError("schema_missing")
            row[name] = node.text().strip()
        rows.append(row)
    progress = []
    targets = []
    for pager_id, target in zip(PAGERS, TARGETS, strict=True):
        pager = root.one("span#" + pager_id)
        current = [n for n in pager.nodes() if n.tag == "span"]
        if len(current) != 1 or not re.fullmatch(
            r"[1-9][0-9]*", current[0].text().strip()
        ):
            raise ShapeError("paging_incomplete")
        next_nodes = [n for n in pager.find("a") if n.text().strip() == ">"]
        if len(next_nodes) > 1:
            raise ShapeError("paging_incomplete")
        continuation = "terminal"
        if next_nodes:
            control = next_nodes[0]
            href = control.attrs.get("href")
            if href == "javascript:__doPostBack('" + target + "','')":
                continuation = "next"
                targets.append(target)
            elif (
                href is not None
                or "aspNetDisabled" not in (control.attrs.get("class") or "").split()
            ):
                raise ShapeError("schema_missing")
        if continuation == "terminal" and any(
            n.text().strip().isascii()
            and n.text().strip().isdigit()
            and int(n.text().strip()) > int(current[0].text().strip())
            and n.attrs.get("href") is not None
            for n in pager.find("a")
        ):
            raise ShapeError("paging_incomplete")
        progress.append(
            {"shown_page": int(current[0].text().strip()), "continuation": continuation}
        )
    if progress[0] != progress[1]:
        raise ShapeError("paging_incomplete")
    forms = root.find("form")
    if len(forms) != 1 or (forms[0].attrs.get("method") or "").lower() != "post":
        raise ShapeError("schema_missing")
    fields: dict[str, str] = {}
    for node in forms[0].find("input"):
        if (node.attrs.get("type") or "").lower() != "hidden":
            continue
        name, val = node.attrs.get("name"), node.attrs.get("value")
        if (
            not isinstance(name, str)
            or name not in shape["form_fields"]
            or name in fields
            or not isinstance(val, str)
        ):
            raise ShapeError("schema_missing")
        fields[name] = val
    if (
        set(fields) != set(shape["form_fields"])
        or fields["__EVENTTARGET"]
        or fields["__EVENTARGUMENT"]
    ):
        raise ShapeError("schema_missing")
    result = canonical(
        {"projection": PROJECTION, "rows": rows, "progress": progress[0]}
    )
    fragment(result)
    return Projected(result, fields, targets[0] if targets else None)
