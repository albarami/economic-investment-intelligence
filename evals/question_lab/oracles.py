"""Independent deterministic graders, with no model and no production validators.

These grade measurements, not assertions that measurements happened. An absent
observation never qualifies. Native/human evidence has a separate boundary.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence, Set
from itertools import pairwise
from pathlib import Path

ACCURACY_KEYS = ("fact_id", "value", "unit", "period", "area", "status")
CHAIN_KEYS = (
    "table",
    "method",
    "version",
    "publisher",
    "dataset",
    "licence",
    "retrieved",
    "hash",
)
MAP_KEYS = ("target", "outline", "camera", "pins", "layer")
VISUAL_KEYS = (
    "map_visible",
    "answer_visible",
    "no_overflow",
    "no_clipping",
    "contrast",
    "targets",
    "fonts",
    "focus",
    "legend",
    "land",
    "bottom_sheet",
    "safe_margins",
    "presenter_type",
    "pixel_baseline",
    "pixel_match",
    "unmirrored_map",
    "numeric_isolates",
    "reading_order",
)
PARITY_KEYS = ("fact_ids", "digits", "unit", "period", "status", "coverage", "depth")
VALUE_KEYS = frozenset({"evidence", "date", "limitation", "next_test", "source"})


def accuracy(
    observed: Mapping[str, object], expected: Mapping[str, object]
) -> list[str]:
    problems = [
        f"accuracy:{key}"
        for key in ACCURACY_KEYS
        if key not in expected or key not in observed or observed[key] != expected[key]
    ]
    chain = observed.get("chain")
    if (
        not isinstance(chain, dict)
        or set(chain) != set(CHAIN_KEYS)
        or any(not isinstance(chain[key], str) or not chain[key] for key in CHAIN_KEYS)
        or re.fullmatch(r"[a-f0-9]{64}", str(chain.get("hash"))) is None
    ):
        problems.append("accuracy:chain")
    if set(observed) != {*ACCURACY_KEYS, "chain"}:
        problems.append("accuracy:property")
    if "chain" in expected and observed.get("chain") != expected["chain"]:
        problems.append("accuracy:chain")
    return problems


def map_behaviour(
    observed: Mapping[str, object], expected: Mapping[str, object]
) -> list[str]:
    return [
        f"map:{key}"
        for key in MAP_KEYS
        if key not in expected or key not in observed or observed[key] != expected[key]
    ]


def disclosure(observed: Mapping[str, object], sentinel: int) -> list[str]:
    """Fixture sentinel and simple difference attack; not document 06's suite."""
    problems = []
    if re.search(
        rf"(?<![0-9]){sentinel}(?![0-9])", json.dumps(observed, ensure_ascii=False)
    ):
        problems.append("disclosure:sentinel")
    numbers = [
        float(v)
        for v in observed.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if any(a - b == sentinel for a in numbers for b in numbers):
        problems.append("disclosure:difference")
    if observed.get("status") == "SUPPRESSED" and observed.get("value") is not None:
        problems.append("disclosure:suppressed_value")
    return problems


def smoothness(
    events: Sequence[tuple[str, float]], *, refusal: bool = False
) -> list[str]:
    problems = []
    if (
        not events
        or any(not math.isfinite(t) or t < 0 for _, t in events)
        or any(a[1] > b[1] for a, b in pairwise(events))
    ):
        problems.append("smoothness:clock")
    names = [name for name, _ in events]
    visible = "reason" if refusal else "chip"
    for name in ("submit", "map", visible, "accounted", "brief"):
        if name not in names:
            problems.append(f"smoothness:missing_{name}")
    if "brief" in names and (
        "accounted" not in names or names.index("accounted") > names.index("brief")
    ):
        problems.append("smoothness:accounting")
    if visible in names and (
        "map" not in names or names.index("map") > names.index(visible)
    ):
        problems.append("smoothness:map_first")
    if "reset" in names and any(
        name in {"chip", "brief", "map"} for name in names[names.index("reset") + 1 :]
    ):
        problems.append("smoothness:late_repaint")
    return problems


def value(present: Set[str], actions: int) -> list[str]:
    problems = [f"value:{key}" for key in sorted(VALUE_KEYS - present)]
    if type(actions) is not int or actions < 0 or actions > 6:
        problems.append("value:actions")
    return problems


def visual(observed: Mapping[str, object]) -> list[str]:
    return [f"visual:{key}" for key in VISUAL_KEYS if observed.get(key) is not True]


def parity(
    en: Mapping[str, object], ar: Mapping[str, object], approved: Mapping[str, object]
) -> list[str]:
    problems = [
        f"parity:{key}"
        for key in PARITY_KEYS
        if key not in en or key not in ar or en[key] != ar[key]
    ]
    for language, card in (("en", en), ("ar", ar)):
        if (
            card.get("language") != language
            or not approved.get(language)
            or card.get("text") != approved[language]
        ):
            problems.append(f"parity:{language}_text")
    if any(
        re.search("[\u0660-\u0669\u06f0-\u06f9]", str(card.get("digits")))
        for card in (en, ar)
    ):
        problems.append("parity:digits")
    return problems


def seal(path: Path, author_root: Path, canary: str) -> list[str]:
    """Must run as author against a separately provisioned volume.

    PermissionError is the only successful read-denial outcome. Missing files,
    directories and arbitrary IO failures are not denial evidence. This never
    reads or returns a held-out prompt: the probe is a dedicated canary file.
    """
    problems = []
    try:
        path.read_bytes()
    except PermissionError:
        pass
    except OSError:
        problems.append("seal:missing")
    else:
        problems.append("seal:author_readable")
    # Only explicit author artifacts, never a recursive walk of the repository.
    for name in ("gallery.html", "manifest.json", "author.log"):
        candidate = author_root / name
        if candidate.is_file() and canary.encode() in candidate.read_bytes():
            problems.append("seal:exposed")
    return problems


def percentile(samples: Sequence[float]) -> dict[str, float | int]:
    if not samples or any(
        type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in samples
    ):
        raise ValueError("timing_samples")
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "p50": ordered[math.ceil(len(ordered) * 0.50) - 1],
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "worst": ordered[-1],
    }
