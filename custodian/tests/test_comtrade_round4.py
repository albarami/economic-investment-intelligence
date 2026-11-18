"""Round-4 plants for the chapter-product mapping refusals. Invented maps only."""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.fixtures.comtrade.invented import (
    body_for,
    invented_entry,
    invented_policy,
)

from eii_custodian.publicdata.comtrade.fetch import fetch_source
from eii_custodian.publicdata.comtrade.policy import PolicyError
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    PreparedRequest,
    SlotSecrets,
)

PRIMARY = "primary-marker"
CHAPTER_PRODUCTS = "chapter_products"


def _clock() -> str:
    return "2026-11-16T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _narrow(**overrides: object):
    base: dict[str, object] = {
        "frequencies": ["annual"],
        "periods": ["2099"],
        "flows": ["flow-in"],
        "daily_calls": 8,
    }
    base.update(overrides)
    return invented_policy(**base)


def _details(values: tuple[object, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for value in values:
        with pytest.raises(PolicyError) as caught:
            invented_policy(chapter_products=value)
        found.append(caught.value.detail)
    return tuple(found)


def test_non_map_and_empty_map_are_one_chapter_products_refusal() -> None:
    """A non-map and an empty map share the mapping-container refusal."""
    assert _details((["ch-a-1"], {})) == (CHAPTER_PRODUCTS, CHAPTER_PRODUCTS)


def test_invalid_and_empty_chapter_keys_are_one_refusal() -> None:
    """A non-string chapter key and an empty chapter key share one refusal."""
    invalid_key: dict[object, object] = {1: ["ch-a-1"]}
    empty_key: dict[object, object] = {"": ["ch-a-1"]}
    assert _details((invalid_key, empty_key)) == (
        CHAPTER_PRODUCTS,
        CHAPTER_PRODUCTS,
    )


def test_non_list_and_empty_child_lists_are_one_refusal() -> None:
    """A non-list child list and an empty child list share one refusal."""
    assert _details(({"ch-a": "ch-a-1"}, {"ch-a": []})) == (
        CHAPTER_PRODUCTS,
        CHAPTER_PRODUCTS,
    )


def test_non_string_and_empty_products_are_one_refusal() -> None:
    """A non-string product and an empty product share one refusal."""
    assert _details(({"ch-a": [1]}, {"ch-a": [""]})) == (
        CHAPTER_PRODUCTS,
        CHAPTER_PRODUCTS,
    )


def test_duplicate_product_is_a_chapter_products_refusal() -> None:
    """A repeated product in one chapter's child list is refused."""
    assert _details(({"ch-a": ["ch-a-1", "ch-a-1"]},)) == (CHAPTER_PRODUCTS,)


def test_map_omitting_a_selected_chapter_stays_pending(tmp_path: Path) -> None:
    """A valid map that leaves out a selected chapter does not activate."""
    opened: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        opened.append(request.url)
        return AttemptResult("ok", body_for(request))

    result = fetch_source(
        invented_entry(_narrow(chapter_products={"ch-other": ["ch-other-1"]})),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "chapter_products_pending"
    assert opened == []
    folder = tmp_path / "un_comtrade"
    assert not folder.exists()
    assert not (folder / "manifest.json").exists()
