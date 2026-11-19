"""The per-op transport: one process per op (RPP v0's calling convention).

``<script> <op> <args...>``: op data on stdin, the answer on stdout, a
failure's message on stderr as ``"<op>: <message>"``, and the exit code from
the RPP table. :func:`run_per_op` builds the op's :class:`~.ops.OpRequest`,
runs its handler, and maps every way a handler can end onto an exit code and
a redacted stderr line. Nothing reaches stdout unless the op succeeded within
its cap.

An op's pipes break only once the gc process that ran it has exited: a live
gc never closes them while the op runs (its buffer takes every write, and on
cancel it sends SIGTERM, then SIGKILL, before it closes them). An op whose
stdout reader has gone ends with exit 1 and prints nothing more, however its
handler ends, even when the handler swallows the failed write; an op whose
stderr reader has gone keeps its exit code. Either way the broken stream is
pointed at ``/dev/null``, so Python's own flush at interpreter shutdown cannot
fail again and turn the exit code into 120.

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
from typing import BinaryIO, Final, List, Mapping, Optional, Sequence, TextIO, Tuple, Union

from .cancel import POLL_INTERVAL_S, CancelToken, Cancelled, Clock, Deadline
from .exitcodes import ExitCode
from .ops import OpError, OpRequest, OpResult, OpTable, deadline_for
from .redact import Redactor

DEADLINE_ENV: Final = "GC_EXEC_DEADLINE_MS"
"""Milliseconds left before gc stops waiting for the op, when gc says so. gc
sends it (gastownhall/gascity#9012); without it the op has gc's own timeout."""

OPLOG_ENV: Final = "GC_HC_TEST_OPLOG"
"""Test-only: a file each op appends one line to (:func:`append_oplog`),
honoured only under ``GC_HC_TEST=1`` (:func:`oplog_path`)."""
TEST_ENV: Final = "GC_HC_TEST"
DRIVING_OPS: Final = frozenset({"nudge", "send-keys", "interrupt", "clear-scrollback"})
"""The ops whose answer carries an input outcome word (:mod:`.outcome`)."""

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


def oplog_path(env: Mapping[str, str]) -> Optional[str]:
    """The op log a test run asked for: :data:`OPLOG_ENV`, an absolute path,
    only under ``GC_HC_TEST=1``; None otherwise."""
    if env.get(TEST_ENV) != "1":
        return None
    path = env.get(OPLOG_ENV, "")
    return path if os.path.isabs(path) else None


def _outcome_word(op: str, code: int, answer: bytes) -> str:
    """A driving op's outcome word: ``delivered`` or the word its answer
    names; empty for every other op and for an answer without one."""
    if op not in DRIVING_OPS:
        return ""
    if code == int(ExitCode.OK) and not answer.strip():
        return "delivered"
    if code not in (int(ExitCode.OK), int(ExitCode.INPUT_OUTCOME)):
        return ""
    from .jsonval import JsonObject, JsonShapeError, loads

    try:
        word = JsonObject.of(loads(answer)).str_or("outcome", "")
    except JsonShapeError:
        return ""
    return word if word.isidentifier() else ""


def append_oplog(path: str, argv: Sequence[str], code: int, answer: bytes, *, begun_ms: int, ended_ms: int) -> None:
    """Append one line to the test op log: the op, its first argument (the
    session; empty for an op without one), its exit code, a driving op's
    outcome word, and when it began and ended. Never stdin, stdout, a later
    argument or an environment value. A log that cannot be written is
    skipped: it is a test aid, never a reason to fail an op."""
    from .jsonval import dumps

    op = argv[1] if len(argv) > 1 else ""
    line = dumps(
        {
            "op": op,
            "session": argv[2] if len(argv) > 2 else "",
            "exit": code,
            "outcome": _outcome_word(op, code, answer),
            "begun_ms": begun_ms,
            "ended_ms": ended_ms,
        }
    )
    data = (line + "\n").encode("utf-8", "surrogateescape")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    except OSError:
        return
    try:
        os.write(fd, data)  # one write of one short line: appends never interleave
    except OSError:
        pass
    finally:
        os.close(fd)


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


class _ReaderGone(Exception):
    """The op's stdout reader has gone: the gc that ran it has exited.

    A handler can catch this, so the runner does not rely on it propagating:
    once a write fails, every later emit raises it again and the op exits 1
    whatever its handler returns.
    """


def _discard(stream: Union[BinaryIO, TextIO]) -> None:
    """Point the file descriptor under ``stream`` at ``/dev/null``.

    Called once its reader has gone: what the stream still buffers then
    flushes into ``/dev/null`` at interpreter shutdown instead of failing
    there, which would make the process exit 120. A stream with no
    descriptor (an in-memory one) is left alone.
    """
    try:
        fd = stream.fileno()
    except (OSError, ValueError):  # io.UnsupportedOperation is both
        return
    try:
        null = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return
    try:
        os.dup2(null, fd)
    except OSError:
        pass  # fd is out of range: no descriptor there to flush to at shutdown
    finally:
        # A closed fd lets open() reuse its number: null is then the stream's
        # own descriptor, already on /dev/null, and stays open.
        if null != fd:
            os.close(null)


def _emit(stderr: TextIO, text: str) -> None:
    try:
        stderr.write(text if text.endswith("\n") else text + "\n")
        stderr.flush()
    except OSError:
        _discard(stderr)  # stderr is gone: there is nowhere left to report to


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
    oplog: Optional[str] = None,
) -> int:
    """Run the op ``argv`` names and return its exit code.

    ``started`` is when the process began (the op's deadline counts from it);
    ``debug`` adds a redacted traceback to unexpected failures; ``oplog``
    (tests only, :func:`oplog_path`) names a file each op appends one line
    to (:func:`append_oplog`).
    """
    begun_ms = int(time.time() * 1000)
    code, answer = _run_per_op(
        argv,
        environ,
        ops,
        started=started,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        debug=debug,
        install_signals=install_signals,
        clock=clock,
    )
    if oplog:
        append_oplog(oplog, argv, code, answer, begun_ms=begun_ms, ended_ms=int(time.time() * 1000))
    return code


def _run_per_op(
    argv: Sequence[str],
    environ: Mapping[str, str],
    ops: OpTable,
    *,
    started: float,
    stdin: BinaryIO,
    stdout: BinaryIO,
    stderr: TextIO,
    debug: bool,
    install_signals: bool,
    clock: Clock,
) -> Tuple[int, bytes]:
    """:func:`run_per_op`'s work: the exit code, and the stdout the op answered."""
    env = dict(environ)
    redactor = Redactor()
    redactor.add_process_env(env)
    if len(argv) < 2 or not argv[1]:
        program = os.path.basename(argv[0]) if argv else "runtime"
        _emit(stderr, f"usage: {program} <op> [args...]")
        return int(ExitCode.UNKNOWN_OP), b""
    op = argv[1]
    spec = ops.get(op)
    if spec is None:
        _emit(stderr, redactor.redact(f"{op}: unknown operation"))
        return int(ExitCode.UNKNOWN_OP), b""

    gone = False  # stdout's reader has gone; set once, read after the handler

    def emit(data: bytes) -> None:
        nonlocal gone
        if gone:
            raise _ReaderGone()
        try:
            stdout.write(data)
            stdout.flush()
        except OSError:  # the gc that ran the op has exited (BrokenPipeError and kin)
            gone = True
            _discard(stdout)
            raise _ReaderGone() from None

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
            emit=emit,
        )
        # gc may have canceled, or given up waiting, while the op read stdin or started up.
        cancel.check()
        if deadline.expired():
            raise OpError("no time left before the op's deadline")
        result = spec.handler(request)
    except _ReaderGone:
        return int(ExitCode.FAIL), b""
    except OpError as err:
        result = OpResult.fail(err.message, err.code)
    except Cancelled as err:
        result = OpResult.fail(str(err))
    except KeyboardInterrupt:
        result = OpResult.fail("canceled (interrupted)")
    except Exception as err:  # the op boundary: every failure becomes exit 1
        result = OpResult.fail(f"internal error: {type(err).__name__}: {err}")
        if debug:
            import traceback

            trace = traceback.format_exc()

    if gone:  # the handler swallowed _ReaderGone: nobody is left to read its answer
        return int(ExitCode.FAIL), b""
    if len(result.stdout) > spec.stdout_cap:
        result = OpResult.fail(f"answer of {len(result.stdout)} bytes is over the {spec.stdout_cap}-byte cap")
    if result.stdout:
        try:
            stdout.write(result.stdout)
            stdout.flush()
        except OSError:  # the gc that ran the op has exited (BrokenPipeError and kin)
            _discard(stdout)
            return int(ExitCode.FAIL), b""
    if result.message:
        _emit(stderr, redactor.redact(f"{op}: {result.message}"))
    if trace:
        _emit(stderr, redactor.redact(trace))
    return int(result.code), result.stdout
