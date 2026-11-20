from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

import pytest

from soakagent import Decision, classify, decide, step_seconds, token16
from soaklib import NotOwned, ProcFS, Rec, read_jsonl, signal_owned

AGENT = Path(__file__).resolve().parents[1] / "bin" / "soak-agent"
BEACON = "[hc-soak] soak-burst-1 • 2026-11-17T10:00:00"
SECRET = "instance-token-must-never-be-logged"


def test_classify_input_lines() -> None:
    assert classify(BEACON) == {"beacon": True, "marker": False, "nonce": None}
    assert classify("SOAK-FIRST-TURN soak-burst") == {"beacon": False, "marker": True, "nonce": None}
    assert classify("SOAK-NUDGE " + "ab" * 16)["nonce"] == "ab" * 16


def test_step_seconds_are_deterministic_and_bounded() -> None:
    values = {step_seconds(f"gc-{i}") for i in range(500)}
    assert min(values) == 10 and max(values) == 30
    assert step_seconds("gc-42") == step_seconds("gc-42")


def test_token16_hides_the_token() -> None:
    assert len(token16(SECRET)) == 16 and SECRET not in token16(SECRET)
    assert token16("") == ""


@pytest.mark.parametrize(
    "result, code, sent, want",
    [
        ({"action": "work", "bead_id": "b1", "root_bead_id": "r1"}, 0, False, Decision("work", "", "b1", "r1")),
        ({"action": "drain", "reason": "no_work"}, 1, False, Decision("idle", "no_work")),
        ({"action": "drain", "reason": "claims_errored"}, 1, False, Decision("idle", "claims_errored")),
        ({"action": "drain", "reason": "drain_pending"}, 1, False, Decision("ack_drain", "drain_pending")),
        ({"action": "drain", "reason": "no_work", "drain_acknowledged": True}, 0, True, Decision("drained", "no_work")),
        ({"action": "drain", "reason": "no_work"}, 0, True, Decision("drained", "no_work")),
        ({"action": "drain", "reason": "no_work"}, 1, True, Decision("idle", "no_work")),
        ({"action": "none"}, 0, False, Decision("idle", "none")),
        (None, 2, False, Decision("error")),
        ({"ok": False}, 2, False, Decision("error")),
    ],
)
def test_decide(result: Optional[Rec], code: int, sent: bool, want: Decision) -> None:
    assert decide(result, code, sent) == want


FAKE_GC = """#!{python}
import json, os, sys
args = sys.argv[1:]
state = {state!r}
with open(state + ".calls", "a") as fh:
    fh.write(" ".join(args) + "\\n")
if args[:2] == ["hook", "--claim"]:
    n = int(open(state).read()) if os.path.exists(state) else 0
    open(state, "w").write(str(n + 1))
    if n == 0:
        print(json.dumps({{"action": "work", "bead_id": "gc-b1", "root_bead_id": "gc-r1"}}))
        sys.exit(0)
    if "--drain-ack" in args:
        print(json.dumps({{"action": "drain", "reason": "no_work", "drain_acknowledged": True}}))
        sys.exit(0)
    print(json.dumps({{"action": "drain", "reason": "no_work"}}))
    sys.exit(1)
if args[0] == "bd" and args[1] == "create":
    print(json.dumps({{"id": "gc-art1"}}))
    sys.exit(0)
if args[0] == "bd":
    sys.exit(0)
sys.exit(3)
"""


class Running:
    def __init__(self, proc: "subprocess.Popen[bytes]", log: Path) -> None:
        self.proc = proc
        self.log = log
        self.out = b""
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        while True:
            chunk = self.proc.stdout.read1(4096)  # type: ignore[attr-defined]
            if not chunk:
                return
            self.out += chunk

    def send(self, *lines: str) -> None:
        assert self.proc.stdin is not None
        for line in lines:
            self.proc.stdin.write(line.encode() + b"\n")
            self.proc.stdin.flush()

    def records(self) -> List[Rec]:
        return read_jsonl(self.log)

    def wait_for(self, pred: Callable[[List[Rec]], bool], timeout: float = 30.0) -> List[Rec]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            recs = self.records()
            if pred(recs):
                return recs
            time.sleep(0.05)
        raise AssertionError(f"timed out; records: {[r.get('ev') for r in self.records()]}; out: {self.out[-500:]!r}")


@pytest.fixture
def agent(tmp_path: Path) -> Iterator[Callable[..., Running]]:
    started: List[Running] = []

    def start(role: str = "burst") -> Running:
        gc = tmp_path / "gc"
        gc.write_text(FAKE_GC.format(python=sys.executable, state=str(tmp_path / "claims")), encoding="utf-8")
        gc.chmod(gc.stat().st_mode | stat.S_IXUSR)
        data = tmp_path / "data"
        env: Dict[str, str] = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp_path),
            "GC_SESSION_ID": "gc-s1",
            "GC_SESSION_NAME": "soak-burst-1",
            "GC_TEMPLATE": "soak-burst",
            "GC_INSTANCE_TOKEN": SECRET,
            "GC_CITY_PATH": str(tmp_path / "city"),
            "GC_BIN": str(gc),
            "SOAK_ROLE": role,
            "SOAK_DATA": str(data),
            "SOAK_POLL_S": "0.2",
            "SOAK_DRAIN_IDLE_S": "0.5",
            "SOAK_STEP_SCALE": "0.01",
        }
        proc = subprocess.Popen([str(AGENT)], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=str(tmp_path))
        running = Running(proc, data / "agents" / "gc-s1.jsonl")
        started.append(running)
        return running

    yield start
    procfs = ProcFS()
    for running in started:
        if running.proc.poll() is None:
            running.proc.kill()
            running.proc.wait()
        for r in running.records():
            for child in r.get("children", []) if r.get("ev") == "bg" else []:
                try:
                    signal_owned(child["pid"], signal.SIGKILL, child["start"], lambda pid: None, procfs)
                except NotOwned:
                    pass


def test_a_burst_agent_works_its_bead_then_drains(agent: Callable[..., Running]) -> None:
    run = agent("burst")
    recs = run.wait_for(lambda rs: any(r["ev"] == "bg" for r in rs))
    boot = recs[0]
    assert boot["ev"] == "boot" and boot["session_id"] == "gc-s1" and boot["token16"] == token16(SECRET)
    assert boot["inc"].split(":")[1] == str(run.proc.pid)
    bg = next(r for r in recs if r["ev"] == "bg")
    assert len(bg["children"]) == 2 and all(isinstance(c.get("pid"), int) for c in bg["children"])
    time.sleep(0.3)
    assert not any(r["ev"] == "claim" for r in run.records()), "the worker waits for the first input"
    run.send(BEACON, "", "SOAK-FIRST-TURN soak-burst")
    recs = run.wait_for(lambda rs: any(r["ev"] == "drain_ack" for r in rs))
    evs = [r["ev"] for r in recs]
    assert evs.index("claim") < evs.index("artifact") < evs.index("close") < evs.index("idle") < evs.index("drain_ack")
    ins = [r for r in recs if r["ev"] == "in"]
    assert [r["beacon"] for r in ins] == [True, False, False] and ins[2]["marker"]
    art = next(r for r in recs if r["ev"] == "artifact")
    assert art["artifact"] == "gc-art1" and art["create_exit"] == 0 and art["close_exit"] == 0
    assert next(r for r in recs if r["ev"] == "close")["exit"] == 0
    assert next(r for r in recs if r["ev"] == "idle")["reason"] == "no_work"
    assert next(r for r in recs if r["ev"] == "drain_ack")["via"] == "hook"
    deadline = time.monotonic() + 5
    while b"drained" not in run.out and time.monotonic() < deadline:
        time.sleep(0.05)
    assert run.out.startswith(b"soak-agent soak-burst-1 pid ") and b"done gc-b1" in run.out and b"drained" in run.out
    os.kill(run.proc.pid, signal.SIGTERM)
    assert run.proc.wait(timeout=10) == 128 + signal.SIGTERM
    assert run.records()[-1]["ev"] == "signal"
    assert SECRET not in run.log.read_text(encoding="utf-8")


def test_a_steady_agent_runs_drill_commands_and_exits_on_eof(agent: Callable[..., Running], tmp_path: Path) -> None:
    run = agent("steady")
    run.wait_for(lambda rs: any(r["ev"] == "bg" for r in rs))
    run.send(BEACON)
    run.wait_for(lambda rs: any(r["ev"] == "idle" for r in rs))
    cmd = tmp_path / "data" / "cmd"
    cmd.mkdir(parents=True, exist_ok=True)
    (cmd / "gc-s1.cmd").write_text("bd-touch\n", encoding="utf-8")
    recs = run.wait_for(lambda rs: any(r["ev"] == "cmd" for r in rs), timeout=10)
    assert next(r for r in recs if r["ev"] == "cmd")["exit"] == 0
    assert not (cmd / "gc-s1.cmd").exists()
    assert not any(r["ev"] == "drain_ack" for r in recs), "a steady agent never drains"
    assert run.proc.stdin is not None
    run.proc.stdin.close()
    assert run.proc.wait(timeout=10) == 0
    assert run.records()[-1]["ev"] == "eof"
    calls = (tmp_path / "claims.calls").read_text(encoding="utf-8")
    assert "list --limit 1 --json" in calls and "--drain-ack" not in calls
