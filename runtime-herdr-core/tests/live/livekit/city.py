"""A scratch city that gc's own controller runs over the pack.

``gc runtime check`` and ``gc runtime conformance`` drive the pack op by op;
neither runs gc's start ladder, and gc has no command that starts one
session through a runtime without a city. So this kit writes a city under
the run's scratch base and runs the pinned gc's per-city controller loop
over it (``gc start --foreground <city>``, as gc's acceptance tests do), as
a child the run owns. gc's fresh start then runs ``provision``, ``launch``,
the launch's identity, the ready prompt, the dialog pass and the queued
first turn, all of it gc's own code; the suites only observe (the agent's
input log, the pack's test op log, hc's own reads) and play the person.

The city directory is the scratch city path, so the harness's own pack ops
resolve the same city as gc's (``GC_EXEC_CITY_PATH``). It imports the pack
by absolute path, selects ``[session] provider = "herdr-core"``, keeps its
beads in files, and runs each agent as an always-on named session.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from gc_runtime_herdr_core.rpp.jsonval import JsonObject, loads

from .owned import NotOwned
from .pack import PACK_ROOT
from .scratch import CITY_NAME, Scratch

STOP_TIMEOUT_S = 120.0
EXIT_WAIT_S = 30.0
OPLOG_ENV = "GC_HC_TEST_OPLOG"


@dataclass(frozen=True)
class CityAgent:
    """One always-on named session of the city: the live agent in ``mode``,
    started with ``first_turn`` as its first turn."""

    name: str
    mode: str
    first_turn: str


@dataclass(frozen=True)
class OpLine:
    """One line of the pack's test op log."""

    op: str
    session: str
    exit: int
    outcome: str
    begun_ms: int
    ended_ms: int


def _q(value: str) -> str:
    """A TOML basic string (JSON's escapes are TOML's)."""
    return json.dumps(value)


def city_toml(scratch: Scratch, agents: Sequence[CityAgent]) -> str:
    """The city's whole configuration."""
    python = scratch.python
    lines = [
        "[workspace]",
        f"name = {_q(CITY_NAME)}",
        "",
        "[imports.herdr-core]",
        f"source = {_q(str(PACK_ROOT))}",
        "",
        "[beads]",
        'provider = "file"',
        "",
        "[session]",
        'provider = "herdr-core"',
    ]
    for agent in agents:
        env = {k: v for k, v in scratch.agent_env(agent.name, GC_HC_LIVE_MODE=agent.mode).items() if k != "GC_INSTANCE_TOKEN"}
        table = ", ".join(f"{_q(k)} = {_q(v)}" for k, v in sorted(env.items()))
        lines += [
            "",
            "[[agent]]",
            f"name = {_q(agent.name)}",
            f"start_command = {_q(scratch.agent_command())}",
            f"process_names = [{_q(os.path.basename(python))}]",
            'prompt_mode = "none"',
            f"ready_prompt_prefix = {_q('❯ ')}",
            f"nudge = {_q(agent.first_turn)}",
            f"work_dir = {_q(scratch.work)}",
            f"env = {{ {table} }}",
            "",
            "[[named_session]]",
            f"template = {_q(agent.name)}",
            'mode = "always"',
        ]
    return "\n".join(lines) + "\n"


def write_city(scratch: Scratch, agents: Sequence[CityAgent]) -> str:
    """Write the city at the scratch city path; returns its directory."""
    city = scratch.city_path
    os.makedirs(os.path.join(city, ".gc"), mode=0o700, exist_ok=True)
    with open(os.path.join(city, "city.toml"), "w", encoding="utf-8") as handle:
        handle.write(city_toml(scratch, agents))
    return city


def read_oplog(path: str) -> List[OpLine]:
    """The pack's op log (one JSON object per op), oldest first."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return []
    out: List[OpLine] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        doc = JsonObject.of(loads(line))
        out.append(
            OpLine(
                op=doc.req_str("op"),
                session=doc.req_str("session"),
                exit=doc.req_int("exit"),
                outcome=doc.req_str("outcome"),
                begun_ms=doc.req_int("begun_ms"),
                ended_ms=doc.req_int("ended_ms"),
            )
        )
    return out


def of_session(lines: Sequence[OpLine], agent: str) -> List[OpLine]:
    """The ops gc ran on ``agent``'s session (gc names it after the agent)."""
    return [line for line in lines if line.session == agent or line.session.endswith(agent)]


class Controller:
    """gc's per-city controller over the scratch city, owned by the run."""

    def __init__(self, scratch: Scratch, gc_bin: str) -> None:
        self.scratch = scratch
        self.gc_bin = gc_bin
        self.proc: Optional["subprocess.Popen[bytes]"] = None
        self.log = os.path.join(scratch.base, "controller.log")
        self.oplog = os.path.join(scratch.base, "oplog.jsonl")

    def env(self) -> Dict[str, str]:
        """gc's environment: a scratch home, file beads and no Dolt, and the
        pack's knobs (the scratch state root, this lane's placement, the
        pinned hc, the op log), which gc passes to every op it runs."""
        home = os.path.join(self.scratch.base, "gchome")
        os.makedirs(home, mode=0o700, exist_ok=True)
        env = self.scratch.pack_env(rescope=self.scratch.lane == "systemd")
        env.update(
            {
                "HOME": home,
                "GC_HOME": home,
                "XDG_CONFIG_HOME": os.path.join(home, ".config"),
                "XDG_DATA_HOME": os.path.join(home, ".local", "share"),
                "XDG_CACHE_HOME": os.path.join(home, ".cache"),
                "TMPDIR": "/tmp",
                "GC_BEADS": "file",
                "GC_DOLT": "skip",
                "DO_NOT_TRACK": "1",
                OPLOG_ENV: self.oplog,
            }
        )
        if self.scratch.lane == "plain":
            env["XDG_RUNTIME_DIR"] = self.scratch.runtime_dir
        return env

    def start(self) -> None:
        with open(self.log, "ab") as out:
            self.proc = subprocess.Popen(
                [self.gc_bin, "start", "--foreground", self.scratch.city_path],
                cwd=self.scratch.city_path,
                env=self.env(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
            )
        self.scratch.ownership.record(self.proc.pid)

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def ops(self) -> List[OpLine]:
        return read_oplog(self.oplog)

    def log_tail(self, limit: int = 6000) -> str:
        try:
            with open(self.log, "rb") as handle:
                return handle.read()[-limit:].decode("utf-8", "replace")
        except FileNotFoundError:
            return ""

    def wait_for(self, what: str, predicate: "object", timeout_s: float, *, step_s: float = 0.5) -> None:
        """Wait until ``predicate()`` holds; fail naming ``what`` with the controller's log."""
        end = time.monotonic() + timeout_s
        while not predicate():  # type: ignore[operator]
            if not self.running():
                raise AssertionError(f"the controller exited while waiting for {what}:\n{self.log_tail()}")
            if time.monotonic() > end:
                raise AssertionError(f"{what} did not happen within {timeout_s:.0f} s:\n{self.log_tail()}")
            time.sleep(step_s)

    def nudge_counts(self, target: str) -> Dict[str, int]:
        """``gc nudge status <target> --json``'s counts: pending, in flight, dead."""
        done = subprocess.run(
            [self.gc_bin, "nudge", "status", target, "--json"],
            cwd=self.scratch.city_path,
            env=self.env(),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if done.returncode != 0:
            raise AssertionError(f"gc nudge status {target} exited {done.returncode}: {done.stderr.strip()[-2000:]}")
        counts = JsonObject.of(loads(done.stdout)).req_obj("counts")
        return {key: counts.int_or(key, 0) for key in ("pending", "in_flight", "dead")}

    def stop(self) -> List[str]:
        """``gc stop <city>`` (it stops the sessions and sends ``server-stop``),
        then wait for the controller to exit. A controller that does not is
        killed by its recorded pid only. Returns what went wrong."""
        problems: List[str] = []
        if self.proc is None:
            return problems
        try:
            done = subprocess.run(
                [self.gc_bin, "stop", self.scratch.city_path],
                cwd=self.scratch.city_path,
                env=self.env(),
                capture_output=True,
                text=True,
                timeout=STOP_TIMEOUT_S,
                check=False,
            )
            if done.returncode != 0:
                problems.append(f"gc stop exited {done.returncode}: {(done.stdout + done.stderr).strip()[-2000:]}")
        except subprocess.TimeoutExpired:
            problems.append(f"gc stop hung for {STOP_TIMEOUT_S:.0f} s")
        try:
            self.proc.wait(timeout=EXIT_WAIT_S)
        except subprocess.TimeoutExpired:
            problems.append(f"the controller did not exit within {EXIT_WAIT_S:.0f} s of gc stop")
            try:
                self.scratch.ownership.signal(self.proc.pid, signal.SIGKILL)
            except NotOwned:
                pass
            self.proc.wait(timeout=EXIT_WAIT_S)
        return problems

