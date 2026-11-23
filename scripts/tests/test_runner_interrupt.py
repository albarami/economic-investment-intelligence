"""Virtual-clock boundary plants for the real interrupt fixture's watcher."""

from __future__ import annotations

import os
import signal
from fractions import Fraction
from unittest.mock import Mock, patch

from hypothesis import example, given
from hypothesis import strategies as st
from scripts.tests import test_runner_failures as failures


def watch(
    start_tick: int, *, finish_tick: int | None = None
) -> tuple[list[float], Mock, Fraction]:
    """Each tick is one polling interval in seconds; no child or signal is real."""
    now = Fraction(0)
    path = Mock()
    finished = Mock()
    observed: list[float] = []

    def wait(seconds: float) -> bool:
        nonlocal now
        now += Fraction(str(seconds))
        return finish_tick is not None and now >= Fraction(finish_tick, 20)

    path.is_file.side_effect = lambda: now >= Fraction(start_tick, 20)
    finished.wait.side_effect = wait
    with (
        patch(
            "scripts.tests.test_runner_failures.time.monotonic",
            side_effect=lambda: float(now),
        ),
        patch("scripts.tests.test_runner_failures.os.kill") as kill,
    ):
        failures.RunnerFailures()._interrupt_when_ready(
            path, 0.0, 30, finished, observed
        )
    return observed, kill, now


@given(st.integers(min_value=0, max_value=595))
@example(0)
@example(401)
@example(595)
def test_every_start_before_the_settle_margin_gets_an_interrupt(tick: int) -> None:
    observed, kill, now = watch(tick)
    assert observed == [float(Fraction(tick, 20))]
    kill.assert_called_once()
    assert kill.call_args.args == (os.getpid(), signal.SIGINT)
    assert now == Fraction(tick, 20) + Fraction(1, 5)


def test_absent_child_gets_no_signal_at_the_suite_deadline() -> None:
    observed, kill, now = watch(600)
    assert observed == []
    kill.assert_not_called()
    assert now == 30


def test_finished_runner_stops_polling_without_a_late_signal() -> None:
    observed, kill, now = watch(21, finish_tick=20)
    assert observed == []
    kill.assert_not_called()
    assert now == 1


def test_finished_runner_during_settle_gets_no_late_signal() -> None:
    observed, kill, now = watch(20, finish_tick=21)
    assert observed == [1.0]
    kill.assert_not_called()
    assert now == Fraction(6, 5)


def test_start_at_the_last_poll_still_respects_runner_completion() -> None:
    observed, kill, now = watch(599, finish_tick=600)
    assert observed == [29.95]
    kill.assert_not_called()
    assert now == Fraction(603, 20)
