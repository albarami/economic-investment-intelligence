"""S2-P58: section 10 figures PUB-71, PUB-72 and PUB-73 on invented counts only.

No census count or share of the real source is written here; PUB-72's
committed open anchors are read from the pack's numbers in the docstring of
the calculation, never from a real file.
"""

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st
from method_rows import chain

from eii_core.calc.public_methods import (
    licence_density_pair,
    places_in_country,
    private_employer_share,
)
from eii_core.calc.public_series import rounded

SOURCE = chain()


def share(zones, named=(69, 70)):
    return private_employer_share(zones, SOURCE, "2020", named)


def test_private_share_sums_and_rounds_half_up_once():
    # 1 of 8 is 12.5 % (0 dp half up: 13); 41 of 200 national is 20.5 %.
    zones = [(69, 1, 8), (70, 40, 192), (71, None, None)]
    assert share(zones) == {
        "national_private": "41",
        "national_all": "200",
        "national_1dp": "20.5",
        "zone_69_0dp": "13",
        "zone_70_0dp": "21",
    }


def test_private_share_one_decimal_boundary_rounds_up():
    # 1 of 16 is 6.25 %; one decimal, half up, is 6.3, never 6.2.
    assert share([(69, 1, 8), (70, 0, 8)])["national_1dp"] == "6.3"


@pytest.mark.parametrize(
    ("zones", "reason"),
    [
        ([(69, 1, 8), (70, 1, 8), (69, 1, 8)], "duplicate_zone"),
        ([(69, 1, 8), (70, None, 8)], "null_pair"),
        ([(69, 1, 8), (70, 1, None)], "null_pair"),
        ([(69, 1, 8), (70, None, None)], "zone_missing"),
        ([(69, 1, 8)], "zone_missing"),
        ([], "zone_missing"),
        ([(69, 9, 8), (70, 1, 8)], "private employed exceeds employed"),
        ([(69, -1, 8), (70, 1, 8)], "negative_count"),
        ([(69, 0, 0), (70, 1, 8)], "invalid binomial counts"),
    ],
)
def test_private_share_refusals(zones, reason):
    with pytest.raises(ValueError, match="^" + reason + "$"):
        share(zones)


zone_rows = st.lists(
    st.tuples(st.integers(1, 200), st.integers(1, 10**6)).flatmap(
        lambda pair: st.tuples(st.integers(0, pair[1]), st.just(pair[1]))
    ),
    min_size=2,
    max_size=8,
)


@given(zone_rows, st.randoms(use_true_random=False))
def test_private_share_exact_rational_oracle_and_order(rows, rng):
    zones = [
        (69 + index, private, total) for index, (private, total) in enumerate(rows)
    ]
    result = share(zones)
    private = sum(row[0] for row in rows)
    total = sum(row[1] for row in rows)
    assert result["national_private"] == str(private)
    assert result["national_all"] == str(total)
    assert result["national_1dp"] == rounded(Fraction(private * 100, total), 1)
    for index, zone in enumerate((69, 70)):
        assert result[f"zone_{zone}_0dp"] == rounded(
            Fraction(rows[index][0] * 100, rows[index][1]), 0
        )
    shuffled = list(zones)
    rng.shuffle(shuffled)
    assert share(shuffled) == result


R = "5610101"


def density(licences, residents, target="A"):
    return licence_density_pair(
        licences,
        residents,
        target=target,
        activity=R,
        period="2025",
        licence_source=chain("licences"),
        resident_source=chain("residents"),
    )


def test_density_reproduces_the_pack_worked_example():
    # Section 10 PUB-72: 361 / 111,282 x 10,000 -> 32; 4,782 / 3,219,982 -> 15.
    licences = [("A", R, 361), ("B", R, 4421), ("A", "5630112", 99), ("B", "561000", 7)]
    residents = [("A", 111282), ("B", 3108700)]
    assert density(licences, residents) == {
        "local_residents": "111282",
        "national_residents": "3219982",
        "local_0dp": "32",
        "national_0dp": "15",
    }


def test_density_zero_dp_boundary_rounds_half_up():
    # 1 / 20,000 x 10,000 is exactly 0.5 -> 1.
    assert density([("A", R, 1)], [("A", 20000)])["local_0dp"] == "1"


@pytest.mark.parametrize(
    ("licences", "residents", "reason"),
    [
        ([("A", R, 1)], [("A", 10), ("A", 10)], "population_duplicate"),
        ([("B", R, 1)], [("B", 10)], "municipality_missing"),
        ([("A", R, 1), ("B", R, 1)], [("A", 10)], "population_missing"),
        ([("A", R, 1)], [("A", 10), ("B", 10)], "population_missing"),
        ([("A", R, -1), ("A", R, 2)], [("A", 10)], "negative_count"),
        ([("A", R, 1)], [("A", -10)], "negative_count"),
        ([("A", R, 1)], [("A", 0)], "non-positive denominator"),
    ],
)
def test_density_refusals(licences, residents, reason):
    with pytest.raises(ValueError, match="^" + reason + "$"):
        density(licences, residents)


@given(
    st.lists(
        st.tuples(
            st.sampled_from("ABC"),
            st.sampled_from((R, "5630112")),
            st.integers(0, 5000),
        ),
        max_size=12,
    ),
    st.tuples(st.integers(1, 10**7), st.integers(1, 10**7), st.integers(1, 10**7)),
    st.randoms(use_true_random=False),
)
def test_density_exact_rational_oracle_and_order(rows, populations, rng):
    residents = list(zip("ABC", populations, strict=True))
    licences = [("A", R, 0), ("B", R, 0), ("C", R, 0), *rows]
    result = density(licences, residents)
    local = sum(n for key, code, n in licences if key == "A" and code == R)
    national = sum(n for _, code, n in licences if code == R)
    assert result["local_residents"] == str(populations[0])
    assert result["national_residents"] == str(sum(populations))
    assert result["local_0dp"] == rounded(Fraction(local * 10000, populations[0]), 0)
    assert result["national_0dp"] == rounded(
        Fraction(national * 10000, sum(populations)), 0
    )
    rng.shuffle(licences)
    rng.shuffle(residents)
    assert density(licences, residents) == result


def test_share_refuses_a_result_without_a_denominator(monkeypatch):
    from eii_core.calc import public_methods
    from eii_core.calc.facts import NoData

    monkeypatch.setattr(
        public_methods, "coverage_share", lambda *a, **k: NoData("no_denominator")
    )
    with pytest.raises(ValueError, match=r"^no_denominator$"):
        share([(69, 1, 8), (70, 1, 8)])


@pytest.mark.parametrize("field", ["geography", "exact_unrounded"])
def test_results_on_another_geography_are_refused(monkeypatch, field):
    from dataclasses import replace

    from eii_core.calc import public_methods

    real = public_methods.licence_density

    def moved(licences, population):
        fact = real(licences, population)
        if field == "geography":
            other = replace(fact, geography="zone:invented")
            object.__setattr__(other, "exact_unrounded", fact.exact_unrounded)
            return other
        object.__setattr__(fact, "exact_unrounded", None)
        return fact

    monkeypatch.setattr(public_methods, "licence_density", moved)
    with pytest.raises(ValueError, match=r"^geography_invalid$"):
        density([("A", R, 1)], [("A", 10)])


# PUB-73: open-places records in the frame box with an address in country QA.
# Invented boxes and records only; (west, south, east, north), inclusive.
BOX = (1.0, 2.0, 3.0, 4.0)


def inside(*countries):
    return ((1.5, 2.5, 2.5, 3.5), countries)


def qa_count(records, box=BOX):
    return places_in_country(records, box, "QA")


def test_places_on_every_box_edge_count():
    edge = ((1.0, 3.0, 2.0, 4.0), ("QA",))  # bbox equals the box exactly
    assert qa_count([edge]) == 1


@pytest.mark.parametrize(
    "bbox",
    [
        (0.999, 2.5, 2.5, 3.5),  # xmin just west
        (1.5, 3.001, 2.5, 3.5),  # xmax just east
        (1.5, 2.5, 1.999, 3.5),  # ymin just south
        (1.5, 2.5, 2.5, 4.001),  # ymax just north
    ],
)
def test_places_just_outside_on_one_side_count_not(bbox):
    assert qa_count([(bbox, ("QA",))]) == 0


@pytest.mark.parametrize(
    "countries",
    [("qa",), ("Qa",), (None,), (), None, ("QAT",), (" QA",), ("AE",)],
)
def test_places_without_an_exact_qa_country_count_not(countries):
    assert qa_count([((1.5, 2.5, 2.5, 3.5), countries)]) == 0


def test_place_with_two_qa_addresses_counts_once():
    assert qa_count([inside("QA", "QA"), inside(None, "QA"), inside("AE", "QA")]) == 3


def test_places_empty_input_counts_zero():
    assert qa_count([]) == 0


finite = st.floats(min_value=-10, max_value=10, allow_nan=False)
countries = st.one_of(
    st.none(), st.lists(st.sampled_from(["QA", "qa", "AE", None]), max_size=3)
)
record = st.tuples(st.tuples(finite, finite, finite, finite), countries)


@given(st.lists(record, max_size=30), st.tuples(finite, finite, finite, finite))
def test_places_count_matches_an_exact_rational_oracle(records, box):
    west, south, east, north = (Fraction(value) for value in box)

    def counts(item):
        (xmin, xmax, ymin, ymax), found = item
        within = (
            west <= Fraction(xmin)
            and Fraction(xmax) <= east
            and south <= Fraction(ymin)
            and Fraction(ymax) <= north
        )
        return within and any(country == "QA" for country in found or [])

    assert qa_count(records, box) == sum(1 for item in records if counts(item))
    assert qa_count(list(reversed(records)), box) == qa_count(records, box)
    assert qa_count(records + records, box) == 2 * qa_count(records, box)
