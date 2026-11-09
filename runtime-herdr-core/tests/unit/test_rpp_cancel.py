"""Cancellation tokens, op deadlines and the inner-budget rule."""

from __future__ import annotations

import threading
import time

import pytest

from gc_runtime_herdr_core.rpp.cancel import DEADLINE_MARGIN_S, CancelToken, Cancelled, Deadline
from gc_runtime_herdr_core.rpp.ops import DEFAULT_DEADLINES_S, deadline_for


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_token_starts_clear() -> None:
    token = CancelToken()
    assert not token.cancelled
    assert token.reason == ""
    token.check()


def test_token_keeps_the_first_reason() -> None:
    token = CancelToken()
    token.cancel("terminated")
    token.cancel("second reason")
    assert token.cancelled
    assert token.reason == "terminated"
    with pytest.raises(Cancelled) as caught:
        token.check()
    assert caught.value.reason == "terminated"


def test_pause_sleeps_when_not_canceled() -> None:
    token = CancelToken()
    started = time.monotonic()
    token.pause(0.15)
    assert time.monotonic() - started >= 0.14


def test_pause_wakes_promptly_on_cancel_from_another_thread() -> None:
    token = CancelToken()
    threading.Timer(0.1, token.cancel, args=("canceled by the caller",)).start()
    started = time.monotonic()
    with pytest.raises(Cancelled):
        token.pause(10.0)
    assert time.monotonic() - started < 1.0


def test_deadline_counts_down_on_its_clock() -> None:
    clock = FakeClock()
    deadline = Deadline.after(2.5, clock=clock)
    assert deadline.remaining() == pytest.approx(2.5)
    clock.now += 2.0
    assert deadline.remaining() == pytest.approx(0.5)
    assert not deadline.expired()
    clock.now += 1.0
    assert deadline.remaining() == 0.0
    assert deadline.expired()


def test_deadline_measured_from_an_earlier_start() -> None:
    clock = FakeClock()
    started = clock.now
    clock.now += 0.4  # interpreter start-up spent before the runner saw the env
    deadline = Deadline.after(2.0, start=started, clock=clock)
    assert deadline.remaining() == pytest.approx(1.6)


def test_budget_is_the_table_value_capped_one_second_before_the_deadline() -> None:
    clock = FakeClock()
    deadline = Deadline.after(30.0, clock=clock)
    assert DEADLINE_MARGIN_S == 1.0
    assert deadline.budget(3.0) == pytest.approx(3.0)
    clock.now += 27.5  # 2.5 s left: an inner call gets at most 1.5 s
    assert deadline.budget(3.0) == pytest.approx(1.5)
    clock.now += 2.0  # 0.5 s left: no inner call fits
    assert deadline.budget(3.0) <= 0.0


def test_budget_honours_a_larger_reserve() -> None:
    clock = FakeClock()
    deadline = Deadline.after(10.0, clock=clock)
    assert deadline.budget(60.0, margin=2.0) == pytest.approx(8.0)


@pytest.mark.parametrize(
    ("deadline_class", "seconds"),
    [("default", 30.0), ("start", 120.0), ("probe", 4.0)],
)
def test_default_deadlines_mirror_gc_exec_timeouts(deadline_class: str, seconds: float) -> None:
    # exec.go NewProvider: 30 s per op, 120 s for start/provision;
    # exec/observe.go probeOpTimeout: 4 s for observe and a v2-ready is-attached.
    assert DEFAULT_DEADLINES_S[deadline_class] == seconds  # type: ignore[index]


def test_deadline_for_prefers_the_op_deadline_gc_sent() -> None:
    clock = FakeClock()
    deadline = deadline_for("default", 2500, start=clock.now, clock=clock)
    assert deadline.remaining() == pytest.approx(2.5)


def test_deadline_for_falls_back_to_the_class_default_without_one() -> None:
    clock = FakeClock()
    assert deadline_for("default", None, start=clock.now, clock=clock).remaining() == pytest.approx(30.0)
    assert deadline_for("start", None, start=clock.now, clock=clock).remaining() == pytest.approx(120.0)
    assert deadline_for("probe", None, start=clock.now, clock=clock).remaining() == pytest.approx(4.0)
