from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .soaktestkit import rec

from soaklib import Rec, append_jsonl
from soakreport import (
    ReportInputs,
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
    trace.write_text("\n".join(src.optrace) + "\n", encoding="utf-8")
    loaded = load_inputs(data, trace, src.alive, src.now)
    assert len(loaded.drills) == 1 and loaded.workflows == src.workflows
    assert render_markdown(compute(loaded)) == render_markdown(compute(src)).replace(src.city, loaded.city)
