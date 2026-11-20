"""``soak check``: the abort predicates (AP1 to AP9) and the warnings, every
five minutes, and the abort procedure on the first hit in ``abort`` mode.

The predicates in :data:`RECORD_ONLY` are judged and recorded but never hit:
over their limit they warn, with the numbers, and their unreadable inputs do
not count towards AP9.

:func:`evaluate` is pure: it judges one run's :class:`Inputs` against the
:class:`State` carried from the previous run. :func:`collect` gathers the
inputs from the city, the logs and the process table.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from soakanalysis import (
    ENDED_UNEXPECTED,
    FT_DUPLICATED,
    FT_LOST,
    FirstTurn,
    HcProc,
    NudgeVerdict,
    NUDGE_DUPLICATED,
    NUDGE_LOST,
    OpStats,
    city_cores,
    event_time,
    find_orphans,
    first_turns,
    foreign_hc,
    hc_runtime,
    incarnations,
    mean_boxes,
    mono_offset,
    nudge_verdicts,
    op_stats,
    parse_optrace,
    parse_ts,
    store_procs,
    supervisor_timeline,
)
from soakhc import HcError, HcRpc, core_tuple
from soaksample import supervisor_state
from soaklib import City, ProcFS, ProcInfo, Rec, SoakPaths, append_jsonl, iso, parse_jsonl, read_jsonl, run, write_atomic

CHECK_PERIOD_S = 300.0
HEALTH_TRIES = 3
HEALTH_SPACING_S = 30.0
INTEGRITY = re.compile(r"catalog|branch head|corrupt|checksum|integrity", re.IGNORECASE)
BUDGET_PER_SESSION = {"legacy": 0.30, "v2": 0.05}
CPU_BUDGET_PER_SESSION = 0.015
HC_STATE_LIMIT = 2 << 30
R_LIMIT = 4 << 30
WINDOW_S = 900.0
UNKNOWN_LIMIT = 3
AGENT_LOG_GRACE_S = 60.0
"""How long a live scripted agent may run before its incarnation must have a
``boot`` record in the agent logs: the agent writes it before it reads any input."""
SAMPLES_STALE_S = 180.0
TRACE_SILENT_S = 600.0
EVENTS_SILENT_S = 600.0
DRILL_PHASES = frozenset({"bringup", "v2-switch", "drills"})
BOX_RANGE = (10, 20)
HOURLY_S = 3600.0
DOCTOR_EVERY_S = 6 * 3600.0
WORKFLOW_IDLE_S = 1200.0
WORKFLOW_OPEN_S = 1800.0
WORKFLOW_KEEP_S = 2 * 86400.0
"""How long the tracker keeps a slung root (the whole 24-hour soak and its end)
and a root's close that no sling has claimed yet."""

OK, WARN, HIT = "OK", "WARN", "HIT"

RECORD_ONLY = frozenset({"AP5"})
"""Predicates that record and warn but never abort. Soak 1 (decision of
2026-11-17): the performance predicate AP5 is record-only; every correctness
predicate aborts."""


@dataclass(frozen=True)
class Finding:
    id: str
    reason: str


@dataclass
class State:
    """What one run hands the next (``check-state.json``)."""

    last_t: float = 0.0
    supervisor: Optional[List[int]] = None
    store: List[List[Any]] = field(default_factory=list)
    unknown: Dict[str, int] = field(default_factory=dict)
    supervisor_history: List[List[float]] = field(default_factory=list)
    controller_starts: List[float] = field(default_factory=list)
    events_offset: int = 0
    quarantined: int = 0
    core_pid: int = 0
    holders: List[int] = field(default_factory=list)
    last_digest_t: float = 0.0
    last_hourly_t: float = 0.0
    last_doctor_t: float = 0.0
    box_out_since: Optional[float] = None
    workflows: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    workflow_closes: Dict[str, float] = field(default_factory=dict)
    """Workflow roots' closes read from the events mirror and not yet matched
    to a sling: id -> the ``bead.closed`` event's time."""
    load_offset: int = 0
    aborted: bool = False
    stopped: bool = False
    """Set, and saved at once, when the abort's ``gc stop`` exits 0. Until
    then every check run after the abort runs ``gc stop`` again."""

    @classmethod
    def load(cls, path: Path) -> "State":
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {k: v for k, v in doc.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path) -> None:
        write_atomic(path, json.dumps(asdict(self), sort_keys=True) + "\n")


@dataclass
class Inputs:
    now: float
    phase: str
    phase_start: float
    reconciler: str
    drill: bool = False
    conformance: bool = False
    final: bool = False
    """``soak check --final``: AP4 judges every incarnation."""
    health: Optional[List[Tuple[bool, str]]] = None
    supervisor: Optional[Tuple[int, int]] = None
    store: Optional[List[Tuple[int, int, str]]] = None
    faults: List[Rec] = field(default_factory=list)
    controller_starts: Optional[List[float]] = None
    first_turns: Optional[List[FirstTurn]] = None
    """None when there is no agent-log directory to read."""
    unlogged_agents: List[str] = field(default_factory=list)
    """Live scripted agents of the city, running for :data:`AGENT_LOG_GRACE_S`
    or more, whose incarnation has no ``boot`` record in the agent logs."""
    ops: Optional[OpStats] = None
    sizes: Optional[Rec] = None
    hc: Optional[List[HcProc]] = None
    city_core: Optional[Tuple[str, str]] = None
    """``(XDG_STATE_HOME, HC_SESSION)`` of the city's core."""
    canary_hits: Optional[List[str]] = None
    """None when the hourly scan did not run this time."""
    samples_age_s: Optional[float] = None
    trace_age_s: Optional[float] = None
    events_age_s: Optional[float] = None
    boxes_now: int = 0
    probe_errors: int = 0
    # warnings
    orphans: Optional[List[str]] = None
    tmux_servers: int = 0
    box_count: Optional[int] = None
    nudges: List[NudgeVerdict] = field(default_factory=list)
    core_pid: int = 0
    holders: Optional[List[int]] = None
    stale_spawn_files: List[str] = field(default_factory=list)
    mem_avail_kib: Optional[int] = None
    disk_free_bytes: Optional[int] = None
    doctor_failed: Optional[int] = None
    load_running: bool = False
    last_workflow_closed: Optional[float] = None
    oldest_slung_open: Optional[float] = None
    workflows_open_30m: int = 0


@dataclass
class Outcome:
    t: float
    phase: str
    mode: str
    hits: List[Finding] = field(default_factory=list)
    warnings: List[Finding] = field(default_factory=list)
    unknown: Dict[str, str] = field(default_factory=dict)
    perf: Optional[Rec] = None
    """AP5's measured values and limits, whenever it was judged."""

    def judge(self, finding: Finding) -> None:
        """A predicate's finding: a hit, or a warning when it is record-only."""
        if finding.id in RECORD_ONLY:
            self.warnings.append(Finding(finding.id, "record-only: " + finding.reason))
        else:
            self.hits.append(finding)

    @property
    def status(self) -> str:
        if self.hits:
            return HIT
        return WARN if self.warnings or self.unknown else OK

    def line(self) -> str:
        if self.hits:
            items = self.hits
        else:
            items = self.warnings + [Finding(k, f"cannot evaluate: {v}") for k, v in sorted(self.unknown.items())]
        ids = ",".join(dict.fromkeys(f.id for f in items)) or "-"
        reason = "; ".join(f"{f.id}: {f.reason}" for f in items) or "all predicates pass"
        return f"{iso(self.t)} {self.phase} {self.status} {ids} {reason}"

    def as_rec(self) -> Rec:
        return {
            "t": self.t,
            "phase": self.phase,
            "mode": self.mode,
            "status": self.status,
            "hits": [asdict(f) for f in self.hits],
            "warnings": [asdict(f) for f in self.warnings],
            "unknown": self.unknown,
            "perf": self.perf,
        }


def fault_covers(fault: Rec, what: str, t0: float, t1: float) -> bool:
    t = fault.get("t")
    if not isinstance(t, (int, float)) or not (t0 <= t <= t1):
        return False
    covers = fault.get("covers") or []
    return what in covers or "all" in covers


def first_turn_cutoff(inp: Inputs, state: State) -> float:
    """AP4 judges a lost or duplicated first turn whose verdict came at or after this.

    A verdict belongs to the phase it comes in, whatever phase its incarnation
    booted in: a survivor's second first turn after the switch, or a loss that
    matures after it, is the new phase's. A run also judges what came since the
    previous run, so a verdict between the last run of one phase and the start
    of the next is judged once. ``--final`` judges every incarnation.
    """
    if inp.final:
        return float("-inf")
    if state.last_t:
        return min(inp.phase_start, state.last_t)
    return inp.phase_start


def judged_first_turns(turns: Sequence[FirstTurn], cutoff: float) -> List[FirstTurn]:
    """The lost or duplicated first turns whose verdict came at or after
    ``cutoff``; one without a verdict time is judged too."""
    return [ft for ft in turns if ft.status in (FT_LOST, FT_DUPLICATED) and (ft.verdict_t is None or ft.verdict_t >= cutoff)]


def evaluate(inp: Inputs, state: State, mode: str) -> Outcome:
    """Judge one run. ``state`` is updated in place for the next run."""
    out = Outcome(t=inp.now, phase=inp.phase, mode=mode)
    since = state.last_t - 60.0 if state.last_t else inp.now - CHECK_PERIOD_S - 60.0

    def unknown(pid: str, why: str) -> None:
        out.unknown[pid] = why

    # AP1 store outage or integrity error
    if inp.health is None:
        unknown("AP1", "gc beads health did not run")
    else:
        failures = [text for ok, text in inp.health if not ok]
        integrity = [t for t in failures if INTEGRITY.search(t)]
        if integrity:
            out.hits.append(Finding("AP1", f"store integrity error: {integrity[0][:200]}"))
        elif len(failures) >= HEALTH_TRIES and not any(ok for ok, _ in inp.health):
            out.hits.append(Finding("AP1", f"{len(failures)} consecutive store health failures: {failures[-1][:200]}"))

    # AP2 an infrastructure process killed
    if inp.supervisor is None or inp.store is None:
        unknown("AP2", "infrastructure pids unreadable")
    elif not inp.drill:
        gone: List[str] = []
        if state.supervisor and inp.supervisor and list(inp.supervisor) != state.supervisor:
            if not any(fault_covers(f, "supervisor", since, inp.now) for f in inp.faults):
                gone.append(f"supervisor pid {state.supervisor[0]}")
        current = {(p, s) for p, s, _ in inp.store}
        for pid, start, label in state.store:
            if (pid, start) not in current and not any(fault_covers(f, "store", since, inp.now) for f in inp.faults):
                gone.append(f"{label} pid {pid}")
        if gone:
            out.hits.append(Finding("AP2", "gone with no fault record covering it: " + ", ".join(gone)))
    if inp.supervisor is not None:
        if state.supervisor is None or list(inp.supervisor) != state.supervisor:
            state.supervisor_history.append([inp.now, float(inp.supervisor[0])])
        state.supervisor = list(inp.supervisor)
    if inp.store is not None:
        state.store = [[p, s, label] for p, s, label in inp.store]
    state.supervisor_history = [h for h in state.supervisor_history if h[0] >= inp.now - 3600.0]

    # AP3 controller crash loop
    window0 = inp.now - WINDOW_S
    if inp.controller_starts is None:
        unknown("AP3", "no controller.started events readable")
    else:
        by_events = sum(1 for t in inp.controller_starts if t >= window0)
        by_pid = sum(1 for i, h in enumerate(state.supervisor_history) if i > 0 and h[0] >= window0)
        excused = sum(1 for f in inp.faults if fault_covers(f, "controller", window0, inp.now))
        starts = max(by_events, by_pid) - excused
        if starts > 3:
            out.hits.append(Finding("AP3", f"{starts} unexplained controller starts in 15 minutes"))

    # AP4 a lost or duplicated first turn
    if inp.first_turns is None:
        unknown("AP4", "no agent-log directory")
    else:
        bad = judged_first_turns(inp.first_turns, first_turn_cutoff(inp, state))
        if bad:
            desc = ", ".join(f"{ft.session_id} {ft.status}" for ft in bad[:5])
            out.hits.append(Finding("AP4", f"{len(bad)} first turn(s) lost or duplicated: {desc}"))
        if inp.unlogged_agents:
            names = ", ".join(inp.unlogged_agents[:5])
            unknown("AP4", f"{len(inp.unlogged_agents)} live scripted agent(s) with no agent log: {names}")

    # AP5 pack cost
    if inp.ops is None:
        unknown("AP5", "no op trace or samples for the window")
    elif inp.reconciler in BUDGET_PER_SESSION and not inp.drill:
        n = max(1.0, inp.ops.sessions)
        limit = 2 * BUDGET_PER_SESSION[inp.reconciler] * n
        cpu_limit = 2 * CPU_BUDGET_PER_SESSION * n
        out.perf = {
            "reconciler": inp.reconciler,
            "n": n,
            "rate_ctl": inp.ops.rate_ctl,
            "rate_limit": limit,
            "ctl_cpu_cores": inp.ops.ctl_cpu_cores,
            "cpu_limit": cpu_limit,
            "record_only": "AP5" in RECORD_ONLY,
        }
        if inp.ops.rate_ctl > limit:
            out.judge(
                Finding("AP5", f"controller-spawned ops {inp.ops.rate_ctl:.3f}/s over {limit:.3f}/s ({inp.reconciler}, n={n:.1f})")
            )
        elif inp.ops.ctl_cpu_cores > cpu_limit:
            out.judge(Finding("AP5", f"controller-spawned op CPU {inp.ops.ctl_cpu_cores:.3f} cores over {cpu_limit:.3f} (n={n:.1f})"))

    # AP6 state size: each size on its own; one the sample lacks makes AP6
    # unknown, even next to a hit on the other
    if inp.sizes is None:
        unknown("AP6", "no size sample")
    else:
        lacking: List[str] = []
        for key, name, limit in (("hc_state", "hc state directory", HC_STATE_LIMIT), ("R", "R", R_LIMIT)):
            size = inp.sizes.get(key)
            if not isinstance(size, int):
                lacking.append(name)
            elif size > limit:
                out.hits.append(Finding("AP6", f"{name} {size} bytes"))
        if lacking:
            unknown("AP6", "size sample lacks " + " and ".join(lacking))

    # AP7 an unexpected core or holder
    if inp.hc is None or inp.city_core is None:
        unknown("AP7", "hc runtime or the city's core tuple unreadable")
    else:
        state_home, session = inp.city_core
        foreign = [] if inp.conformance else foreign_hc(inp.hc, state_home, session)
        cores = city_cores(inp.hc, state_home, session)
        if foreign:
            out.hits.append(
                Finding("AP7", "foreign hc runtime: " + ", ".join(f"{h.role} pid {h.pid} ({h.state_home} {h.session})" for h in foreign))
            )
        if len(cores) > 1:
            out.hits.append(Finding("AP7", "two cores of the city: " + ", ".join(str(h.pid) for h in cores)))

    # AP8 a secret on disk
    if inp.canary_hits:
        out.hits.append(Finding("AP8", "the canary is on disk: " + ", ".join(inp.canary_hits[:5])))

    # AP9 the harness cannot see
    if inp.samples_age_s is None or inp.samples_age_s > SAMPLES_STALE_S:
        unknown("samples", f"last sample {inp.samples_age_s if inp.samples_age_s is not None else 'never'} s ago")
    if inp.boxes_now > 0 and (inp.trace_age_s is None or inp.trace_age_s > TRACE_SILENT_S):
        unknown("trace", "op trace silent for 10 minutes while boxes run")
    if inp.events_age_s is None or inp.events_age_s > EVENTS_SILENT_S:
        unknown("events", "events mirror silent for 10 minutes")
    if inp.probe_errors:
        unknown("probe", f"{inp.probe_errors} failed probe(s)")
    for key in list(state.unknown):
        if key not in out.unknown or key in RECORD_ONLY:
            del state.unknown[key]
    for key in out.unknown:
        if key not in RECORD_ONLY:
            state.unknown[key] = state.unknown.get(key, 0) + 1
    blind = sorted(k for k, n in state.unknown.items() if n >= UNKNOWN_LIMIT)
    if blind:
        out.hits.append(Finding("AP9", "cannot evaluate on 3 consecutive runs: " + ", ".join(f"{k} ({out.unknown[k]})" for k in blind)))

    # warnings
    warn = out.warnings.append
    if inp.orphans:
        warn(Finding("W-orphans", f"{len(inp.orphans)} orphan(s) older than 10 minutes: {', '.join(inp.orphans[:5])}"))
    if inp.tmux_servers:
        warn(Finding("W-tmux", f"{inp.tmux_servers} tmux server(s) of this user"))
    if inp.box_count is not None and inp.phase not in DRILL_PHASES:
        lo, hi = BOX_RANGE
        if inp.box_count < lo or inp.box_count > hi:
            state.box_out_since = state.box_out_since or inp.now
            if inp.now - state.box_out_since >= WINDOW_S:
                warn(Finding("W-boxes", f"{inp.box_count} live boxes for 15 minutes (want {lo} to {hi})"))
        else:
            state.box_out_since = None
    if inp.load_running and inp.oldest_slung_open is not None and inp.now - inp.oldest_slung_open >= WORKFLOW_IDLE_S:
        if inp.last_workflow_closed is None or inp.now - inp.last_workflow_closed >= WORKFLOW_IDLE_S:
            warn(Finding("W-workflows", "no workflow root closed in 20 minutes while load runs"))
    if inp.workflows_open_30m:
        warn(Finding("W-workflows-open", f"{inp.workflows_open_30m} workflow(s) open after 30 minutes"))
    lost = [n for n in inp.nudges if n.status in (NUDGE_LOST, NUDGE_DUPLICATED)]
    if lost:
        warn(Finding("W-nudges", ", ".join(f"{n.nonce[:8]} {n.status}" for n in lost[:5])))
    covered_core = any(fault_covers(f, "core", since, inp.now) for f in inp.faults)
    covered_holder = any(fault_covers(f, "holder", since, inp.now) for f in inp.faults)
    if inp.core_pid and state.core_pid and inp.core_pid != state.core_pid and not covered_core and not inp.drill:
        warn(Finding("W-core", f"core restarted unexplained ({state.core_pid} -> {inp.core_pid})"))
    if inp.holders is not None:
        lost_holders = sorted(set(state.holders) - set(inp.holders))
        if lost_holders and not covered_holder and not covered_core and not inp.drill:
            warn(Finding("W-holder", f"holder(s) lost unexplained: {lost_holders}"))
        state.holders = list(inp.holders)
    if inp.core_pid:
        state.core_pid = inp.core_pid
    if inp.ops is not None:
        unexpected = [(cls, op, n) for cls in ENDED_UNEXPECTED for op, n in sorted(inp.ops.ended_by.get(cls, {}).items())]
        if unexpected:
            total = sum(n for _cls, _op, n in unexpected)
            named = ", ".join(f"{cls} {op} x{n}" for cls, op, n in unexpected)
            warn(Finding("W-op-signal", f"{total} op(s) ended by a signal gc does not send by design in 15 minutes: {named}"))
    if inp.stale_spawn_files:
        warn(Finding("W-spawn-files", f"{len(inp.stale_spawn_files)} spawn file(s) older than 5 minutes"))
    if inp.mem_avail_kib is not None and inp.mem_avail_kib < (1 << 20):
        warn(Finding("W-memory", f"memory available {inp.mem_avail_kib // 1024} MiB"))
    if inp.disk_free_bytes is not None and inp.disk_free_bytes < (10 << 30):
        warn(Finding("W-disk", f"free disk {inp.disk_free_bytes >> 30} GiB"))
    if inp.doctor_failed:
        warn(Finding("W-doctor", f"gc doctor reports {inp.doctor_failed} failed check(s)"))
    state.last_t = inp.now
    return out


# --- collection --------------------------------------------------------------------------------


def read_tail_lines(path: Path, max_bytes: int) -> List[str]:
    """The whole lines in the last ``max_bytes`` of ``path``."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            data = handle.read()
    except OSError:
        return []
    lines = data.decode("utf-8", "replace").split("\n")
    if start > 0:
        lines = lines[1:]
    return [line for line in lines if line]


def read_new_lines(path: Path, offset: int) -> Tuple[List[str], int]:
    """Whole lines appended after ``offset``; the new offset (0 again if the file shrank)."""
    try:
        size = path.stat().st_size
    except OSError:
        return [], offset
    if size < offset:
        offset = 0
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read()
    end = data.rfind(b"\n")
    if end < 0:
        return [], offset
    return data[: end + 1].decode("utf-8", "replace").splitlines(), offset + end + 1


def mtime_age(path: Path, now: float) -> Optional[float]:
    try:
        return now - path.stat().st_mtime
    except OSError:
        return None


def phase_info(city: City) -> Tuple[str, float, str]:
    phases = read_jsonl(city.file("phases.jsonl"))
    if not phases:
        return "", 0.0, ""
    last = phases[-1]
    return str(last.get("phase", "")), float(last.get("t", 0.0)), str(last.get("reconciler", ""))


def alive_by_proc(procfs: ProcFS) -> Callable[[str], bool]:
    boot = procfs.boot_id()[:8]

    def alive(inc: str) -> bool:
        parts = inc.split(":")
        if len(parts) != 3 or parts[0] != boot:
            return False
        stat = procfs.stat(int(parts[1]))
        return stat is not None and stat.start == int(parts[2]) and stat.comm == "soak-agent" and not stat.state.startswith("Z")

    return alive


def agent_records(city: City) -> Dict[str, List[Rec]]:
    out: Dict[str, List[Rec]] = {}
    for path in sorted(city.agents.glob("*.jsonl")):
        out[path.stem] = read_jsonl(path)
    return out


def unlogged_agents(
    snap: Mapping[int, ProcInfo], city_path: str, logged: Iterable[str], boot: str, grace_s: float = AGENT_LOG_GRACE_S
) -> List[str]:
    """``<session> pid <pid>`` of every scripted agent of the city (command name
    ``soak-agent``, the city's ``GC_CITY_PATH``) running for ``grace_s`` or more
    whose ``inc`` (``<boot>:<pid>:<start ticks>``) is not in ``logged``."""
    seen = set(logged)
    return [
        f"{p.env.get('GC_SESSION_ID') or '?'} pid {p.pid}"
        for p in sorted(snap.values(), key=lambda q: q.pid)
        if p.comm == "soak-agent"
        and p.env.get("GC_CITY_PATH") == city_path
        and p.age_s >= grace_s
        and f"{boot}:{p.pid}:{p.start}" not in seen
    ]


def canary_scan(roots: Iterable[Path], canary: str) -> List[str]:
    """Regular files under ``roots`` that contain ``canary``."""
    needle = canary.encode("utf-8")
    hits: List[str] = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, _dirs, files in os.walk(str(root)):
            for name in files:
                path = os.path.join(dirpath, name)
                try:
                    if not os.path.isfile(path) or os.path.islink(path):
                        continue
                    with open(path, "rb") as handle:
                        tail = b""
                        while True:
                            chunk = handle.read(1 << 20)
                            if not chunk:
                                break
                            if needle in tail + chunk:
                                hits.append(path)
                                break
                            tail = chunk[-len(needle) :]
                except OSError:
                    continue
    return hits


def health_runs(city: City, gc: str, sleep: Callable[[float], None] = time.sleep) -> List[Tuple[bool, str]]:
    results: List[Tuple[bool, str]] = []
    for attempt in range(HEALTH_TRIES):
        res = run([gc, "beads", "health", "--json"], cwd=str(city.path), timeout=60.0)
        doc = res.json()
        ok = res.ok and (doc is None or doc.get("ok") is not False)
        results.append((ok, "" if ok else (res.out + res.err)[-1500:]))
        if ok or INTEGRITY.search(results[-1][1]):
            break
        if attempt + 1 < HEALTH_TRIES:
            sleep(HEALTH_SPACING_S)
    return results


def doctor_failed(doc: Optional[Rec]) -> Optional[int]:
    if doc is None:
        return None
    failed = doc.get("failed")
    return failed if isinstance(failed, int) else None


@dataclass
class Collector:
    city: City
    paths: SoakPaths
    procfs: ProcFS = field(default_factory=ProcFS)
    gc: str = "gc"

    def collect(self, state: State, final: bool = False) -> Inputs:
        now = time.time()
        city = self.city
        uid = os.getuid()
        phase, phase_start, reconciler = phase_info(city)
        inp = Inputs(now=now, phase=phase, phase_start=phase_start, reconciler=reconciler, final=final)
        inp.drill = city.flag("DRILL")
        inp.conformance = city.flag("CONFORMANCE")
        inp.faults = read_jsonl(city.file("faults.jsonl"))
        inp.health = health_runs(city, self.gc)
        snap = self.procfs.snapshot(uid)
        sup = supervisor_state()
        sup_stat = self.procfs.stat(sup["pid"]) if sup["pid"] else None
        inp.supervisor = (sup["pid"], sup_stat.start) if sup_stat is not None else None
        if sup["pid"] == 0 and sup.get("active") in ("inactive", "failed"):
            inp.supervisor = (0, 0)
        inp.store = [(p.pid, p.start, p.argv1 or p.comm) for p in store_procs(snap, uid)]
        # events: incremental
        lines, state.events_offset = read_new_lines(city.events, state.events_offset)
        events = parse_jsonl(lines)
        state.workflow_closes.update(workflow_closures(events))
        for event in events:
            t = parse_ts(str(event.get("ts", ""))) or now
            if event.get("type") == "controller.started":
                state.controller_starts.append(t)
            elif event.get("type") == "session.quarantined":
                state.quarantined += 1
        state.controller_starts = [t for t in state.controller_starts if t >= now - 3600.0]
        inp.controller_starts = list(state.controller_starts) if city.events.exists() else None
        # first turns, nudges
        records = agent_records(city)
        alive = alive_by_proc(self.procfs)
        incs = incarnations((r for recs in records.values() for r in recs), alive)
        if city.agents.is_dir():
            inp.first_turns = first_turns(incs, inp.faults, now)
            boot = self.procfs.boot_id()[:8]
            inp.unlogged_agents = unlogged_agents(snap, str(city.path), (i.inc for i in incs), boot)
        inputs_by_session: Dict[str, List[Rec]] = {}
        for sid, recs in records.items():
            inputs_by_session[sid] = [r for r in recs if r.get("ev") == "in"]
        load_recs = parse_jsonl(read_tail_lines(city.file("load.jsonl"), 4 << 20))
        inp.nudges = [n for n in nudge_verdicts(load_recs, inputs_by_session, now) if n.t >= now - 3600.0]
        # ops
        samples = parse_jsonl(read_tail_lines(city.file("samples.jsonl"), 2 << 20))
        offset = mono_offset(samples)
        if offset is not None:
            runs, _ = parse_optrace(read_tail_lines(self.paths.optrace, 8 << 20))
            inp.ops = op_stats(runs, offset, now - WINDOW_S, now, supervisor_timeline(samples), mean_boxes(samples, now - WINDOW_S, now))
        inp.samples_age_s = now - float(samples[-1]["t"]) if samples else None
        sized = [s for s in samples if isinstance(s.get("sizes"), dict)]
        inp.sizes = sized[-1]["sizes"] if sized else None
        if sized:
            inp.mem_avail_kib = sized[-1].get("mem_avail_kib")
            inp.disk_free_bytes = sized[-1].get("disk_free_bytes")
        inp.trace_age_s = mtime_age(self.paths.optrace, now)
        inp.events_age_s = mtime_age(city.events, now)
        recent = [s for s in samples if float(s.get("t", 0)) >= now - 180.0]
        inp.box_count = len(recent[-1].get("boxes") or []) if recent else None
        inp.boxes_now = inp.box_count or 0
        inp.probe_errors = sum(
            1 for f in inp.faults if f.get("kind") == "probe-kill-error" and float(f.get("t", 0)) >= (state.last_t or now - CHECK_PERIOD_S)
        )
        # hc
        inp.hc = hc_runtime(snap)
        try:
            core = core_tuple(str(city.path), self.gc)
            inp.city_core = (core.state_home, core.session)
            try:
                status = HcRpc(core.socket).status()
                inp.core_pid = status.pid
                inp.holders = list(status.holders)
            except HcError:
                pass
        except HcError:
            inp.city_core = None
        inp.tmux_servers = sum(1 for p in snap.values() if p.comm.startswith("tmux"))
        spawn_dir = Path(f"/run/user/{uid}/gc-herdr-core")
        if spawn_dir.is_dir():
            inp.stale_spawn_files = [
                str(p) for p in spawn_dir.rglob("*") if p.is_file() and mtime_age(p, now) is not None and (mtime_age(p, now) or 0) > 300
            ]
        # hourly: canary, orphans
        if final or now - state.last_hourly_t >= HOURLY_S:
            state.last_hourly_t = now
            canary = city.file("canary").read_text(encoding="utf-8").strip() if city.file("canary").exists() else ""
            if canary:
                inp.canary_hits = canary_scan(
                    [self.paths.state_root, self.paths.hc_share, Path(f"/tmp/gc-herdr-core-{uid}")], canary
                )
            orphans = find_orphans(snap, inp.holders or [], str(city.path), 600.0, uid)
            inp.orphans = [f"{p.pid} {p.comm}" for p in orphans]
        # doctor every 6 hours in the soak
        if phase.startswith("soak") and (final or now - state.last_doctor_t >= DOCTOR_EVERY_S):
            state.last_doctor_t = now
            res = run([self.gc, "doctor", "--json"], cwd=str(city.path), timeout=600.0)
            inp.doctor_failed = doctor_failed(res.json())
        # workflows
        self.track_workflows(state, now)
        inp.load_running = not city.flag("PAUSE") and any(
            float(r.get("t", 0)) >= now - 600.0 and str(r.get("action", "")).startswith("sling") for r in load_recs
        )
        closed = [w["closed_t"] for w in state.workflows.values() if w.get("closed_t")]
        inp.last_workflow_closed = max(closed) if closed else None
        open_ = [w["t"] for w in state.workflows.values() if not w.get("closed_t")]
        inp.oldest_slung_open = min(open_) if open_ else None
        inp.workflows_open_30m = sum(1 for t in open_ if now - t >= WORKFLOW_OPEN_S)
        return inp

    def track_workflows(self, state: State, now: float) -> None:
        """Register the roots slung since the last run and settle every pending
        one at once from the closes the events mirror carried (read with the
        rest of the events in ``collect``): a root is closed at its
        ``bead.closed`` event's time, never at the check's time. The store
        binding that holds the roots serves no bulk read through ``gc bd`` and
        keeps no ``closed_at``, so the close event is the authoritative time."""
        lines, state.load_offset = read_new_lines(self.city.file("load.jsonl"), state.load_offset)
        for rec in parse_jsonl(lines):
            wid = rec.get("workflow_id")
            if isinstance(wid, str) and wid:
                state.workflows[wid] = {"t": float(rec.get("t", now)), "action": rec.get("action")}
        unmatched: Dict[str, float] = {}
        for wid, closed_t in state.workflow_closes.items():
            tracked = state.workflows.get(wid)
            if tracked is not None:
                if tracked.get("closed_t") is None:
                    tracked["closed_t"] = closed_t
            elif closed_t >= now - WORKFLOW_KEEP_S:
                unmatched[wid] = closed_t
        state.workflow_closes = unmatched
        state.workflows = {k: v for k, v in state.workflows.items() if v["t"] >= now - WORKFLOW_KEEP_S}


def workflow_closures(events: Iterable[Rec]) -> Dict[str, float]:
    """Workflow roots closed in ``events``: id -> the first ``bead.closed``
    event's time. A root carries ``gc.kind = workflow``; its steps do not.
    An event without a readable time is skipped, not stamped with now."""
    closes: Dict[str, float] = {}
    for event in events:
        if event.get("type") != "bead.closed":
            continue
        payload = event.get("payload")
        meta = payload.get("metadata") if isinstance(payload, dict) else None
        wid = event.get("subject")
        if not isinstance(meta, dict) or meta.get("gc.kind") != "workflow" or not isinstance(wid, str) or not wid:
            continue
        t = event_time(event)
        if t is not None and wid not in closes:
            closes[wid] = t
    return closes


# --- digest, abort, main --------------------------------------------------------------------


def digest(outcomes: Sequence[Rec], now: float) -> str:
    """The hourly digest from the last hour of ``check.jsonl``."""
    hour = [o for o in outcomes if float(o.get("t", 0)) >= now - HOURLY_S]
    counts: Dict[str, int] = {}
    ids: Dict[str, int] = {}
    for o in hour:
        counts[str(o.get("status"))] = counts.get(str(o.get("status")), 0) + 1
        for f in list(o.get("hits", [])) + list(o.get("warnings", [])):
            ids[str(f.get("id"))] = ids.get(str(f.get("id")), 0) + 1
    lines = [
        f"== digest {iso(now)} ({len(hour)} checks in the last hour)",
        "status: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"),
        "findings: " + (", ".join(f"{k} x{v}" for k, v in sorted(ids.items())) or "none"),
    ]
    if hour:
        lines.append("last: " + json.dumps({k: hour[-1].get(k) for k in ("status", "hits", "warnings", "unknown")})[:1500])
    return "\n".join(lines) + "\n"


def abort(city: City, outcome: Outcome, paths: SoakPaths, gc: str, procfs: ProcFS) -> None:
    """Abort steps 1 and 2: ``ABORTED``, stop load, probes and the scheduled
    timers, capture. A capture that fails is recorded and never keeps the city
    running: ``_check`` runs ``stop_city`` (step 3) after this, whatever happens
    here."""
    from soakcapture import capture
    from soakprofile import timer_units

    aborted = city.file("ABORTED")
    with open(aborted, "a", encoding="utf-8") as handle:
        handle.write(f"aborted {iso(outcome.t)} phase {outcome.phase}\n")
        for f in outcome.hits:
            handle.write(f"  {f.id}: {f.reason}\n")
    # The scheduled switch and end (`soak schedule`) must not run on an aborted
    # city. One call: systemctl stops every unit it can and fails only for the
    # ones not loaded (a city run without `soak schedule` has none).
    run(["systemctl", "--user", "stop", "soak-load.service", "soak-probe.timer", *timer_units(city.name)], timeout=60.0)
    try:
        bundle = str(capture(city, paths, gc, procfs))
    except Exception as err:
        bundle = f"FAILED {type(err).__name__}: {err}"
    with open(aborted, "a", encoding="utf-8") as handle:
        handle.write(f"capture: {bundle}\n")


def stop_city(city: City, state: State, state_path: Path, gc: str, procfs: ProcFS) -> None:
    """Abort step 3: ``gc stop`` the city, check what of it remains, record both
    in ``ABORTED``. Only an exit 0 sets ``state.stopped``; until then every
    later check run calls this again, before it collects its inputs."""
    from soakcapture import remains

    stop = run([gc, "stop", str(city.path)], timeout=900.0)
    if stop.ok:
        state.stopped = True
        state.save(state_path)
    try:
        left = remains(city, procfs, gc)
        after = "nothing of the city remains" if not left else "REMAINING " + "; ".join(left)
    except Exception as err:
        after = f"FAILED {type(err).__name__}: {err}"
    with open(city.file("ABORTED"), "a", encoding="utf-8") as handle:
        handle.write(f"gc stop exit {stop.code}: {stop.tail(300)}\n")
        handle.write(f"after stop: {after}\n")


def check_main(city: City, paths: SoakPaths, final: bool = False, gc: str = "gc") -> int:
    """One check run. Runs never overlap: a second one (``--final`` while the
    timer's runs) waits for the first on ``check.lock``."""
    with open(city.file("check.lock"), "a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _check(city, paths, final, gc)


def _append_text(path: Path, text: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def _records(city: City, state: State, inputs: Inputs, outcome: Outcome, final: bool) -> List[Callable[[], None]]:
    """The writes of one run's outcome: ``check.jsonl``, ``check.log`` and,
    hourly and on ``--final``, ``digest.log``."""
    rec = outcome.as_rec()
    rec["final"] = final
    if inputs.ops is not None:
        rec["ops"] = {"rate_ctl": inputs.ops.rate_ctl, "rate_all": inputs.ops.rate_all, "sessions": inputs.ops.sessions}
    writes: List[Callable[[], None]] = [
        lambda: append_jsonl(city.file("check.jsonl"), rec),
        lambda: _append_text(city.file("check.log"), outcome.line() + "\n"),
    ]
    if final or inputs.now - state.last_digest_t >= HOURLY_S:
        state.last_digest_t = inputs.now
        writes.append(lambda: _append_text(city.file("digest.log"), digest(read_jsonl(city.file("check.jsonl")), inputs.now)))
    return writes


def _attempt(writes: Sequence[Callable[[], None]]) -> List[OSError]:
    """Run every write, whatever the ones before it raised; return what they raised."""
    failed: List[OSError] = []
    for write in writes:
        try:
            write()
        except OSError as err:
            failed.append(err)
    return failed


def _check(city: City, paths: SoakPaths, final: bool, gc: str) -> int:
    procfs = ProcFS()
    state_path = city.file("check-state.json")
    state = State.load(state_path)
    if (state.aborted or city.flag("ABORTED")) and not state.stopped:
        # An earlier abort's gc stop failed, that run was killed, or it could
        # not save the abort (a full disk; ``ABORTED`` is written only by an
        # abort): stop the city before anything this run reads or writes can
        # raise.
        state.aborted = True
        stop_city(city, state, state_path, gc, procfs)
    inputs = Collector(city, paths, procfs, gc).collect(state, final=final)
    outcome = evaluate(inputs, state, city.mode)
    writes = _records(city, state, inputs, outcome, final)
    if outcome.hits and city.mode == "abort" and not state.aborted and not city.flag("ABORTED"):
        # From the hit on, gc stop runs whatever raises. The abort's save and
        # this run's records are each tried (the capture holds what got
        # written); a write that failed (a full disk) is raised after the stop.
        state.aborted = True
        failed: List[OSError] = []
        try:
            failed = _attempt([lambda: state.save(state_path), *writes])
            abort(city, outcome, paths, gc, procfs)
        finally:
            stop_city(city, state, state_path, gc, procfs)
        if failed:
            raise failed[0]
    else:
        for write in writes:
            write()
    state.save(state_path)
    print(outcome.line())
    return 1 if final and outcome.hits else 0


__all__ = [
    "AGENT_LOG_GRACE_S",
    "RECORD_ONLY",
    "WORKFLOW_KEEP_S",
    "Collector",
    "Finding",
    "Inputs",
    "Outcome",
    "State",
    "check_main",
    "digest",
    "evaluate",
    "unlogged_agents",
    "workflow_closures",
]
