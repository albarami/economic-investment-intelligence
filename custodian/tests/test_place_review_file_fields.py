"""The place review file field stays clear of generic secret-scanner keywords."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.review import (
    load_flagship_candidates,
    load_showcase_areas,
    load_showcase_gazetteer,
)

_ROOT = repository_root(Path(__file__))
_FILES = tuple(
    _ROOT / folder / name
    for folder, names in (
        (
            "custodian/publicdata/review",
            (
                "flagship_candidates.yaml",
                "showcase_areas.yaml",
                "showcase_gazetteer.yaml",
            ),
        ),
        (
            "custodian/tests/fixtures/places/syn_review",
            (
                "flagship_candidates.yaml",
                "showcase_areas.yaml",
                "showcase_gazetteer.yaml",
            ),
        ),
    )
    for name in names
)
_KEYWORDS = (
    "key",
    "token",
    "secret",
    "passw",
    "auth",
    "api",
    "credential",
    "creds",
    "access",
)


def _high_entropy_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) >= 16
        and any(character.isalpha() for character in value)
        and any(character.isdigit() for character in value)
    )


def _assert_no_scanner_keyword_fields(rows: Sequence[Mapping[str, object]]) -> None:
    violations = [
        (index, name)
        for index, row in enumerate(rows)
        for name, value in row.items()
        if any(word in name.casefold() for word in _KEYWORDS)
        and (name.casefold() != "place_key" or _high_entropy_identifier(value))
    ]
    if violations:
        raise AssertionError(f"scanner keyword fields: {violations}")


def _rows(path: Path) -> list[Mapping[str, object]]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    assert all(isinstance(row, dict) for row in loaded)
    return loaded


@pytest.mark.parametrize("path", _FILES, ids=lambda path: str(path.relative_to(_ROOT)))
def test_review_file_fields_avoid_scanner_keywords(path: Path) -> None:
    rows = _rows(path)
    _assert_no_scanner_keyword_fields(rows)
    planted = [dict(rows[0]) if rows else {"record_ref": None}]
    planted[0]["record_key"] = planted[0].pop("record_ref")
    with pytest.raises(AssertionError, match="record_key"):
        _assert_no_scanner_keyword_fields(planted)


@given(
    word=st.sampled_from(
        (
            "key",
            "token",
            "secret",
            "passw",
            "auth",
            "api",
            "credential",
            "creds",
            "access",
        )
    ),
    prefix=st.sampled_from(("x", "x_", "x-")),
    suffix=st.sampled_from(("x", "_x", "-x")),
    upper=st.booleans(),
)
def test_every_scanner_keyword_case_and_separator_is_refused(
    word: str, prefix: str, suffix: str, upper: bool
) -> None:
    name = prefix + (word.upper() if upper else word) + suffix
    with pytest.raises(AssertionError, match="scanner keyword fields"):
        _assert_no_scanner_keyword_fields([{name: None}])


@given(identifier=st.uuids())
def test_high_entropy_place_key_is_not_exempt(identifier: object) -> None:
    with pytest.raises(AssertionError, match="place_key"):
        _assert_no_scanner_keyword_fields([{"place_key": str(identifier)}])


@pytest.mark.parametrize(
    ("loader", "filename"),
    (
        (load_flagship_candidates, "flagship_candidates.yaml"),
        (load_showcase_areas, "showcase_areas.yaml"),
        (load_showcase_gazetteer, "showcase_gazetteer.yaml"),
    ),
)
@pytest.mark.parametrize("keep_new", (False, True))
def test_old_record_key_is_refused_with_missing_key(
    tmp_path: Path,
    loader: Callable[[Path, Path | None], tuple[str, tuple[Mapping[str, object], ...]]],
    filename: str,
    keep_new: bool,
) -> None:
    source = _rows(_ROOT / "custodian/tests/fixtures/places/syn_review" / filename)[0]
    row = dict(source)
    row["record_key"] = row["record_ref"]
    if not keep_new:
        del row["record_ref"]
    path = tmp_path / filename
    path.write_text(yaml.safe_dump([row]), encoding="utf-8")
    with pytest.raises(PlacesError, match=r"^missing_key$"):
        loader(path, None)
