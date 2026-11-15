"""Full text of the allow-list and mapped-edge refusals.

A CSV reader yields only text, so a non-text allow-list cell is handed to the
row parser directly.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from eii_custodian.publicdata.review.graph import GraphError, _allowlist_row


def _as_any(value: Any) -> Any:
    """Return the argument unchanged."""
    return value


def _refuses(call: object, message: str) -> None:
    """The call raises GraphError with this full text."""
    assert callable(call)
    with pytest.raises(GraphError) as caught:
        call()
    found = caught.value
    assert str(found) == message
    assert found.detail == message


def _load_fixtures() -> Any:
    """Load the invented mapped-row builders from the existing graph tests."""
    path = Path(__file__).with_name("test_activity_graph.py")
    spec = importlib.util.spec_from_file_location("graph_mapped_builders", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FIXTURES = _load_fixtures()


def _row(**changes: object) -> dict[str, object]:
    """One allow-list record with text in every cell."""
    values: dict[str, object] = {
        "isic_class": "5610",
        "category": "cafe",
        "reviewed_by_role": "reader",
        "reviewed_on": "2026-11-01",
    }
    values.update(changes)
    return values


def test_allowlist_class_that_is_not_text_is_named() -> None:
    """A non-text class cell is refused as not a digit string."""
    _refuses(
        lambda: _allowlist_row(_row(isic_class=_as_any(5610))),
        "allow-list class is not a digit string",
    )


def test_allowlist_class_with_a_letter_is_named() -> None:
    """A class containing a letter is refused as not a digit string."""
    _refuses(
        lambda: _allowlist_row(_row(isic_class="56A0")),
        "allow-list class is not a digit string",
    )


def test_allowlist_class_of_three_digits_is_named() -> None:
    """A digit class that is not four digits is refused."""
    _refuses(
        lambda: _allowlist_row(_row(isic_class="561")),
        "allow-list class is not four digits",
    )


def test_allowlist_category_that_is_not_text_is_named() -> None:
    """A non-text category cell is refused as empty."""
    _refuses(
        lambda: _allowlist_row(_row(category=_as_any(1))),
        "allow-list category is empty",
    )


def test_allowlist_category_of_spaces_is_named() -> None:
    """A category of spaces is refused as empty."""
    _refuses(
        lambda: _allowlist_row(_row(category="   ")),
        "allow-list category is empty",
    )


def test_allowlist_category_xxxx_is_kept() -> None:
    """The marker text is a category when the cell actually carries it."""
    row = _allowlist_row(_row(category="XXXX"))
    assert row.category == "XXXX"


def test_allowlist_sign_off_that_is_not_text_is_named() -> None:
    """A non-text reviewer role is refused."""
    _refuses(
        lambda: _allowlist_row(_row(reviewed_by_role=_as_any(1))),
        "allow-list sign-off is not text",
    )


def test_allowlist_date_xxxx_is_not_an_iso_date() -> None:
    """The marker text is not an ISO date."""
    _refuses(
        lambda: _allowlist_row(_row(reviewed_on="XXXX")),
        "allow-list date is not an ISO date",
    )


def test_allowlist_blank_date_is_kept() -> None:
    """A blank date passes the row parser."""
    row = _allowlist_row(_row(reviewed_on=""))
    assert row.reviewed_on == ""
    assert row.reviewed_by_role == "reader"


def test_mapped_edge_refusals_use_their_full_text() -> None:
    """Each mapped-row guard refuses with its full text."""
    fixtures = _FIXTURES
    activities, classes, spine = fixtures._mapped_inputs()
    dropped = tuple(row for row in classes if row.code != "5610")
    plants = (
        (
            fixtures._replace_row(spine, "561000", status="mapped", isic_class="5610"),
            activities,
            classes,
            "mapped edge is not a seven-digit code",
        ),
        (
            fixtures._replace_row(spine, "5610101", isic_class="4100"),
            activities,
            classes,
            "mapped edge class differs from the prefix",
        ),
        (
            fixtures._replace_row(spine, "5610101", isic_class="5610"),
            activities,
            dropped,
            "mapped edge class is not an ISIC class",
        ),
        (
            fixtures._replace_row(spine, "5610101", name_ar="اسم قديم"),
            activities,
            classes,
            "mapped edge name differs from the cached name",
        ),
        (
            fixtures._replace_row(spine, "5610101", reason="reviewer_rejected"),
            activities,
            classes,
            "mapped edge without the reviewer_approved reason",
        ),
        (
            fixtures._replace_row(spine, "5610101", reviewed_by_role=""),
            activities,
            classes,
            "mapped edge without a reviewer role",
        ),
        (
            fixtures._replace_row(spine, "5610101", reviewed_on=""),
            activities,
            classes,
            "mapped edge without an ISO review date",
        ),
        (
            fixtures._replace_row(spine, "5610101", reviewed_on="2026-02-31"),
            activities,
            classes,
            "mapped edge with a malformed date",
        ),
    )
    for planted, rows, titles, message in plants:
        _refuses(
            lambda planted=planted, rows=rows, titles=titles: fixtures.build_graph(
                planted, rows, titles, (), (), fixtures.load_registry()
            ),
            message,
        )
