from __future__ import annotations

import errno
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from soaklib import City, CmdResult, ProcFS, SoakPaths
from soakhc import CoreTuple, HcError
from soakanalysis import (
    ENDED_CANCELED,
    ENDED_CLOSED,
    ENDED_KILLED,
    ENDED_OTHER,
    ENDED_OVERRUN,
    FT_DUPLICATED,
    FT_EXACT,
    FT_LOST,
    FirstTurn,
    HcProc,
    NudgeVerdict,
    OpStats,
    first_turns,
    hc_runtime,
    incarnations,
)
from soakcheck import (
    AGENT_LOG_GRACE_S,
    HIT,
    OK,
    RECORD_ONLY,
    WARN,
    WORKFLOW_KEEP_S,
    Collector,
    Inputs,
    Outcome,
    State,
    canary_scan,
    digest,
    evaluate,
    read_new_lines,
    read_tail_lines,
    workflow_closures,
)

from .soaktestkit import ProcTree, rec

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
    before_phase = healthy(first_turns=[FirstTurn("i2", "s2", FT_LOST, 0, NOW - 9000, None, False, NOW - 8820)])
    assert ids(evaluate(before_phase, primed(), "abort")) == []
    # A bad first turn with no verdict time is judged, whatever its boot.
    unknown_time = healthy(first_turns=[FirstTurn("i2", "s2", FT_LOST, 0, NOW - 9000, None, False)])
    assert ids(evaluate(unknown_time, primed(), "abort")) == ["AP4"]


# --- AP4 across a phase boundary, through the real incarnation and first-turn analysis -----------

SWITCH = NOW - 300  # the phase began here; the survivor booted 100 s before it
SURVIVOR = "b00tb00t:100:5000"
STEADY_BEACON = "[hc-soak] soak-steady-1 • 2026-11-19T10:00:00"


def survivor(*beacons: float) -> List[FirstTurn]:
    """The first turn, as the check sees it at NOW, of a live session booted at
    ``SWITCH - 100`` that received a beacon line at each of ``beacons``."""
    records = [rec("boot", SWITCH - 100, SURVIVOR, session_id="s1", session_name="soak-steady-1", template="soak-steady")]
    records += [rec("in", t, SURVIVOR, text=STEADY_BEACON, beacon=True) for t in beacons]
    return first_turns(incarnations(records, lambda inc: True), [], NOW)


def ap4(turns: List[FirstTurn], last_t: float, final: bool = False) -> List[str]:
    """AP4's answer at NOW in the phase that began at ``SWITCH``, the previous run at ``last_t``."""
    inp = healthy(phase="soak-v2", phase_start=SWITCH, reconciler="v2", first_turns=turns, final=final)
    return [i for i in ids(evaluate(inp, State(last_t=last_t), "abort")) if i == "AP4"]


def test_ap4_judges_a_survivor_s_second_first_turn_in_the_phase_it_came_in() -> None:
    turns = survivor(SWITCH - 99, SWITCH + 50)
    assert [(t.status, t.boot_t, t.verdict_t) for t in turns] == [(FT_DUPLICATED, SWITCH - 100, SWITCH + 50)]
    assert ap4(turns, last_t=NOW - 100) == ["AP4"]
    assert ap4(turns, last_t=0.0) == ["AP4"]  # the phase's first run, and no run before it
    assert ap4(survivor(SWITCH - 99), last_t=NOW - 100) == []  # the control: one first turn


def test_ap4_judges_a_survivor_s_loss_that_matures_after_the_switch() -> None:
    turns = survivor()
    assert [(t.status, t.verdict_t) for t in turns] == [(FT_LOST, SWITCH + 80)]
    assert ap4(turns, last_t=NOW - 100) == ["AP4"]


def test_ap4_judges_a_verdict_from_before_the_switch_once_and_only_if_no_run_saw_it() -> None:
    turns = survivor(SWITCH - 99, SWITCH - 50)
    assert ap4(turns, last_t=SWITCH - 60) == ["AP4"]  # it came after the old phase's last run
    assert ap4(turns, last_t=SWITCH - 40) == []  # the old phase's last run judged it
    assert ap4(turns, last_t=NOW - 100) == []  # an earlier run of this phase judged it
    assert ap4(turns, last_t=NOW - 100, final=True) == ["AP4"]  # --final judges every incarnation


def test_ap4_cannot_evaluate_an_unlogged_agent_and_still_hits_on_the_logged_ones() -> None:
    blind = evaluate(healthy(unlogged_agents=["s2 pid 4002"]), primed(), "abort")
    assert ids(blind) == [] and blind.status == WARN
    assert blind.unknown == {"AP4": "1 live scripted agent(s) with no agent log: s2 pid 4002"}
    lost = healthy(first_turns=[FirstTurn("i2", "s2", FT_LOST, 0, NOW - 600, None, False)], unlogged_agents=["s3 pid 4003"])
    assert ids(evaluate(lost, primed(), "abort")) == ["AP4"]
    assert evaluate(healthy(first_turns=None), primed(), "abort").unknown == {"AP4": "no agent-log directory"}


def warning_ids(outcome: Any) -> List[str]:
    return [f.id for f in outcome.warnings]


def test_ap5_twice_the_budget_is_record_only() -> None:
    # legacy: 2 x 0.30 x 12 = 7.2 ops/s; v2: 2 x 0.05 x 12 = 1.2 ops/s
    assert RECORD_ONLY == frozenset({"AP5"})
    busy = OpStats(seconds=900.0, sessions=12.0, ops=7000, ctl_ops=900 * 7, ctl_cpu_us=0)
    out = evaluate(healthy(ops=busy), primed(), "abort")
    assert out.status == OK and out.perf is not None and out.perf["rate_limit"] == pytest.approx(7.2)
    over = evaluate(healthy(ops=busy, reconciler="v2"), primed(), "abort")
    assert ids(over) == [] and over.status == WARN and warning_ids(over) == ["AP5"]
    assert over.warnings[0].reason.startswith("record-only: controller-spawned ops 7.000/s over 1.200/s")
    assert over.as_rec()["perf"] == {
        "reconciler": "v2",
        "n": 12.0,
        "rate_ctl": pytest.approx(7.0),
        "rate_limit": pytest.approx(1.2),
        "ctl_cpu_cores": 0.0,
        "cpu_limit": pytest.approx(0.36),
        "record_only": True,
    }
    hot = OpStats(seconds=900.0, sessions=12.0, ops=10, ctl_ops=10, ctl_cpu_us=int(0.4 * 900 * 1e6))
    out = evaluate(healthy(ops=hot), primed(), "abort")
    assert ids(out) == [] and warning_ids(out) == ["AP5"] and "0.400 cores over 0.360" in out.warnings[0].reason


def test_ap5_over_budget_never_aborts_while_a_correctness_predicate_still_does(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import soakcheck

    busy = OpStats(seconds=900.0, sessions=12.0, ops=7000, ctl_ops=900 * 7, ctl_cpu_us=int(0.4 * 900 * 1e6))
    aborts: List[Any] = []
    stops: List[Any] = []
    monkeypatch.setattr(soakcheck, "abort", lambda city, outcome, paths, gc, procfs: aborts.append(outcome))
    monkeypatch.setattr(soakcheck, "stop_city", lambda city, state, state_path, gc, procfs: stops.append(city))

    class FakeCollector:
        inputs: Inputs

        def __init__(self, *args: Any) -> None:
            pass

        def collect(self, state: State, final: bool = False) -> Inputs:
            return FakeCollector.inputs

    monkeypatch.setattr(soakcheck, "Collector", FakeCollector)
    city = City(name="hc-soak", path=tmp_path, data=tmp_path, mode="abort")
    for i in range(4):
        FakeCollector.inputs = healthy(now=NOW + 300 * i, ops=busy, reconciler="v2")
        assert soakcheck._check(city, None, False, "gc") == 0  # type: ignore[arg-type]
    assert aborts == [] and stops == [] and not State.load(tmp_path / "check-state.json").aborted
    log = (tmp_path / "check.log").read_text(encoding="utf-8").splitlines()
    assert len(log) == 4 and all(" WARN AP5 AP5: record-only: controller-spawned ops 7.000/s over 1.200/s" in line for line in log)
    recs = [json.loads(line) for line in (tmp_path / "check.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(r["status"] == WARN and r["hits"] == [] and r["perf"]["rate_ctl"] == pytest.approx(7.0) for r in recs)

    FakeCollector.inputs = healthy(now=NOW + 1500, ops=busy, reconciler="v2", first_turns=[FirstTurn("i2", "s2", FT_LOST, 0, NOW - 600, None, False)])
    soakcheck._check(city, None, False, "gc")  # type: ignore[arg-type]
    assert [ids(o) for o in aborts] == [["AP4"]] and warning_ids(aborts[0]) == ["AP5"] and stops == [city]


INTEGRITY_HIT = [(False, "error: checksum mismatch in chunk")]
ABORT_TIMERS = ("soak-hc-soak-v2-switch.timer", "soak-hc-soak-end.timer")
"""The scheduled switch and end of the rig's city, which the abort stops."""


class AbortRig:
    """``_check`` in ``abort`` mode on inputs a test sets, with the abort's
    commands faked: ``systemctl`` exits 0 (or raises ``systemctl_error``), each
    ``gc stop`` exits with the next of ``stop_codes``; ``capture`` raises
    ``capture_error`` when one is given; ``remains`` finds nothing of the
    city, or raises ``remains_error`` once; the collector raises
    ``collect_error`` while a test sets one."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        stop_codes: Sequence[int],
        capture_error: Optional[Exception] = None,
        remains_error: Optional[Exception] = None,
        systemctl_error: Optional[Exception] = None,
    ) -> None:
        import soakcapture
        import soakcheck

        self.city = City(name="hc-soak", path=tmp_path, data=tmp_path, mode="abort")
        self.calls: List[Tuple[str, ...]] = []
        self.inputs = healthy()
        self.collect_error: Optional[Exception] = None
        codes = list(stop_codes)
        raises = [remains_error] if remains_error is not None else []
        rig = self

        def fake_run(argv: Sequence[str], **kwargs: Any) -> CmdResult:
            rig.calls.append(tuple(argv))
            if argv[0] == "systemctl" and systemctl_error is not None:
                raise systemctl_error
            code = codes.pop(0) if tuple(argv[:2]) == ("gc", "stop") else 0
            return CmdResult(tuple(argv), code, "", "" if code == 0 else f"city busy ({code})", 0.1)

        def fake_capture(city: City, paths: SoakPaths, gc: str, procfs: ProcFS) -> Path:
            if capture_error is not None:
                raise capture_error
            return city.data / "captures" / "bundle.tar.gz"

        def fake_remains(city: City, procfs: ProcFS, gc: str = "gc") -> List[str]:
            if raises:
                raise raises.pop()
            return []

        class FakeCollector:
            def __init__(self, *args: Any) -> None:
                pass

            def collect(self, state: State, final: bool = False) -> Inputs:
                if rig.collect_error is not None:
                    raise rig.collect_error
                return rig.inputs

        monkeypatch.setattr(soakcheck, "run", fake_run)
        monkeypatch.setattr(soakcheck, "Collector", FakeCollector)
        monkeypatch.setattr(soakcapture, "capture", fake_capture)
        monkeypatch.setattr(soakcapture, "remains", fake_remains)

    def check(self, **overrides: Any) -> int:
        import soakcheck

        self.inputs = healthy(**overrides)
        return soakcheck._check(self.city, None, False, "gc")  # type: ignore[arg-type]

    def stops(self) -> int:
        return sum(1 for argv in self.calls if argv[:2] == ("gc", "stop"))

    def state(self) -> State:
        return State.load(self.city.data / "check-state.json")

    def aborted(self) -> str:
        return (self.city.data / "ABORTED").read_text(encoding="utf-8")


def test_an_abort_whose_capture_fails_still_stops_the_city(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[0], capture_error=OSError(errno.ENOSPC, "No space left on device"))
    assert rig.check(health=INTEGRITY_HIT) == 0
    assert rig.calls == [
        ("systemctl", "--user", "stop", "soak-load.service", "soak-probe.timer", *ABORT_TIMERS),
        ("gc", "stop", str(tmp_path)),
    ]
    assert rig.aborted().splitlines()[1:] == [
        "  AP1: store integrity error: error: checksum mismatch in chunk",
        "capture: FAILED OSError: [Errno 28] No space left on device",
        "gc stop exit 0: ",
        "after stop: nothing of the city remains",
    ]
    assert rig.state().aborted and rig.state().stopped
    rig.check(now=NOW + 300, health=INTEGRITY_HIT)
    rig.check(now=NOW + 600)
    assert rig.stops() == 1 and len(rig.calls) == 2


def test_a_gc_stop_that_fails_is_run_again_by_each_check_until_it_exits_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[1, 124, 0], remains_error=OSError(errno.EACCES, "Permission denied"))
    rig.check(health=INTEGRITY_HIT)
    assert rig.stops() == 1 and rig.state().aborted and not rig.state().stopped
    rig.check(now=NOW + 300)
    assert rig.stops() == 2 and not rig.state().stopped
    rig.check(now=NOW + 600, health=INTEGRITY_HIT)
    assert rig.stops() == 3 and rig.state().stopped
    rig.check(now=NOW + 900)
    assert rig.stops() == 3 and [argv[0] for argv in rig.calls].count("systemctl") == 1
    assert rig.aborted().splitlines()[2:] == [
        f"capture: {tmp_path / 'captures' / 'bundle.tar.gz'}",
        "gc stop exit 1: city busy (1)",
        "after stop: FAILED PermissionError: [Errno 13] Permission denied",
        "gc stop exit 124: city busy (124)",
        "after stop: nothing of the city remains",
        "gc stop exit 0: ",
        "after stop: nothing of the city remains",
    ]


def test_an_abort_that_raises_before_its_capture_still_stops_the_city(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[0], systemctl_error=PermissionError(errno.EACCES, "Permission denied"))
    with pytest.raises(PermissionError):
        rig.check(health=INTEGRITY_HIT)
    assert rig.stops() == 1 and rig.state().aborted and rig.state().stopped
    assert rig.aborted().splitlines()[2:] == ["gc stop exit 0: ", "after stop: nothing of the city remains"]
    rig.check(now=NOW + 300)
    assert rig.stops() == 1


def test_an_abort_that_raises_and_whose_gc_stop_fails_is_stopped_by_the_next_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[1, 0], systemctl_error=PermissionError(errno.EACCES, "Permission denied"))
    with pytest.raises(PermissionError):
        rig.check(health=INTEGRITY_HIT)
    assert rig.stops() == 1 and rig.state().aborted and not rig.state().stopped
    rig.check(now=NOW + 300)
    assert rig.stops() == 2 and rig.state().stopped
    assert rig.aborted().splitlines()[2:] == [
        "gc stop exit 1: city busy (1)",
        "after stop: nothing of the city remains",
        "gc stop exit 0: ",
        "after stop: nothing of the city remains",
    ]


def test_a_pending_gc_stop_runs_before_the_inputs_are_collected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # the abort's gc stop failed (or that run was killed), and now every
    # collect raises: each run still tries gc stop until one exits 0
    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[1, 0])
    rig.collect_error = PermissionError(errno.EACCES, "Permission denied")
    State(aborted=True).save(tmp_path / "check-state.json")
    for _ in range(3):
        with pytest.raises(PermissionError):
            rig.check()
    assert rig.calls == [("gc", "stop", str(tmp_path))] * 2
    assert rig.state().aborted and rig.state().stopped
    assert rig.aborted().splitlines() == [
        "gc stop exit 1: city busy (1)",
        "after stop: nothing of the city remains",
        "gc stop exit 0: ",
        "after stop: nothing of the city remains",
    ]


def test_the_abort_is_on_disk_before_its_first_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import soakcapture

    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[0])
    fake = soakcapture.capture
    on_disk: List[bool] = []

    def spy(city: City, paths: SoakPaths, gc: str, procfs: ProcFS) -> Path:
        on_disk.append(State.load(city.data / "check-state.json").aborted)
        rig.calls.append(("capture",))
        return fake(city, paths, gc, procfs)

    monkeypatch.setattr(soakcapture, "capture", spy)
    rig.check(health=INTEGRITY_HIT)
    assert on_disk == [True]
    assert rig.calls == [
        ("systemctl", "--user", "stop", "soak-load.service", "soak-probe.timer", *ABORT_TIMERS),
        ("capture",),
        ("gc", "stop", str(tmp_path)),
    ]


RECORDS = ("check.jsonl", "check.log", "digest.log")


@pytest.mark.parametrize("full", RECORDS)
def test_an_abort_whose_records_cannot_be_written_still_stops_the_city(full: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A full disk refuses one of the run's records: the abort and its gc stop
    # still run, the other records are still tried, and the refusal is raised
    # after the stop.
    import soakcheck
    from soaklib import append_jsonl

    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[0])
    append_text = soakcheck._append_text

    def refuse(path: Path) -> None:
        if path.name == full:
            raise OSError(errno.ENOSPC, "No space left on device")

    def jsonl(path: Path, record: Dict[str, Any]) -> None:
        refuse(path)
        append_jsonl(path, record)

    def text(path: Path, data: str) -> None:
        refuse(path)
        append_text(path, data)

    monkeypatch.setattr(soakcheck, "append_jsonl", jsonl)
    monkeypatch.setattr(soakcheck, "_append_text", text)
    with pytest.raises(OSError, match="No space left on device"):
        rig.check(health=INTEGRITY_HIT)
    assert rig.calls == [
        ("systemctl", "--user", "stop", "soak-load.service", "soak-probe.timer", *ABORT_TIMERS),
        ("gc", "stop", str(tmp_path)),
    ]
    assert rig.state().aborted and rig.state().stopped
    assert rig.aborted().splitlines()[1:] == [
        "  AP1: store integrity error: error: checksum mismatch in chunk",
        f"capture: {tmp_path / 'captures' / 'bundle.tar.gz'}",
        "gc stop exit 0: ",
        "after stop: nothing of the city remains",
    ]
    assert [name for name in RECORDS if (tmp_path / name).exists()] == [name for name in RECORDS if name != full]


def test_an_abort_that_cannot_save_itself_still_stops_the_city_and_the_next_run_stops_it_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A full disk refuses check-state.json, so the abort is in ABORTED only,
    # and its gc stop fails: the stop was still tried, and the next run, which
    # finds ABORTED, runs it again before it collects anything.
    rig = AbortRig(tmp_path, monkeypatch, stop_codes=[1, 0])
    save = State.save
    refusals = [OSError(errno.ENOSPC, "No space left on device")]

    def full_once(self: State, path: Path) -> None:
        if refusals:
            raise refusals.pop()
        save(self, path)

    monkeypatch.setattr(State, "save", full_once)
    with pytest.raises(OSError, match="No space left on device"):
        rig.check(health=INTEGRITY_HIT)
    assert rig.stops() == 1 and not (tmp_path / "check-state.json").exists()
    rig.collect_error = PermissionError(errno.EACCES, "Permission denied")
    with pytest.raises(PermissionError):
        rig.check(now=NOW + 300)
    assert rig.stops() == 2 and rig.state().aborted and rig.state().stopped
    rig.collect_error = None
    rig.check(now=NOW + 600, health=INTEGRITY_HIT)
    assert rig.stops() == 2 and [argv[0] for argv in rig.calls].count("systemctl") == 1
    assert rig.aborted().splitlines()[2:] == [
        f"capture: {tmp_path / 'captures' / 'bundle.tar.gz'}",
        "gc stop exit 1: city busy (1)",
        "after stop: nothing of the city remains",
        "gc stop exit 0: ",
        "after stop: nothing of the city remains",
    ]


def test_ap5_inputs_unreadable_never_make_ap9() -> None:
    state = primed()
    for i in range(4):
        out = evaluate(healthy(now=NOW + 300 * i, ops=None), state, "abort")
        assert "AP5" in out.unknown and not out.hits and out.status == WARN
    assert "AP5" not in state.unknown
    stale = primed()
    stale.unknown["AP5"] = 7
    assert ids(evaluate(healthy(ops=None), stale, "abort")) == [] and "AP5" not in stale.unknown


def test_ap6_state_size() -> None:
    assert ids(evaluate(healthy(sizes={"R": 5 << 30, "hc_state": 1}), primed(), "abort")) == ["AP6"]
    assert ids(evaluate(healthy(sizes={"R": 1, "hc_state": 3 << 30}), primed(), "abort")) == ["AP6"]


@pytest.mark.parametrize(
    "sizes, hits, lacking",
    [
        ({"R": None, "hc_state": None}, [], "hc state directory and R"),
        ({"R": 5 << 30, "hc_state": None}, ["AP6"], "hc state directory"),
        ({"R": None, "hc_state": 3 << 30}, ["AP6"], "R"),
        ({"hc_state": 1}, [], "R"),
    ],
    ids=["both-lacking", "hc-state-lacking-r-over", "r-lacking-hc-state-over", "r-not-sampled"],
)
def test_ap6_is_unknown_while_the_size_sample_lacks_a_size_and_still_hits_on_the_other(
    sizes: Dict[str, Optional[int]], hits: List[str], lacking: str
) -> None:
    state = primed()
    for i in range(3):
        out = evaluate(healthy(now=NOW + 300 * i, sizes=sizes), state, "abort")
        assert out.unknown["AP6"] == f"size sample lacks {lacking}"
        assert ids(out) == hits + (["AP9"] if i == 2 else [])
    assert f"AP6 (size sample lacks {lacking})" in out.hits[-1].reason


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


def signaled_ops(ended_by: Dict[str, Dict[str, int]]) -> OpStats:
    return OpStats(
        seconds=900.0,
        sessions=12.0,
        ops=900,
        ctl_ops=800,
        ctl_cpu_us=0,
        signaled=sum(sum(per_op.values()) for per_op in ended_by.values()),
        ended_by=ended_by,
    )


def test_gcs_designed_ends_raise_no_op_signal_warning() -> None:
    designed = signaled_ops({ENDED_CLOSED: {"watch-startup": 14}, ENDED_CANCELED: {"set-meta": 1}})
    out = evaluate(healthy(ops=designed), primed(), "abort")
    assert out.status == OK and "W-op-signal" not in warning_ids(out)


@pytest.mark.parametrize(
    "cls, op, word",
    [(ENDED_KILLED, "is-running", "killed"), (ENDED_OTHER, "peek", "other"), (ENDED_OVERRUN, "observe", "overrun")],
)
def test_an_op_signal_warning_names_the_unexpected_ends(cls: str, op: str, word: str) -> None:
    ops = signaled_ops({ENDED_CLOSED: {"watch-startup": 14}, ENDED_CANCELED: {"set-meta": 1}, cls: {op: 2}})
    out = evaluate(healthy(ops=ops), primed(), "abort")
    found = [w for w in out.warnings if w.id == "W-op-signal"]
    assert ids(out) == [] and len(found) == 1
    assert found[0].reason == f"2 op(s) ended by a signal gc does not send by design in 15 minutes: {word} {op} x2"


def _root_closed(wid: str, ts: str, kind: str = "workflow") -> Dict[str, Any]:
    return {"type": "bead.closed", "ts": ts, "subject": wid, "payload": {"id": wid, "status": "closed", "metadata": {"gc.kind": kind}}}


def test_workflow_closures_take_the_close_event_time_of_workflow_roots_only() -> None:
    events = [
        _root_closed("w1", "1970-01-02T03:46:40.5Z"),
        _root_closed("s1", "1970-01-02T03:46:41Z", kind=""),
        {"type": "bead.updated", "ts": "1970-01-02T03:46:42Z", "subject": "w2", "payload": {"metadata": {"gc.kind": "workflow"}}},
        _root_closed("w3", "not a time"),
        _root_closed("w1", "1970-01-02T03:50:00Z"),
    ]
    assert workflow_closures(events) == {"w1": 100_000.5}


def _collector(tmp_path: Path) -> Collector:
    return Collector(City(name="hc-soak", path=tmp_path, data=tmp_path, mode="abort"), None)  # type: ignore[arg-type]


def _append(path: Path, *recs: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for rec in recs:
            handle.write(json.dumps(rec) + "\n")


def test_track_workflows_settles_every_pending_root_from_one_read_with_the_close_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import soakcheck

    def no_gc(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the tracker reads no bead per id")

    monkeypatch.setattr(soakcheck, "run", no_gc)
    collector, state = _collector(tmp_path), State()
    slings = [{"action": "sling-burst", "t": NOW - 3000 + i, "workflow_id": f"w{i}"} for i in range(40)]
    _append(tmp_path / "load.jsonl", *slings)
    state.workflow_closes = {f"w{i}": NOW - 2000 + i for i in range(30)}
    collector.track_workflows(state, NOW)
    closed = {k: v["closed_t"] for k, v in state.workflows.items() if v.get("closed_t") is not None}
    assert len(state.workflows) == 40 and len(closed) == 30
    assert closed["w0"] == NOW - 2000 and closed["w29"] == NOW - 1971
    assert all(t < NOW for t in closed.values()) and state.workflow_closes == {}


def test_track_workflows_keeps_a_close_read_before_its_sling_and_never_uses_the_check_time(tmp_path: Path) -> None:
    collector, state = _collector(tmp_path), State()
    state.workflow_closes = {"early": NOW - 100, "stale": NOW - WORKFLOW_KEEP_S - 1}
    collector.track_workflows(state, NOW)
    assert state.workflows == {} and state.workflow_closes == {"early": NOW - 100}
    _append(tmp_path / "load.jsonl", {"action": "sling-steady", "t": NOW - 160, "workflow_id": "early"}, {"action": "sling-steady", "t": NOW - 150, "workflow_id": "open"})
    collector.track_workflows(state, NOW + 300)
    assert state.workflows["early"]["closed_t"] == NOW - 100
    assert state.workflows["open"].get("closed_t") is None and state.workflow_closes == {}


def test_track_workflows_keeps_a_whole_soak_of_roots(tmp_path: Path) -> None:
    collector, state = _collector(tmp_path), State()
    _append(tmp_path / "load.jsonl", {"action": "sling-burst", "t": NOW, "workflow_id": "first"})
    collector.track_workflows(state, NOW)
    collector.track_workflows(state, NOW + 86400.0 + 1800.0)
    assert "first" in state.workflows
    collector.track_workflows(state, NOW + WORKFLOW_KEEP_S + 1)
    assert "first" not in state.workflows


# --- AP4 through the real collector: blind without the agent logs ---------------------------------

AGENT_BEACON = "[hc-soak] soak-steady-1 • 2026-11-19T10:00:00"


def _offline_collector(tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch) -> Collector:
    """The real collector over a synthetic ``/proc``; gc, systemd and hc answer offline."""
    import soakcheck

    def gc_ok(argv: Sequence[str], **kwargs: Any) -> CmdResult:
        return CmdResult(tuple(argv), 0, '{"ok": true}', "", 0.0)

    def no_core(*args: Any, **kwargs: Any) -> CoreTuple:
        raise HcError("no core in a unit test")

    monkeypatch.setattr(soakcheck, "run", gc_ok)
    monkeypatch.setattr(soakcheck, "supervisor_state", lambda: {"pid": 0, "nrestarts": 0, "active": "inactive"})
    monkeypatch.setattr(soakcheck, "core_tuple", no_core)
    city = City(name="hc-soak", path=tmp_path / "city", data=tmp_path / "data", mode="abort")
    return Collector(city, SoakPaths(home=tmp_path / "home"), ProcFS(str(proc_tree.root)))


def _agent(proc_tree: ProcTree, collector: Collector, pid: int, session: str, age_s: float = 3000.0, city: Optional[str] = None) -> str:
    """A live scripted agent of the city (or of ``city``), ``age_s`` old: its ``inc``."""
    start = int((collector.procfs.uptime_s() - age_s) * collector.procfs.hz)
    proc_tree.add(pid, "soak-agent", start=start, env={"GC_CITY_PATH": city or str(collector.city.path), "GC_SESSION_ID": session})
    return f"b00tb00t:{pid}:{start}"


def _logged(collector: Collector, session: str, inc: str) -> None:
    """The session's agent log gains the ``boot`` of ``inc`` and its one first turn."""
    t = time.time() - 600.0
    _append(collector.city.agents / f"{session}.jsonl", rec("boot", t, inc, session_id=session), rec("in", t + 5.0, inc, text=AGENT_BEACON, beacon=True))


def _runs(collector: Collector, state: State, n: int) -> List[Outcome]:
    return [evaluate(collector.collect(state), state, "abort") for _ in range(n)]


def _ap9(outcome: Outcome) -> str:
    return "; ".join(f.reason for f in outcome.hits if f.id == "AP9")


def test_collect_makes_ap4_blind_without_the_agent_log_directory(tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _offline_collector(tmp_path, proc_tree, monkeypatch)
    _agent(proc_tree, collector, 4001, "s1")
    assert not collector.city.agents.exists()
    first, second, third = _runs(collector, State(), 3)
    for out in (first, second, third):
        assert out.unknown.get("AP4") == "no agent-log directory" and "AP4" not in ids(out)
    assert "AP4" not in _ap9(second) and "AP4 (no agent-log directory)" in _ap9(third)


def test_collect_makes_ap4_blind_while_a_live_scripted_agent_has_no_log(tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _offline_collector(tmp_path, proc_tree, monkeypatch)
    _logged(collector, "s1", _agent(proc_tree, collector, 4001, "s1"))
    s2 = _agent(proc_tree, collector, 4002, "s2")
    _logged(collector, "s2", "b00tb00t:4002:5")  # an earlier incarnation of the session only
    _agent(proc_tree, collector, 4003, "s3", age_s=AGENT_LOG_GRACE_S - 30.0)  # within its grace
    _agent(proc_tree, collector, 4004, "s4", city="/home/soak/cities/other")  # another city's agent
    proc_tree.add(4005, "python3", env={"GC_CITY_PATH": str(collector.city.path), "GC_SESSION_ID": "s5"})  # not an agent
    state = State()
    first, second, third = _runs(collector, state, 3)
    reason = "1 live scripted agent(s) with no agent log: s2 pid 4002"
    for out in (first, second, third):
        assert out.unknown.get("AP4") == reason and "AP4" not in ids(out)
    assert "AP4" not in _ap9(second) and f"AP4 ({reason})" in _ap9(third)
    _logged(collector, "s2", s2)
    (fourth,) = _runs(collector, state, 1)
    assert "AP4" not in fourth.unknown and "AP4" not in state.unknown
    assert "AP4" not in ids(fourth) and "AP4" not in _ap9(fourth)


def test_collect_hands_final_to_ap4_which_then_judges_every_incarnation(tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _offline_collector(tmp_path, proc_tree, monkeypatch)
    inc = _agent(proc_tree, collector, 4001, "s1")
    t = time.time()
    # Its first turn came twice an hour ago, in a phase that has since ended.
    first, again = (rec("in", t - 3600.0 + d, inc, text=AGENT_BEACON, beacon=True) for d in (5.0, 60.0))
    _append(collector.city.agents / "s1.jsonl", rec("boot", t - 3600.0, inc, session_id="s1"), first, again)
    _append(collector.city.file("phases.jsonl"), {"t": t - 900.0, "phase": "soak-end", "reconciler": "v2"})
    state = State(last_t=t - 300.0)
    assert "AP4" not in ids(evaluate(collector.collect(state), state, "abort"))
    assert "AP4" in ids(evaluate(collector.collect(state, final=True), state, "abort"))


# --- what of a stopped city remains: every session's processes, logged or not ---------------------

STOPPED_CORE = CoreTuple("gc-hc-soak", "/run/user/1000/hc/gc-hc-soak.sock", "/R", "/R/hc-config")
HC_MINE = {"XDG_STATE_HOME": "/R", "HC_SESSION": "gc-hc-soak", "HC_RUNTIME": "1"}


def _stopped_city(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> City:
    """A city whose core tuple is still found (``gc herdr-core status --env``
    answers) and that has one scripted agent's log, ``agents/steady-1.jsonl``."""
    import soakcapture

    monkeypatch.setattr(soakcapture, "core_tuple", lambda city_dir, gc="gc": STOPPED_CORE)
    city = City(name="hc-soak", path=tmp_path / "city", data=tmp_path / "data", mode="abort")
    _append(city.agents / "steady-1.jsonl", rec("boot", time.time() - 600.0, "b00tb00t:4001:5", session_id="steady-1"))
    return city


NO_TUPLE = "`gc herdr-core status --env` exited 1: no city is running here"


def _no_core_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    """``gc herdr-core status --env`` no longer names the city's core tuple."""
    import soakcapture

    def fails(city_dir: str, gc: str = "gc") -> CoreTuple:
        raise HcError(NO_TUPLE)

    monkeypatch.setattr(soakcapture, "core_tuple", fails)


def _session_env(city: City, session: str, **extra: str) -> Dict[str, str]:
    env = {"GC_CITY_PATH": str(city.path), "GC_SESSION_ID": session}
    env.update(extra)
    return env


def test_remains_finds_every_session_s_processes_after_the_core_and_holders_are_gone(
    tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    from soakcapture import remains

    city = _stopped_city(tmp_path, monkeypatch)
    dispatcher = _session_env(city, "dispatcher-1", GC_TEMPLATE="core.control-dispatcher", GC_INSTANCE_TOKEN="t0k3n")
    # The control-dispatcher writes no agent log: its box, and a descendant
    # reparented to init when the holder went.
    proc_tree.add(4010, "sh", argv=["sh", "-c", "gc hook --claim"], env=dispatcher)
    proc_tree.add(4011, "sleep", ppid=1, argv=["sleep", "600"], env=dispatcher)
    # A scripted agent that never wrote its log, and the one that did.
    proc_tree.add(4020, "soak-agent", env=_session_env(city, "steady-3"))
    proc_tree.add(4001, "soak-agent", env=_session_env(city, "steady-1"))
    # Not this city's sessions: another city's (with the same session id), one
    # without a city, and a process of this city outside any session.
    proc_tree.add(4030, "soak-agent", env={"GC_CITY_PATH": "/home/soak/cities/other", "GC_SESSION_ID": "steady-1"})
    proc_tree.add(4031, "soak-agent", env={"GC_SESSION_ID": "steady-2"})
    proc_tree.add(4032, "sleep", env={"GC_CITY_PATH": str(city.path), "GC_SESSION_ID": ""})
    procfs = ProcFS(str(proc_tree.root))
    assert hc_runtime(procfs.snapshot()) == []  # the core and its holders are gone
    assert sorted(remains(city, procfs)) == [
        "session dispatcher-1 pid 4010 sh",
        "session dispatcher-1 pid 4011 sleep",
        "session steady-1 pid 4001 soak-agent",
        "session steady-3 pid 4020 soak-agent",
    ]


def test_remains_names_the_core_and_holders_of_the_city_s_core_tuple_only(
    tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    from soakcapture import remains

    city = _stopped_city(tmp_path, monkeypatch)
    proc_tree.add(3001, "herdr-core", argv=["/hc/herdr-core", "serve"], env=HC_MINE)
    proc_tree.add(3002, "herdr-core", argv=["/hc/herdr-core", "hold"], env=HC_MINE)
    proc_tree.add(3003, "herdr-core", argv=["/hc/herdr-core", "hold"], env=dict(HC_MINE, XDG_STATE_HOME="/other"))
    proc_tree.add(3004, "herdr-core", argv=["/hc/herdr-core", "serve"], env=dict(HC_MINE, HC_SESSION="gc-other"))
    assert sorted(remains(city, ProcFS(str(proc_tree.root)))) == ["hc hold pid 3002", "hc serve pid 3001"]


def test_remains_that_cannot_name_the_core_tuple_never_reads_as_nothing_remaining(
    tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    from soakcapture import remains

    city = _stopped_city(tmp_path, monkeypatch)
    _no_core_tuple(monkeypatch)
    procfs = ProcFS(str(proc_tree.root))
    assert remains(city, procfs) == [f"core tuple unknown: {NO_TUPLE}"]
    # The core and a holder outlived the stop; neither carries a GC_* variable.
    proc_tree.add(3001, "herdr-core", argv=["/hc/herdr-core", "serve"], env=HC_MINE)
    proc_tree.add(3002, "herdr-core", argv=["/hc/herdr-core", "hold"], env=HC_MINE)
    assert remains(city, procfs) == [f"core tuple unknown: {NO_TUPLE}"]
    # The tuple a caller found before the stop: no discovery, and both are seen.
    assert sorted(remains(city, procfs, core=STOPPED_CORE)) == ["hc hold pid 3002", "hc serve pid 3001"]


def test_final_scan_fails_while_a_core_runs_whose_tuple_cannot_be_named(
    tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import soakcheck
    import soakcli

    city = _stopped_city(tmp_path, monkeypatch)
    _no_core_tuple(monkeypatch)
    city.file("canary").write_text("soak-canary-x\n", encoding="utf-8")
    monkeypatch.setattr(soakcheck, "canary_scan", lambda roots, canary: [])
    monkeypatch.setattr(soakcli, "ProcFS", lambda: ProcFS(str(proc_tree.root)))
    proc_tree.add(3001, "herdr-core", argv=["/hc/herdr-core", "serve"], env=HC_MINE)
    assert soakcli.cmd_final_scan(city, SoakPaths(home=tmp_path / "home")) == 1
    assert json.loads(capsys.readouterr().out) == {"canary_hits": [], "remains": [f"core tuple unknown: {NO_TUPLE}"]}


def test_final_scan_fails_while_a_dispatcher_descendant_without_an_agent_log_runs(
    tmp_path: Path, proc_tree: ProcTree, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import soakcheck
    import soakcli

    city = _stopped_city(tmp_path, monkeypatch)
    city.file("canary").write_text("soak-canary-x\n", encoding="utf-8")
    monkeypatch.setattr(soakcheck, "canary_scan", lambda roots, canary: [])
    monkeypatch.setattr(soakcli, "ProcFS", lambda: ProcFS(str(proc_tree.root)))
    paths = SoakPaths(home=tmp_path / "home")
    assert soakcli.cmd_final_scan(city, paths) == 0
    assert json.loads(capsys.readouterr().out) == {"canary_hits": [], "remains": []}
    proc_tree.add(4011, "sleep", argv=["sleep", "600"], env=_session_env(city, "dispatcher-1", GC_TEMPLATE="core.control-dispatcher"))
    assert soakcli.cmd_final_scan(city, paths) == 1
    assert json.loads(capsys.readouterr().out)["remains"] == ["session dispatcher-1 pid 4011 sleep"]
