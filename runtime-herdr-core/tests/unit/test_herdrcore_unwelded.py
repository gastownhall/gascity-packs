"""provision and launch (``proc.provision`` with ``proc.launch``): gc's
un-welded start against an in-process fake-hc.

``provision`` prepares the name and creates no terminal: no agent runs, so
``is-running`` answers false, ``observe`` absent and ``inventory`` leaves the
name out. ``launch`` creates the terminal, seeds the launch's identity and
types nothing; without ``fresh_only`` it replaces a running agent, killing
the old one before the new terminal exists and removing the old record only
after, so the name is never listed absent mid-relaunch."""

from __future__ import annotations

import json
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest
from cityharness import City, in_thread, make_city
from fakehc.cli import SEND_GATE_ENV, write_launcher
from conftest import teardown_cores
from fakehc.rawclient import raw_call
from test_herdrcore_core import core_environ, entry_env, invoke
from test_herdrcore_inputs import answer
from test_herdrcore_server import no_core_started

from gc_runtime_herdr_core.hc.paths import resolve_paths
from gc_runtime_herdr_core.herdrcore import provisioned
from gc_runtime_herdr_core.herdrcore.lifecycle import STARTUP_UNCONFIRMED_KEY
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, scan_environ
from gc_runtime_herdr_core.herdrcore.reads import META_GC_AGE_S
from gc_runtime_herdr_core.rpp.cancel import CancelToken
from gc_runtime_herdr_core.rpp.frozen import replace

TOKEN = f"tok-unwelded-{os.getpid()}"
IDENTITY = {
    "GC_SESSION_ID": "mc-1",
    "GC_RUNTIME_EPOCH": "3",
    "GC_INSTANCE_TOKEN": TOKEN,  # every kill scans the host by token: no other run carries it
    "GT_PROCESS_NAMES": "cat",
}
LAUNCH_IDENTITY = dict(IDENTITY, GC_CONTINUATION_EPOCH="5")


def config(**fields: object) -> bytes:
    doc: Dict[str, object] = {"command": "exec cat", "env": dict(LAUNCH_IDENTITY), "process_names": ["cat"]}
    doc.update(fields)
    return json.dumps(doc).encode()


def provision(city: City, name: str = "mc-a", **fields: object) -> Any:
    return city.run("provision", name, stdin=config(**fields))


def launch(city: City, name: str = "mc-a", **fields: object) -> Any:
    return city.run("launch", name, stdin=config(**fields))


def observe(city: City, name: str, *names: str) -> Dict[str, Any]:
    done = city.run("observe", name, stdin="".join(n + "\n" for n in names).encode())
    assert done.code == 0, done.stderr
    answer: Dict[str, Any] = json.loads(done.stdout)
    return answer


def inventory_names(city: City) -> List[str]:
    done = city.run("inventory")
    assert done.code == 0, done.stderr
    return [entry["name"] for entry in json.loads(done.stdout)["sessions"]]


def record_path(city: City, name: str) -> Path:
    return Path(provisioned.record_path(city.context(), name))


def wait_for(predicate: "object", timeout: float = 5.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.05)
    raise AssertionError("condition not met in time")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat_line = Path(f"/proc/{pid}/stat").read_text() if Path(f"/proc/{pid}/stat").exists() else ""
    return ") Z " not in stat_line


def carriers(token: str) -> List[int]:
    procs = LinuxProcs()
    return [p.pid for p in scan_environ(procs, procs.snapshot(), "GC_INSTANCE_TOKEN", token)]


# --- provision ------------------------------------------------------------------------------------


def test_provision_creates_no_agent(city: City) -> None:
    canary = "sk-canary-provision-0123456789"
    env = dict(LAUNCH_IDENTITY, ANTHROPIC_API_KEY=canary)
    done = provision(city, fresh_only=True, env=env)
    assert done.code == 0, done.stderr
    assert city.fake.call_count("terminal.run") == 0  # type: ignore[union-attr]
    assert city.terminals() == []
    assert not city.spawn_dir.exists() or list(city.spawn_dir.iterdir()) == []
    assert city.run("is-running", "mc-a").text.strip() == "false"
    assert observe(city, "mc-a", "cat") == {"state": "absent"}
    assert "mc-a" not in inventory_names(city)
    assert carriers(TOKEN) == [], "no process carries the token"
    path = record_path(city, "mc-a")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    raw = path.read_text()
    assert canary not in raw, "no env value but the identity seed is kept"
    doc = json.loads(raw)
    assert doc["session"] == "mc-a"
    assert doc["values"] == LAUNCH_IDENTITY
    assert "session_setup" not in doc and "work_dir" not in doc


def test_provision_does_exactly_what_the_config_carries(city: City) -> None:
    work = city.root / "work"
    work.mkdir()
    overlay = city.root / "overlay"
    overlay.mkdir()
    (overlay / "staged.txt").write_text("staged")
    marker = city.root / "pre-start-ran"
    done = provision(city, work_dir=str(work), overlay_dir=str(overlay), pre_start=[f"touch '{marker}'"])
    assert done.code == 0, done.stderr
    assert (work / "staged.txt").read_text() == "staged"
    assert marker.exists()

    # gc stripped the host work (fs.host): nothing is staged or run.
    work_b = city.root / "work-b"
    work_b.mkdir()
    assert provision(city, "mc-b", work_dir=str(work_b)).code == 0
    assert list(work_b.iterdir()) == []

    failing = provision(city, "mc-c", pre_start=["exit 3"])
    assert failing.code == 1 and "pre_start[0] exited 3" in failing.stderr
    assert not record_path(city, "mc-c").exists()
    assert city.terminals() == []


def test_provision_defers_session_steps_to_launch(city: City) -> None:
    agent_mark = city.root / "agent-ran"
    setup_mark = city.root / "setup-ran"
    command = f"touch '{agent_mark}'; exec cat"
    setup = [f"test -e '{agent_mark}' && echo \"$GC_SESSION\" > '{setup_mark}'"]
    assert provision(city, command=command, session_setup=setup, fresh_only=True).code == 0
    assert not setup_mark.exists(), "session_setup waits for the agent"
    done = launch(city, command=command, fresh_only=True)  # gc's launch config leaves the host work out
    assert done.code == 0, done.stderr
    assert setup_mark.read_text().strip() == "mc-a", "run once the agent's process exists"
    setup_mark.unlink()
    replaced = launch(city, command=command)
    assert replaced.code == 0, replaced.stderr
    assert not setup_mark.exists(), "a replacing launch runs no deferred steps"


def test_launch_runs_its_own_session_steps_never_both(city: City) -> None:
    deferred = city.root / "deferred"
    own = city.root / "own"
    assert provision(city, session_setup=[f"echo x >> '{deferred}'"]).code == 0
    done = launch(city, session_setup=[f"echo x >> '{own}'"])
    assert done.code == 0, done.stderr
    assert own.read_text() == "x\n" and not deferred.exists()


@pytest.mark.parametrize("dead", [False, True], ids=["live", "dead"])
def test_provision_fresh_only_on_any_record_exits_73_and_touches_nothing(city: City, dead: bool) -> None:
    if dead:
        assert city.start("mc-a", config(command="exit 0", lifecycle="one_shot").decode()).code == 0
        wait_for(lambda: observe(city, "mc-a")["state"] == "dead")
    else:
        assert city.start("mc-a", config().decode()).code == 0
    before = city.terminals()
    marker = city.root / "pre-start-ran"
    done = provision(city, fresh_only=True, pre_start=[f"touch '{marker}'"])
    assert done.code == 73, done.stderr
    assert not marker.exists()
    assert city.terminals() == before
    assert not record_path(city, "mc-a").exists()


def test_provision_on_a_live_incarnation_is_already_exists(city: City) -> None:
    assert city.start("mc-a", config().decode()).code == 0
    marker = city.root / "pre-start-ran"
    done = provision(city, pre_start=[f"touch '{marker}'"])
    assert done.code == 1 and 'session "mc-a" already exists' in done.stderr
    assert not marker.exists(), "a live work dir is never staged over"
    assert observe(city, "mc-a")["state"] == "running"


def test_provision_recycles_finished_and_broken_records(city: City) -> None:
    assert city.start("mc-a", config(command="exit 0", lifecycle="one_shot").decode()).code == 0
    wait_for(lambda: observe(city, "mc-a")["state"] == "dead")
    assert city.start("mc-b", config().decode()).code == 0
    broken = city.address("mc-b")
    raw_call(city.paths.socket, "terminal.keep", {"terminal": broken, "keep": True})
    city.fake.lose_holder(broken)  # type: ignore[union-attr]
    for name in ("mc-a", "mc-b"):
        done = provision(city, name)
        assert done.code == 0, done.stderr
        assert record_path(city, name).exists()
    assert city.terminals() == []


def test_a_second_provision_replaces_the_first_record(city: City) -> None:
    assert provision(city).code == 0
    assert provision(city, env=dict(LAUNCH_IDENTITY, GC_INSTANCE_TOKEN="tok-second")).code == 0
    assert json.loads(record_path(city, "mc-a").read_text())["values"]["GC_INSTANCE_TOKEN"] == "tok-second"


# --- launch ------------------------------------------------------------------------------------------


def test_launch_types_nothing(city: City) -> None:
    turn = "first-turn-must-not-be-typed"
    command = "printf 'READY>\\n'; exec cat"
    assert provision(city, fresh_only=True).code == 0
    done = launch(city, command=command, nudge=turn, ready_prompt_prefix="READY>", fresh_only=True)
    assert done.code == 0, done.stderr
    time.sleep(0.3)
    address = city.address("mc-a")
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]
    assert city.fake.key_log(address) == []  # type: ignore[union-attr]
    assert turn not in city.run("peek", "mc-a", "50").text
    assert city.run("is-running", "mc-a").text.strip() == "true"

    # Control: the welded start still types the same config's turn.
    welded = city.start("mc-b", config(command=command, nudge=turn, ready_prompt_prefix="READY>").decode())
    assert welded.code == 0, welded.stderr
    assert city.fake.input_log(city.address("mc-b")) == [turn]  # type: ignore[union-attr]


def test_launch_fresh_only_on_a_running_agent_exits_73(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    assert launch(city, fresh_only=True).code == 0
    [before] = city.terminals()
    again = launch(city, fresh_only=True)
    assert again.code == 73, again.stderr
    [after] = city.terminals()
    assert (after["address"], after["pid"], after["labels"]) == (before["address"], before["pid"], before["labels"])
    assert alive(int(str(before["pid"])))


def test_launch_fresh_only_on_a_dead_record_exits_73(city: City) -> None:
    assert city.start("mc-a", config(command="exit 0", lifecycle="one_shot").decode()).code == 0
    wait_for(lambda: observe(city, "mc-a")["state"] == "dead")
    before = city.terminals()
    assert launch(city, fresh_only=True).code == 73
    assert city.terminals() == before


def test_launch_replaces_a_running_agent(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    assert launch(city, fresh_only=True).code == 0
    [old] = city.terminals()
    old_pid = int(str(old["pid"]))
    assert city.run("set-meta", "mc-a", "custom.key", stdin=b"kept").code == 0
    assert city.run("set-meta", "mc-a", STARTUP_UNCONFIRMED_KEY, stdin=b"withheld").code == 0
    second = f"{TOKEN}-second"
    done = launch(city, env=dict(LAUNCH_IDENTITY, GC_INSTANCE_TOKEN=second, GC_RUNTIME_EPOCH="4"))
    assert done.code == 0, done.stderr
    wait_for(lambda: not alive(old_pid))
    [new] = city.terminals()
    assert new["address"] != old["address"], "the old record is removed"
    assert new["labels"]["gc.obj"] != old["labels"]["gc.obj"]  # type: ignore[index]
    answer = observe(city, "mc-a", "cat")
    assert answer["state"] == "running" and answer["agent"] == "alive"
    assert answer["identity"]["GC_INSTANCE_TOKEN"] == second
    assert answer["identity"]["GC_RUNTIME_EPOCH"] == "4"
    assert city.run("get-meta", "mc-a", "custom.key").text == "kept", "set-meta's keys carry over"
    assert city.run("get-meta", "mc-a", STARTUP_UNCONFIRMED_KEY).text == "", "the pack's own per-launch key does not"
    assert carriers(TOKEN) == [], "the old incarnation's tree is gone"


def test_a_launch_that_cannot_start_leaves_the_running_agent(city: City, tmp_path: Path) -> None:
    assert provision(city, fresh_only=True).code == 0
    assert launch(city, fresh_only=True).code == 0
    [old] = city.terminals()
    old_pid = int(str(old["pid"]))
    done = launch(city, work_dir=str(tmp_path / "gone"))
    assert done.code == 1 and "work_dir is not an existing directory" in done.stderr, done.stderr
    assert alive(old_pid), "the agent it would replace still runs"
    assert city.terminals() == [old]
    assert observe(city, "mc-a", "cat")["agent"] == "alive"


def test_a_launch_whose_config_carries_no_token_keeps_the_boxs(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    assert launch(city, fresh_only=True).code == 0
    env = {k: v for k, v in LAUNCH_IDENTITY.items() if k != "GC_INSTANCE_TOKEN"}
    done = launch(city, env=env)
    assert done.code == 0, done.stderr
    assert city.run("get-meta", "mc-a", "GC_INSTANCE_TOKEN").text == TOKEN


@pytest.mark.parametrize(
    "held",
    [
        # Held after the new terminal exists: a launch that removed the old
        # record before creating the new one would read absent here.
        "terminal.rm",
        # Held while the new terminal is created.
        "terminal.run",
    ],
)
def test_replace_never_reads_absent(city: City, held: str) -> None:
    assert provision(city, fresh_only=True).code == 0
    assert launch(city, fresh_only=True).code == 0
    city.fake.delay_reply(held, 1.0)  # type: ignore[union-attr]
    results: List[Any] = []
    thread = in_thread(lambda: results.append(launch(city)))
    missing: List[str] = []
    polls = 0
    while thread.is_alive():
        listed = raw_call(city.paths.socket, "terminal.list", {"all": True})["result"]["terminals"]
        if not any(t["labels"].get("gc.session") == "mc-a" for t in listed):
            missing.append("terminal.list")
        if "mc-a" not in inventory_names(city):
            missing.append("inventory")
        polls += 1
    thread.join()
    assert results and results[0].code == 0, results[0].stderr
    assert polls > 3
    assert missing == [], "the name read absent mid-relaunch"
    assert len(city.terminals()) == 1


def test_identity_readable_right_after_launch(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    assert launch(city, fresh_only=True).code == 0
    for key in ("GC_RUNTIME_EPOCH", "GC_CONTINUATION_EPOCH", "GC_INSTANCE_TOKEN"):
        assert city.run("get-meta", "mc-a", key).text == LAUNCH_IDENTITY[key], key
    assert observe(city, "mc-a")["identity"] == IDENTITY


def test_the_welded_start_seeds_the_continuation_epoch_too(city: City) -> None:
    assert city.start("mc-a", config().decode()).code == 0
    assert city.run("get-meta", "mc-a", "GC_CONTINUATION_EPOCH").text == "5"
    assert observe(city, "mc-a")["identity"] == IDENTITY, "observe's identity is unchanged"


def test_launch_without_provision_or_box_refuses(city: City) -> None:
    done = launch(city, fresh_only=True)
    assert done.code == 1 and "nothing is provisioned" in done.stderr
    assert launch(city).code == 1
    assert city.fake.call_count("terminal.run") == 0  # type: ignore[union-attr]


def test_stop_between_provision_and_launch_makes_launch_refuse(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    stopped = city.run("stop", "mc-a")
    assert stopped.code == 0, stopped.stderr
    assert not record_path(city, "mc-a").exists()
    done = launch(city, fresh_only=True)
    assert done.code == 1 and "nothing is provisioned" in done.stderr
    assert city.terminals() == []


def test_stop_drops_the_record_with_the_core_down(city: City) -> None:
    assert provision(city).code == 0
    city.fake.close()  # type: ignore[union-attr]
    city.fake = None
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert not record_path(city, "mc-a").exists()


@pytest.fixture
def settling(short_tmp: Path, home_dir: Path) -> Iterator[City]:
    """A city whose core refuses a terminal's sends in its first seconds, as hc does."""
    made = make_city(short_tmp, home_dir)
    made.start_core(send_settle_s=4.0)
    try:
        yield made
    finally:
        teardown_cores(made.root / "R")
        if made.fake is not None:
            made.fake.close()
            assert made.fake.schema_violations == []


def test_a_first_turn_sent_while_the_terminal_settles_is_not_sent(settling: City) -> None:
    # gc's queue may deliver the first turn early in the terminal's life:
    # hc's settle refusal is not_sent, nothing typed, and the retry lands once.
    assert provision(settling, fresh_only=True).code == 0
    assert launch(settling, fresh_only=True).code == 0
    [record] = settling.terminals()
    early = settling.run("nudge", "mc-a", stdin=b"first turn")
    assert answer(early) == (80, "not_sent"), early.stderr
    assert settling.fake.input_log(str(record["address"])) == []  # type: ignore[union-attr]
    deadline = time.monotonic() + 10.0
    while True:
        done = settling.run("nudge", "mc-a", stdin=b"first turn")
        if done.code == 0:
            break
        assert answer(done) == (80, "not_sent") and time.monotonic() < deadline, done.stderr
        time.sleep(0.5)
    assert settling.fake.input_log(str(record["address"])) == ["first turn"]  # type: ignore[union-attr]


def test_a_launchers_send_gate_refuses_the_first_turn_until_removed(short_tmp: Path, home_dir: Path) -> None:
    # What gc's own contract harness uses: a fake-hc launcher whose core
    # refuses every send while a file exists, so a nudge answers not_sent.
    gate = short_tmp / "send-gate"
    gate.write_text("")
    env = entry_env(short_tmp, home_dir)
    write_launcher(env["GC_HC_TEST_BIN"], send_gate=str(gate))
    paths = resolve_paths(env)
    try:
        start = config(fresh_only=True)
        for op in ("provision", "launch"):
            done = invoke(env, op, "mc-a", stdin=start)
            assert done.returncode == 0, done.stderr
        assert SEND_GATE_ENV not in core_environ(paths.socket), "the gate is fake-hc's, never the core's env"
        refused = invoke(env, "nudge", "mc-a", stdin=b"first turn")
        assert refused.returncode == 80 and json.loads(refused.stdout)["outcome"] == "not_sent", refused.stderr
        gate.unlink()
        taken = invoke(env, "nudge", "mc-a", stdin=b"first turn")
        assert taken.returncode == 0, taken.stderr
        assert invoke(env, "stop", "mc-a").returncode == 0
    finally:
        teardown_cores(Path(paths.state_root))


@pytest.fixture
def at_rest(short_tmp: Path, home_dir: Path) -> Iterator[City]:
    """A city no core has ever run for."""
    made = make_city(short_tmp, home_dir)
    try:
        yield made
    finally:
        teardown_cores(made.root / "R")


def test_launch_in_a_city_at_rest_refuses_and_starts_no_core(at_rest: City) -> None:
    for fresh_only in (True, False):
        done = launch(at_rest, fresh_only=fresh_only)
        assert done.code == 1 and "nothing is provisioned" in done.stderr, done.stderr
    assert no_core_started(at_rest, wait_s=2.0)
    assert not os.path.exists(at_rest.paths.state_dir)


def test_launch_waits_for_the_agent_and_fails_when_it_exits_during_startup(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    done = launch(city, command="echo oops; exit 3", fresh_only=True)
    assert done.code == 1 and "exited during startup" in done.stderr
    assert len(city.terminals()) == 1, "the box is left for gc's token-gated stop"
    assert observe(city, "mc-a")["identity"]["GC_INSTANCE_TOKEN"] == TOKEN
    assert city.run("stop", "mc-a").code == 0
    assert city.terminals() == []


def test_launch_waits_for_the_agents_processes(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    done = launch(city, command="sleep 0.5; exec cat", fresh_only=True)
    assert done.code == 0, done.stderr
    assert observe(city, "mc-a", "cat")["agent"] == "alive", "launch returns once the agent runs"


def test_launch_cancel_rolls_back(city: City) -> None:
    assert provision(city, fresh_only=True).code == 0
    city.fake.delay_reply("terminal.run", 1.0)  # type: ignore[union-attr]
    cancel = CancelToken()
    results: List[Any] = []
    thread = in_thread(lambda: results.append(city.run("launch", "mc-a", stdin=config(fresh_only=True), cancel=cancel)))
    wait_for(lambda: city.fake.call_count("terminal.run") == 1)  # type: ignore[union-attr]
    cancel.cancel("terminated")
    thread.join(timeout=20)
    assert results and results[0].code == 1
    wait_for(lambda: all(t["state"] != "live" for t in city.terminals()))
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []
    assert not city.spawn_dir.exists() or list(city.spawn_dir.iterdir()) == []


def test_provision_record_expires(city: City) -> None:
    now = [int(time.time() * 1000)]
    city.host = replace(city.host, now_ms=lambda: now[0])
    assert provision(city).code == 0
    now[0] += int(META_GC_AGE_S * 1000) + 1
    done = launch(city)
    assert done.code == 1 and "nothing is provisioned" in done.stderr
    assert record_path(city, "mc-a").exists(), "launch reads it as absent; the next provision sweeps it"
    assert provision(city, "mc-b").code == 0
    assert not record_path(city, "mc-a").exists()


def test_provision_ttl_is_the_metadata_grace(city: City) -> None:
    assert provisioned.TTL_MS == int(META_GC_AGE_S * 1000)


def test_server_stop_drops_provision_records(city: City) -> None:
    assert provision(city).code == 0
    assert provision(city, "mc-b").code == 0
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert not record_path(city, "mc-a").exists() and not record_path(city, "mc-b").exists()
    late = launch(city)
    assert late.code == 1 and "the city is stopped" in late.stderr, late.stderr
    assert no_core_started(city, wait_s=1.0), "a late launch never revives the city"


def test_a_launch_in_a_parked_city_refuses_whatever_the_record_says(city: City) -> None:
    # A provision whose last write lands after server-stop dropped the
    # records leaves a stale one: the parked city still refuses the launch.
    assert provision(city).code == 0
    path = record_path(city, "mc-a")
    stale = path.read_bytes()
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    path.write_bytes(stale)
    os.chmod(path, 0o600)
    late = launch(city)
    assert late.code == 1 and "the city is stopped" in late.stderr, late.stderr
    assert "nothing is provisioned" not in late.stderr, late.stderr
    assert no_core_started(city, wait_s=1.0), "a late launch never revives the city"


def test_a_concurrent_launch_and_stop_leave_no_agent(city: City) -> None:
    # stop takes the record under the name's lock; a launch that loses the
    # race refuses, and one that wins is then stopped.
    assert provision(city, fresh_only=True).code == 0
    results: Dict[str, Any] = {}
    barrier = threading.Barrier(2)

    def run(op: str) -> None:
        barrier.wait()
        results[op] = launch(city, fresh_only=True) if op == "launch" else city.run("stop", "mc-a")

    threads = [in_thread(lambda op=op: run(op)) for op in ("launch", "stop")]
    for thread in threads:
        thread.join(timeout=60)
    assert results["stop"].code == 0
    if results["launch"].code == 0:
        assert city.run("stop", "mc-a").code == 0
    assert city.terminals() == []
