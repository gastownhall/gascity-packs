"""The pack's own core where its environment does not show who started it.

On macOS hc starts the core as a launchd job: the core runs as
``<hc> --hc-launchd <dir>/ready`` with launchd's environment, and ``<dir>``
names the pid of the process that asked for it. The pack records the core
its own hc asked for, and accepts a core a holder of the city restarted by
that holder's environment, recording it; any other launchd core is foreign.
Under systemd a core a holder restarted has that holder's environment in its
unit file: the pack's by the lineage the pack recorded when it accepted that
holder's core, never by a live holder. Under systemd older than 244 a core's
unit has no ``RUNTIME_DIRECTORY``, so the pack finds its environment file
through the core's control group. Everywhere the environment can be judged,
it is: a record never overrides it. Only a start records. Nothing here runs
a real herdr-core."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pytest
from cityharness import City, in_thread, make_city
from conftest import teardown_cores
from fakehc.cli import systemd_unit_env, write_launcher
from fakehc.procfs import add_boot, add_proc
from fakehc.rawclient import raw_call
from test_herdrcore_commands import run as run_command
from test_herdrcore_core import core_environ, entry_env, invoke

from gc_runtime_herdr_core.hc.paths import resolve_paths
from gc_runtime_herdr_core.herdrcore import admin, commands, core, coreid, corescan
from gc_runtime_herdr_core.herdrcore.context import OpContext, live_host
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcError, PsProcs
from gc_runtime_herdr_core.rpp.cancel import CancelToken, Deadline
from gc_runtime_herdr_core.rpp.ops import OpError, OpRequest
from gc_runtime_herdr_core.rpp.redact import Redactor

needs_proc = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")

FAKE_CLI = Path(__file__).resolve().parents[1] / "fakehc" / "cli.py"

LAUNCHD_KEYS = (
    # What a launchd user agent's job runs with when its plist sets no
    # EnvironmentVariables (launchd.plist(5), launchd's own defaults): hc's
    # core on macOS (hc macos_launchd.rs) carries these and nothing of its
    # starter's. Values synthetic.
    "HOME LOGNAME PATH SHELL SSH_AUTH_SOCK TMPDIR USER XPC_FLAGS XPC_SERVICE_NAME __CF_USER_TEXT_ENCODING"
).split()


def launchd_environ() -> Dict[str, str]:
    env = {key: f"launchd-{key.lower()}" for key in LAUNCHD_KEYS}
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return env


def launchd_argv(starter_pid: int, asked_ns: Optional[int] = None) -> Tuple[str, ...]:
    """hc's launchd core argv (``platform/macos_launchd.rs`` ``launch``/``detach``)."""
    stamp = time.time_ns() if asked_ns is None else asked_ns
    return ("/opt/hc/herdr-core", "--hc-launchd", f"/tmp/hc-launchd-{starter_pid}-{stamp}-{uuid.uuid4().hex}/ready")


def as_launchd_core(city: City, starter_pid: int, asked_ns: Optional[int] = None) -> None:
    """Make the in-process core read as a launchd-placed one."""
    city.procs.core_argv = launchd_argv(starter_pid, asked_ns)
    city.procs.core_environ = launchd_environ()


def record_running_core(city: City, starter_pid: int = 4242) -> OpContext:
    """Record the in-process core as the launchd core the pack's hc (pid ``starter_pid``) started."""
    since_ms = coreid.wall_ms()
    as_launchd_core(city, starter_pid)
    ctx = city.context()
    assert coreid.record(ctx, ctx.client().server_status(), starter_pid=starter_pid, since_ms=since_ms)
    return ctx


def identity_path(ctx: OpContext) -> Path:
    return Path(ctx.pack_state) / coreid.IDENTITY_FILE


def rewrite_identity(ctx: OpContext, **changes: object) -> None:
    path = identity_path(ctx)
    doc = json.loads(path.read_text())
    doc.update(changes)
    path.write_text(json.dumps(doc))


def forget_core_json(city: City) -> None:
    """A core of another state: its id is not the one in the city's core.json."""
    (Path(city.paths.state_dir) / "core.json").write_text(json.dumps({"id": "0" * 32, "name": "x"}))


# --- hc's launchd argv ------------------------------------------------------------------------


def test_the_launchd_argv_names_its_starter_and_when_it_asked() -> None:
    started = coreid.launchd_start(("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-31-1700000000000000000-" + "a" * 32 + "/ready"))
    assert started == coreid.LaunchdStart(starter_pid=31, asked_ns=1_700_000_000_000_000_000)
    script = ("/usr/bin/python3", "/x/cli.py", "--hc-launchd", "/s/hc-launchd-7-5-" + "b" * 32 + "/ready")
    assert coreid.launchd_start(script) == coreid.LaunchdStart(starter_pid=7, asked_ns=5)
    # ps prints argv joined by spaces: an hc path with spaces reads as more words.
    spaced = ("/Applications/Herdr", "Core.app/Contents/MacOS/herdr-core", "--hc-launchd", "/tmp/hc-launchd-9-5-" + "c" * 32 + "/ready")
    assert coreid.launchd_start(spaced) == coreid.LaunchdStart(starter_pid=9, asked_ns=5)
    for argv in (
        ("/opt/hc/herdr-core", "serve"),
        ("/opt/hc/herdr-core", "--hc-launchd"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-31-5-" + "a" * 32 + "/other"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-31-5-short/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-x-5-" + "a" * 32 + "/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/elsewhere-31-5-" + "a" * 32 + "/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-0-5-" + "a" * 32 + "/ready"),
        ("--hc-launchd", "/tmp/hc-launchd-31-5-" + "a" * 32 + "/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-31-5-" + "a" * 32 + "/ready", "extra"),
    ):
        assert coreid.launchd_start(argv) is None, argv


# --- the recorded identity (macOS) ----------------------------------------------------------


def test_the_identity_file_is_private_and_names_pid_start_and_core_id(city: City) -> None:
    ctx = record_running_core(city)
    path = identity_path(ctx)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    doc = json.loads(path.read_text())
    status = ctx.client().server_status()
    proc = city.procs.process(status.pid)
    assert proc is not None
    assert doc == {"pid": status.pid, "start": proc.start, "boot": city.procs.boot(), "core_id": status.core.id}
    assert not [p for p in path.parent.iterdir() if p.name.startswith(".")], "written through a temp file, renamed"


def test_start_accepts_the_launchd_core_the_pack_started(city: City) -> None:
    record_running_core(city)
    done = city.start("mc-a")
    assert done.code == 0, done.stderr


def test_start_refuses_a_launchd_core_the_pack_did_not_start(city: City) -> None:
    as_launchd_core(city, starter_pid=4242)  # not recorded; no such holder
    done = city.start("mc-a")
    assert done.code == 1 and "restart-core" in done.stderr and "launchd" in done.stderr
    assert city.fake is not None and city.fake.call_count("terminal.run") == 0


def test_a_core_another_starter_brought_up_is_never_recorded(city: City) -> None:
    """``hc server start`` has no starter lock: a core another starter (the
    Herdr app's autostart, a person's hc) brought up at the same time wins,
    and the pack's hc then talks to it. It names its own starter."""
    since_ms = coreid.wall_ms()
    as_launchd_core(city, starter_pid=5151)
    ctx = city.context()
    assert not coreid.record(ctx, ctx.client().server_status(), starter_pid=4242, since_ms=since_ms)
    assert not identity_path(ctx).exists()
    assert city.start("mc-a").code == 1


def test_a_core_asked_for_before_the_pack_ran_its_hc_is_never_recorded(city: City) -> None:
    since_ms = coreid.wall_ms()
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms - 1500) * 1_000_000)
    ctx = city.context()
    assert not coreid.record(ctx, ctx.client().server_status(), starter_pid=4242, since_ms=since_ms)
    assert not identity_path(ctx).exists()


def test_a_core_that_is_not_a_launchd_core_is_never_recorded(city: City) -> None:
    ctx = city.context()
    assert not coreid.record(ctx, ctx.client().server_status(), starter_pid=os.getpid(), since_ms=0)
    assert not identity_path(ctx).exists()


def test_a_record_never_overrides_an_environment_that_can_be_judged(city: City) -> None:
    """A core that is not launchd-placed is judged by its environment even
    when a record names it: a record cannot let a foreign environment in."""
    ctx = city.context()
    status = ctx.client().server_status()
    proc = city.procs.process(status.pid)
    boot = city.procs.boot()
    assert proc is not None and boot is not None
    coreid.write(ctx, coreid.CoreIdentity(pid=status.pid, start=proc.start, boot=boot, core_id=status.core.id))
    city.procs.core_environ = dict(city.procs.core_environ or {}, OPENAI_API_KEY="sk-theirs")
    done = city.start("mc-a")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr


@pytest.mark.parametrize(
    "change",
    [
        {"start": "1"},  # the pid was reused: another process
        {"core_id": "0" * 32},  # another core's state
        {"boot": "another-boot"},  # a start token of another boot
        {"pid": 1},  # another process altogether
    ],
    ids=["pid-reused", "other-core-id", "other-boot", "other-pid"],
)
def test_a_core_that_does_not_match_every_recorded_field_is_foreign(city: City, change: Dict[str, object]) -> None:
    ctx = record_running_core(city)
    rewrite_identity(ctx, **change)
    done = city.start("mc-a")
    assert done.code == 1 and "restart-core" in done.stderr
    assert not coreid.started_by_pack(ctx, ctx.client().server_status())


def test_a_forged_identity_file_is_not_trusted(city: City, tmp_path: Path) -> None:
    ctx = record_running_core(city)
    path = identity_path(ctx)
    path.chmod(0o664)  # writable by others: anyone may have written it
    assert city.start("mc-a").code == 1
    path.chmod(0o600)
    assert coreid.started_by_pack(ctx, ctx.client().server_status())
    elsewhere = tmp_path / "forged.json"
    elsewhere.write_bytes(path.read_bytes())
    elsewhere.chmod(0o600)
    path.unlink()
    path.symlink_to(elsewhere)
    assert city.start("mc-a").code == 1
    path.unlink()
    path.write_text("{not json")
    path.chmod(0o600)
    assert city.start("mc-a").code == 1


def test_a_core_whose_process_cannot_be_read_is_never_recorded(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    as_launchd_core(city, starter_pid=4242)
    ctx = city.context()
    status = ctx.client().server_status()

    def unreadable(pid: int) -> Proc:
        raise ProcError("hidden")

    monkeypatch.setattr(city.procs, "process", unreadable)
    assert not coreid.record(ctx, status, starter_pid=4242, since_ms=0)
    monkeypatch.undo()
    monkeypatch.setattr(city.procs, "boot", lambda: None)
    assert not coreid.record(ctx, status, starter_pid=4242, since_ms=0)
    assert not coreid.started_by_pack(ctx, status)


def test_status_knows_the_core_the_pack_started(city: City) -> None:
    record_running_core(city)
    code, out, _ = run_command(city, "status")
    assert code == 0 and "started:   by the pack" in "\n".join(out)


def test_a_core_that_does_not_answer_is_found_by_its_recorded_identity(short_tmp: Path, home_dir: Path) -> None:
    """A core that does not answer its socket is found in the process table
    by its environment, or, where that does not name its socket (launchd,
    whose argv never names ``serve``), by the identity the pack recorded."""
    proc_root = short_tmp / "proc"
    add_proc(proc_root, 1, ppid=0, argv=["/sbin/init"])
    add_boot(proc_root, "boot-1")
    add_proc(proc_root, 4242, ppid=1, argv=list(launchd_argv(77)), start=777, env=launchd_environ())
    made = make_city(short_tmp, home_dir, procs=LinuxProcs(str(proc_root)))
    ctx = made.context()
    snapshot = made.procs.snapshot()
    assert corescan.core_processes(ctx, snapshot) == []
    assert corescan.nothing_runs(ctx)
    coreid.write(ctx, coreid.CoreIdentity(pid=4242, start="777", boot="boot-1", core_id="c" * 32))
    assert [proc.pid for proc in corescan.core_processes(ctx, snapshot)] == [4242]
    assert not corescan.nothing_runs(ctx)
    coreid.write(ctx, coreid.CoreIdentity(pid=4242, start="778", boot="boot-1", core_id="c" * 32))
    assert corescan.core_processes(ctx, snapshot) == []
    since_ms = coreid.wall_ms() - 60_000
    coreid.begin_start(ctx, starter_pid=77, since_ms=since_ms)  # the pack's start still runs
    assert [proc.pid for proc in corescan.core_processes(ctx, snapshot)] == [4242]
    coreid.begin_start(ctx, starter_pid=78, since_ms=since_ms)  # another start leaves its entry be
    assert [proc.pid for proc in corescan.core_processes(ctx, snapshot)] == [4242]
    coreid.close_start(ctx, starter_pid=77, since_ms=since_ms, until_ms=since_ms + 1)  # it ended before the core was asked for
    assert corescan.core_processes(ctx, snapshot) == []


# --- the pack's start, pending until its hc is done (macOS) -----------------------------------


def pending_path(ctx: OpContext) -> Path:
    return Path(ctx.pack_state) / coreid.PENDING_FILE


STALLED_HC = """#!/bin/sh
echo $$ > {pidfile}
while [ ! -e {release} ]; do sleep 0.02; done
exit {code}
"""
"""An hc whose ``server start`` asked launchd for the core (its pid in
``pidfile``) and then waits until ``release`` exists."""


def stalled_hc(tmp: Path, *, code: int = 0) -> Tuple[str, Path, Path]:
    pidfile, release = tmp / "hc.pid", tmp / "release"
    script = tmp / "stalled-hc"
    script.write_text(STALLED_HC.format(pidfile=pidfile, release=release, code=code))
    script.chmod(0o755)
    return str(script), pidfile, release


def await_pid(pidfile: Path) -> int:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        text = pidfile.read_text().strip() if pidfile.exists() else ""
        if text:
            return int(text)
        time.sleep(0.02)
    raise AssertionError("the stand-in hc did not start")


def test_the_pending_start_is_recorded_before_the_packs_hc_is_waited_on(city: City) -> None:
    """The pack names its hc's pid before it waits on it, privately; a start
    that times out keeps it, closed at the time its hc ended."""
    script, pidfile, _ = stalled_hc(city.root)
    ctx = city.context(deadline_s=2.5)
    since_ms = coreid.wall_ms()
    with pytest.raises(OpError, match="timed out"):
        core.start_core(ctx, script)
    (pending,) = coreid.read_pending(ctx)
    assert pending.starter_pid == int(pidfile.read_text())
    assert since_ms <= pending.since_ms and pending.until_ms is not None and pending.since_ms < pending.until_ms <= coreid.wall_ms()
    path = pending_path(ctx)
    assert json.loads(path.read_text()) == {
        "starts": [{"starter_pid": pending.starter_pid, "since_ms": pending.since_ms, "until_ms": pending.until_ms}]
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not [p for p in path.parent.iterdir() if p.name.startswith(".")], "written through a temp file, renamed"


def test_a_core_a_timed_out_start_asked_for_is_accepted_by_a_later_start(city: City) -> None:
    """hc asked launchd for the core and was killed at the pack's deadline;
    the core comes up after. The next start accepts it and pins it."""
    script, pidfile, _ = stalled_hc(city.root)
    ctx = city.context(deadline_s=2.5)
    with pytest.raises(OpError, match="timed out"):
        core.start_core(ctx, script)
    (pending,) = coreid.read_pending(ctx)
    assert pending.until_ms is not None
    as_launchd_core(city, starter_pid=int(pidfile.read_text()), asked_ns=(pending.since_ms + 1) * 1_000_000)
    done = city.start("mc-a")
    assert done.code == 0, done.stderr
    ctx = city.context()
    assert coreid.started_by_pack(ctx, ctx.client().server_status()), "pinned on its first acceptance"
    assert coreid.read_pending(ctx) == (), "superseded by the record it pinned"
    assert not pending_path(ctx).exists()


def quick_hc(tmp: Path) -> str:
    """An hc whose ``server start`` finds the core answering, and asked for none."""
    script = tmp / "quick-hc"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    return str(script)


def await_pending(ctx: OpContext, starter_pid: int) -> None:
    """Until the pack's start that runs ``starter_pid`` has noted it."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if any(entry.starter_pid == starter_pid for entry in coreid.read_pending(ctx)):
            return
        time.sleep(0.02)
    raise AssertionError(f"no pending start names {starter_pid}")


def test_a_core_a_timed_out_start_asked_for_stays_the_packs_after_another_start(city: City) -> None:
    """hc A asked launchd for the core and was killed at the pack's deadline;
    the core came up after, and another start's hc B then found it
    answering. B's start leaves A's entry be: a later start accepts the core
    A asked for, and pins it."""
    script, pidfile, _ = stalled_hc(city.root)
    with pytest.raises(OpError, match="timed out"):
        core.start_core(city.context(deadline_s=2.5), script)
    ctx = city.context()
    (first,) = coreid.read_pending(ctx)
    as_launchd_core(city, starter_pid=int(pidfile.read_text()), asked_ns=(first.since_ms + 1) * 1_000_000)
    core.start_core(ctx, quick_hc(city.root))
    assert coreid.read_pending(ctx) == (first,), "B's start finished; A's entry stays"
    done = city.start("mc-a")
    assert done.code == 0, done.stderr
    assert coreid.started_by_pack(ctx, ctx.client().server_status())
    assert coreid.read_pending(ctx) == ()


def test_a_core_a_running_start_asked_for_is_the_packs_while_another_start_runs_and_ends(city: City) -> None:
    """Starts of the pack run at once: hc A asked launchd for the core and
    still runs when another start's hc B finds that core answering and ends.
    A's entry stays open, so a start that checks now accepts A's core."""
    script, pidfile, release = stalled_hc(city.root)
    errors: List[BaseException] = []

    def first() -> None:
        try:
            core.start_core(city.context(), script)
        except BaseException as err:  # noqa: BLE001 - reported below
            errors.append(err)

    thread = in_thread(first)
    ctx = city.context()
    try:
        pid = await_pid(pidfile)
        await_pending(ctx, pid)
        as_launchd_core(city, starter_pid=pid)
        core.start_core(ctx, quick_hc(city.root))
        assert [entry.starter_pid for entry in coreid.read_pending(ctx)] == [pid]
        done = city.start("mc-a")
        assert done.code == 0, done.stderr
    finally:
        release.touch()
        thread.join(timeout=30)
    assert not thread.is_alive() and errors == []
    assert coreid.started_by_pack(ctx, ctx.client().server_status())
    assert coreid.read_pending(ctx) == ()


def test_a_start_that_checks_while_the_packs_hc_still_runs_accepts_its_core(city: City) -> None:
    """Two ops of the pack start the city at once: the second finds the core
    the first one's hc asked for answering before the first recorded it."""
    script, pidfile, release = stalled_hc(city.root)
    errors: List[BaseException] = []

    def first() -> None:
        try:
            core.start_core(city.context(), script)
        except BaseException as err:  # noqa: BLE001 - reported below
            errors.append(err)

    thread = in_thread(first)
    as_launchd_core(city, starter_pid=await_pid(pidfile))
    ctx = city.context()
    assert not identity_path(ctx).exists()
    done = city.start("mc-a")
    assert done.code == 0, done.stderr
    release.touch()
    thread.join(timeout=30)
    assert not thread.is_alive() and errors == []
    assert coreid.started_by_pack(ctx, ctx.client().server_status())
    assert coreid.read_pending(ctx) == (), "its start finished"


def test_a_pending_start_never_lets_another_starter_in(city: City) -> None:
    """The pending start names the pack's hc: a core another starter asked
    for, or one asked for outside the time the pack's hc ran (its pid since
    reused), is refused, and nothing is recorded."""
    ctx = city.context()
    since_ms = coreid.wall_ms() - 5000
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms)
    as_launchd_core(city, starter_pid=5151, asked_ns=(since_ms + 1) * 1_000_000)
    assert city.start("mc-a").code == 1
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms - 1) * 1_000_000)
    assert city.start("mc-a").code == 1
    coreid.close_start(ctx, starter_pid=4242, since_ms=since_ms, until_ms=since_ms + 1000)
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + 1001) * 1_000_000)
    assert city.start("mc-a").code == 1
    assert not identity_path(ctx).exists()
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + 1000) * 1_000_000)
    assert city.start("mc-a").code == 0


def test_each_start_changes_only_its_own_entry(city: City) -> None:
    """A later start leaves an earlier one's entry be: the core the earlier
    one's hc asked for in its time stays the pack's."""
    ctx = city.context()
    since_ms = coreid.wall_ms()
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms)
    coreid.begin_start(ctx, starter_pid=4343, since_ms=since_ms + 1)
    coreid.close_start(ctx, starter_pid=4242, since_ms=since_ms, until_ms=since_ms + 2)
    first = coreid.PendingStart(starter_pid=4242, since_ms=since_ms, until_ms=since_ms + 2)
    assert coreid.read_pending(ctx) == (first, coreid.PendingStart(starter_pid=4343, since_ms=since_ms + 1, until_ms=None))
    coreid.finish_start(ctx, starter_pid=4343, since_ms=since_ms + 1)
    assert coreid.read_pending(ctx) == (first,)
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + 1) * 1_000_000)
    assert city.start("mc-a").code == 0


def test_starts_whose_hcs_had_one_pid_are_told_apart_by_when_they_ran(city: City) -> None:
    """The pid of one start's hc was reused by a later start's: each start
    closes and drops only its own entry, and a core that pid asked for
    between the two runs is neither's."""
    ctx = city.context()
    since_ms = coreid.wall_ms() - 10_000
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms)
    coreid.close_start(ctx, starter_pid=4242, since_ms=since_ms, until_ms=since_ms + 1000)
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms + 5000)
    coreid.close_start(ctx, starter_pid=4242, since_ms=since_ms + 5000, until_ms=since_ms + 6000)
    assert [(s.since_ms, s.until_ms) for s in coreid.read_pending(ctx)] == [
        (since_ms, since_ms + 1000),
        (since_ms + 5000, since_ms + 6000),
    ]
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + 3000) * 1_000_000)
    assert city.start("mc-a").code == 1
    coreid.finish_start(ctx, starter_pid=4242, since_ms=since_ms)
    assert [(s.since_ms, s.until_ms) for s in coreid.read_pending(ctx)] == [(since_ms + 5000, since_ms + 6000)]


def test_an_entry_whose_hc_never_ended_counts_only_for_a_while(city: City) -> None:
    """The pack was killed waiting on its hc, so it never closed the entry:
    it counts as ended PENDING_OPEN_MS after it began, and a core a process
    with that pid asked for after that is not the pack's."""
    ctx = city.context()
    since_ms = coreid.wall_ms() - coreid.PENDING_OPEN_MS - 60_000
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms)
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + coreid.PENDING_OPEN_MS + 1) * 1_000_000)
    assert city.start("mc-a").code == 1
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + coreid.PENDING_OPEN_MS) * 1_000_000)
    assert city.start("mc-a").code == 0


def test_an_open_entry_outlasts_every_wait_on_the_packs_hc() -> None:
    assert coreid.PENDING_OPEN_MS > (core.CORE_START_WAIT_S + commands.STOP_WAIT_S) * 1000


def test_entries_that_ended_long_ago_go_and_only_the_newest_are_kept(city: City) -> None:
    ctx = city.context()
    now = coreid.wall_ms()
    ended = now - coreid.PENDING_KEEP_MS - 10_000
    coreid.begin_start(ctx, starter_pid=4141, since_ms=ended - 1000)
    coreid.close_start(ctx, starter_pid=4141, since_ms=ended - 1000, until_ms=ended)
    coreid.begin_start(ctx, starter_pid=4242, since_ms=now)
    assert [s.starter_pid for s in coreid.read_pending(ctx)] == [4242]
    for n in range(coreid.PENDING_MAX + 3):
        coreid.begin_start(ctx, starter_pid=5000 + n, since_ms=now + n)
    assert [s.starter_pid for s in coreid.read_pending(ctx)] == list(range(5003, 5000 + coreid.PENDING_MAX + 3))


def test_a_forged_pending_start_is_not_trusted(city: City) -> None:
    ctx = city.context()
    since_ms = coreid.wall_ms()
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms)
    pending_path(ctx).chmod(0o664)
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + 1) * 1_000_000)
    assert coreid.read_pending(ctx) == ()
    assert city.start("mc-a").code == 1


def test_status_records_nothing(city: City) -> None:
    """Only a start records what it accepts: ``status`` reads the core a
    pending start asked for as the pack's, and leaves the entry and the
    record as they were."""
    ctx = city.context()
    since_ms = coreid.wall_ms()
    coreid.begin_start(ctx, starter_pid=4242, since_ms=since_ms)
    as_launchd_core(city, starter_pid=4242, asked_ns=(since_ms + 1) * 1_000_000)
    code, out, _ = run_command(city, "status")
    assert code == 0 and "started:   by the pack" in "\n".join(out)
    assert core.foreign_core(ctx, ctx.client().server_status(), city.env["GC_HC_TEST_BIN"]) is None
    assert not identity_path(ctx).exists() and len(coreid.read_pending(ctx)) == 1
    assert city.start("mc-a").code == 0
    assert identity_path(ctx).exists() and coreid.read_pending(ctx) == ()


# --- a holder of the city restarted the core (macOS) ------------------------------------------


def holder_env(city: City, **extra: str) -> Dict[str, str]:
    """A macOS holder's environment: the environment its core restored (the
    pack's allowlist, with hc's marks), and the mark of its re-exec."""
    env = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    env.update({"HC_RUNTIME": "1", "XPC_SERVICE_NAME": "0", "_HC_RESPONSIBLE_PID": "1"})
    env.update(extra)
    return env


@pytest.fixture
def started() -> Iterator[List["subprocess.Popen[bytes]"]]:
    """Processes a test starts; each is killed by its own pid at the end."""
    procs: List["subprocess.Popen[bytes]"] = []
    yield procs
    for proc in procs:
        proc.kill()
        proc.wait()


def run_holder(started: List["subprocess.Popen[bytes]"], city: City, env: Dict[str, str], *, socket: Optional[str] = None) -> int:
    """A holder stand-in (``hold --socket <city prefix><id>.sock``); a core
    answers, so it starts none."""
    sock = socket or corescan.holder_prefix(city.paths) + "0123abcd.sock"
    proc = subprocess.Popen([sys.executable, str(FAKE_CLI), "hold", "--socket", sock], env=env)
    started.append(proc)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        found = city.procs.process(proc.pid)
        if found is not None and "hold" in found.argv:
            return proc.pid
        time.sleep(0.02)
    raise AssertionError("the holder stand-in did not start")


@needs_proc
def test_a_launchd_core_a_holder_of_the_city_restarted_is_accepted(city: City, started: List["subprocess.Popen[bytes]"]) -> None:
    pid = run_holder(started, city, holder_env(city))
    as_launchd_core(city, starter_pid=pid)
    done = city.start("mc-a")
    assert done.code == 0, done.stderr


@needs_proc
def test_a_launchd_core_a_holder_restarted_stays_the_packs_once_that_holder_ends(
    city: City, started: List["subprocess.Popen[bytes]"]
) -> None:
    """The start that accepts it records it: once the holder that restarted
    it ends (its session did), the core still runs, and is still the pack's."""
    pid = run_holder(started, city, holder_env(city))
    as_launchd_core(city, starter_pid=pid)
    ctx = city.context()
    code, _, _ = run_command(city, "status")
    assert code == 0 and not identity_path(ctx).exists(), "status records nothing"
    done = city.start("mc-a")
    assert done.code == 0, done.stderr
    assert coreid.started_by_pack(ctx, ctx.client().server_status()), "recorded on its acceptance"
    holder = started.pop()
    holder.kill()
    holder.wait()
    done = city.start("mc-b")
    assert done.code == 0, done.stderr


@needs_proc
def test_a_launchd_core_whose_holder_carries_a_foreign_environment_is_refused(
    city: City, started: List["subprocess.Popen[bytes]"]
) -> None:
    pid = run_holder(started, city, holder_env(city, OPENAI_API_KEY="sk-theirs"))
    as_launchd_core(city, starter_pid=pid)
    done = city.start("mc-a")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr


@needs_proc
def test_a_launchd_core_asked_for_before_its_holder_started_is_refused(city: City, started: List["subprocess.Popen[bytes]"]) -> None:
    """A holder asks launchd only once it runs: a core asked for before the
    holder named by its pid started was asked for by an earlier process
    with that pid."""
    pid = run_holder(started, city, holder_env(city))
    as_launchd_core(city, starter_pid=pid, asked_ns=time.time_ns() - 60 * 1_000_000_000)
    done = city.start("mc-a")
    assert done.code == 1 and "restart-core" in done.stderr


@needs_proc
def test_a_launchd_core_started_by_a_holder_of_another_socket_or_by_no_holder_is_refused(
    city: City, started: List["subprocess.Popen[bytes]"]
) -> None:
    other = run_holder(started, city, holder_env(city), socket="/tmp/other-city.holder.0123abcd.sock")
    as_launchd_core(city, starter_pid=other)
    assert city.start("mc-a").code == 1
    plain = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], env=holder_env(city))
    started.append(plain)
    as_launchd_core(city, starter_pid=plain.pid)
    assert city.start("mc-a").code == 1


# --- whose core restart-core and upgrade may replace ----------------------------------------


def test_restart_core_replaces_the_citys_launchd_core_by_its_core_id(city: City) -> None:
    """A launchd core shows none of the city's variables, and one the holder
    restarted was never recorded: it is the city's by the core id hc keeps
    in the city's state directory."""
    as_launchd_core(city, starter_pid=4242)
    owner = admin.ownership(city.context(), city.context().client().server_status())
    assert owner.own, owner.reason
    code, _, err = run_command(city, "restart-core")
    assert code == 0, err
    assert city.fake is not None and city.fake.call_count("server.stop") == 1


def test_restart_core_refuses_a_core_of_another_state(city: City) -> None:
    as_launchd_core(city, starter_pid=4242)
    forget_core_json(city)
    code, _, err = run_command(city, "restart-core")
    assert code != 0 and "not this city's core" in "\n".join(err), err
    assert city.fake is not None and city.fake.call_count("server.stop") == 0


# --- systemd older than 244: the unit found through the control group ----------------------


def legacy_unit(city: City, starter: Dict[str, str]) -> Tuple[Dict[str, str], str]:
    """A core hc placed under systemd 239 (no RUNTIME_DIRECTORY), started
    with ``starter``: its environ and its control group."""
    run = city.env["GC_HC_TEST_RUNTIME_DIR"]
    env, unit = systemd_unit_env(starter, run, legacy=True)
    uid = os.getuid()
    return env, f"/user.slice/user-{uid}.slice/user@{uid}.service/app.slice/{unit}.service"


@pytest.fixture
def legacy_city(city: City) -> City:
    run = city.root / "run-user"
    run.mkdir(mode=0o700)
    city.env["GC_HC_TEST_RUNTIME_DIR"] = str(run)
    return city


def test_the_core_unit_is_read_from_the_control_group() -> None:
    uid = os.getuid()
    base = f"/user.slice/user-{uid}.slice/user@{uid}.service"
    assert core.core_unit(f"{base}/app.slice/hc-serve-0a1b2c3d.service", uid) == "hc-serve-0a1b2c3d"
    assert core.core_unit(f"{base}/hc-serve-0a1b2c3d.service", uid) == "hc-serve-0a1b2c3d"
    for cgroup in (
        None,
        "",
        f"{base}/app.slice/hc-hold-0a1b2c3d.service",
        f"{base}/app.slice/hc-serve-0a1b2c3.service",
        f"{base}/app.slice/hc-serve-0A1B2C3D.service",
        f"{base}/app.slice/hc-serve-0a1b2c3d.scope",
        f"/user.slice/user-{uid + 1}.slice/user@{uid + 1}.service/hc-serve-0a1b2c3d.service",
        "/system.slice/hc-serve-0a1b2c3d.service",
    ):
        assert core.core_unit(cgroup, uid) is None, cgroup


def test_the_packs_own_core_under_old_systemd_is_judged_by_its_unit_file(legacy_city: City) -> None:
    starter = core.core_env(legacy_city.context(), legacy_city.env["GC_HC_TEST_BIN"])
    env, cgroup = legacy_unit(legacy_city, starter)
    assert "RUNTIME_DIRECTORY" not in env
    legacy_city.procs.core_environ = env
    legacy_city.procs.core_cgroup = cgroup
    done = legacy_city.start("mc-a")
    assert done.code == 0, done.stderr


def test_a_core_someone_else_started_under_old_systemd_is_refused(legacy_city: City) -> None:
    starter = core.core_env(legacy_city.context(), legacy_city.env["GC_HC_TEST_BIN"])
    env, cgroup = legacy_unit(legacy_city, dict(starter, OPENAI_API_KEY="sk-theirs"))
    legacy_city.procs.core_environ = env
    legacy_city.procs.core_cgroup = cgroup
    done = legacy_city.start("mc-a")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr


def test_an_old_systemd_core_whose_unit_cannot_be_found_is_judged_by_its_live_environment(legacy_city: City) -> None:
    starter = core.core_env(legacy_city.context(), legacy_city.env["GC_HC_TEST_BIN"])
    env, _ = legacy_unit(legacy_city, starter)
    legacy_city.procs.core_environ = env
    legacy_city.procs.core_cgroup = "/user.slice/session-2.scope"
    done = legacy_city.start("mc-a")
    assert done.code == 1 and "GOCACHE" in done.stderr  # the manager's block, which the live environment carries


def systemd_core(city: City, starter: Dict[str, str], *, legacy: bool) -> Tuple[Dict[str, str], str]:
    """A core hc placed under systemd (``legacy``: older than 244), started
    with ``starter``: its environ and its control group."""
    env, unit = systemd_unit_env(starter, city.env["GC_HC_TEST_RUNTIME_DIR"], legacy=legacy)
    uid = os.getuid()
    return env, f"/user.slice/user-{uid}.slice/user@{uid}.service/app.slice/{unit}.service"


def lineage_path(city: City) -> Path:
    return Path(city.context().pack_state) / coreid.LINEAGE_FILE


def accept_packs_systemd_core(city: City, *, legacy: bool, **block: str) -> Dict[str, str]:
    """The pack's own core under systemd, which a start accepts (and records
    the lineage of); ``block``: more of the manager's block when it started.
    Its environ."""
    starter = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    env, cgroup = systemd_core(city, starter, legacy=legacy)
    env.update(block)
    city.procs.core_environ, city.procs.core_cgroup = env, cgroup
    done = city.start("mc-a")
    assert done.code == 0, done.stderr
    return env


def holder_of(city: City, core_environ: Dict[str, str], *, legacy: bool) -> Dict[str, str]:
    """The environ of a holder the core running with ``core_environ`` spawned:
    a unit too (hc ``client.rs`` ``spawn_detached``), so the manager's block,
    that core's environment less systemd's service variables, and its own."""
    holder, _ = systemd_unit_env(core_environ, city.env["GC_HC_TEST_RUNTIME_DIR"], legacy=legacy, verb="hold")
    return holder


@pytest.mark.parametrize("legacy", [True, False], ids=["systemd-239", "systemd-255"])
def test_a_start_records_the_lineage_of_the_systemd_core_it_accepts(legacy_city: City, legacy: bool) -> None:
    """What every holder of the pack's core carries: a digest of each value
    by name, privately; never a value. ``status`` records none."""
    city = legacy_city
    starter = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    city.procs.core_environ, city.procs.core_cgroup = systemd_core(city, starter, legacy=legacy)
    code, out, _ = run_command(city, "status")
    assert code == 0 and "started:   by the pack" in "\n".join(out)
    assert not lineage_path(city).exists()
    env = accept_packs_systemd_core(city, legacy=legacy)
    path = lineage_path(city)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {
        "digests": {key: coreid.value_digest(value) for key, value in env.items() if key not in core.SERVICE_KEYS}
    }
    assert env["GOCACHE"] not in path.read_text() and env["SSH_AUTH_SOCK"] not in path.read_text()


@pytest.mark.parametrize("legacy", [True, False], ids=["systemd-239", "systemd-255"])
def test_a_core_a_holder_of_the_packs_core_restarted_under_systemd_is_the_packs_by_lineage(legacy_city: City, legacy: bool) -> None:
    """hc writes a holder's whole environment into the file of the core it
    restarts (hc holder.rs, systemd.rs): names the pack never sets, the
    manager's block, with the values the pack recorded when it accepted
    that holder's core. No holder need still run, and the core it restarted
    passes the lineage on to its own holders."""
    city = legacy_city
    packs_core = accept_packs_systemd_core(city, legacy=legacy)
    restarted, city.procs.core_cgroup = systemd_core(city, holder_of(city, packs_core, legacy=legacy), legacy=legacy)
    city.procs.core_environ = restarted
    done = city.start("mc-b")
    assert done.code == 0, done.stderr
    city.procs.core_environ, city.procs.core_cgroup = systemd_core(city, holder_of(city, restarted, legacy=legacy), legacy=legacy)
    done = city.start("mc-c")
    assert done.code == 0, done.stderr


def test_a_holder_restarted_core_keeps_names_that_left_the_managers_block(legacy_city: City) -> None:
    """The manager's block had DISPLAY and WAYLAND_DISPLAY when the pack's
    core started, and lost them at logout: that core's holders still carry
    them, and so does the file of a core one of them restarts."""
    city = legacy_city
    packs_core = accept_packs_systemd_core(city, legacy=True, DISPLAY=":0", WAYLAND_DISPLAY="wayland-0")
    city.procs.core_environ, city.procs.core_cgroup = systemd_core(city, holder_of(city, packs_core, legacy=True), legacy=True)
    assert city.procs.core_environ["DISPLAY"] == ":0"
    done = city.start("mc-b")
    assert done.code == 0, done.stderr


def test_a_foreign_value_for_a_name_the_lineage_carries_is_refused(legacy_city: City) -> None:
    city = legacy_city
    holder = holder_of(city, accept_packs_systemd_core(city, legacy=True), legacy=True)
    theirs = dict(holder, SSH_AUTH_SOCK="/tmp/theirs/agent.sock")
    city.procs.core_environ, city.procs.core_cgroup = systemd_core(city, theirs, legacy=True)
    done = city.start("mc-b")
    assert done.code == 1 and "SSH_AUTH_SOCK" in done.stderr and "theirs" not in done.stderr


def test_the_lineage_never_lets_a_live_environment_in(legacy_city: City) -> None:
    """The lineage judges only a unit's file: a core judged by its live
    environment carries the manager's block, and is refused."""
    city = legacy_city
    accept_packs_systemd_core(city, legacy=True)
    city.procs.core_cgroup = "/user.slice/session-2.scope"
    done = city.start("mc-b")
    assert done.code == 1 and "GOCACHE" in done.stderr


@needs_proc
def test_with_no_lineage_a_holder_restarted_core_is_refused_whatever_holder_runs(
    legacy_city: City, started: List["subprocess.Popen[bytes]"]
) -> None:
    """No start of the pack accepted the core that holder's environment came
    from: a live holder of the city vouches for nothing."""
    city = legacy_city
    starter = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    packs_core, _ = systemd_core(city, starter, legacy=True)
    holder = holder_of(city, packs_core, legacy=True)
    run_holder(started, city, holder)
    city.procs.core_environ, city.procs.core_cgroup = systemd_core(city, holder, legacy=True)
    done = city.start("mc-a")
    assert done.code == 1 and "GOCACHE" in done.stderr
    assert not lineage_path(city).exists()


def foreign_systemd_core(city: City, *, legacy: bool) -> Tuple[Dict[str, str], str, Dict[str, str]]:
    """A core someone else started under systemd with the city's discovery
    tuple and their own key: its environ, its control group, and the
    environ of a holder of the city's socket it spawns, run by this user."""
    starter = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    env, cgroup = systemd_core(city, dict(starter, OPENAI_API_KEY="sk-theirs"), legacy=legacy)
    return env, cgroup, holder_of(city, env, legacy=legacy)


@needs_proc
@pytest.mark.parametrize("legacy", [True, False], ids=["systemd-239", "systemd-255"])
def test_a_holder_a_foreign_core_spawned_never_vouches_for_that_core(
    legacy_city: City, started: List["subprocess.Popen[bytes]"], legacy: bool
) -> None:
    city = legacy_city
    accept_packs_systemd_core(city, legacy=legacy)
    city.procs.core_environ, city.procs.core_cgroup, holder = foreign_systemd_core(city, legacy=legacy)
    done = city.start("mc-b")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr
    run_holder(started, city, holder)
    done = city.start("mc-b")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr


@needs_proc
@pytest.mark.parametrize("legacy", [True, False], ids=["systemd-239", "systemd-255"])
def test_a_core_a_holder_of_a_foreign_core_restarted_is_refused(
    legacy_city: City, started: List["subprocess.Popen[bytes]"], legacy: bool
) -> None:
    """That holder writes its own environment, the foreign one, into the file
    of the core it restarts, and still runs."""
    city = legacy_city
    accept_packs_systemd_core(city, legacy=legacy)
    _, _, holder = foreign_systemd_core(city, legacy=legacy)
    run_holder(started, city, holder)
    city.procs.core_environ, city.procs.core_cgroup = systemd_core(city, holder, legacy=legacy)
    done = city.start("mc-b")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr


# --- the process table, one process at a time ---------------------------------------------


def test_linux_reads_one_process_without_listing_the_table(tmp_path: Path) -> None:
    add_proc(tmp_path, 7, ppid=1, argv=["/opt/hc/herdr-core", "serve"], start=4321)
    source = LinuxProcs(str(tmp_path))
    found = source.process(7)
    assert found is not None and (found.pid, found.ppid, found.start) == (7, 1, "4321")
    assert source.process(8) is None


def test_ps_reads_one_process_as_its_snapshot_does() -> None:
    class Ps(PsProcs):
        def __init__(self) -> None:
            self.calls: List[Tuple[str, ...]] = []

        def _ps(self, *args: str) -> str:
            self.calls.append(args)
            return "  31     1   501 Ss   Mon Nov  9 08:00:00 2026 /opt/hc/herdr-core serve\n"

    source = Ps()
    found = source.process(31)
    assert found is not None and found.start == "Mon Nov 9 08:00:00 2026" and found.argv == ("/opt/hc/herdr-core", "serve")
    assert source.calls == [("-ww", "-o", "pid=,ppid=,uid=,stat=,lstart=,args=", "-p", "31")]
    assert source.process(32) is None


@pytest.mark.skipif(subprocess.run(["ps", "-o", "lstart=", "-p", "1"], capture_output=True, check=False).returncode != 0, reason="no ps lstart")
def test_a_ps_start_reads_the_same_in_every_time_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    """One process records the start, others compare it: the reader's zone
    or locale, or a change of the host's zone, must not change it."""
    seen = set()
    for zone in ("America/Los_Angeles", "America/New_York", "Asia/Kolkata"):
        monkeypatch.setenv("TZ", zone)
        time.tzset()
        found = PsProcs().process(os.getpid())
        assert found is not None
        seen.add((found.start, PsProcs().started_ms(found)))
    monkeypatch.delenv("TZ")
    time.tzset()
    assert len(seen) == 1, seen
    started_ms = next(iter(seen))[1]
    assert started_ms is not None and abs(started_ms - coreid.wall_ms()) < 24 * 3600 * 1000


# --- end to end: the pack's own executable and fake-hc's launchd placement -----------------


def _discovery(env: Dict[str, str]) -> Dict[str, str]:
    paths = resolve_paths(env)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": env["HOME"],
        "HC_SESSION": paths.session,
        "HC_SOCKET": paths.socket,
        "XDG_STATE_HOME": paths.state_root,
        "XDG_CONFIG_HOME": paths.config_home,
    }


def _foreign_core(env: Dict[str, str], placement_bin: str) -> None:
    """Someone else starts the city's core: the city's discovery tuple, their
    own environment."""
    theirs = dict(_discovery(env), OPENAI_API_KEY="sk-theirs")
    done = subprocess.run([placement_bin, "server", "start"], env=theirs, capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr


def _await_down(sock: str) -> None:
    raw_call(sock, "server.stop", {}, timeout=10.0)
    deadline = time.monotonic() + 15
    while os.path.exists(sock) and time.monotonic() < deadline:
        try:
            raw_call(sock, "hello", {}, timeout=1.0)
        except (OSError, ValueError):
            break
        time.sleep(0.05)


def _pack_core_env(env: Dict[str, str]) -> Dict[str, str]:
    """The allowlist the pack's own executable starts the core with."""
    request = OpRequest(
        op="t", args=(), stdin=b"", env=env, cancel=CancelToken(), deadline=Deadline.after(5), redactor=Redactor()
    )
    return core.core_env(OpContext(request, live_host(sys.executable)), env["GC_HC_TEST_BIN"])


@needs_proc
def test_the_pack_accepts_the_launchd_core_it_started_and_refuses_one_someone_else_started(short_tmp: Path, home_dir: Path) -> None:
    env = entry_env(short_tmp, home_dir)
    write_launcher(env["GC_HC_TEST_BIN"], placement="launchd")
    paths = resolve_paths(env)
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 0, done.stderr
        assert "HC_SOCKET" not in core_environ(paths.socket)
        pid = raw_call(paths.socket, "server.status", {})["result"]["pid"]
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        assert b"--hc-launchd" in argv and b"serve" not in argv
        again = invoke(env, "start", "mc-b", stdin=b'{"command":"cat"}')
        assert again.returncode == 0, again.stderr
        _await_down(paths.socket)
        _foreign_core(env, env["GC_HC_TEST_BIN"])
        refused = invoke(env, "start", "mc-c", stdin=b'{"command":"cat"}')
        assert refused.returncode == 1 and b"restart-core" in refused.stderr and b"sk-theirs" not in refused.stderr
    finally:
        teardown_cores(Path(paths.state_root))


@needs_proc
def test_the_pack_accepts_a_launchd_core_a_holder_of_the_city_restarted(
    short_tmp: Path, home_dir: Path, started: List["subprocess.Popen[bytes]"]
) -> None:
    env = entry_env(short_tmp, home_dir)
    write_launcher(env["GC_HC_TEST_BIN"], placement="launchd")
    paths = resolve_paths(env)
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 0, done.stderr
        _await_down(paths.socket)  # the core crashed
        holder = dict(_pack_core_env(env), HC_RUNTIME="1", XPC_SERVICE_NAME="0", _HC_RESPONSIBLE_PID="1")
        sock = corescan.holder_prefix(paths) + "0123abcd.sock"
        started.append(subprocess.Popen([env["GC_HC_TEST_BIN"], "hold", "--socket", sock], env=holder))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                raw_call(paths.socket, "hello", {}, timeout=1.0)
                break
            except (OSError, ValueError):
                time.sleep(0.05)
        restarted = raw_call(paths.socket, "server.status", {})["result"]["pid"]
        argv = Path(f"/proc/{restarted}/cmdline").read_bytes()
        assert f"hc-launchd-{started[0].pid}-".encode() in argv
        again = invoke(env, "start", "mc-b", stdin=b'{"command":"cat"}')
        assert again.returncode == 0, again.stderr
    finally:
        teardown_cores(Path(paths.state_root))


RACING_HC = """#!{python}
import os, subprocess, sys
real = {real!r}
if sys.argv[1:] == ["server", "start"]:
    theirs = {theirs!r}
    subprocess.run([real, "server", "start"], env=theirs, check=True, stdout=subprocess.DEVNULL)
os.execv(real, [real, *sys.argv[1:]])
"""
"""An hc whose ``server start`` loses the race: another starter's ``hc
server start`` brings the city's core up first, with its own environment,
and this one then finds it answering (hc ``client.rs`` ``connect_starting``
takes no lock for the starter)."""


@needs_proc
@pytest.mark.parametrize("placement", ["launchd", ""], ids=["launchd", "plain"])
def test_a_core_another_starter_brings_up_during_the_packs_start_is_refused(
    short_tmp: Path, home_dir: Path, placement: str
) -> None:
    env = entry_env(short_tmp, home_dir)
    real = env["GC_HC_TEST_BIN"] + "-real"
    write_launcher(real, placement=placement)
    theirs = dict(_discovery(env), OPENAI_API_KEY="sk-theirs")
    Path(env["GC_HC_TEST_BIN"]).write_text(RACING_HC.format(python=sys.executable, real=real, theirs=theirs))
    paths = resolve_paths(env)
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 1 and b"restart-core" in done.stderr and b"sk-theirs" not in done.stderr, done.stderr
        assert not list(Path(paths.state_root).glob(f"pack/*/{coreid.IDENTITY_FILE}"))
    finally:
        teardown_cores(Path(paths.state_root))
