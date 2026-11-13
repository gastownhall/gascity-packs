"""fake-hc honesty: programs are real child processes in their own
session, so pids and process trees are true; holder loss and core restarts
follow hc v0.1.19's documented record changes."""

from __future__ import annotations

import os
import signal
import socket
import time
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import pytest

from fakehc import FakeHc
from fakehc.rawclient import raw_call


def run(fake: FakeHc, workdir: Path, command: str, **extra: object) -> Dict[str, object]:
    params: Dict[str, object] = {
        "argv": ["/bin/sh", "-c", command],
        "cwd": str(workdir),
        "labels": {"gc.city": "c"},
        "no_parent": True,
        "no_notify": True,
    }
    params.update(extra)
    reply = raw_call(fake.socket_path, "terminal.run", params)
    result = reply["result"]
    assert isinstance(result, dict)
    return result


def get(fake: FakeHc, address: str) -> Dict[str, object]:
    result = raw_call(fake.socket_path, "terminal.get", {"terminal": address})["result"]
    assert isinstance(result, dict)
    return result


def wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def alive(pid: int) -> bool:
    """A pid names a running process (a zombie awaiting its reaper is not running)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    if not os.path.isdir("/proc/self"):
        return True  # no procfs: kill(0) said it exists
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def test_a_program_is_a_real_child_in_its_own_session(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "echo hi; exec cat")
    pid = rec["pid"]
    assert isinstance(pid, int)
    assert os.getsid(pid) == pid and os.getpgid(pid) == pid
    env = fake_hc.terminal_env(str(rec["address"]))
    assert env["HC_TERMINAL_ID"] == rec["address"]
    assert env["HC_SCOPE"]  # what hc's holder-loss sweep keys on
    assert env["HC_TERMINAL_SOCKET"] == fake_hc.socket_path
    wait_for(lambda: "hi" in str(raw_call(fake_hc.socket_path, "terminal.read", {"terminal": rec["address"]})["result"]))


def test_names_are_unique_among_live_terminals(fake_hc: FakeHc, short_tmp: Path) -> None:
    run(fake_hc, short_tmp, "exec cat", name="ga")
    reply = raw_call(fake_hc.socket_path, "terminal.run", {"argv": ["/bin/sh"], "name": "ga"})
    assert reply["error"]["data"]["kind"] == "name_taken"


def test_kill_ends_the_programs_process_group(fake_hc: FakeHc, short_tmp: Path) -> None:
    pidfile = short_tmp / "grandchild.pid"
    rec = run(fake_hc, short_tmp, f"sleep 60 & echo $! > {pidfile}; exec cat")
    wait_for(pidfile.exists)
    wait_for(lambda: pidfile.read_text().strip() != "")
    grandchild = int(pidfile.read_text())
    killed = raw_call(fake_hc.socket_path, "terminal.kill", {"terminal": rec["address"]})["result"]
    assert killed["state"] == "finished" and killed["reason"] == "killed"
    wait_for(lambda: not alive(grandchild))


def test_a_finished_program_keeps_its_record_until_removed(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exit 3")
    address = str(rec["address"])
    wait_for(lambda: get(fake_hc, address)["state"] == "finished")
    done = get(fake_hc, address)
    assert done["reason"] == "exited" and done["exit_code"] == 3
    assert done["pid"] == rec["pid"]  # a finished record keeps its last pid (hc terminals.rs finish)
    assert done["foreground"] is None
    listed = raw_call(fake_hc.socket_path, "terminal.list", {})["result"]
    assert listed["terminals"] == [] and listed["hidden_finished"] == 1
    assert "machines" not in listed  # hc v0.1.19 omits it when empty (#190)
    assert raw_call(fake_hc.socket_path, "terminal.rm", {"terminal": address})["result"] == {"removed": address}


def test_rm_refuses_a_live_terminal(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exec cat")
    reply = raw_call(fake_hc.socket_path, "terminal.rm", {"terminal": rec["address"]})
    assert reply["error"]["data"]["kind"] == "live"


def test_holder_loss_finishes_an_unkept_program(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exec cat")
    pid = rec["pid"]
    assert isinstance(pid, int)
    fake_hc.lose_holder(str(rec["address"]))
    done = get(fake_hc, str(rec["address"]))
    assert done["state"] == "finished" and done["reason"] == "holder_lost"
    assert done["pid"] == pid and done["exit_code"] is None and done["signal"] is None
    wait_for(lambda: not alive(pid))


def test_holder_loss_of_a_kept_terminal_waits_then_restarts_a_shell(fake_hc: FakeHc, short_tmp: Path) -> None:
    # hc: the record stays live with no pid and refuses input while it waits
    # (terminals.rs check_program); the first retry comes after 1.5 s
    # (KEEP_RETRY_MS); the restart sets the new pid and clears the reason
    # (runtime.rs spawn_result).
    rec = run(fake_hc, short_tmp, "exec cat", keep=True)
    address = str(rec["address"])
    old_pid = rec["pid"]
    assert isinstance(old_pid, int)
    fake_hc.set_status(address, "working", app="claude")
    lost_at = time.monotonic()
    fake_hc.lose_holder(address)
    lost = get(fake_hc, address)
    assert lost["state"] == "live" and lost["keep"] is True and lost["reason"] == "holder_lost"
    assert lost["pid"] is None and lost["foreground"] is None and lost["finished_ms"] is None
    assert lost["status"] is None and lost["turn"] == 1  # the working turn ended with the program
    refused: List[Tuple[str, Dict[str, object]]] = [
        ("terminal.send", {"terminal": address, "text": "x"}),
        ("terminal.keys", {"terminal": address, "keys": ["enter"]}),
        ("terminal.interrupt", {"terminal": address, "timeout": 1.0}),
    ]
    for method, params in refused:
        reply = raw_call(fake_hc.socket_path, method, params)
        assert reply["error"]["data"]["kind"] == "unavailable", method
    wait_for(lambda: not alive(old_pid))
    wait_for(lambda: get(fake_hc, address)["pid"] is not None, timeout=10.0)
    assert time.monotonic() - lost_at >= 1.4
    back = get(fake_hc, address)
    assert back["state"] == "live" and back["reason"] is None
    assert back["exit_code"] is None and back["signal"] is None
    assert isinstance(back["pid"], int) and back["pid"] != old_pid
    assert fake_hc.input_log(address) == []  # nothing was typed while it was lost


def test_a_kept_program_killed_by_a_signal_is_lost_then_restarted(fake_hc: FakeHc, short_tmp: Path) -> None:
    # hc runtime.rs record_finish: a kept program that died by a signal with
    # no exit code is "signaled", which is loss, not an end.
    rec = run(fake_hc, short_tmp, "kill -TERM $$", keep=True)
    address = str(rec["address"])
    wait_for(lambda: get(fake_hc, address)["reason"] == "signaled")
    lost = get(fake_hc, address)
    assert lost["state"] == "live" and lost["pid"] is None
    assert lost["signal"] == signal.SIGTERM and lost["exit_code"] is None and lost["finished_ms"] is None
    reply = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "x"})
    assert reply["error"]["data"]["kind"] == "unavailable"
    wait_for(lambda: get(fake_hc, address)["pid"] is not None, timeout=10.0)
    back = get(fake_hc, address)
    assert back["state"] == "live" and back["reason"] is None and back["signal"] is None


def test_an_unkept_program_killed_by_a_signal_finishes(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "kill -TERM $$")
    address = str(rec["address"])
    wait_for(lambda: get(fake_hc, address)["state"] == "finished")
    done = get(fake_hc, address)
    assert done["reason"] == "exited" and done["signal"] == signal.SIGTERM and done["exit_code"] is None
    assert done["pid"] == rec["pid"]


def test_killing_a_lost_kept_terminal_ends_it(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exec cat", keep=True)
    address = str(rec["address"])
    fake_hc.lose_holder(address)
    killed = raw_call(fake_hc.socket_path, "terminal.kill", {"terminal": address})["result"]
    assert killed["state"] == "finished" and killed["reason"] == "killed"
    time.sleep(1.8)  # past the retry it would have had
    assert get(fake_hc, address)["state"] == "finished"


def test_a_name_reaches_the_live_holder_else_the_latest_finished(fake_hc: FakeHc, short_tmp: Path) -> None:
    # hc terminals.rs resolve: a name means whoever holds it now, else the
    # most recent finished terminal that had it.
    first = str(run(fake_hc, short_tmp, "exit 0", name="ga")["address"])
    wait_for(lambda: get(fake_hc, first)["state"] == "finished")
    second = str(run(fake_hc, short_tmp, "exit 0", name="ga")["address"])
    wait_for(lambda: get(fake_hc, second)["state"] == "finished")
    assert get(fake_hc, "ga")["address"] == second
    live = str(run(fake_hc, short_tmp, "exec cat", name="ga")["address"])
    assert get(fake_hc, "ga")["address"] == live
    assert raw_call(fake_hc.socket_path, "terminal.get", {"terminal": "gb"})["error"]["data"]["kind"] == "not_found"


def test_send_refuses_a_blocked_program_and_reports_started(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exec cat")
    address = str(rec["address"])
    silent = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "a"})["result"]
    assert silent["started"] is None
    fake_hc.set_status(address, "blocked", kind="permission", app="claude")
    refused = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "b"})
    assert refused["error"]["data"]["kind"] == "blocked"
    fake_hc.set_status(address, "idle", app="claude")
    idle = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "c"})["result"]
    assert idle["started"] is False and idle["status"] == "idle"
    fake_hc.work_on_send(address)
    working = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "d"})["result"]
    assert working["started"] is True
    assert fake_hc.input_log(address) == ["a", "c", "d"]


def test_sent_text_shows_on_the_screen_once_as_a_terminal_echoes_it(fake_hc: FakeHc, short_tmp: Path) -> None:
    # hc types into a PTY whose line discipline echoes the text, so it shows
    # on the screen even for a program that never reads its input.
    address = str(run(fake_hc, short_tmp, "exec sleep 30")["address"])
    raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "typed-once"})
    screen = str(raw_call(fake_hc.socket_path, "terminal.read", {"terminal": address})["result"]["text"])
    assert screen.count("typed-once") == 1
    refused = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "never", "if": "working"})
    assert refused["error"]["data"]["kind"] == "status_mismatch"
    assert "never" not in str(raw_call(fake_hc.socket_path, "terminal.read", {"terminal": address})["result"]["text"])


def test_status_changes_advance_the_turn_when_leaving_working(fake_hc: FakeHc, short_tmp: Path) -> None:
    address = str(run(fake_hc, short_tmp, "exec cat")["address"])
    fake_hc.set_status(address, "working", app="claude")
    fake_hc.set_status(address, "blocked", kind="question", app="claude")  # leaves working: turn 1
    fake_hc.set_status(address, "idle", app="claude")  # blocked -> idle leaves nothing
    assert get(fake_hc, address)["turn"] == 1
    fake_hc.set_status(address, "working", app="claude")
    fake_hc.set_status(address, "idle", app="claude")
    rec = get(fake_hc, address)
    assert rec["reported"] is True and rec["turn"] == 2
    status = rec["status"]
    assert isinstance(status, dict) and status["state"] == "idle"
    assert isinstance(rec["status_ms"], int)


def test_a_core_restart_drops_connections_and_keeps_programs(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exec cat")
    accepted = fake_hc.connections
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.settimeout(5)
    conn.connect(fake_hc.socket_path)
    try:
        wait_for(lambda: fake_hc.connections > accepted)
        fake_hc.restart_core(version="0.1.20")
        assert conn.recv(1) == b""  # EOF: the old core is gone
    finally:
        conn.close()
    after = get(fake_hc, str(rec["address"]))
    assert after["pid"] == rec["pid"] and after["state"] == "live" and after["screen"] == "inexact"
    assert raw_call(fake_hc.socket_path, "hello", {"generation": 1})["result"]["version"] == "0.1.20"


def test_server_stop_ends_programs_and_the_core(fake_hc: FakeHc, short_tmp: Path) -> None:
    rec = run(fake_hc, short_tmp, "exec cat")
    pid = rec["pid"]
    assert isinstance(pid, int)
    assert raw_call(fake_hc.socket_path, "server.stop", {})["result"] == {"stopped": True}
    wait_for(lambda: not alive(pid))
    with pytest.raises(OSError):
        raw_call(fake_hc.socket_path, "hello", {})


def test_close_reaps_every_program(short_tmp: Path) -> None:
    fake = FakeHc(str(short_tmp / "own.sock"))
    fake.start()
    rec = run(fake, short_tmp, "exec sleep 60")
    pid = rec["pid"]
    assert isinstance(pid, int)
    fake.close()
    assert not alive(pid)
    with pytest.raises(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)


def test_a_lone_surrogate_escape_is_a_parse_error_that_answers_no_request(fake_hc: FakeHc, short_tmp: Path) -> None:
    # hc server.rs handle: serde_json refuses a lone surrogate escape, so the
    # line never parses and the reply carries no request id.
    address = str(run(fake_hc, short_tmp, "cat")["address"])
    reply = raw_call(fake_hc.socket_path, "terminal.send", {"terminal": address, "text": "caf\udce9"})
    assert reply["id"] is None
    assert reply["error"]["code"] == -32700
    assert fake_hc.input_log(address) == []
