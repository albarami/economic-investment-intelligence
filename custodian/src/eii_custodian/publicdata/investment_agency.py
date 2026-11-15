"""Read one agency page as a title and heading-led blocks.

Content is what lies inside main and outside the furniture. Text is the
published text: character references decoded, white space collapsed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from eii_custodian.publicdata.investment_contracts import (
    PROVENANCE_PUBLIC,
    InvestmentFailure,
    KindRule,
    SourceEnvelope,
    bare_digit_run,
    fail,
)

_SPACE = re.compile(r"\s+")
_VOID = frozenset({"br", "img", "input", "meta", "link", "hr", "source", "wbr"})
_EXCLUDED = frozenset({"header", "nav", "footer", "script", "style"})
_CAPTURED = frozenset({"h1", "h2", "h3", "h4", "h5", "p", "li", "a"})
_HEADING = {"h2": 2, "h3": 3, "h4": 4, "h5": 5}


@dataclass
class _Cap:
    tag: str
    href: str
    parts: list[str] = field(default_factory=list)
    has_p: bool = False


@dataclass
class _Block:
    level: int
    heading: str
    ordinal: int
    texts: list[str] = field(default_factory=list)
    links: list[dict[str, object]] = field(default_factory=list)


class _Collector(HTMLParser):
    """Collect content events. The first problem sticks."""

    def __init__(self, furniture: frozenset[str], page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._furniture = furniture
        self._page_url = page_url
        self._host = (urlsplit(page_url).hostname or "").casefold()
        self._main = 0
        self._skip = 0
        self._stack: list[tuple[str, bool, bool]] = []
        self._capture: list[_Cap] = []
        self.saw_main = False
        self.saw_main_end = False
        self.saw_html_end = False
        self.problem: str | None = None
        self.events: list[tuple[object, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open a region or a captured element."""
        attr = {name: value or "" for name, value in attrs}
        self._open(tag, attr)
        if self.problem is not None or (tag in _VOID and tag != "br"):
            return
        if tag == "br" and self._in_content():
            for cap in self._capture:
                cap.parts.append(" ")
            return
        if not self._in_content():
            return
        if tag == "table":
            self.problem = tag
            return
        if tag == "p":
            for cap in self._capture:
                if cap.tag == "li":
                    cap.has_p = True
        if tag in _CAPTURED:
            self._capture.append(_Cap(tag, attr.get("href", "")))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Treat a closed empty tag as a start, then an end when it has content."""
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        """Emit a finished element, then close its region."""
        if tag == "main":
            self.saw_main_end = True
        if tag == "html":
            self.saw_html_end = True
        if self._capture and self._capture[-1].tag == tag:
            cap = self._capture.pop()
            if self.problem is None:
                self._emit(cap)
        self._close(tag)

    def handle_data(self, data: str) -> None:
        """Keep text only while a captured element is open in the content."""
        if not self._in_content():
            return
        for cap in self._capture:
            cap.parts.append(data)

    def unfinished(self) -> bool:
        """True unless the one main and the html end were seen, with nothing captured still open."""
        return (
            not self.saw_main_end
            or self._main != 0
            or bool(self._capture)
            or not self.saw_html_end
        )

    def _in_content(self) -> bool:
        return self._main > 0 and self._skip == 0

    def _open(self, tag: str, attr: dict[str, str]) -> None:
        if tag in _VOID:
            return
        opened_main = tag == "main"
        if opened_main:
            self.saw_main = True
            self._main += 1
        classes = set(attr.get("class", "").split())
        furniture = tag == "section" and bool(classes & self._furniture)
        excluded = tag in _EXCLUDED or furniture or tag == "form"
        opened_skip = excluded and self._main > 0
        if opened_skip:
            self._skip += 1
        self._stack.append((tag, opened_main, opened_skip))

    def _close(self, tag: str) -> None:
        if tag in _VOID:
            return
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] != tag:
                continue
            for _name, opened_main, opened_skip in self._stack[index:]:
                if opened_main:
                    self._main -= 1
                if opened_skip:
                    self._skip -= 1
            del self._stack[index:]
            return

    def _emit(self, cap: _Cap) -> None:
        text = _SPACE.sub(" ", "".join(cap.parts)).strip()
        if cap.tag == "h1":
            if text == "":
                self.problem = self.problem or "empty_heading"
            self.events.append(("h1", text))
            return
        if cap.tag in _HEADING:
            if text == "":
                self.problem = self.problem or "empty_heading"
            self.events.append(("heading", _HEADING[cap.tag], text))
            return
        if cap.tag == "p":
            self.events.append(("p", text))
            return
        if cap.tag == "li" and not cap.has_p:
            self.events.append(("li", text))
            return
        href = cap.href.strip()
        if cap.tag != "a" or href == "":
            return
        absolute = urljoin(self._page_url, href)
        parts = urlsplit(absolute)
        host = (parts.hostname or "").casefold()
        self.events.append(
            (
                "a",
                {
                    "document": parts.path.endswith(".pdf"),
                    "outside": host != self._host,
                    "text": text,
                    "url": absolute,
                },
            )
        )


def parse_agency(
    body: bytes,
    *,
    rule: KindRule,
    furniture: frozenset[str],
    minimum_blocks: int,
    minimum_paragraphs: int,
    envelope: SourceEnvelope,
) -> tuple[dict[str, object], ...] | InvestmentFailure:
    """Return the page record and its blocks, or one source failure."""
    try:
        text = body.decode("utf-8")
    except UnicodeError:
        return fail(envelope, "unreadable", "utf-8", "not utf-8")
    collector = _Collector(furniture, envelope.page_url)
    collector.feed(text)
    collector.close()
    if not collector.saw_main:
        return fail(envelope, "no_main", "main", "absent")
    if collector.problem == "empty_heading":
        return fail(envelope, "empty_heading", "heading text", "absent")
    if collector.problem == "table":
        return fail(envelope, "unsupported_shape", "no table", collector.problem)
    if collector.unfinished():
        return fail(envelope, "truncated", "closed page", "cut")
    built = _assemble(
        collector.events, rule, minimum_blocks, minimum_paragraphs, envelope
    )
    if isinstance(built, InvestmentFailure):
        return built
    return tuple(_lineage(row, envelope) for row in built)


def _assemble(
    events: list[tuple[object, ...]],
    rule: KindRule,
    minimum_blocks: int,
    minimum_paragraphs: int,
    envelope: SourceEnvelope,
) -> list[dict[str, object]] | InvestmentFailure:
    titles: list[str] = []
    blocks: list[_Block] = []
    current: _Block | None = None
    paragraphs = 0
    for event in events:
        kind = event[0]
        if kind == "h1":
            titles.append(str(event[1]))
            current = None
            continue
        if kind == "heading" and isinstance(event[1], int):
            current = _Block(event[1], str(event[2]), len(blocks) + 1)
            blocks.append(current)
            continue
        if kind == "p":
            paragraphs += 1
            if current is not None:
                current.texts.append(str(event[1]))
            continue
        if current is None:
            continue
        if kind == "li":
            current.texts.append(str(event[1]))
        elif kind == "a" and isinstance(event[1], dict):
            current.links.append(event[1])
    if not titles:
        return fail(envelope, "no_title", "h1", "absent")
    if minimum_paragraphs > 0 and paragraphs < minimum_paragraphs:
        return fail(envelope, "paragraph", str(minimum_paragraphs), str(paragraphs))
    if minimum_blocks > 0:
        found = sum(1 for block in blocks if block.level == rule.leading_level)
        if found < minimum_blocks:
            return fail(envelope, "leading_level", str(minimum_blocks), str(found))
    page_key = _page_key(envelope)
    if isinstance(page_key, InvestmentFailure):
        return page_key
    title = titles[-1]
    refused = _digits(title, envelope)
    if refused is not None:
        return refused
    rows = [_page_row(rule.page_kind, page_key, title, envelope.page_url)]
    for index, block in enumerate(blocks):
        refused = _digits(block.heading, envelope)
        if refused is not None:
            return refused
        for item in block.texts:
            refused = _digits(item, envelope)
            if refused is not None:
                return refused
        record_kind = _block_kind(rule, blocks, index)
        parent = _parent(blocks, index)
        rows.append(_block_row(record_kind, page_key, block, parent, envelope.page_url))
    return rows


def _block_kind(rule: KindRule, blocks: list[_Block], index: int) -> str:
    if rule.block_kind:
        return rule.block_kind
    block = blocks[index]
    if rule.h3_under_h4 and block.level == 3 and _under_h4(blocks, index):
        return rule.h3_under_h4
    return rule.level_kinds.get(block.level, "block")


def _under_h4(blocks: list[_Block], index: int) -> bool:
    for earlier in range(index - 1, -1, -1):
        level = blocks[earlier].level
        if level == 4:
            return True
        if level <= 2:
            return False
    return False


def _parent(blocks: list[_Block], index: int) -> int | None:
    level = blocks[index].level
    for earlier in range(index - 1, -1, -1):
        if blocks[earlier].level < level:
            return blocks[earlier].ordinal
    return None


def _page_key(envelope: SourceEnvelope) -> str | InvestmentFailure:
    """Return the page path: lower-cased host dropped, path as written, no trailing slash."""
    path = urlsplit(envelope.page_url).path.rstrip("/")
    if path == "":
        return fail(envelope, "key_shape", "page path", "absent")
    return path


def _digits(text: str, envelope: SourceEnvelope) -> InvestmentFailure | None:
    if bare_digit_run(text):
        return fail(envelope, "identifier_shape", "no bare digit run", "text")
    return None


def _page_row(kind: str, page_key: str, title: str, page_url: str) -> dict[str, object]:
    return {
        "record_type": kind,
        "record_key": page_key,
        "page_key": page_key,
        "title": title,
        "heading": None,
        "level": None,
        "ordinal": None,
        "parent_ordinal": None,
        "text_items": None,
        "links": None,
        "page_url": page_url,
        "provenance": PROVENANCE_PUBLIC,
        "join_key": "",
    }


def _block_row(
    kind: str,
    page_key: str,
    block: _Block,
    parent: int | None,
    page_url: str,
) -> dict[str, object]:
    return {
        "record_type": kind,
        "record_key": f"{page_key}:{block.ordinal}",
        "page_key": page_key,
        "title": None,
        "heading": block.heading,
        "level": block.level,
        "ordinal": block.ordinal,
        "parent_ordinal": parent,
        "text_items": json.dumps(block.texts, ensure_ascii=True, separators=(",", ":")),
        "links": json.dumps(
            block.links, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ),
        "page_url": page_url,
        "provenance": PROVENANCE_PUBLIC,
        "join_key": "",
    }


def _lineage(row: dict[str, object], envelope: SourceEnvelope) -> dict[str, object]:
    row.update(
        {
            "source_id": envelope.source_id,
            "publisher": envelope.publisher,
            "page_url": envelope.page_url,
            "licence_id": envelope.licence_id,
            "licence_basis": envelope.licence_basis,
            "decision_record": envelope.decision_record,
            "terms_sha256": envelope.terms_sha256,
            "terms_url": envelope.terms_url,
            "retrieved_utc": envelope.retrieved_utc,
            "page_sha256": envelope.page_sha256,
            "method": envelope.method,
            "method_version": envelope.method_version,
        }
    )
    return row
