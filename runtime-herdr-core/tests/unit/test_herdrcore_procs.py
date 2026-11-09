"""The process table: snapshots, gc's agent matching rules and the attach scan."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

import pytest
from cityharness import City
from fakehc.procfs import add_proc

from gc_runtime_herdr_core.herdrcore import attach
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


def proc(pid: int, argv: Tuple[str, ...], *, comm: str = "", ppid: int = 1, start: str = "1") -> Proc:
    return Proc(pid=pid, ppid=ppid, uid=os.getuid(), start=start, comm=comm or os.path.basename(argv[0]), argv=argv)


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
