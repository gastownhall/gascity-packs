"""The per-op runner: argv + env -> OpRequest -> handler -> exit code."""

from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

import pytest

from gc_runtime_herdr_core.rpp.exitcodes import ExitCode
from gc_runtime_herdr_core.rpp.ops import Handler, OpError, OpRequest, OpResult, OpSpec, OpTable, handshake_op
from gc_runtime_herdr_core.rpp import perop
from gc_runtime_herdr_core.rpp.perop import parse_deadline_ms, run_per_op
from gc_runtime_herdr_core.rpp.wire import Handshake

ASSETS = Path(__file__).resolve().parents[2] / "assets"


class Run:
    def __init__(self, code: int, stdout: bytes, stderr: str, stdin_pos: int) -> None:
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.stdin_pos = stdin_pos


def run(
    ops: OpTable,
    *argv: str,
    env: Optional[Mapping[str, str]] = None,
    stdin: bytes = b"",
    debug: bool = False,
) -> Run:
    stdin_io = io.BytesIO(stdin)
    stdout_io = io.BytesIO()
    stderr_io = io.StringIO()
    code = run_per_op(
        ["gc-runtime-herdr-core", *argv],
        dict(env or {}),
        ops,
        started=time.monotonic(),
        stdin=stdin_io,
        stdout=stdout_io,
        stderr=stderr_io,
        debug=debug,
        install_signals=False,
    )
    return Run(code, stdout_io.getvalue(), stderr_io.getvalue(), stdin_io.tell())


def spec(handler: Handler, *, reads_stdin: bool = False, deadline: str = "default", cap: int = 1 << 16) -> OpSpec:
    return OpSpec(handler=handler, reads_stdin=reads_stdin, deadline=deadline, stdout_cap=cap)  # type: ignore[arg-type]


def test_protocol_answers_the_static_handshake() -> None:
    ops = {"protocol": handshake_op(Handshake(capabilities=(), locality="local"))}
    result = run(ops, "protocol")
    assert result.code == 0
    assert result.stdout == b'{"version":0,"capabilities":[],"locality":"local"}\n'
    assert result.stderr == ""


@pytest.mark.parametrize("op", ["exec", "provision", "check-image", "frobnicate", "start"])
def test_an_op_outside_the_table_exits_2_without_reading_stdin(op: str) -> None:
    result = run({}, op, "mc-mayor", stdin=b"tmux send-keys -t main 'rm -rf ~' Enter\n")
    assert result.code == ExitCode.UNKNOWN_OP
    assert result.stdin_pos == 0
    assert result.stdout == b""
    assert result.stderr.startswith(f"{op}: ")


def test_no_op_is_a_usage_error_with_exit_2() -> None:
    result = run({})
    assert result.code == ExitCode.UNKNOWN_OP
    assert "usage" in result.stderr


def test_stdin_is_read_only_for_ops_that_take_it() -> None:
    seen: List[bytes] = []

    def handler(req: OpRequest) -> OpResult:
        seen.append(req.stdin)
        return OpResult.ok()

    assert run({"nudge": spec(handler, reads_stdin=True)}, "nudge", "mc-a", stdin=b"hi").code == 0
    assert run({"stop": spec(handler)}, "stop", "mc-a", stdin=b"ignored").stdin_pos == 0
    assert seen == [b"hi", b""]


def run_on_pipe(handler: Handler, read_end: int, env: Optional[Mapping[str, str]] = None) -> Tuple[int, str]:
    """An op that takes stdin, run with stdin on ``read_end``: its exit code and stderr."""
    stderr = io.StringIO()
    with os.fdopen(read_end, "rb") as stdin:
        code = run_per_op(
            ["gc-runtime-herdr-core", "nudge"],
            dict(env or {}),
            {"nudge": spec(handler, reads_stdin=True)},
            started=time.monotonic(),
            stdin=stdin,
            stdout=io.BytesIO(),
            stderr=stderr,
            install_signals=False,
        )
    return code, stderr.getvalue()


def test_stdin_from_a_pipe_is_read_to_its_end() -> None:
    seen: List[bytes] = []

    def handler(req: OpRequest) -> OpResult:
        seen.append(req.stdin)
        return OpResult.ok()

    payload = bytes(range(256)) * 1024  # several pipe buffers, several reads
    read_end, write_end = os.pipe()

    def feed() -> None:
        with os.fdopen(write_end, "wb") as pipe:
            pipe.write(payload)

    writer = threading.Thread(target=feed)
    writer.start()
    code, _ = run_on_pipe(handler, read_end)
    writer.join()
    assert code == 0
    assert seen == [payload]


def test_stdin_still_open_at_the_deadline_fails_the_op_unrun() -> None:
    seen: List[bytes] = []

    def handler(req: OpRequest) -> OpResult:
        seen.append(req.stdin)
        return OpResult.ok()

    read_end, write_end = os.pipe()
    writer = os.fdopen(write_end, "wb")  # held open: no EOF ever comes
    backstop = threading.Timer(5.0, writer.close)  # ends a read that ignores the deadline
    backstop.start()
    begun = time.monotonic()
    try:
        code, stderr = run_on_pipe(handler, read_end, env={"GC_EXEC_DEADLINE_MS": "1500"})
    finally:
        backstop.cancel()
        writer.close()
    assert time.monotonic() - begun < 1.0  # the read gives up 1 s before the deadline
    assert code == ExitCode.FAIL
    assert seen == []
    assert stderr == "nudge: stdin was still open at the op's deadline\n"


def test_an_op_out_of_time_before_its_handler_fails_unrun() -> None:
    seen: List[str] = []

    def handler(req: OpRequest) -> OpResult:
        seen.append(req.op)
        return OpResult.ok()

    result = run({"stop": spec(handler)}, "stop", "mc-a", env={"GC_EXEC_DEADLINE_MS": "0"})
    assert result.code == ExitCode.FAIL
    assert seen == []
    assert result.stderr == "stop: no time left before the op's deadline\n"


def test_handlers_see_args_and_an_env_snapshot() -> None:
    seen: Dict[str, object] = {}

    def handler(req: OpRequest) -> OpResult:
        seen["op"] = req.op
        seen["args"] = req.args
        seen["env"] = dict(req.env)
        return OpResult.answer("true")

    result = run({"is-running": spec(handler)}, "is-running", "mc-a", env={"GC_EXEC_CITY_PATH": "/c"})
    assert result.stdout == b"true\n"
    assert seen == {"op": "is-running", "args": ("mc-a",), "env": {"GC_EXEC_CITY_PATH": "/c"}}


def test_op_errors_become_prefixed_stderr_and_their_exit_code() -> None:
    def handler(req: OpRequest) -> OpResult:
        raise OpError("no screen for mc-a", code=ExitCode.NO_SCREEN)

    result = run({"peek": spec(handler)}, "peek", "mc-a", "50")
    assert result.code == 66
    assert result.stderr == "peek: no screen for mc-a\n"
    assert result.stdout == b""


def test_failures_are_redacted_with_the_op_environment() -> None:
    def handler(req: OpRequest) -> OpResult:
        return OpResult.fail(f"backend said {req.env['ANTHROPIC_API_KEY']}")

    result = run({"stop": spec(handler)}, "stop", "mc-a", env={"ANTHROPIC_API_KEY": "sk-ant-12345"})
    assert result.code == 1
    assert "sk-ant-12345" not in result.stderr
    assert result.stderr == "stop: backend said [REDACTED]\n"


def test_handlers_can_register_start_env_secrets() -> None:
    def handler(req: OpRequest) -> OpResult:
        req.redactor.add_start_env({"GC_INSTANCE_TOKEN": "tok-abcdef-123", "GC_AGENT": "worker-12"})
        raise OpError("could not seed tok-abcdef-123 for worker-12")

    result = run({"start": spec(handler, reads_stdin=True)}, "start", "mc-a")
    assert "tok-abcdef-123" not in result.stderr
    assert "worker-12" not in result.stderr


def test_unexpected_exceptions_fail_without_a_traceback() -> None:
    def handler(req: OpRequest) -> OpResult:
        raise ValueError("boom sk-ant-777777")

    result = run({"stop": spec(handler)}, "stop", "mc-a", env={"MY_API_KEY": "sk-ant-777777"})
    assert result.code == 1
    assert result.stderr == "stop: internal error: ValueError: boom [REDACTED]\n"


def test_debug_adds_a_redacted_traceback() -> None:
    def handler(req: OpRequest) -> OpResult:
        raise ValueError("boom sk-ant-777777")

    result = run({"stop": spec(handler)}, "stop", "mc-a", env={"MY_API_KEY": "sk-ant-777777"}, debug=True)
    assert "Traceback" in result.stderr
    assert "sk-ant-777777" not in result.stderr


def test_an_answer_over_the_ops_cap_fails_and_prints_nothing() -> None:
    def handler(req: OpRequest) -> OpResult:
        return OpResult.ok(b"x" * 101)

    result = run({"observe": spec(handler, cap=100)}, "observe", "mc-a")
    assert result.code == 1
    assert result.stdout == b""
    assert "100" in result.stderr


@pytest.mark.parametrize(
    ("deadline_class", "env", "expected"),
    [
        ("default", {}, 30.0),
        ("start", {}, 120.0),
        ("probe", {}, 4.0),
        ("default", {"GC_EXEC_DEADLINE_MS": "2500"}, 2.5),
        ("probe", {"GC_EXEC_DEADLINE_MS": "1200"}, 1.2),
        ("start", {"GC_EXEC_DEADLINE_MS": "not-a-number"}, 120.0),
        ("default", {"GC_EXEC_DEADLINE_MS": "-5"}, 30.0),
    ],
)
def test_the_op_deadline_comes_from_gc_or_the_ops_default(
    deadline_class: str, env: Dict[str, str], expected: float
) -> None:
    seen: List[float] = []

    def handler(req: OpRequest) -> OpResult:
        seen.append(req.deadline.remaining())
        return OpResult.ok()

    run({"op": spec(handler, deadline=deadline_class)}, "op", env=env)
    assert seen[0] == pytest.approx(expected, abs=0.25)


@pytest.mark.parametrize(
    ("raw", "parsed"),
    [(None, None), ("", None), ("0", 0), ("2500", 2500), (" 2500", None), ("2.5", None), ("-1", None), ("١٢", None)],
)
def test_parse_deadline_ms(raw: Optional[str], parsed: Optional[int]) -> None:
    assert parse_deadline_ms(raw) == parsed


class BrokenPipe(io.BytesIO):
    def write(self, data: bytes) -> int:  # type: ignore[override]
        raise BrokenPipeError()


def test_a_closed_stdout_is_a_quiet_failure() -> None:
    ops = {"protocol": handshake_op(Handshake(capabilities=(), locality=None))}
    code = run_per_op(
        ["x", "protocol"],
        {},
        ops,
        started=time.monotonic(),
        stdin=io.BytesIO(),
        stdout=BrokenPipe(),
        stderr=io.StringIO(),
        install_signals=False,
    )
    assert code == ExitCode.FAIL


def test_discard_keeps_dev_null_open_when_it_reuses_the_streams_closed_fd(monkeypatch: pytest.MonkeyPatch) -> None:
    # A stream whose descriptor is already closed: os.open hands /dev/null
    # that same number, which must stay open as the stream's descriptor.
    read_end, write_end = os.pipe()
    os.close(read_end)
    stream = os.fdopen(write_end, "wb", closefd=False)
    os.close(write_end)
    real_open = os.open

    def open_reusing(path: str, flags: int) -> int:
        null = real_open(path, flags)
        os.dup2(null, write_end)
        os.close(null)
        return write_end

    monkeypatch.setattr(os, "open", open_reusing)
    try:
        perop._discard(stream)
        assert os.fstat(write_end).st_rdev == os.stat(os.devnull).st_rdev
    finally:
        monkeypatch.undo()
        os.close(write_end)


class PipeThatBreaksOnce(io.BytesIO):
    """A stdout whose first write fails as a gone reader's does; later writes
    land, as they would once the runner points the descriptor at /dev/null."""

    def __init__(self) -> None:
        super().__init__()
        self.broken = False

    def write(self, data: bytes) -> int:  # type: ignore[override]
        if not self.broken:
            self.broken = True
            raise BrokenPipeError()
        return super().write(data)


def swallow_and_answer(req: OpRequest, raised: List[str]) -> OpResult:
    for _ in range(3):
        try:
            req.emit(b"screen\n")
        except Exception as err:
            raised.append(type(err).__name__)
    return OpResult.answer("{}")


def swallow_and_fail(req: OpRequest, raised: List[str]) -> OpResult:
    try:
        req.emit(b"screen\n")
    except Exception as err:
        raised.append(type(err).__name__)
    raise OpError("no session 'a'", ExitCode.NO_SCREEN)


@pytest.mark.parametrize("handler, emits", [(swallow_and_answer, 3), (swallow_and_fail, 1)])
def test_a_gone_reader_fails_the_op_even_when_its_handler_swallows_that(
    handler: Callable[[OpRequest, List[str]], OpResult], emits: int
) -> None:
    raised: List[str] = []
    stdout = PipeThatBreaksOnce()
    stderr = io.StringIO()
    code = run_per_op(
        ["x", "op"],
        {},
        {"op": spec(lambda req: handler(req, raised))},
        started=time.monotonic(),
        stdin=io.BytesIO(),
        stdout=stdout,
        stderr=stderr,
        install_signals=False,
    )
    assert code == ExitCode.FAIL
    # Every emit after the first failure fails too, though the stream behind
    # it would now take the write.
    assert raised == ["_ReaderGone"] * emits
    assert stdout.getvalue() == b""
    assert stderr.getvalue() == ""


HARNESS = """
import sys, time
sys.path.insert(0, sys.argv[1])
from gc_runtime_herdr_core.rpp.ops import OpResult, OpSpec
from gc_runtime_herdr_core.rpp.perop import run_per_op

def wait(req):
    print("ready", file=sys.stderr, flush=True)
    req.cancel.pause(30.0)
    return OpResult.ok()

ops = {"wait": OpSpec(handler=wait, reads_stdin=False, deadline="default", stdout_cap=1024)}
sys.exit(run_per_op(["x", "wait"], {}, ops, started=time.monotonic(), stdin=sys.stdin.buffer,
                    stdout=sys.stdout.buffer, stderr=sys.stderr))
"""


def test_sigterm_cancels_the_op_promptly() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-I", "-S", "-c", HARNESS, str(ASSETS)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert proc.stderr is not None
        assert proc.stderr.readline() == b"ready\n"
        started = time.monotonic()
        os.kill(proc.pid, signal.SIGTERM)
        _, err = proc.communicate(timeout=5)
        assert time.monotonic() - started < 1.5
        assert proc.returncode == ExitCode.FAIL
        assert err.decode().strip() == "wait: canceled (terminated)"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


STDIN_HARNESS = """
import io, os, signal, sys, time
sys.path.insert(0, sys.argv[1])
from gc_runtime_herdr_core.rpp.ops import OpResult, OpSpec
from gc_runtime_herdr_core.rpp.perop import run_per_op

class Announced:
    # stdin, saying on stderr when the runner starts on it
    def __init__(self, raw):
        self.raw = raw
    def fileno(self):
        print("reading", file=sys.stderr, flush=True)
        return self.raw.fileno()
    def read(self, *size):
        print("reading", file=sys.stderr, flush=True)
        return self.raw.read(*size)

class TermAtEof(io.BytesIO):
    # stdin that ends just as gc sends SIGTERM
    def read(self, *size):
        data = io.BytesIO.read(self, *size)
        os.kill(os.getpid(), signal.SIGTERM)
        return data

def nudge(req):
    print("handler called", flush=True)
    return OpResult.ok()

stdin = Announced(sys.stdin.buffer) if sys.argv[2] == "held" else TermAtEof(b"hi")
ops = {"nudge": OpSpec(handler=nudge, reads_stdin=True, deadline="default", stdout_cap=1024)}
sys.exit(run_per_op(["x", "nudge"], {}, ops, started=time.monotonic(), stdin=stdin,
                    stdout=sys.stdout.buffer, stderr=sys.stderr))
"""


def test_sigterm_ends_a_stdin_read_and_the_op_never_runs() -> None:
    read_end, write_end = os.pipe()
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", STDIN_HARNESS, str(ASSETS), "held"],
            stdin=read_end,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    finally:
        os.close(read_end)
    try:
        assert proc.stderr is not None
        assert proc.stderr.readline() == b"reading\n"
        started = time.monotonic()
        os.kill(proc.pid, signal.SIGTERM)
        out, err = proc.communicate(timeout=5)  # stdin stays open: only the signal ends the read
        assert time.monotonic() - started < 1.5
        assert proc.returncode == ExitCode.FAIL
        assert out == b""
        assert err.decode().strip() == "nudge: canceled (terminated)"
    finally:
        os.close(write_end)
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_a_sigterm_as_stdin_ends_stops_the_op_before_its_handler() -> None:
    proc = subprocess.run(
        [sys.executable, "-I", "-S", "-c", STDIN_HARNESS, str(ASSETS), "term-at-eof"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
        start_new_session=True,
    )
    assert proc.returncode == ExitCode.FAIL
    assert proc.stdout == b""
    assert proc.stderr.decode().strip() == "nudge: canceled (terminated)"


GONE_HARNESS = """
import sys, time
sys.path.insert(0, sys.argv[1])
from gc_runtime_herdr_core.rpp.exitcodes import ExitCode
from gc_runtime_herdr_core.rpp.ops import OpError, OpResult, OpSpec
from gc_runtime_herdr_core.rpp.perop import run_per_op

def answer(req):
    return OpResult.answer("{}")

def outcome(req):
    return OpResult(ExitCode.INPUT_OUTCOME, b'{"outcome":"not-delivered"}\\n')

def stream(req):
    for _ in range(3):
        req.emit(b'{"content":"screen"}\\n')
    return OpResult.ok()

def fail(req):
    raise OpError("no session 'a'")

def outcome_with_message(req):
    return OpResult(ExitCode.INPUT_OUTCOME, b'{"outcome":"not-delivered"}\\n', "the program is waiting on its own question")

def warn(req):
    return OpResult(ExitCode.OK, b"", "could not record the start time")

def swallow(req):
    for _ in range(3):
        try:
            req.emit(b'{"content":"screen"}\\n')
        except Exception:
            pass
    return OpResult.answer("{}")

def spec(handler):
    return OpSpec(handler=handler, reads_stdin=False, deadline="default", stdout_cap=1024)

ops = {name: spec(handler) for name, handler in [
    ("answer", answer), ("outcome", outcome), ("stream", stream), ("fail", fail),
    ("outcome_with_message", outcome_with_message), ("warn", warn), ("swallow", swallow),
]}
sys.exit(run_per_op(["x", sys.argv[2]], {}, ops, started=time.monotonic(), stdin=sys.stdin.buffer,
                    stdout=sys.stdout.buffer, stderr=sys.stderr))
"""
"""Ops that answer on stdout every way an op can, one that swallows its gone
reader, and ones that end with a message on stderr."""


def run_without_reader(argv: List[str], gone: str) -> Tuple[int, str]:
    """Run ``argv`` with the read end of its ``gone`` stream (``stdout`` or
    ``stderr``) closed before the op starts, as when gc has already exited;
    return the exit status and what the other stream carried."""
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        proc = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=write_end if gone == "stdout" else subprocess.PIPE,
            stderr=write_end if gone == "stderr" else subprocess.PIPE,
            timeout=10,
            start_new_session=True,
        )
    finally:
        os.close(write_end)
    other = proc.stderr if gone == "stdout" else proc.stdout
    return proc.returncode, (other or b"").decode()


@pytest.mark.parametrize("op", ["answer", "outcome", "stream", "swallow"])
def test_an_op_whose_caller_has_gone_exits_1_quietly(op: str) -> None:
    # Python flushes stdout again at interpreter shutdown; a second
    # BrokenPipeError there turns exit 1 into 120 and prints a traceback.
    code, err = run_without_reader([sys.executable, "-I", "-S", "-c", GONE_HARNESS, str(ASSETS), op], "stdout")
    assert code == ExitCode.FAIL
    assert err == ""


@pytest.mark.parametrize(
    "op, exit_code, answer",
    [
        ("fail", ExitCode.FAIL, ""),
        ("outcome_with_message", ExitCode.INPUT_OUTCOME, '{"outcome":"not-delivered"}\n'),
        ("warn", ExitCode.OK, ""),
    ],
)
def test_an_op_whose_stderr_reader_has_gone_keeps_its_exit_code(op: str, exit_code: int, answer: str) -> None:
    code, out = run_without_reader([sys.executable, "-I", "-S", "-c", GONE_HARNESS, str(ASSETS), op], "stderr")
    assert code == exit_code
    assert out == answer


def test_the_executable_exits_1_when_gc_has_stopped_reading() -> None:
    entry = ASSETS / "bin" / "gc-runtime-herdr-core"
    code, err = run_without_reader([sys.executable, "-I", "-S", str(entry), "protocol"], "stdout")
    assert code == ExitCode.FAIL
    assert err == ""


# --- the test-only op log ----------------------------------------------------------------------


def test_the_op_log_is_honoured_only_under_test_mode(tmp_path: Path) -> None:
    log = str(tmp_path / "ops.log")
    assert perop.oplog_path({"GC_HC_TEST_OPLOG": log}) is None
    assert perop.oplog_path({"GC_HC_TEST": "0", "GC_HC_TEST_OPLOG": log}) is None
    assert perop.oplog_path({"GC_HC_TEST": "1", "GC_HC_TEST_OPLOG": "relative.log"}) is None
    assert perop.oplog_path({"GC_HC_TEST": "1", "GC_HC_TEST_OPLOG": log}) == log
    assert perop.oplog_path({"GC_HC_TEST": "1"}) is None


def test_the_op_log_records_op_session_exit_and_outcome_only(tmp_path: Path) -> None:
    import json

    canary = "sk-oplog-canary-0123456789"
    refused = b'{"outcome":"pending_interaction","detail":"a dialog shows"}\n'

    def nudge(request: OpRequest) -> OpResult:
        if request.stdin == b"refuse":
            return OpResult(ExitCode.INPUT_OUTCOME, refused)
        return OpResult.ok()

    def start(request: OpRequest) -> OpResult:
        return OpResult(ExitCode.FRESH_COLLISION, b"", f"already exists {canary}")

    table: OpTable = {"nudge": spec(nudge, reads_stdin=True), "start": spec(start, reads_stdin=True)}
    log = tmp_path / "ops.log"

    def logged(*argv: str, stdin: bytes) -> int:
        return run_per_op(
            ["gc-runtime-herdr-core", *argv],
            {"SECRET_TOKEN": canary},
            table,
            started=time.monotonic(),
            stdin=io.BytesIO(stdin),
            stdout=io.BytesIO(),
            stderr=io.StringIO(),
            install_signals=False,
            oplog=str(log),
        )

    assert logged("nudge", "mc-a", stdin=canary.encode()) == 0
    assert logged("nudge", "mc-a", stdin=b"refuse") == 80
    assert logged("start", "mc-b", "extra-arg", stdin=json.dumps({"env": {"K": canary}}).encode()) == 73
    assert logged("frobnicate", stdin=b"") == 2
    text = log.read_text()
    assert canary not in text and "extra-arg" not in text and "a dialog shows" not in text
    lines = [json.loads(line) for line in text.splitlines()]
    assert [(d["op"], d["session"], d["exit"], d["outcome"]) for d in lines] == [
        ("nudge", "mc-a", 0, "delivered"),
        ("nudge", "mc-a", 80, "pending_interaction"),
        ("start", "mc-b", 73, ""),
        ("frobnicate", "", 2, ""),
    ]
    assert all(d["begun_ms"] <= d["ended_ms"] for d in lines)
    assert set(lines[0]) == {"op", "session", "exit", "outcome", "begun_ms", "ended_ms"}
    assert oct(log.stat().st_mode & 0o777) == "0o600"


def test_without_an_op_log_nothing_is_written(tmp_path: Path) -> None:
    def ok(request: OpRequest) -> OpResult:
        return OpResult.ok()

    before = sorted(os.listdir(tmp_path))
    assert run({"stop": spec(ok)}, "stop", "mc-a", env={"GC_HC_TEST_OPLOG": str(tmp_path / "ops.log")}).code == 0
    assert sorted(os.listdir(tmp_path)) == before


def test_the_entry_logs_ops_under_test_mode_only(tmp_path: Path) -> None:
    import json

    entry = ASSETS / "bin" / "gc-runtime-herdr-core"
    log = tmp_path / "ops.log"
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GC_HC_TEST_OPLOG": str(log)}
    for env in (base, dict(base, GC_HC_TEST="1")):
        done = subprocess.run([sys.executable, "-I", "-S", str(entry), "frobnicate", "mc-a"], env=env, capture_output=True, timeout=30, check=False)
        assert done.returncode == 2
    [line] = log.read_text().splitlines()
    assert json.loads(line)["op"] == "frobnicate"
