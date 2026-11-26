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
        self.language = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open a region or a captured element."""
        attr = {name: value or "" for name, value in attrs}
        if tag == "html":
            self.language = attr.get("lang", "").split("-")[0].casefold()
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
        text = _collapse(cap.parts)
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
    language: str = "",
) -> tuple[dict[str, object], ...] | InvestmentFailure:
    """Return the page record and its blocks, or one source failure."""
    try:
        text = body.decode("utf-8")
    except UnicodeError:
        return fail(envelope, "unreadable", "utf-8", "not utf-8")
    collector = _Collector(furniture, envelope.page_url)
    collector.feed(text)
    collector.close()
    if language and (language not in {"en", "ar"} or collector.language != language):
        return fail(envelope, "page_language", language, "missing or different")
    if not collector.saw_main:
        return fail(envelope, "no_main", "main", "absent")
    if collector.problem == "empty_heading":
        return fail(envelope, "empty_heading", "heading text", "absent")
    if collector.problem == "table":
        return fail(envelope, "unsupported_shape", "no table", collector.problem)
    if collector.unfinished():
        return fail(envelope, "truncated", "closed page", "cut")
    for event in collector.events:
        if any(isinstance(value, str) and bare_digit_run(value) for value in event[1:]):
            return fail(envelope, "identifier_shape", "no bare digit run", "text")
    built = _assemble(
        collector.events, rule, minimum_blocks, minimum_paragraphs, envelope
    )
    if isinstance(built, InvestmentFailure):
        return built
    rows = tuple(_lineage(row, envelope) for row in built)
    if language:
        for row in rows:
            row["language"] = language
    return rows


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


# Decision 0029 item 2: the version fixes these structural lists. No CSS or
# script is evaluated. The reviewed record reader supplies its furniture classes.
# @2 (L-1856): they gate <section> only, a <button> inside a heading and outside
# any <form> is text, and a line's raw text collapses before trimming.
_PAGE_EXCLUDED = frozenset(
    {
        "header",
        "nav",
        "footer",
        "aside",
        "script",
        "style",
        "svg",
        "form",
        "input",
        "select",
        "option",
        "textarea",
        "label",
        "noscript",
        "template",
    }
)
_PAGE_FURNITURE = frozenset(
    {"cookie", "cookies", "consent", "cookie-banner", "side-menu"}
)
_PAGE_BLOCKS = frozenset(
    {
        "main",
        "article",
        "section",
        "div",
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
        "blockquote",
        "pre",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "td",
        "th",
        "figure",
        "figcaption",
        "br",
        "hr",
    }
)
_PAGE_HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


def _collapse(parts: list[str]) -> str:
    """Raw text parts joined in order, whitespace collapsed, ends trimmed."""
    return _SPACE.sub(" ", "".join(parts)).strip()


class _PageText(HTMLParser):
    """Visible text nodes in source order; block edges separate nonempty lines."""

    def __init__(self, furniture: frozenset[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.furniture = furniture
        self.stack: list[tuple[str, bool, bool]] = []
        self.languages: list[str] = []
        self.english: list[str] = []
        self.lines: list[list[str]] = [[]]
        self.titles: list[str] = []
        self.title_parts: list[str] | None = None
        self.main_count = 0
        self.closed_main = False
        self.closed_html = False

    def visible(self) -> bool:
        return any(main for _, main, _ in self.stack) and not any(
            skip for _, _, skip in self.stack
        )

    def boundary(self) -> None:
        if self.lines[-1]:
            self.lines.append([])

    def _in_heading(self) -> bool:
        """A heading element is open on the stack."""
        return any(tag in _PAGE_HEADINGS for tag, _, _ in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "html":
            self.languages.append((attr.get("lang") or "").split("-")[0].casefold())
        if (
            tag == "link"
            and "alternate" in (attr.get("rel") or "").split()
            and attr.get("hreflang") == "en"
            and attr.get("href")
        ):
            self.english.append(str(attr["href"]))
        classes = set((attr.get("class") or "").split())
        skip = (
            tag in _PAGE_EXCLUDED
            or (tag == "button" and not self._in_heading())
            or "hidden" in attr
            or (attr.get("aria-hidden") or "").casefold() == "true"
            or bool(classes & _PAGE_FURNITURE)
            or (tag == "section" and bool(classes & self.furniture))
        )
        if tag not in _VOID:
            self.stack.append((tag, tag == "main", skip))
        if tag == "main":
            self.main_count += 1
        if self.visible() and not skip:
            if tag in _PAGE_BLOCKS:
                self.boundary()
            if tag == "h1":
                self.title_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.visible():
            if tag == "h1" and self.title_parts is not None:
                self.titles.append(_collapse(self.title_parts))
                self.title_parts = None
            if tag in _PAGE_BLOCKS:
                self.boundary()
        if tag == "main":
            self.closed_main = True
        if tag == "html":
            self.closed_html = True
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        import unicodedata

        if self.visible():
            text = unicodedata.normalize("NFC", data)
            self.lines[-1].append(text)
            if self.title_parts is not None:
                self.title_parts.append(text)


def _page_decode(body: bytes, charset: str) -> str:
    """BOM, receipt charset, then page meta charset; never guess an encoding."""
    import codecs

    for marker, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    ):
        if body.startswith(marker):
            return body.decode(encoding)
    if not charset:
        meta = re.search(
            rb"<meta\b[^>]*\bcharset\s*=\s*['\"]?([A-Za-z0-9_-]+)",
            body,
            re.IGNORECASE,
        )
        if meta is None:
            raise ValueError("encoding absent")
        charset = meta[1].decode("ascii")
    return body.decode(charset)


def page_refusal(check: str, url: str = "") -> InvestmentFailure:
    """Release reports identify the check without copying a rejected token."""
    return InvestmentFailure(
        1, "investqa_pages", url, check, "verified page", "refused"
    )


def extract_page(
    body: bytes,
    *,
    page_url: str,
    page_language: str,
    sequence: int | None,
    retrieved_on: str,
    page_sha256: str,
    manifest_sha256: str,
    charset: str = "",
    furniture: frozenset[str] = frozenset(),
    extractor: str = "investqa_page_text@2",
) -> dict[str, object] | InvestmentFailure:
    """Decision 0029: extract one exact page row, or refuse the whole quotation."""
    import hashlib
    import unicodedata
    from datetime import date

    from .investment_contracts import PAGE_EXTRACTOR

    if extractor != PAGE_EXTRACTOR:
        return page_refusal("page_extractor_version", page_url)
    digest = hashlib.sha256(body).hexdigest()
    if digest != page_sha256 or digest != manifest_sha256:
        return page_refusal("page_hash_mismatch", page_url)
    try:
        text = _page_decode(body, charset)
        date.fromisoformat(retrieved_on)
    except (UnicodeError, LookupError, ValueError):
        return page_refusal("page_decode", page_url)
    collector = _PageText(furniture)
    collector.feed(text)
    collector.close()
    if page_language not in {"en", "ar"} or collector.languages != [page_language]:
        return page_refusal("page_language", page_url)
    if (
        collector.main_count != 1
        or not collector.closed_main
        or not collector.closed_html
        or collector.stack
    ):
        return page_refusal("page_truncated", page_url)
    page_text = "\n".join(
        part for part in (_collapse(line) for line in collector.lines) if part
    )
    runs = re.findall(r"\d+", page_text)
    if any(len(run) in {8, 11} for run in runs):
        return page_refusal("page_identifier_shape", page_url)
    if re.search(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", page_text) or any(
        7 <= sum(unicodedata.category(char) == "Nd" for char in match) <= 15
        for match in re.findall(r"\+?\d+(?:[ ()-]\d+)*", page_text)
        if not (
            re.fullmatch(r"(?:19|20)[0-9]{2}-(?:19|20)[0-9]{2}", match)
            and match[:4] <= match[5:]
        )
    ):
        return page_refusal("page_contact_shape", page_url)
    if re.search(r"SYN-[A-Z]-|CANARY", page_text, re.IGNORECASE):
        return page_refusal("page_release_token", page_url)
    if len(set(collector.english)) > 1:
        return page_refusal("page_key", page_url)
    key_url = urljoin(page_url, collector.english[0]) if collector.english else page_url
    key = re.sub(r"[^a-z0-9]+", "_", urlsplit(key_url).path.casefold()).strip("_")
    if not key or not key[0].isalpha():
        return page_refusal("page_key", page_url)
    if sequence is not None and (type(sequence) is not int or sequence < 1):
        return page_refusal("page_sequence", page_url)
    return {
        "page_key": key,
        "page_language": page_language,
        "sequence": sequence,
        "page_title": collector.titles[-1] if collector.titles else None,
        "page_url": page_url,
        "retrieved_on": retrieved_on,
        "page_sha256": digest,
        "extractor": PAGE_EXTRACTOR,
        "page_text": page_text,
        "source_id": "investqa_pages",
    }
