"""The soak's scripted agent: a deterministic program gc runs as a session.

It logs every input line and every action to
``$SOAK_DATA/agents/<GC_SESSION_ID>.jsonl`` (one ``write(2)`` per line), claims
work with ``gc hook --claim --json``, runs each step for a time derived from
the bead id, makes one store write per step, and closes the bead. It never
reads a model credential and holds no secret: the instance token is logged
only as a sha256 prefix.
"""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, NoReturn, Optional, Sequence, TextIO, Tuple

from soakanalysis import BEACON, MARKER, NUDGE_NONCE
from soaklib import CmdResult, Rec, append_jsonl, last_json_object, parse_stat, run

PROMPT = "soak> "
CLAIM_TIMEOUT_S = 60.0
STORE_TIMEOUT_S = 60.0
HEARTBEAT_S = 60.0
CMD_POLL_S = 1.0
TOUCH_AFTER_LIMIT_S = 60.0
_NO_WORK_REASONS = frozenset({"no_work", "claims_errored"})
_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


def classify(text: str) -> Dict[str, Any]:
    """What one input line is: gc's beacon, the first-turn marker, a nudge nonce."""
    nonce = NUDGE_NONCE.search(text)
    return {
        "beacon": BEACON.match(text) is not None,
        "marker": MARKER in text,
        "nonce": nonce.group(1) if nonce else None,
    }


def step_seconds(bead: str) -> int:
    """A step's run time, 10 to 30 s, fixed by the bead id."""
    return 10 + int(hashlib.sha256(bead.encode("utf-8")).hexdigest()[:8], 16) % 21


def token16(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else ""


@dataclass(frozen=True)
class Decision:
    """What to do after one claim."""

    kind: str
    """``work``, ``drained`` (the seat leaves), ``ack_drain`` (a pending drain
    to acknowledge), ``idle`` (no work) or ``error`` (no parsable record)."""
    reason: str = ""
    bead: str = ""
    root: str = ""


def decide(result: Optional[Rec], code: int, sent_drain_ack: bool) -> Decision:
    """The agent's reading of one ``gc hook --claim --json`` answer. gc exits 1
    with a ``drain`` record when there is no work, so the record decides, not
    the exit code."""
    if result is None or not isinstance(result.get("action"), str):
        return Decision("error")
    action = result["action"]
    reason = str(result.get("reason", ""))
    if action == "work" and result.get("bead_id"):
        return Decision("work", reason, str(result["bead_id"]), str(result.get("root_bead_id", "")))
    if action == "drain":
        if sent_drain_ack and (result.get("drain_acknowledged") is True or code == 0):
            return Decision("drained", reason)
        if not sent_drain_ack and reason and reason not in _NO_WORK_REASONS:
            return Decision("ack_drain", reason)
    return Decision("idle", reason or action)


def self_identity(proc_root: str = "/proc") -> Tuple[str, int, int]:
    """``(boot id prefix, pid, start ticks)`` of this process."""
    pid = os.getpid()
    with open(f"{proc_root}/{pid}/stat", encoding="utf-8") as handle:
        start = parse_stat(handle.read()).start
    try:
        with open(f"{proc_root}/sys/kernel/random/boot_id", encoding="utf-8") as handle:
            boot = handle.read().strip()[:8]
    except OSError:
        boot = "unknown"
    return boot, pid, start


def start_ticks(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            return parse_stat(handle.read()).start
    except (OSError, ValueError, IndexError):
        return -1


class Agent:
    def __init__(self, env: Mapping[str, str], out: TextIO) -> None:
        self.env = dict(env)
        self.out = out
        self.session_id = env.get("GC_SESSION_ID", "") or "unknown"
        self.gc = env.get("GC_BIN", "") or "gc"
        self.role = env.get("SOAK_ROLE", "steady")
        self.poll_s = float(env.get("SOAK_POLL_S", "") or 15)
        self.drain_idle_s = float(env.get("SOAK_DRAIN_IDLE_S", "") or 60)
        self.step_scale = float(env.get("SOAK_STEP_SCALE", "") or 1.0)
        data = env.get("SOAK_DATA", "")
        if not data:
            raise SystemExit("soak-agent: SOAK_DATA is not set")
        self.data = Path(data)
        (self.data / "agents").mkdir(parents=True, exist_ok=True, mode=0o700)
        self.log_path = self.data / "agents" / f"{self.session_id}.jsonl"
        self.cmd_path = self.data / "cmd" / f"{self.session_id}.cmd"
        boot, pid, start = self_identity()
        self.pid = pid
        self.inc = f"{boot}:{pid}:{start}"
        self.lock = threading.Lock()
        self.input_seen = threading.Event()
        self.started = threading.Event()
        self.n_in = 0

    # --- output ------------------------------------------------------------------------

    def log(self, ev: str, **fields: Any) -> None:
        rec: Rec = {"ev": ev, "t": time.time(), "mono": time.monotonic(), "pid": self.pid, "inc": self.inc}
        rec.update(fields)
        append_jsonl(self.log_path, rec)

    def say(self, text: str) -> None:
        with self.lock:
            self.out.write(text)
            self.out.flush()

    def prompt(self) -> None:
        self.say(PROMPT)

    # --- boot -----------------------------------------------------------------------------

    def boot(self) -> None:
        try:
            with open("/proc/self/cgroup", encoding="utf-8") as handle:
                cgroup = handle.read().strip()
        except OSError:
            cgroup = ""
        ppid = os.getppid()
        try:
            with open(f"/proc/{ppid}/comm", encoding="utf-8") as handle:
                parent_comm = handle.read().strip()
        except OSError:
            parent_comm = ""
        self.log(
            "boot",
            session_id=self.session_id,
            session_name=self.env.get("GC_SESSION_NAME", ""),
            alias=self.env.get("GC_ALIAS", ""),
            agent=self.env.get("GC_AGENT", ""),
            template=self.env.get("GC_TEMPLATE", ""),
            token16=token16(self.env.get("GC_INSTANCE_TOKEN", "")),
            epoch=self.env.get("GC_RUNTIME_EPOCH", ""),
            city=self.env.get("GC_CITY_PATH", "") or self.env.get("GC_CITY", ""),
            role=self.role,
            cgroup=cgroup,
            ppid=ppid,
            parent_comm=parent_comm,
            hc_scope="HC_SCOPE" in self.env,
        )
        children: List[Dict[str, Any]] = []
        for argv in (["sleep", "86400"], [sys.executable, "-I", "-m", "http.server", "0", "--bind", "127.0.0.1"]):
            try:
                child = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    cwd="/",
                )
            except OSError as err:
                children.append({"argv": argv[:2], "error": str(err)})
                continue
            children.append({"argv": argv[:2], "pid": child.pid, "start": start_ticks(child.pid)})
        self.log("bg", children=children)
        self.say(f"soak-agent {self.env.get('GC_SESSION_NAME', '')} pid {self.pid}\n")
        self.prompt()

    # --- threads -------------------------------------------------------------------------

    def reader(self, stdin: Any) -> None:
        while True:
            raw = stdin.readline()
            if not raw:
                self.log("eof", n=self.n_in)
                os._exit(0)
            text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
            text = text.rstrip("\r\n")
            self.n_in += 1
            self.log("in", n=self.n_in, text=text[:1000], **classify(text))
            self.started.set()
            self.input_seen.set()

    def heartbeat(self) -> None:
        while True:
            time.sleep(HEARTBEAT_S)
            self.log("hb")

    def commands(self) -> None:
        while True:
            time.sleep(CMD_POLL_S)
            claimed = self.cmd_path.with_name(f".{self.cmd_path.name}.{self.pid}")
            try:
                os.rename(self.cmd_path, claimed)
            except OSError:
                continue
            try:
                text = claimed.read_text(encoding="utf-8").strip()
            except OSError:
                text = ""
            try:
                claimed.unlink()
            except OSError:
                pass
            self.run_command(text)

    def run_command(self, text: str) -> None:
        words = text.split()
        verb = words[0] if words else ""
        if verb == "bd-touch":
            res = self.bd_touch()
            self.log("cmd", cmd=text, exit=res.code, dur_s=round(res.duration_s, 3), tail=res.tail(300))
        elif verb == "bd-touch-after":
            pairs = [(int(words[i]), int(words[i + 1])) for i in range(1, len(words) - 1, 2)]
            waited = wait_gone(pairs, TOUCH_AFTER_LIMIT_S)
            res = self.bd_touch()
            self.log("cmd", cmd=text, waited_s=round(waited, 3), exit=res.code, dur_s=round(res.duration_s, 3), tail=res.tail(300))
        elif verb == "hc-ls":
            res = run(["hc", "ls"], timeout=30.0)
            self.log("cmd", cmd=text, exit=res.code, out=res.out[-1500:], tail=res.tail(300))
        elif verb == "exit" and len(words) == 2 and words[1].isdigit():
            self.log("cmd", cmd=text, exit=int(words[1]))
            os._exit(int(words[1]))
        else:
            self.log("cmd", cmd=text, error="unknown command")

    def bd_touch(self) -> CmdResult:
        return run([self.gc, "bd", "list", "--limit", "1", "--json"], timeout=STORE_TIMEOUT_S)

    # --- work ------------------------------------------------------------------------------

    def claim(self, drain_ack: bool) -> Tuple[Optional[Rec], CmdResult]:
        argv = [self.gc, "hook", "--claim", "--json"] + (["--drain-ack"] if drain_ack else [])
        res = run(argv, timeout=CLAIM_TIMEOUT_S)
        return last_json_object(res.out), res

    def work(self, bead: str, root: str) -> None:
        self.log("claim", bead=bead, root=root)
        seconds = step_seconds(bead)
        time.sleep(seconds * self.step_scale)
        created = run([self.gc, "bd", "create", f"soak artifact {bead}", "--json"], timeout=STORE_TIMEOUT_S)
        doc = last_json_object(created.out)
        artifact = str(doc.get("id", "")) if doc else ""
        closed: Optional[CmdResult] = None
        if artifact:
            closed = run([self.gc, "bd", "close", artifact], timeout=STORE_TIMEOUT_S)
        self.log(
            "artifact",
            bead=bead,
            artifact=artifact,
            create_exit=created.code,
            create_s=round(created.duration_s, 3),
            close_exit=None if closed is None else closed.code,
            close_s=None if closed is None else round(closed.duration_s, 3),
            tail="" if created.ok else created.tail(300),
        )
        update = [self.gc, "bd", "update", bead, "--set-metadata", "gc.outcome=pass", "--status=closed"]
        res = run(update, timeout=STORE_TIMEOUT_S)
        tries = 1
        if not res.ok:
            time.sleep(5.0 * min(1.0, self.step_scale))
            res = run(update, timeout=STORE_TIMEOUT_S)
            tries = 2
        self.log("close", bead=bead, step_s=seconds, exit=res.code, tries=tries, tail="" if res.ok else res.tail(300))
        self.say(f"done {bead}\n")
        self.prompt()

    def wait_input(self, seconds: float) -> None:
        self.input_seen.wait(seconds)
        self.input_seen.clear()

    def park(self) -> NoReturn:
        """Stop claiming and wait to be stopped."""
        while True:
            time.sleep(3600)

    def loop(self) -> None:
        self.started.wait()
        idle_since: Optional[float] = None
        last_reason: Optional[str] = None
        while True:
            self.input_seen.clear()
            drain_ack = self.role == "burst" and idle_since is not None and time.monotonic() - idle_since >= self.drain_idle_s
            self.say("[claim]\n")
            result, res = self.claim(drain_ack)
            decision = decide(result, res.code, drain_ack)
            if decision.kind == "work":
                idle_since, last_reason = None, None
                self.work(decision.bead, decision.root)
                continue
            if decision.kind == "drained":
                self.log("drain_ack", via="hook", reason=decision.reason, exit=res.code)
                self.say("drained\n")
                self.park()
            if decision.kind == "ack_drain":
                ack = run([self.gc, "runtime", "drain-ack"], timeout=CLAIM_TIMEOUT_S)
                self.log("drain_ack", via="runtime", reason=decision.reason, exit=ack.code, tail=ack.tail(300))
                self.say("drained\n")
                self.park()
            if decision.kind == "error":
                self.log("claim_error", exit=res.code, timed_out=res.timed_out, tail=res.tail(600))
                self.prompt()
                self.wait_input(self.poll_s)
                continue
            if idle_since is None:
                idle_since = time.monotonic()
            if decision.reason != last_reason:
                self.log("idle", reason=decision.reason, exit=res.code)
                last_reason = decision.reason
            self.prompt()
            self.wait_input(self.poll_s)


def wait_gone(pairs: Sequence[Tuple[int, int]], limit_s: float) -> float:
    """Poll every 50 ms until each ``(pid, start ticks)`` is gone; the seconds waited."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        if all(start_ticks(pid) != start for pid, start in pairs):
            break
        time.sleep(0.05)
    return time.monotonic() - t0


def main(env: Mapping[str, str]) -> int:
    agent = Agent(env, sys.stdout)

    def on_signal(signum: int, frame: object) -> None:
        agent.log("signal", signal=signum)
        os._exit(128 + signum)

    for sig in _SIGNALS:
        signal.signal(sig, on_signal)
    agent.boot()
    for target, args in ((agent.reader, (sys.stdin.buffer,)), (agent.heartbeat, ()), (agent.commands, ())):
        threading.Thread(target=target, args=args, daemon=True).start()
    agent.loop()
    return 0


__all__ = ["Agent", "Decision", "classify", "decide", "main", "step_seconds", "token16"]
