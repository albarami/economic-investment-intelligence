"""Small attribute-aware HTML tree; preserves the portal's div-inside-tr markup."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser


class ShapeError(ValueError):
    """Closed structural reason only, never document content."""


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    def text(self) -> str:
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def nodes(self) -> list[Node]:
        return [c for c in self.children if isinstance(c, Node)]

    def descendants(self) -> list[Node]:
        return [n for c in self.nodes() for n in (c, *c.descendants())]

    def matches(self, selector: str) -> bool:
        # Closed simple selectors, no expressions, pseudo-selectors or wildcards.
        match = re.fullmatch(
            r'([a-z][a-z0-9-]*)(?:#([\w-]+))?((?:\.[\w-]+)*)(?:\[([\w-]+)="([^"\]]*)"\])?',
            selector,
        )
        if match is None:
            raise ShapeError("schema_missing")
        tag, ident, classes, attr, value = match.groups()
        return (
            self.tag == tag
            and (ident is None or self.attrs.get("id") == ident)
            and set(classes.lstrip(".").split(".") if classes else ())
            <= set((self.attrs.get("class") or "").split())
            and (attr is None or self.attrs.get(attr) == value)
        )

    def find(self, selector: str) -> list[Node]:
        parts = selector.split(" > ")
        nodes = [n for n in self.descendants() if n.matches(parts[0])]
        for part in parts[1:]:
            nodes = [n for parent in nodes for n in parent.nodes() if n.matches(part)]
        return nodes

    def one(self, selector: str) -> Node:
        found = self.find(selector)
        if len(found) != 1:
            raise ShapeError("schema_missing")
        return found[0]


class Tree(HTMLParser):
    def __init__(self, body: bytes) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.current = self.root
        try:
            self.feed(body.decode("utf-8"))
            self.close()
        except UnicodeError:
            raise ShapeError("schema_missing") from None
        if self.current != self.root:
            raise ShapeError("schema_missing")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len(dict(attrs)) != len(attrs):
            raise ShapeError("schema_missing")
        node = Node(tag, dict(attrs), parent=self.current)
        self.current.children.append(node)
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.current.tag == tag:
            self.current = self.current.parent or self.root

    def handle_endtag(self, tag: str) -> None:
        # Omitted end tags occur in real HTML. Close only an open matching ancestor.
        node: Node | None = self.current
        while node is not None and node != self.root:
            if node.tag == tag:
                self.current = node.parent or self.root
                return
            node = node.parent

    def handle_data(self, data: str) -> None:
        self.current.children.append(data)


def table_rows(table: Node, headers: list[str]) -> list[list[Node]]:
    rows = table.find("thead > tr")
    if len(rows) != 1:
        raise ShapeError("schema_missing")
    heads = rows[0].nodes()
    if (
        any(c.tag != "th" for c in heads)
        or [c.text().strip() for c in heads] != headers
    ):
        raise ShapeError("schema_missing")
    result = []
    for row in table.find("tbody > tr"):
        cells = row.nodes()
        if len(cells) != len(headers) or any(c.tag != "td" for c in cells):
            raise ShapeError("schema_missing")
        result.append(cells)
    for c in [*heads, *(c for row in result for c in row)]:
        if c.find("table") or any(
            c.attrs.get(k, "1") != "1" for k in ("colspan", "rowspan")
        ):
            raise ShapeError("schema_missing")
    return result
