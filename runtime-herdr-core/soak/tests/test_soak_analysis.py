from __future__ import annotations

from typing import Dict, List

from .soaktestkit import ProcTree, rec

from soakanalysis import (
    ENDED_CANCELED,
    ENDED_CLOSED,
    ENDED_KILLED,
    ENDED_OTHER,
    ENDED_OVERRUN,
    FT_DUPLICATED,
    FT_EXACT,
    FT_FAULTED,
    FT_LOST,
    FT_PENDING,
    FT_SHORT_LIVED,
    NUDGE_DUPLICATED,
    NUDGE_LOST,
    NUDGE_PENDING,
    NUDGE_RECEIVED,
    NUDGE_REFUSED,
    city_cores,
    find_orphans,
    first_turn,
    foreign_hc,
    hc_runtime,
    incarnations,
    input_bursts,
    is_beacon,
    mean_boxes,
    message_ops,
    mono_offset,
    nudge_verdicts,
    op_stats,
    parse_optrace,
    parse_ts,
    percentile,
    pid_at,
    store_procs,
    supervisor_timeline,
)
from soaklib import CmdResult, ProcFS, Rec, cmd_record

BEACON = "[hc-soak] soak-steady-1 • 2026-11-17T10:00:00"
INC = "b00tb00t:100:5000"


def boot(t: float = 0.0, inc: str = INC, sid: str = "s1") -> Rec:
    return rec("boot", t, inc, session_id=sid, session_name="soak-steady-1", template="soak-steady")


def line(t: float, text: str, inc: str = INC) -> Rec:
    return rec("in", t, inc, text=text, beacon=is_beacon(text))


def one(records: List[Rec], alive: bool = True, now: float = 1000.0, faults: List[Rec] = []) -> str:
    incs = incarnations(records, lambda inc: alive)
    assert len(incs) == 1
    return first_turn(incs[0], faults, now).status


def test_beacon_matches_gcs_first_line_only() -> None:
    assert is_beacon(BEACON)
    assert not is_beacon("SOAK-FIRST-TURN soak-steady")
    assert not is_beacon("[x] y • 2026-11-17 10:00:00")


def test_bursts_split_at_one_second() -> None:
    ins = [line(10.0, "a"), line(10.4, "b"), line(11.3, "c"), line(12.5, "d")]
    assert [len(b) for b in input_bursts(ins)] == [3, 1]


def test_first_turn_exact_and_its_latency() -> None:
    records = [boot(0.0), line(5.0, BEACON), line(5.2, ""), line(5.4, "SOAK-FIRST-TURN soak-steady")]
    incs = incarnations(records, lambda inc: True)
    turn = first_turn(incs[0], [], 1000.0)
    assert turn.status == FT_EXACT and turn.latency_s == 5.0 and turn.marker and turn.beacons == 1


def test_first_turn_typed_twice_is_duplicated() -> None:
    records = [boot(), line(5.0, BEACON), line(5.3, "SOAK-FIRST-TURN x"), line(40.0, BEACON), line(40.2, "SOAK-FIRST-TURN x")]
    assert one(records) == FT_DUPLICATED


def test_a_first_turn_re_sent_inside_the_burst_gap_is_duplicated() -> None:
    # The pack re-sends a first turn the box refused as unavailable after
    # 0.5 s, so both copies land in one input burst: two beacon lines.
    turn_lines = [BEACON, "", "SOAK-FIRST-TURN soak-steady"]
    first = [line(5.0 + 0.1 * i, text) for i, text in enumerate(turn_lines)]
    again = [line(5.5 + 0.1 * i, text) for i, text in enumerate(turn_lines)]
    incs = incarnations([boot()] + first + again, lambda inc: True)
    assert len(input_bursts(incs[0].inputs)) == 1
    turn = first_turn(incs[0], [], 1000.0)
    assert turn.status == FT_DUPLICATED and turn.beacons == 2 and turn.latency_s == 5.0
    # The control: one copy, its prompt running on in the same burst, is exact.
    assert one([boot()] + first + [line(5.5, "the rest of the prompt"), line(5.6, "")]) == FT_EXACT


def test_first_turn_lost_pending_short_lived_and_faulted() -> None:
    nudge_only = [boot(), line(30.0, "SOAK-NUDGE " + "a" * 32)]
    assert one(nudge_only, alive=True, now=200.0) == FT_LOST
    assert one(nudge_only, alive=True, now=100.0) == FT_PENDING
    ended_early = [boot(), rec("hb", 60.0, INC)]
    assert one(ended_early, alive=False) == FT_SHORT_LIVED
    fault = {"t": 59.0, "kind": "drill-holder-kill", "all": True}
    assert one(ended_early, alive=False, faults=[fault]) == FT_FAULTED
    ended_late = [boot(), rec("hb", 200.0, INC)]
    assert one(ended_late, alive=False, faults=[fault]) == FT_LOST


def test_a_bad_first_turn_carries_the_time_its_verdict_came() -> None:
    def turn(records: List[Rec], alive: bool = True, now: float = 1000.0) -> object:
        incs = incarnations(records, lambda inc: alive)
        t = first_turn(incs[0], [], now)
        return t.status, t.verdict_t

    assert turn([boot(), line(5.0, BEACON), line(40.0, BEACON), line(90.0, BEACON)]) == (FT_DUPLICATED, 40.0)
    assert turn([boot(), line(40.0, BEACON), line(5.0, BEACON)]) == (FT_DUPLICATED, 40.0)  # by time, not log order
    assert turn([boot(10.0)]) == (FT_LOST, 190.0)
    assert turn([boot(10.0), rec("hb", 300.0, INC)], alive=False) == (FT_LOST, 190.0)
    assert turn([boot(), line(5.0, BEACON)]) == (FT_EXACT, None)
    assert turn([boot()], now=100.0) == (FT_PENDING, None)
    assert turn([boot(), rec("hb", 60.0, INC)], alive=False) == (FT_SHORT_LIVED, None)


def test_an_operator_note_that_covers_everything_explains_an_early_end() -> None:
    ended_early = [boot(), rec("hb", 60.0, INC)]
    note = {"t": 59.0, "kind": "note", "what": "city-stop", "covers": ["all"]}
    assert one(ended_early, alive=False, faults=[note]) == FT_FAULTED
    narrow = {"t": 59.0, "kind": "note", "what": "supervisor-restart", "covers": ["supervisor", "controller", "store"]}
    assert one(ended_early, alive=False, faults=[narrow]) == FT_SHORT_LIVED


def test_incarnations_group_by_inc_and_collect_background_children() -> None:
    other = "b00tb00t:200:6000"
    records = [
        boot(0.0),
        rec("bg", 0.1, INC, children=[{"pid": 101, "start": 5001}, {"pid": 102, "start": 5002}]),
        boot(300.0, other, "s1"),
        rec("hb", 360.0, other),
        rec("in", 1.0, "unknown:1:1", text="orphan line"),
    ]
    incs = incarnations(records, lambda inc: inc == other)
    assert [i.inc for i in incs] == [INC, other]
    assert incs[0].bg == [(101, 5001), (102, 5002)] and not incs[0].alive
    assert incs[1].alive and incs[1].last_t == 360.0


def nudge_rec(t: float, nonce: str, exit_code: int = 0, outcome: str = "submitted") -> Rec:
    return {"t": t, "action": "nudge", "session_id": "s1", "nonce": nonce, "mode": "wait-idle", "exit": exit_code, "json": {"ok": exit_code == 0, "outcome": outcome, "queued": outcome == "queued"}}


def test_nudge_verdicts() -> None:
    a, b, c, d, e = ("a" * 32, "b" * 32, "c" * 32, "d" * 32, "e" * 32)
    load = [nudge_rec(100.0, a), nudge_rec(100.0, b, outcome="queued"), nudge_rec(100.0, c), nudge_rec(1900.0, d), nudge_rec(100.0, e, exit_code=1)]
    inputs: Dict[str, List[Rec]] = {"s1": [{"t": 102.0, "nonce": a}, {"t": 200.0, "nonce": b}, {"t": 201.0, "nonce": b}]}
    verdicts = {v.nonce: v for v in nudge_verdicts(load, inputs, now=2000.0)}
    assert verdicts[a].status == NUDGE_RECEIVED and verdicts[a].latency_s == 2.0 and verdicts[a].cli == "delivered"
    assert verdicts[b].status == NUDGE_DUPLICATED and verdicts[b].cli == "queued"
    assert verdicts[c].status == NUDGE_LOST
    assert verdicts[d].status == NUDGE_PENDING
    assert verdicts[e].status == NUDGE_REFUSED


def test_a_nudge_is_judged_from_when_it_was_sent_not_when_its_command_returned() -> None:
    """``cmd_record`` stamps a nudge when ``gc session nudge`` returns, here
    10 s after it was sent; the session read it 1 s after it was sent."""
    nonce = "f" * 32
    res = CmdResult(("gc", "session", "nudge"), 0, '{"ok": true, "outcome": "submitted"}', "", 10.0)
    record = cmd_record("nudge", res, session_id="s1", nonce=nonce, mode="wait-idle")
    returned = float(record["t"])
    [verdict] = nudge_verdicts([record], {"s1": [{"t": returned - 9.0, "nonce": nonce}]}, now=returned + 1000.0)
    assert verdict.status == NUDGE_RECEIVED and abs(verdict.t - (returned - 10.0)) < 1e-6
    assert verdict.latency_s is not None and abs(verdict.latency_s - 1.0) < 1e-6


def op_event(op_id: str, ts: str, status: str, **extra: object) -> Rec:
    op: Dict[str, object] = {"id": op_id, "kind": "message", "status": status}
    op.update(extra)
    return {"type": "op.changed", "ts": ts, "payload": {"op": op}}


def test_message_ops_take_the_last_post_image_and_count_unconfirmed() -> None:
    ok = {"arm": "succeeded", "result": {"delivery": {"ack": "delivered"}}}
    events = [
        op_event("o1", "2026-11-17T10:00:00Z", "executing"),
        op_event("o1", "2026-11-17T10:00:01.5Z", "closed", attempt=1, outcome=ok),
        op_event("o2", "2026-11-17T10:00:02Z", "closed", attempt=2, outcome=ok),
        op_event("o3", "2026-11-17T10:00:03Z", "closed", maybe_delivered=1, outcome=ok),
        op_event("o4", "2026-11-17T10:00:04Z", "closed", outcome={"arm": "failed", "reason": "delivery_unconfirmed"}),
        op_event("o5", "2026-11-17T10:00:05Z", "closed", outcome={"arm": "succeeded", "result": {"delivery": {"ack": "unconfirmed_echo"}}}),
        op_event("o6", "2026-11-17T10:00:06Z", "accepted"),
        {"type": "op.changed", "ts": "2026-11-17T10:00:07Z", "payload": {"op": {"id": "k", "kind": "kill", "status": "closed"}}},
        {"type": "session.woke", "ts": "2026-11-17T10:00:08Z"},
    ]
    stats = message_ops(events)
    assert stats.closed == 5 and stats.open == 1
    assert sorted(stats.unconfirmed_ids) == ["o2", "o3", "o4", "o5"]
    assert stats.by_arm == {"succeeded": 4, "failed": 1}
    assert stats.by_ack == {"delivered": 3, "unconfirmed_echo": 1}
    assert stats.ratio == 0.8
    since = parse_ts("2026-11-17T10:00:03Z")
    assert message_ops(events, since=since).closed == 3


def test_parse_ts() -> None:
    assert parse_ts("1970-01-01T00:00:10Z") == 10.0
    assert parse_ts("1970-01-01T01:00:10+01:00") == 10.0
    assert parse_ts("1970-01-01T00:00:10.250000000Z") == 10.25
    assert parse_ts("garbage") is None


def test_parse_optrace_pairs_ops_and_recovers_a_split_argv() -> None:
    lines = [
        "B 1000",
        "E 2000000000 501 77 gc /p/gc-runtime-herdr-core observe --x",
        "E 2100000000 502 77 gc ",
        "X 2050000000 501 0 50 12000",
        "/p/gc-runtime-herdr-core inventory",
        "X 2300000000 502 9 200 30000",
        "E 2400000000 503 900 python3 /p/gc-runtime-herdr-core start",
        "X 2500000000 503 256 100 40000",
        "X 9 999 0 1 1",
    ]
    runs, starts = parse_optrace(lines)
    assert starts == [1000]
    assert [r.op for r in runs] == ["observe", "inventory", "start"]
    assert runs[0].wall_ms == 50 and runs[0].status == 0 and runs[0].signal is None
    assert runs[1].signal == 9
    assert runs[2].status == 1 and runs[2].signal is None


def test_op_stats_count_controller_spawned_ops_against_the_mainpid_of_the_time() -> None:
    runs, _ = parse_optrace(
        [
            "E 10000000000 1 77 gc /e observe",
            "X 10050000000 1 0 50 15000",
            "E 70000000000 2 88 gc /e observe",
            "X 70050000000 2 0 50 15000",
            "E 71000000000 3 77 gc /e inventory",
            "X 71100000000 3 0 100 20000",
            "E 72000000000 4 1234 bash /e start",
        ]
    )
    samples = [
        {"t": 1000.0, "mono_ns": 0, "supervisor": {"pid": 77}, "boxes": [1, 2]},
        {"t": 1060.0, "mono_ns": 60_000_000_000, "supervisor": {"pid": 88}, "boxes": [1, 2, 3, 4]},
    ]
    offset = mono_offset(samples)
    assert offset == 1000.0
    timeline = supervisor_timeline(samples)
    assert pid_at(timeline, 1005.0) == 77 and pid_at(timeline, 1065.0) == 88 and pid_at(timeline, 0.0) == 77
    stats = op_stats(runs, offset, 1000.0, 1120.0, timeline, mean_boxes(samples, 1000.0, 1120.0))
    assert stats.ops == 4 and stats.ctl_ops == 2
    assert stats.by_op == {"observe": 2, "inventory": 1, "start": 1}
    assert stats.ctl_cpu_us == 30000
    assert abs(stats.rate_ctl - 2 / 120.0) < 1e-9
    assert stats.sessions == 3.0
    assert abs(stats.rate_ctl_per_session - 2 / 120.0 / 3.0) < 1e-9
    assert stats.latency_ms["observe"] == [50, 50]


def test_percentile_is_nearest_rank() -> None:
    assert percentile([], 50) is None
    assert percentile([5.0], 99) == 5.0
    values = [float(v) for v in range(1, 101)]
    assert percentile(values, 50) == 50.0 and percentile(values, 95) == 95.0 and percentile(values, 99) == 99.0


CITY = "/home/soak/cities/hc-soak"


def test_find_orphans(proc_tree: ProcTree) -> None:
    city = {"GC_CITY_PATH": CITY}
    proc_tree.add(10, "herdr-core", argv=["/hc/herdr-core", "hold"], env={"HC_RUNTIME": "1", "XDG_STATE_HOME": "/s", "HC_SESSION": "c"})
    proc_tree.add(20, "soak-agent", ppid=10, env=dict(city, GC_INSTANCE_TOKEN="live"))
    proc_tree.add(21, "sleep", ppid=1, env=dict(city, GC_INSTANCE_TOKEN="live"), start=10)
    proc_tree.add(30, "sleep", ppid=1, env=dict(city, GC_INSTANCE_TOKEN="dead"), start=10)
    proc_tree.add(31, "python3", ppid=1, env=dict(city, GC_INSTANCE_TOKEN="dead"), start=999_000)
    proc_tree.add(40, "bd", ppid=1, argv=["/usr/local/bin/bd", "db-proxy-child"], env=dict(city, GC_INSTANCE_TOKEN="dead"), start=10)
    proc_tree.add(41, "dolt", ppid=40, argv=["dolt", "sql-server"], env=dict(city, GC_INSTANCE_TOKEN="dead"), start=10)
    proc_tree.add(50, "sleep", ppid=1, env={"GC_CITY_PATH": "/other", "GC_INSTANCE_TOKEN": "dead"}, start=10)
    proc_tree.add(60, "sleep", ppid=1, env=dict(city, GC_INSTANCE_TOKEN="dead"), uid=0, start=10)
    snap = ProcFS(str(proc_tree.root)).snapshot()
    orphans = find_orphans(snap, [10], CITY, 600.0, uid=__import__("os").getuid())
    assert [p.pid for p in orphans] == [30]
    assert [p.pid for p in find_orphans(snap, [10], CITY, 0.0, uid=__import__("os").getuid())] == [30, 31]


def test_hc_runtime_names_the_owner_of_every_core_and_holder(proc_tree: ProcTree) -> None:
    mine = {"XDG_STATE_HOME": "/R", "HC_SESSION": "gc-city"}
    proc_tree.add(1, "herdr-core", argv=["/hc/herdr-core", "serve"], env=mine)
    proc_tree.add(2, "herdr-core", argv=["/hc/herdr-core", "hold", "--socket", "x"], env=mine)
    proc_tree.add(3, "python3", argv=["python3", "cli.py", "serve", "0.1.19"], env={"HC_RUNTIME": "1", "XDG_STATE_HOME": "/tmp/hcconf/state", "HC_SESSION": "x"})
    proc_tree.add(4, "herdr-core", argv=["/hc/herdr-core", "ls"], env=mine)
    proc_tree.add(5, "herdr-core", argv=["/hc/herdr-core", "serve"], env=mine)
    hcs = hc_runtime(ProcFS(str(proc_tree.root)).snapshot())
    assert [(h.pid, h.role) for h in hcs] == [(1, "serve"), (2, "hold"), (3, "serve"), (5, "serve")]
    assert [h.pid for h in foreign_hc(hcs, "/R", "gc-city")] == [3]
    assert [h.pid for h in city_cores(hcs, "/R", "gc-city")] == [1, 5]


def test_store_procs(proc_tree: ProcTree) -> None:
    proc_tree.add(40, "bd", argv=["/usr/local/bin/bd", "db-proxy-child", "--x"])
    proc_tree.add(41, "dolt", ppid=40, argv=["dolt", "sql-server", "--config", "c"])
    proc_tree.add(42, "sleep", ppid=40)
    proc_tree.add(43, "dolt", ppid=1, argv=["dolt", "sql-server"])
    snap = ProcFS(str(proc_tree.root)).snapshot()
    assert [p.pid for p in store_procs(snap, __import__("os").getuid())] == [40, 41]


def test_a_watch_startup_killed_at_its_deadline_is_an_overrun() -> None:
    runs, _ = parse_optrace(
        [
            "E 1000000000 11 77 gc /p/gc-runtime-herdr-core watch-startup soak-1",
            "X 1000000000 11 9 119500 122000",
            "E 2000000000 12 77 gc /p/gc-runtime-herdr-core watch-startup soak-1",
            "X 2000000000 12 9 118000 122000",
        ]
    )
    assert [r.ended_by for r in runs] == [ENDED_OVERRUN, ENDED_CLOSED]


def test_an_op_ended_by_a_signal_is_classed_by_who_ended_it() -> None:
    runs, _ = parse_optrace(
        [
            "E 1000000000 11 77 gc /p/gc-runtime-herdr-core watch-startup soak-1",
            "X 1241000000 11 9 241 122000",
            "E 2000000000 12 900 gc /p/gc-runtime-herdr-core set-meta soak-1 GC_DRAIN_ACK_SOURCE",
            "X 2069000000 12 15 69 61000",
            "E 3000000000 13 77 gc /p/gc-runtime-herdr-core is-running soak-1",
            "X 3300000000 13 9 300 50000",
            "E 4000000000 14 77 gc /p/gc-runtime-herdr-core observe",
            "X 7990000000 14 15 3990 90000",
            "E 8000000000 15 77 gc /p/gc-runtime-herdr-core peek soak-1 120",
            "X 8010000000 15 11 10 5000",
            "E 9000000000 16 77 gc /p/gc-runtime-herdr-core observe",
            "X 9050000000 16 0 50 15000",
            "E 10000000000 17 77 gc /p/gc-runtime-herdr-core observe",
            "X 12999000000 17 15 2999 15000",
            "E 13000000000 18 77 gc /p/gc-runtime-herdr-core start soak-2",
            "X 13000000000 18 15 119000 15000",
            "E 14000000000 19 77 gc /p/gc-runtime-herdr-core get-meta soak-2 X",
            "X 14000000000 19 15 29000 15000",
            "E 15000000000 20 77 gc /p/gc-runtime-herdr-core get-meta soak-2 X",
            "X 15000000000 20 15 28999 15000",
        ]
    )
    assert [r.ended_by for r in runs] == [
        ENDED_CLOSED,
        ENDED_CANCELED,
        ENDED_KILLED,
        ENDED_OVERRUN,
        ENDED_OTHER,
        None,
        ENDED_CANCELED,
        ENDED_OVERRUN,
        ENDED_OVERRUN,
        ENDED_CANCELED,
    ]


def test_a_start_op_canceled_before_the_start_deadline_is_canceled_not_overrun() -> None:
    """gc runs provision and launch, as it runs start, under its 120 s start deadline."""
    ops = ("start", "provision", "launch")
    lines: List[str] = []
    for pid, op in enumerate(ops, 11):  # SIGTERM after 45 s, well before 120 s less 1 s
        lines += [f"E 1000000000 {pid} 77 gc /p/gc-runtime-herdr-core {op} soak-1", f"X 1000000000 {pid} 15 45000 15000"]
    runs, _ = parse_optrace(lines)
    assert [(r.op, r.ended_by) for r in runs] == [(op, ENDED_CANCELED) for op in ops]


def test_op_stats_count_signaled_ops_per_class_and_name_them() -> None:
    runs, _ = parse_optrace(
        [
            "E 1000000000 11 77 gc /e watch-startup a",
            "X 1241000000 11 9 241 1",
            "E 2000000000 12 77 gc /e watch-startup b",
            "X 2241000000 12 9 241 1",
            "E 3000000000 13 900 gc /e set-meta a K",
            "X 3069000000 13 15 69 1",
            "E 4000000000 14 77 gc /e is-running a",
            "X 4300000000 14 9 300 1",
            "E 5000000000 15 77 gc /e observe",
            "X 5050000000 15 0 50 1",
        ]
    )
    stats = op_stats(runs, 0.0, 0.0, 100.0, [], 1.0)
    assert stats.signaled == 4
    assert stats.ended_by == {
        ENDED_CLOSED: {"watch-startup": 2},
        ENDED_CANCELED: {"set-meta": 1},
        ENDED_KILLED: {"is-running": 1},
    }
    assert stats.ended_count(ENDED_CLOSED) == 2 and stats.ended_count(ENDED_OVERRUN) == 0
