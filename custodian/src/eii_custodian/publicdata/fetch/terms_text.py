"""SHA-256 of a terms page's normalised visible text.

The TERMS comparison uses this digest. A per-request token that lives only in
a tag attribute does not change it. Callers record the kind
``visible_text`` beside the digest and compare only that kind, so a build log
written from raw page bytes does not count as a changed terms page.
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

from eii_custodian.publicdata.fetch.receipts import sha256_hex

FINGERPRINT_VISIBLE_TEXT = "visible_text"
_SKIPPED_TAGS = frozenset({"script", "style"})
_SPACE = re.compile(r"\s+")


class _VisibleText(HTMLParser):
    """Collect text outside script, style and comments. Tags are dropped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        """Return the collected text, still with its original white space."""
        return "".join(self._parts)


def terms_text_sha256(body: bytes) -> str:
    """Return the SHA-256 hex digest of the page's normalised visible text.

    Args:
        body: Raw terms-page bytes.

    Returns:
        Hex digest of the visible text after scripts, styles, comments and
        tags are removed, HTML entities are decoded, white space is collapsed
        and the text is Unicode NFC.
    """
    parser = _VisibleText()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    collapsed = _SPACE.sub(" ", parser.text()).strip()
    normalised = unicodedata.normalize("NFC", collapsed)
    return sha256_hex(normalised.encode("utf-8"))
