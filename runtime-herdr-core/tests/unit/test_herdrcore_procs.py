"""The process table: snapshots, gc's agent matching rules and the attach scan."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

import pytest
from cityharness import City
from fakehc.procfs import add_proc, add_thread

from gc_runtime_herdr_core.hc.parse import parse_terminal
from gc_runtime_herdr_core.hc.types import Terminal
from gc_runtime_herdr_core.herdrcore import attach
from gc_runtime_herdr_core.herdrcore.reads import agent_state
from gc_runtime_herdr_core.herdrcore.procs import (
    LinuxProcs,
    Proc,
    ProcError,
    expand_names,
    find_agent,
    matches,
    parse_environ,
    subtree,
)


needs_file_modes = pytest.mark.skipif(os.getuid() == 0, reason="root reads any file")


def proc(pid: int, argv: Tuple[str, ...], *, comm: str = "", ppid: int = 1, start: str = "1") -> Proc:
    return Proc(pid=pid, ppid=ppid, uid=os.getuid(), start=start, comm=comm or os.path.basename(argv[0]), argv=argv)


def hide(root: Path, pid: int) -> None:
    """Make ``pid`` read as ``hidepid=1`` shows a non-dumpable process of this user's."""
    for leaf in ("stat", "cmdline", "environ"):
        (root / str(pid) / leaf).chmod(0)


def box(pid: int) -> Terminal:
    """A live record whose program runs as ``pid``."""
    return parse_terminal(
        {
            "address": "t1",
            "labels": {"gc.session": "mc-a", "gc.pid": str(pid)},
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


def test_linux_snapshot_reads_stat_cmdline_and_environ(tmp_path: Path) -> None:
    add_proc(tmp_path, 10, ppid=1, argv=["/bin/sh", "-c", "x"], start=77)
    add_proc(tmp_path, 11, ppid=10, argv=["node", "/opt/claude/cli.js"], comm="node-MainThread", env={"A": "1", "B": "x=y"})
    (tmp_path / "self").mkdir()
    snap = LinuxProcs(str(tmp_path)).snapshot()
    assert set(snap) == {10, 11}
    assert snap[10].start == "77" and snap[11].ppid == 10
    assert snap[11].argv == ("node", "/opt/claude/cli.js") and snap[11].comm == "node-MainThread"
    assert LinuxProcs(str(tmp_path)).environ(11) == {"A": "1", "B": "x=y"}
    assert LinuxProcs(str(tmp_path)).environ(99) is None


def test_comm_with_spaces_and_parens_parses(tmp_path: Path) -> None:
    add_proc(tmp_path, 12, ppid=1, argv=["weird"], comm="a (b) c")
    assert LinuxProcs(str(tmp_path)).snapshot()[12].comm == "a (b) c"


def test_an_empty_proc_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ProcError):
        LinuxProcs(str(tmp_path)).snapshot()


@needs_file_modes
def test_an_unreadable_process_of_this_user_is_opaque_under_the_parent_listing_it(tmp_path: Path) -> None:
    add_proc(tmp_path, 10, ppid=1, argv=["node"], children=[])
    add_thread(tmp_path, 10, 13, [11])  # a child is listed by the thread that forked it
    add_proc(tmp_path, 11, ppid=10, argv=["claude"])
    (tmp_path / "12").mkdir()  # exited between the listing and the read
    hide(tmp_path, 11)
    snap = LinuxProcs(str(tmp_path)).snapshot()
    assert set(snap) == {10, 11} and not snap[10].opaque
    assert snap[11].opaque and snap[11].ppid == 10 and snap[11].argv == () and snap[11].comm == ""
    # Another user's is left out, as hidepid=1 hides every one.
    assert set(LinuxProcs(str(tmp_path), uid=os.getuid() + 1).snapshot()) == {10}


@needs_file_modes
def test_without_children_lists_an_unreadable_process_fails_the_snapshot(tmp_path: Path) -> None:
    add_proc(tmp_path, 10, ppid=1, argv=["/bin/sh"])
    add_proc(tmp_path, 11, ppid=10, argv=["claude"])
    hide(tmp_path, 11)
    # It cannot be placed, and a snapshot without it could judge a live agent dead.
    with pytest.raises(ProcError, match="cannot place pid 11"):
        LinuxProcs(str(tmp_path)).snapshot()


@needs_file_modes
def test_a_process_whose_children_cannot_be_read_is_opaque(tmp_path: Path) -> None:
    add_proc(tmp_path, 10, ppid=1, argv=["/bin/sh"], children=[11])
    add_proc(tmp_path, 11, ppid=10, argv=["ssh-agent"])
    add_proc(tmp_path, 20, ppid=1, argv=["/bin/sh"], children=[])
    hide(tmp_path, 11)
    (tmp_path / "20" / "task" / "20" / "children").chmod(0)
    snap = LinuxProcs(str(tmp_path)).snapshot()
    assert snap[20].opaque and snap[20].ppid == 1 and snap[20].argv == ("/bin/sh",)
    assert snap[11].ppid == 10 and not snap[10].opaque


@needs_file_modes
def test_an_opaque_process_outside_a_box_leaves_its_agent_answers(tmp_path: Path) -> None:
    add_proc(tmp_path, 5, ppid=1, argv=["systemd", "--user"], children=[20])
    add_proc(tmp_path, 20, ppid=5, argv=["ssh-agent"])
    add_proc(tmp_path, 10, ppid=1, argv=["/bin/sh"], children=[11])
    add_proc(tmp_path, 11, ppid=10, argv=["claude"])
    add_proc(tmp_path, 30, ppid=1, argv=["/bin/sh"], children=[])
    hide(tmp_path, 20)
    snap = LinuxProcs(str(tmp_path)).snapshot()
    assert agent_state(snap, box(10), ["claude"], None) == ("alive", "11")
    assert agent_state(snap, box(30), ["claude"], None) == ("dead", None)


@needs_file_modes
def test_an_opaque_process_in_a_box_makes_its_agent_cannot_tell_never_dead(tmp_path: Path) -> None:
    add_proc(tmp_path, 10, ppid=1, argv=["/bin/sh"], children=[20])
    add_proc(tmp_path, 20, ppid=10, argv=["claude"])
    add_proc(tmp_path, 30, ppid=1, argv=["/bin/sh"], children=[31])
    add_proc(tmp_path, 31, ppid=30, argv=["sudo-like"])
    add_proc(tmp_path, 32, ppid=31, argv=["claude"])
    hide(tmp_path, 20)
    hide(tmp_path, 31)
    snap = LinuxProcs(str(tmp_path)).snapshot()
    # The process that cannot be read may be the agent.
    assert agent_state(snap, box(10), ["claude"], None) == (None, None)
    # An agent below one is still found.
    assert agent_state(snap, box(30), ["claude"], None) == ("alive", "32")


def test_parse_environ() -> None:
    assert parse_environ(b"A=1\0B=\0=bad\0C=x=y\0") == {"A": "1", "B": "", "C": "x=y"}


@pytest.mark.parametrize(
    "argv, comm, names, want",
    [
        (("claude", "--x"), "claude", {"claude"}, True),
        (("/usr/bin/node", "/opt/x/claude.js"), "node-MainThread", {"claude"}, True),
        (("bun", "run", "--hot", "codex"), "bun", {"codex"}, True),
        (("npx", "-y", "x", "gemini"), "npx", {"gemini"}, True),  # x is a runner subcommand
        (("npx", "-y", "some-pkg", "gemini"), "npx", {"gemini"}, False),  # only the first script counts
        (("node", "server.js"), "node", {"claude"}, False),
        (("/home/u/.local/bin/kimi-code",), "kimi-code", {"kimi"}, True),
        (("/opt/bin/.gc-wrapped", "hook"), ".gc-wrapped", {"gc"}, True),
        (("python3", "agent.py"), "python3", {"agent"}, False),
    ],
)
def test_agent_matching_follows_gc(argv: Tuple[str, ...], comm: str, names: set, want: bool) -> None:  # type: ignore[type-arg]
    wanted = expand_names(names, gc_binary="/opt/bin/.gc-wrapped")
    assert matches(proc(5, argv, comm=comm), wanted) is want


def test_subtree_is_breadth_first() -> None:
    snap = {
        1: proc(1, ("sh",), ppid=0),
        2: proc(2, ("a",), ppid=1),
        3: proc(3, ("b",), ppid=2),
        4: proc(4, ("c",), ppid=1),
        5: proc(5, ("other",), ppid=0),
    }
    assert [p.pid for p in subtree(snap, 1)] == [1, 2, 4, 3]
    assert subtree(snap, 99) == []


def test_find_agent_looks_through_wrappers() -> None:
    snap = {
        1: proc(1, ("/bin/sh", "-c", "x"), ppid=0),
        2: proc(2, ("bash", "-lc", "y"), ppid=1),
        3: proc(3, ("node", "/x/claude.js"), comm="node-MainThread", ppid=2),
    }
    found = find_agent(snap, 1, expand_names(["claude"]))
    assert found is not None and found.pid == 3
    assert find_agent(snap, 1, expand_names(["codex"])) is None


# --- the attach scan ---------------------------------------------------------------------


def test_viewer_scan_counts_hc_attach_on_this_core_only(city: City, tmp_path: Path) -> None:
    root = tmp_path / "proc"
    mine = {"HC_SOCKET": city.paths.socket}
    add_proc(root, 41, ppid=1, argv=["/home/u/.local/bin/herdr-core", "attach", "t3"], env=mine)
    add_proc(root, 42, ppid=1, argv=["hc", "attach", "--observe", "gabc"], env={"HC_SESSION": city.paths.session})
    add_proc(root, 43, ppid=1, argv=["hc", "attach", "t9"], env={"HC_SOCKET": "/other.sock"})
    add_proc(root, 44, ppid=1, argv=["hc", "ls", "t5"], env=mine)
    snapshot = LinuxProcs(str(root)).snapshot()
    ctx = city.context()
    procs = city.procs.inner
    city.procs.inner = LinuxProcs(str(root))
    try:
        assert attach.viewer_targets(ctx, snapshot) == {"t3", "gabc"}
    finally:
        city.procs.inner = procs


def test_is_attached_while_the_packs_attach_holds_its_lock(city: City) -> None:
    import fcntl
    import json

    assert city.start("mc-a", '{"command":"cat"}').code == 0
    assert city.run("is-attached", "mc-a").text.strip() == "false"
    assert city.run("is-attached", "nobody").text.strip() == "false"
    obj = city.terminals()[0]["labels"]["gc.obj"]  # type: ignore[index]
    lock_path = city.context().attach_lock_path(str(obj))
    holder = subprocess.Popen(
        [sys.executable, "-c", "import fcntl, os, sys, time; fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600); fcntl.flock(fd, fcntl.LOCK_SH); print('held', flush=True); time.sleep(60)", lock_path],
        stdout=subprocess.PIPE,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline() == b"held\n"
        assert city.run("is-attached", "mc-a").text.strip() == "true"
        inventory = json.loads(city.run("inventory").stdout)
        assert inventory["sessions"][0]["attached"] is True
        obj_answer = json.loads(city.run("observe", "mc-a").stdout)["object"]
        corpse = city.run("kill-object", "mc-a", stdin=json.dumps({"object": obj_answer, "mode": "zombie"}).encode())
        assert corpse.text.strip() == "changed"
    finally:
        holder.kill()
        holder.wait()
    _ = fcntl


def test_is_attached_cannot_tell_without_a_process_table(city: City) -> None:
    class Broken(LinuxProcs):
        def snapshot(self) -> Dict[int, Proc]:
            raise ProcError("no /proc")

    assert city.start("mc-a", '{"command":"cat"}').code == 0
    city.procs.inner = Broken()
    done = city.run("is-attached", "mc-a")
    assert done.code == 1 and "cannot tell" in done.stderr


def test_an_attach_viewer_whose_environment_cannot_be_read_cannot_tell(city: City, tmp_path: Path) -> None:
    root = tmp_path / "proc"
    add_proc(root, 41, ppid=1, argv=["hc", "attach", "t3"])
    (root / "41" / "environ").chmod(0)
    snapshot = LinuxProcs(str(root)).snapshot()
    saved = city.procs.inner
    city.procs.inner = LinuxProcs(str(root))
    try:
        if os.getuid() == 0:
            pytest.skip("root reads any file")
        with pytest.raises(ProcError):
            attach.viewer_targets(city.context(), snapshot)
    finally:
        city.procs.inner = saved
        (root / "41" / "environ").chmod(0o600)


def test_a_viewer_that_exited_is_not_a_viewer(city: City, tmp_path: Path) -> None:
    root = tmp_path / "proc"
    add_proc(root, 41, ppid=1, argv=["hc", "attach", "t3"])
    snapshot = LinuxProcs(str(root)).snapshot()
    (root / "41" / "environ").unlink()
    saved = city.procs.inner
    city.procs.inner = LinuxProcs(str(root))
    try:
        assert attach.viewer_targets(city.context(), snapshot) == frozenset()
    finally:
        city.procs.inner = saved
