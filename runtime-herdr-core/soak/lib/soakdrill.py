"""``soak drill <name>``: the fault drills F1 to F10.

Each drill takes the drill lock (``DRILL``, which ``soak check`` honours),
records the state before, injects its fault (and a ``faults.jsonl`` record
naming what it ends, written before the signal), measures, waits for the
settle window, scans for orphans, and writes ``drills/<name>-<time>.json``
with every criterion's measured value and verdict.

Every signal goes through :func:`soaklib.signal_owned` after an ownership
check: hc runtime of the city's core tuple, a scripted agent of the city, or
the city's store proxy. Nothing is ever killed by name or pattern.
"""

from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from soakanalysis import (
    FT_DUPLICATED,
    FT_EXACT,
    FT_PENDING,
    city_cores,
    find_orphans,
    first_turns,
    foreign_hc,
    hc_role,
    hc_runtime,
    incarnations,
    store_procs,
)
from soakcapture import remains
from soakcheck import agent_records, alive_by_proc
from soakhc import CoreStatus, CoreTuple, HcError, HcRpc, core_tuple, hc_env, wait_answers
from soakload import STEADY, agent_owner, kill_agent, running_sessions
from soaklib import (
    City,
    CmdResult,
    NotOwned,
    ProcFS,
    ProcInfo,
    Rec,
    SoakPaths,
    append_jsonl,
    iso,
    read_jsonl,
    run,
    signal_owned,
    unit_of,
    write_atomic,
)

PATROL_S = 30.0
BACK_LIMIT_S = 2 * PATROL_S + 10.0
REAP_LIMIT_S = PATROL_S + 10.0
SETTLE_S = 600.0
CORE_ANSWER_S = 30.0
HC_VERSION = "0.1.19"
UPGRADE_VERSION = "0.1.20"
FOREIGN_REFUSAL = "started outside the pack"
UPGRADE_LINE = f"handed the city's core over from herdr-core {HC_VERSION} to {UPGRADE_VERSION}; its sessions kept running"
ALWAYS_ON_TEMPLATES = (STEADY, "control-dispatcher")

PIN_0_1_20: Dict[str, Any] = {
    "version": "0.1.20",
    "generation": 1,
    "min_version": "0.1.19",
    "tested": ["0.1.19", "0.1.20"],
    "releases": "https://releases.herdr.dev/core",
    "binary": "herdr-core",
    "targets": {
        "linux-x86_64": {
            "asset": "herdr-core-linux-x86_64.tar.gz",
            "sha256": "ac6b86890c451a37584620aaa438b71bc0d0bd430a2e7c1d7e095f052c414e74",
        },
        "linux-aarch64": {
            "asset": "herdr-core-linux-aarch64.tar.gz",
            "sha256": "5f3037379d15cc76cfc72d2fd1a4262ea1c5b24df278bf7cfd8adcff7b914862",
        },
        "macos-aarch64": {
            "asset": "herdr-core-macos-aarch64.tar.gz",
            "sha256": "e58985d3fef6e909f33d3c5a4426e4898c81564a557d4636591cec9e3a06af26",
        },
        "macos-x86_64": {
            "asset": "herdr-core-macos-x86_64.tar.gz",
            "sha256": "36c0331c3ffea0ffaada195b89a3c7496f7f3fc5bf35e4605c19c84e5c205a56",
        },
    },
}
"""The 0.1.20 pin written over the pack copy's ``assets/hc-pin.json`` for the
upgrade drill only (the 0.1.20 release manifest's sha256 values)."""

DRILLS = (
    "place-store",
    "holder-kill",
    "holder-unit-kill",
    "core-kill",
    "core-restart",
    "agent-kill",
    "hc-update",
    "upgrade",
    "stop-wedged",
    "reboot",
    "reboot-verify",
)


class DrillError(Exception):
    pass


@dataclass
class Criterion:
    id: str
    what: str
    measured: Any
    passed: Optional[bool]
    """None: recorded, not judged."""

    def as_rec(self) -> Rec:
        return {"id": self.id, "what": self.what, "measured": self.measured, "pass": self.passed}


@dataclass
class Before:
    t: float
    core: Optional[CoreStatus]
    boxes: Dict[int, Tuple[int, str]]
    """pid -> (start ticks, GC_SESSION_ID)."""
    sessions: Dict[str, str]
    """Running session id -> template, from ``gc session list``."""
    store: List[Tuple[int, int, str]]
    supervisor_pid: int
    alive_incs: Set[str]
    bg: List[Tuple[int, int]]
    supervisor_lines: Set[str]

    def as_rec(self) -> Rec:
        return {
            "t": self.t,
            "core": None if self.core is None else {"pid": self.core.pid, "version": self.core.version, "holders": list(self.core.holders)},
            "boxes": {str(p): list(v) for p, v in self.boxes.items()},
            "sessions": self.sessions,
            "store": [list(s) for s in self.store],
            "supervisor_pid": self.supervisor_pid,
        }


def is_always_on(template: str) -> bool:
    return any(template == t or template.endswith("/" + t) or template.endswith("." + t) for t in ALWAYS_ON_TEMPLATES)


@dataclass
class Drill:
    name: str
    city: City
    paths: SoakPaths
    procfs: ProcFS = field(default_factory=ProcFS)
    gc: str = "gc"
    settle_s: float = SETTLE_S
    criteria: List[Criterion] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    t_inject: float = 0.0
    core: Optional[CoreTuple] = None

    # --- plumbing --------------------------------------------------------------------------

    @property
    def uid(self) -> int:
        return os.getuid()

    def say(self, text: str) -> None:
        print(f"{iso(time.time())} drill {self.name}: {text}", flush=True)

    def gc_run(self, argv: Sequence[str], timeout: float = 300.0) -> CmdResult:
        return run([self.gc, *argv], cwd=str(self.city.path), timeout=timeout)

    def judge(self, cid: str, what: str, measured: Any, passed: Optional[bool]) -> None:
        self.criteria.append(Criterion(cid, what, measured, passed))
        mark = "recorded" if passed is None else ("pass" if passed else "FAIL")
        self.say(f"{cid} {mark}: {what}: {measured}")

    def fault(self, kind: str, covers: Sequence[str], **extra: Any) -> Rec:
        rec: Rec = {"t": time.time(), "kind": kind, "drill": self.name, "covers": list(covers)}
        rec.update(extra)
        append_jsonl(self.city.file("faults.jsonl"), rec)
        return rec

    def core_tuple(self) -> CoreTuple:
        if self.core is None:
            self.core = core_tuple(str(self.city.path), self.gc)
        return self.core

    def rpc(self) -> HcRpc:
        return HcRpc(self.core_tuple().socket)

    def hc_bin(self, version: str = HC_VERSION) -> str:
        return str(self.paths.pinned_hc(version))

    def status(self) -> Optional[CoreStatus]:
        try:
            return self.rpc().status()
        except HcError:
            return None

    def snapshot(self) -> Dict[int, ProcInfo]:
        return self.procfs.snapshot(self.uid)

    def boxes_now(self, holders: Sequence[int]) -> Dict[int, Tuple[int, str]]:
        holder_set = set(holders)
        return {p.pid: (p.start, p.env.get("GC_SESSION_ID", "")) for p in self.snapshot().values() if p.ppid in holder_set}

    def sessions_now(self) -> Dict[str, str]:
        res = self.gc_run(["session", "list", "--json"], timeout=60.0)
        doc = res.json() or {}
        running = set(running_sessions(doc, ""))
        out: Dict[str, str] = {}
        for row in doc.get("sessions") or []:
            if isinstance(row, dict) and str(row.get("id")) in running:
                out[str(row["id"])] = str(row.get("template", ""))
        return out

    def store_now(self) -> List[Tuple[int, int, str]]:
        return [(p.pid, p.start, p.argv1 or p.comm) for p in store_procs(self.snapshot(), self.uid)]

    def supervisor_pid(self) -> int:
        from soaksample import supervisor_state

        return int(supervisor_state()["pid"])

    def supervisor_lines(self) -> Set[str]:
        res = run([self.gc, "supervisor", "logs", "-n", "5000"], timeout=120.0)
        return set(res.out.splitlines())

    def incs(self) -> List[Any]:
        records = agent_records(self.city)
        return incarnations((r for recs in records.values() for r in recs), alive_by_proc(self.procfs))

    def before(self) -> Before:
        status = self.status()
        holders = list(status.holders) if status else []
        incs = self.incs()
        alive = [i for i in incs if i.alive]
        return Before(
            t=time.time(),
            core=status,
            boxes=self.boxes_now(holders),
            sessions=self.sessions_now(),
            store=self.store_now(),
            supervisor_pid=self.supervisor_pid(),
            alive_incs={i.inc for i in alive},
            bg=[pair for i in alive for pair in i.bg],
            supervisor_lines=self.supervisor_lines(),
        )

    # --- ownership ------------------------------------------------------------------------------

    def hc_owner(self, role: str) -> Callable[[int], Optional[str]]:
        core = self.core_tuple()

        def owns(pid: int) -> Optional[str]:
            info = self.procfs.info(pid)
            if info is None:
                return "gone"
            if info.uid != self.uid:
                return "another user's process"
            if hc_role(info) != role:
                return f"not an hc {role} process"
            if info.env.get("XDG_STATE_HOME") != core.state_home or info.env.get("HC_SESSION") != core.session:
                return "hc runtime of another core"
            return None

        return owns

    def store_owner(self) -> Callable[[int], Optional[str]]:
        city = str(self.city.path)
        beads = os.path.join(city, ".beads")

        def owns(pid: int) -> Optional[str]:
            info = self.procfs.info(pid)
            if info is None:
                return "gone"
            if info.uid != self.uid:
                return "another user's process"
            is_proxy = info.argv1 == "db-proxy-child"
            is_dolt = info.comm == "dolt" and "sql-server" in info.argv
            if not (is_proxy or is_dolt):
                return "not a store proxy or its Dolt"
            try:
                cwd = os.readlink(f"/proc/{pid}/cwd")
            except OSError:
                cwd = ""
            if info.env.get("GC_CITY_PATH") == city or any(beads in a for a in info.argv) or cwd.startswith(beads):
                return None
            return "not this city's store"

        return owns

    def kill(self, pid: int, start: int, sig: int, owner: Callable[[int], Optional[str]]) -> bool:
        try:
            signal_owned(pid, sig, start, owner, self.procfs)
        except NotOwned as err:
            self.notes.append(f"not signalled: {err}")
            self.say(f"not signalled: {err}")
            return False
        return True

    # --- shared criteria ------------------------------------------------------------------------------

    def measure_back(self, before: Before, ended: Dict[str, int]) -> Dict[str, Optional[float]]:
        """Seconds from the injection until each ended session runs a new box."""
        back: Dict[str, Optional[float]] = {sid: None for sid in ended}
        deadline = self.t_inject + max(BACK_LIMIT_S * 3, 300.0)
        while time.time() < deadline and any(v is None for v in back.values()):
            status = self.status()
            now_boxes = self.boxes_now(status.holders) if status else {}
            for pid, (_start, sid) in now_boxes.items():
                if sid in back and back[sid] is None and pid != ended[sid]:
                    back[sid] = round(time.time() - self.t_inject, 1)
            time.sleep(1.0)
        return back

    def measure_reaped(self, pairs: Sequence[Tuple[int, int]]) -> Optional[float]:
        deadline = self.t_inject + REAP_LIMIT_S * 4
        while time.time() < deadline:
            if all(not self.procfs.alive(pid, start) for pid, start in pairs):
                return round(time.time() - self.t_inject, 1)
            time.sleep(0.5)
        return None

    def ended_sessions(self, before: Before) -> Dict[str, int]:
        """Always-on sessions whose box from before is gone: session id -> old box pid."""
        out: Dict[str, int] = {}
        for pid, (start, sid) in before.boxes.items():
            if sid and is_always_on(before.sessions.get(sid, "")) and not self.procfs.alive(pid, start):
                out[sid] = pid
        return out

    def c1(self, before: Before, store_may_change: bool = False) -> None:
        res = self.gc_run(["beads", "health", "--json"], timeout=120.0)
        doc = res.json()
        healthy = res.ok and (doc is None or doc.get("ok") is not False)
        if store_may_change:
            self.judge("C1", "store healthy (the drill restarts or stops the store by design)", {"health_exit": res.code}, healthy)
            return
        now = {(p, s) for p, s, _ in self.store_now()}
        kept = all((p, s) in now for p, s, _ in before.store)
        self.judge("C1", "store healthy and its pids unchanged", {"health_exit": res.code, "before": before.store, "kept": kept}, healthy and kept)

    def c2_c3(self, before: Before) -> Dict[str, int]:
        time.sleep(2.0)
        ended = self.ended_sessions(before)
        dead_incs = [i for i in self.incs() if i.inc in before.alive_incs and not i.alive]
        pairs = [pair for i in dead_incs for pair in i.bg]
        reaped = self.measure_reaped(pairs) if pairs else 0.0
        back = self.measure_back(before, ended)
        worst = max([v for v in back.values() if v is not None], default=0.0)
        all_back = all(v is not None for v in back.values())
        self.judge("C2", f"ended always-on sessions run again within {BACK_LIMIT_S:.0f} s", {"sessions": back, "max_s": worst}, all_back and worst <= BACK_LIMIT_S)
        self.judge(
            "C3",
            f"background children of ended incarnations gone within {REAP_LIMIT_S:.0f} s",
            {"children": len(pairs), "reaped_s": reaped},
            reaped is not None and reaped <= REAP_LIMIT_S,
        )
        return ended

    def settle(self) -> None:
        remaining = self.t_inject + self.settle_s - time.time()
        if remaining > 0:
            self.say(f"settling {remaining:.0f} s")
            time.sleep(remaining)

    def c4(self) -> None:
        status = self.status()
        orphans = find_orphans(self.snapshot(), status.holders if status else [], str(self.city.path), 0.0, self.uid)
        self.judge("C4", "no orphan after the settle window", [f"{p.pid} {p.comm} {' '.join(p.argv[:3])}" for p in orphans], not orphans)

    def c5(self, before: Before, sessions: Optional[Set[str]] = None) -> None:
        now = time.time()
        faults = read_jsonl(self.city.file("faults.jsonl"))
        turns = first_turns(self.incs(), faults, now)
        new = [t for t in turns if t.boot_t >= self.t_inject and (sessions is None or t.session_id in sessions)]
        bad_new = [f"{t.session_id} {t.status}" for t in new if t.status not in (FT_EXACT, FT_PENDING)]
        survivors = [t for t in turns if t.inc in before.alive_incs and t.status == FT_DUPLICATED]
        self.judge(
            "C5",
            "every new incarnation has exactly one first turn; no survivor got a second",
            {"new": len(new), "bad_new": bad_new, "survivors_duplicated": [t.session_id for t in survivors]},
            not bad_new and not survivors,
        )

    def c6(self, before: Before) -> None:
        core = self.core_tuple()
        foreign = foreign_hc(hc_runtime(self.snapshot()), core.state_home, core.session)
        refusals = sorted(line for line in self.supervisor_lines() - before.supervisor_lines if FOREIGN_REFUSAL in line)
        self.judge(
            "C6",
            "no foreign hc runtime; no start refused as started outside the pack",
            {"foreign": [f"{h.role} {h.pid}" for h in foreign], "refusals": refusals[:5]},
            not foreign and not refusals,
        )

    def boxes_unchanged(self, before: Before, what: str = "every box unchanged") -> None:
        gone = [pid for pid, (start, _sid) in before.boxes.items() if not self.procfs.alive(pid, start)]
        self.judge("boxes", what, {"before": len(before.boxes), "gone": gone}, not gone)

    def herdr_status(self) -> str:
        res = self.gc_run(["herdr-core", "status"], timeout=120.0)
        return str(res.out)

    def pick_steady(self, before: Before) -> str:
        steady = sorted(sid for sid, tmpl in before.sessions.items() if tmpl == STEADY or tmpl.endswith("/" + STEADY))
        if not steady:
            raise DrillError("no running soak-steady session")
        state = self.city.file("drill-agent-last")
        last = state.read_text(encoding="utf-8").strip() if state.exists() else ""
        choice = next((s for s in steady if s > last), steady[0])
        write_atomic(state, choice + "\n")
        return choice

    # --- the drills ---------------------------------------------------------------------------------

    def run(self) -> Rec:
        method = getattr(self, "drill_" + self.name.replace("-", "_"), None)
        if method is None:
            raise DrillError(f"unknown drill {self.name!r}; one of {', '.join(DRILLS)}")
        started = time.time()
        before = None if self.name == "reboot-verify" else self.before()
        if before is not None:
            self.say(f"before: core {before.core.pid if before.core else None}, {len(before.boxes)} boxes, {len(before.store)} store pids")
        method(before)
        verdict = all(c.passed is not False for c in self.criteria)
        rec: Rec = {
            "drill": self.name,
            "t_start": started,
            "t_inject": self.t_inject,
            "t_end": time.time(),
            "before": None if before is None else before.as_rec(),
            "criteria": [c.as_rec() for c in self.criteria],
            "notes": self.notes,
            "verdict": "pass" if verdict else "fail",
        }
        return rec

    def inject_agent_kill(self, before: Before, kind: str = "drill-agent-kill") -> str:
        sid = self.pick_steady(before)
        self.t_inject = time.time()
        rec = kill_agent(self.city, sid, self.procfs, kind, note=f"drill {self.name}")
        if rec.get("kind") != kind:
            raise DrillError(f"agent-kill: {rec.get('why')}")
        self.say(f"killed {sid} pid {rec['pids'][0]}")
        return sid

    def drill_agent_kill(self, before: Before) -> None:
        sid = self.inject_agent_kill(before)
        self.c2_c3(before)
        self.settle()
        self.c4()
        self.c5(before, {sid})

    def drill_place_store(self, before: Before) -> None:
        sid = self.pick_steady(before)
        landed = False
        attempts: List[Rec] = []
        for attempt in range(3):
            store = store_procs(self.snapshot(), self.uid)
            proxies = [p for p in store if p.argv1 == "db-proxy-child"]
            if not proxies:
                raise DrillError("place-store: no store proxy runs")
            proxy = proxies[0]
            dolts = [p for p in store if p.ppid == proxy.pid]
            pairs = " ".join(f"{p.pid} {p.start}" for p in [proxy, *dolts])
            agent = self.agent_cgroup(sid)
            (self.city.cmd).mkdir(mode=0o700, exist_ok=True)
            write_atomic(self.city.cmd / f"{sid}.cmd", f"bd-touch-after {pairs}\n")
            if attempt == 0:
                self.t_inject = time.time()
            self.fault("drill-store-term", ["store"], pids=[proxy.pid] + [d.pid for d in dolts], attempt=attempt + 1)
            self.kill(proxy.pid, proxy.start, signal.SIGTERM, self.store_owner())
            time.sleep(30.0)
            for dolt in dolts:
                if self.procfs.alive(dolt.pid, dolt.start):
                    self.notes.append(f"attempt {attempt + 1}: Dolt {dolt.pid} outlived its proxy by 30 s; SIGTERM")
                    self.kill(dolt.pid, dolt.start, signal.SIGTERM, self.store_owner())
            new = self.wait_new_store({proxy.pid, *(d.pid for d in dolts)}, 90.0)
            where = [{"pid": p.pid, "comm": p.comm, "unit": unit_of(p.cgroup), "cgroup": p.cgroup, "hc_scope": "HC_SCOPE" in p.env} for p in new]
            attempts.append({"attempt": attempt + 1, "agent_cgroup": agent, "new_store": where})
            if new and agent and all(p.cgroup == agent for p in new):
                landed = True
                break
        new_store = store_procs(self.snapshot(), self.uid)
        write_atomic(self.city.file("f1-store.json"), json.dumps([[p.pid, p.start] for p in new_store]) + "\n")
        clean = all("HC_SCOPE" not in p.env and "gascity-agents.slice" in p.cgroup.split("/") for p in new_store)
        if landed:
            self.judge("F1", "the new store runs in the agent's run-*.scope under gascity-agents.slice without HC_SCOPE", attempts, clean)
        else:
            self.notes.append("the controller restarted the store first every time; F2/F3 run on the controller-placed store")
            self.judge("F1", "store placement (controller-placed: recorded)", attempts, None)
        self.c1(before, store_may_change=True)
        self.settle()
        self.c4()
        self.c6(before)

    def agent_cgroup(self, sid: str) -> str:
        for inc in reversed(self.incs()):
            if inc.session_id == sid and inc.alive:
                info = self.procfs.info(inc.pid)
                return info.cgroup if info else ""
        return ""

    def wait_new_store(self, old: Set[int], timeout: float) -> List[ProcInfo]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            new = [p for p in store_procs(self.snapshot(), self.uid) if p.pid not in old]
            if any(p.argv1 == "db-proxy-child" for p in new) and len(new) >= 2:
                return new
            time.sleep(1.0)
        return [p for p in store_procs(self.snapshot(), self.uid) if p.pid not in old]

    def f1_store_kept(self) -> None:
        path = self.city.file("f1-store.json")
        if not path.exists():
            self.judge("F1-store", "the store placed in F1 runs unchanged", "no F1 record", None)
            return
        pairs = [tuple(p) for p in json.loads(path.read_text(encoding="utf-8"))]
        kept = all(self.procfs.alive(int(p[0]), int(p[1])) for p in pairs)
        self.judge("F1-store", "the store placed in F1 runs unchanged", pairs, kept)

    def holder_kill(self, before: Before, cgroup_wide: bool) -> None:
        if before.core is None or not before.core.holders:
            raise DrillError("no holders to kill")
        snap = self.snapshot()
        self.t_inject = time.time()
        self.fault("drill-holder-kill", ["holder", "boxes"], pids=list(before.core.holders), all=True)
        for pid in before.core.holders:
            info = snap.get(pid)
            if info is None:
                continue
            if cgroup_wide:
                unit = unit_of(info.cgroup) or ""
                if not (unit.startswith("hc-hold-") and unit.endswith((".service", ".scope"))):
                    raise DrillError(f"holder {pid} runs in {unit!r}, not one hc-hold-* unit")
                if self.hc_owner("hold")(pid) is not None:
                    raise DrillError(f"holder {pid} is not this city's")
                res = run(["systemctl", "--user", "kill", "--kill-whom=all", "--signal=SIGKILL", "--", unit], timeout=60.0)
                self.notes.append(f"systemctl kill {unit}: exit {res.code}")
            else:
                self.kill(pid, info.start, signal.SIGKILL, self.hc_owner("hold"))
        self.c2_c3(before)
        self.f1_store_kept()
        self.judge("controller", "the controller pid is unchanged", {"before": before.supervisor_pid, "now": self.supervisor_pid()}, before.supervisor_pid == self.supervisor_pid())
        self.c1(before)
        self.settle()
        self.c4()
        self.c5(before)
        self.c6(before)

    def drill_holder_kill(self, before: Before) -> None:
        self.holder_kill(before, cgroup_wide=False)

    def drill_holder_unit_kill(self, before: Before) -> None:
        self.holder_kill(before, cgroup_wide=True)

    def drill_core_kill(self, before: Before) -> None:
        if before.core is None:
            raise DrillError("no core answers")
        info = self.procfs.info(before.core.pid)
        if info is None:
            raise DrillError("the core pid is gone")
        self.t_inject = time.time()
        self.fault("drill-core-kill", ["core"], pids=[before.core.pid])
        self.kill(before.core.pid, info.start, signal.SIGKILL, self.hc_owner("serve"))
        answered = wait_answers(self.rpc(), 120.0)
        self.judge("F4-answer", f"a core answers within {CORE_ANSWER_S:.0f} s", answered, answered is not None and answered <= CORE_ANSWER_S)
        self.boxes_unchanged(before, "no box ends")
        self.c1(before)
        self.settle()
        self.c4()
        self.c6(before)
        self.notes.append("run the agent-kill drill next: a later start must not be refused as foreign")

    def drill_core_restart(self, before: Before) -> None:
        if before.core is None:
            raise DrillError("no core answers")
        core = self.core_tuple()
        self.t_inject = time.time()
        self.fault("drill-core-restart", ["core"], pids=[before.core.pid])
        res = run([self.hc_bin(), "server", "restart"], env=hc_env(core, self.hc_bin(), os.environ), timeout=300.0)
        self.notes.append(f"hc server restart: exit {res.code}: {res.tail(300)}")
        wait_answers(self.rpc(), 60.0)
        after = self.status()
        self.boxes_unchanged(before)
        self.judge(
            "F5-core",
            "the core pid changed, its version did not",
            {"before": [before.core.pid, before.core.version], "after": None if after is None else [after.pid, after.version]},
            after is not None and after.pid != before.core.pid and after.version == before.core.version,
        )
        text = self.herdr_status()
        self.judge("F5-status", "gc herdr-core status says started: by the pack", _line(text, "started:"), "started:   by the pack" in text)
        self.c1(before)
        self.settle()
        self.c4()
        self.c6(before)

    def drill_hc_update(self, before: Before) -> None:
        core = self.core_tuple()
        self.t_inject = time.time()
        self.fault("drill-hc-update", [])
        res = run([self.hc_bin(), "update"], env=hc_env(core, self.hc_bin(), os.environ), timeout=300.0)
        self.judge("F7-exit", "hc update exits non-zero (the binary is read-only)", {"exit": res.code, "tail": res.tail(300)}, res.code != 0)
        text = self.herdr_status()
        self.judge("F7-installed", "gc herdr-core status still says the install matches the pin", _line(text, "installed:"), "(matches the pin)" in text)
        after = self.status()
        same = after is not None and before.core is not None and (after.pid, after.version) == (before.core.pid, before.core.version)
        self.judge("F7-core", "the core's version and pid unchanged", None if after is None else [after.pid, after.version], same)
        self.boxes_unchanged(before)

    def drill_upgrade(self, before: Before) -> None:
        pin = self.paths.pack / "assets" / "hc-pin.json"
        self.t_inject = time.time()
        self.fault("drill-upgrade", ["core"])
        write_atomic(pin, json.dumps(PIN_0_1_20, indent=2) + "\n", mode=0o644)
        res = self.gc_run(["herdr-core", "upgrade"], timeout=900.0)
        out = res.out + res.err
        self.judge("F8-handover", "gc herdr-core upgrade hands the core over with its sessions running", {"exit": res.code, "tail": out[-400:]}, res.ok and UPGRADE_LINE in out)
        self.boxes_unchanged(before)
        text = self.herdr_status()
        self.judge(
            "F8-status",
            f"gc herdr-core status runs {UPGRADE_VERSION}, started by the pack",
            [_line(text, "running:"), _line(text, "started:")],
            f"herdr-core {UPGRADE_VERSION}" in _line(text, "running:") and "started:   by the pack" in text,
        )
        self.settle()
        sub = self.before()
        self.say("agent kill under the upgraded core")
        sid = self.inject_agent_kill(sub)
        self.c2_c3(sub)
        self.settle()
        self.c4()
        self.c5(sub, {sid})

    def drill_stop_wedged(self, before: Before) -> None:
        if before.core is None:
            raise DrillError("no core answers")
        info = self.procfs.info(before.core.pid)
        if info is None:
            raise DrillError("the core pid is gone")
        city = str(self.city.path)
        self.t_inject = time.time()
        self.fault("drill-stop-wedged", ["all"], all=True)
        self.kill(before.core.pid, info.start, signal.SIGSTOP, self.hc_owner("serve"))
        first = run([self.gc, "stop", city], timeout=900.0)
        self.kill(before.core.pid, info.start, signal.SIGCONT, self.hc_owner("serve"))
        self.judge("F9-first-stop", "the first stop exits non-zero and names the server teardown failure", {"exit": first.code, "tail": (first.out + first.err)[-400:]}, first.code != 0 and "teardown" in (first.out + first.err).lower())
        second = run([self.gc, "stop", city], timeout=900.0)
        left = remains(self.city, self.procfs, self.gc)
        self.judge("F9-second-stop", "the second stop prints City stopped. and exits 0; nothing of the city runs", {"exit": second.code, "remains": left}, second.ok and "City stopped." in second.out and not left)
        self.restore_pin()
        self.t_inject = time.time()
        start = run([self.gc, "start", city], timeout=900.0)
        self.notes.append(f"gc start: exit {start.code}")
        ended = {sid: pid for pid, (_s, sid) in before.boxes.items() if sid and is_always_on(before.sessions.get(sid, ""))}
        back = self.measure_back(before, ended)
        worst = max([v for v in back.values() if v is not None], default=0.0)
        self.judge("C2", "every always-on session back after gc start (measured from the start)", back, all(v is not None for v in back.values()))
        self.judge("C2-latency", "slowest session back (s)", worst, None)
        text = self.herdr_status()
        self.judge("F9-version", f"the core runs {HC_VERSION} again", _line(text, "running:"), f"herdr-core {HC_VERSION}" in _line(text, "running:"))
        self.c1(before, store_may_change=True)
        self.settle()
        self.c4()
        self.c5(before)

    def restore_pin(self) -> None:
        commit = (self.paths.home / "packs" / "runtime-herdr-core.COMMIT").read_text(encoding="utf-8").strip()
        res = run(["git", "-C", str(self.paths.live_src), "show", f"{commit}:runtime-herdr-core/assets/hc-pin.json"], timeout=60.0)
        if not res.ok:
            raise DrillError(f"cannot read the pinned hc-pin.json: {res.tail(300)}")
        write_atomic(self.paths.pack / "assets" / "hc-pin.json", res.out, mode=0o644)
        check = run(["sha256sum", "--quiet", "-c", "../runtime-herdr-core.SHA256SUMS"], cwd=str(self.paths.pack), timeout=120.0)
        self.judge("pack-restored", "the pack copy matches its SHA256SUMS again", {"exit": check.code, "tail": check.tail(300)}, check.ok)

    def drill_reboot(self, before: Before) -> None:
        """Records the state before a reboot; root reboots; ``reboot-verify`` measures."""
        self.t_inject = time.time()
        self.fault("drill-reboot", ["all"], all=True)
        write_atomic(self.city.file("drills/reboot-pending.json"), json.dumps(dict(before.as_rec(), t_inject=self.t_inject)) + "\n")
        self.notes.append("now reboot as root (systemctl reboot), then run `soak drill reboot-verify` as soak")
        self.judge("F10-prepared", "state before the reboot recorded", str(self.city.file("drills/reboot-pending.json")), None)

    def drill_reboot_verify(self, before: Optional[Before]) -> None:
        pending_path = self.city.file("drills/reboot-pending.json")
        if not pending_path.exists():
            raise DrillError("no reboot-pending.json: run `soak drill reboot` before the reboot")
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        self.t_inject = float(pending["t_inject"])
        sessions: Dict[str, str] = {str(k): str(v) for k, v in pending.get("sessions", {}).items()}
        wanted = {sid for sid, tmpl in sessions.items() if is_always_on(tmpl)}
        verify_start = time.time()
        deadline = verify_start + 600.0
        ok_running = False
        while time.time() < deadline:
            from soaksample import supervisor_state

            sup = supervisor_state()
            doc = self.gc_run(["status", "--json"], timeout=60.0).json() or {}
            running = set(self.sessions_now())
            if sup.get("active") == "active" and doc.get("running") and wanted <= running:
                ok_running = True
                break
            time.sleep(5.0)
        self.judge("F10-up", "within 10 minutes: the supervisor, the city and every configured session run", {"after_s": round(time.time() - verify_start, 1), "wanted": sorted(wanted)}, ok_running)
        time.sleep(200.0)  # let every new incarnation pass the first-turn window
        empty = Before(self.t_inject, None, {}, sessions, [], 0, set(), [], set())
        faults = read_jsonl(self.city.file("faults.jsonl"))
        turns = [t for t in first_turns(self.incs(), faults, time.time()) if t.boot_t >= self.t_inject and t.session_id in wanted]
        new_sessions = {t.session_id for t in turns}
        bad = [f"{t.session_id} {t.status}" for t in turns if t.status != FT_EXACT]
        self.judge("F10-turns", "each session has a new incarnation with exactly one first turn", {"missing": sorted(wanted - new_sessions), "bad": bad}, not bad and wanted <= new_sessions)
        self.c1(empty, store_may_change=True)
        self.c4()
        res = self.gc_run(["doctor", "--check", "exec-runtime-identity", "--check", "ownerless-runtimes", "--json"], timeout=600.0)
        doc = res.json() or {}
        self.judge("F10-doctor", "exec-runtime-identity and ownerless-runtimes clean", {"exit": res.code, "failed": doc.get("failed"), "warned": doc.get("warned")}, res.ok and not doc.get("failed"))
        self.c6(empty)
        pending_path.rename(pending_path.with_name(f"reboot-pending-{int(self.t_inject)}.done.json"))


def _line(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    return ""


def take_lock(city: City, name: str) -> Path:
    lock = city.file("DRILL")
    try:
        fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise DrillError(f"another drill holds {lock}: {lock.read_text(encoding='utf-8').strip()}") from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{name} pid {os.getpid()} since {iso(time.time())}\n")
    return lock


def drill_main(city: City, paths: SoakPaths, name: str, settle_s: float = SETTLE_S, gc: str = "gc") -> int:
    if name not in DRILLS:
        raise DrillError(f"unknown drill {name!r}; one of {', '.join(DRILLS)}")
    # The reboot drill keeps the lock across the reboot; reboot-verify releases it.
    lock = city.file("DRILL") if name == "reboot-verify" else take_lock(city, name)
    drill = Drill(name, city, paths, gc=gc, settle_s=settle_s)
    rec: Rec
    try:
        rec = drill.run()
    except DrillError as err:
        rec = {"drill": name, "t_inject": drill.t_inject, "criteria": [c.as_rec() for c in drill.criteria], "notes": drill.notes + [str(err)], "verdict": "error"}
    finally:
        keep = name == "reboot" and drill.t_inject > 0
        if not keep:
            try:
                lock.unlink()
            except OSError:
                pass
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(rec.get("t_inject") or time.time()))
    out = city.file("drills") / f"{name}-{stamp}.json"
    out.parent.mkdir(mode=0o700, exist_ok=True)
    write_atomic(out, json.dumps(rec, indent=2, sort_keys=True) + "\n")
    print(f"drill {name}: {rec['verdict']} ({out})")
    return 0 if rec["verdict"] == "pass" else 1


__all__ = ["DRILLS", "Drill", "DrillError", "PIN_0_1_20", "agent_owner", "city_cores", "drill_main", "take_lock"]
