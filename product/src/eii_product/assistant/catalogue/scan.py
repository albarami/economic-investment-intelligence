"""Build-time scan of rendered catalogue words."""

from __future__ import annotations

import re
import unicodedata

from eii_product.assistant.catalogue.schema import Refusal

NUMERAL_CATEGORIES = frozenset({"Nd", "Nl", "No"})
NUMERAL_SYMBOLS = (
    "\u20e3",
    "\U0001f51f",
    "\U0001f522",
    "\U0001f4af",
    "\U0001f51e",
)
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")
_CHARREF = re.compile(r"&(?:#|[A-Za-z])")


def find_numeral(text: str) -> str | None:
    """Return the first character whose Unicode category is Nd, Nl or No."""
    for character in text:
        if unicodedata.category(character) in NUMERAL_CATEGORIES:
            return character
    return None


def check_rendered(
    text: str,
    slot_names: tuple[str, ...],
    path: str,
    *,
    require_slots: bool,
) -> Refusal | None:
    """Refuse a numeral, a stray brace, an unknown placeholder or a missing slot."""
    if not isinstance(text, str) or text == "":
        return Refusal("MISSING_PROPERTY", path)
    for character in text:
        if character in NUMERAL_SYMBOLS:
            return Refusal("TEMPLATE_NUMERAL_SYMBOL", path)
    if _CHARREF.search(text) is not None:
        return Refusal("TEMPLATE_CHARREF", path)
    if find_numeral(text) is not None:
        return Refusal("TEMPLATE_NUMERAL", path)
    seen: set[str] = set()
    index = 0
    while index < len(text):
        character = text[index]
        if character not in "{}":
            index += 1
            continue
        if character == "}":
            return Refusal("TEMPLATE_BRACE", path)
        match = PLACEHOLDER.match(text, index)
        if match is None:
            return Refusal("TEMPLATE_BRACE", path)
        name = match.group(1)
        if name not in slot_names:
            return Refusal("TEMPLATE_SLOT", path)
        seen.add(name)
        index = match.end()
    if require_slots:
        for name in slot_names:
            if name not in seen:
                return Refusal("TEMPLATE_SLOT", path)
    return None
