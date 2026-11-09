"""The per-op transport: one process per op (RPP v0's calling convention).

``<script> <op> <args...>``: op data on stdin, the answer on stdout, a
failure's message on stderr as ``"<op>: <message>"``, and the exit code from
the RPP table. :func:`run_per_op` builds the op's :class:`~.ops.OpRequest`,
runs its handler, and maps every way a handler can end onto an exit code and
a redacted stderr line. Nothing reaches stdout unless the op succeeded within
its cap.

Reading stdin waits in :data:`~.cancel.POLL_INTERVAL_S` steps, so a SIGTERM
or the op's deadline ends it, and no handler starts once its op is canceled
or out of time.
"""

from __future__ import annotations

import io
import os
import re
import select
import signal
import time
import traceback
from typing import BinaryIO, Final, List, Mapping, Optional, Sequence, TextIO

from .cancel import POLL_INTERVAL_S, CancelToken, Cancelled, Clock, Deadline
from .exitcodes import ExitCode
from .ops import OpError, OpRequest, OpResult, OpTable, deadline_for
from .redact import Redactor

DEADLINE_ENV: Final = "GC_EXEC_DEADLINE_MS"
"""Milliseconds left before gc stops waiting for the op, when gc says so. No
gc release sends it yet; the op then has gc's own timeout for it."""

_DEADLINE_MS: Final = re.compile(r"[0-9]{1,12}")
_STDIN_CHUNK: Final = 1 << 16


def parse_deadline_ms(raw: Optional[str]) -> Optional[int]:
    """``GC_EXEC_DEADLINE_MS`` as milliseconds; None when absent or malformed.

    A malformed value reads as absent: the op then keeps gc's own per-op
    timeout, exactly as under a gc that predates the variable.
    """
    if raw is None or _DEADLINE_MS.fullmatch(raw) is None:
        return None
    return int(raw)


def _install_sigterm(cancel: CancelToken) -> None:
    # gc cancels with SIGTERM to the op's process group, then SIGKILL 2 s
    # later. The handler only sets the flag; the op's waits poll it.
    def on_sigterm(signum: int, frame: object) -> None:
        cancel.cancel("terminated")

    previous: object = signal.signal(signal.SIGTERM, on_sigterm)
    del previous


def _read_stdin(stdin: BinaryIO, cancel: CancelToken, deadline: Deadline) -> bytes:
    """All of stdin. A blocking read would sit out a SIGTERM and the deadline
    alike, so each wait is a poll interval long, and stdin still open within
    the deadline margin fails the op."""
    try:
        fd = stdin.fileno()
    except io.UnsupportedOperation:  # an in-memory stream never blocks
        return stdin.read()
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    chunks: List[bytes] = []
    while True:
        cancel.check()
        timeout = deadline.budget(POLL_INTERVAL_S)
        if timeout <= 0:
            raise OpError("stdin was still open at the op's deadline")
        if poller.poll(timeout * 1000.0):
            chunk = os.read(fd, _STDIN_CHUNK)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)


def _emit(stderr: TextIO, text: str) -> None:
    try:
        stderr.write(text if text.endswith("\n") else text + "\n")
        stderr.flush()
    except OSError:
        pass  # stderr is gone: there is nowhere left to report to


def run_per_op(
    argv: Sequence[str],
    environ: Mapping[str, str],
    ops: OpTable,
    *,
    started: float,
    stdin: BinaryIO,
    stdout: BinaryIO,
    stderr: TextIO,
    debug: bool = False,
    install_signals: bool = True,
    clock: Clock = time.monotonic,
) -> int:
    """Run the op ``argv`` names and return its exit code.

    ``started`` is when the process began (the op's deadline counts from it);
    ``debug`` adds a redacted traceback to unexpected failures.
    """
    env = dict(environ)
    redactor = Redactor()
    redactor.add_process_env(env)
    if len(argv) < 2 or not argv[1]:
        program = os.path.basename(argv[0]) if argv else "runtime"
        _emit(stderr, f"usage: {program} <op> [args...]")
        return int(ExitCode.UNKNOWN_OP)
    op = argv[1]
    spec = ops.get(op)
    if spec is None:
        _emit(stderr, redactor.redact(f"{op}: unknown operation"))
        return int(ExitCode.UNKNOWN_OP)

    cancel = CancelToken()
    if install_signals:
        _install_sigterm(cancel)
    deadline = deadline_for(spec.deadline, parse_deadline_ms(env.get(DEADLINE_ENV)), start=started, clock=clock)
    trace = ""
    try:
        request = OpRequest(
            op=op,
            args=tuple(argv[2:]),
            stdin=_read_stdin(stdin, cancel, deadline) if spec.reads_stdin else b"",
            env=env,
            cancel=cancel,
            deadline=deadline,
            redactor=redactor,
        )
        # gc may have canceled, or given up waiting, while the op read stdin or started up.
        cancel.check()
        if deadline.expired():
            raise OpError("no time left before the op's deadline")
        result = spec.handler(request)
    except OpError as err:
        result = OpResult.fail(err.message, err.code)
    except Cancelled as err:
        result = OpResult.fail(str(err))
    except KeyboardInterrupt:
        result = OpResult.fail("canceled (interrupted)")
    except Exception as err:  # the op boundary: every failure becomes exit 1
        result = OpResult.fail(f"internal error: {type(err).__name__}: {err}")
        if debug:
            trace = traceback.format_exc()

    if len(result.stdout) > spec.stdout_cap:
        result = OpResult.fail(f"answer of {len(result.stdout)} bytes is over the {spec.stdout_cap}-byte cap")
    if result.stdout:
        try:
            stdout.write(result.stdout)
            stdout.flush()
        except OSError:  # gc stopped reading (BrokenPipeError and kin)
            return int(ExitCode.FAIL)
    if result.message:
        _emit(stderr, redactor.redact(f"{op}: {result.message}"))
    if trace:
        _emit(stderr, redactor.redact(trace))
    return int(result.code)
