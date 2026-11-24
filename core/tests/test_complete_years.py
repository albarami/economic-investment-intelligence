"""Complete calendar years are selected only inside calc."""


def test_complete_years():
    from eii_core.calc.public_series import C2_CALENDAR, complete_years

    result = complete_years()
    assert tuple(year for year, _ in result) == tuple(str(y) for y in range(2015, 2025))
    assert tuple(m for _, months in result for m in months) == C2_CALENDAR[:120]
    assert all(len(months) == 12 for _, months in result)


def test_partial_start_is_not_a_complete_year():
    from eii_core.calc.public_series import C2_CALENDAR, complete_years

    result = complete_years(C2_CALENDAR[5:])
    assert tuple(year for year, _ in result) == tuple(str(y) for y in range(2016, 2025))
    assert all(
        months == tuple(f"{year}-{m:02}" for m in range(1, 13))
        for year, months in result
    )
