"""Packet-level negative controls. These are fixtures, never external evidence."""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from evals.question_lab.oracles import (
    CHAIN_KEYS,
    PARITY_KEYS,
    VALUE_KEYS,
    VISUAL_KEYS,
    accuracy,
    disclosure,
    map_behaviour,
    parity,
    seal,
    smoothness,
    value,
    visual,
)


def plant_results() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, diagnostic: str, control: list[str], planted: list[str]) -> None:
        rows.append(
            {
                "guard": name,
                "intended_diagnostic": diagnostic,
                "control_problems": control,
                "plant_problems": planted,
                "scope": "invented_oracle_fixture_not_external_evidence",
            }
        )

    expected: dict[str, Any] = {
        "fact_id": "INVENTED-fact-a",
        "value": 4,
        "unit": "radiance_nw_cm2_sr",
        "period": "2026-03",
        "area": "INVENTED-area-a",
        "status": "OK",
    }
    fact = {**expected, "chain": {key: "INVENTED" for key in CHAIN_KEYS}}
    fact["chain"]["hash"] = "ab" * 32
    for key, bad_scalar in (
        ("value", 7),
        ("fact_id", "INVENTED-fact-b"),
        ("unit", "count"),
        ("period", "2025"),
        ("area", "INVENTED-area-b"),
        ("status", "SUPPRESSED"),
    ):
        add(
            "accuracy_" + key,
            "accuracy:" + key,
            accuracy(fact, expected),
            accuracy({**fact, key: bad_scalar}, expected),
        )
    for key in CHAIN_KEYS:
        bad_fact = copy.deepcopy(fact)
        del bad_fact["chain"][key]
        add(
            "chain_" + key,
            "accuracy:chain",
            accuracy(fact, expected),
            accuracy(bad_fact, expected),
        )
    add(
        "model_property",
        "accuracy:property",
        accuracy(fact, expected),
        accuracy({**fact, "prose": "INVENTED"}, expected),
    )
    target = {
        "target": "INVENTED-place-a",
        "outline": [[1, 1], [2, 2]],
        "camera": [1, 1],
        "pins": ["INVENTED-pin-a"],
        "layer": "night_lights",
    }
    for key, bad_map in (
        ("target", "INVENTED-place-b"),
        ("outline", []),
        ("camera", [2, 2]),
        ("pins", []),
        ("layer", "wages"),
    ):
        add(
            "map_" + key,
            "map:" + key,
            map_behaviour(target, target),
            map_behaviour({**target, key: bad_map}, target),
        )
    for name, bad_disclosure, diagnostic in (
        ("json", {"value": 37}, "sentinel"),
        ("text", {"text": "37"}, "sentinel"),
        ("attribute", {"aria-label": "INVENTED 37"}, "sentinel"),
        ("difference", {"total": 50, "published": 13}, "difference"),
        ("suppressed_zero", {"status": "SUPPRESSED", "value": 0}, "suppressed_value"),
    ):
        add(
            "disclosure_" + name,
            "disclosure:" + diagnostic,
            disclosure({"status": "SUPPRESSED", "value": None}, 37),
            disclosure(bad_disclosure, 37),
        )
    events = [
        ("submit", 0.0),
        ("map", 1.0),
        ("chip", 2.0),
        ("accounted", 3.0),
        ("brief", 4.0),
        ("reset", 5.0),
    ]
    for name in ("submit", "map", "chip", "accounted", "brief"):
        add(
            "event_" + name,
            "smoothness:missing_" + name,
            smoothness(events),
            smoothness([row for row in events if row[0] != name]),
        )
    add(
        "late_repaint",
        "smoothness:late_repaint",
        smoothness(events),
        smoothness([*events, ("brief", 6.0)]),
    )
    for key in VALUE_KEYS:
        add(
            "value_" + key,
            "value:" + key,
            value(VALUE_KEYS, 6),
            value(VALUE_KEYS - {key}, 6),
        )
    add(
        "interaction_budget",
        "value:actions",
        value(VALUE_KEYS, 6),
        value(VALUE_KEYS, 7),
    )
    clean_visual = dict.fromkeys(VISUAL_KEYS, True)
    for key in VISUAL_KEYS:
        add(
            "visual_" + key,
            "visual:" + key,
            visual(clean_visual),
            visual({**clean_visual, key: False}),
        )
    common = dict.fromkeys(PARITY_KEYS, "INVENTED-matching-field")
    en, ar = (
        {**common, "text": "INVENTED caveat", "language": "en"},
        {**common, "text": "قيد مخترع", "language": "ar"},
    )
    approved = {"en": en["text"], "ar": ar["text"]}
    add(
        "english_only_arabic_card",
        "parity:ar_text",
        parity(en, ar, approved),
        parity(en, {**ar, "text": en["text"]}, approved),
    )
    for key in PARITY_KEYS:
        add(
            "parity_" + key,
            "parity:" + key,
            parity(en, ar, approved),
            parity(en, {**ar, key: None}, approved),
        )
    # The clean control models denied canary IO. It cannot prove an OS identity.
    # Actual qualification still requires the separately provisioned real seal.
    denied, readable = Mock(spec=Path), Mock(spec=Path)
    denied.read_bytes.side_effect = PermissionError
    readable.read_bytes.return_value = b"INVENTED-canary"
    temp_root = Path(__file__).resolve().parents[2] / ".overnight/tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root, prefix="lab-seal-fixture-") as work:
        folder = Path(work)

        def check(probe: Path) -> list[str]:
            return seal(probe, folder, "INVENTED-canary")

        control = check(denied)
        add("held_out_author_read", "seal:author_readable", control, check(readable))
        add("held_out_missing", "seal:missing", control, check(folder / "missing"))
        (folder / "gallery.html").write_text("INVENTED-canary")
        add("held_out_exposure", "seal:exposed", control, check(denied))
    return rows
