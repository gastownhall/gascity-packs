"""The pack's executable driven op by op, as gc drives it (RPP v0's per-op
calling convention): ``<entry> <op> <session> ...``, op data on stdin, the
answer on stdout and the exit code."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Collection, Dict, List, Mapping, Optional, Sequence

from gc_runtime_herdr_core.rpp.jsonval import JsonObject, loads

if TYPE_CHECKING:
    from .scratch import Scratch

PACK_ROOT = Path(__file__).resolve().parents[3]
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"
OP_TIMEOUT_S = 90.0


@dataclass(frozen=True)
class OpAnswer:
    code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class Seen:
    """An ``observe`` answer."""

    state: str
    object_id: Optional[str]
    created: Optional[str]
    agent_pid: Optional[str]

    @property
    def object(self) -> Dict[str, str]:
        if self.object_id is None or self.created is None:
            raise AssertionError(f"observe named no object (state {self.state})")
        return {"id": self.object_id, "created": self.created}


class Pack:
    def __init__(self, scratch: "Scratch", *, rescope: bool = False) -> None:
        self.scratch = scratch
        self.rescope = rescope

    def argv(self, *args: str) -> List[str]:
        return [self.scratch.python, "-I", "-S", str(ENTRY), *args]

    def op(self, *args: str, stdin: bytes = b"", timeout_s: float = OP_TIMEOUT_S, extra_env: Optional[Mapping[str, str]] = None) -> OpAnswer:
        env = self.scratch.pack_env(rescope=self.rescope)
        env.update(extra_env or {})
        done = subprocess.run(
            self.argv(*args),
            env=env,
            cwd=self.scratch.work,
            input=stdin,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        return OpAnswer(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))

    def popen(self, *args: str, stdin: bytes = b"") -> "subprocess.Popen[bytes]":
        """An op left running (to be killed mid-flight); the run owns it."""
        proc = subprocess.Popen(
            self.argv(*args),
            env=self.scratch.pack_env(rescope=self.rescope),
            cwd=self.scratch.work,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.scratch.ownership.record(proc.pid)
        assert proc.stdin is not None
        proc.stdin.write(stdin)
        proc.stdin.close()
        return proc

    def start_config(
        self, name: str, command: str, *, env: Optional[Mapping[str, str]] = None, pre_start: Sequence[str] = ()
    ) -> bytes:
        doc: Dict[str, object] = {
            "command": command,
            "work_dir": self.scratch.work,
            "env": dict(env if env is not None else self.scratch.agent_env(name)),
        }
        if pre_start:
            doc["pre_start"] = list(pre_start)
        return json.dumps(doc).encode("utf-8")

    def start(self, name: str, command: str, *, env: Optional[Mapping[str, str]] = None) -> OpAnswer:
        return self.op("start", name, stdin=self.start_config(name, command, env=env))

    def unwelded_config(self, name: str, *, fresh_only: bool = False, **extra: str) -> bytes:
        """The live agent's start config as gc sends it to ``provision`` and
        ``launch`` (``fresh_only`` for a fresh start)."""
        doc = json.loads(self.start_config(name, self.scratch.agent_command(), env=self.scratch.agent_env(name, **extra)))
        if fresh_only:
            doc["fresh_only"] = True
        return json.dumps(doc).encode("utf-8")

    def provision(self, name: str, config: bytes) -> OpAnswer:
        """gc's ``provision``: the name prepared, no agent started."""
        return self.op("provision", name, stdin=config)

    def launch(self, name: str, config: bytes) -> OpAnswer:
        """gc's ``launch``: the agent started in what ``provision`` prepared."""
        return self.op("launch", name, stdin=config)

    def start_agent(self, name: str, **extra: str) -> OpAnswer:
        """Start the live agent as session ``name`` (see ``agent.py``)."""
        return self.start(name, self.scratch.agent_command(), env=self.scratch.agent_env(name, **extra))

    def observe(self, name: str) -> Seen:
        answer = self.op("observe", name)
        if answer.code != 0:
            raise AssertionError(f"observe {name}: exit {answer.code}: {answer.stderr}")
        doc = JsonObject.of(loads(answer.stdout))
        box = doc.opt_obj("object")
        return Seen(
            state=doc.req_str("state"),
            object_id=None if box is None else box.req_str("id"),
            created=None if box is None else box.req_str("created"),
            agent_pid=doc.opt_str("agent_pid"),
        )

    def wait_state(self, name: str, states: Collection[str], timeout_s: float) -> Seen:
        end = time.monotonic() + timeout_s
        seen = self.observe(name)
        while seen.state not in states and time.monotonic() < end:
            time.sleep(0.5)
            seen = self.observe(name)
        return seen

    def kill_object(self, name: str, obj: Mapping[str, str], mode: str = "corpse") -> OpAnswer:
        return self.op("kill-object", name, stdin=json.dumps({"object": dict(obj), "mode": mode}).encode("utf-8"))

    def stop(self, name: str) -> OpAnswer:
        return self.op("stop", name)

    def is_running(self, name: str) -> bool:
        answer = self.op("is-running", name)
        return answer.code == 0 and answer.stdout.strip() == "true"

    def nudge(self, name: str, text: str) -> OpAnswer:
        return self.op("nudge", name, stdin=text.encode("utf-8"))

    def restart_after_death(self, name: str, *, timeout_s: float = 30.0, **extra: str) -> Seen:
        """What gc does with a dead box: kill the object (the corpse's tree,
        by identity), then start the session again."""
        dead = self.wait_state(name, ("dead", "absent"), timeout_s)
        if dead.state == "dead":
            killed = self.kill_object(name, dead.object)
            if killed.code != 0 or killed.stdout.strip() not in ("killed", "gone"):
                raise AssertionError(f"kill-object {name}: exit {killed.code} {killed.stdout.strip()!r}: {killed.stderr}")
        self.scratch.forget_agent(name)
        started = self.start_agent(name, **extra)
        if started.code != 0:
            raise AssertionError(f"restart {name}: exit {started.code}: {started.stderr}")
        return self.wait_state(name, ("running",), timeout_s)
