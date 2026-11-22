"""C47 / MTH-125: the PUB-106 height order, overlap choice and fallback errors.

The worked fixture is card C47's worked example of document 07, word for word.
Every value is invented (fixture ids SYN-B-*); the storey height of the fixture
is 4 m, an invented fixture value, not the asset manifest's stated constant.
"""

import inspect
from dataclasses import replace
from decimal import ROUND_UP, Decimal, localcontext

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from eii_core.calc.building_heights import (
    NO_PAIRS,
    NONE_SOURCE,
    ORDER,
    ORDER_EXHAUSTED,
    HeightChoice,
    choose_height,
    error_from_pairs,
    errors_by_class,
    fallback_errors,
    floor_height,
    height_counts,
    height_value,
    largest_overlap,
    metres,
    positive_height,
    scaled_cell,
)

STOREY = Decimal(4)

# building id -> (recorded, floors, 3dglobfp, wsf3d)
FIXTURE = {
    "SYN-B-0001": (Decimal(30), Decimal(8), Decimal(24), Decimal(18)),
    "SYN-B-0002": (Decimal(12), Decimal(3), Decimal(15), None),
    "SYN-B-0003": (Decimal(21), None, Decimal(15), Decimal(13)),
    "SYN-B-0004": (None, Decimal(5), Decimal(11), None),
    "SYN-B-0005": (None, None, None, Decimal(6)),
    "SYN-B-0006": (None, None, None, None),
    "SYN-B-0007": (None, None, Decimal(7), Decimal(5)),
}


def _candidates(recorded, floors, globfp, wsf3d):
    """Return one candidate row as the pipeline builds it."""
    return {
        "recorded": recorded,
        "floor_count": (floor_height(floors, STOREY) if floors is not None else None),
        "3dglobfp": globfp,
        "wsf3d": wsf3d,
    }


def _rows():
    return {
        building_id: _candidates(*values)
        for building_id, values in sorted(FIXTURE.items())
    }


def test_the_order_is_applied_building_by_building_and_the_source_is_kept():
    """C47's worked fixture: the first present source wins, per building."""
    rows = _rows()
    expected = {
        "SYN-B-0001": (Decimal(30), "recorded"),
        "SYN-B-0002": (Decimal(12), "recorded"),
        "SYN-B-0003": (Decimal(21), "recorded"),
        "SYN-B-0004": (Decimal(20), "floor_count"),
        "SYN-B-0005": (Decimal(6), "wsf3d"),
        "SYN-B-0006": (None, "none"),
        "SYN-B-0007": (Decimal(7), "3dglobfp"),
    }
    counts = {"recorded": 0, "floor_count": 0, "3dglobfp": 0, "wsf3d": 0, "none": 0}
    for building_id, (height, source) in expected.items():
        choice = choose_height(rows[building_id])
        assert choice.height == height
        assert choice.source == source
        counts[source] += 1
    assert counts == {
        "recorded": 3,
        "floor_count": 1,
        "3dglobfp": 1,
        "wsf3d": 1,
        "none": 1,
    }


def test_a_recorded_height_beats_a_3dglobfp_height_on_the_same_building():
    """3D-GloBFP under-reads towers: the recorded height always wins."""
    choice = choose_height(rows := _candidates(Decimal(30), None, Decimal(24), None))
    assert rows["recorded"] == Decimal(30)
    assert choice.height == Decimal(30)
    assert choice.source == "recorded"


def test_the_floor_count_product_times_the_storey_height():
    """The product is the floor count times the storey height passed in."""
    assert floor_height(Decimal(5), Decimal(4)) == Decimal(20)
    choice = choose_height(_candidates(None, Decimal(5), Decimal(11), None))
    assert choice.height == Decimal(20)
    assert choice.source == "floor_count"


def test_an_all_none_row_gives_none_with_order_exhausted_and_no_number():
    """MTH-09: an exhausted order returns a reason, never a zero height."""
    choice = choose_height(_candidates(None, None, None, None))
    assert choice.height is None
    assert choice.source == "none"
    assert choice.reason == ORDER_EXHAUSTED


def test_fallback_errors_come_from_the_candidate_rows_not_the_chosen_height():
    """The error block pairs every fallback with the recorded height that wins."""
    errors = fallback_errors(_rows().values())
    floor = errors["floor_count"]
    assert floor.count == 2
    assert floor.mean_signed == Decimal(1)
    assert floor.mean_absolute == Decimal(1)
    assert floor.median_absolute == Decimal(1)
    assert floor.reason == ""
    globfp = errors["3dglobfp"]
    assert globfp.count == 3
    assert globfp.mean_signed == Decimal(-3)
    assert globfp.mean_absolute == Decimal(5)
    assert globfp.median_absolute == Decimal(6)
    wsf3d = errors["wsf3d"]
    assert wsf3d.count == 2
    assert wsf3d.mean_signed == Decimal(-10)
    assert wsf3d.mean_absolute == Decimal(10)
    assert wsf3d.median_absolute == Decimal(10)


def test_errors_by_class_refuses_an_empty_class_name() -> None:
    with pytest.raises(ValueError, match="class name required"):
        errors_by_class([(Decimal("1"), Decimal("2"), "")])


def test_error_from_pairs_matches_fallback_errors_for_one_source() -> None:
    rows = _rows()
    pairs = []
    for candidates in rows.values():
        raw = candidates.get("3dglobfp")
        recorded = candidates.get("recorded")
        if raw is not None and recorded is not None:
            from eii_core.calc.building_heights import height_value

            usable = height_value(raw)
            recorded_usable = height_value(recorded)
            if usable is not None and recorded_usable is not None:
                pairs.append((usable, recorded_usable))
    assert error_from_pairs(pairs) == fallback_errors(rows.values())["3dglobfp"]


def test_errors_by_class_splits_one_fallbacks_pairs_by_class_name():
    """GlobalBuildingAtlas calibration groups error statistics by class."""
    pairs = [
        (Decimal("90"), Decimal("100"), "tower"),
        (Decimal("55"), Decimal("50"), "lowrise"),
    ]
    found = errors_by_class(pairs)
    tower = found["tower"]
    assert tower.count == 1
    assert tower.mean_signed == Decimal("-10.00")
    assert tower.mean_absolute == Decimal("10.00")
    lowrise = found["lowrise"]
    assert lowrise.count == 1
    assert lowrise.mean_signed == Decimal("5.00")
    assert lowrise.mean_absolute == Decimal("5.00")


def test_errors_by_class_on_two_pairs_shares_the_even_count_median() -> None:
    pairs = [
        (Decimal("91"), Decimal("100"), "tower"),
        (Decimal("89"), Decimal("100"), "tower"),
    ]
    block = errors_by_class(pairs)["tower"]
    assert block.count == 2
    assert block.mean_signed == Decimal("-10.00")
    assert block.median_absolute == Decimal("10.00")


def test_error_from_pairs_on_normalized_pairs_matches_fallback_errors() -> None:
    """The shared core helper only; the GBA caller's own parity is decided by
    test_gba_calibration_equals_fallback_errors_on_identical_raw_pairs."""
    rows = _rows()
    gba_pairs: list[tuple[Decimal, Decimal]] = []
    for candidates in rows.values():
        raw = candidates.get("3dglobfp")
        recorded = candidates.get("recorded")
        if raw is not None and recorded is not None:
            gba_raw = height_value(raw)
            recorded_usable = height_value(recorded)
            if gba_raw is not None and recorded_usable is not None:
                gba_pairs.append((gba_raw, recorded_usable))
    overall = error_from_pairs(gba_pairs)
    fallback = fallback_errors(rows.values())["3dglobfp"]
    assert overall.count == fallback.count
    assert overall.mean_signed == fallback.mean_signed
    assert overall.mean_absolute == fallback.mean_absolute
    assert overall.median_absolute == fallback.median_absolute


def test_error_from_pairs_on_boundary_pairs_matches_fallback_errors() -> None:
    """The shared core helper only, at the precision and half-up boundaries."""
    cases = [
        (Decimal("100.001"), Decimal("100")),
        (Decimal("99.995"), Decimal("100")),
        (Decimal("0.001"), Decimal("30")),
    ]
    for raw, recorded in cases:
        row = _candidates(recorded, None, raw, None)
        gba_usable = height_value(raw)
        recorded_usable = height_value(recorded)
        if gba_usable is None:
            assert fallback_errors([row])["3dglobfp"].count == 0
            assert error_from_pairs([]).count == 0
            continue
        assert (
            error_from_pairs([(gba_usable, recorded_usable)])
            == fallback_errors([row])["3dglobfp"]
        )


def test_errors_by_class_refuses_an_empty_input() -> None:
    assert errors_by_class(()) == {}


def test_errors_over_chosen_heights_alone_lose_the_fallbacks_of_recorded_wins():
    """Using the chosen height as the fallback drops SYN-B-0001's pair."""
    rows = _rows()
    chosen = {
        "recorded": None,
        "floor_count": None,
        "3dglobfp": None,
        "wsf3d": None,
    }
    for candidates in rows.values():
        choice = choose_height(candidates)
        if choice.source != "none":
            chosen[choice.source] = choice.height
    assert fallback_errors([chosen])["3dglobfp"].count != 3


def test_a_row_without_recorded_height_is_skipped_not_the_rows_after_it():
    """The pair filter skips only the row without a recorded height."""
    rows = [
        _candidates(Decimal(10), None, Decimal(11), None),
        _candidates(None, Decimal(8), Decimal(7), None),
        _candidates(Decimal(10), None, Decimal(12), None),
    ]
    block = fallback_errors(rows)["3dglobfp"]
    assert block.count == 2
    assert block.mean_signed == Decimal("1.5")


def test_a_fallback_with_no_pair_gives_count_0_and_no_statistic():
    """MTH-09: no pair gives a reason for each missing statistic, never 0."""
    rows = [_candidates(Decimal(30), None, None, None)]
    errors = fallback_errors(rows)
    for name in ("floor_count", "3dglobfp", "wsf3d"):
        block = errors[name]
        assert block.count == 0
        assert block.mean_signed is None
        assert block.mean_absolute is None
        assert block.median_absolute is None
        assert block.reason == NO_PAIRS
    empty = fallback_errors([])
    assert empty["3dglobfp"].count == 0


def test_an_even_count_median_is_the_mean_of_the_two_central_values():
    """The even-count median averages the two central absolute errors."""
    rows = [
        _candidates(Decimal(10), None, Decimal(11), None),
        _candidates(Decimal(10), None, Decimal(14), None),
    ]
    block = fallback_errors(rows)["3dglobfp"]
    assert block.count == 2
    assert block.median_absolute == Decimal("2.5")
    assert block.mean_signed == Decimal("2.5")


def test_an_even_count_of_four_uses_only_the_two_central_values():
    """Four absolute errors 1, 2, 3 and 10 give the median 2.5, not 1.5."""
    rows = [
        _candidates(Decimal(10), None, Decimal(11), None),
        _candidates(Decimal(10), None, Decimal(12), None),
        _candidates(Decimal(10), None, Decimal(13), None),
        _candidates(Decimal(10), None, Decimal(20), None),
    ]
    block = fallback_errors(rows)["3dglobfp"]
    assert block.count == 4
    assert block.median_absolute == Decimal("2.5")
    assert block.mean_absolute == Decimal(4)


def test_the_largest_overlap_wins_and_a_residual_tie_takes_the_lowest():
    """Overlaps 50 and 40 give 50; 40 on 'b' row 0 and 40 on 'a' row 3 give 'a' 3."""
    first = largest_overlap(
        [
            (Decimal(40), "b", 0, Decimal(8)),
            (Decimal(50), "a", 0, Decimal(9)),
        ]
    )
    assert first is not None
    assert first[0] == Decimal(50)
    assert first[1] == "a"
    tied = largest_overlap(
        [
            (Decimal(40), "b", 0, Decimal(8)),
            (Decimal(40), "a", 3, Decimal(9)),
        ]
    )
    assert tied is not None
    assert tied[1] == "a"
    assert tied[2] == 3
    assert tied[3] == Decimal(9)
    zero = largest_overlap(
        [
            (Decimal(0), "b", 0, Decimal(8)),
            (Decimal(40), "a", 0, Decimal(9)),
        ]
    )
    assert zero is not None
    assert zero[1] == "a"
    same_file = largest_overlap(
        [
            (Decimal(40), "a", 5, Decimal(8)),
            (Decimal(40), "a", 2, Decimal(9)),
        ]
    )
    assert same_file is not None
    assert same_file[2] == 2
    assert largest_overlap([]) is None


def test_metres_rounds_once_half_up_to_two_decimals() -> None:
    """The written form of a height or statistic: two decimals, halves up."""
    assert metres(Decimal(30)) == Decimal("30.00")
    assert metres(Decimal("10.005")) == Decimal("10.01")
    assert metres(Decimal("-10.005")) == Decimal("-10.01")
    assert metres(Decimal("10.004")) == Decimal("10.00")
    assert metres(Decimal("10.0051")) == Decimal("10.01")
    for bad in (10, "10.5", Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError):
            metres(bad)


@pytest.mark.parametrize(
    "good",
    [
        Decimal(7),
        Decimal("0.004"),
        Decimal("123.456789012345678"),
        Decimal("1E+60"),
    ],
)
def test_positive_height_accepts_a_positive_finite_decimal(good) -> None:
    """F5/R1: the reader's predicate lives here and rounds nothing."""
    assert positive_height(good) is True


def test_positive_height_never_rounds_the_value_it_judges() -> None:
    """A value `height_value` would drop or round keeps every digit here."""
    tiny = Decimal("0.004")
    assert positive_height(tiny) is True
    assert height_value(tiny) is None
    long_text = Decimal("123.456789012345678")
    assert positive_height(long_text) is True
    assert height_value(long_text) == Decimal("123.46")


@pytest.mark.parametrize(
    "bad",
    [Decimal(0), Decimal(-1), Decimal("-0.1"), Decimal("Infinity"), Decimal("NaN")],
)
def test_positive_height_refuses_zero_negative_and_non_finite(bad) -> None:
    """F5: the zero, negative and non-finite cases are tested here."""
    assert positive_height(bad) is False


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(float("nan"), id="nan-float"),
        pytest.param(30, id="int"),
        pytest.param("30", id="str"),
    ],
)
def test_positive_height_of_another_type_is_a_defect(bad) -> None:
    """A non-Decimal is a programming defect of the caller and raises the
    closed refusal text whole, whether the value is not finite or any other
    kind the function refuses with that text."""
    with pytest.raises(ValueError) as err:
        positive_height(bad)
    assert str(err.value) == "finite Decimal required"


def test_each_written_height_and_statistic_is_the_rounded_decimal() -> None:
    """The product, the chosen height and every statistic round once here."""
    assert floor_height(Decimal(5), Decimal("4.001")) == Decimal("20.01")
    choice = choose_height(_candidates(Decimal("30.127"), None, Decimal(24), None))
    assert choice.height == Decimal("30.13")
    assert choice.reason == ""
    rows = [
        _candidates(Decimal(1), None, Decimal("1.01"), None),
        _candidates(Decimal(1), None, Decimal("1.01"), None),
        _candidates(Decimal(1), None, Decimal("1.02"), None),
    ]
    block = fallback_errors(rows)["3dglobfp"]
    # The exact mean signed error is 0.04/3, a long decimal expansion.
    assert block.mean_signed == Decimal("0.01")
    assert block.mean_absolute == Decimal("0.01")


def test_an_error_pair_uses_the_written_heights_not_the_raw_inputs() -> None:
    """Rounded inputs give +0.01 here; the raw inputs would give +0.00."""
    rows = [_candidates(Decimal("10.004"), None, Decimal("10.006"), None)]
    block = fallback_errors(rows)["3dglobfp"]
    assert block.count == 1
    assert block.mean_signed == Decimal("0.01")
    assert block.mean_absolute == Decimal("0.01")
    assert block.median_absolute == Decimal("0.01")


def test_the_product_uses_the_calculation_context_precision() -> None:
    """A fresh 28-digit context would clip this 29-digit product before metres."""
    assert floor_height(Decimal("4115226300411892296707485593"), Decimal(3)) == Decimal(
        "12345678901235676890122456779.00"
    )


def test_the_statistics_use_the_calculation_context_precision() -> None:
    """A fresh 28-digit context would clip this 31-digit error before metres."""
    found = fallback_errors(
        [
            _candidates(
                Decimal(1),
                None,
                Decimal("100000000000000000000000000000.005"),
                None,
            )
        ]
    )["3dglobfp"]
    expected = Decimal("99999999999999999999999999999.01")
    assert found.mean_signed == expected
    assert found.mean_absolute == expected
    assert found.median_absolute == expected


def test_the_results_ignore_the_callers_decimal_context() -> None:
    """A hostile ambient context changes nothing: CALC_CONTEXT is used."""
    calls = [
        lambda: floor_height(Decimal(5), Decimal("0.00099998")),
        lambda: choose_height(_candidates(Decimal("30.127"), None, None, None)),
        lambda: largest_overlap(
            [
                (Decimal("1.0000001"), "a", 0, Decimal(8)),
                (Decimal("1.0000002"), "b", 0, Decimal(9)),
            ]
        ),
        lambda: fallback_errors(
            [_candidates(Decimal(10), None, Decimal("10.0049999"), None)]
        )["3dglobfp"],
    ]
    baseline = [call() for call in calls]
    with localcontext() as hostile:
        hostile.prec = 6
        hostile.rounding = ROUND_UP
        assert [call() for call in calls] == baseline


def test_the_refusal_messages_are_the_closed_texts() -> None:
    """Every refusal carries its own closed message, asserted in full."""
    with pytest.raises(ValueError) as err:
        floor_height(Decimal(0), Decimal(4))
    assert str(err.value) == "floor_count must be positive"
    with pytest.raises(ValueError) as err:
        floor_height(Decimal(5), Decimal(0))
    assert str(err.value) == "storey_height must be positive"
    candidates = {key: None for key in ORDER}
    candidates["recorded"] = Decimal(0)
    with pytest.raises(ValueError) as err:
        choose_height(candidates)
    assert str(err.value) == "recorded must be positive"
    with pytest.raises(ValueError) as err:
        fallback_errors([_candidates(Decimal(0), None, None, None)])
    assert str(err.value) == "recorded must be positive"
    with pytest.raises(ValueError) as err:
        choose_height(
            {**_candidates(Decimal(30), None, None, None), "invented": Decimal(1)}
        )
    assert str(err.value) == "candidate outside the closed order"
    with pytest.raises(ValueError) as err:
        fallback_errors(
            [{**_candidates(Decimal(30), None, None, None), "invented": Decimal(1)}]
        )
    assert str(err.value) == "candidate outside the closed order"
    with pytest.raises(ValueError) as err:
        largest_overlap([(Decimal(-1), "a", 0, Decimal(8))])
    assert str(err.value) == "overlap area must not be negative"
    with pytest.raises(ValueError) as err:
        height_value("30")
    assert str(err.value) == "finite Decimal required"
    with pytest.raises(ValueError) as err:
        height_counts([HeightChoice(Decimal("30"), "invented", "", ())], [[]])
    assert str(err.value) == "height source outside the closed list"
    with pytest.raises(ValueError) as err:
        height_counts([HeightChoice(None, NONE_SOURCE, "", ())], [[]])
    assert str(err.value) == "a none choice needs its reason"
    with pytest.raises(ValueError) as err:
        height_counts(
            [HeightChoice(None, NONE_SOURCE, ORDER_EXHAUSTED, ("recorded",))], [[]]
        )
    assert str(err.value) == "candidate outside the closed order"


def test_a_zero_overlap_area_is_a_candidate_not_a_refusal() -> None:
    """Only a negative area is refused; an all-zero tie takes the lowest."""
    winner = largest_overlap(
        [
            (Decimal(0), "b", 0, Decimal(9)),
            (Decimal(0), "a", 3, Decimal(8)),
        ]
    )
    assert winner == (Decimal(0), "a", 3, Decimal(8))


@pytest.mark.parametrize(
    "floors,storey",
    [
        (Decimal(0), Decimal(4)),
        (Decimal(-2), Decimal(4)),
        (Decimal("Infinity"), Decimal(4)),
        (Decimal("NaN"), Decimal(4)),
        (Decimal(5), Decimal(0)),
        (Decimal(5), Decimal("-1")),
        (Decimal(5), Decimal("Infinity")),
        (Decimal(5), Decimal("NaN")),
        (5, Decimal(4)),
        (Decimal(5), 4),
        ("5", Decimal(4)),
    ],
)
def test_a_non_positive_or_non_finite_floor_count_or_storey_is_refused(floors, storey):
    """Every floor count and storey height is a positive finite Decimal."""
    with pytest.raises(ValueError):
        floor_height(floors, storey)


@pytest.mark.parametrize(
    "bad",
    [
        Decimal(0),
        Decimal(-1),
        Decimal("Infinity"),
        Decimal("NaN"),
        Decimal("0.004"),
        pytest.param(30, id="int"),
        pytest.param("30", id="str"),
    ],
)
def test_a_non_positive_or_non_finite_recorded_height_is_refused(bad):
    """A recorded candidate that is not a usable height is refused."""
    with pytest.raises(ValueError):
        choose_height(
            {
                "recorded": bad,
                "floor_count": None,
                "3dglobfp": Decimal(7),
                "wsf3d": None,
            }
        )


@pytest.mark.parametrize(
    "bad",
    [Decimal(0), Decimal(-1), Decimal("Infinity"), Decimal("NaN")],
)
def test_a_non_positive_or_non_finite_fallback_is_no_value(bad):
    """V1: a bad fallback candidate is no value, counted, never a crash."""
    choice = choose_height(
        {
            "recorded": Decimal(30),
            "floor_count": None,
            "3dglobfp": bad,
            "wsf3d": Decimal(5),
        }
    )
    assert choice.height == Decimal(30)
    assert choice.source == "recorded"
    assert choice.dropped == ("3dglobfp",)
    alone = choose_height(
        {
            "recorded": None,
            "floor_count": None,
            "3dglobfp": bad,
            "wsf3d": Decimal(5),
        }
    )
    assert alone.height == Decimal(5)
    assert alone.source == "wsf3d"
    assert alone.dropped == ("3dglobfp",)


@pytest.mark.parametrize(
    "bad", [pytest.param(30, id="int"), pytest.param("30", id="str")]
)
def test_a_fallback_candidate_of_another_type_is_a_defect(bad):
    """A non-Decimal fallback is a programming error and still raises."""
    with pytest.raises(ValueError):
        choose_height(
            {
                "recorded": None,
                "floor_count": None,
                "3dglobfp": bad,
                "wsf3d": Decimal(5),
            }
        )


def test_a_candidate_outside_the_closed_order_is_refused():
    """No fifth name ever enters the order."""
    with pytest.raises(ValueError):
        choose_height(
            {
                "recorded": Decimal(30),
                "floor_count": None,
                "3dglobfp": None,
                "wsf3d": None,
                "invented_source": Decimal(99),
            }
        )
    with pytest.raises(ValueError):
        fallback_errors(
            [
                {
                    "recorded": Decimal(30),
                    "floor_count": None,
                    "3dglobfp": None,
                    "wsf3d": None,
                    "invented_source": Decimal(99),
                }
            ]
        )


def test_a_fallback_that_rounds_to_zero_is_no_value_and_counted():
    """V7: a fallback height that rounds to 0.00 at the stated places is none."""
    choice = choose_height(_candidates(None, None, Decimal("0.004"), Decimal(7)))
    assert choice.height == Decimal(7)
    assert choice.source == "wsf3d"
    assert choice.dropped == ("3dglobfp",)
    alone = choose_height(_candidates(None, None, None, Decimal("0.004")))
    assert alone.source == "none"
    assert alone.reason == ORDER_EXHAUSTED
    assert alone.dropped == ("wsf3d",)


def test_a_bad_fallback_contributes_no_error_pair_and_loses_no_valid_pair():
    """V1: a non-positive fallback is skipped; the valid pairs stay."""
    rows = [
        _candidates(Decimal(10), None, Decimal(0), None),
        _candidates(Decimal(10), None, Decimal(11), None),
    ]
    block = fallback_errors(rows)["3dglobfp"]
    assert block.count == 1
    assert block.mean_signed == Decimal(1)


def test_a_floor_product_cannot_round_to_zero_at_the_stated_places():
    """V7: a positive floor count times a positive storey height is >= it."""
    assert floor_height(Decimal(1), STOREY) == STOREY
    assert floor_height(Decimal(2), STOREY) > floor_height(Decimal(1), STOREY)


def test_a_rounded_zero_is_written_without_a_sign():
    """V5: a rounded zero is unsigned, on the function and through the errors."""
    assert str(metres(Decimal("-0.004"))) == "0.00"
    assert str(metres(Decimal("-0.005"))) == "-0.01"
    rows = [
        _candidates(Decimal(10), None, Decimal("9.99"), None),
        _candidates(Decimal(10), None, Decimal("10.00"), None),
        _candidates(Decimal(10), None, Decimal("10.00"), None),
    ]
    block = fallback_errors(rows)["3dglobfp"]
    # The errors are -0.01, 0 and 0: the exact mean signed error is
    # -0.0033..., a rounded zero that is written "0.00", never "-0.00".
    assert str(block.mean_signed) == "0.00"
    assert not block.mean_signed.is_signed()
    assert str(block.mean_absolute) == "0.00"
    assert str(block.median_absolute) == "0.00"


def test_height_counts_counts_every_choice_once_by_source():
    """V10: counts by source, none reasons, drops and fallbacks, one function."""
    rows = _rows()
    counts = height_counts(
        [choose_height(row) for row in rows.values()], [[] for _ in rows]
    )
    assert counts.by_source == {
        "recorded": 3,
        "floor_count": 1,
        "3dglobfp": 1,
        "wsf3d": 1,
        "none": 1,
    }
    assert counts.none_reasons == {"order_exhausted": 1}
    assert counts.no_value_reasons == {}
    assert counts.fallback_buildings == 3


def test_height_counts_names_each_dropped_value_with_its_reason():
    """V1/V10: a dropped fallback value counts under <source>_value_not_positive."""
    choices = [
        choose_height(_candidates(Decimal(30), None, None, Decimal(0))),
        choose_height(_candidates(None, None, None, Decimal(0))),
        choose_height(_candidates(None, None, Decimal("0.004"), None)),
    ]
    counts = height_counts(choices, [[], [], []])
    assert counts.no_value_reasons == {
        "3dglobfp_value_not_positive": 1,
        "wsf3d_value_not_positive": 2,
    }
    assert counts.by_source["recorded"] == 1
    assert counts.none_reasons == {"order_exhausted": 2}
    assert counts.fallback_buildings == 0


def test_height_counts_keeps_the_resolved_none_reason_and_empty_choices():
    """V10: a none row keeps its written reason; an empty run gives zeros."""
    resolved = [
        replace(choice, reason="structure_unconfirmed")
        if choice.source == "none"
        else choice
        for choice in (choose_height(row) for row in _rows().values())
    ]
    counts = height_counts(resolved, [[] for _ in _rows()])
    assert counts.none_reasons == {"structure_unconfirmed": 1}
    empty = height_counts([], [])
    assert empty.by_source == {
        "recorded": 0,
        "floor_count": 0,
        "3dglobfp": 0,
        "wsf3d": 0,
        "none": 0,
    }
    assert empty.fallback_buildings == 0


def test_height_counts_refuses_a_source_outside_the_closed_list():
    """V10: an invented source on a choice is refused, never counted."""
    with pytest.raises(ValueError):
        height_counts([HeightChoice(Decimal(5), "invented_source", "")], [[]])
    with pytest.raises(ValueError):
        height_counts([HeightChoice(None, "none", "")], [[]])


def test_a_match_list_of_the_wrong_length_is_refused() -> None:
    """P4: the match list pairs one row with each choice, by index."""
    choice = HeightChoice(Decimal(7), "3dglobfp", "", ())
    with pytest.raises(ValueError) as err:
        height_counts([choice], [])
    assert str(err.value) == "match list length differs from the choices"
    with pytest.raises(ValueError) as err:
        height_counts([], [[]])
    assert str(err.value) == "match list length differs from the choices"


def test_globfp_matches_is_a_required_argument() -> None:
    """P4: no default match list; every caller passes one row per choice."""
    parameter = inspect.signature(height_counts).parameters["globfp_matches"]
    assert parameter.default is inspect.Parameter.empty


def test_scaled_cell_multiplies_the_stored_value_by_the_declared_scale():
    """A stored raster value times the declared scale, one Decimal product."""
    assert scaled_cell(Decimal(180), Decimal("0.1")) == Decimal("18.0")
    assert scaled_cell(Decimal(7), Decimal("0.1")) == Decimal("0.7")
    assert scaled_cell(Decimal(-32767), Decimal("0.1")) == Decimal("-3276.7")
    for stored, scale in (
        (Decimal(1), Decimal(0)),
        (Decimal(1), Decimal("-0.1")),
        (Decimal(1), Decimal("NaN")),
        (Decimal("NaN"), Decimal("0.1")),
        (Decimal("Infinity"), Decimal("0.1")),
        (1, Decimal("0.1")),
        (Decimal(1), 0.1),
        ("1", Decimal("0.1")),
    ):
        with pytest.raises(ValueError):
            scaled_cell(stored, scale)


def test_scaled_cell_stays_finite_when_the_product_overflows_the_context():
    """A stored value past the context precision rounds, never a crash."""
    stored = Decimal("1." + "5" * 60)
    result = scaled_cell(stored, Decimal("0.1"))
    assert result.is_finite()
    assert result > Decimal(0)


def test_height_counts_counts_a_different_height_tie_once():
    """A winning overlap tied at a different height counts one building."""
    area = Decimal(1)
    matches = [
        (area, "f", 0, Decimal(7)),
        (area, "f", 1, Decimal(9)),
    ]
    choice = HeightChoice(Decimal(7), "3dglobfp", "", ())
    counts = height_counts([choice], [matches])
    assert counts.tied_height_buildings == 1


def test_height_counts_ignores_a_same_height_or_losing_tie():
    """A tie at the winning area but one height, or among losers, is none."""
    area = Decimal(1)
    same_height = [
        (area, "f", 0, Decimal(7)),
        (area, "f", 1, Decimal(7)),
    ]
    losing_tie = [
        (Decimal(2), "f", 0, Decimal(7)),
        (Decimal(1), "f", 1, Decimal(9)),
        (Decimal(1), "f", 2, Decimal(11)),
    ]
    choice = HeightChoice(Decimal(7), "3dglobfp", "", ())
    assert height_counts([choice], [same_height]).tied_height_buildings == 0
    assert height_counts([choice], [losing_tie]).tied_height_buildings == 0
    assert height_counts([choice], [[]]).tied_height_buildings == 0


def test_scaled_cell_refusals_carry_their_closed_messages() -> None:
    """Each scale check names its own fault in the closed refusal text."""
    with pytest.raises(ValueError) as err:
        scaled_cell(Decimal("NaN"), Decimal("0.1"))
    assert str(err.value) == "finite Decimal required"
    with pytest.raises(ValueError) as err:
        scaled_cell(Decimal(1), Decimal("NaN"))
    assert str(err.value) == "finite Decimal required"
    with pytest.raises(ValueError) as err:
        scaled_cell(Decimal(1), Decimal(0))
    assert str(err.value) == "scale must be positive"


def test_scaled_cell_uses_the_calculation_context_precision() -> None:
    """The product is exact at the stated context, not the ambient one."""
    stored = Decimal("1." + "5" * 40)
    assert scaled_cell(stored, Decimal("0.1")) == Decimal("0.1" + "5" * 40)


def test_height_counts_counts_each_tied_building() -> None:
    """Two buildings each winning on a different-height tie count two."""
    area = Decimal(1)
    matches = [
        (area, "f", 0, Decimal(7)),
        (area, "f", 1, Decimal(9)),
    ]
    choice = HeightChoice(Decimal(7), "3dglobfp", "", ())
    counts = height_counts([choice, choice], [matches, matches])
    assert counts.tied_height_buildings == 2


def test_gba_counts_no_footprint_zero_overlap_unusable_ties_and_shared():
    from eii_core.calc.building_heights import gba_match_counts

    winner = (Decimal("2"), "SYN-a", 0, Decimal("20"))
    other = (Decimal("2"), "SYN-b", 0, Decimal("30"))
    tiny = (Decimal("1"), "SYN-c", 0, Decimal("0.004"))
    zero = (Decimal("0"), "SYN-z", 0, Decimal("15"))
    assert gba_match_counts(
        [
            (None, []),
            (Decimal("10"), []),
            (Decimal("10"), [tiny]),
            (Decimal("10"), [other, winner]),
            (Decimal("10"), [winner]),
            (Decimal("10"), [winner]),
            (Decimal("10"), [zero]),
        ]
    ) == {
        "recorded_buildings": 6,
        "matched": 4,
        "no_footprint": 1,
        "unusable_height": 1,
        "recorded_height_unusable": 0,
        "tied_height": 1,
        "shared_footprint": 1,
    }


def test_gba_accounting_refuses_a_planted_identity_break():
    from eii_core.calc.building_heights import gba_read_counts, sum_gba_read_counts

    counts = gba_read_counts(["", "height_null"])
    counts["rows_in_bounds"] = 1
    with pytest.raises(ValueError, match=r"^gba row accounting$"):
        sum_gba_read_counts([counts])


def test_gba_accounting_refuses_unknown_outcome():
    from eii_core.calc.building_heights import gba_read_counts

    with pytest.raises(ValueError, match=r"^gba row outcome$"):
        gba_read_counts(["SYN-unknown"])


@pytest.mark.parametrize("counter", ["height_null", "bbox_null"])
def test_gba_accounting_refuses_negative_count(counter):
    from eii_core.calc.building_heights import gba_read_counts, sum_gba_read_counts

    counts = gba_read_counts([])
    counts[counter] = -1
    with pytest.raises(ValueError, match=r"^non-negative integer count required$"):
        sum_gba_read_counts([counts])


def test_gba_accounting_refuses_unknown_counter():
    from eii_core.calc.building_heights import gba_read_counts, sum_gba_read_counts

    counts = gba_read_counts([])
    counts["SYN-extra"] = 0
    with pytest.raises(ValueError, match=r"^gba row accounting$"):
        sum_gba_read_counts([counts])


@given(
    st.lists(
        st.tuples(
            st.sampled_from(
                ["", "geometry_null", "geometry_empty", "geometry_invalid"]
            ),
            st.one_of(st.none(), st.decimals(allow_nan=True, allow_infinity=True)),
        )
    )
)
@example([])
@example([("", Decimal("-999"))])
@example([("geometry_null", None), ("geometry_empty", Decimal("NaN"))])
def test_gba_exclusions_partition_rows_with_geometry_precedence(rows):
    from collections import Counter

    from eii_core.calc.building_heights import (
        gba_exclusion,
        gba_read_counts,
        sum_gba_read_counts,
    )

    expected = Counter()
    for geometry_reason, value in rows:
        if geometry_reason:
            reason = geometry_reason
        elif value is None:
            reason = "height_null"
        elif not value.is_finite():
            reason = "height_non_finite"
        elif value == Decimal("-999"):
            reason = "height_nodata"
        elif value <= 0:
            reason = "height_non_positive"
        else:
            reason = ""
        expected[reason] += 1
    outcomes = [gba_exclusion(reason, value, Decimal("-999")) for reason, value in rows]
    counts = gba_read_counts(outcomes)
    assert counts["rows_in_bounds"] == len(rows)
    assert counts["rows_kept"] == expected[""]
    for reason in counts.keys() - {"rows_in_bounds", "rows_kept"}:
        assert counts[reason] == expected[reason]
    assert sum_gba_read_counts([counts]) == counts


@pytest.mark.parametrize("counter", ["rows_kept", "bbox_null"])
@pytest.mark.parametrize("value", [False, "0", None])
def test_gba_accounting_refuses_non_integer_counter(value, counter):
    from eii_core.calc.building_heights import gba_read_counts, sum_gba_read_counts

    counts = gba_read_counts([])
    counts[counter] = value
    with pytest.raises(ValueError, match=r"^non-negative integer count required$"):
        sum_gba_read_counts([counts])


def test_gba_bbox_null_totals_stay_outside_the_bounded_partition():
    from eii_core.calc.building_heights import gba_read_counts, sum_gba_read_counts

    first = gba_read_counts(["", "height_null"])
    second = gba_read_counts([""])
    first["bbox_null"] = 2
    second["bbox_null"] = 3
    total = sum_gba_read_counts([first, second])
    assert total == {**gba_read_counts(["", "height_null", ""]), "bbox_null": 5}


@given(
    st.lists(
        st.lists(
            st.sampled_from(
                [
                    "",
                    "geometry_null",
                    "geometry_empty",
                    "geometry_invalid",
                    "height_null",
                    "height_nodata",
                    "height_non_finite",
                    "height_non_positive",
                ]
            )
        )
    )
)
@example([])
@example([[""], ["height_nodata", "height_null"]])
def test_gba_read_counts_are_additive_and_order_independent(files):
    from eii_core.calc.building_heights import gba_read_counts, sum_gba_read_counts

    counts = [gba_read_counts(rows) for rows in files]
    combined = sum_gba_read_counts(counts)
    assert combined == gba_read_counts([reason for rows in files for reason in rows])
    assert sum_gba_read_counts(reversed(counts)) == combined


_GBA_MATCHES = st.lists(
    st.tuples(
        st.decimals(
            min_value=0,
            max_value=100,
            places=3,
            allow_nan=False,
            allow_infinity=False,
        ),
        st.sampled_from(["SYN-a", "SYN-b"]),
        st.integers(min_value=0, max_value=3),
        st.decimals(
            min_value="0.001",
            max_value="100",
            places=3,
            allow_nan=False,
            allow_infinity=False,
        ),
    ),
    unique_by=lambda row: (row[1], row[2]),
)


@given(st.lists(_GBA_MATCHES))
@example([])
@example([[]])
def test_gba_match_counts_ignore_input_scan_order(rows):
    from eii_core.calc.building_heights import gba_match_counts

    recorded = Decimal("10")
    forward = gba_match_counts([(recorded, matches) for matches in rows])
    assert forward == gba_match_counts(
        [(recorded, list(reversed(matches))) for matches in reversed(rows)]
    )
    assert forward["matched"] + forward["no_footprint"] + forward[
        "unusable_height"
    ] == len(rows)
    assert forward["recorded_buildings"] == len(rows)


def test_gba_shared_footprint_counts_distinct_reused_keys():
    from eii_core.calc.building_heights import gba_match_counts

    first = [(Decimal("1"), "SYN-a", 0, Decimal("20"))]
    second = [(Decimal("1"), "SYN-a", 1, Decimal("20"))]
    rows = [
        (Decimal("10"), matches) for matches in (first, first, second, second, second)
    ]
    assert gba_match_counts(rows)["shared_footprint"] == 2


def test_gba_match_counts_withhold_an_unusable_recorded_pair():
    from eii_core.calc.building_heights import gba_match_counts

    matches = [(Decimal("1"), "SYN-a", 0, Decimal("20"))]
    result = gba_match_counts([(Decimal("0.004"), matches)])
    assert result == {
        "recorded_buildings": 1,
        "matched": 0,
        "no_footprint": 0,
        "unusable_height": 0,
        "recorded_height_unusable": 1,
        "tied_height": 0,
        "shared_footprint": 0,
    }
    assert result["recorded_buildings"] == sum(
        result[name]
        for name in (
            "matched",
            "no_footprint",
            "unusable_height",
            "recorded_height_unusable",
        )
    )


@pytest.mark.parametrize("recorded", [None, Decimal("0.004")])
@pytest.mark.parametrize(
    ("height", "outcome"),
    [
        (None, "no_footprint"),
        (Decimal("0.004"), "unusable_height"),
        (Decimal("20"), "recorded_height_unusable"),
    ],
)
def test_gba_match_outcome_precedence(recorded, height, outcome):
    from eii_core.calc.building_heights import gba_match_counts

    matches = [] if height is None else [(Decimal("1"), "SYN-a", 0, height)]
    result = gba_match_counts([(recorded, matches)])
    assert result["recorded_buildings"] == int(recorded is not None)
    for name in (
        "matched",
        "no_footprint",
        "unusable_height",
        "recorded_height_unusable",
    ):
        assert result[name] == int(recorded is not None and name == outcome)


@given(
    st.lists(
        st.tuples(
            st.one_of(st.none(), st.decimals(allow_nan=True, allow_infinity=True)),
            _GBA_MATCHES,
        )
    )
)
@example([(Decimal("0.004"), [(Decimal("1"), "SYN-a", 0, Decimal("20"))])])
def test_gba_match_outcomes_partition_recorded_buildings(rows):
    from eii_core.calc.building_heights import gba_match_counts

    result = gba_match_counts(rows)
    assert result["recorded_buildings"] == sum(
        recorded is not None for recorded, _ in rows
    )
    assert result["recorded_buildings"] == sum(
        result[name]
        for name in (
            "matched",
            "no_footprint",
            "unusable_height",
            "recorded_height_unusable",
        )
    )


def test_gba_match_accounting_refuses_a_planted_count(monkeypatch):
    from eii_core.calc import building_heights

    class BrokenCounts:
        @staticmethod
        def fromkeys(keys, value):
            counts = dict.fromkeys(keys, value)
            counts["recorded_buildings"] = 1
            return counts

    monkeypatch.setattr(building_heights, "dict", BrokenCounts, raising=False)
    with pytest.raises(ValueError, match=r"^gba match accounting$"):
        building_heights.gba_match_counts([])
