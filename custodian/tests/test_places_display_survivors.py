"""The display mutants that survived the first campaign. Every place is invented."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.display import (
    CategoryResult,
    Caveat,
    CensusFigure,
    DuplicateOutcome,
    PubPlace,
    _absorb_inside,
    _labels,
    _unresolved,
    category_result,
    census_figure,
    inventory_names,
    open_listings_caveat,
    place_stand_ins,
    resolve_duplicates,
)
from eii_custodian.publicdata.places_fsq.policy import PlaceStandIn

_LICENCE = "SYN-LICENCE"
_RELEASE = "2026-10-21.0"
_SOURCE = "syn-source"
_CAVEAT_KEY = "open_listings_incomplete"
_CAVEAT_EN = "Open listings are incomplete"
_CAVEAT_AR = "القوائم المفتوحة غير مكتملة"
_ARABIC_REVIEW = "pending native review"
_CENSUS_SOURCE = "est_census"
_ABSENT = "not found in public places data"
_ARABIC_NAME = "مقهى تجريبي"
# 0.0004 degrees of latitude is 44.5 m on the pack's sphere: inside PUB-51's 50 m.
# 0.0008 degrees is 89.0 m: outside it.
_NEAR = Decimal("0.0004")
_FAR = Decimal("0.0008")


def _refusal(call: Callable[[], object], whole: str) -> None:
    """Fail unless the call refuses with exactly this whole message."""
    with pytest.raises(PlacesError) as caught:
        call()
    assert str(caught.value) == whole
    assert caught.value.reason == whole


def _row(
    place_id: str,
    confidence: Decimal,
    lon: Decimal,
    lat: Decimal,
    *,
    name: str = "SYN Cafe",
    name_ar: str | None = None,
    category: str = "syn_other",
    category_class: str = "other",
    merged: str = "",
) -> PubPlace:
    """One invented pub_place row at six decimal places."""
    return PubPlace(
        place_id,
        name,
        name_ar,
        category,
        category_class,
        lon.quantize(Decimal("0.000001")),
        lat.quantize(Decimal("0.000001")),
        7,
        _RELEASE,
        _SOURCE,
        _LICENCE,
        confidence,
        merged,
    )


def _merged_ids(outcome: DuplicateOutcome) -> dict[str, str]:
    """The merge list of every kept row, keyed by its place id."""
    return {place.place_id: place.merged_ids for place in outcome.places}


def _figure(**overrides: Any) -> CensusFigure:
    """One invented census figure carrying the frame's whole lineage."""
    fields: dict[str, Any] = {
        "source_key": _CENSUS_SOURCE,
        "table": "syn_table",
        "indicator": "syn_establishments",
        "retrieval_date": "2026-11-14",
        "digest": "c" * 64,
        "value": 1234,
    }
    fields.update(overrides)
    return CensusFigure(**fields)


def test_a_bare_number_and_each_missing_lineage_field_refuse() -> None:
    """A census input is refused whole unless every lineage field is present."""
    assert census_figure(None) is None
    assert census_figure(_figure()) == _figure()
    _refusal(lambda: census_figure(1234), "census_lineage")
    _refusal(lambda: census_figure(_figure(source_key="syn_other")), "census_lineage")
    _refusal(lambda: census_figure(_figure(table="")), "census_lineage")
    _refusal(lambda: census_figure(_figure(indicator="")), "census_lineage")
    _refusal(lambda: census_figure(_figure(retrieval_date="")), "census_lineage")
    _refusal(lambda: census_figure(_figure(digest="")), "census_lineage")


def test_the_caveat_without_a_census_holds_no_figure() -> None:
    """The standing note carries its four fixed lines and no census field."""
    assert open_listings_caveat() == Caveat(
        _CAVEAT_KEY,
        _CAVEAT_EN,
        _CAVEAT_AR,
        _ARABIC_REVIEW,
        "",
        "",
        "",
        "",
        "",
        None,
    )
    assert open_listings_caveat(None) == open_listings_caveat()


def test_the_caveat_with_a_census_carries_its_whole_lineage() -> None:
    """The same four fixed lines, then the census figure's six lineage fields."""
    assert open_listings_caveat(_figure()) == Caveat(
        _CAVEAT_KEY,
        _CAVEAT_EN,
        _CAVEAT_AR,
        _ARABIC_REVIEW,
        _CENSUS_SOURCE,
        "syn_table",
        "syn_establishments",
        "2026-11-14",
        "c" * 64,
        1234,
    )


def test_a_reviewed_duplicate_beside_a_landmark_merges_into_it() -> None:
    """Inside, only a reviewed duplicate merges, and it merges into the other row."""
    left = _row("SYN-P-L", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    right = _row("SYN-P-R", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"))
    outcome = resolve_duplicates(
        (left, right),
        frozenset({"SYN-P-L"}),
        {"SYN-P-L": "verified_open", "SYN-P-R": "duplicate"},
    )
    assert _merged_ids(outcome) == {"SYN-P-L": "SYN-P-R", "SYN-P-R": ""}
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-L"})


def test_a_landmark_pair_with_no_review_merges_nothing() -> None:
    """Inside, two rows no reviewer has settled stay apart and stay unresolved."""
    left = _row("SYN-P-L", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    right = _row("SYN-P-R", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"))
    outcome = resolve_duplicates(
        (left, right), frozenset({"SYN-P-L"}), {"SYN-P-L": "verified_open"}
    )
    assert _merged_ids(outcome) == {"SYN-P-L": "", "SYN-P-R": ""}
    assert outcome.unresolved == (("SYN-P-L", "SYN-P-R"),)
    assert outcome.shown == frozenset({"SYN-P-L", "SYN-P-R"})


def test_a_landmark_pair_with_no_review_at_all_is_unresolved() -> None:
    """One row inside and no status for either is a pair a reviewer must settle."""
    left = _row("SYN-P-L", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    right = _row("SYN-P-R", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"))
    outcome = resolve_duplicates((left, right), frozenset({"SYN-P-L"}), {})
    assert outcome.unresolved == (("SYN-P-L", "SYN-P-R"),)
    assert _merged_ids(outcome) == {"SYN-P-L": "", "SYN-P-R": ""}
    assert outcome.shown == frozenset({"SYN-P-R"})


def test_two_reviewed_duplicates_of_one_landmark_pair_stay_unresolved() -> None:
    """Both rows reviewed as duplicate is no choice, so the pair is unresolved."""
    left = _row("SYN-P-L", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    right = _row("SYN-P-R", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"))
    status = {"SYN-P-L": "duplicate", "SYN-P-R": "duplicate"}
    outcome = resolve_duplicates((left, right), frozenset({"SYN-P-L"}), status)
    assert outcome.unresolved == (("SYN-P-L", "SYN-P-R"),)
    assert _merged_ids(outcome) == {"SYN-P-L": "", "SYN-P-R": ""}
    assert outcome.shown == frozenset({"SYN-P-R"})


def test_a_reviewed_duplicate_of_a_landmark_only_reads_the_pair_it_names() -> None:
    """A pair with one row inside and one review is not the pair the review names."""
    found = _unresolved(
        (),
        (("SYN-P-L", "SYN-P-R"),),
        frozenset({"SYN-P-L"}),
        {"SYN-P-L": "duplicate"},
        {},
    )
    assert found == ()


def test_an_absorbed_pair_outside_every_area_is_not_unresolved() -> None:
    """Outside, the higher confidence absorbs the other and no pair is left over."""
    high = _row("SYN-P-A", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    low = _row("SYN-P-B", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"))
    outcome = resolve_duplicates((high, low), frozenset(), {})
    assert _merged_ids(outcome) == {"SYN-P-A": "SYN-P-B", "SYN-P-B": ""}
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-A"})


def test_the_unresolved_list_holds_the_pair_after_an_absorbed_one() -> None:
    """An absorbed pair does not stop the walk over the pairs that follow it."""
    absorbed_high = _row("SYN-P-A", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    absorbed_low = _row(
        "SYN-P-B", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"), name="SYN Cafe"
    )
    level_one = _row(
        "SYN-P-C",
        Decimal("0.8000"),
        Decimal("51.55"),
        Decimal("25.35"),
        name="SYN Shop",
    )
    level_two = _row(
        "SYN-P-D",
        Decimal("0.8000"),
        Decimal("51.55"),
        Decimal("25.35"),
        name="SYN Shop",
    )
    outcome = resolve_duplicates(
        (absorbed_high, absorbed_low, level_one, level_two), frozenset(), {}
    )
    assert outcome.unresolved == (("SYN-P-C", "SYN-P-D"),)
    assert _merged_ids(outcome) == {
        "SYN-P-A": "SYN-P-B",
        "SYN-P-B": "",
        "SYN-P-C": "",
        "SYN-P-D": "",
    }
    assert outcome.shown == frozenset({"SYN-P-A", "SYN-P-C", "SYN-P-D"})


def test_both_outside_pairs_are_unresolved() -> None:
    """Two level-confidence pairs outside every area are both left for a reviewer."""
    first = _row("SYN-P-A", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"))
    second = _row(
        "SYN-P-B", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"), name="SYN Cafe"
    )
    third = _row(
        "SYN-P-C",
        Decimal("0.8000"),
        Decimal("51.55"),
        Decimal("25.35"),
        name="SYN Shop",
    )
    fourth = _row(
        "SYN-P-D",
        Decimal("0.8000"),
        Decimal("51.55"),
        Decimal("25.35"),
        name="SYN Shop",
    )
    outcome = resolve_duplicates((first, second, third, fourth), frozenset(), {})
    assert outcome.unresolved == (("SYN-P-A", "SYN-P-B"), ("SYN-P-C", "SYN-P-D"))
    assert all(place.merged_ids == "" for place in outcome.places)
    assert outcome.shown == frozenset({"SYN-P-A", "SYN-P-B", "SYN-P-C", "SYN-P-D"})


def test_the_inside_absorb_step_walks_every_pair_it_is_given() -> None:
    """One skipped pair never stops the merge of the pairs the walk still holds.

    The step reads its pairs as a set, so no test can fix the order it walks
    them in. Twenty invented groups of four pairs each are given: a pair of two
    rows outside every area, a pair of two rows no reviewer settled, a pair with
    one reviewed duplicate that must merge, and a pair whose dropped row is
    already merged. A walk that stops at the first skipped pair loses a merge
    unless every merging pair happens to come before every skipped one, which
    one order in 137846528820 does.
    """
    pairs: list[tuple[str, str]] = []
    inside: set[str] = set()
    status: dict[str, str] = {}
    absorbed: dict[str, str] = {}
    expected: dict[str, str] = {}
    for index in range(20):
        tag = f"{index:02d}"
        pairs.append((f"SYN-A-{tag}", f"SYN-B-{tag}"))
        pairs.append((f"SYN-C-{tag}", f"SYN-D-{tag}"))
        inside.add(f"SYN-C-{tag}")
        pairs.append((f"SYN-E-{tag}", f"SYN-F-{tag}"))
        inside.add(f"SYN-E-{tag}")
        status[f"SYN-F-{tag}"] = "duplicate"
        expected[f"SYN-F-{tag}"] = f"SYN-E-{tag}"
        pairs.append((f"SYN-G-{tag}", f"SYN-H-{tag}"))
        inside.add(f"SYN-G-{tag}")
        status[f"SYN-H-{tag}"] = "duplicate"
        absorbed[f"SYN-H-{tag}"] = f"SYN-KEPT-{tag}"
        expected[f"SYN-H-{tag}"] = f"SYN-KEPT-{tag}"
    _absorb_inside((), tuple(pairs), frozenset(inside), status, absorbed)
    assert absorbed == expected


def test_the_highest_confidence_keeps_all_three_of_a_chain() -> None:
    """Three rows at one point merge into the one a reviewer would trust most."""
    high = _row("SYN-P-C", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    middle = _row(
        "SYN-P-A", Decimal("0.8500"), Decimal("51.5"), Decimal("25.3"), name="SYN Cafe"
    )
    low = _row(
        "SYN-P-B", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3"), name="SYN Cafe"
    )
    outcome = resolve_duplicates((high, middle, low), frozenset(), {})
    assert _merged_ids(outcome) == {
        "SYN-P-A": "",
        "SYN-P-B": "",
        "SYN-P-C": "SYN-P-A;SYN-P-B",
    }
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-C"})


def test_an_absorbed_keeper_does_not_absorb_the_next_row_itself() -> None:
    """A chain of three rows 44.5 m apart keeps the first and the third."""
    first = _row("SYN-P-1", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    second = _row(
        "SYN-P-2", Decimal("0.8500"), Decimal("51.5"), Decimal("25.3") + _NEAR
    )
    third = _row("SYN-P-3", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3") + _FAR)
    outcome = resolve_duplicates((first, second, third), frozenset(), {})
    assert _merged_ids(outcome) == {"SYN-P-1": "SYN-P-2", "SYN-P-2": "", "SYN-P-3": ""}
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-1", "SYN-P-3"})


def test_a_skipped_keeper_does_not_stop_the_walk_over_the_keepers() -> None:
    """Two pairs far apart merge on their own, and the first absorbed row is walked past."""
    first = _row("SYN-P-A", Decimal("0.9500"), Decimal("51.5"), Decimal("25.3"))
    second = _row(
        "SYN-P-B", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3") + _NEAR
    )
    third = _row(
        "SYN-P-C", Decimal("0.8500"), Decimal("51.5"), Decimal("25.6"), name="SYN Cafe"
    )
    fourth = _row(
        "SYN-P-D",
        Decimal("0.8000"),
        Decimal("51.5"),
        Decimal("25.6") + _NEAR,
        name="SYN Cafe",
    )
    outcome = resolve_duplicates((first, second, third, fourth), frozenset(), {})
    assert _merged_ids(outcome) == {
        "SYN-P-A": "SYN-P-B",
        "SYN-P-B": "",
        "SYN-P-C": "SYN-P-D",
        "SYN-P-D": "",
    }
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-A", "SYN-P-C"})


def test_an_absorbed_row_is_not_absorbed_again_by_a_later_keeper() -> None:
    """The middle row of a chain stays with the keeper that took it first."""
    first = _row("SYN-P-X", Decimal("0.9500"), Decimal("51.5"), Decimal("25.3"))
    second = _row(
        "SYN-P-Y", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3") + _NEAR
    )
    third = _row("SYN-P-Z", Decimal("0.9200"), Decimal("51.5"), Decimal("25.3") + _FAR)
    outcome = resolve_duplicates((first, second, third), frozenset(), {})
    assert _merged_ids(outcome) == {"SYN-P-X": "SYN-P-Y", "SYN-P-Y": "", "SYN-P-Z": ""}
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-X", "SYN-P-Z"})


def test_a_row_inside_an_area_is_never_absorbed_by_a_keeper_outside_it() -> None:
    """The showcase row stays apart and its pair is left for a reviewer."""
    keeper = _row("SYN-P-K", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    landmark = _row(
        "SYN-P-O", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3") + _NEAR
    )
    outcome = resolve_duplicates((keeper, landmark), frozenset({"SYN-P-O"}), {})
    assert _merged_ids(outcome) == {"SYN-P-K": "", "SYN-P-O": ""}
    assert outcome.unresolved == (("SYN-P-K", "SYN-P-O"),)
    assert outcome.shown == frozenset({"SYN-P-K"})


def test_a_row_inside_an_area_does_not_stop_the_walk_over_the_other_rows() -> None:
    """The keeper walks past the showcase row and still takes the row behind it."""
    landmark = _row(
        "SYN-P-A", Decimal("0.9500"), Decimal("51.5"), Decimal("25.3") + _NEAR
    )
    keeper = _row("SYN-P-M", Decimal("0.9000"), Decimal("51.5"), Decimal("25.3"))
    behind = _row(
        "SYN-P-Z", Decimal("0.8000"), Decimal("51.5"), Decimal("25.3") - _NEAR
    )
    outcome = resolve_duplicates((landmark, keeper, behind), frozenset({"SYN-P-A"}), {})
    assert _merged_ids(outcome) == {"SYN-P-A": "", "SYN-P-M": "SYN-P-Z", "SYN-P-Z": ""}
    assert outcome.unresolved == (("SYN-P-A", "SYN-P-M"),)
    assert outcome.shown == frozenset({"SYN-P-M"})


def test_a_blank_arabic_name_is_not_a_shared_label() -> None:
    """White space alone folds to nothing, so it links no pair and is not kept."""
    blank = _row(
        "SYN-P-A",
        Decimal("0.9000"),
        Decimal("51.5"),
        Decimal("25.3"),
        name="SYN Cafe",
        name_ar="   ",
    )
    other = _row(
        "SYN-P-B",
        Decimal("0.8000"),
        Decimal("51.5"),
        Decimal("25.3"),
        name="SYN Shop",
        name_ar="  ",
    )
    nameless = _row(
        "SYN-P-C", Decimal("0.9000"), Decimal("51.55"), Decimal("25.35"), name="   "
    )
    assert _labels(blank) == {"syn cafe"}
    assert _labels(other) == {"syn shop"}
    assert _labels(nameless) == set()
    outcome = resolve_duplicates((blank, other), frozenset(), {})
    assert _merged_ids(outcome) == {"SYN-P-A": "", "SYN-P-B": ""}
    assert outcome.unresolved == ()
    assert outcome.shown == frozenset({"SYN-P-A", "SYN-P-B"})


def test_a_stored_merge_list_is_sorted_and_every_field_survives() -> None:
    """A row already carrying a merge list is rewritten, sorted and whole."""
    row = PubPlace(
        "SYN-P-M",
        "SYN Cafe",
        _ARABIC_NAME,
        "syn_restaurant",
        "restaurant",
        Decimal("51.500000"),
        Decimal("25.300000"),
        42,
        _RELEASE,
        _SOURCE,
        _LICENCE,
        Decimal("0.9000"),
        "SYN-P-Z;SYN-P-A",
    )
    outcome = resolve_duplicates((row,), frozenset(), {})
    assert outcome.places == (
        PubPlace(
            "SYN-P-M",
            "SYN Cafe",
            _ARABIC_NAME,
            "syn_restaurant",
            "restaurant",
            Decimal("51.500000"),
            Decimal("25.300000"),
            42,
            _RELEASE,
            _SOURCE,
            _LICENCE,
            Decimal("0.9000"),
            "SYN-P-A;SYN-P-Z",
        ),
    )
    assert outcome.shown == frozenset({"SYN-P-M"})
    assert outcome.unresolved == ()


def test_a_present_category_counts_and_carries_no_sentence() -> None:
    """A category that exists returns its shown count and an empty sentence."""
    wanted = _row(
        "SYN-P-A",
        Decimal("0.9000"),
        Decimal("51.5"),
        Decimal("25.3"),
        category="syn_restaurant",
    )
    other = _row("SYN-P-B", Decimal("0.9000"), Decimal("51.55"), Decimal("25.35"))
    found = category_result((wanted, other), "syn_restaurant", frozenset({"SYN-P-A"}))
    assert found == CategoryResult(True, 1, "")
    absent = category_result((wanted, other), "syn_missing", frozenset({"SYN-P-A"}))
    assert absent == CategoryResult(False, None, _ABSENT)


def test_a_stand_in_row_carries_the_arabic_name_and_the_showcase_flag() -> None:
    """The further source reads the Arabic name and the showcase membership."""
    row = _row(
        "SYN-P-A",
        Decimal("0.9000"),
        Decimal("51.5"),
        Decimal("25.3"),
        name_ar=_ARABIC_NAME,
    )
    plain = _row("SYN-P-B", Decimal("0.9000"), Decimal("51.55"), Decimal("25.35"))
    assert place_stand_ins((row, plain), frozenset({"SYN-P-A"})) == (
        PlaceStandIn("SYN-P-A", "SYN Cafe", _ARABIC_NAME, 51.5, 25.3, True),
        PlaceStandIn("SYN-P-B", "SYN Cafe", None, 51.55, 25.35, False),
    )


def test_the_inventory_holds_every_name_and_every_arabic_name() -> None:
    """Both languages of a row enter the real-name inventory, in the row's order."""
    arabic = _row(
        "SYN-P-A",
        Decimal("0.9000"),
        Decimal("51.5"),
        Decimal("25.3"),
        name="SYN Cafe",
        name_ar=_ARABIC_NAME,
    )
    plain = _row(
        "SYN-P-B",
        Decimal("0.9000"),
        Decimal("51.55"),
        Decimal("25.35"),
        name="SYN Shop",
    )
    assert inventory_names((arabic, plain)) == ("SYN Cafe", _ARABIC_NAME, "SYN Shop")
