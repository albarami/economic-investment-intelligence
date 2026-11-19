"""Closed, offline reviewed inputs for the existing milestone audit."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from custodian.tests.test_investment_evidence import (
    _milestone_envelope,
    _milestone_shape,
)
from custodian.tests.test_source_completeness import entry

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_milestones import load_milestones


def test_missing_review_is_no_independent_milestone_claim(tmp_path: Path) -> None:
    assert load_milestones(tmp_path, ()) == ()


def test_review_is_closed_and_passes_real_typed_arguments(tmp_path: Path) -> None:
    envelope = _milestone_envelope()
    shape = _milestone_shape()
    row = entry(source=envelope.source_id)
    document = {
        "milestones": [
            {
                "key": row.key,
                "identity": "a" * 64,
                "shape": {**asdict(shape), "fields": sorted(shape.fields)},
                "envelope": asdict(envelope),
                "links": [],
                "crosswalk_key": "",
            }
        ]
    }
    (tmp_path / "review").mkdir()
    path = tmp_path / "review/investment_milestones.json"
    path.write_text(json.dumps(document))
    selected = load_milestones(tmp_path, (row,))
    assert selected[0].shape == shape
    assert selected[0].envelope == envelope
    assert selected[0].identity == "a" * 64
    document["milestones"][0]["unknown"] = "SYN-extra"
    path.write_text(json.dumps(document))
    with pytest.raises(AssemblyError, match="assembly_milestone_review_invalid"):
        load_milestones(tmp_path, (row,))


def test_registry_only_or_other_source_cannot_be_a_milestone(tmp_path: Path) -> None:
    (tmp_path / "review").mkdir()
    path = tmp_path / "review/investment_milestones.json"
    path.write_text(json.dumps({"milestones": [{"key": "unregistered"}]}))
    with pytest.raises(AssemblyError, match="assembly_milestone_review_invalid"):
        load_milestones(tmp_path, ())
