"""Cancellation and op deadlines.

gc cancels a per-op process with SIGTERM to its process group and SIGKILL two
seconds later (gascity ``docs/reference/exec-session-provider.md``
"Cancellation"); a long-lived transport would cancel one request of many.
Either way the op learns of it through a :class:`CancelToken`. A token is a plain flag that waiters poll every
:data:`POLL_INTERVAL_S`: a signal handler can set it at any bytecode
boundary, where taking a lock (as ``threading.Event.set`` does) could
deadlock against the interrupted code.

A :class:`Deadline` is an op's absolute expiry: the time gc allows when it
says so (``GC_EXEC_DEADLINE_MS``), else gc's own timeout for the op. Every inner wait ends
:data:`DEADLINE_MARGIN_S` before it (:meth:`Deadline.budget`), so the pack
answers while gc is still listening.
"""

from __future__ import annotations

import time
from typing import Callable, Final, Optional

Clock = Callable[[], float]

POLL_INTERVAL_S: Final = 0.1
"""How often blocked waits look at their cancel token."""

DEADLINE_MARGIN_S: Final = 1.0
"""Inner budgets finish at least this long before the op's deadline."""


class Cancelled(Exception):
    """The op was canceled; whatever it answers no longer reaches gc."""

    def __init__(self, reason: str) -> None:
        Exception.__init__(self, f"canceled ({reason})")
        self.reason = reason


class CancelToken:
    """A one-way cancellation flag, safe to set from a signal handler."""

    def __init__(self) -> None:
        self._reason: Optional[str] = None

    def cancel(self, reason: str) -> None:
        """Cancel; the first reason given is kept."""
        if self._reason is None:
            self._reason = reason

    @property
    def cancelled(self) -> bool:
        """Whether the token has been canceled."""
        return self._reason is not None

    @property
    def reason(self) -> str:
        """Why the token was canceled ("" while it is not)."""
        return self._reason or ""

    def check(self) -> None:
        """Raise :class:`Cancelled` if the token has been canceled."""
        reason = self._reason
        if reason is not None:
            raise Cancelled(reason)

    def pause(self, seconds: float) -> None:
        """Sleep for ``seconds``, waking within a poll interval of a cancel."""
        end = time.monotonic() + seconds
        while True:
            self.check()
            left = end - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(POLL_INTERVAL_S, left))


class Deadline:
    """An op's absolute expiry on a monotonic clock."""

    def __init__(self, expires_at: float, clock: Clock = time.monotonic) -> None:
        self._expires_at = expires_at
        self._clock = clock

    @classmethod
    def after(cls, seconds: float, *, start: Optional[float] = None, clock: Clock = time.monotonic) -> Deadline:
        """The deadline ``seconds`` after ``start`` (default: now on ``clock``)."""
        origin = clock() if start is None else start
        return cls(origin + seconds, clock)

    def remaining(self) -> float:
        """Seconds left, never negative."""
        return max(0.0, self._expires_at - self._clock())

    def expired(self) -> bool:
        """Whether no time is left."""
        return self.remaining() <= 0.0

    def budget(self, cap: float, *, margin: float = DEADLINE_MARGIN_S) -> float:
        """An inner wait's timeout: ``cap``, cut to end ``margin`` before the deadline.

        Zero or less means the wait cannot fit and must not start.
        """
        return min(cap, self.remaining() - margin)
