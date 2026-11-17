"""LR3 support provenance values and exact frame-disagreement refusal."""

import json

import pytest
from custodian.tests.test_pub67 import FRAME, selected_fixture

from eii_custodian.publicdata.series.support import load_support, validate_support


def _whole_text(found: object, literal: str) -> None:
    assert str(found) == literal


def test_receipt_labels_are_copied(tmp_path):
    entries, selected = selected_fixture(tmp_path)
    selected.pop("lic_active")
    for entry in entries[1:]:
        path = tmp_path / entry.key / (selected[entry.key] + ".meta.json")
        receipt = json.loads(path.read_text())
        receipt["publisher"] = "SYN publisher"
        receipt["fetch_url"] = "https://example.org/SYN"
        path.write_text(json.dumps(receipt))
    _, support = load_support(tmp_path, entries, selected, FRAME)
    for source in (support["classification"], *support["frame"]["upstream"]):
        assert source["publisher"] == "SYN publisher"
        assert source["fetch_url"] == "https://example.org/SYN"
    assert support["classification"]["dataset"] == entries[1].title_en
    assert [s["dataset"] for s in support["frame"]["upstream"]] == [
        entries[2].title_en,
        entries[3].title_en,
    ]


def test_disagreeing_frame_whole_refusal(tmp_path):
    entries, selected = selected_fixture(tmp_path)
    selected.pop("lic_active")
    with pytest.raises(ValueError) as caught:
        load_support(tmp_path, entries, selected, FRAME[:1])
    _whole_text(caught.value, "supporting provenance frame differs")


@pytest.mark.parametrize("yielded", [1, 3])
def test_upstream_iteration_must_match_advertised_length(tmp_path, yielded):
    """Object admission accepts list subclasses, whose iterators can disagree."""
    entries, selected = selected_fixture(tmp_path)
    selected.pop("lic_active")
    _, support = load_support(tmp_path, entries, selected, FRAME)

    class Miscounted(list):
        def __iter__(self):
            rows = self[:1] if yielded == 1 else [*self[:2], self[0]]
            return iter(rows)

    support["frame"]["upstream"] = Miscounted(support["frame"]["upstream"])
    with pytest.raises(ValueError) as caught:
        validate_support(support)
    literal = (
        "zip() argument 2 is longer than argument 1"
        if yielded == 1
        else "zip() argument 2 is shorter than argument 1"
    )
    _whole_text(caught.value, literal)
