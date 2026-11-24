"""INVENTED rows only: the Wilson example's stock and pre-registered period cases.

These never read the lead's real cache; `custodian/data_tests` stays lead-shell only.
"""

import re
import warnings
from decimal import Decimal as D

import pytest
from custodian.data_tests import cache
from custodian.data_tests import test_pinned_methods as methods
from custodian.tests.test_method_cache import _write_cached_source
from custodian.tests.test_restricted_expectation_guards import child_run
from hypothesis import given
from hypothesis import strategies as st

SHAMAL = "بلدية الشمال"
OTHER = "بلدية تجريبية"
ACTIVITY = "5610101"
BULK_MONTH = ("2019", 7)

# Written here before any run (L-1717; L5c section 1 option B item 1). Never widened.
PREREGISTERED_WILSON_GRID = (
    ("2015", "2015"),
    ("2016", "2016"),
    ("2017", "2017"),
    ("2018", "2018"),
    ("2019", "2019"),
    ("2020", "2020"),
    ("2021", "2021"),
    ("2022", "2022"),
    ("2023", "2023"),
    ("2024", "2024"),
    ("2025-partial", "2025"),
)


def active_rows(stock_parts=(20, 8)):
    rows = [
        {
            "lbldy": SHAMAL,
            "rmz_lnsht_ltjry": ACTIVITY,
            "lnsht_ltjry": "نشاط تجريبي",
            "dd_lrkhs_lnsht": part,
        }
        for part in stock_parts
    ]
    rows.append(
        {
            "lbldy": OTHER,
            "rmz_lnsht_ltjry": ACTIVITY,
            "lnsht_ltjry": "نشاط تجريبي",
            "dd_lrkhs_lnsht": 500,
        }
    )
    return rows


def cancellation(municipality, year, month, count, activity=ACTIVITY):
    return {
        "sn_llg": year,
        "shhr_llg": month,
        "lbldy": municipality,
        "rmz_lnsht_ltjry": activity,
        "sm_lnsht_ltjry": "نشاط تجريبي",
        "dd_lrkhs_lmlg": count,
    }


def cancelled_rows(shamal):
    """A steady invented background of 10 a month, one bulk month, then Al Shamal."""
    rows = [
        cancellation(OTHER, period[:4], int(period[5:]), 10)
        for period in methods.C2_CALENDAR
    ]
    rows.append(cancellation(OTHER, BULK_MONTH[0], BULK_MONTH[1], 1000))
    rows.extend(
        cancellation(SHAMAL, year, month, count)
        for (year, month), count in shamal.items()
    )
    # Undated rows and another activity never enter a year's count.
    rows.append(cancellation(SHAMAL, None, None, 6))
    rows.append(cancellation(SHAMAL, "2018", 3, 6, activity="5630112"))
    return rows


def readings(tmp_path, shamal, stock_parts=(20, 8)):
    pins = {
        "lic_active": _write_cached_source(
            tmp_path, "lic_active", active_rows(stock_parts)
        ),
        "lic_cancelled": _write_cached_source(
            tmp_path, "lic_cancelled", cancelled_rows(shamal)
        ),
    }
    active, active_chain = cache.cached(tmp_path, "lic_active", pins["lic_active"])
    cancelled, cancelled_chain = cache.cached(
        tmp_path, "lic_cancelled", pins["lic_cancelled"]
    )
    return active, active_chain, cancelled, cancelled_chain


# 2019 holds 4 in an ordinary month and 2 in the flagged bulk month: 6 only
# when flagged months are included. Every other cell differs from 6.
ONE_MATCH = {
    ("2016", 2): 5,
    ("2019", 3): 4,
    (BULK_MONTH[0], BULK_MONTH[1]): 2,
    ("2021", 11): 7,
    ("2024", 9): 3,
    ("2025", 4): 1,
}


def test_wilson_grid_is_exactly_the_preregistered_set():
    if tuple(methods.WILSON_PERIOD_GRID) != PREREGISTERED_WILSON_GRID:
        raise AssertionError("wilson_grid_changed")
    assert methods.WILSON_MUNICIPALITY == (SHAMAL, "al_shamal")
    assert (methods.WILSON_STOCK, methods.WILSON_CANCELLATIONS) == (D(28), D(6))


@pytest.mark.parametrize(
    "mutated",
    [
        (("2014", "2014"), *PREREGISTERED_WILSON_GRID),
        PREREGISTERED_WILSON_GRID[1:],
        (*PREREGISTERED_WILSON_GRID[:-1], ("2025", "2025")),
        tuple(reversed(PREREGISTERED_WILSON_GRID)),
        (*PREREGISTERED_WILSON_GRID, ("2024-excluding", "2024")),
    ],
    ids=["widened", "narrowed", "relabelled", "reordered", "excluding_variant"],
)
def test_wilson_grid_mutation_fails_the_pin(monkeypatch, mutated):
    monkeypatch.setattr(methods, "WILSON_PERIOD_GRID", mutated)
    with pytest.raises(AssertionError, match=r"^wilson_grid_changed$"):
        test_wilson_grid_is_exactly_the_preregistered_set()


def test_wilson_stock_reproduces_period_free(tmp_path):
    methods.wilson_stock_check(*readings(tmp_path, {}))


@pytest.mark.parametrize("stock_parts", [(20, 7), (20, 9), (28, 0, 1)])
def test_wilson_stock_mismatch(tmp_path, stock_parts):
    rows = readings(tmp_path, ONE_MATCH, stock_parts)
    with pytest.raises(ValueError, match=r"^wilson_stock_mismatch$"):
        methods.wilson_stock_check(*rows)
    # The period is never identified while n does not reproduce.
    with pytest.raises(ValueError, match=r"^wilson_stock_mismatch$"):
        methods.wilson_period_label(*rows)


def test_wilson_period_one_match_reports_only_its_label(tmp_path):
    rows = readings(tmp_path, ONE_MATCH)
    assert methods.wilson_period_label(*rows) == "2019"
    # The 2019 match needs the flagged month: excluding it would give 4.
    _, _, result = methods.c2_municipal_churn(
        *rows, *methods.WILSON_MUNICIPALITY, year="2019"
    )
    assert "2019-07" in result["bulk_months_unrounded"]
    assert result["excluding_percent"].exact_unrounded * 28 == 4 * 100


def test_wilson_period_partial_2025_cell(tmp_path):
    rows = readings(tmp_path, {("2025", 1): 2, ("2025", 5): 4, ("2024", 2): 1})
    assert methods.wilson_period_label(*rows) == "2025-partial"


def test_wilson_period_refuses_a_month_after_the_calendar(tmp_path):
    rows = readings(tmp_path, {("2025", 1): 2, ("2025", 6): 4})
    with pytest.raises(ValueError, match=r"^month outside calendar$"):
        methods.wilson_period_label(*rows)


def test_wilson_period_no_match(tmp_path):
    rows = readings(tmp_path, {**ONE_MATCH, ("2019", 3): 5})
    with pytest.raises(ValueError, match=r"^wilson_period_no_match$"):
        methods.wilson_period_label(*rows)


def test_wilson_period_ambiguous(tmp_path):
    rows = readings(tmp_path, {**ONE_MATCH, ("2024", 10): 3})
    with pytest.raises(ValueError, match=r"^wilson_period_ambiguous$"):
        methods.wilson_period_label(*rows)


def test_wilson_period_reads_the_module_grid(tmp_path, monkeypatch):
    rows = readings(tmp_path, ONE_MATCH)
    monkeypatch.setattr(
        methods,
        "WILSON_PERIOD_GRID",
        tuple(cell for cell in PREREGISTERED_WILSON_GRID if cell[0] != "2019"),
    )
    with pytest.raises(ValueError, match=r"^wilson_period_no_match$"):
        methods.wilson_period_label(*rows)


@pytest.fixture(scope="module")
def chains(tmp_path_factory):
    return readings(tmp_path_factory.mktemp("wilson_chains"), {})


GRID_MONTHS = st.sampled_from(
    [(str(y), m) for y in range(2015, 2025) for m in range(1, 13)]
    + [("2025", m) for m in range(1, 6)]
)


@given(st.dictionaries(GRID_MONTHS, st.integers(min_value=0, max_value=6)))
def test_wilson_period_matches_a_plain_oracle(chains, shamal):
    active, active_chain, _, cancelled_chain = chains
    cancelled = cancelled_rows(shamal)
    per_label = {label: 0 for label, _ in PREREGISTERED_WILSON_GRID}
    for (year, _), count in shamal.items():
        per_label["2025-partial" if year == "2025" else year] += count
    matches = [label for label, total in per_label.items() if total == 6]
    args = (active, active_chain, cancelled, cancelled_chain)
    if len(matches) == 1:
        assert methods.wilson_period_label(*args) == matches[0]
    else:
        reason = "no_match" if not matches else "ambiguous"
        with pytest.raises(ValueError, match=f"^wilson_period_{reason}$"):
            methods.wilson_period_label(*args)


CHILD = (
    '"""PYTEST_DONT_REWRITE"""\n'
    "import sys\nfrom pathlib import Path\n"
    "sys.path.insert(0, str(Path.cwd()))\n"
    "import custodian.data_tests.test_pinned_methods as methods\n"
    "from custodian.tests import test_pinned_wilson as invented\n"
    "methods.pinned = invented.child_pinned({shamal!r}, {parts!r})\n"
    "from custodian.data_tests.test_pinned_methods import (\n"
    "    test_pinned_c2_wilson_period,\n"
    "    test_pinned_c2_wilson_stock,\n"
    ")\n"
)


def child_pinned(shamal, parts):
    """Serve invented rows in a child run; the child never sees a real cache."""
    import tempfile
    from pathlib import Path

    rows = readings(Path(tempfile.mkdtemp()), shamal, parts)
    by_source = {"lic_active": rows[:2], "lic_cancelled": rows[2:]}
    return lambda source: by_source[source]


def summary(result):
    """Every FAILED or ERROR line must be exactly `<CASE>:<reason>`."""
    reasons = set()
    for line in (result.stdout + result.stderr).splitlines():
        if line.startswith(("FAILED ", "ERROR ")):
            found = re.fullmatch(
                r"FAILED \S+ - Failed: (C2-(?:WILSON-[A-Z]+|ISIC-5610):[a-z_]+)", line
            )
            assert found is not None, "summary_unparsed"
            reasons.add(found.group(1))
    return reasons


def test_wilson_cases_print_only_case_reason_or_label(tmp_path):
    planted = {**ONE_MATCH, ("2023", 8): 9876543}
    passing = child_run(tmp_path, CHILD.format(shamal=planted, parts=(20, 8)))
    output = passing.stdout + passing.stderr
    assert passing.returncode == 0, output
    assert "WilsonPeriodIdentified: C2-WILSON-PERIOD:2019" in output
    assert "9876543" not in output
    ambiguous = {**planted, ("2024", 10): 3}
    for parts, shamal, expected in (
        (
            (9876543, 0),
            ambiguous,
            {
                "C2-WILSON-STOCK:wilson_stock_mismatch",
                "C2-WILSON-PERIOD:wilson_stock_mismatch",
            },
        ),
        ((20, 8), ambiguous, {"C2-WILSON-PERIOD:wilson_period_ambiguous"}),
        ((20, 8), {("2019", 3): 9876543}, {"C2-WILSON-PERIOD:wilson_period_no_match"}),
        (
            (20, 8),
            {**ONE_MATCH, ("2025", 6): 9876543},
            {
                "C2-WILSON-STOCK:month_outside_calendar",
                "C2-WILSON-PERIOD:month_outside_calendar",
            },
        ),
    ):
        failing = child_run(tmp_path, CHILD.format(shamal=shamal, parts=parts))
        output = failing.stdout + failing.stderr
        assert failing.returncode == 1, output
        assert "9876543" not in output
        assert summary(failing) == expected


SENTINEL = 9876543
FAULT_CHILD = CHILD.replace(
    "methods.pinned = invented.child_pinned({shamal!r}, {parts!r})\n",
    "invented.plant_fault(methods, {where!r}, {kind!r})\n",
)


def plant_fault(methods_module, where, kind):
    """Raise an unexpected error carrying a sentinel count from `where`."""
    error = (
        KeyError(f"{SENTINEL}")
        if kind == "key"
        else ValueError(f"{SENTINEL} rows: lic_active")
    )

    def raiser(*_args, **_kwargs):
        raise error

    methods_module.pinned = child_pinned(ONE_MATCH, (20, 8))
    setattr(methods_module, where, raiser)


@pytest.mark.parametrize("kind", ["key", "value"])
@pytest.mark.parametrize("where", ["pinned", "c2_municipal_churn"])
def test_wilson_unexpected_errors_print_only_source_invalid(tmp_path, where, kind):
    failing = child_run(tmp_path, FAULT_CHILD.format(where=where, kind=kind))
    output = failing.stdout + failing.stderr
    assert failing.returncode == 1, "child_not_failed"
    assert str(SENTINEL) not in output, "sentinel_leaked"
    assert summary(failing) == {
        "C2-WILSON-STOCK:source_invalid",
        "C2-WILSON-PERIOD:source_invalid",
    }


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("wilson_stock_mismatch", "wilson_stock_mismatch"),
        ("wilson_period_no_match", "wilson_period_no_match"),
        ("wilson_period_ambiguous", "wilson_period_ambiguous"),
        ("month outside calendar", "month_outside_calendar"),
        ("public_cache_missing:lic_active", "public_cache_missing"),
        ("public_cache_missing:lic_cancelled", "public_cache_missing"),
        ("receipt_hash_mismatch:lic_active", "receipt_hash_mismatch"),
        ("receipt_hash_mismatch:lic_cancelled", "receipt_hash_mismatch"),
        ("wilson_stock_mismatch:28", "source_invalid"),
        ("public_cache_missing:pop_muni", "source_invalid"),
        ("month outside calendar ", "source_invalid"),
        ("9876543", "source_invalid"),
        ("", "source_invalid"),
    ],
)
def test_wilson_reason_admits_only_the_closed_set(message, reason):
    assert methods.wilson_reason(ValueError(message)) == reason


@pytest.mark.parametrize("kind", [TypeError, ArithmeticError, UnicodeError])
def test_wilson_reason_admits_only_a_plain_value_error(kind):
    assert methods.wilson_reason(kind("wilson_stock_mismatch")) == "source_invalid"


@given(st.text(), st.sampled_from([ValueError, KeyError, TypeError, StopIteration]))
def test_wilson_reason_is_always_closed(message, kind):
    reason = methods.wilson_reason(kind(message))
    admitted = methods.WILSON_REASONS.get(message)
    expected = admitted if kind is ValueError and admitted else "source_invalid"
    assert reason == expected
    assert re.fullmatch(r"[a-z_]+", reason)


def test_wilson_period_warning_names_the_label_only(monkeypatch, tmp_path):
    rows = readings(tmp_path, ONE_MATCH)
    by_source = {"lic_active": rows[:2], "lic_cancelled": rows[2:]}
    monkeypatch.setattr(methods, "pinned", lambda source: by_source[source])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        methods.test_pinned_c2_wilson_period()
    assert [str(w.message) for w in caught] == ["C2-WILSON-PERIOD:2019"]
    assert [w.category for w in caught] == [methods.WilsonPeriodIdentified]
