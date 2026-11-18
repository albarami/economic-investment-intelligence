"""MTH-03 guard plants, all inputs invented under tmp_path.

Every plant names the exact error code of the guard it targets, and each is
built so that only that guard can fail. Assumptions to confirm in pass 2:
S2-T08 artifact/config shapes in the fixture helper, the scalar encoding for
compound values, and the per-line C5 value encoding.
"""

import copy
import re
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
    SECTION_PROSE,
    blocks,
    case,
    digest,
    methods_document,
    pending,
    save,
    write_json,
    write_yaml,
)

# F10: paths anchor on the test file's own location, never on the working folder.
ROOT = Path(__file__).resolve().parents[2]
COMMITTED_RECORD = ROOT / "custodian/publicdata/review/s2_t09_source_checks.yaml"
COMMITTED_METHODS = ROOT / "docs/07_ECONOMIC_METHODS.md"


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
    with pytest.raises(ValueError, match="pin_value_mismatch"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize(
    "reviewer,code",
    [
        ("", "pin_maker_unknown"),
        ("OpenAI", "pin_reviewer_missing_or_same_maker"),
        (" openai ", "pin_maker_unknown"),
        ("OpenAI Codex", "pin_maker_unknown"),
    ],
)
def test_plant_missing_same_maker_or_variant_reviewer(tmp_path, reviewer, code):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["reviewer_maker"] = reviewer
    save(paths, record, artifact)
    with pytest.raises(ValueError, match=re.escape(code)):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize(
    "field,variant,code",
    [
        ("builder_maker", "Invented Maker", "pin_maker_unknown"),
        ("reviewer_maker", "OpenAI Codex", "pin_maker_unknown"),
    ],
)
def test_plant_maker_not_in_closed_set(tmp_path, field, variant, code):
    paths, record, _, _ = case(tmp_path)
    record["pins"][0][field] = variant
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match=re.escape(code)):
        validate_source_check_record(*paths[:3])


def test_plant_wrong_configuration_hash(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["settings_sha256"] = digest(b"wrong settings")
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_settings_hash_mismatch"):
        validate_source_check_record(*paths[:3])


def test_plant_unrecorded_setting(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    artifact["pins"][0]["settings"]["unrecorded_seed"] = 9
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_unrecorded_setting"):
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
    with pytest.raises(ValueError, match=re.escape(gate + ":unpinned:")):
        completion_evidence(*paths, gate=gate)


@pytest.mark.parametrize("treatment", ["", "clean"])
def test_plant_contaminated_c5_parent(tmp_path, treatment):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["parent_contains_excluded"] = True
            settings["parent_treatment"] = treatment
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(
        ValueError,
        match=re.escape("c5_parent_requires_includes excluded lines_or_withheld"),
    ):
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
    with pytest.raises(ValueError, match="c5_window_prior_2024_required"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize(
    "substitute,code",
    [
        ("six_months", "c5_window_latest_twelve_required"),
        ("2019", "c5_window_latest_2025_2026_required"),
    ],
)
def test_plant_c5_latest_window_substitute(tmp_path, substitute, code):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["latest_months"] = (
                settings["latest_months"][:6]
                if substitute == "six_months"
                else [f"2019-{month:02}" for month in range(1, 13)]
            )
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match=re.escape(code)):
        validate_source_check_record(*paths[:3])


def test_plant_c5_parent_review_missing(tmp_path):
    paths, record, artifact, config = case(tmp_path)
    for settings in config["pins"].values():
        if "parent_contains_excluded" in settings:
            settings.pop("parent_contains_excluded")
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_review_missing"):
        validate_source_check_record(*paths[:3])


def test_plant_c5_clean_parent_with_withheld_treatment(tmp_path):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["parent_contains_excluded"] = False
            settings["parent_treatment"] = "withheld"
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_treatment"):
        validate_source_check_record(*paths[:3])


def test_plant_c5_withheld_with_value(tmp_path):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["parent_contains_excluded"] = True
            settings["parent_treatment"] = "withheld"
    for produced in artifact["pins"]:
        pin = produced["pin_id"]
        produced["settings"] = copy.deepcopy(config["pins"][pin])
        if pin in ("c5.prior12", "c5.trend"):
            produced["values"] = {"value": "1"}
    for row in record["pins"]:
        if row["pin_id"] in ("c5.prior12", "c5.trend"):
            row["values"] = {"value": "1"}
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_withheld_value"):
        validate_source_check_record(*paths[:3])


def test_plant_checked_row_without_evidence(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # The record and the artifact row agree, so only the record's own
    # checked-evidence guard can fail on the empty value set.
    record["pins"][0]["values"] = {}
    artifact["pins"][0]["values"] = {}
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_checked_evidence_missing"):
        validate_source_check_record(*paths[:3])


def test_plant_wrong_card_anchor(tmp_path):
    paths, record, _, _ = case(tmp_path)
    record["pins"][1]["card_anchor"] = "c6"
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match="pin_unknown_or_anchor"):
        validate_source_check_record(*paths[:3])


def test_plant_unknown_configuration_pin(tmp_path):
    paths, record, _, config = case(tmp_path)
    config["pins"]["c99.x"] = {"fixture_setting": "invented"}
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match="pin_artifact_fields"):
        validate_source_check_record(*paths[:3])


def test_plant_artifact_row_duplicated(tmp_path):
    paths, _, artifact, _ = case(tmp_path)
    artifact["pins"].append(copy.deepcopy(artifact["pins"][0]))
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_artifact_duplicate_or_unknown"):
        validate_source_check_record(*paths[:3])


def test_plant_artifact_row_missing(tmp_path):
    paths, _, artifact, _ = case(tmp_path)
    artifact["pins"] = [
        row for row in artifact["pins"] if row["pin_id"] != "wilson.period"
    ]
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_artifact_missing"):
        validate_source_check_record(*paths[:3])


def test_plant_artifact_lineage_mismatch(tmp_path):
    paths, _, artifact, _ = case(tmp_path)
    artifact["pins"][0]["source_lineage"][0]["sha256"] = digest(b"different rows")
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_lineage_mismatch"):
        validate_source_check_record(*paths[:3])


def test_plant_lineage_date_without_timezone(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # The naive timestamp is planted in the record and in the artifact row of
    # the same pin, so only the record's own lineage-date guard can fail.
    record["pins"][0]["source_lineage"][0]["retrieved_utc"] = "2026-11-18T00:00:00"
    artifact["pins"][0]["source_lineage"][0]["retrieved_utc"] = "2026-11-18T00:00:00"
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_lineage_date"):
        validate_source_check_record(*paths[:3])


def test_plant_lineage_row_duplicated(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # The duplicate lineage row is planted in the record and in the artifact
    # row of the same pin, so only the record's own duplicate guard can fail.
    record["pins"][0]["source_lineage"].append(
        dict(record["pins"][0]["source_lineage"][0])
    )
    artifact["pins"][0]["source_lineage"].append(
        dict(artifact["pins"][0]["source_lineage"][0])
    )
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_lineage_duplicate"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize("where", ["record", "config", "artifact"])
def test_plant_schema_version(tmp_path, where):
    paths, record, artifact, config = case(tmp_path)
    if where == "record":
        record["schema_version"] = 2
        write_yaml(paths[0], record)
    elif where == "config":
        config["schema_version"] = 2
        write_json(paths[2], config)
        for row in record["pins"]:
            row["settings_sha256"] = digest(paths[2].read_bytes())
        write_yaml(paths[0], record)
    else:
        artifact["schema_version"] = 2
        write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_schema_version"):
        validate_source_check_record(*paths[:3])


def test_plant_unknown_gate(tmp_path):
    paths, *_ = case(tmp_path)
    with pytest.raises(ValueError, match="pin_gate_unknown"):
        completion_evidence(*paths, gate="S3")


@pytest.mark.parametrize(
    "field",
    ["values", "source_lineage", "settings_sha256", "reviewer_maker", "review_date"],
)
def test_plant_pending_row_carries_evidence(tmp_path, field):
    paths, record, _, _ = case(tmp_path)
    pending(record["pins"][0])
    row = record["pins"][0]
    if field == "values":
        row["values"] = {"value": "unreviewed"}
    elif field == "source_lineage":
        row["source_lineage"] = [dict(record["pins"][1]["source_lineage"][0])]
    elif field == "settings_sha256":
        row["settings_sha256"] = digest(b"invented settings")
    elif field == "reviewer_maker":
        row["reviewer_maker"] = "Google"
    else:
        row["review_date"] = "2026-11-18"
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match="pin_unpinned_carries_evidence"):
        validate_source_check_record(*paths[:3])


@pytest.mark.parametrize(
    "change,code",
    [
        ("value", "card_sync_value_mismatch"),
        ("unchecked", "card_sync_unchecked_or_duplicate"),
        ("duplicate", "card_sync_unchecked_or_duplicate"),
        ("outside_block", "card_sync_baseline_or_missing_value"),
    ],
)
def test_plant_card_sync_failure(tmp_path, change, code):
    paths, record, artifact, _ = case(tmp_path)
    text = paths[3].read_text()
    if change == "value":
        text = text.replace("invented:wilson.period", "unchecked value")
    elif change == "unchecked":
        # The block is rewritten to the pending row's empty value set, so the
        # value comparison passes and only the unchecked guard can fail.
        pending(record["pins"][0])
        text = text.replace('{"value": "invented:wilson.period"}', "{}")
        save(paths, record, artifact)
    elif change == "duplicate":
        # A second identical block inside the same governed section.
        block = blocks(record["pins"][:1])
        text = text.replace(block, block + block)
    else:
        # A prose edit inside a governed span but outside every block.
        text = text.replace(SECTION_PROSE, "Unchecked price 7", 1)
    paths[3].write_text(text)
    with pytest.raises(ValueError, match=re.escape(code)):
        verify_method_cards_sync(paths[0], paths[3])


def test_plant_card_sync_block_in_wrong_card_section(tmp_path):
    paths, record, _, _ = case(tmp_path)
    moved = blocks([row for row in record["pins"] if row["pin_id"] == "c5.hhi"])
    text = paths[3].read_text().replace(moved, "")
    text = text.replace(
        "### C6 Typical neighbours\n\n" + SECTION_PROSE + "\n",
        "### C6 Typical neighbours\n\n" + SECTION_PROSE + "\n" + moved,
    )
    paths[3].write_text(text)
    with pytest.raises(ValueError, match="card_sync_wrong_anchor"):
        verify_method_cards_sync(paths[0], paths[3])


def test_plant_card_sync_block_outside_governed_sections(tmp_path):
    paths, record, _, _ = case(tmp_path)
    block = blocks(record["pins"][:1])
    text = paths[3].read_text().replace(block, "")
    # After the trailing section heading, outside every governed span.
    paths[3].write_text(text + block)
    with pytest.raises(ValueError, match="card_sync_block_outside_sections"):
        verify_method_cards_sync(paths[0], paths[3])


@pytest.mark.parametrize("defect", ["missing", "duplicated"])
def test_plant_card_sync_governed_heading_count(tmp_path, defect):
    paths, _, _, _ = case(tmp_path)
    text = paths[3].read_text()
    if defect == "missing":
        text = text.replace("### C6 Typical neighbours\n\n", "")
    else:
        text += "### C5 Customs supplier lens\n"
    paths[3].write_text(text)
    with pytest.raises(ValueError, match="card_sync_section_missing"):
        verify_method_cards_sync(paths[0], paths[3])


def test_plant_record_governed_sections_mismatch(tmp_path):
    paths, record, _, _ = case(tmp_path)
    record["governed_sections"] = record["governed_sections"][:4]
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match="card_sync_sections_unrecorded"):
        validate_source_check_record(*paths[:3])


def test_edit_outside_governed_sections_leaves_sync_green(tmp_path):
    paths, _, _, _ = case(tmp_path)
    text = paths[3].read_text()
    text = text.replace(
        "# Invented method cards\n\n",
        "# Invented method cards, edited outside the governed sections\n\n",
    )
    text = text.replace(
        "## 4. Version 1 method cards\n",
        "## 4. Version 1 method cards, edited outside the governed sections\n",
    )
    text = text.replace(
        "## 5. Method cards added by decisions 0016 and 0017\n",
        "## 5. Method cards added by decisions 0016 and 0017, edited outside\n",
    )
    paths[3].write_text(text)
    verify_method_cards_sync(paths[0], paths[3])


def test_committed_record_schema_valid_but_both_gates_fail(tmp_path):
    entries = validate_source_check_record(
        COMMITTED_RECORD, tmp_path / "absent", tmp_path / "absent"
    )
    assert set(entries) == set(PINS)
    assert all(not entry.values and entry.unpinned_reason for entry in entries.values())
    verify_method_cards_sync(COMMITTED_RECORD, COMMITTED_METHODS)
    for gate in ("S2", "S7"):
        with pytest.raises(ValueError, match=re.escape(gate + ":unpinned:")):
            completion_evidence(
                COMMITTED_RECORD,
                tmp_path / "absent",
                tmp_path / "absent",
                COMMITTED_METHODS,
                gate=gate,
            )


@pytest.mark.parametrize(
    "defect,code",
    [
        ("missing", "pin_missing_or_duplicate"),
        ("duplicate", "pin_missing_or_duplicate"),
        ("unknown", "pin_record_fields"),
        ("bool_value", "pin_review_result"),
        ("lineage", "pin_record_text"),
        ("date", "pin_review_date"),
    ],
)
def test_closed_record_schema(tmp_path, defect, code):
    paths, record, artifact, _ = case(tmp_path)
    if defect == "missing":
        record["pins"].pop()
    elif defect == "duplicate":
        record["pins"].append(record["pins"][0])
    elif defect == "unknown":
        record["pins"][0]["unknown"] = True
    elif defect == "bool_value":
        record["pins"][0]["checked_against_source"] = 1
    elif defect == "lineage":
        # The empty licence is planted in the record and in the artifact row
        # of the same pin, so only the record's own text guard can fail.
        record["pins"][0]["source_lineage"][0]["licence_id"] = ""
        artifact["pins"][0]["source_lineage"][0]["licence_id"] = ""
    else:
        record["pins"][0]["review_date"] = "not-a-date"
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match=re.escape(code)):
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
    paths[3].write_text(methods_document([]))
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
    with pytest.raises(ValueError, match="pin_unrecorded_setting"):
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
    with pytest.raises(ValueError, match="c5_parent_visible_label_missing"):
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
