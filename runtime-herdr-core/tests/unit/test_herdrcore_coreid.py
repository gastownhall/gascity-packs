"""The pack's own core where its environment does not show who started it.

On macOS hc starts the core as a launchd job: the core runs as
``<hc> --hc-launchd <dir>/ready`` with launchd's environment, and ``<dir>``
names the pid of the process that asked for it. The pack records the core
its own hc asked for, and accepts a core a holder of the city restarted by
that holder's environment; any other launchd core is foreign. Under systemd
older than 244 a core's unit has no ``RUNTIME_DIRECTORY``, so the pack finds
its environment file through the core's control group. Everywhere the
environment can be judged, it is: a record never overrides it. Nothing here
runs a real herdr-core."""

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
from cityharness import City, make_city
from conftest import teardown_cores
from fakehc.cli import MANAGER_BLOCK, systemd_unit_env, write_launcher
from fakehc.procfs import add_boot, add_proc
from fakehc.rawclient import raw_call
from test_herdrcore_commands import run as run_command
from test_herdrcore_core import core_environ, entry_env, invoke

from gc_runtime_herdr_core.hc.paths import resolve_paths
from gc_runtime_herdr_core.herdrcore import admin, core, coreid, corescan
from gc_runtime_herdr_core.herdrcore.context import OpContext, live_host
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcError, PsProcs
from gc_runtime_herdr_core.herdrcore.usermanager import parse_busctl_environment
from gc_runtime_herdr_core.rpp.cancel import CancelToken, Deadline
from gc_runtime_herdr_core.rpp.ops import OpRequest
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
    for argv in (
        ("/opt/hc/herdr-core", "serve"),
        ("/opt/hc/herdr-core", "--hc-launchd"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-31-5-" + "a" * 32 + "/other"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-31-5-short/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-x-5-" + "a" * 32 + "/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/elsewhere-31-5-" + "a" * 32 + "/ready"),
        ("/opt/hc/herdr-core", "--hc-launchd", "/tmp/hc-launchd-0-5-" + "a" * 32 + "/ready"),
        ("a", "b", "c", "--hc-launchd", "/tmp/hc-launchd-31-5-" + "a" * 32 + "/ready"),
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
def test_a_launchd_core_whose_holder_carries_a_foreign_environment_is_refused(
    city: City, started: List["subprocess.Popen[bytes]"]
) -> None:
    pid = run_holder(started, city, holder_env(city, OPENAI_API_KEY="sk-theirs"))
    as_launchd_core(city, starter_pid=pid)
    done = city.start("mc-a")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr and "sk-theirs" not in done.stderr


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


def test_a_core_a_holder_restarted_under_old_systemd_is_accepted(legacy_city: City) -> None:
    """A holder runs as a unit with the manager's block, and hands it on in
    the environment file of the core it restarts (hc holder.rs, systemd.rs):
    the block's names are not the starter's."""
    city = legacy_city
    starter = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    run = city.env["GC_HC_TEST_RUNTIME_DIR"]
    packs_core, _ = systemd_unit_env(starter, run, legacy=True)
    holder, _ = systemd_unit_env(packs_core, run, legacy=True, verb="hold")
    env, cgroup = legacy_unit(city, holder)
    city.procs.core_environ = env
    city.procs.core_cgroup = cgroup
    refused = city.start("mc-a")
    assert refused.code == 1 and "GOCACHE" in refused.stderr, "the manager's block cannot be read: nothing excuses it"
    city.manager_block.append(frozenset(MANAGER_BLOCK))
    done = city.start("mc-a")
    assert done.code == 0, done.stderr
    city.procs.core_environ, city.procs.core_cgroup = legacy_unit(city, dict(holder, OPENAI_API_KEY="sk-theirs"))
    done = city.start("mc-b")
    assert done.code == 1 and "OPENAI_API_KEY" in done.stderr


def test_the_managers_block_is_read_as_busctl_prints_it() -> None:
    reply = 'as 3 "HOME=/home/u" "PATH=/usr/bin:/bin" "WEIRD=a\\"b\\\\c\\nd\\303\\251"\n'
    assert parse_busctl_environment(reply) == frozenset({"HOME", "PATH", "WEIRD"})
    assert parse_busctl_environment("as 0\n") == frozenset()
    for bad in ('as 2 "A=b"', 's "A=b"', 'as 1 "A=b', 'as 1 "A=b"x', 'as 1 "\\q"', "as x"):
        assert parse_busctl_environment(bad) is None, bad


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
