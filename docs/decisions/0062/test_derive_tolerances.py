"""Tests of the derivations behind draft decision record 0062, revision 3.

Every input below is invented. No custodian record, calibration table or
public-cache value is read. Run from the repository root:

    uv run --locked python -m unittest discover -s docs/decisions/0062 -p 'test_*.py' -v

The classes named ``Plant...`` hold DERIVATION PLANTS: invented wrong worlds
that each proposed rule must fail, with a passing or boundary control. They
show that the proposed rules separate wrong from right on fixtures. They are
not the production guards that S4-T12 will build into the fit.
"""

import unittest
from fractions import Fraction as F
from typing import ClassVar

import derive_tolerances as d

K1000 = d.tail_level(1000)  # an invented fit-wide family of 1,000 tests


def iid_cell(n: int, k: int, t: F) -> d.Cell:
    """n equal-weight units drawn at t, of which k fell in the category."""
    return d.Cell(units=tuple((1, t, i < k) for i in range(n)))


DECL_IID = d.Declaration(
    numerator="units in the category",
    denominator="units in the cell",
    target_population="declared",
    unit="declared draw unit",
    weights="equal",
    conditional_independence="declared",
    eligibility="declared",
    mechanism="iid_equal_weight",
)
DECL_W = d.Declaration(
    **{**DECL_IID.__dict__, "weights": "declared", "mechanism": "weighted_independent"}
)
DECL_H = d.Declaration(**{**DECL_IID.__dict__, "mechanism": "without_replacement"})
DECL_A = d.Declaration(
    **{
        **DECL_IID.__dict__,
        "mechanism": "deterministic_allocation",
        "rounding": "half_even",
    }
)


# ======================================================== Rule B (R1)


class RuleB(unittest.TestCase):
    """Exact binomial tails, equal allocation, Bonferroni over the fit."""

    def test_tail_level_is_alpha_over_2k(self) -> None:
        self.assertEqual(d.tail_level(1), F(1, 40))
        self.assertEqual(d.tail_level(1000), F(1, 40000))
        with self.assertRaises(ValueError):
            d.tail_level(0)

    def test_limits_equal_the_brute_force_acceptance_set(self) -> None:
        for n in range(1, 36):
            for t in (F(0), F(1, 100), F(1, 7), F(1, 2), F(3, 5), F(99, 100), F(1)):
                for k_tests in (1, 8, 1000):
                    c = d.tail_level(k_tests)
                    pmf = d.binomial_pmf(n, t)
                    accepted = [
                        k
                        for k in range(n + 1)
                        if pmf[k] > 0
                        and sum(pmf[j] for j in range(k + 1)) >= c
                        and sum(pmf[j] for j in range(k, n + 1)) >= c
                    ]
                    lo, hi = d.binomial_limits(n, t, c)
                    self.assertEqual(accepted, list(range(lo, hi + 1)), (n, t, k_tests))

    def test_cell_false_fail_is_below_alpha_over_k_for_every_small_cell(self) -> None:
        # The finite-sample guarantee: exact, sparse cells and endpoints included.
        for n in (1, 2, 5, 10, 30, 80):
            for t in (F(0), F(1, 1000), F(1, 100), F(1, 10), F(1, 2), F(97, 100), F(1)):
                for k_tests in (1, 8, 1000):
                    c = d.tail_level(k_tests)
                    lo, hi = d.binomial_limits(n, t, c)
                    self.assertLess(d.binomial_rejection(n, t, lo, hi), 2 * c)

    def test_endpoints_and_empty_cells(self) -> None:
        self.assertEqual(d.binomial_limits(500, F(0), K1000), (0, 0))
        self.assertEqual(d.binomial_limits(500, F(1), K1000), (500, 500))
        with self.assertRaises(d.Undefined):
            d.binomial_limits(0, F(1, 2), K1000)
        self.assertEqual(d.evaluate_family(DECL_IID, [], K1000), d.UNDEFINED)

    def test_review_counterexample_one_sparse_cell(self) -> None:
        # K=1, n=10, t=1%: r1 accepted only k=0, false fail 1 - 0.99^10 = 0.0956.
        r1 = d.r1_false_fail(10, F(1, 100), 1)
        self.assertEqual(r1, 1 - F(99, 100) ** 10)
        self.assertGreater(r1, F(5, 100))
        lo, hi = d.binomial_limits(10, F(1, 100), d.tail_level(1))
        self.assertEqual((lo, hi), (0, 1))
        self.assertLessEqual(d.binomial_rejection(10, F(1, 100), lo, hi), F(5, 100))

    def test_review_counterexample_eight_sparse_cells(self) -> None:
        r1 = d.r1_false_fail(10, F(1, 100), 8)
        self.assertEqual(
            d.independent_family_false_fail([r1] * 8), 1 - F(99, 100) ** 80
        )
        lo, hi = d.binomial_limits(10, F(1, 100), d.tail_level(8))
        rb = d.binomial_rejection(10, F(1, 100), lo, hi)
        self.assertLessEqual(d.independent_family_false_fail([rb] * 8), F(5, 100))

    def test_review_counterexample_thousand_cells_of_thirty(self) -> None:
        r1 = d.r1_false_fail(30, F(1, 1000), 1000)
        self.assertEqual(r1, 1 - F(999, 1000) ** 30)
        self.assertGreater(d.independent_family_false_fail([r1] * 1000), F(999, 1000))
        lo, hi = d.binomial_limits(30, F(1, 1000), K1000)
        self.assertEqual((lo, hi), (0, 2))
        rb = d.binomial_rejection(30, F(1, 1000), lo, hi)
        self.assertLessEqual(d.independent_family_false_fail([rb] * 1000), F(5, 100))

    def test_review_counterexample_twenty_cells_of_four_hundred(self) -> None:
        r1 = d.r1_false_fail(400, F(3, 10), 20)
        self.assertAlmostEqual(
            float(d.independent_family_false_fail([r1] * 20)), 0.051992655, places=8
        )
        lo, hi = d.binomial_limits(400, F(3, 10), d.tail_level(20))
        rb = d.binomial_rejection(400, F(3, 10), lo, hi)
        self.assertLessEqual(rb * 20, F(5, 100))  # Bonferroni sum
        self.assertLessEqual(d.independent_family_false_fail([rb] * 20), F(5, 100))

    def test_review_power_counterexample_and_exact_power(self) -> None:
        # r1 claimed 95% power for a 2.521-point bias at n=1000, t=2%, K=1000.
        alt = F(2, 100) + F(25210689, 10**9)
        z2 = d.r1_z2(1000)
        pmf = d.binomial_pmf(1000, alt)
        r1_power = sum(
            p for k, p in pmf.items() if not d.r1_score_pass(k, 1000, F(2, 100), z2)
        )
        self.assertAlmostEqual(float(r1_power), 0.8818, places=3)
        lo, hi = d.binomial_limits(1000, F(2, 100), K1000)
        self.assertLess(d.binomial_rejection(1000, alt, lo, hi), F(95, 100))
        step = F(1, 10000)
        bias = d.least_bias_for_power(1000, F(2, 100), K1000, F(95, 100), step)
        self.assertGreaterEqual(
            d.binomial_rejection(1000, F(2, 100) + bias, lo, hi), F(95, 100)
        )
        self.assertLess(
            d.binomial_rejection(1000, F(2, 100) + bias - step, lo, hi), F(95, 100)
        )

    def test_crossing_with_a_fixed_two_point_band(self) -> None:
        # Neither rule dominates: the trade-off is put to the owner.
        self.assertTrue(d.rule_b_pass(298, 2000, F(12, 100), K1000))
        self.assertFalse(d.absolute_pp_pass(F(298, 2000), F(12, 100), F(2)))
        self.assertFalse(d.rule_b_pass(280, 5000, F(4, 100), K1000))
        self.assertTrue(d.absolute_pp_pass(F(280, 5000), F(4, 100), F(2)))

    def test_and_with_two_points_raises_false_fail_of_small_cells(self) -> None:
        # Option (b) of the record: exact rule AND 2 points, n=400, t=30%.
        lo, hi = d.binomial_limits(400, F(3, 10), K1000)
        both_lo, both_hi = max(lo, 120 - 8), min(hi, 120 + 8)
        self.assertGreater(
            d.binomial_rejection(400, F(3, 10), both_lo, both_hi), F(1, 10)
        )
        self.assertLess(d.binomial_rejection(400, F(3, 10), lo, hi), 2 * K1000)

    def test_worked_limits_of_the_record(self) -> None:
        self.assertEqual(d.binomial_limits(5000, F(4, 100), K1000), (146, 258))
        self.assertEqual(d.binomial_limits(2000, F(12, 100), K1000), (183, 301))
        self.assertEqual(d.binomial_limits(50000, F(3, 10), K1000), (14585, 15417))
        self.assertEqual(d.binomial_limits(50000, F(7, 10), K1000), (34583, 35415))
        self.assertEqual(d.binomial_limits(20000, F(8, 100), K1000), (1447, 1758))


class CrossFamilyK(unittest.TestCase):
    """K is one frozen fit-wide count, computed without numerators."""

    PLANS: ClassVar[list[d.FamilyPlan]] = [
        d.FamilyPlan("iid_equal_weight", (2,) * 3),  # gender: 3 cells, 1 test each
        d.FamilyPlan("iid_equal_weight", (7,) * 2),  # age bands: 2 cells, 7 tests each
        d.FamilyPlan("weighted_independent", (2,)),  # accommodation: 1 test
        d.FamilyPlan("deterministic_allocation", (5,)),  # exact: no test spent
    ]

    def test_family_size_sums_tests_over_families(self) -> None:
        self.assertEqual(d.fit_family_size(self.PLANS), 3 + 14 + 1)

    def test_family_size_cannot_see_numerators(self) -> None:
        import inspect

        self.assertEqual(
            list(inspect.signature(d.fit_family_size).parameters), ["plans"]
        )
        self.assertNotIn("observed", d.FamilyPlan.__dataclass_fields__)

    def test_plant_per_family_k(self) -> None:
        # Eight families, one cell each, n=400, t=30%. Planted: each family its own K=1.
        fit_k = d.fit_family_size([d.FamilyPlan("iid_equal_weight", (2,))] * 8)
        self.assertEqual(fit_k, 8)
        lo8, hi8 = d.binomial_limits(400, F(3, 10), d.tail_level(fit_k))
        lo1, hi1 = d.binomial_limits(400, F(3, 10), d.tail_level(1))
        self.assertGreater(hi8, hi1)
        self.assertTrue(d.rule_b_pass(hi8, 400, F(3, 10), d.tail_level(fit_k)))
        self.assertFalse(d.rule_b_pass(hi8, 400, F(3, 10), d.tail_level(1)))
        right = d.binomial_rejection(400, F(3, 10), lo8, hi8)
        wrong = d.binomial_rejection(400, F(3, 10), lo1, hi1)
        self.assertLessEqual(d.independent_family_false_fail([right] * 8), F(5, 100))
        self.assertGreater(d.independent_family_false_fail([wrong] * 8), F(5, 100))


# ===================================================== declarations (R2)


class Declarations(unittest.TestCase):
    """MISSING_METHOD and MISSING_DECLARATIONS branches: never a default pass."""

    def test_no_mechanism_is_a_missing_method_gap(self) -> None:
        decl = d.Declaration(**{**DECL_IID.__dict__, "mechanism": None})
        self.assertEqual(
            d.evaluate_family(decl, [iid_cell(10, 3, F(3, 10))], K1000),
            d.MISSING_METHOD,
        )
        self.assertEqual(
            d.evaluate_family(None, [iid_cell(10, 3, F(3, 10))], K1000),
            d.MISSING_METHOD,
        )

    def test_unknown_mechanism_is_a_missing_method_gap(self) -> None:
        decl = d.Declaration(
            **{**DECL_IID.__dict__, "mechanism": "normal_approximation"}
        )
        self.assertEqual(
            d.evaluate_family(decl, [iid_cell(10, 3, F(3, 10))], K1000),
            d.MISSING_METHOD,
        )

    def test_each_missing_field_is_a_declarations_gap(self) -> None:
        for name in d.REQUIRED:
            decl = d.Declaration(**{**DECL_IID.__dict__, name: None})
            self.assertEqual(
                d.evaluate_family(decl, [iid_cell(10, 3, F(3, 10))], K1000),
                d.MISSING_DECLARATIONS,
                name,
            )

    def test_allocation_without_declared_rounding_is_a_gap(self) -> None:
        decl = d.Declaration(**{**DECL_A.__dict__, "rounding": None})
        self.assertEqual(
            d.evaluate_cell(decl, d.Cell(n=1000, target=F(8, 100), observed=80), K1000),
            d.MISSING_DECLARATIONS,
        )

    def test_deterministic_allocation_is_exact(self) -> None:
        cell = d.Cell(n=1001, target=F(1, 2), observed=500)  # 500.5 -> 500 (half even)
        self.assertEqual(d.evaluate_cell(DECL_A, cell, K1000), d.PASS)
        cell = d.Cell(n=1001, target=F(1, 2), observed=501)
        self.assertEqual(d.evaluate_cell(DECL_A, cell, K1000), d.EXACT_MISMATCH)


class RepeatedTrips(unittest.TestCase):
    """Person-trip flow shares: weights are trips per person (Rule W)."""

    # Person 1 (category A) makes 3 trips, person 2 (category B) makes 1 trip.
    CELL = d.Cell(units=((3, F(1, 2), True), (1, F(1, 2), False)))

    def test_trip_share_is_not_the_person_share(self) -> None:
        trips_a = sum(w for w, _, inside in self.CELL.units if inside)
        trips = sum(w for w, _, _ in self.CELL.units)
        self.assertEqual(F(trips_a, trips), F(3, 4))
        self.assertEqual(
            F(1, 2), F(sum(1 for *_, i in self.CELL.units if i), len(self.CELL.units))
        )

    def test_exact_law_of_trip_counts(self) -> None:
        pmf = d.weighted_bernoulli_pmf([(3, F(1, 2)), (1, F(1, 2))])
        self.assertEqual(pmf, {0: F(1, 4), 1: F(1, 4), 3: F(1, 4), 4: F(1, 4)})
        self.assertFalse(d.pmf_tail_pass(pmf, 2, d.tail_level(1)))  # impossible count

    def test_plant_binomial_on_unequal_trip_weights_is_refused(self) -> None:
        self.assertEqual(d.evaluate_cell(DECL_IID, self.CELL, K1000), d.MISSING_METHOD)
        self.assertEqual(d.evaluate_cell(DECL_W, self.CELL, K1000), d.PASS)


class UnequalClusters(unittest.TestCase):
    """Worker-weighted accommodation share under a cluster draw (Rule W)."""

    def test_cluster_count_is_not_the_worker_share(self) -> None:
        # Two employer clusters of 1 and 99 workers; only the small one is housed.
        units = ((1, F(1, 2), True), (99, F(1, 2), False))
        cluster_share = F(sum(1 for *_, i in units if i), len(units))
        worker_share = F(sum(w for w, _, i in units if i), sum(w for w, _, _ in units))
        self.assertEqual(cluster_share, F(1, 2))
        self.assertEqual(worker_share, F(1, 100))
        pmf = d.weighted_bernoulli_pmf([(w, p) for w, p, _ in units])
        self.assertEqual(sorted(pmf), [0, 1, 99, 100])  # worker-weighted law

    def test_plant_worker_binomial_fails_a_correct_cluster_world(self) -> None:
        # Correct world: the 99-worker cluster housed (probability 1/4 under the mechanism).
        cell = d.Cell(units=((1, F(1, 2), False), (99, F(1, 2), True)))
        self.assertEqual(d.evaluate_cell(DECL_W, cell, d.tail_level(1)), d.PASS)
        self.assertFalse(d.rule_b_pass(99, 100, F(1, 2), d.tail_level(1)))  # wrong law

    SIZES = tuple(range(1, 41))  # 40 invented clusters, 820 workers

    def _cell(self, housed: set[int], p: F) -> d.Cell:
        return d.Cell(units=tuple((s, p, s in housed) for s in self.SIZES))

    def test_rule_w_catches_one_share_for_all_groups(self) -> None:
        # Target 65% of workers; planted generator uses 30% (one share for all).
        planted = set(range(1, 22))  # the 21 smallest clusters: 231 of 820 workers
        self.assertEqual(sum(planted), 231)
        self.assertLess(abs(F(sum(planted), 820) - F(3, 10)), F(2, 100))
        self.assertEqual(
            d.evaluate_cell(DECL_W, self._cell(planted, F(65, 100)), K1000), d.OUT
        )
        control = {13, *range(25, 41)}  # 533 of 820 workers = 65%
        self.assertEqual(F(sum(control), 820), F(65, 100))
        self.assertEqual(
            d.evaluate_cell(DECL_W, self._cell(control, F(65, 100)), K1000), d.PASS
        )


class FinitePopulation(unittest.TestCase):
    """A fixed national count spread over cells without replacement (Rule H)."""

    def test_hypergeometric_variance_is_smaller(self) -> None:
        pmf = d.hypergeometric_pmf(100, 30, 50)
        mean = sum(k * p for k, p in pmf.items())
        var = sum((k - mean) ** 2 * p for k, p in pmf.items())
        self.assertEqual(mean, 15)
        self.assertEqual(var, F(50 * 30 * 70 * 50, 100 * 100 * 99))  # 5.30 < 10.5
        self.assertLess(var, F(105, 10))

    def test_plant_binomial_passes_a_count_the_exact_law_rejects(self) -> None:
        c = d.tail_level(1)
        pmf = d.hypergeometric_pmf(100, 30, 50)
        lo, hi = d.binomial_limits(50, F(3, 10), c)
        wrong = [k for k in range(lo, hi + 1) if not d.pmf_tail_pass(pmf, k, c)]
        self.assertTrue(wrong)
        cell = d.Cell(population=100, marked=30, drawn=50, observed=wrong[-1])
        self.assertEqual(d.evaluate_cell(DECL_H, cell, c), d.OUT)
        self.assertEqual(
            d.evaluate_cell(
                DECL_H, d.Cell(population=100, marked=30, drawn=50, observed=15), c
            ),
            d.PASS,
        )


# ================================================= per-value plants (R6)


class PlantSize(unittest.TestCase):
    PUBLIC: ClassVar[list[F]] = [
        F(v) for v in (1200, 800, 600, 400, 400, 300, 300)
    ]  # 4,000 employees

    def test_plant_three_point_shift_fails(self) -> None:
        world = [F(1080), *self.PUBLIC[1:6], F(420)]
        self.assertEqual(d.size_check(self.PUBLIC, world, 4000, 4000), d.OUT)

    def test_control_two_points_passes_at_the_boundary(self) -> None:
        world = [F(1120), *self.PUBLIC[1:6], F(380)]
        self.assertEqual(d.size_check(self.PUBLIC, world, 4000, 4000), d.PASS)

    def test_small_cell_is_a_gap_and_rebanding_is_refused(self) -> None:
        self.assertEqual(
            d.size_check(self.PUBLIC, self.PUBLIC, 999, 4000), d.UNSUPPORTED_COVERAGE
        )
        four = [F(2000), F(1000), F(600), F(400)]
        self.assertEqual(
            d.size_check(self.PUBLIC, four, 4000, 4000), "FIT_PUBLIC_SIZE_REBANDING"
        )


class PlantNationality(unittest.TestCase):
    def test_plant_national_share_for_every_activity(self) -> None:
        self.assertEqual(
            d.evaluate_cell(DECL_IID, iid_cell(5000, 300, F(4, 100)), K1000), d.OUT
        )

    def test_control_and_boundaries(self) -> None:
        for k, outcome in (
            (200, d.PASS),
            (146, d.PASS),
            (258, d.PASS),
            (145, d.OUT),
            (259, d.OUT),
        ):
            self.assertEqual(
                d.evaluate_cell(DECL_IID, iid_cell(5000, k, F(4, 100)), K1000),
                outcome,
                k,
            )


class PlantEmploymentGender(unittest.TestCase):
    def test_plant_uniform_gender_draw(self) -> None:
        cells = [iid_cell(2000, 1000, F(12, 100))]
        self.assertEqual(d.employment_gender_check(True, DECL_IID, cells, K1000), d.OUT)

    def test_control_and_boundaries(self) -> None:
        for k, outcome in (
            (240, d.PASS),
            (183, d.PASS),
            (301, d.PASS),
            (182, d.OUT),
            (302, d.OUT),
        ):
            cells = [iid_cell(2000, k, F(12, 100))]
            self.assertEqual(
                d.employment_gender_check(True, DECL_IID, cells, K1000), outcome, k
            )

    def test_without_the_table_it_is_not_drawn_never_a_pass(self) -> None:
        cells = [iid_cell(2000, 240, F(12, 100))]
        self.assertEqual(
            d.employment_gender_check(False, DECL_IID, cells, K1000), d.NOT_DRAWN
        )


class PlantSpread(unittest.TestCase):
    """R3 and R4: exact construction prediction plus the rounding bound only."""

    SERIES = (
        (F(10, 100), F(1000)),
        (F(25, 100), F(1500)),
        (F(50, 100), F(2500)),
        (F(75, 100), F(4000)),
        (F(90, 100), F(7000)),
    )
    Q = F(1)

    def test_prediction_equals_type7_of_the_construction(self) -> None:
        for n in range(1, 160):
            values = d.construct(self.SERIES, n)
            for p, _ in self.SERIES:
                self.assertEqual(
                    d.predicted_hf7(self.SERIES, n, p), d.hf7(values, p), (n, p)
                )

    def test_grid_aligned_knots_have_zero_discrepancy(self) -> None:
        for n in (21, 41, 101):
            for p, _ in self.SERIES:
                self.assertEqual(d.interpolation_discrepancy(self.SERIES, n, p), 0)

    def test_every_rounded_construction_passes_with_zero_allowance(self) -> None:
        for n in range(1, 160):
            values = [d.round_half_even(v, self.Q) for v in d.construct(self.SERIES, n)]
            self.assertEqual(d.spread_check(values, self.SERIES, self.Q), d.PASS, n)

    def test_n21_internal_group_is_tested_and_passes(self) -> None:
        values = d.construct(self.SERIES, 21)
        for p, q in self.SERIES:
            self.assertEqual(d.hf7(values, p), q)
        self.assertEqual(d.spread_check(values, self.SERIES, self.Q), d.PASS)

    def test_singleton_and_pair_are_definable(self) -> None:
        self.assertEqual(d.spread_check([F(2500)], self.SERIES, self.Q), d.PASS)
        self.assertEqual(d.spread_check([F(2600)], self.SERIES, self.Q), d.OUT)
        self.assertEqual(
            d.spread_check([F(1000), F(7000)], self.SERIES, self.Q), d.PASS
        )
        self.assertEqual(d.spread_check([], self.SERIES, self.Q), d.UNDEFINED)

    def test_plant_p90_7050_fails_under_zero_allowance(self) -> None:
        values = d.construct(self.SERIES, 101)
        raised = [v + 50 if i >= 90 else v for i, v in enumerate(sorted(values))]
        self.assertEqual(d.hf7(raised, F(1, 2)), F(2500))
        self.assertEqual(d.hf7(raised, F(9, 10)), F(7050))
        self.assertEqual(d.spread_check(raised, self.SERIES, self.Q), d.OUT)
        self.assertTrue(
            d.r1_spread_pass(raised, self.SERIES, self.Q)
        )  # r1's hidden slack
        self.assertEqual(d.r1_extra_slack(self.SERIES, 101, F(9, 10)), 50)

    def test_extra_allowance_is_explicit_and_quantified(self) -> None:
        values = d.construct(self.SERIES, 101)
        raised = [v + 50 if i >= 90 else v for i, v in enumerate(sorted(values))]
        self.assertEqual(
            d.spread_check(raised, self.SERIES, self.Q, extra=F(99, 2)), d.PASS
        )
        self.assertEqual(
            d.spread_check(raised, self.SERIES, self.Q, extra=F(98, 2)), d.OUT
        )

    def test_plant_tails_squeezed_median_exact(self) -> None:
        values = d.construct(self.SERIES, 101)
        mid = values[50]
        squeezed = [mid + (v - mid) * F(9, 10) for v in values]
        self.assertEqual(d.hf7(squeezed, F(1, 2)), F(2500))
        self.assertEqual(d.spread_check(squeezed, self.SERIES, self.Q), d.OUT)

    def test_plant_scale_then_median_repair(self) -> None:
        values = d.construct(self.SERIES, 101)
        scaled = [v * F(11, 10) for v in values]
        shift = F(2500) - d.hf7(scaled, F(1, 2))
        self.assertEqual(
            d.spread_check([v + shift for v in scaled], self.SERIES, self.Q), d.OUT
        )

    def test_type6_is_not_construction_consistent(self) -> None:
        values = d.construct(self.SERIES, 21)
        self.assertNotEqual(d.hf6(values, F(25, 100)), F(1500))


class PlantMeans(unittest.TestCase):
    def test_plant_mean_lifted_twelve_percent(self) -> None:
        self.assertEqual(d.mean_check(F(5000), F(5600), "monthly", "monthly"), d.OUT)

    def test_control_and_boundary(self) -> None:
        self.assertEqual(d.mean_check(F(5000), F(5500), "monthly", "monthly"), d.PASS)
        self.assertEqual(d.mean_check(F(5000), F(4500), "monthly", "monthly"), d.PASS)
        self.assertEqual(d.mean_check(F(5000), F(5501), "monthly", "monthly"), d.OUT)

    def test_annual_is_never_monthly(self) -> None:
        self.assertEqual(
            d.mean_check(F(60000), F(5000), "annual", "monthly"), d.ANNUAL_AS_MONTHLY
        )


class PlantF15(unittest.TestCase):
    TARGET = F(3, 10)

    def test_plant_shortcut_passes_a_world_the_estimator_fails(self) -> None:
        wages = [F(v) for v in (9000, 1500, 9000, 9000, 1000, 1000, 3000, 1200)]
        prices = [F(v) for v in (20, 30, 10, 20, 10, 10, 20, 30)]
        self.assertAlmostEqual(
            d.spearman(wages, prices), 0.1429, places=4
        )  # not exactly 1/7
        self.assertEqual(d.spearman_shortcut(wages, prices), F(3, 14))
        self.assertEqual(d.f15_check(wages, prices, self.TARGET), d.OUT)
        self.assertEqual(d.f15_check_shortcut(wages, prices, self.TARGET), d.PASS)

    def test_control_estimator_passes_a_world_the_shortcut_fails(self) -> None:
        wages = [F(v) for v in (3000, 3000, 3000, 9000, 1500, 1200, 3000, 3000)]
        prices = [F(v) for v in (30, 20, 30, 10, 10, 10, 30, 20)]
        self.assertEqual(d.f15_check(wages, prices, self.TARGET), d.PASS)
        self.assertEqual(d.f15_check_shortcut(wages, prices, self.TARGET), d.OUT)

    def test_ties_are_average_ranks_and_constant_is_undefined(self) -> None:
        self.assertEqual(
            d.average_ranks([F(5), F(1), F(5), F(3)]), [F(7, 2), F(1), F(7, 2), F(2)]
        )
        self.assertEqual(
            d.f15_check([F(1)] * 3, [F(1), F(2), F(3)], self.TARGET), d.UNDEFINED
        )


class PlantF19(unittest.TestCase):
    """One fixture per statement (N3); sensitivity to one row (N2)."""

    CLEAN: ClassVar[list[list[F]]] = [
        [F(10), F(10), F(10), F(5), F(5), F(10)],
        [F(11), F(9), F(10), F(5), F(5), F(10)],
        [F(10), F(10), F(9), F(6), F(5), F(10)],
        [F(10), F(10), F(10), F(5), F(6), F(9)],
    ]
    CLOSURE: ClassVar[list[F]] = [F(1), F(1), F(1), F(1), F(1), F(1)]

    def test_fixture_a_four_clean_years(self) -> None:
        rows = [d.shares(r) for r in self.CLEAN]
        anchor = d.mean_rows(rows)
        self.assertEqual(d.loo_median_gap(rows), F(1, 50))
        self.assertEqual(d.max_gap([F(1, 6)] * 6, anchor), F(37, 600))

    def test_fixture_b_with_a_closure_year(self) -> None:
        rows = [d.shares(r) for r in [*self.CLEAN, self.CLOSURE]]
        anchor = d.mean_rows(rows)
        self.assertEqual(d.loo_median_gap(rows), F(13, 600))
        self.assertEqual(d.max_gap([F(1, 6)] * 6, anchor), F(37, 750))

    def test_plant_flat_month_shape_fails_and_control_passes(self) -> None:
        rows = [d.shares(r) for r in self.CLEAN]
        self.assertEqual(d.shape_check([F(1, 6)] * 6, rows), d.OUT)
        self.assertEqual(d.shape_check(d.shares(self.CLEAN[0]), rows), d.PASS)

    def test_sensitivity_one_row_moves_tau_from_zero_to_a_quarter(self) -> None:
        same = [F(1), F(0), F(0)]
        self.assertEqual(d.loo_median_gap([same] * 4), 0)
        rows = [same] * 4 + [[F(0), F(1), F(0)]]
        self.assertEqual(d.loo_median_gap(rows), F(1, 4))
        self.assertEqual(
            d.max_gap([F(1, 3)] * 3, d.mean_rows(rows)), F(7, 15)
        )  # guard admits

    def test_flat_anchor_and_too_few_rows_are_gaps(self) -> None:
        flat_rows = [[F(1, 3)] * 3] * 3
        self.assertEqual(
            d.shape_check([F(1, 3)] * 3, flat_rows), d.UNSUPPORTED_COVERAGE
        )
        self.assertEqual(
            d.shape_check([F(1, 3)] * 3, flat_rows[:2]), d.UNSUPPORTED_COVERAGE
        )


class PlantF21(unittest.TestCase):
    VENUES: ClassVar[list[list[F]]] = [
        [F(20), F(40), F(40)],
        [F(10), F(10), F(30)],
        [F(2), F(3), F(5)],
    ]

    def test_c26_fixture(self) -> None:
        rows = [d.shares(r) for r in self.VENUES]
        self.assertEqual(d.mean_rows(rows), [F(1, 5), F(3, 10), F(1, 2)])
        self.assertEqual(d.loo_gaps(rows), [F(3, 20), F(3, 20), F(0)])
        self.assertEqual(d.loo_median_gap(rows), F(3, 20))  # 15 points

    def test_plant_flat_hourly_shape_fails_and_control_passes(self) -> None:
        rows = [d.shares(r) for r in self.VENUES]
        self.assertEqual(d.shape_check([F(1, 3)] * 3, rows), d.OUT)  # gap 1/6 > 3/20
        self.assertEqual(
            d.shape_check([F(1, 4), F(1, 4), F(1, 2)], rows), d.PASS
        )  # gap 1/20

    def test_below_three_venues_has_no_anchor(self) -> None:
        rows = [d.shares(r) for r in self.VENUES[:2]]
        self.assertEqual(
            d.shape_check([F(1, 5), F(3, 10), F(1, 2)], rows), d.UNSUPPORTED_COVERAGE
        )


class PlantMovement(unittest.TestCase):
    """Age, gender (presence: Rule B on persons; flows: Rule W on trips)."""

    def test_plant_age_band_shift_one_point(self) -> None:
        self.assertEqual(
            d.evaluate_cell(DECL_IID, iid_cell(50000, 15500, F(3, 10)), K1000), d.OUT
        )
        self.assertEqual(
            d.evaluate_cell(DECL_IID, iid_cell(50000, 15417, F(3, 10)), K1000), d.PASS
        )
        self.assertEqual(
            d.evaluate_cell(DECL_IID, iid_cell(50000, 15418, F(3, 10)), K1000), d.OUT
        )

    def test_plant_movement_gender_uniform(self) -> None:
        self.assertEqual(
            d.evaluate_cell(DECL_IID, iid_cell(50000, 25000, F(7, 10)), K1000), d.OUT
        )
        self.assertEqual(
            d.evaluate_cell(DECL_IID, iid_cell(50000, 35000, F(7, 10)), K1000), d.PASS
        )

    def test_plant_flow_split_tested_on_distinct_persons(self) -> None:
        # Flow cell: 30 persons, person i makes (i % 3) + 1 trips, category drawn at 1/2.
        units = tuple(((i % 3) + 1, F(1, 2), i < 15) for i in range(30))
        cell = d.Cell(units=units)
        self.assertEqual(d.evaluate_cell(DECL_IID, cell, K1000), d.MISSING_METHOD)
        self.assertEqual(d.evaluate_cell(DECL_W, cell, K1000), d.PASS)

    def test_plant_nationality_split_redrawn(self) -> None:
        people = ["A"] * 140 + ["B"] * 860
        self.assertEqual(d.aggregation_check(people, {"A": 140, "B": 860}), d.PASS)
        self.assertEqual(
            d.aggregation_check(people, {"A": 141, "B": 859}), d.EXACT_MISMATCH
        )

    def test_international_visitors_without_declaration_is_a_gap(self) -> None:
        self.assertEqual(
            d.evaluate_family(None, [iid_cell(100, 10, F(1, 10))], K1000),
            d.MISSING_METHOD,
        )


class PlantFlows(unittest.TestCase):
    """Joiners and leavers: n = previous month's covered stock."""

    def test_plant_joiners_on_current_stock(self) -> None:
        self.assertEqual(d.binomial_limits(1000000, F(15, 1000), K1000), (14510, 15495))
        self.assertFalse(
            d.rule_b_pass(15750, 1000000, F(15, 1000), K1000)
        )  # stock grown 5%
        self.assertTrue(d.rule_b_pass(15000, 1000000, F(15, 1000), K1000))
        self.assertTrue(d.rule_b_pass(15495, 1000000, F(15, 1000), K1000))
        self.assertFalse(d.rule_b_pass(15496, 1000000, F(15, 1000), K1000))

    def test_plant_leavers_exclude_closures(self) -> None:
        self.assertFalse(d.rule_b_pass(14000, 1000000, F(15, 1000), K1000))
        self.assertTrue(d.rule_b_pass(14510, 1000000, F(15, 1000), K1000))
        self.assertFalse(d.rule_b_pass(14509, 1000000, F(15, 1000), K1000))

    def test_the_same_denominator_error_is_not_caught_in_a_small_stock(self) -> None:
        # Stated limitation: at a stock of 100,000 the 5% error (1,575 vs 1,500) passes.
        self.assertTrue(d.rule_b_pass(1575, 100000, F(15, 1000), K1000))


class PlantResidence(unittest.TestCase):
    def test_plant_accommodation_one_share_for_all_groups(self) -> None:
        self.assertEqual(d.binomial_limits(200000, F(65, 100), K1000), (129134, 130864))
        self.assertFalse(
            d.rule_b_pass(60000, 200000, F(65, 100), K1000)
        )  # 30% for all groups
        self.assertTrue(d.rule_b_pass(130000, 200000, F(65, 100), K1000))

    def test_plant_staleness_over_all_residents(self) -> None:
        # 8% drawn over 200,000 residents, counted against 20,000 movers.
        self.assertFalse(d.rule_b_pass(16000, 20000, F(8, 100), K1000))
        self.assertTrue(d.rule_b_pass(1600, 20000, F(8, 100), K1000))


class PlantX1(unittest.TestCase):
    """R5: tie-aware exact null; the minimum stays open."""

    def test_twelve_zone_tied_fixture(self) -> None:
        tied = [F(1)] * 11 + [F(2)]
        self.assertEqual(d.exact_null_upper_tail(tied, tied, F(6, 10)), F(1, 12))
        self.assertAlmostEqual(
            d.r1_null_pass_probability(F(6, 10), 12), 0.0233, places=4
        )

    def test_one_high_family_needs_twenty_zones_for_five_percent(self) -> None:
        for n in (12, 19, 20, 30):
            one = [F(1)] * (n - 1) + [F(2)]
            self.assertEqual(d.exact_null_upper_tail(one, one, F(6, 10)), F(1, n))
        self.assertGreater(F(1, 19), F(5, 100))

    def test_exact_null_equals_brute_force(self) -> None:
        cases = [
            ([3, 1, 4, 1, 5, 9, 2], [2, 7, 1, 8, 2, 8, 1]),
            ([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]),
            ([1, 1, 2, 2, 3, 3], [1, 2, 2, 3, 3, 3]),
        ]
        for x, y in cases:
            fx, fy = [F(v) for v in x], [F(v) for v in y]
            for r in (F(-1, 2), F(0), F(3, 10), F(6, 10)):
                self.assertEqual(
                    d.exact_null_upper_tail(fx, fy, r),
                    d.brute_null_upper_tail(fx, fy, r),
                )

    def test_threshold_is_inclusive_and_exact(self) -> None:
        x = [F(v) for v in (1, 2, 3, 4, 5)]
        y = [F(v) for v in (2, 1, 4, 5, 3)]  # sum d^2 = 8, rho = 3/5 exactly
        self.assertEqual(d.spearman_cmp(x, y, F(6, 10)), 0)
        self.assertEqual(d.x1_check(x, y, minimum=5), d.PASS)
        self.assertEqual(
            d.x1_check(x, y, threshold=F(6, 10) + F(1, 10**9), minimum=5), d.OUT
        )

    def test_plant_x1_passing_while_its_minimum_is_open(self) -> None:
        zones = [F(v) for v in range(11)]
        self.assertEqual(
            d.x1_check(zones, zones), d.MISSING_TOLERANCE
        )  # rho = 1, still a gap
        self.assertEqual(d.x1_check(zones[:2], zones[:2]), d.MISSING_TOLERANCE)


def _x1_null_fixtures() -> list[tuple[str, list[F], list[F]]]:
    """Every tied and untied X1 fixture of this file, plus small untied and
    two-level tie patterns. All invented."""
    out: list[tuple[str, list[F], list[F]]] = []
    tied = [F(1)] * 11 + [F(2)]
    out.append(("twelve-zone tied", tied, tied))
    for n in (12, 19, 20, 30, 54):
        one = [F(1)] * (n - 1) + [F(2)]
        out.append((f"one-high n={n}", one, one))
    for x, y in (
        ([3, 1, 4, 1, 5, 9, 2], [2, 7, 1, 8, 2, 8, 1]),
        ([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]),
        ([1, 1, 2, 2, 3, 3], [1, 2, 2, 3, 3, 3]),
        ([1, 2, 3, 4, 5], [2, 1, 4, 5, 3]),
    ):
        out.append((f"existing {x}", [F(v) for v in x], [F(v) for v in y]))
    for n in range(3, 10):
        u = [F(v) for v in range(n)]
        out.append((f"untied n={n}", u, u))
    half = [F(1)] * 5 + [F(2)] * 5
    out.append(("half-half n=10", half, half))
    out.append(
        (
            "mixed ties n=10",
            [F(v) for v in (1, 1, 1, 2, 2, 3, 4, 4, 5, 6)],
            [F(v) for v in (1, 2, 2, 2, 3, 3, 4, 5, 5, 5)],
        )
    )
    return out


R_GRID = [F(k, 10) for k in range(1, 11)]


class X1CantelliBound(unittest.TestCase):
    """r3 (REVIEW-0062-R2 note S1): a conservative fixed minimum for X1.

    For fixed nonconstant centred rank vectors under the exact permutation
    null, E[rho] = 0 and Var(rho) = 1/(n-1) whatever the ties; the one-sided
    Cantelli inequality gives P(rho >= r) <= 1/(1 + (n-1) r^2) for r > 0.
    A candidate for the owner only; X1 stays MISSING_TOLERANCE.
    """

    def test_null_moments_hold_under_ties_by_brute_force(self) -> None:
        fixtures = [
            ([1, 1, 2, 2, 3, 3], [1, 2, 2, 3, 3, 3]),
            ([3, 1, 4, 1, 5, 9, 2], [2, 7, 1, 8, 2, 8, 1]),
            ([1, 1, 1, 1, 1, 1, 2], [1, 1, 1, 1, 1, 1, 2]),
            ([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]),
            ([1, 1, 1, 2, 2, 2, 2, 3], [5, 4, 4, 3, 3, 3, 1, 1]),
        ]
        for x, y in fixtures:
            fx, fy = [F(v) for v in x], [F(v) for v in y]
            mean_sxy, mean_rho_sq = d.brute_null_rho_moments(fx, fy)
            self.assertEqual(mean_sxy, 0)  # E[rho] = 0
            self.assertEqual(mean_rho_sq, F(1, len(x) - 1))  # Var(rho) = 1/(n-1)

    def test_bound_formula(self) -> None:
        self.assertEqual(d.cantelli_null_bound(54, F(3, 5)), F(25, 502))
        self.assertEqual(d.cantelli_null_bound(53, F(3, 5)), F(25, 493))
        self.assertEqual(d.cantelli_null_bound(2, F(1)), F(1, 2))
        self.assertEqual(d.cantelli_bound_from_variance(F(1, 53), F(3, 5)), F(25, 502))

    def test_bound_refuses_undefined_inputs(self) -> None:
        for n, r in (
            (1, F(3, 5)),
            (0, F(3, 5)),
            (10, F(0)),
            (10, F(-1, 2)),
            (10, F(11, 10)),
        ):
            with self.assertRaises(d.Undefined):
                d.cantelli_null_bound(n, r)

    def test_first_n_at_three_fifths_and_five_percent_is_54(self) -> None:
        alpha, r = F(1, 20), F(3, 5)
        self.assertEqual(d.cantelli_first_n(r, alpha), 54)
        self.assertLessEqual(d.cantelli_null_bound(54, r), alpha)
        self.assertGreater(d.cantelli_null_bound(53, r), alpha)
        self.assertEqual(F(25, 493) - alpha, F(7, 9860))  # 53 misses by 7/9860
        # The bound decreases in n, so every n >= 54 holds as well.
        prev = d.cantelli_null_bound(2, r)
        for n in range(3, 400):
            cur = d.cantelli_null_bound(n, r)
            self.assertLess(cur, prev)
            prev = cur

    def test_first_n_closed_form_equals_direct_search(self) -> None:
        for r in (F(1, 2), F(3, 5), F(7, 10), F(4, 5), F(1)):
            for alpha in (F(1, 20), F(1, 100), F(1, 10)):
                n = 2
                while d.cantelli_null_bound(n, r) > alpha:
                    n += 1
                self.assertEqual(d.cantelli_first_n(r, alpha), n)

    def test_bound_is_never_below_the_exact_null_tail_on_the_fixtures(self) -> None:
        for name, x, y in _x1_null_fixtures():
            n = len(x)
            for r in R_GRID:
                exact = d.exact_null_upper_tail(x, y, r)
                bound = d.cantelli_null_bound(n, r)
                self.assertGreaterEqual(bound, exact, f"{name} r={r}")

    def test_the_bound_is_conservative_where_an_exact_minimum_is_smaller(self) -> None:
        # The one-high family needs only 20 zones exactly, against 54 by the bound.
        for n in (20, 30, 53):
            one = [F(1)] * (n - 1) + [F(2)]
            self.assertLessEqual(d.exact_null_upper_tail(one, one, F(3, 5)), F(1, 20))
        # Cantelli is attained by the one-high family at r = 1: exact 1/n.
        for n in (12, 20):
            one = [F(1)] * (n - 1) + [F(2)]
            self.assertEqual(
                d.exact_null_upper_tail(one, one, F(1)), d.cantelli_null_bound(n, F(1))
            )

    def test_plant_wrong_variance_one_over_n_fails(self) -> None:
        """Planted wrong variance 1/n (population form) in place of 1/(n-1)."""

        def plant(n: int, r: F) -> F:
            return d.cantelli_bound_from_variance(F(1, n), r)

        # 1. It disagrees with the exact null second moment on a tied fixture.
        tied = [F(v) for v in (1, 1, 2, 2, 3, 3)]
        _, mean_rho_sq = d.brute_null_rho_moments(tied, tied)
        self.assertNotEqual(F(1, 6), mean_rho_sq)
        # 2. It falls below an exact null tail: the safety test fails for it.
        below = [
            (name, r)
            for name, x, y in _x1_null_fixtures()
            for r in R_GRID
            if plant(len(x), r) < d.exact_null_upper_tail(x, y, r)
        ]
        self.assertTrue(below)
        one = [F(1)] * 11 + [F(2)]
        self.assertLess(
            plant(12, F(1)), d.exact_null_upper_tail(one, one, F(1))
        )  # 1/13 < 1/12
        # 3. It would wrongly lower the candidate minimum to 53.
        n = 2
        while plant(n, F(3, 5)) > F(1, 20):
            n += 1
        self.assertEqual(n, 53)
        self.assertNotEqual(n, d.cantelli_first_n(F(3, 5), F(1, 20)))

    def test_size_dependent_threshold_option(self) -> None:
        """Option C of open point 9: rho^2 >= (1 - alpha) / (alpha (n - 1))."""
        alpha = F(1, 20)
        self.assertEqual(d.cantelli_threshold_sq(35, alpha), F(19, 34))
        # At that threshold the bound equals alpha exactly: 1 / (1 + 34 * 19/34) = 1/20.
        self.assertEqual(1 / (1 + 34 * d.cantelli_threshold_sq(35, alpha)), alpha)
        self.assertGreater(
            d.cantelli_threshold_sq(19, alpha), 1
        )  # unreachable below 20
        self.assertEqual(d.cantelli_threshold_sq(20, alpha), 1)
        self.assertLessEqual(
            d.cantelli_threshold_sq(54, alpha), F(9, 25)
        )  # 0.60 binds from 54

    def test_one_high_against_two_high_needs_forty_zones(self) -> None:
        """A universal fixed minimum must be at least 40: the pattern with one
        high zone on one side and two on the other gives exactly 2/n."""
        for n in (10, 20, 39, 40, 54):
            x = [F(1)] * (n - 1) + [F(2)]
            y = [F(1)] * (n - 2) + [F(2)] * 2
            self.assertEqual(d.exact_null_upper_tail(x, y, F(3, 5)), F(2, n))
        self.assertGreater(F(2, 39), F(1, 20))
        self.assertEqual(F(2, 40), F(1, 20))

    def test_worst_two_level_pattern(self) -> None:
        for n in (10, 39, 40, 54):
            p, pattern = d.worst_two_level_tail(n, F(3, 5))
            self.assertEqual((p, pattern), (F(2, n), (1, 2)))
        self.assertEqual(d.largest_n_two_level_over(F(3, 5), F(1, 20), 54), 39)

    def test_untied_ranks_need_nine_zones_exactly(self) -> None:
        tails = {}
        for n in (8, 9, 10, 11):
            u = [F(v) for v in range(n)]
            tails[n] = d.exact_null_upper_tail(u, u, F(3, 5))
        self.assertEqual(tails[8], F(1159, 20160))
        self.assertGreater(tails[8], F(1, 20))
        self.assertEqual(tails[9], F(2509, 51840))
        for n in (9, 10, 11):
            self.assertLessEqual(tails[n], F(1, 20))

    def test_x1_stays_a_gap_with_the_candidate(self) -> None:
        zones = [F(v) for v in range(60)]
        self.assertEqual(d.x1_check(zones, zones), d.MISSING_TOLERANCE)


class PlantOtherCorrelations(unittest.TestCase):
    def test_plant_construction_assumption_as_target(self) -> None:
        pair = {
            "pair": "basic and net ranks",
            "target_source": "construction_assumption",
        }
        self.assertEqual(d.additional_correlations([pair]), d.SPEC_MISSING)

    def test_no_pair_keeps_the_gap(self) -> None:
        self.assertEqual(d.additional_correlations([]), d.MISSING_DECLARATIONS)


class CommonPlants(unittest.TestCase):
    def test_plant_strict_boundary(self) -> None:
        lo, hi = d.binomial_limits(5000, F(4, 100), K1000)

        def strict(k: int) -> bool:  # the plant: '<' in place of '<='
            return lo < k < hi

        for k in (lo, hi):
            self.assertTrue(d.rule_b_pass(k, 5000, F(4, 100), K1000))
            self.assertFalse(strict(k))

    def test_plant_tolerance_from_output(self) -> None:
        self.assertEqual(
            d.tolerance_from_roster({"source": "output", "tolerance_ref": "x"}),
            d.SPEC_MISSING,
        )
        self.assertEqual(
            d.tolerance_from_roster({"source": "roster", "tolerance_ref": "x"}), d.PASS
        )

    def test_report_runs(self) -> None:
        lines: list[str] = []
        self.assertEqual(d.main(lines.append), 0)
        self.assertTrue(any("X1" in line for line in lines))
        self.assertTrue(
            any(
                "Cantelli" in line and "first n = 54" in line and "25/502" in line
                for line in lines
            )
        )


if __name__ == "__main__":
    unittest.main()
