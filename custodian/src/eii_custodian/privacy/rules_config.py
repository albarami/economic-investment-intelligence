"""Check the rules configuration for the exported set, movement bases and window.

The privacy engine is not implemented here. ``load_rules`` reads a TOML file of
``rules_version`` entries and refuses the faults named by task S1-T09.
"""

import hashlib
import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

TASK_ID = "S1-T09"
WINDOW_MIN = 1
WINDOW_MAX = 23
LATEST_COMPLETE_INDEX = 2025 * 12 + 11

ENTRY_FIELD_ORDER: tuple[str, ...] = (
    "rules_version_id",
    "parameter_set",
    "rule_code",
    "value",
    "unit",
    "description_en",
)
ENTRY_FIELDS = frozenset(ENTRY_FIELD_ORDER)
PARAMETER_SETS = frozenset({"A", "B", "shared"})
EXPORTED_SETS = frozenset({"A", "B"})
RECORD_FIELDS: tuple[str, ...] = (
    "task",
    "rules_version_id",
    "exported_set",
    "movement_base_a",
    "movement_base_b",
    "window_months",
    "first_month",
    "last_month",
    "entries_sha256",
)
REQUIRED_PLACEMENTS: tuple[tuple[str, str], ...] = (
    ("A", "round_movement"),
    ("B", "round_movement"),
    ("shared", "export_parameter_set"),
    ("shared", "window_months"),
)
TASK_PLACEMENTS = frozenset(REQUIRED_PLACEMENTS)
TASK_RULE_SETS: dict[str, frozenset[str]] = {
    "export_parameter_set": frozenset({"shared"}),
    "window_months": frozenset({"shared"}),
    "round_movement": frozenset({"A", "B"}),
}
TASK_UNITS: dict[str, str] = {
    "export_parameter_set": "parameter set",
    "window_months": "months",
    "round_movement": "people or vehicle trips",
}
# Named here so the check refuses them. They are in neither closed list of DAT-129.
RETIRED_CODES = frozenset(
    {
        "presence_base",
        "presence_scale",
        "flow_scale",
    }
)
SET_RULE_CODES = frozenset(
    {
        "min_earners_count",
        "min_groups_count",
        "min_earners_money",
        "min_earners_quartile",
        "max_group_share",
        "max_top2_share",
        "max_person_share",
        "min_band_cell",
        "round_count",
        "round_money",
        "min_earners_trend",
        "min_panel_devices",
        "round_movement",
        "audit_headcount_width",
        "audit_wage_relative_width",
        "money_delta",
    }
)
SHARED_RULE_CODES = frozenset(
    {
        "export_parameter_set",
        "window_months",
        "min_full_month_days",
        "situation_windows",
        "feasibility_tolerance",
        "integrality_tolerance",
        "optimality_tolerance",
        "outward_bound",
    }
)


class RulesRefusal(Exception):
    """The rules configuration failed its check."""


@dataclass(frozen=True)
class RuleEntry:
    """One ``rules_version`` row that passed the shape check."""

    rules_version_id: str
    parameter_set: str
    rule_code: str
    value: str
    unit: str
    description_en: str


@dataclass(frozen=True)
class CheckedRules:
    """Rules that passed the check, with the digest of this task's four entries."""

    entries: tuple[RuleEntry, ...]
    rules_version_id: str
    export_parameter_set: str
    movement_base_a: str
    movement_base_b: str
    window_months: str
    entries_sha256: str


def load_rules(path: Path) -> CheckedRules:
    """Read a rules file and refuse a configuration this task does not allow.

    Args:
        path: Filesystem path of a TOML rules file.

    Returns:
        The checked rules, including the digest of this task's four entries.

    Raises:
        RulesRefusal: The file cannot be read or fails a check.
    """
    document = _load_document(path)
    entries = tuple(
        _checked_entry(index, raw)
        for index, raw in enumerate(_raw_entries(document), start=1)
    )
    _one_identifier(entries)
    _known_codes(entries)
    _task_sets(entries)
    _no_duplicates(entries)
    _required(entries)
    _units(entries)
    export_set, base_a, base_b, window = _values(entries)
    return CheckedRules(
        entries=entries,
        rules_version_id=entries[0].rules_version_id,
        export_parameter_set=export_set,
        movement_base_a=base_a,
        movement_base_b=base_b,
        window_months=window,
        entries_sha256=_entries_sha256(entries),
    )


def compute_gate_record(path: Path) -> dict[str, str]:
    """Build the gate record from a rules file.

    Args:
        path: Filesystem path of a TOML rules file.

    Returns:
        The nine record fields. Month bounds end at November 2025.

    Raises:
        RulesRefusal: The file fails ``load_rules``.
    """
    checked = load_rules(path)
    first_month, last_month = _window_span(int(checked.window_months))
    return {
        "task": TASK_ID,
        "rules_version_id": checked.rules_version_id,
        "exported_set": checked.export_parameter_set,
        "movement_base_a": checked.movement_base_a,
        "movement_base_b": checked.movement_base_b,
        "window_months": checked.window_months,
        "first_month": first_month,
        "last_month": last_month,
        "entries_sha256": checked.entries_sha256,
    }


def compare_gate_records(
    committed: Mapping[str, object],
    computed: Mapping[str, object],
) -> None:
    """Refuse a missing field, an extra field, or any different value.

    Args:
        committed: The record read from the committed file.
        computed: The record just computed from the configuration.

    Raises:
        RulesRefusal: A field is missing, extra, or different.
    """
    missing = [
        field for field in RECORD_FIELDS if field in computed and field not in committed
    ]
    if not missing:
        missing = sorted(field for field in computed if field not in committed)
    if missing:
        preferred = [field for field in RECORD_FIELDS if field in missing]
        name = preferred[0] if preferred else missing[0]
        raise RulesRefusal(f"missing field {name}")
    extra = sorted(field for field in committed if field not in computed)
    if extra:
        raise RulesRefusal(f"extra field {extra[0]}")
    for field, value in computed.items():
        if committed[field] != value:
            raise RulesRefusal(f"field {field} differs")


def _load_document(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RulesRefusal("file: not UTF-8 text") from exc
    except OSError as exc:
        raise RulesRefusal("file: cannot be read") from exc
    try:
        loaded: object = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RulesRefusal("file: invalid TOML") from exc
    if not isinstance(loaded, dict):
        raise RulesRefusal("file field rules_version: not a list of entries")
    document: dict[str, object] = {}
    for key, value in loaded.items():
        if not isinstance(key, str):
            raise RulesRefusal("file: field name is not text")
        document[key] = value
    return document


def _raw_entries(document: Mapping[str, object]) -> list[dict[str, object]]:
    if "rules_version" not in document:
        return []
    raw = document["rules_version"]
    if not isinstance(raw, list):
        raise RulesRefusal("file field rules_version: not a list of entries")
    entries: list[dict[str, object]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise RulesRefusal(f"file: entry {index} is not a table")
        table: dict[str, object] = {}
        for key, value in item.items():
            if not isinstance(key, str):
                raise RulesRefusal(f"file: entry {index} field name is not text")
            table[key] = value
        entries.append(table)
    return entries


def _label(index: int, raw: Mapping[str, object]) -> str:
    parameter_set = raw.get("parameter_set")
    rule_code = raw.get("rule_code")
    if (
        isinstance(parameter_set, str)
        and isinstance(rule_code, str)
        and parameter_set != ""
        and rule_code != ""
    ):
        return f"{parameter_set}/{rule_code}"
    return f"#{index}"


def _checked_entry(index: int, raw: Mapping[str, object]) -> RuleEntry:
    label = _label(index, raw)
    unknown = sorted(set(raw) - ENTRY_FIELDS)
    if unknown:
        raise RulesRefusal(f"entry {label} field {unknown[0]}: unknown")
    texts: dict[str, str] = {}
    for field in ENTRY_FIELD_ORDER:
        if field not in raw:
            raise RulesRefusal(f"entry {label} field {field}: missing")
        value = raw[field]
        if not isinstance(value, str):
            raise RulesRefusal(f"entry {label} field {field}: not text")
        texts[field] = value
    if texts["parameter_set"] not in PARAMETER_SETS:
        raise RulesRefusal(f"entry {label} field parameter_set: not A, B or shared")
    if texts["rules_version_id"].strip() == "":
        raise RulesRefusal(f"entry {label} field rules_version_id: blank")
    return RuleEntry(
        rules_version_id=texts["rules_version_id"],
        parameter_set=texts["parameter_set"],
        rule_code=texts["rule_code"],
        value=texts["value"],
        unit=texts["unit"],
        description_en=texts["description_en"],
    )


def _one_identifier(entries: Sequence[RuleEntry]) -> None:
    if not entries:
        return
    common = entries[0].rules_version_id
    for entry in entries[1:]:
        if entry.rules_version_id != common:
            label = f"{entry.parameter_set}/{entry.rule_code}"
            raise RulesRefusal(f"entry {label} field rules_version_id: differs")


def _known_codes(entries: Sequence[RuleEntry]) -> None:
    for entry in entries:
        code = entry.rule_code
        listed = code in SET_RULE_CODES or code in SHARED_RULE_CODES
        if code in RETIRED_CODES or not listed:
            raise RulesRefusal(f"rule {code}: in neither closed list")


def _task_sets(entries: Sequence[RuleEntry]) -> None:
    for entry in entries:
        allowed = TASK_RULE_SETS.get(entry.rule_code)
        if allowed is not None and entry.parameter_set not in allowed:
            label = f"{entry.parameter_set}/{entry.rule_code}"
            raise RulesRefusal(
                f"entry {label} field parameter_set: "
                f"{entry.rule_code} is not a rule of this set"
            )


def _no_duplicates(entries: Sequence[RuleEntry]) -> None:
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry.parameter_set, entry.rule_code)
        if key in seen:
            raise RulesRefusal(
                f"rule {entry.rule_code}: given twice for set {entry.parameter_set}"
            )
        seen.add(key)


def _required(entries: Sequence[RuleEntry]) -> None:
    present = {(entry.parameter_set, entry.rule_code) for entry in entries}
    for parameter_set, rule_code in REQUIRED_PLACEMENTS:
        if (parameter_set, rule_code) not in present:
            raise RulesRefusal(f"rule {rule_code}: missing for set {parameter_set}")


def _units(entries: Sequence[RuleEntry]) -> None:
    for entry in entries:
        expected = TASK_UNITS.get(entry.rule_code)
        if expected is not None and entry.unit != expected:
            raise RulesRefusal(f"rule {entry.rule_code}: wrong unit")


def _canonical_whole(text: str) -> int | None:
    if not text.isascii() or not text.isdigit():
        return None
    if len(text) > 1 and text.startswith("0"):
        return None
    return int(text)


def _values(entries: Sequence[RuleEntry]) -> tuple[str, str, str, str]:
    by_key = {(entry.parameter_set, entry.rule_code): entry for entry in entries}
    export_set = by_key[("shared", "export_parameter_set")].value
    if export_set not in EXPORTED_SETS:
        raise RulesRefusal("rule export_parameter_set: exported set is not A or B")
    window_text = by_key[("shared", "window_months")].value
    window = _canonical_whole(window_text)
    if window is None or window < WINDOW_MIN or window > WINDOW_MAX:
        raise RulesRefusal("rule window_months: not a whole number from 1 to 23")
    bases: dict[str, int] = {}
    base_text: dict[str, str] = {}
    for parameter_set in ("A", "B"):
        text = by_key[(parameter_set, "round_movement")].value
        number = _canonical_whole(text)
        if number is None or number < 1:
            raise RulesRefusal(
                "rule round_movement: "
                f"set {parameter_set} value is not a positive whole number"
            )
        bases[parameter_set] = number
        base_text[parameter_set] = text
    if bases["B"] < bases["A"]:
        raise RulesRefusal("rule round_movement: set B base is smaller than set A")
    return export_set, base_text["A"], base_text["B"], window_text


def _entries_sha256(entries: Sequence[RuleEntry]) -> str:
    selected = [
        entry
        for entry in entries
        if (entry.parameter_set, entry.rule_code) in TASK_PLACEMENTS
    ]
    selected.sort(key=lambda entry: (entry.parameter_set, entry.rule_code))
    payload = [
        {
            "description_en": entry.description_en,
            "parameter_set": entry.parameter_set,
            "rule_code": entry.rule_code,
            "rules_version_id": entry.rules_version_id,
            "unit": entry.unit,
            "value": entry.value,
        }
        for entry in selected
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _month_text(index: int) -> str:
    year, month_index = divmod(index - 1, 12)
    return f"{year:04d}-{month_index + 1:02d}"


def _window_span(count: int) -> tuple[str, str]:
    start = LATEST_COMPLETE_INDEX - (count - 1)
    return _month_text(start), _month_text(LATEST_COMPLETE_INDEX)
