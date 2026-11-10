"""stop and kill-object end the incarnation's whole process tree, never city
infrastructure, and find a broken incarnation's orphans by its instance
token. Real processes under fake-hc."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List

import pytest
from cityharness import City

from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcError

PROXY = """\
import os, subprocess, sys, time
child = subprocess.Popen(["sleep", "600"])
open(sys.argv[1] if len(sys.argv) > 1 else "proxy.pids", "w").write(f"{os.getpid()} {child.pid}")
time.sleep(600)
"""


def alive(pid: int) -> bool:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat[stat.rfind(")") + 2] != "Z"


def wait_file(path: Path, timeout: float = 10.0) -> str:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"{path} never written")


def wait_dead(pid: int, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not alive(pid):
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def leftovers() -> Iterator[List[int]]:
    pids: List[int] = []
    yield pids
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def proxy_dir(city: City) -> Path:
    """A fake bd proxy (argv[1] is its verb), which the agent starts in its
    own session as bd does, and which starts a child of its own."""
    workdir = city.root / "work"
    workdir.mkdir(exist_ok=True)
    (workdir / "db-proxy-child").write_text(PROXY)
    return workdir


def test_stop_kills_the_tree_but_not_fenced_infrastructure(city: City, leftovers: List[int]) -> None:
    work = proxy_dir(city)
    command = (
        f"cd {work}; setsid {sys.executable} db-proxy-child & "
        f"setsid sleep 600 & echo $! > {work}/detached.pid; "
        f"sleep 600 & echo $! > {work}/child.pid; exec cat"
    )
    assert city.start("mc-a", json.dumps({"command": command, "work_dir": str(work)})).code == 0
    proxy, proxy_child = (int(p) for p in wait_file(work / "proxy.pids").split())
    detached = int(wait_file(work / "detached.pid"))
    child = int(wait_file(work / "child.pid"))
    leftovers.extend([proxy, proxy_child, detached, child])
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(detached) and wait_dead(child)
    assert alive(proxy) and alive(proxy_child), "infrastructure and its subtree survive a session stop"


def test_holder_loss_orphans_are_found_by_instance_token(city: City, leftovers: List[int]) -> None:
    work = proxy_dir(city)
    env = {"GC_INSTANCE_TOKEN": "tok-orphan-scan-1", "GC_SESSION_ID": "s1"}
    command = (
        f"cd {work}; setsid {sys.executable} db-proxy-child & "
        f"setsid sleep 600 & echo $! > {work}/detached.pid; exec cat"
    )
    assert city.start("mc-a", json.dumps({"command": command, "work_dir": str(work), "env": env})).code == 0
    proxy, proxy_child = (int(p) for p in wait_file(work / "proxy.pids").split())
    detached = int(wait_file(work / "detached.pid"))
    leftovers.extend([proxy, proxy_child, detached])
    city.fake.lose_holder(city.address("mc-a"))  # type: ignore[union-attr]
    assert alive(detached), "a holder loss leaves the detached orphan behind"
    assert json.loads(city.run("observe", "mc-a").stdout)["state"] == "dead"
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(detached), "the orphan carried the incarnation's token"
    assert alive(proxy) and alive(proxy_child), "infrastructure is fenced even when it carries the token"


def test_another_incarnations_tree_is_never_scanned_away(city: City, leftovers: List[int]) -> None:
    work = city.root / "w2"
    work.mkdir()
    token = {"GC_INSTANCE_TOKEN": "tok-shared"}
    assert city.start("mc-b", json.dumps({"command": f"sleep 600 & echo $! > {work}/b.pid; exec cat", "env": token})).code == 0
    b_child = int(wait_file(work / "b.pid"))
    leftovers.append(b_child)
    assert city.start("mc-a", json.dumps({"command": "exec cat", "env": token})).code == 0
    city.fake.lose_holder(city.address("mc-a"))  # type: ignore[union-attr]
    assert city.run("stop", "mc-a").code == 0
    assert alive(b_child), "a live intact box's tree is protected"


def test_stop_without_a_process_table_still_stops_but_exits_1(city: City) -> None:
    class Broken(LinuxProcs):
        def snapshot(self) -> Dict[int, Proc]:
            raise ProcError("no /proc")

    assert city.start("mc-a", '{"command":"cat"}').code == 0
    city.procs.inner = Broken()
    done = city.run("stop", "mc-a")
    assert done.code == 1 and "descendants may survive" in done.stderr
    assert city.terminals() == []
    assert city.run("stop", "mc-a").code == 0


def test_descendants_die_even_when_hcs_kill_fails(city: City, leftovers: List[int]) -> None:
    work = city.root / "w3"
    work.mkdir()
    assert city.start("mc-a", json.dumps({"command": f"sleep 600 & echo $! > {work}/c.pid; exec cat"})).code == 0
    child = int(wait_file(work / "c.pid"))
    leftovers.append(child)
    city.fake.fail_next("terminal.kill", "internal")  # type: ignore[union-attr]
    done = city.run("stop", "mc-a")
    assert done.code == 1
    assert wait_dead(child), "the captured tree is killed whatever hc answered"


def test_nothing_under_an_opaque_process_is_signalled(city: City) -> None:
    from gc_runtime_herdr_core.herdrcore.lifecycle import kill_targets
    from gc_runtime_herdr_core.herdrcore.procs import Proc

    def p(pid: int, ppid: int, opaque: bool = False) -> Proc:
        return Proc(pid=pid, ppid=ppid, uid=os.getuid(), start="" if opaque else "1", comm="x", argv=() if opaque else ("x",), opaque=opaque)

    # 10 is the agent; 11 cannot be read (it may be infrastructure whose
    # command line hides); 12 is its readable child; 13 an ordinary child.
    snapshot = {10: p(10, 1), 11: p(11, 10, opaque=True), 12: p(12, 11), 13: p(13, 10)}
    signal, unsure = kill_targets(snapshot, list(snapshot.values()), keep=set())
    assert [x.pid for x in signal] == [10, 13]
    assert sorted(x.pid for x in unsure) == [11, 12]
