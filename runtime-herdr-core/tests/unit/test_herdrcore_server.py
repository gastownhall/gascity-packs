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
import time
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence

import pytest
from cityharness import City
from fakehc.rawclient import raw_call
from test_herdrcore_treekill import PROXY, alive, token, wait_dead, wait_file

from gc_runtime_herdr_core.herdrcore import core
from gc_runtime_herdr_core.herdrcore.config import write_private_file
from gc_runtime_herdr_core.herdrcore.corescan import holder_prefix
from gc_runtime_herdr_core.herdrcore.infra_argv import BD_PROXY_CHILD_VERB, MANAGED_DOLT_SCOPE_WATCHDOG_VERB
from gc_runtime_herdr_core.herdrcore.metastore import Meta, MetaError, MetaStore
from gc_runtime_herdr_core.herdrcore.procs import (
    LAUNCHER_NAME,
    LinuxProcs,
    Proc,
    ProcError,
    ProcSource,
)
from gc_runtime_herdr_core.herdrcore.server import sweep_without_core

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


def start_config(command: str, tok: str = "", work_dir: str = "") -> str:
    doc: Dict[str, object] = {"command": command}
    if tok:
        doc["env"] = {"GC_INSTANCE_TOKEN": tok}
    if work_dir:
        doc["work_dir"] = work_dir
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
    write_meta(city, "b" * 32, Meta(session="mc-b", pid=by_pid, pid_start=start_of(by_pid)))
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
    write_meta(city, "c" * 32, Meta(session="mc-a", pid=stranger.pid, pid_start="1"))
    assert city.run("server-stop").code == 0
    assert alive(stranger.pid), "another start time is another process"


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


def test_server_stop_parks_only_when_it_stopped_the_core(city: City) -> None:
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
    server = unix_socket.socket(unix_socket.AF_UNIX, unix_socket.SOCK_STREAM)
    server.bind(listening)
    server.listen(1)
    try:
        core_down(city)
        write_private_file(city.paths.core_lock, listening.encode())
        done = city.run("is-running", "mc-a")
        assert done.code == 1, "a core listening elsewhere may run the city's programs"
    finally:
        server.close()


def test_a_failure_to_record_the_program_keeps_the_start(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(self: Meta, pid: int, start: str) -> Meta:
        raise MetaError("cannot write")

    monkeypatch.setattr(Meta, "with_program", broken)
    done = city.start("mc-a", start_config("exec cat"))
    assert done.code == 0, done.stderr
    assert city.run("is-running", "mc-a").text.strip() == "true"
    [record] = city.terminals()
    meta = MetaStore(city.context().state_dir("meta")).read(str(record["labels"]["gc.obj"]))  # type: ignore[index]
    assert meta is not None and meta.pid == 0
