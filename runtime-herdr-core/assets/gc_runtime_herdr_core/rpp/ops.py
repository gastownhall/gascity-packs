"""Ops: the request a handler sees, the result it returns, and the table that
names them.

The per-op runner (:mod:`.perop`) builds an :class:`OpRequest` from argv and
the process environment; a long-lived transport would build one from its own
request. Handlers read only their request, never ``os.environ``, so every
transport answers alike.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Final, Literal, Mapping, Optional, Tuple

from .cancel import CancelToken, Clock, Deadline
from .exitcodes import ExitCode
from .redact import Redactor
from .wire import Handshake

DeadlineClass = Literal["default", "start", "probe"]

DEFAULT_DEADLINES_S: Final[Mapping[DeadlineClass, float]] = {
    "default": 30.0,
    "start": 120.0,
    "probe": 4.0,
}
"""gc's own op timeouts, the deadline when gc sends no ``GC_EXEC_DEADLINE_MS``:
30 s per op and 120 s for start/provision (gc ``exec.NewProvider``), 4 s for
observe and a v2-ready is-attached (gc ``exec/observe.go`` probeOpTimeout)."""

SMALL_STDOUT_CAP: Final = 64 << 10
OBSERVE_STDOUT_CAP: Final = 1 << 20
INVENTORY_STDOUT_CAP: Final = 8 << 20
"""Stdout caps. gc fails an ``observe`` answer over 1 MiB and an ``inventory``
answer over 8 MiB (exec-session-provider.md "observe.v1"); other answers are a
line or two."""


@dataclass(frozen=True)
class OpRequest:
    """One op, as every transport hands it to its handler."""

    op: str
    args: Tuple[str, ...]
    stdin: bytes
    env: Mapping[str, str]
    cancel: CancelToken
    deadline: Deadline
    redactor: Redactor


@dataclass(frozen=True)
class OpResult:
    """How an op ended: exit code, stdout bytes, and a stderr message."""

    code: ExitCode
    stdout: bytes = b""
    message: str = ""

    @classmethod
    def ok(cls, stdout: bytes = b"") -> OpResult:
        return cls(ExitCode.OK, stdout)

    @classmethod
    def answer(cls, line: str) -> OpResult:
        """Exit 0 with one line of stdout."""
        return cls(ExitCode.OK, (line + "\n").encode("utf-8", "surrogateescape"))

    @classmethod
    def fail(cls, message: str, code: ExitCode = ExitCode.FAIL) -> OpResult:
        return cls(code, b"", message)


class OpError(Exception):
    """Raised anywhere under a handler to end the op with ``code`` and ``message``."""

    def __init__(self, message: str, code: ExitCode = ExitCode.FAIL) -> None:
        Exception.__init__(self, message)
        self.message = message
        self.code = code


Handler = Callable[[OpRequest], OpResult]


@dataclass(frozen=True)
class OpSpec:
    """An op's handler and the transport facts about it."""

    handler: Handler
    reads_stdin: bool
    """Only these ops read stdin; any other op leaves it untouched (an unread
    ``exec`` payload is never run)."""
    deadline: DeadlineClass
    stdout_cap: int


OpTable = Mapping[str, OpSpec]


def handshake_op(handshake: Handshake) -> OpSpec:
    """The ``protocol`` op: answers ``handshake``, reading nothing."""
    line = handshake.encode()

    def protocol(request: OpRequest) -> OpResult:
        return OpResult.answer(line)

    return OpSpec(handler=protocol, reads_stdin=False, deadline="default", stdout_cap=SMALL_STDOUT_CAP)


def deadline_for(
    deadline_class: DeadlineClass,
    deadline_ms: Optional[int],
    *,
    start: float,
    clock: Clock = time.monotonic,
) -> Deadline:
    """The op's deadline: what gc sent, else the class default, from ``start``."""
    seconds = DEFAULT_DEADLINES_S[deadline_class] if deadline_ms is None else deadline_ms / 1000.0
    return Deadline.after(seconds, start=start, clock=clock)
