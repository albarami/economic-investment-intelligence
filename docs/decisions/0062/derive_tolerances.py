"""Derivations behind draft decision record 0062, revision 3 (S4-T12 tolerances).

Revision 3 adds only X1 evidence: the Cantelli bound (cantelli_*,
brute_null_rho_moments) and the two-level tie-pattern search (worst_two_level_tail,
largest_n_two_level_over).

Standard library only. Every comparison is exact rational or integer
arithmetic; floats appear only in printed summaries. Every input this module
is ever given, in its tests or in ``main``, is invented. It reads no file.

This is evidence for a proposal. It is not the S4-T12 implementation, its
"plants" are derivation plants (they show that a proposed rule separates a
planted wrong world from a right one), not the production guards S4-T12 will
build, and nothing here is active before the owner's approval.

Contents
- Rule B: exact binomial two-sided tails, equal tail allocation, Bonferroni
  over one frozen fit-wide family of K tests (replaces r1's Rule D).
- Rule H: exact hypergeometric tails for a without-replacement draw.
- Rule W: exact tails of a weighted sum of independent Bernoulli units
  (repeated trips of one person, workers of one employer cluster).
- Rule A: exact comparison for a deterministic allocation.
- The declaration check that maps a conditional family to one of these, or to
  a MISSING_METHOD / MISSING_DECLARATIONS gap, never to a default pass.
- SPREAD: the exact type-7 prediction of the undisturbed construction plus the
  rounding bound only.
- Shapes (F19, F21), ranks (F15, X1, exact tie-aware permutation null).
- r1's withdrawn Rule D, kept only to reproduce the review's counterexamples.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cache
from statistics import NormalDist, median

ALPHA = Fraction(5, 100)  # doc 07 Interval paragraph: 95%, held fit-wide

PASS = "PASS"
OUT = "FIT_OUT_OF_TOLERANCE"
EXACT_MISMATCH = "FIT_EXACT_MISMATCH"
UNDEFINED = "FIT_UNDEFINED"
SPEC_MISSING = "FIT_SPEC_MISSING"
MISSING_METHOD = "MISSING_METHOD"
MISSING_DECLARATIONS = "MISSING_DECLARATIONS"
MISSING_TOLERANCE = "MISSING_TOLERANCE"
NOT_DRAWN = "NOT_DRAWN"
UNSUPPORTED_COVERAGE = "UNSUPPORTED_COVERAGE"
ANNUAL_AS_MONTHLY = "ANNUAL_AS_MONTHLY"
GAPS = frozenset(
    {
        MISSING_METHOD,
        MISSING_DECLARATIONS,
        MISSING_TOLERANCE,
        NOT_DRAWN,
        UNSUPPORTED_COVERAGE,
        ANNUAL_AS_MONTHLY,
    }
)


class Undefined(ValueError):
    """An undefined statistic: FIT_UNDEFINED, never a pass."""


# =============================================================== Rule B


def tail_level(tests: int, alpha: Fraction = ALPHA) -> Fraction:
    """Per-tail level c = alpha / (2K): equal two-sided allocation, Bonferroni.

    Bonferroni needs no independence between the K tests, so it holds for
    dependent movement cells and across check families alike.
    """
    if type(tests) is not int or tests < 1:
        raise ValueError("K must be a positive integer")
    return alpha / (2 * tests)


def _check_share(n: int, t: Fraction) -> None:
    if type(n) is not int or n < 1:
        raise Undefined("empty cell")
    if not isinstance(t, Fraction) or not 0 <= t <= 1:
        raise ValueError("target must be an exact share in [0, 1]")


@cache
def binomial_limits(n: int, t: Fraction, c: Fraction) -> tuple[int, int]:
    """Acceptance limits [lo, hi] of Rule B, exact integer arithmetic.

    lo is the smallest k with P(X <= k) >= c and hi the largest k with
    P(X >= k) >= c, for X ~ Bin(n, t). A count k passes iff lo <= k <= hi
    (equality at the level passes). Under the null each tail rejects with
    probability < c, so a cell rejects with probability < 2c = alpha / K.
    """
    _check_share(n, t)
    if t == 0:
        return 0, 0
    if t == 1:
        return n, n
    if t > Fraction(1, 2):  # count the other category: Bin(n, 1 - t)
        lo, hi = binomial_limits(n, 1 - t, c)
        return n - hi, n - lo
    a, b = t.numerator, t.denominator
    total = b**n  # P(.) * b^n are integers
    need = c.numerator * total  # P >= c  <=>  integer * c.den >= need
    cd = c.denominator
    stop = total * cd - need  # P(X >= i + 1) < c  <=>  cum * cd > stop
    term = (b - a) ** n  # C(n,0) a^0 (b-a)^n
    cum = 0
    lo = None
    i = 0
    while True:
        cum += term  # cum = b^n * P(X <= i)
        scaled = cum * cd
        if lo is None and scaled >= need:
            lo = i
        if scaled > stop:
            assert lo is not None
            return lo, i
        term = term * ((n - i) * a) // ((i + 1) * (b - a))
        i += 1


def binomial_cdf(n: int, t: Fraction, k: int) -> Fraction:
    """P(X <= k), X ~ Bin(n, t), exact."""
    _check_share(n, t)
    if k < 0:
        return Fraction(0)
    if k >= n:
        return Fraction(1)
    if t == 0:
        return Fraction(1)
    if t == 1:
        return Fraction(0)
    a, b = t.numerator, t.denominator
    term = (b - a) ** n
    cum = 0
    for i in range(k + 1):
        cum += term
        term = term * ((n - i) * a) // ((i + 1) * (b - a))
    return Fraction(cum, b**n)


def binomial_rejection(n: int, t_true: Fraction, lo: int, hi: int) -> Fraction:
    """P(X < lo) + P(X > hi) for X ~ Bin(n, t_true): exact rejection rate.

    Under the target it is the cell's exact false-fail probability; under an
    alternative it is the exact power at that alternative.
    """
    return binomial_cdf(n, t_true, lo - 1) + 1 - binomial_cdf(n, t_true, hi)


def rule_b_pass(k: int, n: int, t: Fraction, c: Fraction) -> bool:
    if not 0 <= k <= n:
        raise ValueError("count outside the cell")
    lo, hi = binomial_limits(n, t, c)
    return lo <= k <= hi


def least_bias_for_power(
    n: int, t: Fraction, c: Fraction, power: Fraction, step: Fraction, up: bool = True
) -> Fraction:
    """Smallest multiple of ``step`` whose exact power reaches ``power``."""
    lo, hi = binomial_limits(n, t, c)
    d = step
    while True:
        alt = t + d if up else t - d
        if not 0 <= alt <= 1:
            raise ValueError("no alternative inside [0, 1] reaches the power")
        if binomial_rejection(n, alt, lo, hi) >= power:
            return d
        d += step


# ------------------------------------------------- generic exact tails


def pmf_tail_pass(pmf: dict[int, Fraction], k: int, c: Fraction) -> bool:
    """Exact two-sided tail test on a finite distribution.

    k passes iff k is a possible value and both P(S <= k) and P(S >= k) reach
    c. A count the declared mechanism cannot produce fails.
    """
    if pmf.get(k, 0) == 0:
        return False
    lower = sum((p for v, p in pmf.items() if v <= k), Fraction(0))
    upper = sum((p for v, p in pmf.items() if v >= k), Fraction(0))
    return lower >= c and upper >= c


def pmf_rejection(pmf: dict[int, Fraction], c: Fraction) -> Fraction:
    """Exact null probability that ``pmf_tail_pass`` fails."""
    return sum((p for v, p in pmf.items() if not pmf_tail_pass(pmf, v, c)), Fraction(0))


# ============================================================ Rule H


def hypergeometric_pmf(population: int, marked: int, drawn: int) -> dict[int, Fraction]:
    """Marked units among ``drawn`` taken without replacement: exact law."""
    if not 0 <= marked <= population or not 0 <= drawn <= population:
        raise ValueError("impossible finite population")
    if drawn == 0:
        raise Undefined("empty cell")
    whole = math.comb(population, drawn)
    return {
        x: Fraction(
            math.comb(marked, x) * math.comb(population - marked, drawn - x), whole
        )
        for x in range(max(0, drawn - population + marked), min(marked, drawn) + 1)
    }


def binomial_pmf(n: int, t: Fraction) -> dict[int, Fraction]:
    """Exact Bin(n, t) law as a dict (small n only)."""
    _check_share(n, t)
    return {
        k: Fraction(math.comb(n, k)) * t**k * (1 - t) ** (n - k) for k in range(n + 1)
    }


# ============================================================ Rule W


def weighted_bernoulli_pmf(
    units: Sequence[tuple[int, Fraction]],
) -> dict[int, Fraction]:
    """Exact law of S = sum w_j B_j, B_j independent Bernoulli(p_j).

    A unit is a person whose w_j trips all carry the person's category, or an
    employer cluster whose w_j workers share one accommodation draw. S is the
    weighted (trip- or worker-weighted) count; its expectation divided by the
    total weight is the declared share only if sum w_j p_j = t * sum w_j.
    """
    if not units:
        raise Undefined("empty cell")
    dist: dict[int, Fraction] = {0: Fraction(1)}
    for w, p in units:
        if type(w) is not int or w < 1 or not 0 <= p <= 1:
            raise ValueError("unit weight must be a positive integer, p a share")
        nxt: dict[int, Fraction] = {}
        for s, q in dist.items():
            if p < 1:
                nxt[s] = nxt.get(s, Fraction(0)) + q * (1 - p)
            if p > 0:
                nxt[s + w] = nxt.get(s + w, Fraction(0)) + q * p
        dist = nxt
    return dist


# ======================================================= declarations

MECHANISMS = frozenset(
    {
        "iid_equal_weight",
        "weighted_independent",
        "without_replacement",
        "deterministic_allocation",
    }
)
REQUIRED = (
    "numerator",
    "denominator",
    "target_population",
    "unit",
    "weights",
    "conditional_independence",
    "eligibility",
)


@dataclass(frozen=True)
class Declaration:
    """What the producing task must declare for one conditional family.

    Every field is the producing task's declaration (plan r2 page 2,
    ``inputs.*``); this record fills none of them. ``mechanism`` None means no
    method is declared.
    """

    numerator: str | None = None
    denominator: str | None = None
    target_population: str | None = None
    unit: str | None = None
    weights: str | None = None
    conditional_independence: str | None = None
    eligibility: str | None = None
    mechanism: str | None = None
    rounding: str | None = None  # deterministic allocation only


@dataclass(frozen=True)
class Cell:
    """One cell's inputs to the derivation harness (never reported).

    units: (weight, draw probability, in_category) per draw unit, for the
    iid_equal_weight and weighted_independent mechanisms.
    population/marked/drawn/observed: for without_replacement.
    n/target/observed: for deterministic_allocation.
    """

    units: tuple[tuple[int, Fraction, bool], ...] = ()
    population: int = 0
    marked: int = 0
    drawn: int = 0
    n: int = 0
    target: Fraction = Fraction(0)
    observed: int = 0


def declaration_gap(decl: Declaration | None) -> str | None:
    """None when the declaration is complete; otherwise the gap reason."""
    if decl is None or decl.mechanism is None:
        return MISSING_METHOD
    if decl.mechanism not in MECHANISMS:
        return MISSING_METHOD
    if any(getattr(decl, name) is None for name in REQUIRED):
        return MISSING_DECLARATIONS
    if decl.mechanism == "deterministic_allocation" and decl.rounding != "half_even":
        return MISSING_DECLARATIONS
    return None


def half_even(value: Fraction) -> int:
    return round(value)  # Python rounds a Fraction half to even


def evaluate_cell(decl: Declaration, cell: Cell, c: Fraction) -> str:
    """Outcome of one cell under its declared mechanism (derivation harness)."""
    gap = declaration_gap(decl)
    if gap is not None:
        return gap
    mech = decl.mechanism
    if mech == "deterministic_allocation":
        if cell.n < 1:
            return UNDEFINED
        return (
            PASS if cell.observed == half_even(cell.n * cell.target) else EXACT_MISMATCH
        )
    if mech == "without_replacement":
        if cell.drawn < 1:
            return UNDEFINED
        pmf = hypergeometric_pmf(cell.population, cell.marked, cell.drawn)
        return PASS if pmf_tail_pass(pmf, cell.observed, c) else OUT
    if not cell.units:
        return UNDEFINED
    k = sum(w for w, _, inside in cell.units if inside)
    if mech == "iid_equal_weight":
        probs = {p for _, p, _ in cell.units}
        if any(w != 1 for w, _, _ in cell.units) or len(probs) != 1:
            # binomial is valid only for iid equal-weight units of the statistic
            return MISSING_METHOD
        (t,) = probs
        return PASS if rule_b_pass(k, len(cell.units), t, c) else OUT
    pmf = weighted_bernoulli_pmf([(w, p) for w, p, _ in cell.units])
    return PASS if pmf_tail_pass(pmf, k, c) else OUT


def evaluate_family(decl: Declaration, cells: Sequence[Cell], c: Fraction) -> str:
    """AND over the cells; an empty family is never a pass."""
    if not cells:
        return UNDEFINED
    gap = declaration_gap(decl)
    if gap is not None:
        return gap
    for cell in cells:
        outcome = evaluate_cell(decl, cell, c)
        if outcome != PASS:
            return outcome
    return PASS


@dataclass(frozen=True)
class FamilyPlan:
    """Frozen before any numerator is read: mechanism and category counts.

    ``categories`` holds, per eligible cell (denominator at least 1), the
    number of categories tested in it. Numerators are not an input, so K
    cannot depend on the output's residuals.
    """

    mechanism: str
    categories: tuple[int, ...] = field(default_factory=tuple)


def tests_in_cell(categories: int) -> int:
    """Two categories are one test (k and n - k reject together)."""
    if categories < 2:
        raise ValueError("a share needs at least two categories")
    return 1 if categories == 2 else categories


def fit_family_size(plans: Sequence[FamilyPlan]) -> int:
    """K: random-mechanism tests summed over every family of the whole fit."""
    k = sum(
        tests_in_cell(cats)
        for plan in plans
        if plan.mechanism != "deterministic_allocation"
        for cats in plan.categories
    )
    if k < 1:
        raise ValueError("no random-mechanism test in the fit")
    return k


def employment_gender_check(
    table_available: bool, decl: Declaration, cells: Sequence[Cell], c: Fraction
) -> str:
    """Without the owner's gender table the field is null: NOT_DRAWN, no pass."""
    if not table_available:
        return NOT_DRAWN
    return evaluate_family(decl, cells, c)


def additional_correlations(pairs: Sequence[dict[str, object]]) -> str:
    """OTHER_CORRELATIONS: no sourced pair means the gap stays."""
    if not pairs:
        return MISSING_DECLARATIONS
    for pair in pairs:
        if pair.get("target_source") != "public_source":
            return SPEC_MISSING  # a construction assumption is not a target
    return PASS


def tolerance_from_roster(entry: dict[str, object]) -> str:
    """A tolerance must come from the frozen roster, never from the output."""
    if entry.get("source") != "roster" or entry.get("tolerance_ref") is None:
        return SPEC_MISSING
    return PASS


# ===================================================== r1 Rule D (withdrawn)


def r1_sidak_z(cells: int) -> float:
    alpha = 1.0 - 0.95 ** (1.0 / cells)
    return NormalDist().inv_cdf(1.0 - alpha / 2.0)


def r1_z2(cells: int) -> Fraction:
    return Fraction(math.ceil(r1_sidak_z(cells) ** 2 * 10_000), 10_000)


def r1_score_pass(k: int, n: int, t: Fraction, z2: Fraction) -> bool:
    """r1's normal score band; withdrawn, kept for the counterexamples."""
    return (k - n * t) ** 2 <= z2 * n * t * (1 - t)


def r1_false_fail(n: int, t: Fraction, cells: int) -> Fraction:
    """Exact per-cell rejection rate of r1's band under the target."""
    z2 = r1_z2(cells)
    pmf = binomial_pmf(n, t)
    return sum(
        (p for k, p in pmf.items() if not r1_score_pass(k, n, t, z2)), Fraction(0)
    )


def r1_detectable_bias(n: int, t: Fraction, cells: int, power: float = 0.95) -> float:
    return (r1_sidak_z(cells) + NormalDist().inv_cdf(power)) * math.sqrt(
        float(t * (1 - t)) / n
    )


def independent_family_false_fail(per_cell: Sequence[Fraction]) -> Fraction:
    """1 - prod(1 - r_i): exact when the cells are independent."""
    keep = Fraction(1)
    for r in per_cell:
        keep *= 1 - r
    return 1 - keep


# ============================================================ spread

Series = Sequence[tuple[Fraction, Fraction]]


def _interpolate(series: Series, rank: Fraction) -> Fraction:
    """Copy of the S4-T03 rule: flat tails, linear between declared quantiles."""
    if rank <= series[0][0]:
        return series[0][1]
    for (p, value), (q, nxt) in itertools.pairwise(series):
        if rank <= q:
            return value + (rank - p) / (q - p) * (nxt - value)
    return series[-1][1]


def construct(series: Series, n: int) -> list[Fraction]:
    """Undisturbed construction: ranks index/(n-1), a singleton at 1/2."""
    if n < 1:
        raise Undefined("empty group")
    if n == 1:
        return [_interpolate(series, Fraction(1, 2))]
    return [_interpolate(series, Fraction(i, n - 1)) for i in range(n)]


def hf7(values: Sequence[Fraction], p: Fraction) -> Fraction:
    """Hyndman-Fan type 7: position (n-1)p, linear between order statistics."""
    if not values:
        raise Undefined("empty group")
    x = sorted(values)
    h = (len(x) - 1) * p
    j = math.floor(h)
    if j + 1 >= len(x):
        return x[-1]
    return x[j] + (h - j) * (x[j + 1] - x[j])


def hf6(values: Sequence[Fraction], p: Fraction) -> Fraction:
    """Hyndman-Fan type 6, for contrast only."""
    x = sorted(values)
    h = (len(x) + 1) * p
    j = math.floor(h)
    if j < 1:
        return x[0]
    if j >= len(x):
        return x[-1]
    return x[j - 1] + (h - j) * (x[j] - x[j - 1])


def predicted_hf7(series: Series, n: int, p: Fraction) -> Fraction:
    """L(p): type 7 of the undisturbed, unrounded construction, in closed form.

    n = 1: the singleton's value, Q*(1/2), at every p. n >= 2: with
    w = 1/(n-1), h = (n-1)p and j = floor(h), L(p) interpolates Q* linearly
    between the rank-grid points j w and (j+1) w. At a grid-aligned knot
    (h an integer) L(p) = Q*(p): the interpolation discrepancy is zero.
    """
    if n < 1:
        raise Undefined("empty group")
    if n == 1:
        return _interpolate(series, Fraction(1, 2))
    h = (n - 1) * p
    j = math.floor(h)
    left = _interpolate(series, Fraction(j, n - 1))
    if j + 1 >= n:
        return left
    right = _interpolate(series, Fraction(j + 1, n - 1))
    return left + (h - j) * (right - left)


def interpolation_discrepancy(series: Series, n: int, p: Fraction) -> Fraction:
    """D_p = L(p) - Q*(p), signed and exact."""
    target = dict(series)[p]
    return predicted_hf7(series, n, p) - target


def round_half_even(value: Fraction, quantum: Fraction) -> Fraction:
    return Fraction(round(value / quantum)) * quantum


def spread_check(
    values: Sequence[Fraction],
    series: Series,
    quantum: Fraction,
    extra: Fraction = Fraction(0),
) -> str:
    """Proposed SPREAD rule for one group and one basis.

    R_p = Q^(p) / Q*(p). Accepted iff, at every declared p,
    |Q^(p) - L(p)| <= quantum / 2 + extra, i.e.
    R_p in [(L(p) - quantum/2 - extra) / Q*(p), (L(p) + quantum/2 + extra) / Q*(p)].
    ``extra`` is the disturbance allowance; the record proposes zero.
    """
    if not values:
        return UNDEFINED
    if any(q <= 0 for _, q in series):
        return UNDEFINED  # the construction refuses PAY_REFERENCE_DOMAIN first
    n = len(values)
    for p, _ in series:
        if abs(hf7(values, p) - predicted_hf7(series, n, p)) > quantum / 2 + extra:
            return OUT
    return PASS


def r1_construction_bound(series: Series, n: int, p: Fraction) -> Fraction:
    """r1's envelope B_p (withdrawn): w * sum |slope change| / 4 in the bracket."""
    seg = [(q1 - q0) / (p1 - p0) for (p0, q0), (p1, q1) in itertools.pairwise(series)]
    slopes = list(zip([Fraction(0), *seg], [*seg, Fraction(0)], strict=False))
    w = Fraction(1, n - 1)
    j = math.floor((n - 1) * p)
    lo, hi = j * w, (j + 1) * w
    total = sum(
        (
            abs(r - left)
            for (q, _), (left, r) in zip(series, slopes, strict=False)
            if lo <= q <= hi
        ),
        Fraction(0),
    )
    return w * total / 4


def r1_spread_pass(
    values: Sequence[Fraction], series: Series, quantum: Fraction
) -> bool:
    """r1's rule without its n >= 30 refusal: |Q^ - Q*| <= B_p + quantum/2."""
    n = len(values)
    return all(
        abs(hf7(values, p) - q) <= r1_construction_bound(series, n, p) + quantum / 2
        for p, q in series
    )


def r1_extra_slack(series: Series, n: int, p: Fraction) -> Fraction:
    """How far r1's envelope reaches beyond the proposed interval at p."""
    return r1_construction_bound(series, n, p) + abs(
        interpolation_discrepancy(series, n, p)
    )


# ============================================================ shapes


def shares(row: Sequence[Fraction]) -> list[Fraction]:
    total = sum(row, Fraction(0))
    if total <= 0 or any(v < 0 for v in row):
        raise Undefined("no shape")
    return [Fraction(v) / total for v in row]


def mean_rows(rows: Sequence[Sequence[Fraction]]) -> list[Fraction]:
    return [sum(col, Fraction(0)) / len(rows) for col in zip(*rows, strict=True)]


def max_gap(a: Sequence[Fraction], b: Sequence[Fraction]) -> Fraction:
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


def loo_gaps(rows: Sequence[Sequence[Fraction]]) -> list[Fraction]:
    if len(rows) < 3:
        raise Undefined("needs three rows")
    return [
        max_gap(row, mean_rows([r for j, r in enumerate(rows) if j != i]))
        for i, row in enumerate(rows)
    ]


def loo_median_gap(rows: Sequence[Sequence[Fraction]]) -> Fraction:
    """Median over rows of the row's largest gap to the mean of the others."""
    return Fraction(median(loo_gaps(rows)))


def shape_check(
    simulated: Sequence[Fraction], rows: Sequence[Sequence[Fraction]]
) -> str:
    """F19/F21 derivation harness: tolerance from the anchor's own rows."""
    if len(rows) < 3:
        return UNSUPPORTED_COVERAGE
    anchor = mean_rows(rows)
    tau = loo_median_gap(rows)
    flat = [Fraction(1, len(anchor))] * len(anchor)
    if max_gap(flat, anchor) <= tau:
        return UNSUPPORTED_COVERAGE  # the anchor cannot tell its shape from flat
    return PASS if max_gap(simulated, anchor) <= tau else OUT


# ============================================================ ranks


def average_ranks(values: Sequence[Fraction]) -> list[Fraction]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [Fraction(0)] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mid = Fraction(i + j + 2, 2)
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    return ranks


def _moments(
    x: Sequence[Fraction], y: Sequence[Fraction]
) -> tuple[Fraction, Fraction, Fraction]:
    rx, ry = average_ranks(x), average_ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy, sxx, syy


def corr_cmp(sxy: Fraction, sxx: Fraction, syy: Fraction, r: Fraction) -> int:
    """Sign of sxy / sqrt(sxx syy) - r, exactly (no square root taken)."""
    if sxx == 0 or syy == 0:
        raise Undefined("constant series")
    s = sxx * syy
    if sxy >= 0 and r < 0:
        return 1
    if sxy < 0 and r >= 0:
        return -1
    lhs, rhs = sxy * sxy, r * r * s
    if sxy >= 0:  # both non-negative
        return (lhs > rhs) - (lhs < rhs)
    return (rhs > lhs) - (rhs < lhs)  # both negative: larger |.| is smaller


def spearman_cmp(x: Sequence[Fraction], y: Sequence[Fraction], r: Fraction) -> int:
    return corr_cmp(*_moments(x, y), r)


def spearman(x: Sequence[Fraction], y: Sequence[Fraction]) -> float:
    """Display only: Pearson correlation of average ranks."""
    sxy, sxx, syy = _moments(x, y)
    if sxx == 0 or syy == 0:
        raise Undefined("constant series")
    return float(sxy) / math.sqrt(float(sxx * syy))


def spearman_shortcut(x: Sequence[Fraction], y: Sequence[Fraction]) -> Fraction:
    """1 - 6 sum d^2 / (n (n^2 - 1)): exact only without ties (planted contrast)."""
    n = len(x)
    d2 = sum(
        (a - b) ** 2 for a, b in zip(average_ranks(x), average_ranks(y), strict=True)
    )
    return 1 - 6 * d2 / (n * (n * n - 1))


def f15_check(
    wages: Sequence[Fraction],
    prices: Sequence[Fraction],
    target: Fraction,
    tol: Fraction = Fraction(1, 10),
) -> str:
    """F15 with the proposed estimator: |rho - target| <= tol, exact."""
    if len(set(wages)) < 2 or len(set(prices)) < 2:
        return UNDEFINED
    low = spearman_cmp(wages, prices, target - tol)
    high = spearman_cmp(wages, prices, target + tol)
    return PASS if low >= 0 and high <= 0 else OUT


def f15_check_shortcut(
    wages: Sequence[Fraction],
    prices: Sequence[Fraction],
    target: Fraction,
    tol: Fraction = Fraction(1, 10),
) -> str:
    """Planted wrong estimator: the no-ties shortcut."""
    return PASS if abs(spearman_shortcut(wages, prices) - target) <= tol else OUT


def _levels(ranks: Sequence[Fraction]) -> list[tuple[Fraction, int]]:
    out: dict[Fraction, int] = {}
    for r in ranks:
        out[r] = out.get(r, 0) + 1
    return sorted(out.items())


def _compositions(total: int, caps: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
    if not caps:
        if total == 0:
            yield ()
        return
    first, rest = caps[0], caps[1:]
    room = sum(rest)
    for v in range(max(0, total - room), min(first, total) + 1):
        for tail in _compositions(total - v, rest):
            yield (v, *tail)


def exact_null_upper_tail(
    x: Sequence[Fraction], y: Sequence[Fraction], r: Fraction
) -> Fraction:
    """P(rho >= r) when y is matched to x by a uniformly random permutation.

    Tie-aware and exact: the tie structures (average ranks) of both series are
    kept, and the law is enumerated over contingency tables of rank levels
    with fixed margins, each weighted by its number of permutations.
    """
    rx, ry = average_ranks(x), average_ranks(y)
    n = len(rx)
    xl, yl = _levels(rx), _levels(ry)
    if len(xl) < 2 or len(yl) < 2:
        raise Undefined("constant series")
    mean = Fraction(n + 1, 2)
    sxx = sum((a - mean) ** 2 for a in rx)
    syy = sum((b - mean) ** 2 for b in ry)
    yvals = tuple(v for v, _ in yl)
    states: dict[tuple[int, ...], dict[Fraction, int]] = {
        tuple(cnt for _, cnt in yl): {Fraction(0): 1}
    }
    for a, m in xl:
        nxt: dict[tuple[int, ...], dict[Fraction, int]] = {}
        for rem, dist in states.items():
            for comp in _compositions(m, rem):
                ways = math.factorial(m)  # m! / prod(v!): exact multinomial
                for v in comp:
                    ways //= math.factorial(v)
                add = a * sum(v * b for v, b in zip(comp, yvals, strict=False))
                key = tuple(rr - v for rr, v in zip(rem, comp, strict=False))
                bucket = nxt.setdefault(key, {})
                for s, wgt in dist.items():
                    bucket[s + add] = bucket.get(s + add, 0) + wgt * ways
        states = nxt
    (final,) = states.values()
    scale = math.prod(math.factorial(cnt) for _, cnt in yl)
    whole = math.factorial(n)
    hit = sum(
        wgt
        for t, wgt in final.items()
        if corr_cmp(t - n * mean * mean, sxx, syy, r) >= 0
    )
    return Fraction(hit * scale, whole)


def brute_null_upper_tail(
    x: Sequence[Fraction], y: Sequence[Fraction], r: Fraction
) -> Fraction:
    """The same probability by listing every permutation (small n only)."""
    perms = list(itertools.permutations(y))
    hit = sum(1 for p in perms if spearman_cmp(x, list(p), r) >= 0)
    return Fraction(hit, len(perms))


def brute_null_rho_moments(
    x: Sequence[Fraction], y: Sequence[Fraction]
) -> tuple[Fraction, Fraction]:
    """(E[sxy], E[rho^2]) under the uniform permutation null, by listing every
    permutation (small n only). E[rho] = E[sxy] / sqrt(sxx syy), so E[rho] = 0
    exactly when the first entry is 0; then Var(rho) is the second entry."""
    rx, ry = average_ranks(x), average_ranks(y)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cx = [a - mx for a in rx]
    cy = [b - my for b in ry]
    sxx = sum(a * a for a in cx)
    syy = sum(b * b for b in cy)
    if sxx == 0 or syy == 0:
        raise Undefined("constant series")
    total, total_sq, count = Fraction(0), Fraction(0), 0
    for p in itertools.permutations(cy):
        sxy = sum(a * b for a, b in zip(cx, p, strict=True))
        total += sxy
        total_sq += sxy * sxy
        count += 1
    return total / count, total_sq / count / (sxx * syy)


def cantelli_bound_from_variance(variance: Fraction, r: Fraction) -> Fraction:
    """One-sided Cantelli bound P(Z - E[Z] >= r) <= v / (v + r^2), for r > 0."""
    if r <= 0:
        raise Undefined("Cantelli's one-sided bound needs r > 0")
    return variance / (variance + r * r)


def cantelli_null_bound(n: int, r: Fraction) -> Fraction:
    """Conservative bound on P(rho >= r) under the exact permutation null.

    For fixed nonconstant centred rank vectors of n zones, E[rho] = 0 and
    Var(rho) = 1/(n - 1) whatever the ties, so P(rho >= r) <= 1/(1 + (n-1) r^2).
    """
    if n < 2:
        raise Undefined("rho needs at least two zones")
    if r <= 0 or r > 1:
        raise Undefined("the bound is stated for 0 < r <= 1")
    return cantelli_bound_from_variance(Fraction(1, n - 1), r)


def cantelli_first_n(r: Fraction, alpha: Fraction) -> int:
    """Smallest n >= 2 with cantelli_null_bound(n, r) <= alpha (exact).

    1/(1 + (n-1) r^2) <= alpha  <=>  n - 1 >= (1 - alpha) / (alpha r^2).
    """
    if not 0 < alpha < 1:
        raise Undefined("alpha must lie in (0, 1)")
    need = (1 - alpha) / (alpha * r * r)
    return max(2, 1 + math.ceil(need))


def cantelli_threshold_sq(n: int, alpha: Fraction) -> Fraction:
    """Option C of open point 9: the squared threshold at which the bound for n
    zones equals alpha, (1 - alpha) / (alpha (n - 1)). Above 1 it is unreachable."""
    if n < 2:
        raise Undefined("rho needs at least two zones")
    return (1 - alpha) / (alpha * (n - 1))


def worst_two_level_tail(n: int, r: Fraction) -> tuple[Fraction, tuple[int, int]]:
    """Largest exact P(rho >= r) over every two-level tie pattern of n zones:
    a high zones of x (a <= n/2, by symmetry) and b high zones of y. Returns the
    probability and the first (a, b) that attains it. A lower bound on the
    worst case over all tie patterns, not the worst case itself."""
    worst: tuple[Fraction, tuple[int, int]] = (Fraction(-1), (0, 0))
    for a in range(1, n // 2 + 1):
        x = [Fraction(1)] * (n - a) + [Fraction(2)] * a
        for b in range(1, n):
            y = [Fraction(1)] * (n - b) + [Fraction(2)] * b
            p = exact_null_upper_tail(x, y, r)
            if p > worst[0]:
                worst = (p, (a, b))
    return worst


def largest_n_two_level_over(r: Fraction, alpha: Fraction, up_to: int) -> int | None:
    """Largest n <= up_to at which some two-level pattern exceeds alpha."""
    last = None
    for n in range(2, up_to + 1):
        if worst_two_level_tail(n, r)[0] > alpha:
            last = n
    return last


def x1_check(
    presence: Sequence[Fraction],
    visits: Sequence[Fraction],
    threshold: Fraction = Fraction(6, 10),
    minimum: int | None = None,
) -> str:
    """X1 derivation harness. The minimum zones stays open (None): gap."""
    if minimum is None:
        return MISSING_TOLERANCE
    if len(presence) < minimum:
        return UNSUPPORTED_COVERAGE
    if len(set(presence)) < 2 or len(set(visits)) < 2:
        return UNDEFINED
    return PASS if spearman_cmp(presence, visits, threshold) >= 0 else OUT


def r1_null_pass_probability(rho: Fraction, n: int) -> float:
    """r1's normal approximation (withdrawn as a general claim)."""
    return 1 - NormalDist().cdf(float(rho) * math.sqrt(n - 1))


# ======================================================= conventions


def size_check(
    public: Sequence[Fraction],
    world: Sequence[Fraction],
    units_public: int,
    units_world: int,
    points: Fraction = Fraction(2),
    floor: int = 1000,
) -> str:
    """SIZE: every class share within ``points`` percentage points, own classes."""
    if len(public) != len(world):
        return "FIT_PUBLIC_SIZE_REBANDING"
    if units_public < floor or units_world < floor:
        return UNSUPPORTED_COVERAGE
    gap = max_gap(shares(public), shares(world)) * 100
    return PASS if gap <= points else OUT


def mean_check(
    public: Fraction,
    synthetic: Fraction,
    public_basis: str,
    synthetic_basis: str,
    rel: Fraction = Fraction(1, 10),
) -> str:
    """MEANS: |synthetic / public - 1| <= 10%, same monthly basis only."""
    if public_basis != synthetic_basis or public_basis != "monthly":
        return ANNUAL_AS_MONTHLY
    if public <= 0:
        return UNDEFINED
    return PASS if abs(synthetic / public - 1) <= rel else OUT


def absolute_pp_pass(observed: Fraction, target: Fraction, points: Fraction) -> bool:
    return abs(observed - target) * 100 <= points


def aggregation_check(person_groups: Sequence[str], written: dict[str, int]) -> str:
    """MOVEMENT_NATIONALITY (simulated groups): written split = aggregation."""
    counts: dict[str, int] = {}
    for g in person_groups:
        counts[g] = counts.get(g, 0) + 1
    return PASS if counts == written else EXACT_MISMATCH


# ============================================================ report


def _fmt(x: Fraction, digits: int = 6) -> str:
    return f"{float(x):.{digits}g}"


def main(say: Callable[[str], None] = print) -> int:
    c1000 = tail_level(1000)
    say("Rule B: per-tail level c = 0.05/(2K)")
    for k in (1, 8, 20, 1000):
        say(f"  K={k:>4}  c={tail_level(k)}")
    say("Rule B worked limits at K = 1,000 (lo, hi): a count passes iff lo <= k <= hi")
    for n, t in (
        (5000, Fraction(4, 100)),
        (2000, Fraction(12, 100)),
        (50000, Fraction(30, 100)),
        (50000, Fraction(70, 100)),
        (20000, Fraction(8, 100)),
        (200000, Fraction(65, 100)),
        (1000000, Fraction(15, 1000)),
    ):
        say(f"  n={n:>7} t={t}  {binomial_limits(n, t, c1000)}")
    say("Review counterexamples: exact null rejection, r1 band against Rule B")
    for k_cells, n, t, cells in (
        (1, 10, Fraction(1, 100), 1),
        (8, 10, Fraction(1, 100), 8),
        (1000, 30, Fraction(1, 1000), 1000),
        (20, 400, Fraction(3, 10), 20),
    ):
        r1 = r1_false_fail(n, t, k_cells)
        lo, hi = binomial_limits(n, t, tail_level(k_cells))
        rb = binomial_rejection(n, t, lo, hi)
        say(
            f"  K={k_cells} n={n} t={t}: r1 family {_fmt(independent_family_false_fail([r1] * cells))}"
            f"  Rule B limits {(lo, hi)} family {_fmt(independent_family_false_fail([rb] * cells))}"
            f"  Bonferroni sum {_fmt(rb * cells)}"
        )
    lo, hi = binomial_limits(1000, Fraction(2, 100), c1000)
    say(
        f"Power: n=1000 t=2% K=1000 limits {(lo, hi)}; r1's 2.52-point bias,"
        f" exact power under Rule B at t=4.52%: {_fmt(binomial_rejection(1000, Fraction(452, 10000), lo, hi))}"
    )
    d = least_bias_for_power(
        1000, Fraction(2, 100), c1000, Fraction(95, 100), Fraction(1, 10000)
    )
    say(
        f"  smallest upward bias (0.01-point steps) with exact power >= 95%: {_fmt(d * 100)} points"
    )
    say("Crossing with a fixed 2-point band (K = 1,000)")
    for n, t, k in ((2000, Fraction(12, 100), 298), (5000, Fraction(4, 100), 280)):
        say(
            f"  n={n} t={t} k={k}: Rule B {rule_b_pass(k, n, t, c1000)}  2 points "
            f"{absolute_pp_pass(Fraction(k, n), t, Fraction(2))}"
        )
    series = (
        (Fraction(1, 10), Fraction(1000)),
        (Fraction(1, 4), Fraction(1500)),
        (Fraction(1, 2), Fraction(2500)),
        (Fraction(3, 4), Fraction(4000)),
        (Fraction(9, 10), Fraction(7000)),
    )
    say("SPREAD: interpolation discrepancy D_p and r1's extra slack, q = 1")
    for n in (21, 30, 101):
        say(
            f"  n={n}: D = {[str(interpolation_discrepancy(series, n, p)) for p, _ in series]}"
            f"  r1 extra = {[str(r1_extra_slack(series, n, p)) for p, _ in series]}"
        )
    tied = [Fraction(1)] * 11 + [Fraction(2)]
    say(
        f"X1: 12-zone tied fixture, exact P(rho >= 0.6) = {exact_null_upper_tail(tied, tied, Fraction(6, 10))}"
    )
    for n in (12, 20, 30):
        one = [Fraction(1)] * (n - 1) + [Fraction(2)]
        say(
            f"  one-high family n={n}: {exact_null_upper_tail(one, one, Fraction(6, 10))}"
        )
    r, alpha = Fraction(3, 5), Fraction(1, 20)
    first = cantelli_first_n(r, alpha)
    say(
        f"X1 Cantelli bound 1/(1+(n-1)r^2) at r=3/5, alpha=1/20: first n = {first},"
        f" bound there {cantelli_null_bound(first, r)} = {_fmt(cantelli_null_bound(first, r), 15)};"
        f" at n={first - 1}: {cantelli_null_bound(first - 1, r)}"
    )
    say(
        f"  at n=35 (the visits_phcc row count): bound {cantelli_null_bound(35, r)};"
        f" option C threshold^2 = {cantelli_threshold_sq(35, alpha)}"
    )
    p, pattern = worst_two_level_tail(39, r)
    say(
        f"  worst two-level tie pattern at n=39: (a, b) = {pattern}, exact {p};"
        f" largest n <= 54 with a two-level pattern over 5%:"
        f" {largest_n_two_level_over(r, alpha, 54)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
