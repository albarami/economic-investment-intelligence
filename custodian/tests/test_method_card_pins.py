"""MTH-03 guard plants, all inputs invented under tmp_path.

Assumptions to confirm in pass 2: S2-T08 artifact/config shapes in the fixture
helper, scalar encoding for compound values, and checked-value Markdown blocks.
"""

import copy
from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.method_card_validation import (
    completion_evidence,
    validate_source_check_record,
    verify_method_cards_sync,
)

from .method_card_pin_fixtures import (
    PINS,
    blocks,
    case,
    digest,
    pending,
    save,
    write_json,
    write_yaml,
)


def test_checked_fixture_and_sync(tmp_path):
    paths, record, _, _ = case(tmp_path)
    entries = validate_source_check_record(*paths[:3])
    assert set(entries) == set(PINS)
    assert entries["wilson.period"].values == record["pins"][0]["values"]
    verify_method_cards_sync(paths[0], paths[3])
    for gate in ("S2", "S7"):
        assert set(completion_evidence(*paths, gate=gate)) == set(PINS)


def test_plant_tampered_value(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["values"]["value"] = "tampered"
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="value_mismatch"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize("reviewer", ["", "OpenAI", " openai "])
def test_plant_missing_or_same_maker_reviewer(tmp_path, reviewer):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["reviewer_maker"] = reviewer
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="reviewer"):
        validate_source_check_record(*paths[:3])


def test_plant_missing_review_result(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["checked_against_source"] = False
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="unpinned"):
        validate_source_check_record(*paths[:3])


def test_plant_wrong_configuration_hash(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["settings_sha256"] = digest(b"wrong settings")
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="settings_hash"):
        validate_source_check_record(*paths[:3])


def test_plant_unrecorded_setting(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    artifact["pins"][0]["settings"]["unrecorded_seed"] = 9
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="unrecorded_setting"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize("gate", ["S2", "S7"])
@pytest.mark.parametrize("pin", PINS)
def test_plant_unpinned_at_gate_even_with_open_item(tmp_path, gate, pin):
    paths, record, artifact, _ = case(tmp_path)
    row = next(row for row in record["pins"] if row["pin_id"] == pin)
    pending(row)
    save(paths, record, artifact)
    # An OPEN_ITEMS entry cannot supply a missing checked value.
    (tmp_path / "OPEN_ITEMS.md").write_text(f"Recorded: {pin} still unpinned.\n")
    with pytest.raises(ValueError, match=f"{gate}:unpinned"):
        completion_evidence(*paths, gate=gate)


@pytest.mark.parametrize("treatment", ["", "clean"])
def test_plant_contaminated_c5_parent(tmp_path, treatment):
    paths, record, artifact, config = case(tmp_path)
    for pin in config["pins"]:
        if pin.startswith("c5."):
            config["pins"][pin]["parent_contains_excluded"] = True
            config["pins"][pin]["parent_treatment"] = treatment
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="includes excluded lines"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize("substitute", ["half_year", "2019"])
def test_plant_half_year_or_2019_substitute(tmp_path, substitute):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["prior_months"] = (
                settings["prior_months"][:6]
                if substitute == "half_year"
                else [
                    month.replace("2024", "2019") for month in settings["prior_months"]
                ]
            )
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_window"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize("change", ["value", "unchecked", "outside_block", "duplicate"])
def test_plant_card_sync_failure(tmp_path, change):
    paths, record, artifact, _ = case(tmp_path)
    text = paths[3].read_text()
    if change == "value":
        text = text.replace("invented:wilson.period", "unchecked value")
    elif change == "unchecked":
        pending(record["pins"][0])
        save(paths, record, artifact)
    elif change == "duplicate":
        text += blocks(record["pins"][:1])
    else:
        text = text.replace("No public value", "Unchecked price 7")
    paths[3].write_text(text)
    with pytest.raises(ValueError, match="card_sync"):
        verify_method_cards_sync(paths[0], paths[3])


def test_committed_record_schema_valid_but_both_gates_fail(tmp_path):
    record_path = Path("custodian/publicdata/review/s2_t09_source_checks.yaml")
    entries = validate_source_check_record(
        record_path, tmp_path / "absent", tmp_path / "absent"
    )
    assert set(entries) == set(PINS)
    assert all(not entry.values and entry.unpinned_reason for entry in entries.values())
    verify_method_cards_sync(record_path, Path("docs/07_ECONOMIC_METHODS.md"))
    for gate in ("S2", "S7"):
        with pytest.raises(ValueError, match=f"{gate}:unpinned"):
            completion_evidence(
                record_path,
                tmp_path / "absent",
                tmp_path / "absent",
                Path("docs/07_ECONOMIC_METHODS.md"),
                gate=gate,
            )


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "unknown", "bool_value", "lineage", "date"]
)
def test_closed_record_schema(tmp_path, defect):
    paths, record, _artifact, _ = case(tmp_path)
    if defect == "missing":
        record["pins"].pop()
    elif defect == "duplicate":
        record["pins"].append(record["pins"][0])
    elif defect == "unknown":
        record["pins"][0]["unknown"] = True
    elif defect == "bool_value":
        record["pins"][0]["checked_against_source"] = 1
    elif defect == "lineage":
        record["pins"][0]["source_lineage"][0]["licence_id"] = ""
    else:
        record["pins"][0]["review_date"] = "not-a-date"
    write_yaml(paths[0], record)
    with pytest.raises(ValueError):
        validate_source_check_record(*paths[:3])


def test_unpinned_has_no_values_or_reviews(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    pending(record["pins"][0])
    record["pins"][0]["values"] = {"value": "unreviewed"}
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="unpinned"):
        validate_source_check_record(*paths[:3])


def test_pending_fixture_needs_no_live_file(tmp_path):
    paths, record, _, _ = case(tmp_path)
    for row in record["pins"]:
        pending(row)
    write_yaml(paths[0], record)
    paths[1].unlink()
    paths[2].unlink()
    assert len(validate_source_check_record(*paths[:3])) == len(PINS)
    # No checked block may appear even when all source records are unpinned.
    paths[3].write_text(
        "# Invented method cards\n\nNo public value appears in this fixture.\n"
    )
    verify_method_cards_sync(paths[0], paths[3])
    assert yaml.safe_load(paths[0].read_text())["pins"][0]["values"] == {}


def test_plant_setting_removed_from_both_artifact_and_config(tmp_path):
    paths, record, artifact, config = case(tmp_path)
    pin = "c6.seed"
    config["pins"][pin] = {}
    next(row for row in artifact["pins"] if row["pin_id"] == pin)["settings"] = {}
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="unrecorded_setting"):
        validate_source_check_record(*paths[:3])


def test_plant_contamination_label_not_recorded_with_value(tmp_path):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["parent_contains_excluded"] = True
            settings["parent_treatment"] = "includes excluded lines"
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_visible_label"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize("treatment", ["includes excluded lines", "withheld"])
def test_reviewed_contaminated_parent_must_label_or_withhold_values(
    tmp_path, treatment
):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["parent_contains_excluded"] = True
            settings["parent_treatment"] = treatment
    for row in record["pins"]:
        if row["pin_id"] in ("c5.prior12", "c5.trend"):
            if treatment == "withheld":
                row["values"] = {
                    "value": "NO_DATA",
                    "reason": "includes excluded lines",
                }
            else:
                row["values"]["caveat"] = "includes excluded lines"
    for produced in artifact["pins"]:
        pin = produced["pin_id"]
        produced["settings"] = copy.deepcopy(config["pins"][pin])
        produced["values"] = next(
            row["values"].copy() for row in record["pins"] if row["pin_id"] == pin
        )
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    assert validate_source_check_record(*paths[:3])["c5.prior12"].checked_against_source
