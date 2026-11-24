"""Backend origin markers of a generated output (decision 0035 item 3).

The audience sees no data-origin word (decision 0035 items 1 and 2), so the
backend must say it instead. Every generated record, table, file and release
carries an explicit ``origin`` whose value is ``synthetic`` or ``simulated``,
with the generator's ``generator_name`` and ``generator_version``. Its source
chain names the producing pipeline and its version, never an outside
publisher it does not have, and never calls the output official, measured or
from a ministry or a real register (decision 0035 item 4; rule 24).

This module only checks. It never adds, renames or strips a marker to make a
check pass, and it changes nothing it reads. The exact placement of these
fields in the closed release, database and ledger schemas belongs to the
backend tasks S4-T01, S5-T04 and S9-T01; until then the checks run on
invented fixtures only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence

ORIGIN_KEY = "origin"
GENERATOR_NAME_KEY = "generator_name"
GENERATOR_VERSION_KEY = "generator_version"
MARKER_KEYS = (ORIGIN_KEY, GENERATOR_NAME_KEY, GENERATOR_VERSION_KEY)
GENERATED_ORIGINS = frozenset({"synthetic", "simulated"})

LEVELS = ("release", "file", "table", "record")
CHILDREN = {"release": "files", "file": "tables", "table": "records"}

REFUSAL_CODES = frozenset(
    {
        "level_unknown",
        "level_shape",
        "marker_missing",
        "marker_blank",
        "origin_not_generated",
        "pipeline_missing",
        "pipeline_mismatch",
        "outside_publisher",
        "claim_word",
    }
)

_CLAIM_EN = (
    r"official(?:ly)?",
    r"measured",
    r"ministry",
    r"ministerial",
    r"government\s+data",
    r"observed\s+from\s+(?:a|the)\s+real\s+register",
    r"real\s+register",
)
_CLAIM_AR = (
    "رسمي",
    "رسمية",
    "الرسمي",
    "الرسمية",
    "مقاس",
    "مقاسة",
    "المقاس",
    "المقاسة",
    "وزارة",
    "الوزارة",
    "وزاري",
    "سجل حقيقي",
)
_CLAIM = re.compile(
    r"(?<![\w])(?:" + "|".join((*_CLAIM_EN, *_CLAIM_AR)) + r")(?![\w])",
    re.IGNORECASE,
)
_ARABIC_MARKS = re.compile("[\u064b-\u0652\u0670\u0640]")
_ALEF = re.compile("[\u0622\u0623\u0625]")

DISPLAY_KEYS = ("method", "pipeline", "label_en", "label_ar", "caveat_text")


class BackendOriginRefusal(ValueError):
    """A generated output whose backend origin or source chain is not whole."""

    def __init__(self, code: str, where: str) -> None:
        if code not in REFUSAL_CODES:
            raise ValueError("unknown refusal code")
        super().__init__(f"{code}:{where}")
        self.code = code
        self.where = where


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFC", value)
    text = _ARABIC_MARKS.sub("", text)
    text = _ALEF.sub("\u0627", text)
    return text.replace("_", " ").replace("-", " ")


def claim_word_in(value: str) -> bool:
    """True when a display text calls generated data official or measured."""
    return _CLAIM.search(_normalise(value)) is not None


def require_markers(
    level: str, metadata: Mapping[str, object], where: str = ""
) -> None:
    """Refuse a generated output of one level without its three markers."""
    if level not in LEVELS:
        raise BackendOriginRefusal("level_unknown", level)
    place = where or level
    for key in MARKER_KEYS:
        if key not in metadata:
            raise BackendOriginRefusal("marker_missing", f"{place}.{key}")
        value = metadata[key]
        if not isinstance(value, str) or value.strip() == "":
            raise BackendOriginRefusal("marker_blank", f"{place}.{key}")
    if metadata[ORIGIN_KEY] not in GENERATED_ORIGINS:
        raise BackendOriginRefusal("origin_not_generated", f"{place}.{ORIGIN_KEY}")


def require_generated_output(release: Mapping[str, object]) -> None:
    """Walk a release, its files, their tables and their records.

    Every level is checked on its own: a marker is never inherited from the
    level above, so a level that lost its marker fails even when its parent
    still has one.
    """
    _walk("release", release, "release")


def _walk(level: str, metadata: Mapping[str, object], where: str) -> None:
    require_markers(level, metadata, where)
    child_key = CHILDREN.get(level)
    if child_key is None:
        return
    children = metadata.get(child_key)
    if not isinstance(children, Sequence) or isinstance(children, str) or not children:
        raise BackendOriginRefusal("level_shape", f"{where}.{child_key}")
    child_level = LEVELS[LEVELS.index(level) + 1]
    for index, child in enumerate(children):
        if not isinstance(child, Mapping):
            raise BackendOriginRefusal("level_shape", f"{where}.{child_key}[{index}]")
        _walk(child_level, child, f"{where}.{child_key}[{index}]")


def require_truthful_chain(
    chain: Mapping[str, object], markers: Mapping[str, object]
) -> None:
    """Refuse a source chain that does not name its producing pipeline truthfully.

    ``chain`` holds what the source drawer shows for a generated output: the
    ``method`` and ``method_version``, the ``pipeline`` and
    ``pipeline_version`` that produced it, optional label and caveat texts,
    and ``inputs``, the actual Public inputs with their own publishers. The
    output itself has no ``publisher``: an outside publisher it does not have
    is never shown as its source.
    """
    require_markers("release", markers, "markers")
    for key in ("method", "method_version", "pipeline", "pipeline_version"):
        value = chain.get(key)
        if not isinstance(value, str) or value.strip() == "":
            raise BackendOriginRefusal("pipeline_missing", f"chain.{key}")
    if chain["pipeline"] != markers[GENERATOR_NAME_KEY]:
        raise BackendOriginRefusal("pipeline_mismatch", "chain.pipeline")
    if chain["pipeline_version"] != markers[GENERATOR_VERSION_KEY]:
        raise BackendOriginRefusal("pipeline_mismatch", "chain.pipeline_version")
    publisher = chain.get("publisher")
    if publisher is not None:
        raise BackendOriginRefusal("outside_publisher", "chain.publisher")
    for key in DISPLAY_KEYS:
        value = chain.get(key)
        if isinstance(value, str) and claim_word_in(value):
            raise BackendOriginRefusal("claim_word", f"chain.{key}")
