"""Fail-closed journal and exact budget boundary tests, using invented counters."""

import sys
from decimal import Decimal
from io import StringIO

import pytest
from product.tests.test_map_modes import provider as provider

from eii_product.photoreal_tiles import limit


def assert_failure(action, message="count_unavailable"):
    with pytest.raises(limit.BudgetFailure) as error:
        action()
    assert str(error.value) == message


@pytest.mark.parametrize(
    "journal",
    [
        "ready:0",
        "SYN-invalid\n",
        "\n",
        "ready:0\npending\n",
        "ready:0\npending:one\n",
        "ready:0\npending:0:0\n",
        "ready:0\npending:0\n",
        "ready:0\nready:0\nready:1\n",
        "ready:0\npending:1\nready:1\n",
        "ready:0\npending:0\nSYN-kind:1\n",
        "ready:0\npending:0\nready:2\n",
        "ready:0\npending:0\nready:1\npending:1\nready:0\n",
    ],
)
@pytest.mark.parametrize("operation", ["available", "request"])
def test_damaged_journal_exact_refusal(provider, journal, operation):
    count, calls, _, _ = provider
    count.write_text(journal)
    budget = limit.Budget(count)
    if operation == "available":
        assert_failure(lambda: budget.available(3))
    else:
        assert_failure(
            lambda: budget.request(3, lambda: calls.append("SYN-send"), bool)
        )
    assert count.read_text() == journal
    assert calls == []


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "-Infinity"])
def test_invalid_price_refusal(price):
    assert_failure(lambda: limit.billable_limit(Decimal(price)))


@pytest.mark.parametrize(
    "price,expected",
    [("1", 3333), ("0.5", 3333), ("6", 3333), ("12", 1666), ("20000", 1)],
)
def test_price_floor_and_bound(price, expected):
    assert limit.billable_limit(Decimal(price)) == expected


def test_request_at_cap_sends_nothing(provider):
    count, calls, _, _ = provider
    budget = limit.Budget(count)
    assert budget.request(1, lambda: "SYN-result", lambda result: True) == "SYN-result"
    assert count.read_text() == "ready:0\npending:0\nready:1\n"
    assert_failure(
        lambda: budget.request(1, lambda: calls.append("SYN-send"), bool), "cap_reached"
    )
    assert_failure(lambda: budget.available(1), "cap_reached")
    assert count.read_text() == "ready:0\npending:0\nready:1\n"
    assert calls == []


def test_nonbillable_request_keeps_count(provider):
    count, _, _, _ = provider
    budget = limit.Budget(count)
    assert (
        budget.request(1, lambda: "SYN-refusal", lambda result: False) == "SYN-refusal"
    )
    assert (
        budget.request(1, lambda: "SYN-success", lambda result: True) == "SYN-success"
    )
    assert count.read_text() == "ready:0\npending:0\nready:0\npending:0\nready:1\n"


def test_failed_lock_stays_broken(provider, monkeypatch):
    count, calls, _, _ = provider
    budget = limit.Budget(count)

    def fail_lock(*args):
        raise OSError("SYN-lock-failure")

    with monkeypatch.context() as patch:
        patch.setattr(limit.fcntl, "flock", fail_lock)
        assert_failure(
            lambda: budget.request(2, lambda: calls.append("SYN-send"), bool)
        )
    # The journal is still valid; the same Budget must nevertheless stay closed.
    assert count.read_text() == "ready:0\n"
    assert_failure(lambda: budget.available(2))
    assert_failure(lambda: budget.request(2, lambda: calls.append("SYN-send"), bool))
    assert calls == []


@pytest.mark.parametrize("operation", ["available", "request"])
def test_unicode_journal_is_not_decoded_with_default_encoding(provider, operation):
    count, calls, _, _ = provider
    # UTF-8 splitlines would accept these separators as journal line boundaries.
    count.write_bytes("ready:0\u0085pending:0\u0085ready:1\n".encode())
    budget = limit.Budget(count)
    if operation == "available":
        assert_failure(lambda: budget.available(3))
    else:
        assert_failure(
            lambda: budget.request(3, lambda: calls.append("SYN-send"), bool)
        )
    assert calls == []


def test_missing_counter_is_exact_refusal(provider):
    count, _, _, _ = provider
    count.unlink()
    assert_failure(lambda: limit.Budget(count).available(3))
    assert not count.exists()


def test_read_only_journal_refuses_availability(provider):
    count, _, _, _ = provider
    count.chmod(0o400)
    try:
        assert_failure(lambda: limit.Budget(count).available(3))
    finally:
        count.chmod(0o600)


def test_reader_refuses_non_ascii_decimal(provider):
    # Direct call: public methods reject Unicode at the ASCII file decoder first.
    count, _, _, _ = provider
    assert_failure(
        lambda: limit.Budget(count)._read(
            StringIO("ready:0\npending:\u0660\nready:\u0661\n")
        )
    )


def test_extra_separator_refuses_before_integer_conversion(provider):
    count, _, _, _ = provider
    # available() translates ValueError to BudgetFailure; request() also latches
    # the budget broken on ValueError. Exercise the parser's schema refusal itself.
    journal = "ready:0\npending:0:" + "1" * 641 + "\n"
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        assert_failure(lambda: limit.Budget(count)._read(StringIO(journal)))
    finally:
        sys.set_int_max_str_digits(previous)
