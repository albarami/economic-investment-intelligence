"""Matching normalisation. The steps are document 08 section 2.1.

The order is NFKC, then case folding, then Arabic: alef variants unify,
diacritics and tatweel are removed, and final yaa and taa marbuta unify.
Those steps are the pack's assumption; OI-09 stays open.
"""

from __future__ import annotations

import unicodedata

_ALEF = {
    "\u0622": "\u0627",
    "\u0623": "\u0627",
    "\u0625": "\u0627",
    "\u0671": "\u0627",
}
_YAA = "\u0649"
_YAA_TARGET = "\u064a"
_TAA = "\u0629"
_TAA_TARGET = "\u0647"
_TATWEEL = "\u0640"
_DIACRITIC_START = 0x064B
_DIACRITIC_END = 0x0652
_SUPERSCRIPT_ALEF = "\u0670"


def normalise(text: str) -> str:
    """Apply the pack's matching steps. Exact equality is NFC alone, not this."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    chars: list[str] = []
    for character in folded:
        mapped = _ALEF.get(character)
        if mapped is not None:
            chars.append(mapped)
            continue
        if character == _YAA:
            chars.append(_YAA_TARGET)
            continue
        if character == _TAA:
            chars.append(_TAA_TARGET)
            continue
        if character == _TATWEEL or _diacritic(character):
            continue
        chars.append(character)
    return "".join(chars)


def _diacritic(character: str) -> bool:
    if character == _SUPERSCRIPT_ALEF:
        return True
    code = ord(character)
    return _DIACRITIC_START <= code <= _DIACRITIC_END
