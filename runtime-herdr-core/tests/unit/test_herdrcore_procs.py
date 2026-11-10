"""The process table: snapshots, gc's agent matching rules, the
infrastructure fence, the tree kill and the attach scan."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from cityharness import City
from fakehc.procfs import add_proc, add_thread

from gc_runtime_herdr_core.hc.parse import parse_terminal
from gc_runtime_herdr_core.hc.types import Terminal
from gc_runtime_herdr_core.herdrcore import attach
from gc_runtime_herdr_core.herdrcore.reads import agent_state
from gc_runtime_herdr_core.herdrcore.infra_argv import is_infrastructure_argv
from gc_runtime_herdr_core.herdrcore.procs import (
    LinuxProcs,
    Proc,
    ProcError,
    ProcSource,
    PsProcs,
    expand_names,
    fenced_pids,
    find_agent,
    is_launching,
    is_tmux,
    kill_captured,
    matches,
    parse_environ,
    scan_environ,
    scan_environ_any,
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


def test_find_agent_looks_through_wrappers() -> None:
    snap = {
        1: proc(1, ("/bin/sh", "-c", "x"), ppid=0),
        2: proc(2, ("bash", "-lc", "y"), ppid=1),
        3: proc(3, ("node", "/x/claude.js"), comm="node-MainThread", ppid=2),
    }
    found = find_agent(snap, 1, expand_names(["claude"]))
    assert found is not None and found.pid == 3
    assert find_agent(snap, 1, expand_names(["codex"])) is None


def test_is_launching_until_the_launcher_execs() -> None:
    launching = {7: proc(7, ("/usr/bin/python3", "-I", "-S", "/p/assets/bin/gc-herdr-core-launch", "/run/x.json"))}
    assert is_launching(launching, 7)
    assert not is_launching({7: proc(7, ("cat",))}, 7)


@pytest.mark.parametrize(
    "argv, want",
    [
        (("dolt", "__gc-managed-dolt-scope-watchdog"), True),
        (("/usr/local/bin/bd", "db-proxy-child", "--x"), True),
        (("gc", "nudge", "poll", "mc"), True),
        (("gc", "nudge", "send"), False),
        (("db-proxy-child",), False),
        (("sleep", "60"), False),
    ],
)
def test_infrastructure_verbs_mirror_gc(argv: Tuple[str, ...], want: bool) -> None:
    assert is_infrastructure_argv(argv) is want


def test_fenced_subtrees_are_pruned_whole() -> None:
    snap = {
        1: proc(1, ("sh",), ppid=0),
        2: proc(2, ("gc", "__gc-managed-dolt-scope-watchdog"), ppid=1),
        3: proc(3, ("dolt", "sql-server"), ppid=2),  # the server under the watchdog
        4: proc(4, ("/usr/local/bin/bd", "db-proxy-child"), ppid=1),
        5: proc(5, ("helper",), ppid=4),
        6: proc(6, ("sleep", "600"), ppid=1),
    }
    assert fenced_pids(snap) == {2, 3, 4, 5}
    assert [p.pid for p in subtree(snap, 1)] == [1, 2, 4, 6, 3, 5]


@pytest.mark.parametrize(
    "comm, argv, want",
    [
        ("tmux: server", ("tmux", "new", "-d"), True),
        ("tmux: client", ("tmux", "attach"), True),
        ("tmux: server\n", ("tmux: server (/tmp/tmux-1000/default)",), True),
        ("", ("/opt/homebrew/bin/tmux", "-L", "hq", "new-session", "-d"), True),
        ("", ("tmux:", "server"), True),  # ps -ww splits a proctitle'd "tmux: server" at its space
        ("tmux", ("tmux",), True),
        ("tmux-wrapper", ("/usr/local/bin/tmux-wrapper", "--serve"), False),
        ("tmuxinator", ("tmuxinator", "start"), False),
        ("bash", ("bash", "-c", "tmux new -d"), False),
        ("", (), False),
    ],
)
def test_tmux_is_infrastructure_as_gc_reads_it(comm: str, argv: Tuple[str, ...], want: bool) -> None:
    assert is_tmux(Proc(pid=9, ppid=1, uid=os.getuid(), start="1", comm=comm, argv=argv)) is want


def test_a_tmux_server_and_its_panes_are_fenced_whole() -> None:
    snap = {
        1: proc(1, ("init",), ppid=0),
        2: proc(2, ("tmux", "new", "-d"), comm="tmux: server", ppid=1),
        3: proc(3, ("-bash",), ppid=2),
        4: proc(4, ("vim",), ppid=3),
        5: proc(5, ("sleep", "600"), ppid=1),
    }
    assert fenced_pids(snap) == {2, 3, 4}


def test_a_tmux_server_above_the_killed_program_fences_none_of_its_tree() -> None:
    # hc's core was started from a tmux pane: the box's tree runs under the
    # operator's server, which still fences its other panes and any tmux in the box.
    snap = {
        1: proc(1, ("init",), ppid=0),
        2: proc(2, ("tmux",), comm="tmux: server", ppid=1),
        3: proc(3, ("-zsh",), ppid=2),
        4: proc(4, ("herdr-core", "server"), ppid=2),
        5: proc(5, ("cat",), ppid=4),  # the box's agent
        6: proc(6, ("sleep", "600"), ppid=5),
        7: proc(7, ("tmux", "new", "-d"), comm="tmux: client", ppid=5),
        8: proc(8, ("sleep", "600"), ppid=7),
    }
    assert fenced_pids(snap, own=5) == {2, 3, 4, 7, 8}
    assert fenced_pids(snap) == {2, 3, 4, 5, 6, 7, 8}


class RecordingProcs(LinuxProcs):
    def __init__(self, root: str) -> None:
        LinuxProcs.__init__(self, root)
        self.signals: List[Tuple[int, int]] = []
        self.root = Path(root)

    def kill(self, pid: int, sig: int) -> None:
        self.signals.append((pid, sig))
        if sig == signal.SIGKILL or pid != 22:  # pid 22 ignores TERM
            for leaf in ("stat", "cmdline", "environ"):
                (self.root / str(pid) / leaf).unlink(missing_ok=True)
            (self.root / str(pid)).rmdir()


def test_kill_captured_terms_then_kills_and_fences_by_start_time(tmp_path: Path) -> None:
    add_proc(tmp_path, 21, ppid=1, argv=["a"], start=5)
    add_proc(tmp_path, 22, ppid=1, argv=["stubborn"], start=5)
    add_proc(tmp_path, 23, ppid=1, argv=["recycled"], start=9)
    add_proc(tmp_path, 1, ppid=0, argv=["init"])
    source = RecordingProcs(str(tmp_path))
    captured = [proc(21, ("a",), start="5"), proc(22, ("stubborn",), start="5"), proc(23, ("recycled",), start="5")]
    survivors = kill_captured(source, captured, grace_s=0.3, pause=time.sleep)
    assert survivors == []
    assert (23, signal.SIGTERM) not in source.signals  # a new process on a reused pid is never signalled
    assert source.signals[:2] == [(21, signal.SIGTERM), (22, signal.SIGTERM)]
    assert (22, signal.SIGKILL) in source.signals and (21, signal.SIGKILL) not in source.signals


def test_scan_environ_finds_the_incarnations_processes(tmp_path: Path) -> None:
    add_proc(tmp_path, 31, ppid=1, argv=["orphan"], env={"GC_INSTANCE_TOKEN": "tok-1"})
    add_proc(tmp_path, 32, ppid=1, argv=["other"], env={"GC_INSTANCE_TOKEN": "tok-2"})
    add_proc(tmp_path, 33, ppid=1, argv=["none"])
    source = LinuxProcs(str(tmp_path))
    found = scan_environ(source, source.snapshot(), "GC_INSTANCE_TOKEN", "tok-1")
    assert [p.pid for p in found] == [31]


def test_an_empty_value_matches_no_process(tmp_path: Path) -> None:
    # A process without the key reads as "": an empty value must never find it.
    add_proc(tmp_path, 31, ppid=1, argv=["carrier"], env={"GC_INSTANCE_TOKEN": "tok-1"})
    add_proc(tmp_path, 33, ppid=1, argv=["none"])
    source = LinuxProcs(str(tmp_path))
    snapshot = source.snapshot()
    assert scan_environ_any(source, snapshot, "GC_INSTANCE_TOKEN", frozenset({""})) == []
    assert scan_environ(source, snapshot, "GC_INSTANCE_TOKEN", "") == []
    assert [p.pid for p in scan_environ_any(source, snapshot, "GC_INSTANCE_TOKEN", frozenset({"", "tok-1"}))] == [31]


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


def test_scan_environ_skips_a_process_it_cannot_read(tmp_path: Path) -> None:
    if os.getuid() == 0:
        pytest.skip("root reads any file")
    add_proc(tmp_path, 51, ppid=1, argv=["ssh-agent"], env={"GC_INSTANCE_TOKEN": "tok-1"})
    add_proc(tmp_path, 52, ppid=1, argv=["orphan"], env={"GC_INSTANCE_TOKEN": "tok-1"})
    (tmp_path / "51" / "environ").chmod(0)
    source = LinuxProcs(str(tmp_path))
    try:
        assert [p.pid for p in scan_environ(source, source.snapshot(), "GC_INSTANCE_TOKEN", "tok-1")] == [52]
    finally:
        (tmp_path / "51" / "environ").chmod(0o600)


def test_ps_reads_every_environment_with_one_ps() -> None:
    """macOS: one ``ps -E`` for the whole scan, as gc's proctable reads it,
    with the per-process read as the fallback."""

    class Ps(PsProcs):
        def __init__(self, *, bulk: bool) -> None:
            self.bulk = bulk
            self.calls: List[Tuple[str, ...]] = []

        def _ps(self, *args: str) -> str:
            self.calls.append(args)
            if "-axo" in args:
                if not self.bulk:
                    raise ProcError("ps exited 1")
                return "   31 orphan GC_INSTANCE_TOKEN=tok-1 PATH=/usr/bin\n   32 other GC_INSTANCE_TOKEN=tok-2 9X=no\n   33 none\n"
            return {"31": "orphan GC_INSTANCE_TOKEN=tok-1\n", "32": "other GC_INSTANCE_TOKEN=tok-2\n", "33": "none\n"}[args[-1]]

    snapshot = {pid: proc(pid, (name,)) for pid, name in ((31, "orphan"), (32, "other"), (33, "none"))}
    bulk = Ps(bulk=True)
    assert [p.pid for p in scan_environ(bulk, snapshot, "GC_INSTANCE_TOKEN", "tok-1")] == [31]
    assert bulk.calls == [("-E", "-ww", "-axo", "pid=,command=")]
    want = {31: {"GC_INSTANCE_TOKEN": "tok-1", "PATH": "/usr/bin"}, 32: {"GC_INSTANCE_TOKEN": "tok-2"}}
    assert bulk.environs([31, 32, 99]) == want
    each = Ps(bulk=False)
    assert [p.pid for p in scan_environ(each, snapshot, "GC_INSTANCE_TOKEN", "tok-1")] == [31]
    assert len(each.calls) == 4, "the one ps for all of them fails, then one per process"


def test_a_zombie_is_neither_an_agent_nor_alive(tmp_path: Path) -> None:
    add_proc(tmp_path, 61, ppid=1, argv=["sh"])
    add_proc(tmp_path, 62, ppid=61, argv=["claude"], state="Z")
    source = LinuxProcs(str(tmp_path))
    snap = source.snapshot()
    assert snap[62].state == "Z"
    assert find_agent(snap, 61, expand_names(["claude"])) is None
    assert kill_captured(source, [snap[62]], grace_s=0.2, pause=time.sleep) == []


def test_nothing_is_signalled_when_the_table_cannot_be_reread(tmp_path: Path) -> None:
    add_proc(tmp_path, 71, ppid=1, argv=["a"], start=5)

    class Flaky(RecordingProcs):
        def snapshot(self) -> Dict[int, Proc]:
            raise ProcError("gone")

    source = Flaky(str(tmp_path))
    captured = [proc(71, ("a",), start="5")]
    assert kill_captured(source, captured, grace_s=0.2, pause=time.sleep) == captured
    assert source.signals == []


@pytest.mark.parametrize(
    "argv",
    [
        ("/usr/bin/systemd-run", "--user", "--scope", "--", "/bin/sh", "-c", "claude"),
        ("/usr/bin/env", "-u", "X", "/bin/sh", "-c", "claude"),
    ],
)
def test_the_launch_wrappers_count_as_launching(argv: Tuple[str, ...]) -> None:
    assert is_launching({8: proc(8, argv)}, 8)


def test_a_wrapper_root_with_a_child_has_launched() -> None:
    snap = {
        8: proc(8, ("/usr/bin/systemd-run", "--user", "--scope", "--", "x")),
        9: proc(9, ("claude",), ppid=8),
    }
    assert not is_launching(snap, 8)
    launcher = {7: proc(7, ("/usr/bin/python3", "-I", "-S", "/p/assets/bin/gc-herdr-core-launch", "/run/x.json"))}
    assert is_launching(launcher, 7)


def test_an_opaque_process_is_never_signalled(tmp_path: Path) -> None:
    add_proc(tmp_path, 81, ppid=1, argv=["a"], start=5)
    source = RecordingProcs(str(tmp_path))
    hidden = Proc(pid=81, ppid=1, uid=os.getuid(), start="", comm="", argv=(), opaque=True)
    # Captured without a start token, it cannot be told from a recycled pid:
    # it may survive, and is never signalled.
    assert kill_captured(source, [hidden], grace_s=0.2, pause=time.sleep) == [hidden]
    assert source.signals == []


def test_a_process_that_turns_opaque_after_its_capture_may_survive() -> None:
    """Readable when captured, opaque on every re-read (non-dumpable under
    ``hidepid=1``): never signalled, and reported as surviving, so the
    record and its token stay for the retry."""

    class Hidden(ProcSource):
        def snapshot(self) -> Dict[int, Proc]:
            return {12345: Proc(pid=12345, ppid=1, uid=os.getuid(), start="", comm="", argv=(), opaque=True)}

        def kill(self, pid: int, sig: int) -> None:
            raise AssertionError(f"signalled {pid} with {sig}")

    source = Hidden()
    captured = proc(12345, ("daemon",), start="7")
    assert kill_captured(source, [captured], grace_s=0.3, pause=lambda _: None) == [captured]


@needs_file_modes
def test_a_process_that_turns_opaque_mid_kill_is_reported_beside_one_that_outlived_its_kill(tmp_path: Path) -> None:
    add_proc(tmp_path, 1, ppid=0, argv=["init"], children=[91, 92])
    add_proc(tmp_path, 91, ppid=1, argv=["stubborn"], start=5)
    add_proc(tmp_path, 92, ppid=1, argv=["hiding"], start=5)

    class Turning(RecordingProcs):
        def kill(self, pid: int, sig: int) -> None:
            self.signals.append((pid, sig))  # 91 outlives even its KILL
            if pid == 92:
                hide(self.root, 92)  # turns non-dumpable instead of exiting

    source = Turning(str(tmp_path))
    captured = [proc(91, ("stubborn",), start="5"), proc(92, ("hiding",), start="5")]
    assert kill_captured(source, captured, grace_s=0.2, pause=time.sleep) == captured
    assert source.signals == [(91, signal.SIGTERM), (92, signal.SIGTERM), (91, signal.SIGKILL)]


def test_linux_procs_read_exe_cgroup_and_socket_holders(tmp_path: Path) -> None:
    from fakehc.procfs import add_proc, add_unix_socket

    from gc_runtime_herdr_core.herdrcore.procs import parse_cgroup

    add_proc(tmp_path, 10, ppid=1, argv=["/opt/hc/herdr-core", "serve"], exe="/opt/hc/herdr-core", cgroup="/user.slice/hc-serve-x.service", sockets=[555])
    add_proc(tmp_path, 11, ppid=1, argv=["sleep"])
    add_unix_socket(tmp_path, 555, "/city/.gc/controller.sock")
    procs = LinuxProcs(str(tmp_path))
    assert procs.exe(10) == "/opt/hc/herdr-core" and procs.exe(11) is None
    assert procs.cgroup(10) == "/user.slice/hc-serve-x.service" and procs.cgroup(11) is None
    assert procs.socket_holders("/city/.gc/controller.sock", [10, 11]) == {10}
    assert procs.socket_holders("/other.sock", [10, 11]) == set()
    assert parse_cgroup("12:pids:/a\n1:name=systemd:/b\n") == "/b"
    assert parse_cgroup("0::/c\n1:name=systemd:/b\n") == "/c"
    assert parse_cgroup("") is None


def test_a_process_start_reads_as_wall_clock_ms(tmp_path: Path) -> None:
    """Linux: ``btime`` plus the start time's ticks; ps: ``lstart``, local
    time. A start that cannot be told is None."""
    tick = os.sysconf("SC_CLK_TCK")
    add_proc(tmp_path, 71, ppid=1, argv=["cat"], start=5 * tick)
    source = LinuxProcs(str(tmp_path))
    assert source.started_ms(source.snapshot()[71]) is None, "no btime"
    (tmp_path / "stat").write_text("cpu  1 2 3\nbtime 1700000000\n")
    assert source.started_ms(source.snapshot()[71]) == 1_700_000_005_000
    lstart = time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(1_700_000_000))
    assert PsProcs().started_ms(Proc(72, 1, 0, " ".join(lstart.split()), "cat", ("cat",))) == 1_700_000_000_000
    assert PsProcs().started_ms(Proc(73, 1, 0, "", "cat", ("cat",))) is None
    assert ProcSource().started_ms(Proc(74, 1, 0, "1", "cat", ("cat",))) is None
