"""server-stop (server-lifecycle): the city's core and every session the pack
started for the city end with it; a foreign terminal survives; with the core
not answering, its holders' programs and the incarnations' orphans are found
in the process table; exit 1 whenever a program of the city may survive; a
second call exits 0. Real processes under an in-process fake-hc, and real
stand-in holder processes."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence

import pytest
from cityharness import City
from fakehc.rawclient import raw_call
from test_herdrcore_treekill import alive, token, wait_dead, wait_file

from gc_runtime_herdr_core.herdrcore.corescan import holder_prefix
from gc_runtime_herdr_core.herdrcore.metastore import Meta, MetaStore
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcError, ProcSource

HOLDER = """\
import json, os, signal, subprocess, sys, time
# argv: hold --socket <socket> <spec file> <pid file>
spec, out = sys.argv[4], sys.argv[5]
children = []
for program in json.load(open(spec)):
    env = dict(os.environ)
    env.update(program.get("env", {}))
    children.append(subprocess.Popen(program["argv"], env=env).pid)
open(out + ".tmp", "w").write(" ".join(str(pid) for pid in children))
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


def start_holder(city: City, programs: List[Dict[str, object]], spawned: List[int]) -> List[int]:
    """A stand-in holder of the city's core (``hold --socket <holder socket>``)
    running ``programs``; returns their pids."""
    script = city.root / "holder.py"
    script.write_text(HOLDER)
    spec = city.root / f"programs-{len(spawned)}.json"
    spec.write_text(json.dumps(programs))
    out = city.root / f"programs-{len(spawned)}.pids"
    socket = holder_prefix(city.paths) + "0123abcd.sock"
    holder = subprocess.Popen([sys.executable, str(script), "hold", "--socket", socket, str(spec), str(out)])
    spawned.append(holder.pid)
    pids = [int(p) for p in wait_file(out).split()]
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
