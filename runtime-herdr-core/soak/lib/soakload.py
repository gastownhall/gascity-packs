"""``soak load`` (steady formula load and nudges) and ``soak probe`` (the
periodic death probe that measures death-to-restart latency)."""

from __future__ import annotations

import json
import random
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from soakanalysis import incarnations
from soaklib import City, CmdResult, NotOwned, ProcFS, Rec, append_jsonl, cmd_record, read_jsonl, run, signal_owned, write_atomic

ACTION_TIMEOUT_S = 120.0
RUNNING_STATES = frozenset({"active", "awake"})
STEADY = "soak-steady"
BURST = "soak-burst"


@dataclass(frozen=True)
class LoadConfig:
    burst_s: float
    steady_s: float
    nudge_s: float
    seed: int
    modes: Tuple[Tuple[str, int], ...]

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> "LoadConfig":
        modes = tuple((str(m), int(w)) for m, w in doc.get("nudge_modes", [["wait-idle", 80], ["immediate", 10], ["queue", 10]]))
        return cls(float(doc["burst_s"]), float(doc["steady_s"]), float(doc["nudge_s"]), int(doc.get("seed", 0)), modes)

    def periods(self) -> Dict[str, float]:
        return {"burst": self.burst_s, "steady": self.steady_s, "nudge": self.nudge_s}


def due_actions(now: float, periods: Mapping[str, float], next_due: Dict[str, float]) -> List[str]:
    """The actions due at ``now``; advances ``next_due`` (a missed period is
    skipped, not replayed)."""
    out: List[str] = []
    for action in sorted(periods):
        due = next_due.setdefault(action, now)
        if now >= due:
            out.append(action)
            period = periods[action]
            next_due[action] = due + period * max(1, int((now - due) // period) + 1)
    return out


def pick_mode(rng: random.Random, modes: Sequence[Tuple[str, int]]) -> str:
    total = sum(w for _, w in modes)
    roll = rng.uniform(0, total)
    upto = 0.0
    for mode, weight in modes:
        upto += weight
        if roll <= upto:
            return mode
    return modes[-1][0]


def running_sessions(doc: Optional[Rec], template: str) -> List[str]:
    """Running sessions of ``template`` from ``gc session list --json``, by id."""
    if doc is None:
        return []
    out: List[str] = []
    for row in doc.get("sessions") or []:
        if not isinstance(row, dict) or row.get("closed"):
            continue
        if template and not template_is(str(row.get("template", "")), template):
            continue
        running = row.get("running")
        if running is False:
            continue
        if str(row.get("state", "")) in RUNNING_STATES or running is True:
            out.append(str(row["id"]))
    return sorted(out)


def template_is(name: str, template: str) -> bool:
    """``name`` is ``template``, bare or qualified (``<pack>/<name>`` or ``<pack>.<name>``)."""
    return name == template or name.endswith("/" + template) or name.endswith("." + template)


def nonce(rng: random.Random) -> str:
    return "%032x" % rng.getrandbits(128)


@dataclass
class LoadGen:
    city: City
    cfg: LoadConfig
    gc: str = "gc"
    rng: random.Random = field(default_factory=random.Random)
    seq: int = 0
    next_due: Dict[str, float] = field(default_factory=dict)

    def gc_run(self, argv: Sequence[str], timeout: float = ACTION_TIMEOUT_S) -> CmdResult:
        return run([self.gc, *argv], cwd=str(self.city.path), timeout=timeout)

    def city_running(self) -> bool:
        res = self.gc_run(["status", "--json"], timeout=60.0)
        doc = res.json()
        return bool(doc and doc.get("running"))

    def record(self, rec: Rec) -> None:
        append_jsonl(self.city.file("load.jsonl"), rec)

    def tick(self, now: float) -> List[str]:
        if self.city.flag("PAUSE") or self.city.flag("ABORTED"):
            return []
        actions = due_actions(now, self.cfg.periods(), self.next_due)
        if not actions:
            return []
        if not self.city_running():
            self.record({"t": now, "action": "skip", "why": "city not running", "skipped": actions})
            return []
        for action in actions:
            self.seq += 1
            run_label = f"{self.city.name}-{int(now)}-{self.seq}"
            if action == "burst":
                res = self.gc_run(["sling", BURST, "soak-run", "--formula", "--var", f"run={run_label}", "--json"])
                doc = res.json() or {}
                self.record(cmd_record("sling-burst", res, workflow_id=doc.get("workflow_id"), run=run_label))
            elif action == "steady":
                res = self.gc_run(["sling", STEADY, "soak-pulse", "--formula", "--var", f"run={run_label}", "--json"])
                doc = res.json() or {}
                self.record(cmd_record("sling-steady", res, workflow_id=doc.get("workflow_id"), run=run_label))
            elif action == "nudge":
                self.nudge()
        return actions

    def nudge(self) -> None:
        listing = self.gc_run(["session", "list", "--json", "--template", STEADY], timeout=60.0)
        targets = running_sessions(listing.json(), STEADY)
        if not targets:
            self.record({"t": time.time(), "action": "nudge-skip", "why": "no running soak-steady session"})
            return
        target = self.rng.choice(targets)
        mode = pick_mode(self.rng, self.cfg.modes)
        token = nonce(self.rng)
        res = self.gc_run(["session", "nudge", target, f"SOAK-NUDGE {token}", "--delivery", mode, "--json"])
        self.record(cmd_record("nudge", res, session_id=target, nonce=token, mode=mode))

    def forever(self, sleep: Callable[[float], None] = time.sleep) -> None:
        while not self.city.flag("ABORTED"):
            self.tick(time.time())
            sleep(1.0)


def load_main(city: City, gc: str = "gc") -> int:
    cfg = LoadConfig.from_json(json.loads(city.file("load.json").read_text(encoding="utf-8")))
    LoadGen(city, cfg, gc=gc, rng=random.Random(cfg.seed)).forever()
    return 0


# --- agents and the probe -------------------------------------------------------------------------


def agent_owner(procfs: ProcFS, city_path: str, session_id: Optional[str] = None) -> Callable[[int], Optional[str]]:
    """The ownership check for a scripted agent of this city (and session)."""

    def owns(pid: int) -> Optional[str]:
        info = procfs.info(pid)
        if info is None:
            return "gone"
        if info.comm != "soak-agent":
            return f"command name {info.comm!r}, not soak-agent"
        if info.env.get("GC_CITY_PATH") != city_path:
            return "not this city's agent"
        if session_id is not None and info.env.get("GC_SESSION_ID") != session_id:
            return "another session's agent"
        return None

    return owns


def session_records(city: City, session_id: str) -> List[Rec]:
    return read_jsonl(city.agents / f"{session_id}.jsonl")


def live_incarnation(city: City, session_id: str, procfs: ProcFS) -> Optional[Tuple[int, int]]:
    """``(pid, start)`` of the session's live incarnation, by its agent log and ``/proc``."""
    boot = procfs.boot_id()[:8]

    def alive(inc: str) -> bool:
        parts = inc.split(":")
        return len(parts) == 3 and parts[0] == boot and procfs.alive(int(parts[1]), int(parts[2]))

    owner = agent_owner(procfs, str(city.path), session_id)
    for inc in reversed(incarnations(session_records(city, session_id), alive)):
        if inc.alive and owner(inc.pid) is None:
            return inc.pid, inc.start
    return None


def kill_agent(city: City, session_id: str, procfs: ProcFS, kind: str, note: str = "") -> Rec:
    """SIGKILL the session's live incarnation after the ownership check; the
    fault record is written before the signal."""
    found = live_incarnation(city, session_id, procfs)
    if found is None:
        rec: Rec = {"t": time.time(), "kind": f"{kind}-error", "sessions": [session_id], "why": "no live incarnation"}
        append_jsonl(city.file("faults.jsonl"), rec)
        return rec
    pid, start = found
    rec = {"t": time.time(), "kind": kind, "sessions": [session_id], "pids": [pid], "start": start, "note": note}
    append_jsonl(city.file("faults.jsonl"), rec)
    try:
        signal_owned(pid, signal.SIGKILL, start, agent_owner(procfs, str(city.path), session_id), procfs)
    except NotOwned as err:
        rec = {"t": time.time(), "kind": f"{kind}-error", "sessions": [session_id], "why": str(err)}
        append_jsonl(city.file("faults.jsonl"), rec)
    return rec


def next_round_robin(sessions: Sequence[str], last: Optional[str]) -> Optional[str]:
    if not sessions:
        return None
    ordered = sorted(sessions)
    if last is None:
        return ordered[0]
    for sid in ordered:
        if sid > last:
            return sid
    return ordered[0]


def probe_main(city: City, procfs: ProcFS, gc: str = "gc") -> int:
    if city.flag("ABORTED") or city.flag("DRILL") or city.flag("PAUSE"):
        return 0
    state_path = city.file("probe-state.json")
    try:
        last = json.loads(state_path.read_text(encoding="utf-8")).get("last")
    except (OSError, ValueError):
        last = None
    listing = run([gc, "session", "list", "--json", "--template", STEADY], cwd=str(city.path), timeout=60.0)
    target = next_round_robin(running_sessions(listing.json(), STEADY), last)
    if target is None:
        append_jsonl(city.file("faults.jsonl"), {"t": time.time(), "kind": "probe-kill-error", "why": "no running soak-steady session"})
        return 1
    rec = kill_agent(city, target, procfs, "probe-kill")
    write_atomic(state_path, json.dumps({"last": target}) + "\n")
    return 0 if rec.get("kind") == "probe-kill" else 1


__all__ = ["LoadConfig", "LoadGen", "due_actions", "kill_agent", "pick_mode", "running_sessions"]
