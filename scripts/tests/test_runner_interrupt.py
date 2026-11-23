"""Virtual-clock boundary plants for the real interrupt fixture's watcher."""

from __future__ import annotations

import os
import re
import signal
import threading
import time
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import test_runner_failures as failures
from hypothesis import example, given
from hypothesis import strategies as st


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
    kill = Mock()
    with (
        patch.object(failures, "time", SimpleNamespace(monotonic=lambda: float(now))),
        patch.object(failures, "os", SimpleNamespace(kill=kill, getpid=os.getpid)),
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


def test_virtual_clock_leaves_process_modules_unchanged() -> None:
    original = [time.monotonic, os.kill]
    seen: list[object] = []
    with patch.object(
        failures.RunnerFailures,
        "_interrupt_when_ready",
        side_effect=lambda *_args: seen.extend((time.monotonic, os.kill)),
    ):
        watch(0)
    assert seen == original


def test_late_interrupt_is_a_named_failure_and_restores_sigint(
    tmp_path: Path,
) -> None:
    case = failures.RunnerFailures()
    case.root = tmp_path
    worker = Mock()
    worker.join.side_effect = KeyboardInterrupt
    threads = SimpleNamespace(Event=threading.Event, Thread=Mock(return_value=worker))
    message = (
        "SIGINT reached the test after the runner returned; "
        "child-start seconds=[]; suite limit=30 s"
    )
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        with (
            patch.object(failures, "threading", threads),
            patch.object(case, "_run", return_value=(1, ["FAIL interrupted"], [])),
            pytest.raises(AssertionError, match=f"^{re.escape(message)}$"),
        ):
            try:
                case.test_interrupt_kills_the_process_group()
            except KeyboardInterrupt:
                pytest.fail("late SIGINT escaped the fixture")
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, previous)
