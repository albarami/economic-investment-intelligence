"""Read a hand-made tender list page with the standard-library parser.

Cards are found by class under ``div.page-content``. The parser keeps a
``div`` that sits directly inside ``tr``, which is how the portal writes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

_VOID = frozenset(
    {
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
        "source",
        "track",
        "wbr",
    }
)


class PageShapeError(Exception):
    """The page is not a card list of the documented shape."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass
class _El:
    tag: str
    attrs: dict[str, str]
    parent: _El | None = None
    children: list[_El | str] = field(default_factory=list)

    @property
    def classes(self) -> frozenset[str]:
        return frozenset(self.attrs.get("class", "").split())


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _El("document", {})
        self._stack: list[_El] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = _El(tag, {key: value or "" for key, value in attrs}, self._stack[-1])
        self._stack[-1].children.append(element)
        if tag not in _VOID:
            self._stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)


def _walk(node: _El) -> list[_El]:
    found: list[_El] = []
    for child in node.children:
        if isinstance(child, _El):
            found.append(child)
            found.extend(_walk(child))
    return found


def _text(node: _El) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        else:
            parts.append(_text(child))
    return "".join(parts)


def _norm(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class RawCard:
    """One card before label checks. The internal id stays inside the build."""

    internal_id: int
    tender_number: str
    title: str
    pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RawPage:
    """Language, the pager's last page, and the cards in document order."""

    language: str
    stated_last: int
    cards: tuple[RawCard, ...]


def read_raw_page(html: str) -> RawPage:
    """Parse one list page. A page with no cards returns an empty card tuple."""
    parser = _Tree()
    parser.feed(html)
    parser.close()
    html_nodes = [node for node in _walk(parser.root) if node.tag == "html"]
    if not html_nodes or not html_nodes[0].attrs.get("lang", "").strip():
        raise PageShapeError("language")
    language = html_nodes[0].attrs["lang"].strip()
    stated = _stated_last(parser.root)
    content = [
        node
        for node in _walk(parser.root)
        if node.tag == "div" and "page-content" in node.classes
    ]
    if not content:
        raise PageShapeError("page_shape")
    cards = [
        node
        for node in _walk(content[0])
        if node.tag == "div"
        and "custom-cards" in node.classes
        and "row" in node.classes
    ]
    return RawPage(language, stated, tuple(_card(node) for node in cards))


def _stated_last(root: _El) -> int:
    numbers: list[int] = []
    for node in _walk(root):
        if node.tag != "a" or "page-link" not in node.classes:
            continue
        href = node.attrs.get("href", "").rstrip("/")
        segment = href.rsplit("/", 1)[-1]
        if segment.isascii() and segment.isdecimal():
            numbers.append(int(segment))
    if not numbers:
        raise PageShapeError("pager")
    return max(numbers)


def _card(node: _El) -> RawCard:
    anchor = _title_anchor(node)
    if anchor is None:
        raise PageShapeError("title")
    href = anchor.attrs.get("href", "")
    segment = href.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if not (segment.isascii() and segment.isdecimal()):
        raise PageShapeError("internal_id")
    number_label = _number_label(anchor)
    pairs: list[tuple[str, str]] = []
    for label_node in _walk(node):
        if label_node.tag != "span" or "card-label" not in label_node.classes:
            continue
        if label_node is number_label:
            continue
        pairs.append(_pair(label_node))
    number = _norm(_text(number_label)) if number_label is not None else ""
    return RawCard(int(segment), number, _norm(_text(anchor)), tuple(pairs))


def _title_anchor(card: _El) -> _El | None:
    for node in _walk(card):
        if node.tag != "a":
            continue
        href = node.attrs.get("href", "")
        if "/TendersOnlineServices/TenderDetails/" in href:
            return node
    return None


def _number_label(anchor: _El) -> _El | None:
    node: _El | None = anchor
    while node is not None and "col-header" not in node.classes:
        node = node.parent
    if node is None:
        return None
    for child in _walk(node):
        if child.tag == "span" and "card-label" in child.classes:
            return child
    return None


def _pair(label_node: _El) -> tuple[str, str]:
    spans = [
        child
        for child in label_node.children
        if isinstance(child, _El) and child.tag == "span"
    ]
    if len(spans) >= 2:
        return _norm(_text(spans[0])), _norm(_text(spans[-1]))
    parent = label_node.parent
    values: list[str] = []
    if parent is not None:
        passed = False
        for child in parent.children:
            if child is label_node:
                passed = True
                continue
            if passed and isinstance(child, _El) and "card-title" in child.classes:
                values.append(_norm(_text(child)))
    return _norm(_text(label_node)), "|".join(value for value in values if value)
