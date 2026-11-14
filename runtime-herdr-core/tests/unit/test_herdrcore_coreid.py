"""The core the pack started, known by its recorded identity.

hc starts a core with launchd on macOS, whose process environment is
launchd's (hc restores the starter's environment only in-process), and as a
systemd unit that, before systemd 244, has no ``RUNTIME_DIRECTORY`` to find
its environment file by. Neither core's environment says who started it, so
the pack records the core it started (pid, process start, core id) and
accepts a live core that matches all of it; any other core is judged by its
environment as before. Nothing here runs a real herdr-core."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from cityharness import City, make_city
from conftest import teardown_cores
from fakehc.cli import write_launcher
from fakehc.procfs import add_boot, add_proc
from fakehc.rawclient import raw_call
from test_herdrcore_commands import run as run_command
from test_herdrcore_core import core_environ, entry_env, invoke

from gc_runtime_herdr_core.hc.paths import resolve_paths
from gc_runtime_herdr_core.herdrcore import core, coreid, corescan
from gc_runtime_herdr_core.herdrcore.context import OpContext
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcError, PsProcs

needs_proc = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")

LAUNCHD_KEYS = (
    # What a launchd user agent's job runs with when its plist sets no
    # EnvironmentVariables (launchd.plist(5), launchd's own defaults): hc's
    # core on macOS (hc macos_launchd.rs) carries these and nothing of its
    # starter's. Values synthetic.
    "HOME LOGNAME PATH SHELL SSH_AUTH_SOCK TMPDIR USER XPC_FLAGS XPC_SERVICE_NAME __CF_USER_TEXT_ENCODING"
).split()

LEGACY_SYSTEMD_SERVICE = ("INVOCATION_ID", "JOURNAL_STREAM")
"""What systemd before 244 sets for a service: no RUNTIME_DIRECTORY (added in
244), SYSTEMD_EXEC_PID (248) or MEMORY_PRESSURE_* (254)."""


def launchd_environ() -> Dict[str, str]:
    env = {key: f"launchd-{key.lower()}" for key in LAUNCHD_KEYS}
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return env


def legacy_systemd_environ(city: City) -> Dict[str, str]:
    """A core hc placed under systemd 239: the user manager's block, the unit's
    EnvironmentFile (the pack's allowlist) and systemd's service variables,
    with nothing naming the unit's runtime directory."""
    started = core.core_env(city.context(), city.env["GC_HC_TEST_BIN"])
    env = {key: f"manager-{key.lower()}" for key in ("SHELL", "SSH_AUTH_SOCK", "XDG_DATA_DIRS", "TMPDIR", "GOCACHE")}
    env.update(started)
    env.update({"HC_RUNTIME": "1", "XDG_RUNTIME_DIR": "/run/user/1000"})
    env.update({key: "x" for key in LEGACY_SYSTEMD_SERVICE})
    return env


def record_running_core(city: City) -> OpContext:
    """Record the in-process core as the one the pack started."""
    ctx = city.context()
    assert coreid.record(ctx, ctx.client().server_status(), since_ms=0)
    return ctx


def identity_path(ctx: OpContext) -> Path:
    return Path(ctx.pack_state) / coreid.IDENTITY_FILE


def rewrite_identity(ctx: OpContext, **changes: object) -> None:
    path = identity_path(ctx)
    doc = json.loads(path.read_text())
    doc.update(changes)
    path.write_text(json.dumps(doc))


# --- the recorded identity ---------------------------------------------------------------


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


@pytest.mark.parametrize("environ", ["launchd", "systemd-legacy"])
def test_start_accepts_the_core_the_pack_started_whatever_its_environment_reads(city: City, environ: str) -> None:
    record_running_core(city)
    city.procs.core_environ = launchd_environ() if environ == "launchd" else legacy_systemd_environ(city)
    done = city.start("mc-a")
    assert done.code == 0, done.stderr


@pytest.mark.parametrize("environ", ["launchd", "systemd-legacy"])
def test_start_refuses_such_a_core_the_pack_did_not_start(city: City, environ: str) -> None:
    city.procs.core_environ = launchd_environ() if environ == "launchd" else legacy_systemd_environ(city)
    done = city.start("mc-a")
    assert done.code == 1 and "restart-core" in done.stderr
    assert city.fake is not None and city.fake.call_count("terminal.run") == 0


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
    city.procs.core_environ = launchd_environ()
    done = city.start("mc-a")
    assert done.code == 1 and "restart-core" in done.stderr
    assert not coreid.started_by_pack(ctx, ctx.client().server_status())


def test_a_forged_identity_file_is_not_trusted(city: City, tmp_path: Path) -> None:
    ctx = record_running_core(city)
    path = identity_path(ctx)
    city.procs.core_environ = launchd_environ()
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


def test_a_core_already_running_before_the_start_is_never_recorded(city: City) -> None:
    ctx = city.context()
    status = ctx.client().server_status()
    assert not coreid.record(ctx, status, since_ms=int(time.time() * 1000) + 60_000)
    assert not identity_path(ctx).exists()


def test_a_core_whose_start_cannot_be_read_is_never_recorded(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = city.context()
    status = ctx.client().server_status()

    def unreadable(pid: int) -> Proc:
        raise ProcError("hidden")

    monkeypatch.setattr(city.procs, "process", unreadable)
    assert not coreid.record(ctx, status, since_ms=0)
    monkeypatch.setattr(city.procs, "boot", lambda: None)
    assert not coreid.started_by_pack(ctx, status)


def test_status_and_restart_core_know_the_core_the_pack_started(city: City) -> None:
    record_running_core(city)
    city.procs.core_environ = launchd_environ()
    code, out, _ = run_command(city, "status")
    assert code == 0 and "started:   by the pack" in "\n".join(out)
    code, _, err = run_command(city, "restart-core")
    assert code == 0, err
    assert city.fake is not None and city.fake.call_count("server.stop") == 1


def test_a_core_that_does_not_answer_is_found_by_its_recorded_identity(short_tmp: Path, home_dir: Path) -> None:
    """A core that does not answer its socket is found in the process table
    by its environment, or, where that does not name its socket (launchd), by
    the identity the pack recorded."""
    proc_root = short_tmp / "proc"
    add_proc(proc_root, 1, ppid=0, argv=["/sbin/init"])
    add_boot(proc_root, "boot-1")
    add_proc(proc_root, 4242, ppid=1, argv=["/opt/hc/herdr-core", "serve"], start=777, env=launchd_environ())
    made = make_city(short_tmp, home_dir, procs=LinuxProcs(str(proc_root)))
    ctx = made.context()
    snapshot = made.procs.snapshot()
    assert corescan.core_processes(ctx, snapshot) == []
    coreid.write(ctx, coreid.CoreIdentity(pid=4242, start="777", boot="boot-1", core_id="c" * 32))
    assert [proc.pid for proc in corescan.core_processes(ctx, snapshot)] == [4242]
    assert not corescan.nothing_runs(ctx)
    coreid.write(ctx, coreid.CoreIdentity(pid=4242, start="778", boot="boot-1", core_id="c" * 32))
    assert corescan.core_processes(ctx, snapshot) == []


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


# --- end to end: the pack's own executable and fake-hc's launchd and old-systemd shapes ----


def _foreign_core(env: Dict[str, str], placement_bin: str) -> None:
    """Someone else starts the city's core: the city's discovery tuple, their
    own environment."""
    paths = resolve_paths(env)
    theirs = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": env["HOME"],
        "HC_SESSION": paths.session,
        "HC_SOCKET": paths.socket,
        "XDG_STATE_HOME": paths.state_root,
        "XDG_CONFIG_HOME": paths.config_home,
        "OPENAI_API_KEY": "sk-theirs",
    }
    if "GC_HC_TEST_RUNTIME_DIR" in env:
        theirs["XDG_RUNTIME_DIR"] = env["GC_HC_TEST_RUNTIME_DIR"]
    done = subprocess.run([placement_bin, "server", "start"], env=theirs, capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr


@needs_proc
@pytest.mark.parametrize("placement", ["launchd", "systemd-legacy"])
def test_the_pack_accepts_the_core_it_started_and_refuses_one_someone_else_started(
    short_tmp: Path, home_dir: Path, placement: str
) -> None:
    env = entry_env(short_tmp, home_dir)
    if placement == "systemd-legacy":
        run_user = short_tmp / "run-user"
        run_user.mkdir(mode=0o700)
        env["GC_HC_TEST_RUNTIME_DIR"] = str(run_user)
    write_launcher(env["GC_HC_TEST_BIN"], placement=placement)
    paths = resolve_paths(env)
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 0, done.stderr
        started = core_environ(paths.socket)
        assert "HC_SOCKET" not in started if placement == "launchd" else "RUNTIME_DIRECTORY" not in started
        again = invoke(env, "start", "mc-b", stdin=b'{"command":"cat"}')
        assert again.returncode == 0, again.stderr
        raw_call(paths.socket, "server.stop", {}, timeout=10.0)
        deadline = time.monotonic() + 15
        while os.path.exists(paths.socket) and time.monotonic() < deadline:
            try:
                raw_call(paths.socket, "hello", {}, timeout=1.0)
            except (OSError, ValueError):
                break
            time.sleep(0.05)
        _foreign_core(env, env["GC_HC_TEST_BIN"])
        refused = invoke(env, "start", "mc-c", stdin=b'{"command":"cat"}')
        assert refused.returncode == 1 and b"restart-core" in refused.stderr and b"sk-theirs" not in refused.stderr
    finally:
        teardown_cores(Path(paths.state_root))
