"""Reviewed taxonomy loads offline; all adversarial identifiers are invented."""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_places_fsq import _mapping
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.policy import (
    MAPPING_COLUMNS,
    load_mapping,
    product_categories,
)

_ROOT = repository_root(Path(__file__))
_KEYS = Path(__file__).parent / "fixtures" / "places_fsq" / "place_category_keys.csv"
_MAPPING = _ROOT / "custodian/publicdata/review/places_fsq_categories.csv"
_INVENTED = {
    "source_category_id": "SYN-CATEGORY-ALPHA",
    "place_category_key": "restaurant",
    "mapping_version": "fsq-map-1",
    "review_status": "approved",
    "reviewer_role": "invented reviewer",
    "review_date": "2026-11-26",
    "rationale": "Invented dining category fits restaurant.",
}


def _write(path: Path, rows: list[dict[str, str]]) -> Path:
    """Adapt closed comma-free invented cells to the existing fixture writer."""
    return _mapping(
        path, [",".join(row[column] for column in MAPPING_COLUMNS) for row in rows]
    )


def test_places_fsq_committed_mapping_loads_with_main_place_keys() -> None:
    """Keys only are copied from the lead's diagnostic; no place rows or counts."""
    with _KEYS.open(encoding="utf-8", newline="") as handle:
        keys = frozenset(row["place_category_key"] for row in csv.DictReader(handle))
    mapping = load_mapping(_MAPPING, keys)
    assert mapping, "committed_mapping_empty"
    with _MAPPING.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == MAPPING_COLUMNS
        rows = list(reader)
    assert all(set(row) == set(MAPPING_COLUMNS) for row in rows)
    assert all(
        all(
            row[column].strip()
            for column in MAPPING_COLUMNS
            if column != "place_category_key"
        )
        for row in rows
    )
    assert len(mapping) == 763
    assert sum(row.review_status == "approved" for row in mapping) == 731
    assert sum(row.review_status == "withheld" for row in mapping) == 32
    identifiers = [row.source_category_id for row in mapping]
    assert len(identifiers) == len(set(identifiers)), "mapping_identifiers_repeat"
    assert len(mapping) == len(rows)
    with pytest.raises(PlacesFsqError, match=r"^category_unmapped$"):
        product_categories("SYN-UNREVIEWED-CATEGORY", mapping)


def test_places_fsq_mapping_refuses_changed_header(tmp_path: Path) -> None:
    path = _write(tmp_path / "mapping.csv", [_INVENTED])
    path.write_text(
        path.read_text(encoding="utf-8").replace("source_category_id", "SYN-HEADER", 1),
        encoding="utf-8",
    )
    with pytest.raises(PlacesFsqError, match=r"^mapping_header$"):
        load_mapping(path, frozenset({"restaurant"}))


@pytest.mark.parametrize("column", MAPPING_COLUMNS)
def test_places_fsq_mapping_refuses_each_missing_cell(
    tmp_path: Path, column: str
) -> None:
    row = {**_INVENTED, column: ""}
    with pytest.raises(PlacesFsqError, match=r"^mapping_unsigned$"):
        load_mapping(_write(tmp_path / "mapping.csv", [row]), frozenset({"restaurant"}))


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("review_status", "pending", "mapping_unsigned"),
        ("place_category_key", "SYN-UNKNOWN-KEY", "mapping_unknown_target"),
    ],
)
def test_places_fsq_mapping_refuses_changed_cell(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    row = {**_INVENTED, field: value}
    with pytest.raises(PlacesFsqError, match=f"^{reason}$"):
        load_mapping(_write(tmp_path / "mapping.csv", [row]), frozenset({"restaurant"}))


@pytest.mark.parametrize("target", ["restaurant", "cafe"])
def test_places_fsq_mapping_refuses_repeated_identifier(
    tmp_path: Path, target: str
) -> None:
    rows = [_INVENTED, {**_INVENTED, "place_category_key": target}]
    with pytest.raises(PlacesFsqError, match=r"^mapping_conflict$"):
        load_mapping(
            _write(tmp_path / "mapping.csv", rows), frozenset({"restaurant", "cafe"})
        )


@given(
    st.dictionaries(
        st.text(alphabet="ABCDE", min_size=1, max_size=12),
        st.sampled_from(["restaurant", "cafe", "gym"]),
        min_size=1,
        max_size=20,
    )
)
@example({"A": "restaurant", "B": "cafe", "C": "gym"})
def test_places_fsq_mapping_invented_identifiers_round_trip(
    targets: dict[str, str],
) -> None:
    """Generated identifiers and mixed targets survive loading in source order."""
    rows = [
        {
            **_INVENTED,
            "source_category_id": f"SYN-CATEGORY-{name}",
            "place_category_key": key,
        }
        for name, key in targets.items()
    ]
    identifiers = [row["source_category_id"] for row in rows]
    with TemporaryDirectory() as folder:
        mapping = load_mapping(
            _write(Path(folder) / "mapping.csv", rows),
            frozenset({"restaurant", "cafe", "gym"}),
        )
    assert [row.source_category_id for row in mapping] == identifiers
    assert product_categories(";".join(identifiers), mapping) == ";".join(
        targets.values()
    )
    with pytest.raises(PlacesFsqError, match=r"^category_unmapped$"):
        product_categories(";".join([*identifiers, "SYN-NOT-MAPPED"]), mapping)


_WITHHELD = {**_INVENTED, "review_status": "withheld", "place_category_key": ""}


def test_places_fsq_withheld_loads_and_has_no_product_key(tmp_path: Path) -> None:
    mapping = load_mapping(_write(tmp_path / "mapping.csv", [_WITHHELD]), frozenset())
    assert mapping[0].review_status == "withheld"
    assert mapping[0].place_category_key == ""
    assert product_categories(_WITHHELD["source_category_id"], mapping) is None
    with pytest.raises(PlacesFsqError, match=r"^category_unmapped$"):
        product_categories("SYN-UNKNOWN", mapping)


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("place_category_key", "restaurant", "mapping_withheld_target"),
        ("rationale", "", "mapping_withheld_rationale"),
        ("review_status", "withheled", "mapping_unsigned"),
        *[
            (column, "", "mapping_unsigned")
            for column in MAPPING_COLUMNS
            if column not in {"place_category_key", "rationale"}
        ],
    ],
)
def test_places_fsq_withheld_refuses_changed_cell(
    tmp_path: Path, column: str, value: str, reason: str
) -> None:
    row = {**_WITHHELD, column: value}
    with pytest.raises(PlacesFsqError, match=f"^{reason}$"):
        load_mapping(_write(tmp_path / "mapping.csv", [row]), frozenset({"restaurant"}))


@pytest.mark.parametrize("other", [_WITHHELD, _INVENTED])
def test_places_fsq_withheld_identifier_cannot_repeat(
    tmp_path: Path, other: dict[str, str]
) -> None:
    with pytest.raises(PlacesFsqError, match=r"^mapping_conflict$"):
        load_mapping(
            _write(tmp_path / "mapping.csv", [_WITHHELD, other]),
            frozenset({"restaurant"}),
        )


@given(st.lists(st.booleans(), min_size=1, max_size=20))
@example([True, False, True, False])
@example([False])
def test_places_fsq_withheld_preserves_approved_order(approved: list[bool]) -> None:
    rows = [
        {
            **(_INVENTED if keep else _WITHHELD),
            "source_category_id": "SYN-CATEGORY-" + "A" * (index + 1),
            "place_category_key": ("cafe" if index % 2 else "restaurant")
            if keep
            else "",
        }
        for index, keep in enumerate(approved)
    ]
    with TemporaryDirectory() as folder:
        mapping = load_mapping(
            _write(Path(folder) / "mapping.csv", rows),
            frozenset({"restaurant", "cafe"}),
        )
    result = product_categories(
        ";".join(row["source_category_id"] for row in rows), mapping
    )
    expected = [
        row["place_category_key"]
        for row, keep in zip(rows, approved, strict=True)
        if keep
    ]
    assert result == (";".join(expected) if expected else None)
