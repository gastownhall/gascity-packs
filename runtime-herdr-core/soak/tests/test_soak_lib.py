from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from .soaktestkit import ProcTree

import soaklib
from soaklib import (
    LINE_LIMIT,
    NotOwned,
    ProcFS,
    Refused,
    append_jsonl,
    city_from_env,
    descendants,
    encode_line,
    guard,
    is_infra,
    last_json_object,
    parse_cgroup,
    parse_environ,
    parse_env_file,
    parse_stat,
    read_jsonl,
    run,
    signal_owned,
    unit_of,
)


def test_guard_needs_the_marker_to_hold_this_hosts_machine_id(tmp_path: Path) -> None:
    machine = tmp_path / "machine-id"
    machine.write_text("abc123\n", encoding="utf-8")
    marker = tmp_path / "gc-soak-throwaway"
    with pytest.raises(Refused, match="missing"):
        guard(str(marker), str(machine))
    marker.write_text("another-host\n", encoding="utf-8")
    with pytest.raises(Refused, match="does not hold"):
        guard(str(marker), str(machine))
    marker.write_text("abc123\n", encoding="utf-8")
    guard(str(marker), str(machine))


def test_guard_refuses_an_empty_machine_id(tmp_path: Path) -> None:
    machine = tmp_path / "machine-id"
    machine.write_text("\n", encoding="utf-8")
    marker = tmp_path / "m"
    marker.write_text("\n", encoding="utf-8")
    with pytest.raises(Refused):
        guard(str(marker), str(machine))


def test_this_host_is_not_the_soak_vm() -> None:
    """The unit tests run on operator hosts and CI runners; the real guard refuses there."""
    if Path(soaklib.GUARD_FILE).exists():
        pytest.skip("running on a host provisioned as the soak VM")
    with pytest.raises(Refused):
        guard()


def test_encode_line_keeps_every_line_under_the_limit() -> None:
    line = encode_line({"ev": "in", "t": 1.0, "text": "x" * 10_000, "other": "y" * 3000})
    assert len(line) < LINE_LIMIT
    doc = json.loads(line)
    assert doc["truncated"] is True and doc["ev"] == "in"
    assert len(doc["text"]) == len(doc["other"]) > 1000  # one common cut, as long as fits
    small = encode_line({"ev": "hb", "t": 2.0})
    assert json.loads(small) == {"ev": "hb", "t": 2.0}


def test_encode_line_keeps_a_check_run_s_status_and_finding_ids() -> None:
    """A check run whose finding carries a long reason is cut inside the
    finding: the report and the digest still read its status and ids."""
    reason = "foreign hc runtime: " + ", ".join(f"hold pid {1000 + i} (/home/soak/.local/state/x{i})" for i in range(150))
    rec = {
        "t": 500.0,
        "phase": "soak-v2",
        "mode": "abort",
        "status": "HIT",
        "hits": [{"id": "AP7", "reason": reason}],
        "warnings": [{"id": "AP9", "reason": "record-only: a slow probe"}],
        "unknown": {"AP5": "no ops"},
        "perf": None,
        "final": False,
    }
    line = encode_line(rec)
    assert len(line) < LINE_LIMIT < len(json.dumps(rec))
    doc = json.loads(line)
    assert doc["truncated"] is True
    assert {k: v for k, v in doc.items() if k not in ("hits", "truncated")} == {k: v for k, v in rec.items() if k != "hits"}
    [hit] = doc["hits"]
    assert hit["id"] == "AP7" and reason.startswith(hit["reason"]) and len(hit["reason"]) > 2000


def test_encode_line_halves_the_bulkiest_nested_list_and_keeps_what_wraps_it() -> None:
    sessions = [{"id": f"s{i}", "n": i} for i in range(2000)]
    line = encode_line({"ev": "cmd", "t": 1.0, "json": {"count": 2000, "sessions": sessions}})
    assert len(line) < LINE_LIMIT
    doc = json.loads(line)
    assert doc["truncated"] is True and doc["ev"] == "cmd" and doc["json"]["count"] == 2000
    kept = doc["json"]["sessions"]
    assert 0 < len(kept) < len(sessions) and kept == sessions[: len(kept)]


def test_encode_line_keeps_the_essential_scalars_when_nothing_else_fits() -> None:
    rec = {**{f"k{i:04d}": i for i in range(1000)}, "ev": "x", "t": 3.0, "status": "OK", "kind": "note", "inc": {"nested": [1, 2]}}
    line = encode_line(rec)
    assert len(line) < LINE_LIMIT
    assert json.loads(line) == {"ev": "x", "t": 3.0, "status": "OK", "kind": "note", "truncated": True}


def test_jsonl_round_trip_skips_a_torn_line(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    append_jsonl(path, {"a": 1})
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"torn": ')
        handle.write("\nnot json\n")
    append_jsonl(path, {"b": 2})
    assert read_jsonl(path) == [{"a": 1}, {"b": 2}]
    assert read_jsonl(tmp_path / "missing.jsonl") == []
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_last_json_object() -> None:
    assert last_json_object('noise\n{"action": "drain"}\n{"action": "work"}\n') == {"action": "work"}
    assert last_json_object('{\n  "a": 1\n}\n') == {"a": 1}
    assert last_json_object("nothing") is None


def test_parse_stat_reads_a_command_name_with_spaces_and_parentheses() -> None:
    fields = ["S", "42"] + ["0"] * 9 + ["7", "8", "9", "10"] + ["0"] * 4 + ["12345", "0", "64"]
    st = parse_stat(f"99 (a (weird) name) {' '.join(fields)}")
    assert (st.pid, st.comm, st.state, st.ppid) == (99, "a (weird) name", "S", 42)
    assert (st.utime, st.stime, st.cutime, st.cstime, st.start, st.rss_pages) == (7, 8, 9, 10, 12345, 64)


def test_parse_environ_cgroup_unit() -> None:
    assert parse_environ(b"A=1\0B=x=y\0junk\0") == {"A": "1", "B": "x=y"}
    path = "/user.slice/user-1000.slice/user@1000.service/gascity-agents.slice/run-r1.scope"
    assert parse_cgroup(f"0::{path}\n") == path
    assert unit_of(path) == "run-r1.scope"
    assert unit_of("/user.slice/user-1000.slice/user@1000.service/hc-hold-x.service") == "hc-hold-x.service"
    assert unit_of("/") is None


def test_procfs_reads_a_synthetic_tree(proc_tree: ProcTree) -> None:
    proc_tree.add(10, "soak-agent", ppid=5, start=400, argv=["/usr/bin/python3", "-I", "/x/soak-agent"], env={"GC_SESSION_ID": "s1"})
    proc_tree.add(11, "sleep", ppid=10, start=410)
    proc_tree.add(12, "zomb", state="Z")
    procfs = ProcFS(str(proc_tree.root))
    snap = procfs.snapshot()
    assert sorted(snap) == [10, 11]
    info = snap[10]
    assert info.env == {"GC_SESSION_ID": "s1"} and info.argv1 == "-I" and info.start == 400
    assert info.uid == os.getuid() and info.cpu_ticks == 8
    assert procfs.alive(10, 400) and not procfs.alive(10, 401) and not procfs.alive(12, 100)
    assert procfs.boot_id().startswith("b00tb00t")
    assert descendants(snap, [10]) == [11]


def test_is_infra() -> None:
    def info(argv: list) -> soaklib.ProcInfo:  # type: ignore[type-arg]
        return soaklib.ProcInfo(1, 0, 0, "x", 0, "S", tuple(argv), {}, "", 0, 0, 0.0)

    assert is_infra(info(["/usr/local/bin/bd", "db-proxy-child"]))
    assert is_infra(info(["gc", "__gc-managed-dolt-scope-watchdog"]))
    assert is_infra(info(["gc", "nudge", "poll"]))
    assert not is_infra(info(["gc", "nudge", "send"]))


def test_signal_owned_refuses_without_ownership_or_with_a_stale_start() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        procfs = ProcFS()
        start = procfs.stat(child.pid).start  # type: ignore[union-attr]
        with pytest.raises(NotOwned, match="not ours"):
            signal_owned(child.pid, signal.SIGKILL, start, lambda pid: "not ours", procfs)
        with pytest.raises(NotOwned, match="no longer"):
            signal_owned(child.pid, signal.SIGKILL, start + 1, lambda pid: None, procfs)
        assert child.poll() is None
        signal_owned(child.pid, signal.SIGKILL, start, lambda pid: None, procfs)
        assert child.wait(timeout=10) == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_run_reports_timeouts_and_missing_binaries() -> None:
    slow = run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3)
    assert slow.code == 124 and slow.timed_out
    missing = run(["/nonexistent/binary"])
    assert missing.code == 127
    ok = run([sys.executable, "-c", "print('{\"x\": 1}')"])
    assert ok.ok and ok.json() == {"x": 1}
    assert ok.duration_s < 30
    assert time.time() > 0


def test_city_from_env_prefers_the_environment(tmp_path: Path) -> None:
    paths = soaklib.SoakPaths(home=tmp_path)
    with pytest.raises(LookupError):
        city_from_env({}, paths)
    data = tmp_path / "soak-data" / "c1"
    data.mkdir(parents=True)
    (data / "soak.env").write_text(f"SOAK_CITY={tmp_path}/cities/c1\nSOAK_DATA={data}\nSOAK_MODE=abort\n", encoding="utf-8")
    os.symlink(str(data), str(tmp_path / "soak-data" / "current"))
    city = city_from_env({}, paths)
    assert (city.name, city.data, city.mode) == ("c1", data, "abort")
    other = city_from_env({"SOAK_CITY": "/x/cities/c2", "SOAK_DATA": "/x/d2"}, paths)
    assert other.name == "c2" and other.mode == "abort"
    assert parse_env_file("# c\nA=1\n\nB = 2\n") == {"A": "1", "B": "2"}
