from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

import pytest

from .soaktestkit import rec

from soakcheck import HIT, OK, WARN, Finding, Outcome
from soaklib import LINE_LIMIT, Rec, append_jsonl, encode_line
from soakreport import (
    CHECK_STATUSES,
    ReportInputs,
    restart_causes,
    Window,
    compute,
    core_rss_hourly,
    death_to_restart,
    first_turn_summary,
    load_inputs,
    render_markdown,
    windows,
)
from soakanalysis import incarnations

T0 = 1_800_000_000.0
BEACON = "[hc-soak] soak-steady-1 • 2026-11-17T10:00:00"


def agent_log() -> List[Rec]:
    a, b, c = "bt:100:1", "bt:200:2", "bt:300:3"
    return [
        rec("boot", T0 + 10, a, session_id="s1", template="soak-steady"),
        rec("in", T0 + 15, a, text=BEACON, beacon=True),
        rec("in", T0 + 15.3, a, text="SOAK-FIRST-TURN soak-steady", marker=True),
        rec("in", T0 + 500, a, text="SOAK-NUDGE " + "a" * 32, nonce="a" * 32),
        rec("hb", T0 + 1790, a),
        # killed by the probe at T0 + 1800, back at T0 + 1840
        rec("boot", T0 + 1840, b, session_id="s1", template="soak-steady"),
        rec("in", T0 + 1846, b, text=BEACON, beacon=True),
        rec("hb", T0 + 3600 * 13, b),
        # a v2-half incarnation that got its first turn twice
        rec("boot", T0 + 3600 * 13, c, session_id="s2", template="soak-steady"),
        rec("in", T0 + 3600 * 13 + 5, c, text=BEACON, beacon=True),
        rec("in", T0 + 3600 * 13 + 60, c, text=BEACON, beacon=True),
    ]


def samples() -> List[Rec]:
    out: List[Rec] = []
    for i in range(0, 24 * 60, 10):
        t = T0 + i * 60
        rss = 50_000 if i < 120 else 52_000
        out.append(
            {
                "t": t,
                "mono_ns": int(i * 60 * 1e9),
                "supervisor": {"pid": 77, "ticks": i * 60},
                "core": {"pid": 5, "rss_kib": rss},
                "holders": [{"pid": 6}],
                "boxes": [{"pid": 100}] * 12,
                "store": [{"pid": 40, "start": 1, "argv1": "db-proxy-child"}],
                "user_usage_usec": i * 60 * 500_000,
                "sizes": {"R": 1 << 20, "hc_state": 1 << 19, "gc_dir": 1, "beads_dir": 2, "events": 3},
            }
        )
    return out


def optrace() -> List[str]:
    lines = ["B 0"]
    for i in range(0, 24 * 3600, 10):
        ns = int(i * 1e9)
        lines.append(f"E {ns} {1000 + i} 77 gc /p/gc-runtime-herdr-core observe")
        lines.append(f"X {ns + 30_000_000} {1000 + i} 0 30 15000")
    return lines


def inputs() -> ReportInputs:
    load = [
        {"t": T0 + 499, "action": "nudge", "session_id": "s1", "nonce": "a" * 32, "mode": "wait-idle", "exit": 0, "json": {"ok": True, "outcome": "submitted"}},
        {"t": T0 + 600, "action": "sling-burst", "workflow_id": "w1", "exit": 0},
    ]
    events = [
        {"type": "op.changed", "ts": "2027-01-15T08:10:00Z", "payload": {"op": {"id": "o1", "kind": "message", "status": "closed", "attempt": 1, "outcome": {"arm": "succeeded", "result": {"delivery": {"ack": "delivered"}}}}}},
    ]
    return ReportInputs(
        city="hc-soak",
        now=T0 + 24 * 3600,
        agent_records=agent_log(),
        alive=lambda inc: inc == "bt:300:3",
        load=load,
        events=events,
        samples=samples(),
        faults=[{"t": T0 + 1800, "kind": "probe-kill", "sessions": ["s1"], "pids": [100]}],
        optrace=optrace(),
        phases=[
            {"t": T0, "phase": "soak-legacy", "reconciler": "legacy"},
            {"t": T0 + 12 * 3600, "phase": "soak-v2", "reconciler": "v2"},
        ],
        drills=[{"drill": "agent-kill", "t_inject": T0 - 100, "verdict": "pass", "criteria": [{"id": "C2", "pass": True}, {"id": "x", "pass": None}]}],
        checks=[{"t": T0 + 300, "status": "OK", "hits": [], "warnings": []}, {"t": T0 + 13 * 3600, "status": "WARN", "warnings": [{"id": "W-orphans", "reason": "2 orphan(s) older than 10 minutes"}]}],
        workflows={"w1": {"t": T0 + 600, "closed_t": T0 + 900}},
    )


def test_windows_run_to_the_next_phase() -> None:
    ws = windows([{"t": 10.0, "phase": "b", "reconciler": "v2"}, {"t": 0.0, "phase": "a", "reconciler": "legacy"}], now=20.0)
    assert ws == [Window("a", 0.0, 10.0, "legacy"), Window("b", 10.0, 20.0, "v2")]


def test_compute_per_phase() -> None:
    report = compute(inputs())
    legacy, v2 = report.phases
    assert legacy.window.name == "soak-legacy" and v2.window.name == "soak-v2"
    assert legacy.incarnations == 2 and legacy.first_turns["exact"] == 2
    assert v2.first_turns["duplicated"] == 1 and v2.bad_first_turns
    assert legacy.restarts["probe"] == 1 and legacy.restarts["unexplained"] == 0
    assert legacy.death_to_restart["n"] == 1 and legacy.death_to_restart["p50"] == 40.0
    assert legacy.nudges["sent"] == 1 and legacy.nudges["received"] == 1
    assert legacy.messages.closed == 1 and legacy.messages.unconfirmed == 0
    assert legacy.workflows["closed"] == 1 and legacy.workflows["sling_to_closed_s"]["p50"] == 300.0
    assert legacy.ops is not None and legacy.ops.ctl_ops == legacy.ops.ops == 12 * 360
    assert abs(legacy.ops.rate_ctl_per_session - 0.1 / 12) < 1e-9
    assert legacy.controller_cpu["mean"] is not None and abs(legacy.controller_cpu["mean"] - 0.01) < 1e-9
    assert legacy.core_rss["reference_kib"] == 50_000.0 and legacy.core_rss["within_20pct"] is True
    assert v2.orphans_max == 2 and legacy.checks == {"OK": 1}
    assert legacy.unexplained_store_changes == 0


def test_core_rss_hourly_flags_a_drift_over_20_percent() -> None:
    w = Window("x", 0.0, 4 * 3600.0, "v2")
    rows = [{"t": h * 3600.0 + 60, "core": {"rss_kib": kib}} for h, kib in enumerate([90, 100, 110, 125])]
    rss = core_rss_hourly(rows, w)
    assert rss["reference_kib"] == 100.0 and abs(rss["max_deviation"] - 0.25) < 1e-9 and rss["within_20pct"] is False


def test_death_to_restart_takes_the_next_boot_of_that_session() -> None:
    incs = incarnations(agent_log(), lambda inc: False)
    w = Window("x", T0, T0 + 3600, "legacy")
    faults = [{"t": T0 + 1800, "kind": "probe-kill", "sessions": ["s1"]}, {"t": T0 + 1900, "kind": "probe-kill", "sessions": ["s9"]}]
    assert death_to_restart(faults, incs, w) == [40.0]


def test_render_markdown_has_the_soak_table_and_drills() -> None:
    text = render_markdown(compute(inputs()))
    assert "| S1 | lost first turns | 0 | 0 | 0 |" in text
    assert "| S2 | duplicated first turns | 0 | 0 | 1 |" in text
    assert "| agent-kill |" in text and "C2 pass; x recorded" in text
    assert "### soak-legacy (legacy)" in text and "`observe`: latency p50/p95/p99 30 / 30 / 30 ms" in text
    summary = first_turn_summary(compute(inputs()))
    assert summary.startswith("incarnations 3: exact 2, lost 0, duplicated 1")
    assert "| S7 | no abort | yes | yes | yes |" in text


SWITCHED = T0 + 14 * 3600
"""Two hours after the switch to v2."""


def with_steady_survivor(boot: float, beacons: Sequence[float]) -> ReportInputs:
    """:func:`inputs` with a ``bringup`` phase before ``soak-legacy``, as
    ``soak-phase4 start`` records it, and a steady session that lives to the
    end: booted at ``boot`` and typed a first turn at each of ``beacons``."""
    inp = inputs()
    inp.phases.insert(0, {"t": T0 - 3600, "phase": "bringup", "reconciler": "legacy"})
    inc = "bt:400:4"
    inp.agent_records.append(rec("boot", boot, inc, session_id="s3", template="soak-steady"))
    inp.agent_records.extend(rec("in", t, inc, text=BEACON, beacon=True) for t in beacons)
    inp.agent_records.append(rec("hb", T0 + 23 * 3600, inc))
    return inp


@pytest.mark.parametrize(
    "boot, beacons, s1, s2",
    [
        # booted in bringup, before soak-legacy, and typed its first turn again after the switch
        (T0 - 10, (T0 - 7, SWITCHED), "0 | 0", "0 | 2"),
        # booted in the legacy half and typed its first turn again after the switch
        (T0 + 100, (T0 + 103, SWITCHED), "0 | 0", "0 | 2"),
        # booted in bringup and never typed one: lost 180 s after boot, in the legacy half
        (T0 - 10, (), "1 | 0", "0 | 1"),
    ],
    ids=["bringup-born-duplicated-after-the-switch", "legacy-born-duplicated-after-the-switch", "bringup-born-lost"],
)
def test_s1_and_s2_count_a_lost_or_duplicated_first_turn_in_the_half_its_verdict_came_in(
    boot: float, beacons: Tuple[float, ...], s1: str, s2: str
) -> None:
    text = render_markdown(compute(with_steady_survivor(boot, beacons)))
    assert f"| S1 | lost first turns | 0 | {s1} |" in text
    assert f"| S2 | duplicated first turns | 0 | {s2} |" in text


END = T0 + 24 * 3600
"""When ``soak-phase4 end`` records ``soak-end``; the report runs after its 15-minute settle."""


def with_a_settle(boot: float, beacons: Sequence[float]) -> ReportInputs:
    """:func:`inputs` with ``soak-end`` recorded at ``END`` and the report run
    at the end of its settle, and a steady session booted at ``boot`` that
    typed a first turn at each of ``beacons`` and lives to the report."""
    inp = inputs()
    inp.now = END + 900
    inp.phases.append({"t": END, "phase": "soak-end", "reconciler": "v2"})
    inc = "bt:500:5"
    inp.agent_records.append(rec("boot", boot, inc, session_id="s4", template="soak-steady"))
    inp.agent_records.extend(rec("in", t, inc, text=BEACON, beacon=True) for t in beacons)
    inp.agent_records.append(rec("hb", END + 890, inc))
    return inp


@pytest.mark.parametrize(
    "boot, beacons, s1, s2",
    [
        # booted 60 s before soak-end and never typed one: lost 180 s after boot, in the settle
        (END - 60, (), "0 | 1", "0 | 1"),
        # booted in the v2 half and typed its first turn again 30 s into the settle
        (END - 600, (END - 597, END + 30), "0 | 0", "0 | 2"),
    ],
    ids=["lost-in-the-settle", "duplicated-in-the-settle"],
)
def test_s1_and_s2_count_a_verdict_that_came_in_the_settle_in_the_v2_half(
    boot: float, beacons: Tuple[float, ...], s1: str, s2: str
) -> None:
    report = compute(with_a_settle(boot, beacons))
    assert [m.window.name for m in report.phases] == ["soak-legacy", "soak-v2", "soak-end"]
    text = render_markdown(report)
    assert f"| S1 | lost first turns | 0 | {s1} |" in text
    assert f"| S2 | duplicated first turns | 0 | {s2} |" in text


def test_a_survivor_counts_its_first_turn_failure_once_and_its_latency_by_boot() -> None:
    bringup, legacy, v2 = compute(with_steady_survivor(T0 - 10, (T0 - 7, SWITCHED))).phases
    assert [m.window.name for m in (bringup, legacy, v2)] == ["bringup", "soak-legacy", "soak-v2"]
    assert [m.incarnations for m in (bringup, legacy, v2)] == [1, 2, 1]
    assert [sum(m.first_turns.values()) for m in (bringup, legacy, v2)] == [0, 2, 2]
    assert bringup.bad_first_turns == [] and legacy.bad_first_turns == []
    assert sorted(v2.bad_first_turns) == ["s2 bt:300:3 duplicated", "s3 bt:400:4 duplicated"]
    assert (bringup.first_turn_latency["n"], bringup.first_turn_latency["p50"]) == (1.0, 3.0)
    assert (v2.first_turn_latency["n"], v2.first_turn_latency["p50"]) == (1.0, 5.0)
    assert first_turn_summary(compute(with_steady_survivor(T0 - 10, (T0 - 7, SWITCHED)))).startswith(
        "incarnations 4: exact 2, lost 0, duplicated 2"
    )


def test_s7_reads_the_hit_of_a_check_run_whose_line_was_cut_to_fit() -> None:
    outcome = Outcome(T0 + 13 * 3600 + 300, "soak-v2", "abort")
    outcome.judge(Finding("AP7", "foreign hc runtime: " + ", ".join(f"hold pid {1000 + i} (/home/soak/.local/state/x{i})" for i in range(150))))
    line = encode_line(outcome.as_rec())
    cut = json.loads(line)
    assert len(line) < LINE_LIMIT and cut["truncated"] is True
    assert cut["status"] == HIT and [h["id"] for h in cut["hits"]] == ["AP7"]
    inp = inputs()
    inp.checks.append(cut)
    assert "| S7 | no abort | yes | yes | no (1 hit runs) |" in render_markdown(compute(inp))


def test_s7_is_unknown_for_a_check_run_without_a_status_or_a_half_without_check_runs() -> None:
    assert CHECK_STATUSES == (OK, WARN, HIT)
    inp = inputs()
    inp.checks.append({"t": T0 + 14 * 3600, "truncated": True})
    report = compute(inp)
    assert report.phases[1].checks == {"WARN": 1, "unknown": 1}
    assert "| S7 | no abort | yes | yes | unknown (1 runs without a status) |" in render_markdown(report)
    inp.checks[:] = [c for c in inp.checks if c["t"] < T0 + 12 * 3600]
    assert "| S7 | no abort | yes | yes | unknown (no check run) |" in render_markdown(compute(inp))


def final_check(hit: bool) -> Rec:
    """The record of ``check --final`` 1 s before the settle ends."""
    outcome = Outcome(END + 899, "soak-end", "abort")
    if hit:
        outcome.judge(Finding("AP8", "the canary is on disk: /home/soak/R/x/screen.log"))
    out = outcome.as_rec()
    out["final"] = True
    return out


@pytest.mark.parametrize(
    "final, v2_checks, s7",
    [
        (final_check(hit=True), True, "no (1 hit runs)"),
        ({"t": END + 899, "truncated": True}, True, "unknown (1 runs without a status)"),
        (final_check(hit=False), True, "yes"),
        (final_check(hit=False), False, "unknown (no check run)"),
    ],
    ids=["final-hit", "final-without-a-status", "final-ok", "only-the-settle-has-check-runs"],
)
def test_s7_of_the_v2_half_takes_in_the_check_runs_of_the_settle(final: Rec, v2_checks: bool, s7: str) -> None:
    inp = inputs()
    inp.now = END + 900
    inp.phases.append({"t": END, "phase": "soak-end", "reconciler": "v2"})
    if not v2_checks:
        inp.checks[:] = [c for c in inp.checks if c["t"] < T0 + 12 * 3600]
    inp.checks.append(final)
    report = compute(inp)
    assert [m.window.name for m in report.phases] == ["soak-legacy", "soak-v2", "soak-end"]
    assert f"| S7 | no abort | yes | yes | {s7} |" in render_markdown(report)


def test_render_markdown_counts_ops_ended_by_a_signal_by_who_ended_them() -> None:
    src = inputs()
    src.optrace = optrace() + [
        "E 5000000000 9001 77 gc /p/gc-runtime-herdr-core watch-startup s1",
        "X 5241000000 9001 9 241 122000",
        "E 6000000000 9002 77 gc /p/gc-runtime-herdr-core watch-startup s2",
        "X 6300000000 9002 9 300 122000",
        "E 7000000000 9003 900 gc /p/gc-runtime-herdr-core set-meta s1 K",
        "X 7069000000 9003 15 69 61000",
        "E 8000000000 9004 77 gc /p/gc-runtime-herdr-core is-running s1",
        "X 8100000000 9004 9 100 1000",
        "E 9000000000 9005 77 gc /p/gc-runtime-herdr-core observe",
        "X 12990000000 9005 15 3990 1000",
        "E 13000000000 9006 77 gc /p/gc-runtime-herdr-core peek s1 120",
        "X 13010000000 9006 11 10 1000",
    ]
    text = render_markdown(compute(src))
    assert (
        "ops ended by a signal: 6 (watch-startup closed by gc 2; canceled 1; killed 1; other 1; overrun 1)" in text
    )
    clean = render_markdown(compute(inputs()))
    assert "ops ended by a signal: 0 (watch-startup closed by gc 0; canceled 0; killed 0; other 0; overrun 0)" in clean


def test_load_inputs_reads_a_data_directory(tmp_path: Path) -> None:
    data = tmp_path / "hc-soak"
    (data / "agents").mkdir(parents=True)
    (data / "drills").mkdir()
    (data / "gc-events").mkdir()
    by_session: Dict[str, List[Rec]] = {}
    for r in agent_log():
        sid = "s2" if r["inc"] == "bt:300:3" else "s1"
        by_session.setdefault(sid, []).append(r)
    for sid, recs in by_session.items():
        for r in recs:
            append_jsonl(data / "agents" / f"{sid}.jsonl", r)
    src = inputs()
    for name, items in (("load.jsonl", src.load), ("samples.jsonl", src.samples), ("faults.jsonl", src.faults), ("phases.jsonl", src.phases), ("check.jsonl", src.checks)):
        for item in items:
            append_jsonl(data / name, item)
    for e in src.events:
        append_jsonl(data / "gc-events" / "events.jsonl", e)
    (data / "drills" / "agent-kill-x.json").write_text(json.dumps(src.drills[0]), encoding="utf-8")
    (data / "drills" / "reboot-pending.json").write_text(json.dumps({"t_inject": 1}), encoding="utf-8")
    (data / "check-state.json").write_text(json.dumps({"workflows": src.workflows}), encoding="utf-8")
    trace = tmp_path / "optrace.log"
    trace.write_text("\n".join(optrace()) + "\n", encoding="utf-8")
    loaded = load_inputs(data, trace, src.alive, src.now)
    assert len(loaded.drills) == 1 and loaded.workflows == src.workflows
    assert render_markdown(compute(loaded)) == render_markdown(compute(src)).replace(src.city, loaded.city)


def phases_and_samples(tmp_path: Path) -> Path:
    """A city's data directory with :func:`inputs`' phases and samples only,
    which place the op trace's clock in each half."""
    data = tmp_path / "hc-soak"
    data.mkdir()
    src = inputs()
    for name, items in (("phases.jsonl", src.phases), ("samples.jsonl", src.samples)):
        for item in items:
            append_jsonl(data / name, item)
    return data


def trace_of(text: str) -> Callable[[Path], object]:
    return lambda path: path.write_text(text, encoding="utf-8")


S5_ROW = "| S5 | controller-spawned pack ops / s / session | ≤ 0.30 / ≤ 0.05 |"
NO_OPS = "- pack ops / s: all 0.000; controller-spawned 0.000; per session 0.0000"


@pytest.mark.parametrize(
    "make, legacy, v2",
    [
        # no trace file
        (lambda path: None, "unknown (op trace missing or unreadable)", "unknown (op trace missing or unreadable)"),
        # a directory where the trace should be: reading it fails
        (Path.mkdir, "unknown (op trace missing or unreadable)", "unknown (op trace missing or unreadable)"),
        # bpftrace never reached BEGIN
        (trace_of("Attaching 3 probes...\n"), "unknown (op trace has no start line)", "unknown (op trace has no start line)"),
        # started two hours into the legacy half, whose rate it would understate
        (trace_of(f"B {2 * 3600 * 10**9}\n"), "unknown (op trace started after the phase did)", "0.0000"),
        # ran from the start of the soak and saw no op: a measured zero
        (trace_of("B 0\n"), "0.0000", "0.0000"),
        # restarted two hours into the legacy half: its first start still covers the half
        (trace_of(f"B 0\nB {2 * 3600 * 10**9}\n"), "0.0000", "0.0000"),
    ],
    ids=["missing", "unreadable", "never-started", "started-in-the-legacy-half", "ran-and-saw-no-op", "restarted-in-the-legacy-half"],
)
def test_s5_is_unknown_unless_the_op_trace_ran_from_the_start_of_the_half(
    tmp_path: Path, make: Callable[[Path], object], legacy: str, v2: str
) -> None:
    trace = tmp_path / "optrace.log"
    make(trace)
    text = render_markdown(compute(load_inputs(phases_and_samples(tmp_path), trace, lambda inc: False, T0 + 24 * 3600)))
    assert f"{S5_ROW} {legacy} | {v2} |" in text
    for cell in (legacy, v2):
        assert (NO_OPS if cell == "0.0000" else f"- pack ops: {cell}") in text


def test_s5_is_unknown_without_samples_to_time_the_op_trace_by() -> None:
    inp = inputs()
    inp.samples = [{k: v for k, v in s.items() if k != "mono_ns"} for s in inp.samples]
    gap = "unknown (no samples to time the op trace by)"
    assert f"{S5_ROW} {gap} | {gap} |" in render_markdown(compute(inp))


def test_a_restart_across_an_operator_stop_and_start_is_explained() -> None:
    a, b = "bt:100:1", "bt:200:2"
    records = [
        rec("boot", T0, a, session_id="s1", template="soak-burst"),
        rec("hb", T0 + 60, a),
        rec("boot", T0 + 3600, b, session_id="s1", template="soak-burst"),
    ]
    incs = incarnations(records, lambda inc: inc == b)
    window = Window("w", T0 + 1800, T0 + 7200, "legacy")
    notes = [
        {"t": T0 + 100, "kind": "note", "what": "city-stop", "covers": ["all"]},
        {"t": T0 + 3500, "kind": "note", "what": "city-start", "covers": ["all"]},
    ]
    assert restart_causes(incs, notes, window) == {"starts": 1, "probe": 0, "drill": 0, "operator": 1, "unexplained": 0}
    narrow = [{"t": T0 + 100, "kind": "note", "what": "supervisor-restart", "covers": ["supervisor", "controller", "store"]}]
    assert restart_causes(incs, narrow, window)["unexplained"] == 1
    assert restart_causes(incs, [], window)["unexplained"] == 1


def replaced_by_a_new_session() -> List[Rec]:
    """The legacy reconciler's answer to a probe kill: the killed always-on
    session is closed and a new session of the same template starts."""
    a, b, c, d = "bt:100:1", "bt:200:2", "bt:300:3", "bt:400:4"
    return [
        rec("boot", T0, a, session_id="s1", template="soak-steady"),
        rec("boot", T0 + 5, b, session_id="s2", template="soak-steady"),
        # a demand session of another template starts right after the kill
        rec("boot", T0 + 1810, c, session_id="b1", template="soak-burst"),
        # s1 was killed at T0 + 1800; gc starts n1 in its place
        rec("boot", T0 + 1912, d, session_id="n1", template="soak-steady"),
    ]


def test_a_probe_kill_answered_by_a_new_session_is_a_probe_restart() -> None:
    incs = incarnations(replaced_by_a_new_session(), lambda inc: False)
    w = Window("x", T0 + 600, T0 + 3600, "legacy")
    faults = [{"t": T0 + 1800, "kind": "probe-kill", "pids": [100], "sessions": ["s1"]}]
    assert restart_causes(incs, faults, w) == {"starts": 2, "probe": 1, "drill": 0, "operator": 0, "unexplained": 0}
    assert death_to_restart(faults, incs, w) == [112.0]


def test_one_new_session_answers_one_probe_kill_and_a_same_id_restart_wins() -> None:
    records = replaced_by_a_new_session() + [rec("boot", T0 + 1850, "bt:500:5", session_id="s2", template="soak-steady")]
    incs = incarnations(records, lambda inc: False)
    w = Window("x", T0 + 600, T0 + 3600, "legacy")
    faults = [
        {"t": T0 + 1800, "kind": "probe-kill", "pids": [100], "sessions": ["s1"]},
        {"t": T0 + 1801, "kind": "probe-kill", "pids": [200], "sessions": ["s2"]},
        {"t": T0 + 1802, "kind": "probe-kill", "pids": [1], "sessions": ["gone"]},
    ]
    assert restart_causes(incs, faults, w) == {"starts": 3, "probe": 2, "drill": 0, "operator": 0, "unexplained": 0}
    assert death_to_restart(faults, incs, w) == [112.0, 49.0]


def test_a_new_session_long_after_a_probe_kill_does_not_answer_it() -> None:
    a, b = "bt:100:1", "bt:400:4"
    records = [
        rec("boot", T0, a, session_id="s1", template="soak-steady"),
        # s1 was killed at T0 + 1800; a new session of its template starts 11 minutes later
        rec("boot", T0 + 1800 + 660, b, session_id="n1", template="soak-steady"),
    ]
    incs = incarnations(records, lambda inc: False)
    w = Window("x", T0 + 600, T0 + 3600, "legacy")
    faults = [{"t": T0 + 1800, "kind": "probe-kill", "pids": [100], "sessions": ["s1"]}]
    assert restart_causes(incs, faults, w)["probe"] == 0
    assert death_to_restart(faults, incs, w) == []


def test_a_new_session_of_a_pool_that_scales_does_not_answer_a_probe_kill() -> None:
    a, b = "bt:100:1", "bt:400:4"
    records = [
        rec("boot", T0, a, session_id="b1", template="soak-burst"),
        rec("boot", T0 + 1830, b, session_id="b2", template="soak-burst"),
    ]
    incs = incarnations(records, lambda inc: False)
    w = Window("x", T0 + 600, T0 + 3600, "legacy")
    faults = [{"t": T0 + 1800, "kind": "probe-kill", "pids": [100], "sessions": ["b1"]}]
    assert restart_causes(incs, faults, w)["probe"] == 0
    assert death_to_restart(faults, incs, w) == []
