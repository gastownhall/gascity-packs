"""The per-op runner: argv + env -> OpRequest -> handler -> exit code."""

from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Mapping, Optional

import pytest

from gc_runtime_herdr_core.rpp.exitcodes import ExitCode
from gc_runtime_herdr_core.rpp.ops import Handler, OpError, OpRequest, OpResult, OpSpec, OpTable, handshake_op
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
