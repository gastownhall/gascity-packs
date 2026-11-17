from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

import pytest

from soakanalysis import FT_DUPLICATED, FT_EXACT, FT_LOST, FirstTurn, HcProc, NudgeVerdict, OpStats
from soakcheck import (
    HIT,
    OK,
    WARN,
    Inputs,
    State,
    canary_scan,
    digest,
    evaluate,
    read_new_lines,
    read_tail_lines,
)

NOW = 100_000.0
CORE = ("/home/soak/.local/state/gc-runtime-herdr-core", "gc-hc-soak")


def healthy(**overrides: Any) -> Inputs:
    """Inputs on which every predicate passes."""
    inp = Inputs(
        now=NOW,
        phase="soak-legacy",
        phase_start=NOW - 7200,
        reconciler="legacy",
        health=[(True, "")],
        supervisor=(77, 1000),
        store=[(40, 10, "db-proxy-child"), (41, 11, "dolt")],
        faults=[],
        controller_starts=[NOW - 7000],
        first_turns=[FirstTurn("i1", "s1", FT_EXACT, 1, NOW - 600, 3.0, True)],
        ops=OpStats(seconds=900.0, sessions=12.0, ops=900, ctl_ops=800, ctl_cpu_us=int(0.05 * 900 * 1e6)),
        sizes={"R": 1 << 20, "hc_state": 1 << 20},
        hc=[HcProc(5, 1, "serve", CORE[0], CORE[1], ""), HcProc(6, 1, "hold", CORE[0], CORE[1], "")],
        city_core=CORE,
        canary_hits=[],
        samples_age_s=30.0,
        trace_age_s=5.0,
        events_age_s=5.0,
        boxes_now=12,
        box_count=12,
        core_pid=5,
        holders=[6],
    )
    for key, value in overrides.items():
        setattr(inp, key, value)
    return inp


def primed() -> State:
    state = State()
    evaluate(healthy(now=NOW - 300), state, "abort")
    return state


def ids(outcome: Any) -> List[str]:
    return [f.id for f in outcome.hits]


def test_a_healthy_run_is_ok() -> None:
    out = evaluate(healthy(), primed(), "abort")
    assert out.status == OK and not out.hits and not out.warnings and not out.unknown
    assert out.line().endswith("soak-legacy OK - all predicates pass")


def test_ap1_three_failures_or_one_integrity_error() -> None:
    assert ids(evaluate(healthy(health=[(False, "timeout"), (False, "timeout")]), primed(), "abort")) == []
    three = healthy(health=[(False, "dial tcp: refused")] * 3)
    assert ids(evaluate(three, primed(), "abort")) == ["AP1"]
    integrity = healthy(health=[(False, "error: checksum mismatch in chunk")])
    assert ids(evaluate(integrity, primed(), "abort")) == ["AP1"]
    recovered = healthy(health=[(False, "x"), (False, "x"), (True, "")])
    assert ids(evaluate(recovered, primed(), "abort")) == []


def test_ap2_an_infrastructure_process_gone_without_a_fault_record() -> None:
    gone = healthy(store=[(40, 10, "db-proxy-child"), (99, 12, "dolt")])
    out = evaluate(gone, primed(), "abort")
    assert ids(out) == ["AP2"] and "dolt pid 41" in out.hits[0].reason
    covered = healthy(store=[(42, 20, "db-proxy-child")], faults=[{"t": NOW - 100, "kind": "note", "covers": ["supervisor", "controller", "store"]}], supervisor=(78, 2000))
    assert ids(evaluate(covered, primed(), "abort")) == []
    restarted = healthy(supervisor=(78, 2000))
    assert ids(evaluate(restarted, primed(), "abort")) == ["AP2"]
    during_drill = healthy(store=[], drill=True)
    assert ids(evaluate(during_drill, primed(), "abort")) == []


def test_ap3_more_than_three_unexplained_controller_starts_in_15_minutes() -> None:
    starts = [NOW - 60 * i for i in range(1, 5)]
    assert ids(evaluate(healthy(controller_starts=starts[:3]), primed(), "abort")) == []
    assert ids(evaluate(healthy(controller_starts=starts), primed(), "abort")) == ["AP3"]
    excused = healthy(controller_starts=starts, faults=[{"t": NOW - 120, "kind": "note", "covers": ["controller"]}])
    assert ids(evaluate(excused, primed(), "abort")) == []


def test_ap4_a_lost_or_duplicated_first_turn_in_the_phase() -> None:
    lost = healthy(first_turns=[FirstTurn("i2", "s2", FT_LOST, 0, NOW - 600, None, False)])
    assert ids(evaluate(lost, primed(), "abort")) == ["AP4"]
    dup = healthy(first_turns=[FirstTurn("i3", "s3", FT_DUPLICATED, 2, NOW - 600, 1.0, True)])
    assert ids(evaluate(dup, primed(), "abort")) == ["AP4"]
    before_phase = healthy(first_turns=[FirstTurn("i2", "s2", FT_LOST, 0, NOW - 9000, None, False)])
    assert ids(evaluate(before_phase, primed(), "abort")) == []


def test_ap5_twice_the_budget() -> None:
    # legacy: 2 x 0.30 x 12 = 7.2 ops/s; v2: 2 x 0.05 x 12 = 1.2 ops/s
    busy = OpStats(seconds=900.0, sessions=12.0, ops=7000, ctl_ops=900 * 7, ctl_cpu_us=0)
    assert ids(evaluate(healthy(ops=busy), primed(), "abort")) == []
    assert ids(evaluate(healthy(ops=busy, reconciler="v2"), primed(), "abort")) == ["AP5"]
    hot = OpStats(seconds=900.0, sessions=12.0, ops=10, ctl_ops=10, ctl_cpu_us=int(0.4 * 900 * 1e6))
    assert ids(evaluate(healthy(ops=hot), primed(), "abort")) == ["AP5"]


def test_ap6_state_size() -> None:
    assert ids(evaluate(healthy(sizes={"R": 5 << 30, "hc_state": 1}), primed(), "abort")) == ["AP6"]
    assert ids(evaluate(healthy(sizes={"R": 1, "hc_state": 3 << 30}), primed(), "abort")) == ["AP6"]


def test_ap7_foreign_runtime_or_two_cores() -> None:
    foreign = healthy(hc=[HcProc(5, 1, "serve", CORE[0], CORE[1], ""), HcProc(9, 1, "serve", "/tmp/hcconf.x/state", "s", "")])
    assert ids(evaluate(foreign, primed(), "abort")) == ["AP7"]
    foreign.conformance = True
    assert ids(evaluate(foreign, primed(), "abort")) == []
    two = healthy(hc=[HcProc(5, 1, "serve", CORE[0], CORE[1], ""), HcProc(7, 1, "serve", CORE[0], CORE[1], "")])
    assert ids(evaluate(two, primed(), "abort")) == ["AP7"]


def test_ap8_the_canary_on_disk() -> None:
    assert ids(evaluate(healthy(canary_hits=["/R/x/screen.log"]), primed(), "abort")) == ["AP8"]
    assert ids(evaluate(healthy(canary_hits=None), primed(), "abort")) == []


def test_ap9_blind_on_three_consecutive_runs() -> None:
    state = primed()
    for i in range(2):
        out = evaluate(healthy(now=NOW + 300 * i, samples_age_s=900.0), state, "abort")
        assert out.status == WARN and "samples" in out.unknown and not out.hits
    out = evaluate(healthy(now=NOW + 600, samples_age_s=900.0), state, "abort")
    assert ids(out) == ["AP9"]
    out = evaluate(healthy(now=NOW + 900), state, "abort")
    assert out.status == OK and state.unknown == {}
    silent_trace = healthy(trace_age_s=1200.0)
    assert "trace" in evaluate(silent_trace, primed(), "abort").unknown
    assert "trace" not in evaluate(healthy(trace_age_s=1200.0, boxes_now=0), primed(), "abort").unknown


def test_warnings_never_hit() -> None:
    inp = healthy(
        orphans=["300 sleep"],
        tmux_servers=1,
        nudges=[NudgeVerdict("a" * 32, "s1", NOW - 2000, "queue", "queued", "lost", None)],
        stale_spawn_files=["/run/user/1000/gc-herdr-core/x"],
        mem_avail_kib=500_000,
        disk_free_bytes=5 << 30,
        doctor_failed=2,
        workflows_open_30m=1,
    )
    out = evaluate(inp, primed(), "abort")
    assert not out.hits and out.status == WARN
    assert {f.id for f in out.warnings} == {"W-orphans", "W-tmux", "W-nudges", "W-spawn-files", "W-memory", "W-disk", "W-doctor", "W-workflows-open"}


def test_box_count_out_of_range_warns_after_15_minutes_outside_the_drill_phases() -> None:
    state = primed()
    assert not evaluate(healthy(box_count=4), state, "abort").warnings
    out = evaluate(healthy(now=NOW + 900, box_count=4), state, "abort")
    assert [f.id for f in out.warnings] == ["W-boxes"]
    assert not evaluate(healthy(now=NOW + 1800, box_count=4, phase="drills"), State(), "warn").warnings


def test_unexplained_core_restart_and_holder_loss_warn() -> None:
    state = primed()
    out = evaluate(healthy(core_pid=55, holders=[]), state, "abort")
    assert {f.id for f in out.warnings} == {"W-core", "W-holder"}
    state = primed()
    covered = healthy(core_pid=55, holders=[], faults=[{"t": NOW - 10, "kind": "drill-core-kill", "covers": ["core"]}])
    assert not evaluate(covered, state, "abort").warnings


def test_outcome_line_names_every_hit() -> None:
    out = evaluate(healthy(sizes={"R": 5 << 30, "hc_state": 3 << 30}), primed(), "abort")
    assert out.status == HIT
    assert " soak-legacy HIT AP6 AP6: " in out.line()


def test_state_round_trip(tmp_path: Path) -> None:
    state = primed()
    state.workflows = {"w1": {"t": 1.0}}
    path = tmp_path / "check-state.json"
    state.save(path)
    again = State.load(path)
    assert again == state
    path.write_text(json.dumps({"last_t": 5.0, "unknown_field": 1}), encoding="utf-8")
    assert State.load(path).last_t == 5.0
    assert State.load(tmp_path / "missing.json") == State()


def test_digest_counts_the_last_hour() -> None:
    outcomes = [
        {"t": NOW - 7200, "status": "HIT", "hits": [{"id": "AP1"}], "warnings": []},
        {"t": NOW - 600, "status": "OK", "hits": [], "warnings": []},
        {"t": NOW - 300, "status": "WARN", "hits": [], "warnings": [{"id": "W-tmux"}]},
    ]
    text = digest(outcomes, NOW)
    assert "2 checks in the last hour" in text and "OK 1, WARN 1" in text and "W-tmux x1" in text and "AP1" not in text


def test_canary_scan_finds_it_across_a_chunk_boundary(tmp_path: Path) -> None:
    canary = "soakcanary" + "f" * 32
    root = tmp_path / "R"
    (root / "a").mkdir(parents=True)
    (root / "a" / "clean.log").write_text("nothing here\n", encoding="utf-8")
    big = b"x" * ((1 << 20) - 5) + canary.encode() + b"\n"
    (root / "a" / "screen.log").write_bytes(big)
    os_link = root / "link"
    os_link.symlink_to(root / "a" / "screen.log")
    hits = canary_scan([root, tmp_path / "missing"], canary)
    assert hits == [str(root / "a" / "screen.log")]


def test_read_new_and_tail_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("one\ntwo\nthr", encoding="utf-8")
    lines, offset = read_new_lines(path, 0)
    assert lines == ["one", "two"] and offset == 8
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("ee\n")
    assert read_new_lines(path, offset) == (["three"], 14)
    path.write_text("a\n", encoding="utf-8")
    assert read_new_lines(path, 14) == (["a"], 2)
    path.write_text("first\nsecond\nthird\n", encoding="utf-8")
    assert read_tail_lines(path, 9) == ["third"]
    assert read_tail_lines(path, 1000) == ["first", "second", "third"]


@pytest.mark.parametrize("mode", ["warn", "abort"])
def test_mode_is_recorded(mode: str) -> None:
    assert evaluate(healthy(), primed(), mode).as_rec()["mode"] == mode
