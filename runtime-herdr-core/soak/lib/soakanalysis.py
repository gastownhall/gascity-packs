"""The soak's analyses over its logs: incarnations and first turns from the
agent logs, nudges from the load log, message ops from gc's event mirror,
per-op cost from the bpftrace op trace, orphans and hc runtime from a
process snapshot.

Everything here is pure: it takes records and snapshots and returns
verdicts, so the unit tests drive it with synthetic logs.
"""

from __future__ import annotations

import calendar
import math
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from soaklib import ProcInfo, Rec, descendants, is_infra, obj

BEACON = re.compile(r"^\[[^]]+\] \S+ • \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
"""gc's beacon line: the head of every first turn gc composes."""
MARKER = "SOAK-FIRST-TURN"
NUDGE_NONCE = re.compile(r"SOAK-NUDGE ([0-9a-f]{8,64})")
BURST_GAP_S = 1.0
FIRST_TURN_WINDOW_S = 180.0
NUDGE_WINDOW_S = 900.0

FT_EXACT = "exact"
FT_LOST = "lost"
FT_DUPLICATED = "duplicated"
FT_SHORT_LIVED = "short_lived"
FT_FAULTED = "faulted"
"""Ended by a recorded fault before it could have had a first turn: not a loss."""
FT_PENDING = "pending"
"""Alive and younger than the window: no verdict yet."""


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Nearest-rank percentile (``q`` in 0..100); None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def parse_ts(text: str) -> Optional[float]:
    """An RFC 3339 timestamp (as gc writes them) as epoch seconds."""
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(\.\d+)?(Z|[+-]\d\d:?\d\d)?$", text.strip())
    if m is None:
        return None
    year, month, day, hour, minute, second = (int(m.group(i)) for i in range(1, 7))
    base = float(calendar.timegm((year, month, day, hour, minute, second, 0, 0, 0)))
    if m.group(7):
        base += float("0" + m.group(7))
    zone = m.group(8)
    if zone and zone != "Z":
        sign = 1 if zone[0] == "+" else -1
        digits = zone[1:].replace(":", "")
        base -= sign * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return base


def _num(rec: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = rec.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


# --- incarnations and first turns ---------------------------------------------------------


@dataclass
class Incarnation:
    inc: str
    session_id: str
    session_name: str
    template: str
    pid: int
    start: int
    boot_t: float
    last_t: float
    alive: bool
    inputs: List[Rec] = field(default_factory=list)
    records: List[Rec] = field(default_factory=list)
    bg: List[Tuple[int, int]] = field(default_factory=list)

    @property
    def end_t(self) -> Optional[float]:
        return None if self.alive else self.last_t

    def lived_s(self, now: float) -> float:
        return (now if self.alive else self.last_t) - self.boot_t


def inc_parts(inc: str) -> Tuple[str, int, int]:
    """``<boot id prefix>:<pid>:<start ticks>``."""
    boot, pid, start = inc.split(":")
    return boot, int(pid), int(start)


def incarnations(records: Iterable[Rec], alive: Callable[[str], bool]) -> List[Incarnation]:
    """Incarnations from one or more agent logs, keyed by ``inc``; records
    before their incarnation's ``boot`` (none should exist) are dropped."""
    by_inc: Dict[str, Incarnation] = {}
    for rec in records:
        inc = rec.get("inc")
        if not isinstance(inc, str):
            continue
        t = _num(rec, "t")
        if rec.get("ev") == "boot":
            try:
                _, pid, start = inc_parts(inc)
            except ValueError:
                continue
            by_inc[inc] = Incarnation(
                inc=inc,
                session_id=str(rec.get("session_id", "")),
                session_name=str(rec.get("session_name", "")),
                template=str(rec.get("template", "")),
                pid=pid,
                start=start,
                boot_t=t,
                last_t=t,
                alive=alive(inc),
            )
        current = by_inc.get(inc)
        if current is None:
            continue
        current.records.append(rec)
        current.last_t = max(current.last_t, t)
        if rec.get("ev") == "in":
            current.inputs.append(rec)
        elif rec.get("ev") == "bg":
            for child in rec.get("children", []) or []:
                if isinstance(child, dict) and isinstance(child.get("pid"), int) and isinstance(child.get("start"), int):
                    current.bg.append((child["pid"], child["start"]))
    return sorted(by_inc.values(), key=lambda i: (i.boot_t, i.inc))


def input_bursts(inputs: Sequence[Rec], gap_s: float = BURST_GAP_S) -> List[List[Rec]]:
    """``in`` records grouped into bursts: each less than ``gap_s`` after the previous."""
    ordered = sorted(inputs, key=lambda r: (_num(r, "mono", _num(r, "t")), _num(r, "n")))
    bursts: List[List[Rec]] = []
    last: Optional[float] = None
    for rec in ordered:
        stamp = _num(rec, "mono", _num(rec, "t"))
        if last is None or stamp - last >= gap_s:
            bursts.append([])
        bursts[-1].append(rec)
        last = stamp
    return bursts


def is_beacon(text: str) -> bool:
    return BEACON.match(text) is not None


def _burst_has_beacon(burst: Sequence[Rec]) -> bool:
    return any(bool(r.get("beacon")) or is_beacon(str(r.get("text", ""))) for r in burst)


def fault_covers(fault: Rec, session_id: str, pid: int, t0: float, t1: float) -> bool:
    """Whether a fault record names this session or pid (or everything) and falls in ``[t0, t1]``."""
    t = _num(fault, "t", -1.0)
    if not (t0 <= t <= t1):
        return False
    if fault.get("all"):
        return True
    sessions = fault.get("sessions") or []
    pids = fault.get("pids") or []
    return session_id in sessions or pid in pids


@dataclass(frozen=True)
class FirstTurn:
    inc: str
    session_id: str
    status: str
    beacon_bursts: int
    boot_t: float
    latency_s: Optional[float]
    marker: bool


def first_turn(inc: Incarnation, faults: Sequence[Rec], now: float, window_s: float = FIRST_TURN_WINDOW_S) -> FirstTurn:
    bursts = [b for b in input_bursts(inc.inputs) if _burst_has_beacon(b)]
    latency = None
    marker = False
    if bursts:
        latency = _num(bursts[0][0], "t") - inc.boot_t
        marker = any(MARKER in str(r.get("text", "")) or bool(r.get("marker")) for r in bursts[0])
    if len(bursts) == 1:
        status = FT_EXACT
    elif len(bursts) > 1:
        status = FT_DUPLICATED
    elif inc.lived_s(now) >= window_s:
        status = FT_LOST
    elif inc.alive:
        status = FT_PENDING
    elif any(fault_covers(f, inc.session_id, inc.pid, inc.boot_t, inc.last_t + 5.0) for f in faults):
        status = FT_FAULTED
    else:
        status = FT_SHORT_LIVED
    return FirstTurn(inc.inc, inc.session_id, status, len(bursts), inc.boot_t, latency, marker)


def first_turns(incs: Sequence[Incarnation], faults: Sequence[Rec], now: float) -> List[FirstTurn]:
    return [first_turn(i, faults, now) for i in incs]


def first_turn_counts(turns: Sequence[FirstTurn]) -> Dict[str, int]:
    counts = {s: 0 for s in (FT_EXACT, FT_LOST, FT_DUPLICATED, FT_SHORT_LIVED, FT_FAULTED, FT_PENDING)}
    for turn in turns:
        counts[turn.status] = counts.get(turn.status, 0) + 1
    return counts


# --- nudges -------------------------------------------------------------------------


NUDGE_RECEIVED = "received"
NUDGE_LOST = "lost"
NUDGE_DUPLICATED = "duplicated"
NUDGE_PENDING = "pending"
NUDGE_REFUSED = "refused"
_ACCEPTED_OUTCOMES = frozenset({"submitted", "queued", "interrupted", "delivered", "accepted"})


@dataclass(frozen=True)
class NudgeVerdict:
    nonce: str
    session_id: str
    t: float
    mode: str
    cli: str
    """``delivered``, ``queued`` or ``refused`` (the CLI's answer)."""
    status: str
    latency_s: Optional[float]


def nudge_cli_result(rec: Rec) -> str:
    doc = rec.get("json")
    if rec.get("exit") != 0 or not isinstance(doc, dict) or doc.get("ok") is False:
        return "refused"
    outcome = str(doc.get("outcome", ""))
    if doc.get("queued") is True or outcome == "queued":
        return "queued"
    return "delivered" if outcome in _ACCEPTED_OUTCOMES or outcome == "" else "refused"


def nudge_verdicts(
    load: Iterable[Rec], inputs_by_session: Mapping[str, Sequence[Rec]], now: float, window_s: float = NUDGE_WINDOW_S
) -> List[NudgeVerdict]:
    out: List[NudgeVerdict] = []
    for rec in load:
        if rec.get("action") != "nudge" or not isinstance(rec.get("nonce"), str):
            continue
        nonce = str(rec["nonce"])
        session = str(rec.get("session_id", ""))
        sent = _num(rec, "t")
        cli = nudge_cli_result(rec)
        if cli == "refused":
            out.append(NudgeVerdict(nonce, session, sent, str(rec.get("mode", "")), cli, NUDGE_REFUSED, None))
            continue
        hits = [
            r
            for r in inputs_by_session.get(session, [])
            if r.get("nonce") == nonce and sent - 5.0 <= _num(r, "t") <= sent + window_s
        ]
        if len(hits) == 1:
            status = NUDGE_RECEIVED
        elif len(hits) > 1:
            status = NUDGE_DUPLICATED
        elif now - sent >= window_s:
            status = NUDGE_LOST
        else:
            status = NUDGE_PENDING
        latency = _num(hits[0], "t") - sent if hits else None
        out.append(NudgeVerdict(nonce, session, sent, str(rec.get("mode", "")), cli, status, latency))
    return out


# --- message ops ------------------------------------------------------------------------


@dataclass
class MessageOps:
    closed: int = 0
    open: int = 0
    by_arm: Dict[str, int] = field(default_factory=dict)
    by_ack: Dict[str, int] = field(default_factory=dict)
    failed_reasons: Dict[str, int] = field(default_factory=dict)
    unconfirmed_ids: List[str] = field(default_factory=list)

    @property
    def unconfirmed(self) -> int:
        return len(self.unconfirmed_ids)

    @property
    def ratio(self) -> Optional[float]:
        return None if self.closed == 0 else self.unconfirmed / self.closed


def event_time(event: Rec) -> Optional[float]:
    ts = event.get("ts")
    return parse_ts(ts) if isinstance(ts, str) else None


def is_unconfirmed(op: Rec) -> bool:
    if not isinstance(op, dict) or op.get("status") != "closed":
        return False
    if _num(op, "maybe_delivered") > 0 or _num(op, "attempt") > 1:
        return True
    outcome = op.get("outcome") or {}
    if not isinstance(outcome, dict):
        return False
    if "unconfirmed" in str(outcome.get("reason", "")):
        return True
    result = outcome.get("result") or {}
    delivery = result.get("delivery") if isinstance(result, dict) else None
    return isinstance(delivery, dict) and "unconfirmed" in str(delivery.get("ack", ""))


def message_ops(events: Iterable[Rec], since: Optional[float] = None, until: Optional[float] = None) -> MessageOps:
    """``op.changed`` events of ``op.kind == "message"``: the last post-image per
    op id, counted by the time of that last event."""
    last: Dict[str, Tuple[float, Rec]] = {}
    for event in events:
        if event.get("type") != "op.changed":
            continue
        payload = event.get("payload")
        op = payload.get("op") if isinstance(payload, dict) else None
        if not isinstance(op, dict) or op.get("kind") != "message" or not isinstance(op.get("id"), str):
            continue
        t = event_time(event) or 0.0
        last[op["id"]] = (t, op)
    stats = MessageOps()
    for op_id, (t, op) in sorted(last.items()):
        if since is not None and t < since:
            continue
        if until is not None and t >= until:
            continue
        if op.get("status") != "closed":
            stats.open += 1
            continue
        stats.closed += 1
        outcome = obj(op.get("outcome"))
        arm = str(outcome.get("arm", "unknown"))
        stats.by_arm[arm] = stats.by_arm.get(arm, 0) + 1
        if arm == "succeeded":
            delivery = obj(obj(outcome.get("result")).get("delivery"))
            ack = str(delivery.get("ack", "") or "none")
            stats.by_ack[ack] = stats.by_ack.get(ack, 0) + 1
        elif arm == "failed":
            reason = str(outcome.get("reason", "") or "unknown")
            stats.failed_reasons[reason] = stats.failed_reasons.get(reason, 0) + 1
        if is_unconfirmed(op):
            stats.unconfirmed_ids.append(op_id)
    return stats


# --- the per-op trace ----------------------------------------------------------------------


@dataclass
class OpRun:
    pid: int
    ppid: int
    pcomm: str
    argv: Tuple[str, ...]
    start_ns: int
    end_ns: Optional[int] = None
    exit_code: Optional[int] = None
    wall_ms: Optional[int] = None
    cpu_us: Optional[int] = None

    @property
    def op(self) -> str:
        return self.argv[1] if len(self.argv) > 1 else "?"

    @property
    def signal(self) -> Optional[int]:
        if self.exit_code is None:
            return None
        sig = self.exit_code & 0x7F
        return sig or None

    @property
    def status(self) -> Optional[int]:
        return None if self.exit_code is None else (self.exit_code >> 8) & 0xFF


def parse_optrace(lines: Iterable[str]) -> Tuple[List[OpRun], List[int]]:
    """Ops (``E``/``X`` paired by pid) and the trace's start stamps (``B``).

    bpftrace prints an ``E`` line's argv with a separate ``join``, which ends
    the line; when another event lands in between, the argv arrives on a line
    of its own and is given to the newest ``E`` still without one."""
    runs: List[OpRun] = []
    starts: List[int] = []
    open_by_pid: Dict[int, OpRun] = {}
    awaiting_argv: List[OpRun] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            continue
        tag, _, rest = line.partition(" ")
        try:
            if tag == "B":
                starts.append(int(rest.split()[0]))
                open_by_pid.clear()
                awaiting_argv.clear()
                continue
            if tag == "E":
                parts = rest.split(" ", 4)
                run = OpRun(pid=int(parts[1]), ppid=int(parts[2]), pcomm=parts[3], argv=(), start_ns=int(parts[0]))
                tail = parts[4].strip() if len(parts) > 4 else ""
                if tail:
                    run.argv = tuple(tail.split(" "))
                else:
                    awaiting_argv.append(run)
                runs.append(run)
                open_by_pid[run.pid] = run
                continue
            if tag == "X":
                f = rest.split()
                pid = int(f[1])
                run_x = open_by_pid.pop(pid, None)
                if run_x is not None:
                    run_x.end_ns, run_x.exit_code, run_x.wall_ms, run_x.cpu_us = int(f[0]), int(f[2]), int(f[3]), int(f[4])
                continue
        except (ValueError, IndexError):
            continue
        if awaiting_argv:
            awaiting_argv.pop().argv = tuple(line.strip().split(" "))
    return runs, starts


def mono_offset(samples: Iterable[Rec]) -> Optional[float]:
    """Wall seconds minus monotonic seconds, from the samples' ``(t, mono_ns)`` pairs."""
    offsets = [
        _num(s, "t") - _num(s, "mono_ns") / 1e9 for s in samples if isinstance(s.get("mono_ns"), int) and s.get("t") is not None
    ]
    return statistics.median(offsets) if offsets else None


def supervisor_timeline(samples: Iterable[Rec]) -> List[Tuple[float, int]]:
    out: List[Tuple[float, int]] = []
    for s in samples:
        sup = s.get("supervisor")
        if isinstance(sup, dict) and isinstance(sup.get("pid"), int) and sup["pid"] > 0:
            out.append((_num(s, "t"), sup["pid"]))
    return sorted(out)


def pid_at(timeline: Sequence[Tuple[float, int]], t: float) -> Optional[int]:
    """The supervisor's MainPID at ``t``: the latest sample at or before it, else the first after."""
    best: Optional[int] = None
    for stamp, pid in timeline:
        if stamp <= t:
            best = pid
        else:
            return best if best is not None else pid
    return best


@dataclass
class OpStats:
    seconds: float
    sessions: float
    ops: int = 0
    ctl_ops: int = 0
    ctl_cpu_us: int = 0
    by_op: Dict[str, int] = field(default_factory=dict)
    latency_ms: Dict[str, List[int]] = field(default_factory=dict)
    cpu_us: Dict[str, List[int]] = field(default_factory=dict)
    signaled: int = 0

    @property
    def rate_all(self) -> float:
        return self.ops / self.seconds if self.seconds > 0 else 0.0

    @property
    def rate_ctl(self) -> float:
        return self.ctl_ops / self.seconds if self.seconds > 0 else 0.0

    @property
    def rate_ctl_per_session(self) -> float:
        return self.rate_ctl / max(1.0, self.sessions)

    @property
    def ctl_cpu_cores(self) -> float:
        return self.ctl_cpu_us / 1e6 / self.seconds if self.seconds > 0 else 0.0


def op_stats(
    runs: Iterable[OpRun],
    offset: float,
    t0: float,
    t1: float,
    supervisor: Sequence[Tuple[float, int]],
    sessions: float,
) -> OpStats:
    """Ops exec'd in ``[t0, t1)`` wall time; controller-spawned when the parent
    was the supervisor's MainPID of that time."""
    stats = OpStats(seconds=max(0.0, t1 - t0), sessions=sessions)
    for run in runs:
        t = run.start_ns / 1e9 + offset
        if not (t0 <= t < t1):
            continue
        stats.ops += 1
        stats.by_op[run.op] = stats.by_op.get(run.op, 0) + 1
        controller = pid_at(supervisor, t)
        if controller is not None and run.ppid == controller:
            stats.ctl_ops += 1
            stats.ctl_cpu_us += run.cpu_us or 0
        if run.wall_ms is not None:
            stats.latency_ms.setdefault(run.op, []).append(run.wall_ms)
        if run.cpu_us is not None:
            stats.cpu_us.setdefault(run.op, []).append(run.cpu_us)
        if run.signal is not None:
            stats.signaled += 1
    return stats


def mean_boxes(samples: Iterable[Rec], t0: float, t1: float) -> float:
    """The mean number of live boxes in samples within ``[t0, t1)`` (at least 1)."""
    counts = [len(s.get("boxes") or []) for s in samples if t0 <= _num(s, "t") < t1]
    return max(1.0, statistics.mean(counts)) if counts else 1.0


# --- processes ------------------------------------------------------------------------------


@dataclass(frozen=True)
class HcProc:
    pid: int
    start: int
    role: str
    state_home: str
    session: str
    cgroup: str


def hc_role(proc: ProcInfo) -> Optional[str]:
    """``serve`` or ``hold`` for hc runtime (a ``herdr-core`` binary, or a
    process hc marks with ``HC_RUNTIME=1``); None for anything else."""
    named = proc.comm == "herdr-core" or (bool(proc.argv) and proc.argv[0].rsplit("/", 1)[-1] == "herdr-core")
    if not named and proc.env.get("HC_RUNTIME") != "1":
        return None
    for arg in proc.argv[1:3]:
        if arg in ("serve", "hold"):
            return arg
    return None


def hc_runtime(snapshot: Mapping[int, ProcInfo]) -> List[HcProc]:
    out: List[HcProc] = []
    for proc in snapshot.values():
        role = hc_role(proc)
        if role is None:
            continue
        out.append(
            HcProc(
                pid=proc.pid,
                start=proc.start,
                role=role,
                state_home=proc.env.get("XDG_STATE_HOME", ""),
                session=proc.env.get("HC_SESSION", ""),
                cgroup=proc.cgroup,
            )
        )
    return sorted(out, key=lambda h: h.pid)


def foreign_hc(hcs: Iterable[HcProc], state_home: str, session: str) -> List[HcProc]:
    return [h for h in hcs if h.state_home != state_home or h.session != session]


def city_cores(hcs: Iterable[HcProc], state_home: str, session: str) -> List[HcProc]:
    return [h for h in hcs if h.role == "serve" and h.state_home == state_home and h.session == session]


def boxes(snapshot: Mapping[int, ProcInfo], holder_pids: Iterable[int]) -> List[ProcInfo]:
    """The live boxes: processes whose parent is a holder of the city's core."""
    holders = set(holder_pids)
    return sorted((p for p in snapshot.values() if p.ppid in holders), key=lambda p: p.pid)


def find_orphans(
    snapshot: Mapping[int, ProcInfo],
    holder_pids: Iterable[int],
    city_path: str,
    older_than_s: float,
    uid: int,
) -> List[ProcInfo]:
    """Processes of ``uid`` carrying the city's ``GC_CITY_PATH`` and an instance
    token no live box carries, older than ``older_than_s``, that are neither
    city infrastructure nor under it."""
    live_boxes = boxes(snapshot, holder_pids)
    live_tokens: Set[str] = {b.env.get("GC_INSTANCE_TOKEN", "") for b in live_boxes} - {""}
    infra_roots = [p.pid for p in snapshot.values() if is_infra(p)]
    sheltered = set(infra_roots) | set(descendants(snapshot, infra_roots))
    holders = set(holder_pids)
    out: List[ProcInfo] = []
    for proc in snapshot.values():
        token = proc.env.get("GC_INSTANCE_TOKEN", "")
        if proc.uid != uid or not token or proc.env.get("GC_CITY_PATH") != city_path:
            continue
        if proc.age_s < older_than_s or token in live_tokens or proc.pid in sheltered or proc.pid in holders:
            continue
        if hc_role(proc) is not None:
            continue
        out.append(proc)
    return sorted(out, key=lambda p: p.pid)


def store_procs(snapshot: Mapping[int, ProcInfo], uid: int) -> List[ProcInfo]:
    """This user's store proxies (argv[1] ``db-proxy-child``) and their ``dolt sql-server`` children."""
    proxies = [p for p in snapshot.values() if p.uid == uid and p.argv1 == "db-proxy-child"]
    proxy_pids = {p.pid for p in proxies}
    dolts = [
        p
        for p in snapshot.values()
        if p.uid == uid and p.ppid in proxy_pids and (p.comm == "dolt" or "sql-server" in p.argv)
    ]
    seen: Dict[int, ProcInfo] = {p.pid: p for p in proxies}
    for p in dolts:
        seen[p.pid] = p
    return sorted(seen.values(), key=lambda p: p.pid)
