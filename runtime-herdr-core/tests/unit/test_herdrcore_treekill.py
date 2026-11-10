"""stop, kill-object and a failed start's rollback end the incarnation's
whole process tree, never city infrastructure, and find its re-parented
processes by its instance token, whether the box is live or not. Real
processes under fake-hc."""

from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, cast

import pytest
from cityharness import City

from fakehc.procfs import add_proc
from gc_runtime_herdr_core.hc.client import HcClient
from gc_runtime_herdr_core.hc.parse import parse_terminal
from gc_runtime_herdr_core.hc.types import Terminal
from gc_runtime_herdr_core.herdrcore.lifecycle import INSTANCE_TOKEN_KEY, RESCANS, kill_incarnation
from gc_runtime_herdr_core.herdrcore.metastore import Meta
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcError, subtree

PROXY = """\
import os, subprocess, sys, time
child = subprocess.Popen(["sleep", "600"])
open(sys.argv[1] if len(sys.argv) > 1 else "proxy.pids", "w").write(f"{os.getpid()} {child.pid}")
time.sleep(600)
"""

LATE = """\
import os, signal, subprocess, sys, time
def term(*_):
    child = subprocess.Popen(["sleep", "600"], start_new_session=True)  # outside hc's process groups
    open(os.path.join(sys.argv[1], "late.pid"), "w").write(str(child.pid))
    os._exit(0)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
signal.signal(signal.SIGTERM, term)
open(os.path.join(sys.argv[1], "ready"), "w").write("ready")
while True:
    time.sleep(1)
"""

RESPAWN = """\
import os, signal, subprocess, sys, time
work = sys.argv[1]
def term(*_):
    if not os.path.exists(os.path.join(work, "done")):
        # Blocked across the exec, a TERM sent before the next one's
        # handler is installed waits for it.
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        child = subprocess.Popen([sys.executable, __file__, work], start_new_session=True)
        with open(os.path.join(work, "pids"), "a") as out:
            out.write(f"{child.pid}\\n")
    os._exit(0)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
signal.signal(signal.SIGTERM, term)
signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
open(os.path.join(work, "ready"), "w").write("ready")
while True:
    time.sleep(1)
"""


def token(name: str) -> str:
    """An instance token no other run of these tests carries: the scan by
    token reads every process on the host."""
    return f"tok-{name}-{os.getpid()}"


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


def wait_outside(pid: int, root: int, timeout: float = 5.0) -> bool:
    """Whether ``pid`` leaves ``root``'s subtree (its parent exits) in time."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pid not in {p.pid for p in subtree(LinuxProcs().snapshot(), root)}:
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


class _RecordingProcs(LinuxProcs):
    """A fake ``/proc`` whose kill is recorded, never sent: a signalled
    process leaves the fake tree as if it died."""

    def __init__(self, root: Path) -> None:
        LinuxProcs.__init__(self, str(root))
        self.root = root
        self.signals: List[Tuple[int, int]] = []

    def kill(self, pid: int, sig: int) -> None:
        self.signals.append((pid, sig))
        shutil.rmtree(self.root / str(pid), ignore_errors=True)


class _RecordingClient:
    """The hc calls a kill makes, recorded."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, str]] = []

    def kill(self, address: str) -> None:
        self.calls.append(("kill", address))

    def remove(self, address: str) -> None:
        self.calls.append(("remove", address))


def _live_box(pid: int) -> Terminal:
    return parse_terminal(
        {
            "address": "t1",
            "labels": {"gc.session": "mc-a", "gc.pid": str(pid), "gc.obj": "o1"},
            "argv": ["/bin/sh"],
            "cwd": "/",
            "state": "live",
            "created_ms": 1_700_000_000_000,
            "screen": "exact",
            "cols": 80,
            "rows": 24,
            "pid": pid,
            "reason": None,
            "keep": False,
        }
    )


def test_stop_never_signals_a_tmux_server_or_client_carrying_the_token(city: City, tmp_path: Path) -> None:
    """A tmux server copies its founder's environment, so one founded from
    inside the box (``tmux new -d``), and every pane and editor under it,
    carries the box's instance token; so does another city's server that a
    gc command run in the box founded. gc never signals tmux (its scanner
    never reports a tmux server or client as a root): neither does the
    kill. The box's own tree still dies, also when hc's core was started
    from a tmux pane. A fake ``/proc``; nothing is signalled for real."""
    tok = token("tmux-fence")
    carry = {"GC_INSTANCE_TOKEN": tok}
    root = tmp_path / "proc"
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 100, ppid=1, argv=["tmux"], comm="tmux: server")  # the operator's, hc's core started in it
    add_proc(root, 101, ppid=100, argv=["-zsh"], env=carry)  # a pane of it that ran gc in the box
    add_proc(root, 150, ppid=100, argv=["herdr-core", "server"])
    add_proc(root, 200, ppid=150, argv=["cat"], env=carry)  # the box's agent
    add_proc(root, 201, ppid=200, argv=["sleep", "600"], env=carry)
    add_proc(root, 205, ppid=200, argv=["tmux", "attach"], comm="tmux: client", env=carry)
    add_proc(root, 206, ppid=205, argv=["sleep", "600"], env=carry)
    add_proc(root, 210, ppid=1, argv=["sleep", "600"], env=carry)  # a daemon, re-parented
    add_proc(root, 300, ppid=1, argv=["tmux", "new", "-d"], comm="tmux: server", env=carry)
    add_proc(root, 301, ppid=300, argv=["-bash"], env=carry)  # the user's pane
    add_proc(root, 302, ppid=301, argv=["vim", "notes.md"], env=carry)  # and their editor
    add_proc(root, 500, ppid=1, argv=["/usr/bin/tmux", "-L", "city-t", "new-session", "-d"], comm="tmux: server", env=carry)
    add_proc(root, 501, ppid=500, argv=["claude"], env=carry)  # another city's agent
    source = _RecordingProcs(root)
    client = _RecordingClient()
    city.procs.inner = source
    meta = Meta(session="mc-a").with_value(INSTANCE_TOKEN_KEY, tok)
    problems = kill_incarnation(city.context(), cast(HcClient, client), _live_box(200), meta, pause=lambda _: None)
    assert problems == []
    assert sorted(pid for pid, _ in source.signals) == [200, 201, 210], source.signals
    assert client.calls == [("kill", "t1"), ("remove", "t1")]


def test_a_rollback_reads_the_record_afresh_before_it_captures_a_tree(city: City, tmp_path: Path) -> None:
    """run's reply may be seconds old by the rollback: a pid that ended since
    may run an unrelated process, whose tree is never captured."""
    import dataclasses

    from gc_runtime_herdr_core.herdrcore import lifecycle
    from gc_runtime_herdr_core.herdrcore.records import object_of

    assert city.start("mc-a", json.dumps({"command": "exec cat"})).code == 0
    ctx = city.context()
    record = ctx.client().get(city.address("mc-a"))
    obj = object_of(record)
    assert obj is not None
    root = tmp_path / "proc"
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 777, ppid=1, argv=["unrelated"])  # the stale pid, recycled
    add_proc(root, 778, ppid=777, argv=["sleep", "600"])
    source = _RecordingProcs(root)
    city.procs.inner = source
    lifecycle._undo(ctx, dataclasses.replace(record, pid=777), obj, pending=False)
    assert source.signals == []
    assert city.terminals() == []


def test_holder_loss_orphans_are_found_by_instance_token(city: City, leftovers: List[int]) -> None:
    work = proxy_dir(city)
    env = {"GC_INSTANCE_TOKEN": token("orphan-scan"), "GC_SESSION_ID": "s1"}
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


@pytest.mark.parametrize("op", ["stop", "kill-object"])
def test_a_live_agents_daemon_is_found_by_its_token(city: City, leftovers: List[int], op: str) -> None:
    work = city.root / "w7"
    work.mkdir()
    env = {"GC_INSTANCE_TOKEN": token(f"daemon-{op}")}
    # The subshell exits once it started the daemon, which is re-parented out
    # of the agent's subtree while the agent, cat, still runs.
    command = f"(setsid sleep 600 & echo $! > {work}/daemon.pid); exec cat"
    assert city.start("mc-a", json.dumps({"command": command, "env": env})).code == 0
    daemon = int(wait_file(work / "daemon.pid"))
    leftovers.append(daemon)
    [record] = city.terminals()
    assert record["state"] == "live" and wait_outside(daemon, int(str(record["pid"]))) and alive(daemon)
    if op == "stop":
        done = city.run("stop", "mc-a")
    else:  # the agent reads dead while the box's program runs on
        assert city.run("set-meta", "mc-a", "GT_PROCESS_NAMES", stdin=b"not-running").code == 0
        obj = json.loads(city.run("observe", "mc-a").stdout)["object"]
        done = city.run("kill-object", "mc-a", stdin=json.dumps({"object": obj, "mode": "zombie"}).encode())
        assert done.text.strip() == "killed", done.stderr
    assert done.code == 0, done.stderr
    assert wait_dead(daemon), "a live box's daemon carried the incarnation's token"
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_a_canceled_starts_rollback_finds_its_daemon_by_its_token(city: City, leftovers: List[int]) -> None:
    from cityharness import in_thread

    from gc_runtime_herdr_core.rpp.cancel import CancelToken

    work = city.root / "w8"
    work.mkdir()
    env = {"GC_INSTANCE_TOKEN": token("rollback")}
    command = f"(setsid sleep 600 & echo $! > {work}/daemon.pid); exec cat"
    city.fake.delay_reply("terminal.label", 10.0)  # type: ignore[union-attr]
    cancel = CancelToken()
    results = []
    stdin = json.dumps({"command": command, "env": env}).encode()
    thread = in_thread(lambda: results.append(city.run("start", "mc-a", stdin=stdin, cancel=cancel)))
    daemon = int(wait_file(work / "daemon.pid"))
    leftovers.append(daemon)
    [record] = city.terminals()
    assert wait_outside(daemon, int(str(record["pid"])))
    end = time.monotonic() + 5
    while not city.fake.call_count("terminal.label"):  # type: ignore[union-attr]
        assert time.monotonic() < end, "the start never labelled its terminal"
        time.sleep(0.05)
    cancel.cancel("terminated")  # while the start waits for its label
    thread.join(timeout=20)
    assert results and results[0].code == 1
    assert wait_dead(daemon), "a canceled start's daemon carried the incarnation's token"
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_another_incarnations_tree_is_never_scanned_away(city: City, leftovers: List[int]) -> None:
    work = city.root / "w2"
    work.mkdir()
    shared = {"GC_INSTANCE_TOKEN": token("shared")}
    assert city.start("mc-b", json.dumps({"command": f"sleep 600 & echo $! > {work}/b.pid; exec cat", "env": shared})).code == 0
    b_child = int(wait_file(work / "b.pid"))
    leftovers.append(b_child)
    assert city.start("mc-a", json.dumps({"command": "exec cat", "env": shared})).code == 0
    city.fake.lose_holder(city.address("mc-a"))  # type: ignore[union-attr]
    assert city.run("stop", "mc-a").code == 0
    assert alive(b_child), "a live intact box's tree is protected"


def test_a_failed_starts_rollback_never_scans_another_incarnations_tree_away(city: City, leftovers: List[int]) -> None:
    work = city.root / "w9"
    work.mkdir()
    shared = {"GC_INSTANCE_TOKEN": token("shared-rollback")}
    assert city.start("mc-b", json.dumps({"command": f"sleep 600 & echo $! > {work}/b.pid; exec cat", "env": shared})).code == 0
    b_child = int(wait_file(work / "b.pid"))
    leftovers.append(b_child)
    city.fake.fail_next("terminal.label", "internal")  # type: ignore[union-attr]
    assert city.start("mc-a", json.dumps({"command": "exec cat", "env": shared})).code == 1
    assert alive(b_child), "a live intact box's tree is protected from a rollback too"
    assert [(t["address"], t["state"]) for t in city.terminals()] == [(city.address("mc-b"), "live")]


def test_a_rollback_that_cannot_list_the_city_still_ends_the_created_tree(city: City, leftovers: List[int]) -> None:
    """hc fails the rollback's list of the city's boxes, so another box
    carrying the token cannot be told from this one: the created tree dies,
    nothing is looked for by the token, and the box keeps its token for
    gc's stop, which finds the daemon."""
    from cityharness import in_thread

    from gc_runtime_herdr_core.rpp.cancel import CancelToken

    work = city.root / "w12"
    work.mkdir()
    shared = {"GC_INSTANCE_TOKEN": token("unlisted")}
    assert city.start("mc-b", json.dumps({"command": f"sleep 600 & echo $! > {work}/b.pid; exec cat", "env": shared})).code == 0
    b_child = int(wait_file(work / "b.pid"))
    leftovers.append(b_child)
    labelled = city.fake.call_count("terminal.label")  # type: ignore[union-attr]
    command = f"(setsid sleep 600 & echo $! > {work}/daemon.pid); sleep 600 & echo $! > {work}/child.pid; exec cat"
    city.fake.delay_reply("terminal.label", 10.0)  # type: ignore[union-attr]
    cancel = CancelToken()
    results = []
    stdin = json.dumps({"command": command, "env": shared}).encode()
    thread = in_thread(lambda: results.append(city.run("start", "mc-a", stdin=stdin, cancel=cancel)))
    daemon = int(wait_file(work / "daemon.pid"))
    child = int(wait_file(work / "child.pid"))
    leftovers.extend([daemon, child])
    a_box, b_box = city.address("mc-a"), city.address("mc-b")
    [agent] = [int(str(t["pid"])) for t in city.terminals() if t["address"] == a_box]
    assert wait_outside(daemon, agent)
    end = time.monotonic() + 5
    while city.fake.call_count("terminal.label") == labelled:  # type: ignore[union-attr]
        assert time.monotonic() < end, "the start never labelled its terminal"
        time.sleep(0.05)
    city.fake.fail_next("terminal.list", "internal")  # type: ignore[union-attr]
    cancel.cancel("terminated")  # while the start waits for its label
    thread.join(timeout=20)
    assert results and results[0].code == 1
    assert wait_dead(agent) and wait_dead(child), "the created tree dies without the city's list"
    assert alive(b_child) and alive(daemon), "nothing is looked for by the token without the list"
    assert sorted(str(t["address"]) for t in city.terminals()) == sorted([a_box, b_box]), "the box stays"
    assert len(list(Path(city.context().state_dir("meta")).iterdir())) == 2, "and so does its token"
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(daemon), "gc's stop found the daemon by the token the box kept"
    assert alive(b_child)
    assert [t["address"] for t in city.terminals()] == [b_box]
    assert len(list(Path(city.context().state_dir("meta")).iterdir())) == 1


def test_a_rollback_that_cannot_read_the_created_record_still_ends_its_tree(city: City, leftovers: List[int]) -> None:
    """hc fails the rollback's fresh read of the created record (its core
    went away during the label call): the created tree still dies, from the
    record run gave, and the box keeps its token for gc's stop."""
    from cityharness import in_thread

    from gc_runtime_herdr_core.rpp.cancel import CancelToken

    work = city.root / "w13"
    work.mkdir()
    env = {"GC_INSTANCE_TOKEN": token("unread")}
    command = f"(setsid sleep 600 & echo $! > {work}/daemon.pid); sleep 600 & echo $! > {work}/child.pid; exec cat"
    city.fake.delay_reply("terminal.label", 10.0)  # type: ignore[union-attr]
    cancel = CancelToken()
    results = []
    stdin = json.dumps({"command": command, "env": env}).encode()
    thread = in_thread(lambda: results.append(city.run("start", "mc-a", stdin=stdin, cancel=cancel)))
    daemon = int(wait_file(work / "daemon.pid"))
    child = int(wait_file(work / "child.pid"))
    leftovers.extend([daemon, child])
    [record] = city.terminals()
    agent = int(str(record["pid"]))
    end = time.monotonic() + 5
    while not city.fake.call_count("terminal.label"):  # type: ignore[union-attr]
        assert time.monotonic() < end, "the start never labelled its terminal"
        time.sleep(0.05)
    city.fake.fail_next("terminal.get", "internal")  # type: ignore[union-attr]
    cancel.cancel("terminated")  # while the start waits for its label
    thread.join(timeout=20)
    assert results and results[0].code == 1
    assert wait_dead(agent) and wait_dead(child), "the created tree dies though hc cannot read its record"
    assert [t["address"] for t in city.terminals()] == [city.address("mc-a")], "the box stays"
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(daemon), "gc's stop found the daemon by the token the box kept"
    assert city.terminals() == []


def _boot(root: Path, created_ms: int, *, offset_ticks: int) -> None:
    """A fake ``/proc/stat`` whose boot time puts starttime ``offset_ticks``
    (in clock ticks) at ``created_ms``."""
    tick = os.sysconf("SC_CLK_TCK")
    btime = (created_ms // 1000) - offset_ticks // tick
    root.mkdir(parents=True, exist_ok=True)
    (root / "stat").write_text(f"cpu  0 0 0 0\nbtime {btime}\n")


@pytest.mark.parametrize("stale", [False, True])
def test_a_rollback_without_hc_ends_only_the_box_that_started_at_its_creation(city: City, tmp_path: Path, stale: bool) -> None:
    """With hc failing, the rollback ends the created tree from run's reply:
    a pid that started well after the terminal was created is a recycled
    one, and is never signalled."""
    from gc_runtime_herdr_core.herdrcore import lifecycle

    record = _live_box(777)
    root = tmp_path / "proc"
    tick = os.sysconf("SC_CLK_TCK")
    _boot(root, record.created_ms, offset_ticks=1000 - (60 * tick if stale else 0))
    add_proc(root, 1, ppid=0, argv=["/sbin/init"])
    add_proc(root, 777, ppid=1, argv=["cat"], start=1000)
    add_proc(root, 778, ppid=777, argv=["sleep", "600"], start=1001)
    source = _RecordingProcs(root)
    city.procs.inner = source
    lifecycle._reap_trees(city.context(), [record])
    assert sorted(pid for pid, _ in source.signals) == ([] if stale else [777, 778])


def test_a_child_the_kill_itself_starts_dies_too(city: City, leftovers: List[int]) -> None:
    """The agent ignores HUP, and its TERM handler starts a child in a new
    session: that child was in no capture and is outside hc's process
    groups, so only a scan for the token after the kill finds it."""
    work = city.root / "w10"
    work.mkdir()
    (work / "agent.py").write_text(LATE)
    env = {"GC_INSTANCE_TOKEN": token("late")}
    assert city.start("mc-a", json.dumps({"command": f"exec {sys.executable} {work}/agent.py {work}", "env": env})).code == 0
    wait_file(work / "ready")
    done = city.run("stop", "mc-a")
    late = int(wait_file(work / "late.pid"))
    leftovers.append(late)
    assert done.code == 0, done.stderr
    assert wait_dead(late), "the child carried the incarnation's token"
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_a_daemon_that_keeps_respawning_keeps_the_box_for_the_retry(city: City, leftovers: List[int]) -> None:
    """Each TERM starts the next one in a new session: the kill stops after
    its last round, and the box and its token stay for gc's retry."""
    work = city.root / "w11"
    work.mkdir()
    (work / "agent.py").write_text(RESPAWN)
    env = {"GC_INSTANCE_TOKEN": token("respawn")}
    assert city.start("mc-a", json.dumps({"command": f"exec {sys.executable} {work}/agent.py {work}", "env": env})).code == 0
    wait_file(work / "ready")
    done = city.run("stop", "mc-a")
    born = [int(pid) for pid in (work / "pids").read_text().split()]
    leftovers.extend(born)
    assert len(born) == RESCANS + 1, "one started by hc's kill, then one by each round"
    assert done.code == 1 and f"still respawning after the kill: {born[-1]}" in done.stderr, done.stderr
    assert alive(born[-1])
    assert len(city.terminals()) == 1, "the box stays for the retry"
    assert len(list(Path(city.context().state_dir("meta")).iterdir())) == 1, "and so does its token"
    (work / "done").write_text("done")
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(born[-1]), "the retry found the last one by the token the box kept"
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_a_stop_that_may_leave_survivors_keeps_the_box_and_its_token_for_the_retry(city: City, leftovers: List[int]) -> None:
    class Broken(LinuxProcs):
        def snapshot(self) -> Dict[int, Proc]:
            raise ProcError("no /proc")

    work = city.root / "w4"
    work.mkdir()
    env = {"GC_INSTANCE_TOKEN": token("retry-1")}
    command = f"setsid sleep 600 & echo $! > {work}/detached.pid; exec cat"
    assert city.start("mc-a", json.dumps({"command": command, "env": env})).code == 0
    detached = int(wait_file(work / "detached.pid"))
    leftovers.append(detached)
    readable = city.procs.inner
    city.procs.inner = Broken()
    done = city.run("stop", "mc-a")
    assert done.code == 1 and "descendants may survive" in done.stderr
    assert alive(detached), "hc's kill ends the program's process groups, not a detached child"
    assert len(city.terminals()) == 1, "the box stays for the retry"
    again = city.start("mc-a", json.dumps({"command": "cat", "env": {"GC_INSTANCE_TOKEN": token("retry-2")}}))
    assert again.code == 1 and "may survive" in again.stderr, "no replacement runs beside a survivor"
    city.procs.inner = readable
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(detached), "the retry found the survivor by the token the box kept"
    assert city.terminals() == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


def test_starts_refused_over_survivors_go_ahead_after_the_limit(
    city: City, leftovers: List[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A survivor that never goes away (one unkillable, one respawned from
    outside the kill, a process table that never reads) refuses starts
    only until the limit: then the start warns, naming it, and goes ahead."""
    from gc_runtime_herdr_core.herdrcore import lifecycle

    class Broken(LinuxProcs):
        def snapshot(self) -> Dict[int, Proc]:
            raise ProcError("no /proc")

    work = city.root / "w13"
    work.mkdir()
    command = f"setsid sleep 600 & echo $! > {work}/detached.pid; exec cat"
    assert city.start("mc-a", json.dumps({"command": command, "env": {"GC_INSTANCE_TOKEN": token("limit-1")}})).code == 0
    leftovers.append(int(wait_file(work / "detached.pid")))
    city.procs.inner = Broken()
    assert city.run("stop", "mc-a").code == 1
    again = json.dumps({"command": "exec cat", "env": {"GC_INSTANCE_TOKEN": token("limit-2")}})
    refused = city.start("mc-a", again)
    assert refused.code == 1 and "may survive" in refused.stderr, refused.stderr
    assert "15 minutes after the first refusal, the start goes ahead beside them" in refused.stderr
    assert len(city.terminals()) == 1
    monkeypatch.setattr(lifecycle, "START_REFUSAL_LIMIT_MS", 0)
    done = city.start("mc-a", again)
    assert done.code == 0, done.stderr
    assert "beside an earlier incarnation's processes" in done.stderr and "cannot read the process table" in done.stderr
    [record] = city.terminals()
    assert record["state"] == "live", "only the new incarnation's box is left"
    assert len(list(Path(city.context().state_dir("meta")).iterdir())) == 1


def test_a_refused_record_without_metadata_is_not_refused_forever(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no metadata to record the first refusal in, the limit counts
    from the record's creation."""
    from gc_runtime_herdr_core.herdrcore import lifecycle

    class Broken(LinuxProcs):
        def snapshot(self) -> Dict[int, Proc]:
            raise ProcError("no /proc")

    assert city.start("mc-a", json.dumps({"command": "exec cat"})).code == 0
    for meta in Path(city.context().state_dir("meta")).iterdir():
        meta.unlink()
    city.procs.inner = Broken()
    assert city.run("stop", "mc-a").code == 1
    monkeypatch.setattr(lifecycle, "START_REFUSAL_LIMIT_MS", 0)
    done = city.start("mc-a", json.dumps({"command": "exec cat"}))
    assert done.code == 0, done.stderr
    assert "beside an earlier incarnation's processes" in done.stderr
    [record] = city.terminals()
    assert record["state"] == "live"


def test_a_normally_exited_agents_detached_child_is_found_by_its_token(city: City, leftovers: List[int]) -> None:
    work = city.root / "w5"
    work.mkdir()
    env = {"GC_INSTANCE_TOKEN": token("exited")}
    command = f"setsid sleep 600 & echo $! > {work}/detached.pid; exit 0"
    assert city.start("mc-a", json.dumps({"command": command, "env": env, "lifecycle": "one_shot"})).code == 0
    detached = int(wait_file(work / "detached.pid"))
    leftovers.append(detached)
    end = time.monotonic() + 5
    while json.loads(city.run("observe", "mc-a").stdout)["state"] != "dead":
        assert time.monotonic() < end, "the agent never exited"
        time.sleep(0.05)
    assert [t["reason"] for t in city.terminals()] == ["exited"]
    done = city.run("stop", "mc-a")
    assert done.code == 0, done.stderr
    assert wait_dead(detached), "an exited record's tree is found by its token"
    assert city.terminals() == []


def test_a_corpse_kill_that_leaves_a_survivor_keeps_the_box_for_the_retry(city: City, leftovers: List[int]) -> None:
    work = city.root / "w6"
    work.mkdir()
    env = {"GC_INSTANCE_TOKEN": token("corpse")}
    command = f"setsid sleep 600 & echo $! > {work}/detached.pid; exit 0"
    assert city.start("mc-a", json.dumps({"command": command, "env": env, "lifecycle": "one_shot"})).code == 0
    detached = int(wait_file(work / "detached.pid"))
    leftovers.append(detached)

    class Unkillable(LinuxProcs):
        def kill(self, pid: int, sig: int) -> None:
            if pid != detached:
                LinuxProcs.kill(self, pid, sig)

    end = time.monotonic() + 5
    while json.loads(city.run("observe", "mc-a").stdout)["state"] != "dead":
        assert time.monotonic() < end, "the agent never exited"
        time.sleep(0.05)
    obj = json.loads(city.run("observe", "mc-a").stdout)["object"]
    request = json.dumps({"object": obj, "mode": "corpse"}).encode()
    readable = city.procs.inner
    city.procs.inner = Unkillable()
    done = city.run("kill-object", "mc-a", stdin=request)
    assert done.code == 1 and f"still running: {detached}" in done.stderr
    assert alive(detached) and len(city.terminals()) == 1
    city.procs.inner = readable
    done = city.run("kill-object", "mc-a", stdin=request)
    assert done.code == 0 and done.text.strip() == "killed", done.stderr
    assert wait_dead(detached) and city.terminals() == []


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
