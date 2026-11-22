"""MTH-03 guard plants, all inputs invented under tmp_path.

Every plant names the exact error code of the guard it targets, and each is
built so that only that guard can fail. Assumptions to confirm in pass 2:
S2-T08 artifact/config shapes in the fixture helper, the scalar encoding for
compound values, and the per-line C5 value encoding.
"""

import copy
import re
import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from eii_custodian.publicdata.method_card_validation import (
    CONFIGURATION_PINS,
    S7_DEFERRAL_ITEM,
    S7_DEFERRED_PINS,
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
    lineage_context,
    methods_document,
    pending,
    save,
    write_json,
    write_yaml,
)


def _record(paths):
    return yaml.safe_load(paths[0].read_text())


def _validate(paths, record, **overrides):
    ctx = {**lineage_context(record), **overrides}
    return validate_source_check_record(*paths[:3], **ctx)


def _complete(paths, record, *, gate):
    ctx = lineage_context(record)
    return completion_evidence(*paths, gate=gate, **ctx)


# F10: paths anchor on the test file's own location, never on the working folder.
ROOT = Path(__file__).resolve().parents[2]
COMMITTED_RECORD = ROOT / "custodian/publicdata/review/s2_t09_source_checks.yaml"
COMMITTED_METHODS = ROOT / "docs/07_ECONOMIC_METHODS.md"
COMMITTED_OPEN_ITEMS = ROOT / "OPEN_ITEMS.md"


def _assert_unpinned_have_open_items(open_items):
    """Keep pending source-check pins attributable to an OPEN ledger item."""
    record = yaml.safe_load(COMMITTED_RECORD.read_text(encoding="utf-8"))
    sections = re.split(r"(?m)^#{1,3} ", open_items.read_text(encoding="utf-8"))
    open_sections = [
        section
        for section in sections[1:]
        if re.match(r"(?:OI-\d+|PO-S2-\d+)\b", section)
        and re.search(r"(?m)^- TYPE: OPEN\s*$", section)
    ]
    missing = [
        row["pin_id"]
        for row in record["pins"]
        if row["unpinned_reason"]
        and not any(f"`{row['pin_id']}`" in section for section in open_sections)
    ]
    if missing:
        raise AssertionError("unpinned_without_open_item:" + ",".join(missing))


def test_committed_unpinned_pins_have_open_items():
    _assert_unpinned_have_open_items(COMMITTED_OPEN_ITEMS)


def test_plant_unpinned_pin_removed_from_open_items(tmp_path):
    # Use the ledger's own bytes; removing one pin must break its attribution.
    pin = "wilson.period"
    original = COMMITTED_OPEN_ITEMS.read_text(encoding="utf-8")
    assert f"`{pin}`" in original
    planted = tmp_path / "OPEN_ITEMS.md"
    planted.write_text(original.replace(f"`{pin}`", "`removed-pin`"), encoding="utf-8")
    with pytest.raises(
        AssertionError, match="^" + re.escape(f"unpinned_without_open_item:{pin}") + "$"
    ):
        _assert_unpinned_have_open_items(planted)


# B1: the sixteen "none named" pins of the pass-1 source map, written out
# literally so neither the membership check nor the plants derives from the
# module's own set: dropping a pin from CONFIGURATION_PINS must fail a test,
# never silently deselect its plant.
NONE_NAMED_PINS = (
    "wilson.period",
    "c6.seed",
    "c6.category_ids",
    "c6.candidate_set",
    "c6.box",
    "c6.confidence_min",
    "c6.radius_m",
    "c6.permutations",
    "c6.fdr",
    "c6.min_neighbours",
    "c6.min_clq",
    "c6.max_shown",
    "c7.coordinates",
    "c7.modes",
    "c7.cutoffs",
    "c7.speed_regime",
)


def test_checked_fixture_and_sync(tmp_path):
    paths, record, _, _ = case(tmp_path)
    entries = _validate(paths, record)
    assert set(entries) == set(PINS)
    assert entries["wilson.period"].values == record["pins"][0]["values"]
    verify_method_cards_sync(paths[0], paths[3])
    for gate in ("S2", "S7"):
        assert set(_complete(paths, record, gate=gate)) == set(PINS)


def test_plant_tampered_value(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["values"]["value"] = "tampered"
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_value_mismatch"):
        _validate(paths, record)


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
        _validate(paths, record)


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
        _validate(paths, record)


def test_plant_wrong_configuration_hash(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][0]["settings_sha256"] = digest(b"wrong settings")
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_settings_hash_mismatch"):
        _validate(paths, record)


def test_plant_unrecorded_setting(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    artifact["pins"][0]["settings"]["unrecorded_seed"] = 9
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_unrecorded_setting"):
        _validate(paths, record)


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
        _complete(paths, record, gate=gate)


# Decision 0094: the five C6 neighbour and C7 shared-reach result pins, written
# out literally so the module's own set is checked, never trusted.
DEFERRED_TO_S7 = (
    "c6.expected_clq",
    "c6.expected_p",
    "c6.expected_q",
    "c7.shared_b_given_a",
    "c7.shared_a_given_b",
)
OI_283_REASON = "OI-283: computed by a later slice task, decision 0094"


def _pend(tmp_path, reasons):
    """A complete invented case with each named pin pending under its reason."""
    paths, record, artifact, _ = case(tmp_path)
    for row in record["pins"]:
        if row["pin_id"] in reasons:
            pending(row)
            row["unpinned_reason"] = reasons[row["pin_id"]]
    save(paths, record, artifact)
    paths[3].write_text(methods_document(record["pins"]), encoding="utf-8")
    return paths, record


def _refusal(paths, record, gate):
    with pytest.raises(ValueError) as refused:
        _complete(paths, record, gate=gate)
    return str(refused.value)


def test_s7_deferred_pins_are_the_five_result_pins():
    assert S7_DEFERRED_PINS == frozenset(DEFERRED_TO_S7)
    assert S7_DEFERRAL_ITEM == "OI-283: "


def test_s2_accepts_every_deferred_pin_naming_oi_283_and_s7_refuses(tmp_path):
    paths, record = _pend(tmp_path, dict.fromkeys(DEFERRED_TO_S7, OI_283_REASON))
    assert set(_complete(paths, record, gate="S2")) == set(PINS)
    # The S7 branch is unchanged: every pending pin is refused by name.
    assert _refusal(paths, record, "S7") == "S7:unpinned:" + ",".join(
        sorted(DEFERRED_TO_S7)
    )


@pytest.mark.parametrize("pin", DEFERRED_TO_S7)
def test_s2_accepts_one_deferred_pin_naming_oi_283(tmp_path, pin):
    paths, record = _pend(tmp_path, {pin: OI_283_REASON})
    assert set(_complete(paths, record, gate="S2")) == set(PINS)
    assert _refusal(paths, record, "S7") == "S7:unpinned:" + pin


@pytest.mark.parametrize("pin", [pin for pin in PINS if pin not in DEFERRED_TO_S7])
def test_plant_s2_refuses_other_pending_pin_naming_oi_283(tmp_path, pin):
    # One change from the accepted case: an S2 pin pending under OI-283.
    paths, record = _pend(tmp_path, {pin: OI_283_REASON})
    assert _refusal(paths, record, "S2") == "S2:unpinned:" + pin


@pytest.mark.parametrize(
    "reason",
    [
        "awaiting the live public build of S2-T08 part B",
        "OI-28: computed later",
        "OI-2830: computed later",
        "oi-283: computed later",
        "OI-283 computed later",
        "see OI-283: computed later",
        " OI-283: computed later",
    ],
)
@pytest.mark.parametrize("pin", DEFERRED_TO_S7)
def test_plant_s2_refuses_deferred_pin_not_naming_oi_283(tmp_path, pin, reason):
    paths, record = _pend(tmp_path, {pin: reason})
    assert _refusal(paths, record, "S2") == "S2:unpinned:" + pin


def test_plant_s2_names_only_the_refused_pin_beside_an_accepted_deferral(tmp_path):
    reasons = {"c6.expected_p": OI_283_REASON, "c14.medians_2025": OI_283_REASON}
    paths, record = _pend(tmp_path, reasons)
    assert _refusal(paths, record, "S2") == "S2:unpinned:c14.medians_2025"


@hypothesis_settings(deadline=None, max_examples=40)
@given(
    reasons=st.dictionaries(
        st.sampled_from(PINS),
        st.sampled_from([OI_283_REASON, "awaiting the live build", "OI-2830: x"]),
        max_size=6,
    )
)
def test_property_gate_outcome_over_pending_subsets(reasons):
    # Oracle written from the decision's words, not from the module's code.
    named = {pin for pin, reason in reasons.items() if reason.startswith("OI-283: ")}
    refused_s2 = sorted(set(reasons) - (named & set(DEFERRED_TO_S7)))
    with tempfile.TemporaryDirectory() as folder:
        paths, record = _pend(Path(folder), reasons)
        for gate, refused in (("S2", refused_s2), ("S7", sorted(reasons))):
            if refused:
                assert _refusal(paths, record, gate) == (
                    gate + ":unpinned:" + ",".join(refused)
                )
            else:
                assert set(_complete(paths, record, gate=gate)) == set(PINS)


def _oi_283_section(open_items):
    text = open_items.read_text(encoding="utf-8")
    return text.split("## OI-283 ", 1)[1].split("\n## ", 1)[0]


def _assert_deferred_rows(open_items):
    """Each deferred pin has its own OI-283 row naming its reason and task."""
    section = _oi_283_section(open_items)
    owners = {"c6": "S6-T10", "c7": "S7-T05"}
    missing = [
        pin
        for pin in DEFERRED_TO_S7
        if not any(
            line.startswith(f"  - `{pin}` deferred to slice S7")
            and f"task {owners[pin[:2]]}" in line
            and "decision 0094" in line
            for line in section.splitlines()
        )
    ]
    if missing:
        raise AssertionError("deferred_pin_without_oi_283_row:" + ",".join(missing))


def test_committed_oi_283_has_a_row_per_deferred_pin():
    _assert_deferred_rows(COMMITTED_OPEN_ITEMS)


def test_plant_deferred_pin_row_without_its_task(tmp_path):
    original = COMMITTED_OPEN_ITEMS.read_text(encoding="utf-8")
    planted = tmp_path / "OPEN_ITEMS.md"
    planted.write_text(
        original.replace("task S7-T05", "task S7-T99", 1), encoding="utf-8"
    )
    with pytest.raises(
        AssertionError,
        match="^"
        + re.escape("deferred_pin_without_oi_283_row:c7.shared_b_given_a")
        + "$",
    ):
        _assert_deferred_rows(planted)


@pytest.mark.parametrize("treatment", ["", "clean"])
def test_plant_contaminated_c5_parent(tmp_path, treatment):
    # Per basket line: every reviewed line of every c5 pin is contaminated,
    # so only the contaminated-treatment guard can fail.
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            for line in settings["lines"]:
                settings["lines"][line] = {
                    "parent_contains_excluded": True,
                    "parent_treatment": treatment,
                }
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
        _validate(paths, record)


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
        _validate(paths, record)


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
        _validate(paths, record)


@pytest.mark.parametrize("defect", ["lines_key", "review_field"])
def test_plant_c5_parent_review_missing(tmp_path, defect):
    # The per-line parent review is recorded in settings under "lines": a c5
    # pin without it, or with a malformed line review, has no parent review.
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            if defect == "lines_key":
                settings.pop("lines")
            else:
                next(iter(settings["lines"].values())).pop("parent_contains_excluded")
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_review_missing"):
        _validate(paths, record)


@pytest.mark.parametrize(
    "defect",
    ["value_line_without_review", "reviewed_line_without_value"],
)
def test_plant_c5_value_lines_do_not_match_parent_review(tmp_path, defect):
    # The per-line c5 values and the reviewed lines are the same key set: a
    # released line without a review, or a review without a released line,
    # is a missing parent review. Record and artifact agree, so only the
    # record's own guard can fail.
    paths, record, artifact, _ = case(tmp_path)
    for row in record["pins"]:
        if row["pin_id"].startswith("c5."):
            if defect == "value_line_without_review":
                row["values"]["unreviewed line"] = "1"
            else:
                row["values"].pop("pasta")
    for produced in artifact["pins"]:
        if produced["pin_id"].startswith("c5."):
            produced["values"] = next(
                row["values"].copy()
                for row in record["pins"]
                if row["pin_id"] == produced["pin_id"]
            )
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_review_missing"):
        _validate(paths, record)


def test_plant_c5_clean_parent_with_withheld_treatment(tmp_path):
    # Per basket line: an uncontaminated line reviewed as withheld.
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            for line in settings["lines"]:
                settings["lines"][line] = {
                    "parent_contains_excluded": False,
                    "parent_treatment": "withheld",
                }
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_treatment"):
        _validate(paths, record)


def test_plant_c5_withheld_with_value(tmp_path):
    # Per basket line: every line withheld, and the prior12/trend values are
    # per-line plain values instead of the withheld encoding.
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            for line in settings["lines"]:
                settings["lines"][line] = {
                    "parent_contains_excluded": True,
                    "parent_treatment": "withheld",
                }
    for produced in artifact["pins"]:
        pin = produced["pin_id"]
        produced["settings"] = copy.deepcopy(config["pins"][pin])
        if pin in ("c5.prior12", "c5.trend"):
            produced["values"] = {line: "1" for line in config["pins"][pin]["lines"]}
    for row in record["pins"]:
        if row["pin_id"] in ("c5.prior12", "c5.trend"):
            row["values"] = {
                line: "1" for line in config["pins"][row["pin_id"]]["lines"]
            }
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_withheld_value"):
        _validate(paths, record)


def test_plant_checked_row_without_evidence(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # The record and the artifact row agree, so only the record's own
    # checked-evidence guard can fail on the empty value set.
    record["pins"][0]["values"] = {}
    artifact["pins"][0]["values"] = {}
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_checked_evidence_missing"):
        _validate(paths, record)


def test_plant_wrong_card_anchor(tmp_path):
    paths, record, _, _ = case(tmp_path)
    record["pins"][1]["card_anchor"] = "c6"
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match="pin_unknown_or_anchor"):
        _validate(paths, record)


def test_plant_unknown_configuration_pin(tmp_path):
    paths, record, _, config = case(tmp_path)
    config["pins"]["c99.x"] = {"fixture_setting": "invented"}
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    write_yaml(paths[0], record)
    with pytest.raises(ValueError, match="pin_artifact_fields"):
        _validate(paths, record)


def test_plant_artifact_row_duplicated(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    artifact["pins"].append(copy.deepcopy(artifact["pins"][0]))
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_artifact_duplicate_or_unknown"):
        _validate(paths, record)


def test_plant_artifact_row_missing(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    artifact["pins"] = [
        row for row in artifact["pins"] if row["pin_id"] != "wilson.period"
    ]
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_artifact_missing"):
        _validate(paths, record)


def test_plant_artifact_lineage_receipt_mismatch(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # c5.hhi is a source pin (pins[1]); pins[0] wilson.period is a
    # configuration pin whose record and artifact lineage are both empty.
    record["pins"][1]["source_lineage"][0]["sha256"] = digest(b"different rows")
    artifact["pins"][1]["source_lineage"][0]["sha256"] = digest(b"different rows")
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_lineage_receipt_mismatch"):
        _validate(paths, record)


def test_plant_artifact_lineage_mismatch(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    frozen = lineage_context(record)
    tampered = copy.deepcopy(artifact["pins"][1]["source_lineage"][0])
    tampered["method_id"] = "invented.other@v2"
    artifact["pins"][1]["source_lineage"][0] = tampered
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_lineage_mismatch"):
        _validate(paths, record, **frozen)


def test_plant_lineage_date_without_timezone(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # The naive timestamp is planted in the record and in the artifact row of
    # the same source pin (c5.hhi), so only the record's own lineage-date
    # guard can fail.
    record["pins"][1]["source_lineage"][0]["retrieved_utc"] = "2026-11-18T00:00:00"
    artifact["pins"][1]["source_lineage"][0]["retrieved_utc"] = "2026-11-18T00:00:00"
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_lineage_date"):
        _validate(paths, record)


def test_plant_lineage_row_duplicated(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    # The duplicate lineage row is planted in the record and in the artifact
    # row of the same source pin (c5.hhi), so only the record's own duplicate
    # guard can fail.
    record["pins"][1]["source_lineage"].append(
        dict(record["pins"][1]["source_lineage"][0])
    )
    artifact["pins"][1]["source_lineage"].append(
        dict(artifact["pins"][1]["source_lineage"][0])
    )
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_lineage_duplicate"):
        _validate(paths, record)


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
        _validate(paths, record)


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
        _validate(paths, record)


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


def test_plant_card_sync_missing_block(tmp_path):
    # A checked pin whose block was deleted entirely: the block-free baseline
    # is unchanged and no marker survives, so only the missing-block guard
    # can fail.
    paths, record, _, _ = case(tmp_path)
    block = blocks(record["pins"][:1])
    paths[3].write_text(paths[3].read_text().replace(block, ""))
    with pytest.raises(ValueError, match="card_sync_missing_block"):
        verify_method_cards_sync(paths[0], paths[3])


def test_plant_card_sync_malformed_block(tmp_path):
    # An unclosed method-pin marker left inside a governed span: no block
    # matches it, so it survives into the block-free baseline and only the
    # malformed-marker guard can fail.
    paths, record, _, _ = case(tmp_path)
    text = paths[3].read_text()
    last = blocks([row for row in record["pins"] if row["pin_id"].startswith("c14.")])
    paths[3].write_text(
        text.replace(last, last + "<!-- method-pin:wilson.period -->\n")
    )
    with pytest.raises(ValueError, match="card_sync_malformed_block"):
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
        _validate(paths, record)


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
        # of the same source pin (c5.hhi), so only the record's own text
        # guard can fail.
        record["pins"][1]["source_lineage"][0]["licence_id"] = ""
        artifact["pins"][1]["source_lineage"][0]["licence_id"] = ""
    else:
        record["pins"][0]["review_date"] = "not-a-date"
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match=re.escape(code)):
        _validate(paths, record)


def test_pending_fixture_needs_no_live_file(tmp_path):
    paths, record, _, _ = case(tmp_path)
    for row in record["pins"]:
        pending(row)
    write_yaml(paths[0], record)
    paths[1].unlink()
    paths[2].unlink()
    assert len(_validate(paths, record)) == len(PINS)
    # No checked block may appear even when all source records are unpinned.
    paths[3].write_text(methods_document([]))
    verify_method_cards_sync(paths[0], paths[3])
    assert yaml.safe_load(paths[0].read_text())["pins"][0]["values"] == {}


def test_configuration_pins_are_the_sixteen_none_named_pins():
    # B1: the module's configuration pins are exactly the sixteen "none
    # named" pins of the pass-1 source map, and never the places_ovt source
    # pin c6.release_sha256, checked against this literal list rather than
    # against the module's own set.
    assert CONFIGURATION_PINS == frozenset(NONE_NAMED_PINS)
    assert "c6.release_sha256" not in CONFIGURATION_PINS


@pytest.mark.parametrize("pin", NONE_NAMED_PINS)
def test_plant_setting_removed_from_both_artifact_and_config(tmp_path, pin):
    # Every configuration pin: removing the recorded settings from both the
    # artifact row and the config leaves the pin's value unrecorded, and only
    # the configuration-pin guard can refuse it.
    paths, record, artifact, config = case(tmp_path)
    config["pins"][pin] = {}
    next(row for row in artifact["pins"] if row["pin_id"] == pin)["settings"] = {}
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_unrecorded_setting"):
        _validate(paths, record)


def test_c6_release_sha256_source_pin_needs_no_settings_value(tmp_path):
    # c6.release_sha256 is a places_ovt source pin with lineage, not one of
    # the 16 "none named" configuration pins: its checked value is checked by
    # its recorded settings hash and its source lineage, never by a copy of
    # its own value in the settings.
    paths, record, artifact, config = case(tmp_path)
    pin = "c6.release_sha256"
    config["pins"][pin].pop("value")
    next(row for row in artifact["pins"] if row["pin_id"] == pin)["settings"].pop(
        "value"
    )
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    entries = _validate(paths, record)
    assert entries[pin].values == {"value": "invented:" + pin}
    assert entries[pin].source_lineage != ()


def test_plant_source_pin_with_empty_lineage(tmp_path):
    # Empty lineage is accepted only for a configuration pin: on the source
    # pin c5.hhi the checked-evidence guard refuses it. The record and the
    # artifact row agree, so only the record's own guard can fail.
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][1]["source_lineage"] = []
    artifact["pins"][1]["source_lineage"] = []
    write_yaml(paths[0], record)
    write_json(paths[1], artifact)
    with pytest.raises(ValueError, match="pin_checked_evidence_missing"):
        _validate(paths, record)


def test_plant_contamination_label_not_recorded_with_value(tmp_path):
    # Per basket line: every line reviewed "includes excluded lines", and the
    # prior12/trend values keep the fixture's unmarked per-line values, so only
    # the visible-label guard can fail.
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            for line in settings["lines"]:
                settings["lines"][line] = {
                    "parent_contains_excluded": True,
                    "parent_treatment": "includes excluded lines",
                }
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_visible_label_missing"):
        _validate(paths, record)


def _mixed_lines(config, other_contains, other_treatment):
    """One clean line (pasta) and one reviewed line (other) in one pin."""
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            settings["lines"]["pasta"] = {
                "parent_contains_excluded": False,
                "parent_treatment": "clean",
            }
            settings["lines"]["other"] = {
                "parent_contains_excluded": other_contains,
                "parent_treatment": other_treatment,
            }


def test_plant_mixed_basket_withheld_line_carrying_a_value(tmp_path):
    # Mixed basket: the clean line keeps its plain value, the withheld line
    # still carries a plain value, so only the withheld-value guard can fail.
    paths, record, artifact, config = case(tmp_path)
    _mixed_lines(config, True, "withheld")
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_withheld_value"):
        _validate(paths, record)


def test_plant_mixed_basket_includes_line_without_visible_label(tmp_path):
    # Mixed basket: the clean line keeps its plain value, the "includes
    # excluded lines" line lacks the visible caveat suffix, so only the
    # visible-label guard can fail.
    paths, record, artifact, config = case(tmp_path)
    _mixed_lines(config, True, "includes excluded lines")
    for produced in artifact["pins"]:
        produced["settings"] = copy.deepcopy(config["pins"][produced["pin_id"]])
    write_json(paths[2], config)
    for row in record["pins"]:
        row["settings_sha256"] = digest(paths[2].read_bytes())
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="c5_parent_visible_label_missing"):
        _validate(paths, record)


def test_plant_mixed_basket_clean_line_carrying_a_marker(tmp_path):
    # Mixed basket: the "includes excluded lines" line is marked correctly,
    # but the clean line also carries the caveat suffix, and a clean line
    # never carries either marker.
    paths, record, artifact, config = case(tmp_path)
    _mixed_lines(config, True, "includes excluded lines")
    for row in record["pins"]:
        if row["pin_id"] in ("c5.prior12", "c5.trend"):
            for line in row["values"]:
                row["values"][line] = "1;caveat=includes excluded lines"
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
    with pytest.raises(ValueError, match="c5_parent_treatment"):
        _validate(paths, record)


@pytest.mark.parametrize(
    "other_treatment,other_value",
    [
        ("withheld", "NO_DATA:includes excluded lines"),
        ("includes excluded lines", "1;caveat=includes excluded lines"),
    ],
)
def test_mixed_basket_parent_review_accepts_one_clean_and_one_contaminated_line(
    tmp_path, other_treatment, other_value
):
    # The clean case: one clean line and one contaminated line in one pin,
    # each line's own review governing its own value, is accepted.
    paths, record, artifact, config = case(tmp_path)
    _mixed_lines(config, True, other_treatment)
    for row in record["pins"]:
        if row["pin_id"] in ("c5.prior12", "c5.trend"):
            row["values"]["other"] = other_value
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
    entries = _validate(paths, record)
    assert entries["c5.prior12"].checked_against_source


@pytest.mark.parametrize("treatment", ["includes excluded lines", "withheld"])
def test_reviewed_contaminated_parent_must_label_or_withhold_values(
    tmp_path, treatment
):
    paths, record, artifact, config = case(tmp_path)
    for pin, settings in config["pins"].items():
        if pin.startswith("c5."):
            for line in settings["lines"]:
                settings["lines"][line] = {
                    "parent_contains_excluded": True,
                    "parent_treatment": treatment,
                }
    for row in record["pins"]:
        if row["pin_id"] in ("c5.prior12", "c5.trend"):
            for line in row["values"]:
                row["values"][line] = (
                    "NO_DATA:includes excluded lines"
                    if treatment == "withheld"
                    else "1;caveat=includes excluded lines"
                )
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
    assert _validate(paths, record)["c5.prior12"].checked_against_source


def test_plant_unknown_lineage_source_id(tmp_path):
    # The unknown id is planted only in the record row of the source pin c5.hhi,
    # with the registry frozen to the pre-plant INVENTED sources so only that guard fails.
    paths, record, artifact, _ = case(tmp_path)
    frozen = lineage_context(record)
    record["pins"][1]["source_lineage"][0]["source_id"] = "invented_missing_source"
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_lineage_source_unknown"):
        _validate(paths, record, **frozen)


def test_plant_lineage_receipt_hash_mismatch(tmp_path):
    paths, record, artifact, _ = case(tmp_path)
    record["pins"][1]["source_lineage"][0]["sha256"] = digest(b"wrong receipt body")
    artifact["pins"][1]["source_lineage"][0]["sha256"] = digest(b"wrong receipt body")
    save(paths, record, artifact)
    with pytest.raises(ValueError, match="pin_lineage_receipt_mismatch"):
        _validate(paths, record)


def test_plant_lineage_context_missing_for_checked_source_pin(tmp_path):
    paths, _, _, _ = case(tmp_path)
    with pytest.raises(ValueError, match="pin_lineage_context_missing"):
        validate_source_check_record(*paths[:3])


def test_producer_writes_pin_artifact_from_generation_config(tmp_path):
    from eii_custodian.publicdata.method_card_producer import produce_pin_artifact

    paths, record, artifact, config = case(tmp_path)
    rows = [
        {
            "pin_id": row["pin_id"],
            "values": row["values"],
            "source_lineage": row["source_lineage"],
        }
        for row in record["pins"]
    ]
    built = produce_pin_artifact(config, rows)
    assert built == artifact
    write_json(paths[1], built)
    _validate(paths, record)


def test_method_pin_gate_calls_completion_evidence(tmp_path):
    from eii_custodian.publicdata import gate_report as g

    paths, record, _, _ = case(tmp_path)
    ctx = lineage_context(record)
    report = g.method_pin_gate(*paths, **ctx, gate="S2")
    assert report["task"] == "S2-T09"
    assert report["completion_evidence"] is True
    assert report["state"] == "recorded"


def test_method_pin_gate_pending_when_completion_refused(tmp_path):
    from eii_custodian.publicdata import gate_report as g

    paths, record, _, _ = case(tmp_path)
    record["pins"][0]["checked_against_source"] = False
    record["pins"][0]["unpinned_reason"] = "invented pending"
    write_yaml(paths[0], record)
    ctx = lineage_context(record)
    report = g.method_pin_gate(*paths, **ctx, gate="S2")
    assert report["completion_evidence"] is False
    assert report["state"] == "pending"


def test_plant_lineage_receipt_missing(tmp_path):
    paths, record, _, _ = case(tmp_path)
    ctx = lineage_context(record)
    missing_key = next(iter(ctx["receipts"]))
    ctx["receipts"] = {
        key: value for key, value in ctx["receipts"].items() if key != missing_key
    }
    with pytest.raises(ValueError, match="pin_lineage_receipt_missing"):
        _validate(paths, record, **ctx)


def test_registry_source_family_resolves_matching_key(tmp_path):
    from custodian.tests.test_source_completeness import receipt as build_receipt

    from eii_custodian.publicdata.fetch.registry import load_registry

    paths, record, artifact, _ = case(tmp_path)
    family = [row for row in load_registry() if row.source_id == "trade_ext"][:2]
    assert len(family) == 2
    chosen, other = family
    body = digest(b"family receipt body")
    link = record["pins"][1]["source_lineage"][0]
    link["source_id"] = "trade_ext"
    link["sha256"] = body
    artifact["pins"][1]["source_lineage"][0] = dict(link)
    save(paths, record, artifact)
    receipts = {
        chosen.key: {**build_receipt(chosen), "sha256": body},
        other.key: {**build_receipt(other), "sha256": digest(b"other body")},
    }
    ctx = lineage_context(record)
    ctx["registry"] = [
        row for row in ctx["registry"] if row.source_id != "trade_ext"
    ] + family
    ctx["receipts"] = {
        key: value for key, value in ctx["receipts"].items() if key != "trade_ext"
    }
    ctx["receipts"].update(receipts)
    _validate(paths, record, **ctx)


def test_registry_source_family_ambiguous_hash(tmp_path):
    from eii_custodian.publicdata.fetch.registry import load_registry

    paths, record, artifact, _ = case(tmp_path)
    family = [row for row in load_registry() if row.source_id == "trade_ext"][:2]
    body = digest(b"ambiguous shared body")
    link = record["pins"][1]["source_lineage"][0]
    link["source_id"] = "trade_ext"
    link["sha256"] = body
    for row in artifact["pins"]:
        if row["pin_id"] == "c5.hhi":
            row["source_lineage"][0] = dict(link)
    save(paths, record, artifact)
    receipts = {row.key: {"sha256": body} for row in family}
    with pytest.raises(ValueError, match="pin_lineage_source_ambiguous"):
        _validate(paths, record, registry=tuple(family), receipts=receipts)


def test_committed_registry_does_not_refuse_duplicate_source_families(tmp_path):
    from eii_custodian.publicdata.fetch.registry import load_registry

    paths, record, _, _ = case(tmp_path)
    invented = lineage_context(record)
    registry = (*load_registry(), *invented["registry"])
    with pytest.raises(ValueError, match="pin_lineage_receipt_missing"):
        validate_source_check_record(*paths[:3], registry=registry, receipts={})


@pytest.mark.parametrize(
    "plant,code",
    [
        ("config_lineage", "pin_configuration_lineage_forbidden"),
        ("source_missing_lineage", "pin_source_lineage_required"),
        ("duplicate_pin", "pin_artifact_duplicate_or_unknown"),
        ("missing_settings", "pin_artifact_missing"),
        ("extra_pin", "pin_artifact_fields"),
        ("incomplete", "pin_missing_or_duplicate"),
    ],
)
def test_producer_guard_plants(tmp_path, plant, code):
    from eii_custodian.publicdata.method_card_producer import produce_pin_artifact

    paths, record, _, config = case(tmp_path)
    rows = [
        {
            "pin_id": row["pin_id"],
            "values": row["values"],
            "source_lineage": row["source_lineage"],
        }
        for row in record["pins"]
    ]
    if plant == "config_lineage":
        rows[0]["source_lineage"] = [dict(rows[1]["source_lineage"][0])]
    elif plant == "source_missing_lineage":
        rows[1]["source_lineage"] = []
    elif plant == "duplicate_pin":
        rows.append(dict(rows[0]))
    elif plant == "missing_settings":
        config["pins"].pop("wilson.period")
        write_json(paths[2], config)
    elif plant == "extra_pin":
        config["pins"]["invented.extra"] = {"value": "invented"}
        write_json(paths[2], config)
    else:
        rows.pop()
    with pytest.raises(ValueError, match=re.escape(code)):
        produce_pin_artifact(config, rows)


def _producer_rows(record):
    return [
        {
            "pin_id": row["pin_id"],
            "values": row["values"],
            "source_lineage": row["source_lineage"],
        }
        for row in record["pins"]
    ]


@pytest.mark.parametrize("version", [2, 0, -1, True, 1.0, "1", None])
def test_producer_refuses_schema_version(tmp_path, version):
    from eii_custodian.publicdata.method_card_producer import produce_pin_artifact

    _, record, artifact, config = case(tmp_path)
    rows = _producer_rows(record)
    # Control: the same rows and config with version 1 produce the artifact.
    assert produce_pin_artifact(config, rows) == artifact
    planted = {**config, "schema_version": version}
    with pytest.raises(ValueError, match="pin_schema_version"):
        produce_pin_artifact(planted, rows)


# S2-P63: the closed pending representation of decision 0094, exercised at the
# producer. A deferred result pin may stay pending with empty values and empty
# lineage, never a stand-in value; no other pin may take that shape.
PENDING_LINEAGE_CASES = (
    # pin, pending values, lineage mode, exact refusal or None when accepted
    ("c6.expected_clq", True, "empty", None),
    ("c6.expected_q", True, "empty", None),
    ("c7.shared_a_given_b", True, "empty", None),
    ("c6.expected_clq", True, "link", "pin_pending_lineage_forbidden"),
    ("c7.shared_b_given_a", True, "link", "pin_pending_lineage_forbidden"),
    ("c6.expected_p", False, "empty", "pin_source_lineage_required"),
    ("c5.hhi", True, "empty", "pin_pending_not_deferred"),
    ("c5.trend", True, "link", "pin_pending_not_deferred"),
    ("c14.medians_2025", True, "empty", "pin_pending_not_deferred"),
    ("c7.district_weights", True, "empty", "pin_pending_not_deferred"),
    ("wilson.period", True, "empty", "pin_pending_not_deferred"),
    ("c6.max_shown", True, "empty", "pin_pending_not_deferred"),
    ("wilson.period", False, "link", "pin_configuration_lineage_forbidden"),
)


@pytest.mark.parametrize("pin,pend,mode,code", PENDING_LINEAGE_CASES)
def test_producer_pin_row_pending_shapes(tmp_path, pin, pend, mode, code):
    from eii_custodian.publicdata.method_card_producer import produce_pin_artifact

    _paths, record, _, config = case(tmp_path)
    rows = _producer_rows(record)
    row = next(item for item in rows if item["pin_id"] == pin)
    link = [dict(item["source_lineage"][0]) for item in rows if item["source_lineage"]]
    if pend:
        row["values"] = {}
    if mode == "empty":
        row["source_lineage"] = []
    else:
        row["source_lineage"] = link
    if code is None:
        built = produce_pin_artifact(config, rows)
        produced = next(item for item in built["pins"] if item["pin_id"] == pin)
        assert produced["values"] == row["values"]
        assert produced["source_lineage"] == row["source_lineage"]
    else:
        with pytest.raises(ValueError, match="^" + re.escape(code) + "$"):
            produce_pin_artifact(config, rows)


@hypothesis_settings(deadline=None, max_examples=60)
@given(
    pin=st.sampled_from(PINS),
    pend=st.booleans(),
    carries_lineage=st.booleans(),
)
def test_property_producer_pin_row_shape_oracle(pin, pend, carries_lineage):
    # Oracle written from decision 0094 and the pass-1 configuration rule, not
    # from the producer's code: only a deferred result pin may carry the pending
    # shape, only without lineage; a valued row keeps the existing rules.
    from eii_custodian.publicdata.method_card_producer import produce_pin_artifact

    with tempfile.TemporaryDirectory() as folder:
        _paths, record, _, config = case(Path(folder))
        rows = _producer_rows(record)
        row = next(item for item in rows if item["pin_id"] == pin)
        link = next(
            dict(item["source_lineage"][0]) for item in rows if item["source_lineage"]
        )
        row["values"] = {} if pend else {"value": "invented:" + pin}
        row["source_lineage"] = [link] if carries_lineage else []
        deferred = pin in DEFERRED_TO_S7
        if pend:
            expected = (
                None
                if deferred and not carries_lineage
                else (
                    "pin_pending_lineage_forbidden"
                    if deferred
                    else "pin_pending_not_deferred"
                )
            )
        elif pin in CONFIGURATION_PINS:
            expected = (
                None if not carries_lineage else "pin_configuration_lineage_forbidden"
            )
        else:
            expected = None if carries_lineage else "pin_source_lineage_required"
        if expected is None:
            assert produce_pin_artifact(config, rows) is not None
        else:
            with pytest.raises(ValueError, match="^" + expected + "$"):
                produce_pin_artifact(config, rows)


def test_artifact_matches_config_accepts_matching_artifact(tmp_path):
    from eii_custodian.publicdata.method_card_producer import artifact_matches_config

    _, _, artifact, config = case(tmp_path)
    assert artifact_matches_config(artifact, config) is None


@pytest.mark.parametrize("side", ["artifact", "config"])
def test_artifact_matches_config_refuses_mismatched_settings(tmp_path, side):
    from eii_custodian.publicdata.method_card_producer import artifact_matches_config

    _, _, artifact, config = case(tmp_path)
    pin = next(
        row["pin_id"] for row in artifact["pins"] if row["pin_id"] in CONFIGURATION_PINS
    )
    artifact = copy.deepcopy(artifact)
    config = copy.deepcopy(config)
    if side == "artifact":
        row = next(row for row in artifact["pins"] if row["pin_id"] == pin)
        row["settings"] = {**row["settings"], "invented_setting": "invented-a"}
    else:
        config["pins"][pin] = {**config["pins"][pin], "invented_setting": "invented-b"}
    with pytest.raises(ValueError, match="pin_artifact_mismatch"):
        artifact_matches_config(artifact, config)


def test_method_pin_evidence_records_staged_s2_outputs(tmp_path):
    from custodian.tests.method_pin_gather_fixtures import (
        gathered_s2_t09_confirmation,
        otherwise_complete_audit_with_s2_t09,
        stage_method_pin_gather_build,
    )

    from eii_custodian.publicdata.assembly_reports import require_complete

    build, *_ = stage_method_pin_gather_build(tmp_path)
    s2_t09 = gathered_s2_t09_confirmation(build)
    assert s2_t09["state"] == "recorded"
    require_complete(otherwise_complete_audit_with_s2_t09(s2_t09))
