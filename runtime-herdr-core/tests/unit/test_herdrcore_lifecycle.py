"""start, stop, observe, inventory, kill-object and the metadata ops against
an in-process fake-hc: the observe.v1 promises (exec-session-provider.md
"observe.v1") as this runtime keeps them."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import pytest
from cityharness import City, make_city
from fakehc.rawclient import raw_call

IDENTITY = {
    "GC_SESSION_ID": "mc-1",
    "GC_RUNTIME_EPOCH": "3",
    "GC_INSTANCE_TOKEN": "tok-abcdefgh-1234",
    "GT_PROCESS_NAMES": "cat",
}


def start_config(**fields: object) -> str:
    doc: Dict[str, object] = {"command": "cat", "env": dict(IDENTITY)}
    doc.update(fields)
    return json.dumps(doc)


def observe(city: City, name: str, *names: str) -> Dict[str, Any]:
    done = city.run("observe", name, stdin="".join(n + "\n" for n in names).encode())
    assert done.code == 0, done.stderr
    answer: Dict[str, Any] = json.loads(done.stdout)
    return answer


def wait_for(predicate: "object", timeout: float = 5.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.05)
    raise AssertionError("condition not met in time")


def test_start_then_observe_running_with_identity_and_agent(city: City) -> None:
    done = city.start("mc-mayor", start_config())
    assert done.code == 0, done.stderr
    answer = observe(city, "mc-mayor", "cat")
    assert answer["state"] == "running"
    assert answer["identity"] == IDENTITY
    assert answer["agent"] == "alive"
    assert str(answer["object"]["id"]).startswith("t")
    assert observe(city, "mc-mayor", "no-such-agent")["agent"] == "dead"
    assert "agent" not in observe(city, "mc-mayor")  # no names: not judged


def test_terminal_carries_labels_name_and_no_session_env(city: City) -> None:
    secret = "sk-very-secret-value-1234"
    config = start_config(env=dict(IDENTITY, ANTHROPIC_API_KEY=secret))
    assert city.start("mc-a", config).code == 0
    [record] = [t for t in city.terminals() if t["labels"]["gc.session"] == "mc-a"]  # type: ignore[index]
    labels = record["labels"]
    assert isinstance(labels, dict)
    assert labels["gc.city"] == city.paths.city_id[:12]
    assert len(labels["gc.obj"]) == 32 and labels["gc.pid"] == str(record["pid"])
    assert str(record["name"]).startswith("g") and len(str(record["name"])) == 21
    params = [c.params for c in city.fake.calls if c.method == "terminal.run"]  # type: ignore[union-attr]
    assert params[0]["env"] == {"TERM": "xterm-256color"}
    assert params[0]["no_parent"] is True and params[0]["no_notify"] is True and params[0]["keep"] is False
    assert secret not in json.dumps(params)
    # The agent itself got the session environment.
    env = city.fake.terminal_env(str(record["address"]))  # type: ignore[union-attr]
    assert "HC_SCOPE" in env  # hc set it on the launcher; the launcher drops it before the agent
    assert not list(city.spawn_dir.iterdir()), "the launcher unlinks its spawn file"


def test_duplicate_start_fails_and_fresh_only_exits_73(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    again = city.start("mc-a", start_config())
    assert again.code == 1 and "already exists" in again.stderr
    fresh = city.start("mc-a", start_config(fresh_only=True))
    assert fresh.code == 73


def test_stop_is_idempotent_and_leaves_absent(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    obj = city.terminals()[0]["labels"]["gc.obj"]  # type: ignore[index]
    assert city.run("stop", "mc-a").code == 0
    assert observe(city, "mc-a")["state"] == "absent"
    assert city.run("stop", "mc-a").code == 0
    assert not (Path(city.context().state_dir("meta")) / f"{obj}.json").exists()


def test_stop_with_the_core_down_exits_1(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    city.fake.close()  # type: ignore[union-attr]
    done = city.run("stop", "mc-a", extra={"GC_RPP_FAULT": ""})
    assert done.code == 1
    city.fake = None


def test_exited_program_reads_dead_and_its_screen_stays_readable(city: City) -> None:
    assert city.start("mc-a", start_config(command="echo bye-now; exit 3", lifecycle="one_shot")).code == 0
    wait_for(lambda: observe(city, "mc-a")["state"] == "dead")
    peeked = city.run("peek", "mc-a", "5")
    assert peeked.code == 0 and "bye-now" in peeked.text
    assert city.run("is-running", "mc-a").text.strip() == "false"


def test_peek_of_a_name_no_box_holds_exits_66(city: City) -> None:
    assert city.run("peek", "never", "10").code == 66


def test_kept_terminal_after_holder_loss_is_a_dead_box(city: City) -> None:
    # The Herdr app can adopt a terminal (keep); on holder loss hc gives it a
    # bare shell, which is not the agent.
    assert city.start("mc-a", start_config()).code == 0
    address = city.address("mc-a")
    raw_call(city.paths.socket, "terminal.keep", {"terminal": address, "keep": True})
    city.fake.lose_holder(address)  # type: ignore[union-attr]
    assert observe(city, "mc-a")["state"] == "dead"
    wait_for(lambda: city.terminals()[0]["pid"] is not None)  # the replacement shell
    assert observe(city, "mc-a")["state"] == "dead"
    assert city.run("is-running", "mc-a").text.strip() == "false"
    assert city.run("nudge", "mc-a", stdin=b"hello").code == 0  # gone: nothing typed
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


def test_a_broken_live_record_is_recycled_by_a_plain_start(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    old = city.address("mc-a")
    raw_call(city.paths.socket, "terminal.keep", {"terminal": old, "keep": True})
    city.fake.lose_holder(old)  # type: ignore[union-attr]
    assert city.start("mc-a", start_config(fresh_only=True)).code == 73
    done = city.start("mc-a", start_config())
    assert done.code == 0, done.stderr
    addresses = [t["address"] for t in city.terminals()]
    assert old not in addresses and len(addresses) == 1
    assert observe(city, "mc-a")["state"] == "running"


def test_finished_records_are_removed_before_a_new_incarnation(city: City) -> None:
    assert city.start("mc-a", start_config(command="exit 0", lifecycle="one_shot")).code == 0
    wait_for(lambda: observe(city, "mc-a")["state"] == "dead")
    done = city.start("mc-a", start_config())
    assert done.code == 0, done.stderr
    assert len(city.terminals()) == 1


def test_inventory_lists_each_name_once_with_the_newest_record(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    assert city.start("mc-b", start_config(command="exit 0", lifecycle="one_shot")).code == 0
    wait_for(lambda: observe(city, "mc-b")["state"] == "dead")
    done = city.run("inventory")
    assert done.code == 0, done.stderr
    doc = json.loads(done.stdout)
    assert doc["complete"] is True
    by_name = {entry["name"]: entry for entry in doc["sessions"]}
    assert set(by_name) == {"mc-a", "mc-b"}
    assert by_name["mc-a"]["state"] == "running" and by_name["mc-a"]["attached"] is False
    assert by_name["mc-a"]["agent"] == "alive" and by_name["mc-a"]["last_activity"]
    assert by_name["mc-a"]["restart_requested"] is False
    assert by_name["mc-b"]["state"] == "dead" and by_name["mc-b"]["identity"] == IDENTITY
    assert city.run("set-meta", "mc-a", "GC_RESTART_REQUESTED", stdin=b"1700000000").code == 0
    again = {e["name"]: e for e in json.loads(city.run("inventory").stdout)["sessions"]}
    assert again["mc-a"]["restart_requested"] is True


def test_metadata_ops(city: City) -> None:
    assert city.run("get-meta", "nobody", "K").code == 0
    assert city.run("get-meta", "nobody", "K").stdout == b""
    assert city.run("remove-meta", "nobody", "K").code == 0
    assert city.run("set-meta", "nobody", "K", stdin=b"v").code == 1
    assert city.start("mc-a", start_config()).code == 0
    assert city.run("get-meta", "mc-a", "GC_INSTANCE_TOKEN").stdout == IDENTITY["GC_INSTANCE_TOKEN"].encode()
    assert city.run("set-meta", "mc-a", "GC_INSTANCE_TOKEN", stdin=b"tok-2").code == 0
    assert observe(city, "mc-a")["identity"]["GC_INSTANCE_TOKEN"] == "tok-2"
    assert city.run("set-meta", "mc-a", "K", stdin=b"").code == 0
    assert city.run("get-meta", "mc-a", "K").stdout == b""
    assert city.run("remove-meta", "mc-a", "GC_INSTANCE_TOKEN").code == 0
    assert "GC_INSTANCE_TOKEN" not in observe(city, "mc-a")["identity"]


def test_meta_file_is_private(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    meta_dir = Path(city.context().state_dir("meta"))
    [path] = list(meta_dir.iterdir())
    assert path.stat().st_mode & 0o777 == 0o600
    assert meta_dir.stat().st_mode & 0o777 == 0o700


def test_kill_object_rechecks_then_kills_exactly(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    obj = observe(city, "mc-a", "cat")["object"]

    def kill(mode: str, target: object = obj) -> str:
        done = city.run("kill-object", "mc-a", stdin=json.dumps({"object": target, "mode": mode}).encode())
        assert done.code == 0, done.stderr
        return done.text.strip()

    assert kill("corpse") == "live"
    assert kill("zombie") == "changed"  # cat, the agent, is alive
    assert kill("corpse", {"id": "t999", "created": "2020-01-01T00:00:00.000Z"}) == "gone"
    assert kill("corpse", dict(obj, created="2020-01-01T00:00:00.000Z")) == "gone"
    assert city.run("set-meta", "mc-a", "GT_PROCESS_NAMES", stdin=b"not-running").code == 0
    assert kill("zombie") == "killed"
    assert observe(city, "mc-a")["state"] == "absent"


def test_kill_object_on_a_corpse(city: City) -> None:
    assert city.start("mc-a", start_config(command="exit 0", lifecycle="one_shot")).code == 0
    wait_for(lambda: observe(city, "mc-a")["state"] == "dead")
    obj = observe(city, "mc-a")["object"]
    done = city.run("kill-object", "mc-a", stdin=json.dumps({"object": obj, "mode": "corpse"}).encode())
    assert done.text.strip() == "killed"
    assert observe(city, "mc-a")["state"] == "absent"


def test_list_running_is_runnings_by_prefix(city: City) -> None:
    for name in ("mc-a", "mc-b", "other"):
        assert city.start(name, start_config()).code == 0
    assert city.run("list-running", "mc-").text.split() == ["mc-a", "mc-b"]
    assert city.run("stop", "mc-a").code == 0
    assert city.run("list-running", "").text.split() == ["mc-b", "other"]


def test_list_running_failure_is_not_absence(city: City) -> None:
    done = city.run("list-running", "", extra={"GC_RPP_FAULT": "unavailable"})
    assert done.code == 1 and done.stdout == b""


def test_process_alive(city: City) -> None:
    assert city.run("process-alive", "nobody", stdin=b"cat\n").text.strip() == "false"
    assert city.start("mc-a", start_config()).code == 0
    assert city.run("process-alive", "mc-a", stdin=b"").text.strip() == "true"
    assert city.run("process-alive", "mc-a", stdin=b"cat\n").text.strip() == "true"
    assert city.run("process-alive", "mc-a", stdin=b"vim\n").text.strip() == "false"


def test_faults_read_unknown(city: City) -> None:
    assert city.start("mc-a", start_config()).code == 0
    fault = {"GC_RPP_FAULT": "unavailable"}
    assert json.loads(city.run("observe", "mc-a", extra=fault).stdout) == {"state": "unknown"}
    inventory = json.loads(city.run("inventory", extra=fault).stdout)
    assert inventory == {"complete": False, "sessions": []}
    assert city.run("is-attached", "mc-a", extra=fault).code == 1


def test_cities_on_one_state_root_are_separate(short_tmp: Path, home_dir: Path) -> None:
    first = make_city(short_tmp, home_dir, city_path="/cities/one")
    second = make_city(short_tmp, home_dir, city_path="/cities/two")
    assert first.paths.socket != second.paths.socket
    first.start_core()
    second.start_core()
    try:
        assert first.start("mc-a", start_config()).code == 0
        assert observe(second, "mc-a")["state"] == "absent"
        assert json.loads(second.run("inventory").stdout)["sessions"] == []
    finally:
        for made in (first, second):
            assert made.fake is not None
            made.fake.close()


def test_observe_answers_within_4s_while_a_nudge_is_held(city: City) -> None:
    from cityharness import in_thread

    assert city.start("mc-a", start_config()).code == 0
    address = city.address("mc-a")
    city.fake.hold_input(address)  # type: ignore[union-attr]
    results = []
    thread = in_thread(lambda: results.append(city.run("nudge", "mc-a", stdin=b"held text", deadline_ms=8000)))
    wait_for(lambda: city.fake.call_count("terminal.send") == 1)  # type: ignore[union-attr]
    began = time.monotonic()
    answer = observe(city, "mc-a", "cat")
    assert time.monotonic() - began < 4.0
    assert answer["state"] == "running"
    city.fake.release_input(address)  # type: ignore[union-attr]
    thread.join(timeout=15)
    assert results and results[0].code == 0


@pytest.mark.parametrize("op", ["observe", "inventory", "is-attached"])
def test_reads_with_the_core_down_kick_a_start(city: City, op: str) -> None:
    city.fake.close()  # type: ignore[union-attr]
    city.fake = None
    args = [] if op == "inventory" else ["mc-a"]
    done = city.run(op, *args)
    if op == "observe":
        assert json.loads(done.stdout) == {"state": "unknown"}
    elif op == "inventory":
        assert json.loads(done.stdout)["complete"] is False
    else:
        assert done.code == 1
    # The kicked start runs in the background through the fake hc binary.
    wait_for(lambda: os.path.exists(city.paths.socket), timeout=20)
    wait_for(lambda: city.run("observe", "mc-a").text.strip() == '{"state":"absent"}', timeout=20)
    kick_file = Path(city.context().state_file("kick.json"))
    wait_for(kick_file.exists, timeout=10)
    kick = json.loads(kick_file.read_text())
    assert kick["ok"] is True
    from fakehc.rawclient import raw_call as call

    call(city.paths.socket, "server.stop", {})


def test_inventory_refreshes_activity_of_agents_that_never_report(city: City) -> None:
    command = "while :; do date +%s%N; sleep 0.2; done"
    assert city.start("mc-a", start_config(command=command)).code == 0

    def last() -> str:
        doc = json.loads(city.run("inventory").stdout)
        return str(doc["sessions"][0]["last_activity"])

    first = last()
    time.sleep(1.2)
    assert last() > first, "a changing screen is activity, read by inventory itself"


@pytest.mark.parametrize("miss", ["failed", "deadline"])
def test_inventory_reads_a_screen_it_did_not_read_as_active_now(
    city: City, monkeypatch: pytest.MonkeyPatch, miss: str
) -> None:
    from gc_runtime_herdr_core.herdrcore import reads
    from gc_runtime_herdr_core.rpp.wire import rfc3339_ms

    clock = [int(time.time() * 1000)]
    city.host = dataclasses.replace(city.host, now_ms=lambda: clock[0])
    assert city.start("mc-a", start_config()).code == 0
    assert city.start("mc-b", start_config()).code == 0

    def last() -> Dict[str, str]:
        doc = json.loads(city.run("inventory").stdout)
        return {entry["name"]: str(entry["last_activity"]) for entry in doc["sessions"]}

    still = last()  # cat's screens stay as they are from here on
    assert still == {"mc-a": rfc3339_ms(clock[0]), "mc-b": rfc3339_ms(clock[0])}
    clock[0] += 3_600_000
    read_before = city.fake.call_count("terminal.read")  # type: ignore[union-attr]
    with monkeypatch.context() as patch:
        if miss == "failed":
            city.fake.fail_next("terminal.read", "unavailable", count=2)  # type: ignore[union-attr]
        else:
            patch.setattr(reads, "SCREEN_READ_RESERVE_S", 1e9)  # no time left for any read
        now = rfc3339_ms(clock[0])
        assert last() == {"mc-a": now, "mc-b": now}, "an hour-old time could let gc's idle arm stop a busy box"
    assert city.fake.call_count("terminal.read") == read_before + (2 if miss == "failed" else 0)  # type: ignore[union-attr]
    # The stored entries stay: reading the same screens again gives back their time.
    assert last() == still


def test_a_lost_run_reply_is_found_by_its_object_never_sent_again(city: City) -> None:
    city.fake.drop_reply("terminal.run")  # type: ignore[union-attr]
    done = city.start("mc-a", start_config())
    assert done.code == 0, done.stderr
    assert city.fake.call_count("terminal.run") == 1  # type: ignore[union-attr]
    live = [t for t in city.terminals() if t["state"] == "live"]
    assert len(live) == 1
    assert observe(city, "mc-a")["state"] == "running"


def test_a_quick_command_whose_run_reply_was_lost_runs_once(city: City) -> None:
    marker = city.root / "ran"
    city.fake.drop_reply("terminal.run", after_exit=True)  # type: ignore[union-attr]
    done = city.start("mc-a", start_config(command=f"echo once >> {marker}", lifecycle="one_shot"))
    assert done.code == 0, done.stderr
    assert marker.read_text() == "once\n"
    assert observe(city, "mc-a")["state"] == "dead"


def test_a_lost_run_that_started_nothing_fails_and_keeps_the_metadata(city: City) -> None:
    city.fake.lose_request("terminal.run")  # type: ignore[union-attr]
    done = city.start("mc-a", start_config())
    assert done.code == 1 and "cannot start 'mc-a'" in done.stderr
    assert city.fake.call_count("terminal.run") == 1  # type: ignore[union-attr]
    assert city.terminals() == []
    # hc never answered, so it may still start the terminal: the metadata stays
    # (inventory removes it once it is old and no record carries it).
    assert len(list(Path(city.context().state_dir("meta")).iterdir())) == 1
    assert city.start("mc-a", start_config()).code == 0


def test_a_failed_rollback_keeps_the_metadata_of_the_terminal_it_left(city: City) -> None:
    city.fake.drop_reply("terminal.label")  # type: ignore[union-attr]
    city.fake.fail_next("terminal.kill", "unavailable")  # type: ignore[union-attr]
    done = city.start("mc-a", start_config())
    assert done.code == 1 and "cannot start 'mc-a'" in done.stderr
    # hc refused the kill, so its record stays; the captured tree was killed
    # anyway. The record keeps its identity: gc can still tell whose it is.
    answer = observe(city, "mc-a")
    assert answer["state"] in ("running", "dead") and answer["identity"] == IDENTITY


def cancel_a_start(city: City) -> None:
    """Cancel a start while hc runs its terminal; the start exits 1."""
    from cityharness import in_thread

    from gc_runtime_herdr_core.rpp.cancel import CancelToken

    city.fake.delay_reply("terminal.run", 1.0)  # type: ignore[union-attr]
    cancel = CancelToken()
    results = []
    thread = in_thread(lambda: results.append(city.run("start", "mc-a", stdin=start_config().encode(), cancel=cancel)))
    wait_for(lambda: city.fake.call_count("terminal.run") == 1)  # type: ignore[union-attr]
    cancel.cancel("terminated")
    thread.join(timeout=20)
    assert results and results[0].code == 1


def test_a_canceled_start_leaves_no_terminal_or_metadata(city: City) -> None:
    cancel_a_start(city)
    wait_for(lambda: all(t["state"] != "live" for t in city.terminals()))
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_a_canceled_starts_rollback_waits_out_a_record_still_live(city: City) -> None:
    # The op's pause ends at the cancel, so the rollback waits with its own.
    city.fake.fail_next("terminal.rm", "live")  # type: ignore[union-attr]
    cancel_a_start(city)
    assert city.fake.call_count("terminal.rm") == 2  # type: ignore[union-attr]
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_observe_answers_within_4s_while_a_start_holds_the_name(city: City) -> None:
    from cityharness import in_thread

    city.fake.delay_reply("terminal.run", 5.0)  # type: ignore[union-attr]
    thread = in_thread(lambda: city.start("mc-a", start_config()))
    wait_for(lambda: city.fake.call_count("terminal.run") == 1)  # type: ignore[union-attr]
    began = time.monotonic()
    answer = observe(city, "mc-a")
    assert time.monotonic() - began < 4.0
    assert answer["state"] in ("unknown", "running")
    thread.join(timeout=20)


def test_a_work_dir_that_does_not_exist_fails_the_start(city: City) -> None:
    done = city.start("mc-a", start_config(work_dir=str(city.root / "missing")))
    assert done.code == 1 and "work_dir" in done.stderr
    assert city.terminals() == []


def test_an_unreadable_process_is_cannot_tell_never_dead(city: City) -> None:
    from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs

    assert city.start("mc-a", start_config(command="cat; true")).code == 0
    box = int(str(city.terminals()[0]["pid"]))
    agent = int(observe(city, "mc-a", "cat")["agent_pid"])
    assert agent != box, "cat runs under the box's sh, whose children list places it"

    class Unreadable(LinuxProcs):
        def _read(self, at: int, leaf: str) -> bytes:
            if at == agent and leaf == "cmdline":
                raise PermissionError(13, "Permission denied")
            return super()._read(at, leaf)

    city.procs.inner = Unreadable()
    assert "agent" not in observe(city, "mc-a", "cat")
    done = city.run("process-alive", "mc-a", stdin=b"cat\n")
    assert done.code == 0 and done.stdout == b"", "empty: gc reads it as alive, never dead"
    obj = observe(city, "mc-a")["object"]
    done = city.run("kill-object", "mc-a", stdin=json.dumps({"object": obj, "mode": "zombie"}).encode())
    assert done.code == 0 and done.text.strip() == "changed"
    assert observe(city, "mc-a")["state"] == "running"


@pytest.mark.skipif(
    not os.path.exists(f"/proc/{os.getpid()}/task/{os.getpid()}/children"),
    reason="this kernel keeps no children lists, so an unreadable process fails every snapshot",
)
def test_an_unreadable_process_outside_the_box_leaves_its_answers(city: City) -> None:
    from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs

    assert city.start("mc-a", start_config()).code == 0
    other = subprocess.Popen(["sleep", "60"])  # as ssh-agent reads under hidepid=1

    class Unreadable(LinuxProcs):
        def _read(self, at: int, leaf: str) -> bytes:
            if at == other.pid and leaf in ("stat", "cmdline"):
                raise PermissionError(13, "Permission denied")
            return super()._read(at, leaf)

    try:
        city.procs.inner = Unreadable()
        assert observe(city, "mc-a", "cat")["agent"] == "alive"
        assert observe(city, "mc-a", "vim")["agent"] == "dead"
        assert city.run("process-alive", "mc-a", stdin=b"vim\n").text.strip() == "false"
        assert city.run("is-attached", "mc-a").text.strip() == "false"
        obj = observe(city, "mc-a")["object"]
        assert city.run("set-meta", "mc-a", "GT_PROCESS_NAMES", stdin=b"not-running").code == 0
        done = city.run("kill-object", "mc-a", stdin=json.dumps({"object": obj, "mode": "zombie"}).encode())
        assert done.code == 0 and done.text.strip() == "killed"
    finally:
        other.kill()
        other.wait()


def test_process_alive_without_a_process_table_cannot_tell(city: City) -> None:
    from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, ProcError

    class Broken(LinuxProcs):
        def snapshot(self) -> Dict[int, Any]:
            raise ProcError("no /proc")

    assert city.start("mc-a", start_config()).code == 0
    city.procs.inner = Broken()
    done = city.run("process-alive", "mc-a", stdin=b"cat\n")
    assert done.code == 0 and done.stdout == b"", "empty: gc reads it as alive, never dead"


def test_an_agent_that_dies_during_startup_fails_the_start(city: City) -> None:
    done = city.start("mc-a", start_config(command="echo oops; exit 3", process_names=["cat"]))
    assert done.code == 1 and "exited during startup" in done.stderr
    one_shot = city.start("mc-b", start_config(command="exit 0", lifecycle="one_shot"))
    assert one_shot.code == 0, one_shot.stderr
