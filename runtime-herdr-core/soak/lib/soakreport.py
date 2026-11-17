"""``soak report``: every number the soak report needs, per phase window,
computed from a city's data directory and rendered as Markdown.

:func:`compute` and :func:`render_markdown` are pure; :func:`load_inputs`
reads the files.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from soakanalysis import (
    FT_DUPLICATED,
    FT_EXACT,
    FT_LOST,
    FirstTurn,
    Incarnation,
    MessageOps,
    NUDGE_DUPLICATED,
    NUDGE_LOST,
    NUDGE_PENDING,
    NUDGE_RECEIVED,
    OpRun,
    OpStats,
    event_time,
    first_turn_counts,
    first_turns,
    incarnations,
    mean_boxes,
    message_ops,
    mono_offset,
    nudge_verdicts,
    op_stats,
    parse_optrace,
    percentile,
    supervisor_timeline,
)
from soaklib import Rec, iso, obj, read_jsonl

BUDGET = {"legacy": 0.30, "v2": 0.05}
SOAK_PHASES = ("soak-legacy", "soak-v2")
CLK_TCK = 100


@dataclass(frozen=True)
class Window:
    name: str
    t0: float
    t1: float
    reconciler: str

    def has(self, t: float) -> bool:
        return self.t0 <= t < self.t1


def windows(phases: Sequence[Rec], now: float) -> List[Window]:
    """Phase windows from ``phases.jsonl``: each runs until the next phase starts."""
    ordered = sorted(phases, key=lambda r: float(r.get("t", 0)))
    out: List[Window] = []
    for i, rec in enumerate(ordered):
        t1 = float(ordered[i + 1]["t"]) if i + 1 < len(ordered) else now
        out.append(Window(str(rec.get("phase", "")), float(rec.get("t", 0)), t1, str(rec.get("reconciler", ""))))
    return out


@dataclass
class ReportInputs:
    city: str
    now: float
    agent_records: List[Rec]
    alive: Callable[[str], bool]
    load: List[Rec]
    events: List[Rec]
    samples: List[Rec]
    faults: List[Rec]
    optrace: List[str]
    phases: List[Rec]
    drills: List[Rec]
    checks: List[Rec]
    workflows: Mapping[str, Mapping[str, Any]]
    hz: int = CLK_TCK


def _stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {
        "n": float(len(values)),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values) if values else None,
    }


@dataclass
class PhaseMetrics:
    window: Window
    incarnations: int = 0
    first_turns: Dict[str, int] = field(default_factory=dict)
    first_turn_latency: Dict[str, Optional[float]] = field(default_factory=dict)
    bad_first_turns: List[str] = field(default_factory=list)
    nudges: Dict[str, int] = field(default_factory=dict)
    nudge_latency: Dict[str, Optional[float]] = field(default_factory=dict)
    messages: MessageOps = field(default_factory=MessageOps)
    store_changes: List[str] = field(default_factory=list)
    unexplained_store_changes: int = 0
    restarts: Dict[str, int] = field(default_factory=dict)
    quarantines: int = 0
    controller_starts: int = 0
    core_restarts: int = 0
    holder_losses: int = 0
    workflows: Dict[str, Any] = field(default_factory=dict)
    ops: Optional[OpStats] = None
    controller_cpu: Dict[str, Optional[float]] = field(default_factory=dict)
    user_cpu_cores: Optional[float] = None
    core_rss: Dict[str, Any] = field(default_factory=dict)
    sizes: Optional[Rec] = None
    death_to_restart: Dict[str, Optional[float]] = field(default_factory=dict)
    checks: Dict[str, int] = field(default_factory=dict)
    orphans_max: int = 0


@dataclass
class Report:
    city: str
    now: float
    phases: List[PhaseMetrics]
    drills: List[Rec]
    all_first_turns: List[FirstTurn]


def _covered(faults: Sequence[Rec], what: str, t: float, slack: float = 180.0) -> Optional[str]:
    for f in faults:
        ft = float(f.get("t", 0))
        if t - slack <= ft <= t + 5.0 and (what in (f.get("covers") or []) or "all" in (f.get("covers") or [])):
            return str(f.get("kind", ""))
    return None


def _store_changes(samples: Sequence[Rec], faults: Sequence[Rec], window: Window) -> Tuple[List[str], int]:
    out: List[str] = []
    unexplained = 0
    previous: Optional[set] = None  # type: ignore[type-arg]
    for s in samples:
        t = float(s.get("t", 0))
        current = {(int(p["pid"]), int(p["start"]), str(p.get("argv1") or p.get("comm"))) for p in s.get("store") or [] if isinstance(p, dict)}
        if previous is not None and window.has(t):
            gone = previous - current
            for pid, _start, label in sorted(gone):
                cause = _covered(faults, "store", t, slack=120.0)
                if cause is None:
                    unexplained += 1
                out.append(f"{iso(t)} {label} {pid} ended ({cause or 'unexplained'})")
        previous = current
    return out, unexplained


def _core_changes(samples: Sequence[Rec], faults: Sequence[Rec], window: Window) -> Tuple[int, int]:
    restarts = holder_losses = 0
    prev_core: Optional[int] = None
    prev_holders: set = set()  # type: ignore[type-arg]
    for s in samples:
        t = float(s.get("t", 0))
        core = obj(s.get("core"))
        pid = core.get("pid") if isinstance(core.get("pid"), int) else None
        holders = {h.get("pid") for h in s.get("holders") or [] if isinstance(h, dict)}
        if window.has(t):
            if pid is not None and prev_core is not None and pid != prev_core and _covered(faults, "core", t) is None:
                restarts += 1
            if prev_holders - holders and _covered(faults, "holder", t) is None and _covered(faults, "core", t) is None:
                holder_losses += 1
        if pid is not None:
            prev_core = pid
            prev_holders = holders
    return restarts, holder_losses


def _cpu(samples: Sequence[Rec], window: Window, hz: int) -> Tuple[Dict[str, Optional[float]], Optional[float]]:
    rates: List[float] = []
    user: List[float] = []
    prev: Optional[Rec] = None
    for s in samples:
        t = float(s.get("t", 0))
        if prev is not None and window.has(t):
            dt = t - float(prev.get("t", 0))
            a, b = prev.get("supervisor") or {}, s.get("supervisor") or {}
            if dt > 0 and isinstance(a, dict) and isinstance(b, dict) and a.get("pid") == b.get("pid"):
                if isinstance(a.get("ticks"), int) and isinstance(b.get("ticks"), int) and b["ticks"] >= a["ticks"]:
                    rates.append((b["ticks"] - a["ticks"]) / hz / dt)
            ua, ub = prev.get("user_usage_usec"), s.get("user_usage_usec")
            if dt > 0 and isinstance(ua, int) and isinstance(ub, int) and ub >= ua:
                user.append((ub - ua) / 1e6 / dt)
        prev = s
    return (
        {"mean": statistics.mean(rates) if rates else None, "p95": percentile(rates, 95)},
        statistics.mean(user) if user else None,
    )


def core_rss_hourly(samples: Sequence[Rec], window: Window) -> Dict[str, Any]:
    """Hourly medians of the core's RSS within the window; hour 2's is the reference."""
    hours: Dict[int, List[int]] = {}
    for s in samples:
        t = float(s.get("t", 0))
        core = s.get("core")
        if window.has(t) and isinstance(core, dict) and isinstance(core.get("rss_kib"), int):
            hours.setdefault(int((t - window.t0) // 3600), []).append(core["rss_kib"])
    medians = {h: float(statistics.median(v)) for h, v in sorted(hours.items())}
    ref = medians.get(1)
    deviation = None
    if ref:
        deviation = max(abs(m - ref) / ref for m in medians.values())
    return {"medians_kib": medians, "reference_kib": ref, "max_deviation": deviation, "within_20pct": None if deviation is None else deviation <= 0.20}


def death_to_restart(faults: Sequence[Rec], incs: Sequence[Incarnation], window: Window) -> List[float]:
    out: List[float] = []
    for f in faults:
        if f.get("kind") != "probe-kill" or not window.has(float(f.get("t", 0))):
            continue
        t = float(f["t"])
        sessions = set(f.get("sessions") or [])
        later = sorted(i.boot_t for i in incs if i.session_id in sessions and i.boot_t > t)
        if later:
            out.append(later[0] - t)
    return out


def _restart_causes(incs: Sequence[Incarnation], faults: Sequence[Rec], window: Window) -> Dict[str, int]:
    """Boots in the window after an earlier incarnation of the same session, by cause."""
    by_session: Dict[str, List[Incarnation]] = {}
    for inc in incs:
        by_session.setdefault(inc.session_id, []).append(inc)
    counts = {"starts": 0, "probe": 0, "drill": 0, "unexplained": 0}
    for sid, items in by_session.items():
        items.sort(key=lambda i: i.boot_t)
        previous: List[Optional[Incarnation]] = [None]
        previous.extend(items[:-1])
        for prev, cur in zip(previous, items):
            if not window.has(cur.boot_t):
                continue
            counts["starts"] += 1
            if prev is None:
                continue
            cause = None
            for f in faults:
                ft = float(f.get("t", 0))
                if prev.boot_t <= ft <= cur.boot_t and (f.get("all") or sid in (f.get("sessions") or []) or prev.pid in (f.get("pids") or [])):
                    cause = "probe" if f.get("kind") == "probe-kill" else "drill"
            counts[cause or "unexplained"] += 1
    return counts


def compute(inp: ReportInputs) -> Report:
    incs = incarnations(inp.agent_records, inp.alive)
    turns = first_turns(incs, inp.faults, inp.now)
    by_inc = {t.inc: t for t in turns}
    inputs_by_session: Dict[str, List[Rec]] = {}
    for inc in incs:
        inputs_by_session.setdefault(inc.session_id, []).extend(inc.inputs)
    nudges = nudge_verdicts(inp.load, inputs_by_session, inp.now)
    runs, _ = parse_optrace(inp.optrace)
    offset = mono_offset(inp.samples)
    timeline = supervisor_timeline(inp.samples)
    phases: List[PhaseMetrics] = []
    for w in windows(inp.phases, inp.now):
        m = PhaseMetrics(window=w)
        in_w = [i for i in incs if w.has(i.boot_t)]
        m.incarnations = len(in_w)
        w_turns = [by_inc[i.inc] for i in in_w]
        m.first_turns = first_turn_counts(w_turns)
        m.first_turn_latency = _stats([t.latency_s for t in w_turns if t.latency_s is not None])
        m.bad_first_turns = [f"{t.session_id} {t.inc} {t.status}" for t in w_turns if t.status in (FT_LOST, FT_DUPLICATED)]
        w_nudges = [n for n in nudges if w.has(n.t)]
        m.nudges = {"sent": len(w_nudges)}
        for n in w_nudges:
            m.nudges["cli_" + n.cli] = m.nudges.get("cli_" + n.cli, 0) + 1
            m.nudges[n.status] = m.nudges.get(n.status, 0) + 1
        m.nudge_latency = _stats([n.latency_s for n in w_nudges if n.latency_s is not None])
        m.messages = message_ops(inp.events, w.t0, w.t1)
        m.store_changes, m.unexplained_store_changes = _store_changes(inp.samples, inp.faults, w)
        m.restarts = _restart_causes(incs, inp.faults, w)
        for e in inp.events:
            t = event_time(e)
            if t is None or not w.has(t):
                continue
            if e.get("type") == "session.quarantined":
                m.quarantines += 1
            elif e.get("type") == "controller.started":
                m.controller_starts += 1
        m.core_restarts, m.holder_losses = _core_changes(inp.samples, inp.faults, w)
        slung = [(float(v.get("t", 0)), v.get("closed_t")) for v in inp.workflows.values() if w.has(float(v.get("t", 0)))]
        durations = [float(c) - t for t, c in slung if isinstance(c, (int, float))]
        m.workflows = {
            "slung": len(slung),
            "closed": len(durations),
            "open_30m": sum(1 for t, c in slung if c is None and inp.now - t >= 1800) + sum(1 for d in durations if d > 1800),
            "sling_to_closed_s": _stats(durations),
        }
        if offset is not None:
            m.ops = op_stats(runs, offset, w.t0, w.t1, timeline, mean_boxes(inp.samples, w.t0, w.t1))
        m.controller_cpu, m.user_cpu_cores = _cpu(inp.samples, w, inp.hz)
        m.core_rss = core_rss_hourly(inp.samples, w)
        sized = [s for s in inp.samples if isinstance(s.get("sizes"), dict) and w.has(float(s.get("t", 0)))]
        m.sizes = sized[-1]["sizes"] if sized else None
        m.death_to_restart = _stats(death_to_restart(inp.faults, incs, w))
        for c in inp.checks:
            if w.has(float(c.get("t", 0))):
                m.checks[str(c.get("status"))] = m.checks.get(str(c.get("status")), 0) + 1
                for warning in c.get("warnings") or []:
                    if warning.get("id") == "W-orphans":
                        try:
                            m.orphans_max = max(m.orphans_max, int(str(warning.get("reason", "0")).split()[0]))
                        except ValueError:
                            pass
        phases.append(m)
    return Report(inp.city, inp.now, phases, sorted(inp.drills, key=lambda d: float(d.get("t_inject") or 0)), turns)


# --- rendering -------------------------------------------------------------------------------------


def _f(value: Optional[float], digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _ms(values: Sequence[int]) -> str:
    return f"{_f(percentile(values, 50), 0)} / {_f(percentile(values, 95), 0)} / {_f(percentile(values, 99), 0)}"


def _ops_lines(ops: Optional[OpStats], budget: Optional[float]) -> List[str]:
    if ops is None:
        return ["- pack ops: no op trace or samples"]
    lines = [
        f"- pack ops / s: all {_f(ops.rate_all, 3)}; controller-spawned {_f(ops.rate_ctl, 3)}; "
        f"per session {_f(ops.rate_ctl_per_session, 4)} (n = {ops.sessions:.1f}"
        + (f", budget {budget}" if budget is not None else "")
        + ")",
        f"- controller-spawned op CPU: {_f(ops.ctl_cpu_cores, 4)} cores; ops ended by a signal: {ops.signaled}",
    ]
    top = sorted(ops.by_op.items(), key=lambda kv: -kv[1])[:8]
    if top and ops.seconds > 0:
        lines.append("- top ops by rate: " + ", ".join(f"{op} {n / ops.seconds:.3f}/s" for op, n in top))
    for op, _n in top:
        lat = ops.latency_ms.get(op, [])
        cpu = ops.cpu_us.get(op, [])
        cpu_ms = statistics.mean(cpu) / 1000 if cpu else None
        lines.append(f"  - `{op}`: latency p50/p95/p99 {_ms(lat)} ms; CPU mean {_f(cpu_ms, 1)} ms")
    return lines


def render_phase(m: PhaseMetrics) -> List[str]:
    w = m.window
    ft = m.first_turns
    lines = [
        f"### {w.name} ({w.reconciler or '-'}): {iso(w.t0)} to {iso(w.t1)} ({(w.t1 - w.t0) / 3600:.2f} h)",
        "",
        f"- incarnations: {m.incarnations}; restarts: {m.restarts}",
        f"- first turns: exact {ft.get(FT_EXACT, 0)}, lost {ft.get(FT_LOST, 0)}, duplicated {ft.get(FT_DUPLICATED, 0)}, "
        f"short-lived {ft.get('short_lived', 0)}, ended by a fault {ft.get('faulted', 0)}, pending {ft.get('pending', 0)}; "
        f"boot to first turn p50/p95 {_f(m.first_turn_latency.get('p50'))} / {_f(m.first_turn_latency.get('p95'))} s",
    ]
    if m.bad_first_turns:
        lines.append("  - lost or duplicated: " + ", ".join(m.bad_first_turns[:10]))
    n = m.nudges
    lines.append(
        f"- nudges: sent {n.get('sent', 0)}; CLI delivered {n.get('cli_delivered', 0)}, queued {n.get('cli_queued', 0)}, refused {n.get('cli_refused', 0)}; "
        f"received once {n.get(NUDGE_RECEIVED, 0)}, lost {n.get(NUDGE_LOST, 0)}, duplicated {n.get(NUDGE_DUPLICATED, 0)}, pending {n.get(NUDGE_PENDING, 0)}; "
        f"CLI to received p50/p95 {_f(m.nudge_latency.get('p50'))} / {_f(m.nudge_latency.get('p95'))} s"
    )
    mo = m.messages
    lines.append(
        f"- message ops: closed {mo.closed} (open {mo.open}); arms {json.dumps(mo.by_arm, sort_keys=True)}; acks {json.dumps(mo.by_ack, sort_keys=True)}; "
        f"failed {json.dumps(mo.failed_reasons, sort_keys=True)}; unconfirmed {mo.unconfirmed} ({_f(None if mo.ratio is None else mo.ratio * 100)} %)"
    )
    lines.append(f"- store: {len(m.store_changes)} pid change(s), {m.unexplained_store_changes} unexplained")
    lines += [f"  - {c}" for c in m.store_changes[:10]]
    lines.append(
        f"- sessions: quarantines {m.quarantines}; controller starts {m.controller_starts}; unexplained core restarts {m.core_restarts}; unexplained holder losses {m.holder_losses}"
    )
    wf = m.workflows
    s = wf.get("sling_to_closed_s", {})
    lines.append(
        f"- workflows: slung {wf.get('slung', 0)}, closed {wf.get('closed', 0)}, open after 30 min {wf.get('open_30m', 0)}; "
        f"sling to closed p50/p95/max {_f(s.get('p50'), 0)} / {_f(s.get('p95'), 0)} / {_f(s.get('max'), 0)} s"
    )
    lines += _ops_lines(m.ops, BUDGET.get(w.reconciler))
    lines.append(
        f"- CPU: controller tree mean {_f(m.controller_cpu.get('mean'), 3)} / p95 {_f(m.controller_cpu.get('p95'), 3)} cores; all of this user's {_f(m.user_cpu_cores, 3)} cores"
    )
    rss = m.core_rss
    ref = rss.get("reference_kib")
    dev = rss.get("max_deviation")
    lines.append(
        f"- core RSS: reference (hour 2) {_f(None if ref is None else ref / 1024, 1)} MiB; max deviation {_f(None if dev is None else dev * 100, 1)} %; "
        f"hourly medians {', '.join(f'{v / 1024:.1f}' for v in rss.get('medians_kib', {}).values()) or '-'} MiB"
    )
    if m.sizes:
        lines.append("- sizes at the end: " + ", ".join(f"{k} {_bytes(v)}" for k, v in sorted(m.sizes.items())))
    d = m.death_to_restart
    lines.append(f"- death to restart (probes): n {int(d.get('n') or 0)}, p50 {_f(d.get('p50'), 1)}, p95 {_f(d.get('p95'), 1)}, max {_f(d.get('max'), 1)} s")
    lines.append(f"- checks: {json.dumps(m.checks, sort_keys=True)}; most orphans at one scan: {m.orphans_max}")
    return lines + [""]


def _bytes(value: Any) -> str:
    if not isinstance(value, int):
        return "-"
    size = float(value)
    for unit in ("B", "KiB", "MiB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def soak_table(report: Report) -> List[str]:
    by_name = {m.window.name: m for m in report.phases}
    halves = [by_name.get(p) for p in SOAK_PHASES]
    if not any(halves):
        return []

    def cell(m: Optional[PhaseMetrics], fn: Callable[[PhaseMetrics], str]) -> str:
        return "-" if m is None else fn(m)

    rows = [
        ("S1", "lost first turns", "0", lambda m: str(m.first_turns.get(FT_LOST, 0))),
        ("S2", "duplicated first turns", "0", lambda m: str(m.first_turns.get(FT_DUPLICATED, 0))),
        ("S3", "infrastructure processes killed, Dolt restarts", "0", lambda m: str(m.unexplained_store_changes)),
        ("S4", "unconfirmed message ops", "< 1%", lambda m: f"{m.messages.unconfirmed}/{m.messages.closed}"),
        (
            "S5",
            "controller-spawned pack ops / s / session",
            "≤ 0.30 / ≤ 0.05",
            lambda m: "-" if m.ops is None else f"{m.ops.rate_ctl_per_session:.4f}",
        ),
        ("S6", "core RSS within ±20%", "yes", lambda m: str(m.core_rss.get("within_20pct"))),
        ("S7", "no abort", "yes", lambda m: "yes" if not m.checks.get("HIT") else f"no ({m.checks.get('HIT')} hit runs)"),
    ]
    lines = ["| ID | Criterion | Target | Legacy half | v2 half |", "|---|---|---|---|---|"]
    for rid, what, target, fn in rows:
        lines.append(f"| {rid} | {what} | {target} | {cell(halves[0], fn)} | {cell(halves[1], fn)} |")
    return lines + [""]


def drill_table(drills: Sequence[Rec]) -> List[str]:
    if not drills:
        return []
    lines = ["| Drill | Injected at | Verdict | Criteria |", "|---|---|---|---|"]
    for d in drills:
        crit = "; ".join(
            f"{c.get('id')} {'pass' if c.get('pass') else ('recorded' if c.get('pass') is None else 'FAIL')}" for c in d.get("criteria", [])
        )
        t = d.get("t_inject")
        lines.append(f"| {d.get('drill')} | {iso(float(t)) if t else '-'} | {d.get('verdict')} | {crit} |")
    return lines + [""]


def render_markdown(report: Report) -> str:
    lines = [f"# soak data: {report.city}", "", f"Generated {iso(report.now)} by `soak report`.", ""]
    soak = soak_table(report)
    if soak:
        lines += ["## Soak criteria", ""] + soak
    if report.drills:
        lines += ["## Drills", ""] + drill_table(report.drills)
    lines += ["## Phases", ""]
    for m in report.phases:
        lines += render_phase(m)
    return "\n".join(lines)


def first_turn_summary(report: Report) -> str:
    counts = first_turn_counts(report.all_first_turns)
    bad = [t for t in report.all_first_turns if t.status not in (FT_EXACT, "pending")]
    lines = [f"incarnations {len(report.all_first_turns)}: " + ", ".join(f"{k} {v}" for k, v in counts.items())]
    lines += [f"  {t.session_id} {t.inc} {t.status} ({t.beacon_bursts} beacon bursts)" for t in bad]
    return "\n".join(lines) + "\n"


# --- loading -----------------------------------------------------------------------------------------


def load_inputs(data: Path, optrace: Path, alive: Callable[[str], bool], now: float, hz: int = CLK_TCK) -> ReportInputs:
    agents: List[Rec] = []
    for path in sorted((data / "agents").glob("*.jsonl")):
        agents.extend(read_jsonl(path))
    try:
        trace = optrace.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        trace = []
    drills: List[Rec] = []
    for path in sorted((data / "drills").glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and "drill" in doc:
            drills.append(doc)
    try:
        state = json.loads((data / "check-state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    return ReportInputs(
        city=data.name,
        now=now,
        agent_records=agents,
        alive=alive,
        load=read_jsonl(data / "load.jsonl"),
        events=read_jsonl(data / "gc-events" / "events.jsonl"),
        samples=read_jsonl(data / "samples.jsonl"),
        faults=read_jsonl(data / "faults.jsonl"),
        optrace=trace,
        phases=read_jsonl(data / "phases.jsonl"),
        drills=drills,
        checks=read_jsonl(data / "check.jsonl"),
        workflows=state.get("workflows", {}) if isinstance(state, dict) else {},
        hz=hz,
    )


__all__ = ["Report", "ReportInputs", "Window", "compute", "first_turn_summary", "load_inputs", "render_markdown", "windows"]
