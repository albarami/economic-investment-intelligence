"""Pure policy tests from decision 0031; no provider protocol is assumed."""

import pytest

from eii_custodian.publicdata.busyness.policy import (
    CreditBudget,
    names_match,
    reaches_minimum,
    run_limit,
)


@pytest.mark.parametrize("value", [None, "", "0", "-1", "1.5", "true", " 2", "+2", "٢"])
def test_besttime_limit_refuses_invalid_environment(value: str | None) -> None:
    environ = {} if value is None else {"EII_BESTTIME_RUN_CREDIT_LIMIT": value}
    with pytest.raises(ValueError, match="EII_BESTTIME_RUN_CREDIT_LIMIT"):
        run_limit(environ)


def test_besttime_limit_comes_from_environment() -> None:
    assert run_limit({"EII_BESTTIME_RUN_CREDIT_LIMIT": "3"}) == 3


def test_besttime_exact_limit_reserved_and_over_limit_stops_permanently() -> None:
    budget = CreditBudget(3)
    assert budget.reserve("SYN-a", "forecast", 2)
    assert budget.used == 2
    assert budget.reserve("SYN-a", "query", 1)
    assert budget.used == 3
    assert not budget.reserve("SYN-b", "forecast", 1)
    assert budget.used == 3
    assert not budget.reserve("SYN-c", "forecast", 1)


def test_besttime_stop_does_not_resume_for_cheaper_request() -> None:
    budget = CreditBudget(2)
    assert not budget.reserve("SYN-a", "forecast", 3)
    assert not budget.reserve("SYN-b", "forecast", 1)
    assert budget.used == 0


@pytest.mark.parametrize("kind", ["forecast", "query"])
def test_besttime_duplicate_request_refused(kind: str) -> None:
    budget = CreditBudget(20)
    assert budget.reserve("SYN-a", "forecast", 2)
    if kind == "query":
        assert budget.reserve("SYN-a", "query", 1)
    with pytest.raises(ValueError, match="duplicate"):
        budget.reserve("SYN-a", kind, 1)


@pytest.mark.parametrize("kind", ["query", "other"])
def test_besttime_query_order_and_request_kind_closed(kind: str) -> None:
    with pytest.raises(ValueError):
        CreditBudget(3).reserve("SYN-a", kind, 1)


@pytest.mark.parametrize("cost", [0, -1, True, 1.5])
def test_besttime_invalid_cost_rejected(cost) -> None:
    with pytest.raises(ValueError):
        CreditBudget(3).reserve("SYN-a", "forecast", cost)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_besttime_invalid_budget_rejected(limit) -> None:
    with pytest.raises(ValueError):
        CreditBudget(limit)


def test_besttime_names_use_only_nfc_and_casefold() -> None:
    assert names_match("INVENTED CAFE\u0301", "Invented Café")
    assert names_match("Invented Café", "INVENTED CAFE\u0301")
    assert names_match("Invented Straße", "invented strasse")
    assert not names_match("Invented Cafe", "Invented Café")
    assert not names_match("Invented Cafe", " Invented Cafe")
    assert not names_match("Invented Cafe", "Invented  Cafe")
    assert not names_match("Invented Cafe", "Other Cafe")


def test_besttime_coverage_threshold_two_and_three() -> None:
    assert not reaches_minimum(2)
    assert reaches_minimum(3)
    assert reaches_minimum(4)
