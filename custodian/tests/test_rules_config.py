"""The slice S1 rules configuration: exported set, movement bases, and the window."""

import hashlib
import json
import locale
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from eii_custodian.privacy.rules_config import (
    CheckedRules,
    RulesRefusal,
    compare_gate_records,
    compute_gate_record,
    load_rules,
)

RULES_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "eii_custodian"
    / "privacy"
    / "rules.toml"
)
GATE_RECORD_PATH = RULES_PATH.with_name("gate_record.json")
README_PATH = RULES_PATH.with_name("README.md")
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rules_config"

RECORD_FIELDS = (
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
ENTRY_FIELDS = (
    "rules_version_id",
    "parameter_set",
    "rule_code",
    "value",
    "unit",
    "description_en",
)
TASK_PLACEMENTS = {
    ("A", "round_movement"),
    ("B", "round_movement"),
    ("shared", "export_parameter_set"),
    ("shared", "window_months"),
}
RETIRED_NAMES = ("presence_base", "presence_scale", "flow_scale")
OTHER_CODES = (
    ("A", "min_earners_count"),
    ("A", "min_groups_count"),
    ("A", "min_earners_money"),
    ("A", "min_earners_quartile"),
    ("A", "max_group_share"),
    ("A", "max_top2_share"),
    ("A", "max_person_share"),
    ("A", "min_band_cell"),
    ("A", "round_count"),
    ("A", "round_money"),
    ("A", "min_earners_trend"),
    ("A", "min_panel_devices"),
    ("A", "audit_headcount_width"),
    ("A", "audit_wage_relative_width"),
    ("A", "money_delta"),
    ("shared", "min_full_month_days"),
    ("shared", "situation_windows"),
    ("shared", "feasibility_tolerance"),
    ("shared", "integrality_tolerance"),
    ("shared", "optimality_tolerance"),
    ("shared", "outward_bound"),
)
REFUSED = (
    ("base_a_missing.toml", "rule round_movement: missing for set A"),
    ("base_b_missing.toml", "rule round_movement: missing for set B"),
    (
        "base_zero.toml",
        "rule round_movement: set A value is not a positive whole number",
    ),
    (
        "base_negative.toml",
        "rule round_movement: set A value is not a positive whole number",
    ),
    (
        "base_decimal.toml",
        "rule round_movement: set A value is not a positive whole number",
    ),
    (
        "base_text.toml",
        "rule round_movement: set A value is not a positive whole number",
    ),
    ("base_b_smaller.toml", "rule round_movement: set B base is smaller than set A"),
    (
        "base_b_zero.toml",
        "rule round_movement: set B value is not a positive whole number",
    ),
    (
        "base_b_many.toml",
        "rule round_movement: set B value is not a positive whole number",
    ),
    ("window_missing.toml", "rule window_months: missing for set shared"),
    ("window_zero.toml", "rule window_months: not a whole number from 1 to 23"),
    ("window_24.toml", "rule window_months: not a whole number from 1 to 23"),
    ("window_decimal.toml", "rule window_months: not a whole number from 1 to 23"),
    ("window_text.toml", "rule window_months: not a whole number from 1 to 23"),
    ("rule_twice.toml", "rule export_parameter_set: given twice for set shared"),
    ("unknown_code.toml", "rule not_a_rule: in neither closed list"),
    ("missing_field.toml", "entry shared/export_parameter_set field unit: missing"),
    ("unknown_field.toml", "entry shared/export_parameter_set field note: unknown"),
    (
        "blank_version.toml",
        "entry shared/export_parameter_set field rules_version_id: blank",
    ),
    (
        "different_version.toml",
        "entry B/round_movement field rules_version_id: differs",
    ),
    (
        "bad_parameter_set.toml",
        "entry C/export_parameter_set field parameter_set: not A, B or shared",
    ),
    (
        "movement_on_shared.toml",
        "entry shared/round_movement field parameter_set: "
        "round_movement is not a rule of this set",
    ),
    (
        "export_on_set_a.toml",
        "entry A/export_parameter_set field parameter_set: "
        "export_parameter_set is not a rule of this set",
    ),
    (
        "window_on_set_b.toml",
        "entry B/window_months field parameter_set: "
        "window_months is not a rule of this set",
    ),
    ("wrong_unit_window.toml", "rule window_months: wrong unit"),
    ("wrong_unit_movement.toml", "rule round_movement: wrong unit"),
    ("wrong_unit_export.toml", "rule export_parameter_set: wrong unit"),
    ("base_not_text.toml", "entry A/round_movement field value: not text"),
    ("unit_not_text.toml", "entry A/round_movement field unit: not text"),
    ("rule_code_not_text.toml", "entry #1 field rule_code: not text"),
    ("invalid.toml", "file: invalid TOML"),
    ("not_a_list.toml", "file field rules_version: not a list of entries"),
    ("entry_not_table.toml", "file: entry 1 is not a table"),
    ("empty.toml", "rule round_movement: missing for set A"),
    ("export_missing.toml", "rule export_parameter_set: missing for set shared"),
    ("export_other.toml", "rule export_parameter_set: exported set is not A or B"),
)


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_rules(directory: Path, entries: Sequence[Mapping[str, str]]) -> Path:
    """Write one TOML rules file and return its path."""
    parts: list[str] = []
    for entry in entries:
        lines = ["[[rules_version]]"]
        for field in ENTRY_FIELDS:
            if field not in entry:
                continue
            lines.append(f"{field} = {_quote(entry[field])}")
        parts.append("\n".join(lines))
    path = directory / "rules.toml"
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return path


def load_good_entries() -> list[dict[str, str]]:
    """Return a mutable copy of the committed entries."""
    raw = tomllib.loads(RULES_PATH.read_text(encoding="utf-8"))
    copied: list[dict[str, str]] = []
    for entry in raw["rules_version"]:
        copied.append({key: str(entry[key]) for key in ENTRY_FIELDS})
    return copied


def _replace(
    entries: list[dict[str, str]],
    rule_code: str,
    set_name: str,
    **changes: str,
) -> None:
    for entry in entries:
        if entry["rule_code"] == rule_code and entry["parameter_set"] == set_name:
            entry.update(changes)
            return
    raise AssertionError(f"missing {set_name}/{rule_code}")


def _added(parameter_set: str, rule_code: str, value: str, unit: str) -> dict[str, str]:
    return {
        "rules_version_id": "rv-1.0.0-s1",
        "parameter_set": parameter_set,
        "rule_code": rule_code,
        "value": value,
        "unit": unit,
        "description_en": "Added entry.",
    }


def spec_sha256(path: Path) -> str:
    """Hash this task's four tables from the file text, not from ``load_rules``."""
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    payload = []
    for entry in document["rules_version"]:
        placement = (entry.get("parameter_set"), entry.get("rule_code"))
        if placement not in TASK_PLACEMENTS:
            continue
        payload.append({field: entry[field] for field in ENTRY_FIELDS})
    payload.sort(key=lambda item: (item["parameter_set"], item["rule_code"]))
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert b": " not in encoded
    return hashlib.sha256(encoded).hexdigest()


def assert_digest(path: Path) -> CheckedRules:
    """Load a file and require its digest to match a hash of the raw tables."""
    rules = load_rules(path)
    assert rules.entries_sha256 == spec_sha256(path)
    assert len(rules.entries_sha256) == 64
    return rules


def _refuse(path: Path, needle: str) -> None:
    with pytest.raises(RulesRefusal) as caught:
        load_rules(path)
    assert str(caught.value) == needle


def test_committed_file_fixes_the_exported_set_bases_window_and_record() -> None:
    """The committed file is set A, bases 50 and 100, window 23, and its record."""
    rules = assert_digest(RULES_PATH)
    assert rules.export_parameter_set == "A"
    assert rules.movement_base_a == "50"
    assert rules.movement_base_b == "100"
    assert rules.window_months == "23"
    assert rules.rules_version_id == "rv-1.0.0-s1"
    units = {
        (entry.parameter_set, entry.rule_code): entry.unit for entry in rules.entries
    }
    assert units[("shared", "export_parameter_set")] == "parameter set"
    assert units[("shared", "window_months")] == "months"
    assert units[("A", "round_movement")] == "people or vehicle trips"
    assert units[("B", "round_movement")] == "people or vehicle trips"
    descriptions = {
        (entry.parameter_set, entry.rule_code): entry.description_en
        for entry in rules.entries
    }
    bound = "and every presence bound, for set "
    assert descriptions[("A", "round_movement")] == (
        f"The rounding base of every released presence and flow estimate {bound}A."
    )
    assert descriptions[("B", "round_movement")] == (
        f"The rounding base of every released presence and flow estimate {bound}B."
    )
    assert len(rules.entries) == 4
    fresh = compute_gate_record(RULES_PATH)
    assert list(fresh) == list(RECORD_FIELDS)
    assert fresh["task"] == "S1-T09"
    assert fresh["rules_version_id"] == "rv-1.0.0-s1"
    assert fresh["exported_set"] == "A"
    assert fresh["movement_base_a"] == "50"
    assert fresh["movement_base_b"] == "100"
    assert fresh["window_months"] == "23"
    assert fresh["first_month"] == "2024-01"
    assert fresh["last_month"] == "2025-11"
    assert fresh["entries_sha256"] == rules.entries_sha256
    committed = json.loads(GATE_RECORD_PATH.read_text(encoding="utf-8"))
    assert committed == fresh
    compare_gate_records(committed, fresh)


def test_set_b_is_accepted_and_reported() -> None:
    """A file whose exported set is B is accepted and reported as B."""
    rules = assert_digest(FIXTURES / "export_b.toml")
    assert rules.export_parameter_set == "B"


def test_equal_movement_bases_are_accepted() -> None:
    """Set B's base may equal set A's."""
    rules = assert_digest(FIXTURES / "equal_bases.toml")
    assert rules.movement_base_a == "50"
    assert rules.movement_base_b == "50"


def test_movement_base_of_one_is_a_positive_whole_number(tmp_path: Path) -> None:
    """One is a positive whole number, so both bases may be the text 1."""
    entries = load_good_entries()
    _replace(entries, "round_movement", "A", value="1")
    _replace(entries, "round_movement", "B", value="1")
    rules = assert_digest(write_rules(tmp_path, entries))
    assert rules.movement_base_a == "1"
    assert rules.movement_base_b == "1"


@pytest.mark.parametrize(("name", "needle"), REFUSED)
def test_bad_file_is_refused(name: str, needle: str) -> None:
    """Each planted violation is refused, and the message names it."""
    _refuse(FIXTURES / name, needle)


@pytest.mark.parametrize("code", RETIRED_NAMES)
def test_retired_name_is_refused(code: str, tmp_path: Path) -> None:
    """presence_base, presence_scale and flow_scale are refused by name."""
    entries = load_good_entries()
    entries.append(_added("shared", code, "1", "unspecified"))
    _refuse(write_rules(tmp_path, entries), f"rule {code}: in neither closed list")


@pytest.mark.parametrize(
    ("count", "first", "last"),
    (
        ("1", "2025-11", "2025-11"),
        ("12", "2024-12", "2025-11"),
        ("23", "2024-01", "2025-11"),
    ),
)
def test_window_span_ends_at_november_2025(
    count: str, first: str, last: str, tmp_path: Path
) -> None:
    """The window is the last complete months, ending at November 2025."""
    entries = load_good_entries()
    _replace(entries, "window_months", "shared", value=count)
    record = compute_gate_record(write_rules(tmp_path, entries))
    assert record["window_months"] == count
    assert record["first_month"] == first
    assert record["last_month"] == last


def test_digest_sorts_entries_and_covers_every_field(tmp_path: Path) -> None:
    """File order does not change the digest, and a description change does."""
    original = assert_digest(RULES_PATH).entries_sha256
    reversed_entries = list(reversed(load_good_entries()))
    assert (
        assert_digest(write_rules(tmp_path, reversed_entries)).entries_sha256
        == original
    )
    described = load_good_entries()
    described[0]["description_en"] = described[0]["description_en"] + " café"
    changed = assert_digest(write_rules(tmp_path, described))
    assert changed.entries_sha256 != original


@pytest.mark.parametrize(("parameter_set", "rule_code"), OTHER_CODES)
def test_listed_code_outside_this_task_is_accepted(
    parameter_set: str, rule_code: str, tmp_path: Path
) -> None:
    """A DAT-129 code that is not one of this task's rules is accepted and not hashed."""
    original = assert_digest(RULES_PATH).entries_sha256
    entries = load_good_entries()
    entries.append(_added(parameter_set, rule_code, "no", "unspecified"))
    rules = assert_digest(write_rules(tmp_path, entries))
    assert rules.entries_sha256 == original


def test_placement_of_another_listed_code_is_not_policed(tmp_path: Path) -> None:
    """This check does not place the other DAT-129 codes onto a set."""
    entries = load_good_entries()
    entries.append(_added("shared", "min_earners_count", "1", "unspecified"))
    entries.append(_added("A", "outward_bound", "1", "furlongs"))
    assert_digest(write_rules(tmp_path, entries))


def test_one_shared_identifier_may_differ_from_the_committed_one(
    tmp_path: Path,
) -> None:
    """Entries must share one identifier; the check does not pin the text itself."""
    entries = load_good_entries()
    for entry in entries:
        entry["rules_version_id"] = "rv-other"
    rules = assert_digest(write_rules(tmp_path, entries))
    assert rules.rules_version_id == "rv-other"
    assert (
        compute_gate_record(write_rules(tmp_path, entries))["rules_version_id"]
        == "rv-other"
    )


def test_first_entry_sets_the_shared_identifier(tmp_path: Path) -> None:
    """A later entry cannot define the identifier when the first entry differs."""
    entries = load_good_entries()
    entries[0]["rules_version_id"] = "rv-first"
    _refuse(
        write_rules(tmp_path, entries),
        "entry shared/window_months field rules_version_id: differs",
    )


def test_second_entry_identifier_is_compared(tmp_path: Path) -> None:
    """The entry after the first is part of the shared-identifier check."""
    entries = load_good_entries()
    entries[1]["rules_version_id"] = "rv-second"
    _refuse(
        write_rules(tmp_path, entries),
        "entry shared/window_months field rules_version_id: differs",
    )


def test_whitespace_identifier_is_blank(tmp_path: Path) -> None:
    """A whitespace-only rules_version_id is blank."""
    entries = load_good_entries()
    entries[0]["rules_version_id"] = "   "
    _refuse(
        write_rules(tmp_path, entries),
        "entry shared/export_parameter_set field rules_version_id: blank",
    )


@pytest.mark.parametrize("value", ("+50", "050", "50 ", "\u0665\u0660"))
def test_movement_base_must_be_canonical_text(value: str, tmp_path: Path) -> None:
    """A movement base is the text of a positive whole number, with no sign or padding."""
    entries = load_good_entries()
    _replace(entries, "round_movement", "A", value=value)
    _refuse(
        write_rules(tmp_path, entries),
        "rule round_movement: set A value is not a positive whole number",
    )


@pytest.mark.parametrize("value", ("+1", "01", "023"))
def test_window_must_be_canonical_text(value: str, tmp_path: Path) -> None:
    """window_months is the text of a whole number from 1 to 23."""
    entries = load_good_entries()
    _replace(entries, "window_months", "shared", value=value)
    _refuse(
        write_rules(tmp_path, entries),
        "rule window_months: not a whole number from 1 to 23",
    )


@pytest.mark.parametrize("value", ("a", "A ", "AB", ""))
def test_exported_set_other_than_a_or_b_is_refused(value: str, tmp_path: Path) -> None:
    """The exported set is the text A or the text B."""
    entries = load_good_entries()
    _replace(entries, "export_parameter_set", "shared", value=value)
    _refuse(
        write_rules(tmp_path, entries),
        "rule export_parameter_set: exported set is not A or B",
    )


def test_entry_without_a_rule_code_is_named_by_index(tmp_path: Path) -> None:
    """An entry that has no rule code is named by its position."""
    entries = load_good_entries()
    del entries[0]["rule_code"]
    _refuse(write_rules(tmp_path, entries), "entry #1 field rule_code: missing")


def test_blank_parameter_set_is_named_by_index(tmp_path: Path) -> None:
    """An empty parameter_set is not a label, so the entry is named by its position."""
    entries = load_good_entries()
    entries[0]["parameter_set"] = ""
    _refuse(
        write_rules(tmp_path, entries),
        "entry #1 field parameter_set: not A, B or shared",
    )


def test_blank_rule_code_is_named_by_index(tmp_path: Path) -> None:
    """An empty rule code is not a label, so the entry is named by its position."""
    entries = load_good_entries()
    entries[0]["rule_code"] = ""
    del entries[0]["unit"]
    _refuse(write_rules(tmp_path, entries), "entry #1 field unit: missing")


def test_lower_case_parameter_set_is_refused(tmp_path: Path) -> None:
    """parameter_set is A, B or shared, in that spelling."""
    entries = load_good_entries()
    _replace(entries, "export_parameter_set", "shared", parameter_set="a")
    _refuse(
        write_rules(tmp_path, entries),
        "entry a/export_parameter_set field parameter_set: not A, B or shared",
    )


def test_gate_record_follows_the_file_it_is_given(tmp_path: Path) -> None:
    """The record is computed from the file, not copied from the committed record."""
    entries = load_good_entries()
    _replace(entries, "export_parameter_set", "shared", value="B")
    record = compute_gate_record(write_rules(tmp_path, entries))
    assert record["exported_set"] == "B"
    assert record["entries_sha256"] != compute_gate_record(RULES_PATH)["entries_sha256"]


@pytest.mark.parametrize("field", RECORD_FIELDS)
def test_record_comparison_refuses_a_missing_field(field: str) -> None:
    """A committed record that lacks a field is refused, and the field is named."""
    fresh = compute_gate_record(RULES_PATH)
    committed = dict(fresh)
    del committed[field]
    with pytest.raises(RulesRefusal) as caught:
        compare_gate_records(committed, fresh)
    assert f"missing field {field}" in str(caught.value)


@pytest.mark.parametrize("field", RECORD_FIELDS)
def test_record_comparison_refuses_a_different_value(field: str) -> None:
    """Any different value is refused, and the field is named."""
    fresh = compute_gate_record(RULES_PATH)
    committed = dict(fresh)
    committed[field] = f"{fresh[field]}-changed"
    with pytest.raises(RulesRefusal) as caught:
        compare_gate_records(committed, fresh)
    assert f"field {field} differs" in str(caught.value)


def test_record_comparison_names_a_field_outside_the_nine() -> None:
    """A computed field outside the nine is reported as missing from the committed record."""
    fresh = compute_gate_record(RULES_PATH)
    computed: dict[str, object] = dict(fresh)
    computed["extra_computed"] = "1"
    with pytest.raises(RulesRefusal) as caught:
        compare_gate_records(fresh, computed)
    assert "missing field extra_computed" in str(caught.value)


def test_record_comparison_ignores_a_field_absent_from_both() -> None:
    """The named gap is a computed field the committed record lacks."""
    fresh = compute_gate_record(RULES_PATH)
    computed = dict(fresh)
    del computed["task"]
    committed = dict(computed)
    del committed["exported_set"]
    with pytest.raises(RulesRefusal) as caught:
        compare_gate_records(committed, computed)
    assert str(caught.value) == "missing field exported_set"


def test_record_comparison_refuses_an_extra_field() -> None:
    """A field the computation does not return is refused."""
    fresh = compute_gate_record(RULES_PATH)
    committed = dict(fresh)
    committed["note"] = "x"
    with pytest.raises(RulesRefusal) as caught:
        compare_gate_records(committed, fresh)
    assert "extra field note" in str(caught.value)


def test_record_comparison_refuses_a_number_in_place_of_text() -> None:
    """The record holds the configuration's text, so a JSON number is a difference."""
    fresh = compute_gate_record(RULES_PATH)
    committed: dict[str, object] = dict(fresh)
    committed["movement_base_a"] = 50
    with pytest.raises(RulesRefusal) as caught:
        compare_gate_records(committed, fresh)
    assert "field movement_base_a differs" in str(caught.value)


def test_unreadable_file_is_refused(tmp_path: Path) -> None:
    """A path that cannot be read is a refusal."""
    _refuse(tmp_path / "missing.toml", "file: cannot be read")


def test_directory_path_is_refused(tmp_path: Path) -> None:
    """A directory is not a rules file."""
    _refuse(tmp_path, "file: cannot be read")


def test_non_utf8_file_is_refused(tmp_path: Path) -> None:
    """A file that is not UTF-8 text is a refusal."""
    path = tmp_path / "rules.toml"
    path.write_bytes(b"\xff")
    _refuse(path, "file: not UTF-8 text")


def test_rules_text_is_read_as_utf8(tmp_path: Path) -> None:
    """The file is UTF-8 even when the process locale is ASCII."""
    entries = load_good_entries()
    entries[0]["description_en"] = entries[0]["description_en"] + " café"
    path = write_rules(tmp_path, entries)
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        rules = assert_digest(path)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert "café" in rules.entries[0].description_en


def test_readme_names_the_window_the_retired_names_and_the_limit() -> None:
    """The README names the months, the retired codes, and what this task cannot prove."""
    text = README_PATH.read_text(encoding="utf-8")
    for needle in (
        "2024-01",
        "2025-11",
        "January 2024",
        "November 2025",
        "cannot prove that no world is built with another file",
        "mob.range_multiple",
        "SYN-77",
        "DAT-129",
        "presence_base",
        "presence_scale",
        "flow_scale",
        "exact-set",
        "expected to be January 2024 to November 2025",
        "wages.v1",
        "mob.panel_penetration",
        "which has no value yet",
        "5% to 20%, swept",
        "fixed at slice S1",
    ):
        assert needle in text
    assert "Until they have values, the world build refuses to start" not in text
