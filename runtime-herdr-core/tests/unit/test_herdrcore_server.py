"""server-stop (server-lifecycle): the city's core and every session the pack
started for the city end with it; a foreign terminal survives; with the core
not answering, its holders' programs and the incarnations' orphans are found
in the process table; exit 1 whenever a program of the city may survive; a
second call exits 0. Real processes under an in-process fake-hc, and real
stand-in holder processes."""

from __future__ import annotations

import dataclasses
import json
import os
import socket as unix_socket
import signal
import subprocess
import sys
import shutil
import time
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import pytest
from cityharness import City, in_thread
from fakehc.procfs import add_boot, add_proc
from fakehc.rawclient import raw_call
from test_herdrcore_treekill import PROXY, alive, token, wait_dead, wait_file

from gc_runtime_herdr_core.herdrcore import core, server
from gc_runtime_herdr_core.herdrcore.config import write_private_file
from gc_runtime_herdr_core.herdrcore.corescan import holder_prefix
from gc_runtime_herdr_core.herdrcore.infra_argv import BD_PROXY_CHILD_VERB, MANAGED_DOLT_SCOPE_WATCHDOG_VERB
from gc_runtime_herdr_core.herdrcore.lifecycle import INSTANCE_TOKEN_KEY
from gc_runtime_herdr_core.herdrcore.metastore import Meta, MetaError, MetaStore
from gc_runtime_herdr_core.herdrcore.procs import (
    LAUNCHER_NAME,
    LinuxProcs,
    Proc,
    ProcError,
    ProcSource,
)
from gc_runtime_herdr_core.herdrcore.server import sweep_without_core
from gc_runtime_herdr_core.rpp.ops import OpError

FAKE_BOOT = "00000000-0000-4000-8000-000000000001"
"""The boot a fake ``/proc`` counts its start times from."""

HOLDER = """\
import json, os, signal, subprocess, sys, time
# argv: hold --socket <socket> <spec file> <pid file>
spec, out = sys.argv[4], sys.argv[5]
children = []
for program in json.load(open(spec)):
    env = dict(os.environ)
    env.update(program.get("env", {}))
    children.append(subprocess.Popen(program["argv"], env=env).pid)
open(out + ".tmp", "w").write(" ".join(["ready"] + [str(pid) for pid in children]))
os.rename(out + ".tmp", out)
signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
while True:
    try:
        os.waitpid(-1, 0)  # reap what ends; a holder keeps running without programs
    except ChildProcessError:
        time.sleep(0.2)
"""


@pytest.fixture
def spawned() -> Iterator[List[int]]:
    """Pids a test started; every one is killed at its end."""
    pids: List[int] = []
    yield pids
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def start_config(command: str, tok: str = "", work_dir: str = "", fresh_only: bool = False) -> str:
    doc: Dict[str, object] = {"command": command}
    if tok:
        doc["env"] = {"GC_INSTANCE_TOKEN": tok}
    if work_dir:
        doc["work_dir"] = work_dir
    if fresh_only:
        doc["fresh_only"] = True
    return json.dumps(doc)


def run_foreign(city: City, argv: Sequence[str]) -> Dict[str, object]:
    """A terminal the city did not start (a person's), on the city's core."""
    reply = raw_call(city.paths.socket, "terminal.run", {"argv": list(argv), "keep": False})
    record: Dict[str, object] = reply["result"]
    return record


def core_down(city: City) -> None:
    assert city.fake is not None
    city.fake.close()
    city.fake = None


def start_holder(
    city: City, programs: List[Dict[str, object]], spawned: List[int], socket: Optional[str] = None
) -> List[int]:
    """A stand-in holder (``hold --socket <holder socket>``) running
    ``programs``, of the city's core unless ``socket`` is given; returns the
    holder's pid and then theirs."""
    script = city.root / "holder.py"
    script.write_text(HOLDER)
    spec = city.root / f"programs-{len(spawned)}.json"
    spec.write_text(json.dumps(programs))
    out = city.root / f"programs-{len(spawned)}.pids"
    if socket is None:
        socket = holder_prefix(city.paths) + "0123abcd.sock"
    holder = subprocess.Popen([sys.executable, str(script), "hold", "--socket", socket, str(spec), str(out)])
    spawned.append(holder.pid)
    pids = [int(p) for p in wait_file(out).split()[1:]]
    spawned.extend(pids)
    return [holder.pid] + pids


def write_meta(city: City, obj: str, meta: Meta) -> None:
    MetaStore(city.context().state_dir("meta")).write(obj, meta)


def start_of(pid: int) -> str:
    return LinuxProcs().snapshot()[pid].start


def this_boot() -> str:
    boot = LinuxProcs().boot()
    assert boot, "this host's boot id cannot be read"
    return boot


def no_core_started(city: City, wait_s: float = 1.0) -> bool:
    """No op brought the city's core back (no kick ran)."""
    end = time.monotonic() + wait_s
    while time.monotonic() < end:
        if os.path.exists(city.paths.socket):
            return False
        time.sleep(0.05)
    return True


# --- with the core answering ---------------------------------------------------------------


def test_server_stop_ends_every_session_and_the_core(city: City, spawned: List[int]) -> None:
    work = city.root / "w"
    work.mkdir()
    pids = {}
    for name in ("mc-a", "mc-b"):
        command = f"(setsid sleep 600 & echo $! > {work}/{name}.daemon); sleep 600 & echo $! > {work}/{name}.child; exec cat"
        assert city.start(name, start_config(command, token(f"srv-{name}"))).code == 0
        pids[name] = [int(wait_file(work / f"{name}.daemon")), int(wait_file(work / f"{name}.child"))]
        spawned.extend(pids[name])
    fake = city.fake
    assert fake is not None
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert done.stderr == ""
    for name, found in pids.items():
        assert all(wait_dead(pid) for pid in found), f"{name}'s tree and its daemon end with the server"
    assert fake.call_count("server.stop") == 1 and fake.stopped.is_set()
    assert not os.path.exists(city.paths.socket)
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_a_second_server_stop_exits_0_and_starts_no_core(city: City) -> None:
    assert city.start("mc-a", start_config("exec cat")).code == 0
    assert city.run("server-stop").code == 0
    again = city.run("server-stop")
    assert again.code == 0, again.stderr
    assert again.stderr == ""
    assert no_core_started(city)


def test_server_stop_with_no_core_ever_started_exits_0(city: City) -> None:
    core_down(city)
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert no_core_started(city)


def test_sessions_read_stopped_after_server_stop_and_start_again(city: City) -> None:
    assert city.start("mc-a", start_config("exec cat")).code == 0
    assert city.run("server-stop").code == 0
    running = city.run("is-running", "mc-a")
    assert (running.code, running.text.strip()) == (0, "false"), running.stderr
    alive_answer = city.run("process-alive", "mc-a", stdin=b"cat\n")
    assert (alive_answer.code, alive_answer.text.strip()) == (0, "false"), alive_answer.stderr
    stopped = city.run("stop", "mc-a")
    assert stopped.code == 0, stopped.stderr
    assert no_core_started(city), "a stopped city's reads start no core"
    # The next start brings the core back through an ordinary start.
    city.fake = None
    assert city.start("mc-b", start_config("exec cat")).code == 0
    assert city.run("is-running", "mc-b").text.strip() == "true"
    assert city.run("server-stop").code == 0


def test_a_foreign_terminal_survives_and_keeps_the_core(city: City, spawned: List[int]) -> None:
    work = city.root / "w"
    work.mkdir()
    assert city.start("mc-a", start_config(f"sleep 600 & echo $! > {work}/child; exec cat")).code == 0
    child = int(wait_file(work / "child"))
    spawned.append(child)
    foreign = run_foreign(city, ["sleep", "600"])
    foreign_pid = int(str(foreign["pid"]))
    spawned.append(foreign_pid)
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert wait_dead(child), "the city's session ends"
    assert alive(foreign_pid), "a terminal the city did not start survives"
    fake = city.fake
    assert fake is not None and fake.call_count("server.stop") == 0, "the core keeps running for it"
    assert [(t["address"], t["state"]) for t in city.terminals(all_records=False)] == [(foreign["address"], "live")]


def test_a_foreign_terminal_carrying_a_sessions_token_survives(city: City, spawned: List[int]) -> None:
    # One an agent opened through the in-agent hc may inherit its session's token.
    tok = token("srv-foreign-token")
    assert city.start("mc-a", start_config("exec cat", tok)).code == 0
    reply = raw_call(
        city.paths.socket, "terminal.run", {"argv": ["sleep", "600"], "env": {"GC_INSTANCE_TOKEN": tok}, "keep": False}
    )
    foreign_pid = int(str(reply["result"]["pid"]))
    spawned.append(foreign_pid)
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert alive(foreign_pid), "a live terminal the city did not start is never killed by a session's kill"


class DropKills(ProcSource):
    """The live process table, except that signals to ``spared`` are dropped:
    those processes outlive their kill."""

    def __init__(self, inner: ProcSource) -> None:
        self.inner = inner
        self.spared: List[int] = []

    def snapshot(self) -> Dict[int, Proc]:
        return self.inner.snapshot()

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        return self.inner.environ(pid)

    def boot(self) -> Optional[str]:
        return self.inner.boot()

    def kill(self, pid: int, sig: int) -> None:
        if pid not in self.spared:
            self.inner.kill(pid, sig)


def test_exit_1_when_a_session_may_survive_and_the_core_stays(city: City, spawned: List[int]) -> None:
    work = city.root / "w"
    work.mkdir()
    tok = token("srv-survivor")
    assert city.start("mc-a", start_config(f"(setsid sleep 600 & echo $! > {work}/daemon); exec cat", tok)).code == 0
    daemon = int(wait_file(work / "daemon"))
    spawned.append(daemon)
    dropping = DropKills(city.procs.inner)
    dropping.spared.append(daemon)
    city.procs.inner = dropping
    done = city.run("server-stop")
    assert done.code == 1
    assert "may survive" in done.stderr and str(daemon) in done.stderr
    assert tok not in done.stderr
    fake = city.fake
    assert fake is not None and fake.call_count("server.stop") == 0, "the core keeps the record for a retry"
    assert [t["labels"]["gc.session"] for t in city.terminals()] == ["mc-a"]  # type: ignore[index]
    dropping.spared.clear()
    retry = city.run("server-stop")
    assert retry.code == 0, retry.stderr
    assert wait_dead(daemon)


def test_start_keeps_the_programs_pid_and_start_time(city: City) -> None:
    assert city.start("mc-a", start_config("exec cat")).code == 0
    [record] = city.terminals()
    obj = record["labels"]["gc.obj"]  # type: ignore[index]
    meta = MetaStore(city.context().state_dir("meta")).read(str(obj))
    assert meta is not None and meta.pid == record["pid"]
    assert meta.pid_start == start_of(meta.pid)
    assert meta.boot == this_boot(), "the start time counts from this boot"


# --- with the core not answering --------------------------------------------------------------


def test_an_unreachable_core_triggers_the_holder_scan(city: City, spawned: List[int]) -> None:
    tok = token("srv-holder")
    core_down(city)
    holder, by_token, by_pid, foreign = start_holder(
        city,
        [
            {"argv": ["sleep", "600"], "env": {"GC_INSTANCE_TOKEN": tok}},  # a session's agent
            {"argv": ["sleep", "601"]},  # a session started without a token: found by its pid
            {"argv": ["sleep", "602"]},  # a person's terminal
        ],
        spawned,
    )
    orphan = subprocess.Popen(["sleep", "603"], env=dict(os.environ, GC_INSTANCE_TOKEN=tok), start_new_session=True)
    spawned.append(orphan.pid)
    write_meta(city, "a" * 32, Meta(session="mc-a", values={"GC_INSTANCE_TOKEN": tok}))
    write_meta(city, "b" * 32, Meta(session="mc-b", pid=by_pid, pid_start=start_of(by_pid), boot=this_boot()))
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert wait_dead(by_token) and wait_dead(by_pid), "the city's programs under the holder end"
    orphan.wait(timeout=5)
    assert alive(foreign), "a program the city did not start survives"
    assert alive(holder), "its holder keeps running for it"
    os.kill(foreign, signal.SIGKILL)
    assert wait_dead(foreign)
    again = city.run("server-stop")
    assert again.code == 0, again.stderr
    assert wait_dead(holder), "a holder left with no program ends with the server"
    assert no_core_started(city)


def test_a_recycled_pid_is_never_taken_for_the_program(city: City, spawned: List[int]) -> None:
    core_down(city)
    stranger = subprocess.Popen(["sleep", "600"])
    spawned.append(stranger.pid)
    write_meta(city, "c" * 32, Meta(session="mc-a", pid=stranger.pid, pid_start="1", boot=this_boot()))
    assert city.run("server-stop").code == 0
    assert alive(stranger.pid), "another start time is another process"


def test_a_start_time_from_another_boot_is_never_taken_for_the_program(city: City, spawned: List[int]) -> None:
    """A start time counts clock ticks from boot: after a reboot the same pid
    and tick count may name another process, so one kept with another boot
    finds nothing (no program outlives a reboot)."""
    core_down(city)
    stranger = subprocess.Popen(["sleep", "600"])
    spawned.append(stranger.pid)
    write_meta(city, "c" * 32, Meta(session="mc-a", pid=stranger.pid, pid_start=start_of(stranger.pid), boot=FAKE_BOOT))
    assert city.run("server-stop").code == 0
    assert alive(stranger.pid), "a start time from another boot names another process"


def test_stop_with_the_core_down_and_nothing_running_ends_the_orphans(city: City, spawned: List[int]) -> None:
    tok, other = token("srv-stop-a"), token("srv-stop-b")
    core_down(city)
    mine = subprocess.Popen(["sleep", "600"], env=dict(os.environ, GC_INSTANCE_TOKEN=tok), start_new_session=True)
    theirs = subprocess.Popen(["sleep", "600"], env=dict(os.environ, GC_INSTANCE_TOKEN=other), start_new_session=True)
    spawned.extend([mine.pid, theirs.pid])
    write_meta(city, "a" * 32, Meta(session="mc-a", values={"GC_INSTANCE_TOKEN": tok}))
    write_meta(city, "b" * 32, Meta(session="mc-b", values={"GC_INSTANCE_TOKEN": other}))
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    mine.wait(timeout=5)
    assert alive(theirs.pid), "stop ends only its own session's orphans"
    assert no_core_started(city)


def test_reads_and_stop_with_a_holder_running_but_the_core_down_cannot_tell(city: City, spawned: List[int]) -> None:
    core_down(city)
    start_holder(city, [{"argv": ["sleep", "600"]}], spawned)
    done = city.run("is-running", "mc-a")
    assert done.code == 1, "a holder's programs may run: the answer is unknown"
    assert "cannot read the city's core" in done.stderr
    stopped = city.run("stop", "mc-a")
    assert stopped.code == 1, "and stop cannot end what it cannot read"


class Unreadable(ProcSource):
    def snapshot(self) -> Dict[int, Proc]:
        raise ProcError("no /proc")

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        raise ProcError("no /proc")


def test_exit_1_when_the_process_table_cannot_be_read(city: City) -> None:
    core_down(city)
    city.procs.inner = Unreadable()
    done = city.run("server-stop")
    assert done.code == 1
    assert "may survive" in done.stderr and "process table" in done.stderr
    assert city.run("is-running", "mc-a").code == 1, "and is-running cannot tell either"


def test_exit_1_when_a_program_outlives_its_kill_without_the_core(city: City, spawned: List[int]) -> None:
    tok = token("srv-nocore-survivor")
    core_down(city)
    survivor = subprocess.Popen(["sleep", "600"], env=dict(os.environ, GC_INSTANCE_TOKEN=tok), start_new_session=True)
    spawned.append(survivor.pid)
    write_meta(city, "a" * 32, Meta(session="mc-a", values={"GC_INSTANCE_TOKEN": tok}))
    dropping = DropKills(city.procs.inner)
    dropping.spared.append(survivor.pid)
    city.procs.inner = dropping
    done = city.run("server-stop")
    assert done.code == 1
    assert str(survivor.pid) in done.stderr


def test_exit_1_when_the_core_runs_but_does_not_answer(city: City, spawned: List[int]) -> None:
    core_down(city)
    script = city.root / "herdr-core"
    script.write_text("import time\ntime.sleep(600)\n")
    wedged = subprocess.Popen(
        [sys.executable, str(script), "serve"],  # a core that never binds its socket
        env=dict(os.environ, HC_SOCKET=city.paths.socket),
    )
    spawned.append(wedged.pid)
    done = city.run("server-stop")
    assert done.code == 1
    assert "does not answer" in done.stderr and str(wedged.pid) in done.stderr
    running = city.run("is-running", "mc-a")
    assert running.code == 1, "a core that runs may run programs"


def test_server_stop_under_the_conformance_fault_cannot_tell(city: City) -> None:
    done = city.run("server-stop", extra={"GC_RPP_FAULT": "unavailable"})
    assert done.code == 1
    assert "may survive" in done.stderr


@pytest.mark.parametrize("fault", ["blocked", "lose_reply", "hold_send"])
def test_server_stop_under_an_input_fault_stops_the_city(city: City, fault: str) -> None:
    # Only ``unavailable`` stands in for a core that is down; the input faults
    # touch the driving calls, so server-stop still ends the city.
    assert city.start("mc-a", start_config("exec cat")).code == 0
    done = city.run("server-stop", extra={"GC_RPP_FAULT": fault})
    assert done.code == 0, done.stderr
    running = city.run("is-running", "mc-a")
    assert running.code == 0 and running.stdout.strip() == b"false", running.stderr


# --- a stopped city stays stopped -------------------------------------------------------------


def test_after_server_stop_reads_start_no_core_and_answer_an_empty_city(city: City) -> None:
    assert city.start("mc-a", start_config("exec cat")).code == 0
    assert city.run("server-stop").code == 0
    inventory = city.run("inventory")
    assert inventory.code == 0, inventory.stderr
    assert json.loads(inventory.stdout) == {"complete": True, "sessions": []}
    observed = city.run("observe", "mc-a", stdin=b"cat\n")
    assert json.loads(observed.stdout) == {"state": "absent"}
    listed = city.run("list-running")
    assert (listed.code, listed.text) == (0, ""), listed.stderr
    assert city.run("is-attached", "mc-a").text.strip() == "false"
    assert city.run("peek", "mc-a").code == 66
    assert city.run("is-running", "mc-a").text.strip() == "false"
    assert no_core_started(city, wait_s=2.0), "no read brings a stopped city's core back"


def test_a_core_down_server_stop_removes_the_records_hc_keeps(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    """hc keeps its records across a core restart. A server-stop that finds
    the core down starts it again and removes them, so the empty city its
    reads then answer is the truth: gc's next start of the name, which is
    always fresh_only, is not refused for a record they never showed."""
    assert city.start("mc-a", start_config("exec cat")).code == 0
    fake = city.fake
    assert fake is not None
    fake.crash()  # the core dies; its registry keeps the record for the next core
    starts: List[str] = []

    def start_again(ctx: object, hc_bin: str) -> None:
        starts.append(hc_bin)
        fake.start()  # the next core, with the registry the crashed one kept

    monkeypatch.setattr(server, "start_core", start_again)
    monkeypatch.setattr(core, "start_core", start_again)
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert core.parked(city.context())
    observed = city.run("observe", "mc-a", stdin=b"cat\n")
    assert json.loads(observed.stdout) == {"state": "absent"}
    fresh = city.start("mc-a", start_config("exec cat", fresh_only=True))
    assert fresh.code == 0, fresh.stderr  # 73 (a fresh start's name collision) with the record left
    assert [t["state"] for t in city.terminals()] == ["live"], "the old record is gone, the new one runs"
    assert len(starts) == 2, "server-stop started the core to remove what it keeps, and the start again"


def test_a_core_down_server_stop_that_cannot_start_the_core_leaves_the_city_unparked(
    city: City, monkeypatch: pytest.MonkeyPatch
) -> None:
    """While hc may keep a record of the city, a parked city's empty answer
    would hide it: a core that cannot be started is reported, and the city
    left unparked (one parked before too), so reads kick the core back."""
    assert city.start("mc-a", start_config("exec cat")).code == 0
    core_down(city)
    core.park(city.context())  # as an earlier core-down server-stop that kept the metadata left it

    def cannot_start(ctx: object, hc_bin: str) -> None:
        raise OpError("hc server start failed")

    monkeypatch.setattr(server, "start_core", cannot_start)
    done = city.run("server-stop")
    assert done.code == 1
    assert "records" in done.stderr and "hc server start failed" in done.stderr, done.stderr
    assert not core.parked(city.context())


def test_a_start_after_server_stop_lets_a_crashed_core_be_kicked_again(city: City) -> None:
    assert city.run("server-stop").code == 0
    city.fake = None
    assert city.start("mc-a", start_config("exec cat")).code == 0
    raw_call(city.paths.socket, "server.stop", {})  # the core ends without server-stop: a crash
    end = time.monotonic() + 10
    while os.path.exists(city.paths.socket) and time.monotonic() < end:
        time.sleep(0.05)
    inventory = city.run("inventory")
    assert json.loads(inventory.stdout)["complete"] is False
    end = time.monotonic() + 20
    while not os.path.exists(city.paths.socket) and time.monotonic() < end:
        time.sleep(0.05)
    assert os.path.exists(city.paths.socket), "a core that ended without server-stop is started again"


def test_a_core_that_ended_without_server_stop_is_still_kicked(city: City) -> None:
    core_down(city)
    inventory = city.run("inventory")
    assert json.loads(inventory.stdout)["complete"] is False
    end = time.monotonic() + 20
    while not os.path.exists(city.paths.socket) and time.monotonic() < end:
        time.sleep(0.05)
    assert os.path.exists(city.paths.socket)


def test_liveness_reads_of_a_crashed_core_with_nothing_running_answer_false_unparked(city: City) -> None:
    """is-running and process-alive ask only whether the name runs: with the
    core down and nothing of the city running (no holder, no core process),
    they answer false and kick no start, parked or not."""
    assert city.start("mc-a", start_config("exec cat")).code == 0
    core_down(city)  # the core and its programs end; nothing parks the city
    assert not core.parked(city.context())
    running = city.run("is-running", "mc-a")
    assert (running.code, running.text.strip()) == (0, "false"), running.stderr
    alive_answer = city.run("process-alive", "mc-a", stdin=b"cat\n")
    assert (alive_answer.code, alive_answer.text.strip()) == (0, "false"), alive_answer.stderr
    assert no_core_started(city, wait_s=2.0), "an answer that nothing runs starts no core"


def test_a_core_kept_for_a_foreign_terminal_is_not_parked(city: City) -> None:
    run_foreign(city, ["sleep", "600"])
    assert city.run("server-stop").code == 0
    assert not core.parked(city.context()), "a core kept for a foreign terminal is not parked"


# --- what the sweep without the core never touches -----------------------------------------------


def test_holders_of_other_sockets_survive_server_stop(city: City, spawned: List[int]) -> None:
    core_down(city)
    other_city = str(city.root / "other" / "hc.holder.0123abcd.sock")
    [elsewhere] = start_holder(city, [], spawned, socket=other_city)
    [unrelated] = start_holder(city, [], spawned, socket=str(city.root / "unrelated.sock"))
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert alive(elsewhere), "an idle holder of another core's socket survives"
    assert alive(unrelated), "a hold process whose socket is not a holder of the city's core survives"


def infrastructure(city: City, verb: str, tok: str, spawned: List[int]) -> List[int]:
    """A city-infrastructure stand-in (argv[1] is its verb) and its child,
    carrying the instance token ``tok``; returns their pids."""
    work = city.root / "infra"
    work.mkdir(exist_ok=True)
    (work / verb).write_text(PROXY)
    out = work / f"{verb}.pids"
    proc = subprocess.Popen(
        [sys.executable, verb, str(out)], cwd=work, env=dict(os.environ, GC_INSTANCE_TOKEN=tok), start_new_session=True
    )
    spawned.append(proc.pid)
    pids = [int(p) for p in wait_file(out).split()]
    spawned.extend(pids)
    return pids


@pytest.mark.parametrize("verb", [BD_PROXY_CHILD_VERB, MANAGED_DOLT_SCOPE_WATCHDOG_VERB])
def test_infrastructure_carrying_the_token_survives_stop_and_server_stop_without_the_core(
    city: City, spawned: List[int], verb: str
) -> None:
    tok = token(f"srv-infra-{verb}")
    core_down(city)
    fenced = infrastructure(city, verb, tok, spawned)
    agent = subprocess.Popen(["sleep", "600"], env=dict(os.environ, GC_INSTANCE_TOKEN=tok), start_new_session=True)
    spawned.append(agent.pid)
    write_meta(city, "a" * 32, Meta(session="mc-a", values={"GC_INSTANCE_TOKEN": tok}))
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    agent.wait(timeout=5)
    assert all(alive(pid) for pid in fenced), "stop never ends city infrastructure"
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert all(alive(pid) for pid in fenced), "nor does server-stop"


def test_a_pid_without_a_start_time_outside_the_citys_holders_is_never_taken(city: City, spawned: List[int]) -> None:
    core_down(city)
    stranger = subprocess.Popen(["sleep", "600"])
    spawned.append(stranger.pid)
    write_meta(city, "c" * 32, Meta(session="mc-a", pid=stranger.pid, pid_start=""))
    assert city.run("server-stop").code == 0
    assert alive(stranger.pid), "without a start time, only a city holder's program is taken for it"


def launcher(city: City, obj: str) -> Dict[str, object]:
    """A program still in the pack's launcher, whose spawn file names ``obj``."""
    script = city.root / LAUNCHER_NAME
    script.write_text("import time\ntime.sleep(600)\n")
    return {"argv": [sys.executable, str(script), str(city.root / "spawn" / f"{obj}.json")]}


def test_launchers_under_the_citys_holders(city: City, spawned: List[int]) -> None:
    core_down(city)
    mine, theirs = "a" * 32, "b" * 32
    holder, launching_mine, launching_theirs = start_holder(city, [launcher(city, mine), launcher(city, theirs)], spawned)
    write_meta(city, mine, Meta(session="mc-a"))
    write_meta(city, theirs, Meta(session="mc-b"))
    assert sweep_without_core(city.context(), session="mc-a", end_holders=False) == []
    assert wait_dead(launching_mine), "a session's own launcher under a city holder ends with it"
    assert alive(launching_theirs), "a single session's sweep leaves another session's launcher"
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert wait_dead(launching_theirs), "server-stop ends every launcher under a city holder"
    assert wait_dead(holder)


# --- what may survive is reported -------------------------------------------------------------------


def test_unreadable_metadata_with_the_core_answering_is_reported_and_kept(city: City, spawned: List[int]) -> None:
    work = city.root / "w"
    work.mkdir()
    tok = token("srv-unreadable")
    assert city.start("mc-a", start_config(f"(setsid sleep 600 & echo $! > {work}/daemon); exec cat", tok)).code == 0
    spawned.append(int(wait_file(work / "daemon")))
    meta_dir = Path(city.context().state_dir("meta"))
    [meta_file] = list(meta_dir.iterdir())
    meta_file.write_text("{not json")
    done = city.run("server-stop")
    assert done.code == 1
    assert "metadata" in done.stderr and "may survive" in done.stderr
    assert meta_file.exists(), "the metadata stays for a retry"
    assert [t["labels"]["gc.session"] for t in city.terminals()] == ["mc-a"]  # type: ignore[index]
    fake = city.fake
    assert fake is not None and fake.call_count("server.stop") == 0


class MarkOpaque(ProcSource):
    """The live process table, except that ``hidden`` read as opaque."""

    def __init__(self, inner: ProcSource) -> None:
        self.inner = inner
        self.hidden: List[int] = []

    def snapshot(self) -> Dict[int, Proc]:
        table = self.inner.snapshot()
        return {pid: dataclasses.replace(p, opaque=True) if pid in self.hidden else p for pid, p in table.items()}

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        return None if pid in self.hidden else self.inner.environ(pid)

    def boot(self) -> Optional[str]:
        return self.inner.boot()


def test_a_city_holder_running_a_process_that_cannot_be_read_may_survive(city: City, spawned: List[int]) -> None:
    core_down(city)
    holder, program = start_holder(city, [{"argv": ["sleep", "600"]}], spawned)
    hiding = MarkOpaque(city.procs.inner)
    hiding.hidden.append(program)
    city.procs.inner = hiding
    done = city.run("server-stop")
    assert done.code == 1
    assert "cannot be read" in done.stderr and str(holder) in done.stderr
    assert alive(holder) and alive(program)


def test_a_holder_program_with_an_incarnation_that_names_no_program_may_survive(city: City, spawned: List[int]) -> None:
    core_down(city)
    holder, program = start_holder(city, [{"argv": ["sleep", "600"]}], spawned)
    write_meta(city, "a" * 32, Meta(session="mc-a"))  # neither pid nor instance token
    done = city.run("server-stop")
    assert done.code == 1
    assert str(holder) in done.stderr
    assert alive(holder) and alive(program)


def test_a_core_of_the_session_on_another_socket_is_not_nothing_running(city: City, spawned: List[int]) -> None:
    listening = str(city.root / "elsewhere.sock")
    elsewhere = unix_socket.socket(unix_socket.AF_UNIX, unix_socket.SOCK_STREAM)
    elsewhere.bind(listening)
    elsewhere.listen(1)
    try:
        core_down(city)
        write_private_file(city.paths.core_lock, listening.encode())
        done = city.run("is-running", "mc-a")
        assert done.code == 1, "a core listening elsewhere may run the city's programs"
        stopped = city.run("server-stop")
        assert stopped.code == 1, "and server-stop cannot stop it"
        assert listening in stopped.stderr and "restart-core" in stopped.stderr, stopped.stderr
    finally:
        elsewhere.close()


def test_a_failure_to_record_the_program_keeps_the_start(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(self: Meta, pid: int, start: str, boot: str) -> Meta:
        raise MetaError("cannot write")

    monkeypatch.setattr(Meta, "with_program", broken)
    done = city.start("mc-a", start_config("exec cat"))
    assert done.code == 0, done.stderr
    assert city.run("is-running", "mc-a").text.strip() == "true"
    [record] = city.terminals()
    meta = MetaStore(city.context().state_dir("meta")).read(str(record["labels"]["gc.obj"]))  # type: ignore[index]
    assert meta is not None and meta.pid == 0


# --- the sweep fences tmux as every kill does (a fake /proc; nothing is signalled for real) ---------


class RecordingProcs(LinuxProcs):
    """A fake ``/proc`` whose kill is recorded, never sent: a signalled
    process leaves the fake tree as if it died; ``on_kill`` may add what the
    kill starts (a TERM handler's ``setsid`` child)."""

    def __init__(self, root: Path, on_kill: Optional[Callable[[int], None]] = None) -> None:
        LinuxProcs.__init__(self, str(root))
        self.root = root
        self.on_kill = on_kill
        self.signals: List[Tuple[int, int]] = []

    def kill(self, pid: int, sig: int) -> None:
        self.signals.append((pid, sig))
        shutil.rmtree(self.root / str(pid), ignore_errors=True)
        if self.on_kill is not None:
            self.on_kill(pid)

    def signalled(self) -> List[int]:
        return sorted({pid for pid, _ in self.signals})


def tmux_scene(city: City, root: Path, tok: str, *, holder: bool, pid: bool = True) -> None:
    """A box whose core was started from a pane of the operator's tmux
    server (100), its program 200 (with a child and a tmux client, and a
    daemon re-parented to init) under the city's holder 150 when ``holder``
    (else left under the pane), and three tmux servers carrying the box's
    token: one founded from inside the box (300, with the user's pane and
    editor) and another city's (500, with its agent). Its metadata keeps
    the program's pid and start time when ``pid``, else its token alone."""
    carry = {INSTANCE_TOKEN_KEY: tok}
    add_boot(root, FAKE_BOOT)
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 100, ppid=1, argv=["tmux"], comm="tmux: server")
    add_proc(root, 101, ppid=100, argv=["-zsh"], env=carry)  # the pane that ran gc in the box
    parent = 101
    if holder:
        add_proc(root, 150, ppid=101, argv=["hc", "hold", "--socket", holder_prefix(city.paths) + "0123abcd.sock"])
        parent = 150
    add_proc(root, 200, ppid=parent, argv=["cat"], env=carry, start=2000)  # the box's agent
    add_proc(root, 201, ppid=200, argv=["sleep", "600"], env=carry)
    add_proc(root, 205, ppid=200, argv=["tmux", "attach"], comm="tmux: client", env=carry)
    add_proc(root, 206, ppid=205, argv=["sleep", "600"], env=carry)
    add_proc(root, 210, ppid=1, argv=["sleep", "600"], env=carry)  # a daemon, re-parented
    add_proc(root, 300, ppid=1, argv=["tmux", "new", "-d"], comm="tmux: server", env=carry)
    add_proc(root, 301, ppid=300, argv=["-bash"], env=carry)  # the user's pane
    add_proc(root, 302, ppid=301, argv=["vim", "notes.md"], env=carry)  # and their editor
    add_proc(root, 500, ppid=1, argv=["/usr/bin/tmux", "-L", "city-t", "new-session", "-d"], comm="tmux: server", env=carry)
    add_proc(root, 501, ppid=500, argv=["claude"], env=carry)  # another city's agent
    if pid:
        write_meta(city, "a" * 32, Meta(session="mc-a", values=carry, pid=200, pid_start="2000", boot=FAKE_BOOT))
    else:
        write_meta(city, "a" * 32, Meta(session="mc-a", values=carry))


def test_server_stop_with_the_core_down_never_signals_tmux(city: City, tmp_path: Path) -> None:
    """A tmux server copies its founder's environment, so one founded from
    inside a box, and every pane and editor under it, carries the box's
    token; so does another city's server a gc command run in the box
    founded. server-stop's sweep fences them as ``stop``'s kill does; the
    box's own processes, and the holder left with none, still end."""
    tok = token("sweep-tmux-server-stop")
    root = tmp_path / "proc"
    tmux_scene(city, root, tok, holder=True)
    source = RecordingProcs(root)
    core_down(city)
    city.procs.inner = source
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert source.signalled() == [150, 200, 201, 210], source.signals
    assert core.parked(city.context()), "a core already down at teardown is parked too"


def test_a_holders_program_found_by_its_token_alone_is_a_root_of_the_kill(city: City, tmp_path: Path) -> None:
    """An incarnation whose metadata keeps no pid (its run's pid was never
    recorded) is found by its token: the city holder's program carrying it
    is the terminal's program, so the tmux server its core was started from
    fences none of its tree, as for one found by its pid."""
    tok = token("sweep-tmux-token-only")
    root = tmp_path / "proc"
    tmux_scene(city, root, tok, holder=True, pid=False)
    source = RecordingProcs(root)
    core_down(city)
    city.procs.inner = source
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert source.signalled() == [150, 200, 201, 210], source.signals


def test_stop_with_the_core_down_never_signals_tmux(city: City, tmp_path: Path) -> None:
    tok = token("sweep-tmux-stop")
    root = tmp_path / "proc"
    tmux_scene(city, root, tok, holder=False)
    source = RecordingProcs(root)
    core_down(city)
    city.procs.inner = source
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert source.signalled() == [200, 201, 210], source.signals


def test_the_sweeps_rescan_ends_what_the_kill_started_and_still_fences_tmux(city: City, tmp_path: Path) -> None:
    """A process the kill itself starts (a TERM handler's ``setsid`` child)
    was in no capture: the sweep scans for the token again, through the
    same fence, so a tmux server the handler founds is never signalled."""
    tok = token("sweep-rescan")
    carry = {INSTANCE_TOKEN_KEY: tok}
    root = tmp_path / "proc"
    add_boot(root, FAKE_BOOT)
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 200, ppid=1, argv=["cat"], env=carry, start=2000)
    write_meta(city, "a" * 32, Meta(session="mc-a", values=carry, pid=200, pid_start="2000", boot=FAKE_BOOT))

    def spawn(pid: int) -> None:
        if pid == 200:
            add_proc(root, 220, ppid=1, argv=["sleep", "600"], env=carry)
            add_proc(root, 230, ppid=1, argv=["tmux", "new", "-d"], comm="tmux: server", env=carry)

    source = RecordingProcs(root, on_kill=spawn)
    core_down(city)
    city.procs.inner = source
    assert sweep_without_core(city.context(), session="mc-a", end_holders=False, wait=lambda _: None) == []
    assert source.signalled() == [200, 220], source.signals


def test_server_stop_ends_only_launchers_whose_parent_is_a_city_holder(city: City, tmp_path: Path) -> None:
    """server-stop takes every launcher (``every``), but only one a city
    holder runs: another city's, or a stray process named like the
    launcher, is not the city's."""
    root = tmp_path / "proc"
    spawn = str(city.root / "spawn" / ("c" * 32 + ".json"))
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 150, ppid=1, argv=["hc", "hold", "--socket", holder_prefix(city.paths) + "0123abcd.sock"])
    add_proc(root, 151, ppid=150, argv=[sys.executable, LAUNCHER_NAME, spawn])
    add_proc(root, 400, ppid=1, argv=["hc", "hold", "--socket", "/elsewhere/hc.holder.0123abcd.sock"])
    add_proc(root, 401, ppid=400, argv=[sys.executable, LAUNCHER_NAME, spawn])
    add_proc(root, 402, ppid=1, argv=[sys.executable, LAUNCHER_NAME, spawn])
    source = RecordingProcs(root)
    core_down(city)
    city.procs.inner = source
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert source.signalled() == [150, 151], source.signals


def test_a_pid_kept_from_another_boot_never_names_a_holders_program(city: City, tmp_path: Path) -> None:
    """After a reboot a kept pid and start time name whatever runs under
    that pid now. Under a city holder that is a program no incarnation of
    the city started (it carries no instance token: a person's terminal on
    the city's core), left with its holder as a foreign program is, never
    taken for the incarnation's."""
    root = tmp_path / "proc"
    add_boot(root, FAKE_BOOT)
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 150, ppid=1, argv=["hc", "hold", "--socket", holder_prefix(city.paths) + "0123abcd.sock"])
    add_proc(root, 200, ppid=150, argv=["cat"], start=2000)
    carry = {INSTANCE_TOKEN_KEY: token("another-boot")}
    other_boot = "00000000-0000-4000-8000-000000000002"
    write_meta(city, "a" * 32, Meta(session="mc-a", values=carry, pid=200, pid_start="2000", boot=other_boot))
    source = RecordingProcs(root)
    core_down(city)
    city.procs.inner = source
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert source.signalled() == [], source.signals


def test_no_kick_while_parked_and_a_start_unparks_even_when_it_fails(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = city.context()
    core.park(ctx)
    assert not core.kick_due(ctx), "a parked city's reads kick no start"
    assert not core.kick(ctx)
    core_down(city)

    def cannot_start(ctx: object, hc_bin: str) -> None:
        raise OpError("hc server start failed")

    monkeypatch.setattr(core, "start_core", cannot_start)
    failed = city.start("mc-a", start_config("exec cat"))
    assert failed.code != 0
    assert not core.parked(city.context()), "a start is the way out of a parked city, whatever its core does"
    assert core.kick_due(city.context())


# --- a parked city is never stranded --------------------------------------------------------------


def wait_core_started(city: City, wait_s: float = 20.0) -> bool:
    end = time.monotonic() + wait_s
    while time.monotonic() < end:
        if os.path.exists(city.paths.socket):
            return True
        time.sleep(0.05)
    return False


def test_a_holder_left_running_by_a_core_down_server_stop_leaves_the_city_unparked(city: City, spawned: List[int]) -> None:
    """A holder still running a program server-stop could not attribute (an
    agent's background terminal, a person's) keeps the core's business
    open: gc reads unknown while it runs and so never sends a start. So the
    city is not left parked, and a read kicks the core back to adopt it."""
    core_down(city)
    holder, foreign = start_holder(city, [{"argv": ["sleep", "600"]}], spawned)
    done = city.run("server-stop")
    assert done.code == 0, done.stderr
    assert alive(holder) and alive(foreign)
    assert not core.parked(city.context()), "a core kept for a foreign program is not parked"
    city.fake = None
    assert json.loads(city.run("inventory").stdout)["complete"] is False
    assert wait_core_started(city), "a read kicks the core back"


def test_a_parked_city_with_a_holder_running_is_kicked(city: City, spawned: List[int]) -> None:
    """The escape from a park that outlived its server-stop (one killed at
    its deadline): while anything of the core runs, the mark does not stop
    a kick; it does once nothing runs."""
    core_down(city)
    ctx = city.context()
    core.park(ctx)
    assert not core.kick_due(ctx), "nothing runs: a parked city stays stopped"
    start_holder(city, [{"argv": ["sleep", "600"]}], spawned)
    assert core.kick_due(ctx), "a holder still runs: the core is kicked back for it"


def test_a_known_program_the_fence_keeps_is_reported_and_the_city_unparked(city: City, tmp_path: Path) -> None:
    """A box whose program is a tmux client is fenced, and with the core down
    nothing else can end it: server-stop names it, exits 1 and leaves the
    city unparked so the core comes back for it."""
    root = tmp_path / "proc"
    tok = token("sweep-fenced-program")
    carry = {INSTANCE_TOKEN_KEY: tok}
    add_boot(root, FAKE_BOOT)
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 150, ppid=1, argv=["hc", "hold", "--socket", holder_prefix(city.paths) + "0123abcd.sock"])
    add_proc(root, 200, ppid=150, argv=["tmux", "attach"], comm="tmux: client", env=carry, start=2000)
    write_meta(city, "a" * 32, Meta(session="mc-a", values=carry, pid=200, pid_start="2000", boot=FAKE_BOOT))
    source = RecordingProcs(root)
    core_down(city)
    city.procs.inner = source
    done = city.run("server-stop")
    assert done.code == 1
    assert "200" in done.stderr and "never signalled" in done.stderr, done.stderr
    assert source.signalled() == [], source.signals
    assert not core.parked(city.context())


def test_server_stop_waits_for_a_kick_in_flight(city: City, spawned: List[int]) -> None:
    """A kick that passed its park check before server-stop parked could
    start the core after server-stop's last look: server-stop holds the
    kick lock, so a kick in flight finishes first and none starts during it."""
    core_down(city)
    held = city.context().lock("kick", shared=False, wait_s=0.0)
    held.__enter__()
    try:
        blocked = city.run("server-stop", deadline_ms=1500)
        assert blocked.code == 1
        assert "a start of the city's core is in flight" in blocked.stderr, blocked.stderr
    finally:
        held.__exit__(None, None, None)
    releasing = city.context().lock("kick", shared=False, wait_s=0.0)
    releasing.__enter__()

    def release() -> None:
        time.sleep(0.5)
        releasing.__exit__(None, None, None)

    timer = in_thread(release)
    started = time.monotonic()
    done = city.run("server-stop")
    timer.join()
    assert done.code == 0, done.stderr
    assert time.monotonic() - started >= 0.4, "server-stop waited for the kick"
