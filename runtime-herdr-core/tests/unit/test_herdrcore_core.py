"""The city's core: the allowlist environment it starts with, the pack-owned
hc config, refusing a core someone else started, and the kick a read sends
when the core is down."""

from __future__ import annotations

import json
import os
import pwd
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

import pytest
from cityharness import City
from conftest import stop_cores
from fakehc.cli import write_launcher
from fakehc.rawclient import raw_call

from gc_runtime_herdr_core.hc.paths import resolve_paths
from gc_runtime_herdr_core.herdrcore import core
from gc_runtime_herdr_core.rpp.ops import OpError
from gc_runtime_herdr_core.herdrcore.config import HC_CONFIG_TOML, ConfigError, pinned_binary, resolve_hc_binary

PACK_ROOT = Path(__file__).resolve().parents[2]
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"


def test_core_env_is_the_allowlist(city: City) -> None:
    ctx = city.context(extra={"LANG": "C.UTF-8", "LC_ALL": "C", "ANTHROPIC_API_KEY": "sk-x", "GC_CITY": "/c", "HOME": "/elsewhere"})
    run_user = city.root / "run-user"
    run_user.mkdir()
    (run_user / "bus").write_text("")
    env = core.core_env(ctx, "/opt/hc/0.1.19/herdr-core", run_user=str(run_user))
    assert env == {
        "HOME": str(city.home),
        "USER": env["USER"],
        "LOGNAME": env["USER"],
        "PATH": "/opt/hc/0.1.19:/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C",
        "HC_SESSION": city.paths.session,
        "HC_SOCKET": city.paths.socket,
        "XDG_STATE_HOME": city.paths.state_root,
        "XDG_CONFIG_HOME": city.paths.config_home,
        "XDG_RUNTIME_DIR": str(run_user),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={run_user}/bus",
    }
    no_manager = core.core_env(ctx, "/b/herdr-core", run_user=str(city.root / "absent"))
    assert "XDG_RUNTIME_DIR" not in no_manager and "DBUS_SESSION_BUS_ADDRESS" not in no_manager


def _expected() -> Dict[str, str]:
    return {
        "HOME": "/h",
        "USER": "u",
        "LOGNAME": "u",
        "PATH": "/b:/usr/bin",
        "HC_SESSION": "gc-1",
        "HC_SOCKET": "/r/s.sock",
        "XDG_STATE_HOME": "/r",
        "XDG_CONFIG_HOME": "/r/hc-config",
    }


def test_foreign_reason_accepts_the_packs_own_core() -> None:
    actual = dict(_expected(), HC_RUNTIME="1", LC_CTYPE="C")
    assert core.foreign_reason(actual, _expected()) is None


@pytest.mark.parametrize("key", ["HC_SESSION", "HC_SOCKET", "XDG_STATE_HOME", "XDG_CONFIG_HOME"])
def test_foreign_reason_on_another_discovery_tuple(key: str) -> None:
    actual = dict(_expected(), **{key: "/other"})
    reason = core.foreign_reason(actual, _expected())
    assert reason is not None and key in reason and "/other" not in reason


def test_foreign_reason_on_variables_the_pack_never_sets() -> None:
    actual = dict(_expected(), ANTHROPIC_API_KEY="sk-secret", SHELL="/bin/zsh")
    reason = core.foreign_reason(actual, _expected())
    assert reason is not None and "ANTHROPIC_API_KEY" in reason and "sk-secret" not in reason


def test_systemds_service_variables_are_not_the_starters() -> None:
    actual = dict(_expected(), HC_RUNTIME="1", INVOCATION_ID="abc", MANAGERPIDFDID="7", NOTIFY_SOCKET="/x")
    assert core.foreign_reason(actual, _expected()) is None


def test_start_refuses_a_core_the_pack_did_not_start(city: City) -> None:
    assert city.procs.core_environ is not None
    city.procs.core_environ = dict(city.procs.core_environ, GC_CONTROLLER_TOKEN="leaked-token-1234")
    done = city.start("mc-a")
    assert done.code == 1
    assert "restart-core" in done.stderr and "GC_CONTROLLER_TOKEN" in done.stderr
    assert "leaked-token-1234" not in done.stderr
    assert city.fake.call_count("terminal.run") == 0  # type: ignore[union-attr]
    # Reads stay permissive.
    assert json.loads(city.run("observe", "mc-a").stdout) == {"state": "absent"}


def test_start_refuses_when_the_cores_environment_is_unreadable(city: City) -> None:
    city.procs.core_environ = None
    done = city.start("mc-a")
    assert done.code == 1 and "restart-core" in done.stderr


def test_start_refuses_a_core_listening_elsewhere(city: City, short_tmp: Path) -> None:
    other = short_tmp / "o.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(other))
    listener.listen(1)
    try:
        Path(city.paths.core_lock).write_text(str(other))
        done = city.start("mc-a")
        assert done.code == 1 and str(other) in done.stderr
    finally:
        listener.close()
    Path(city.paths.core_lock).write_text(str(short_tmp / "stale.sock"))  # nobody listens: stale
    assert city.start("mc-a").code == 0


def test_hc_binary_resolution(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state = tmp_path / "state"
    state.mkdir()
    pinned = Path(pinned_binary(lambda: str(home)))
    assert pinned == home / ".local/share/gc-runtime-herdr-core/hc/0.1.19/herdr-core"
    with pytest.raises(ConfigError, match="hc not installed"):
        resolve_hc_binary({}, str(state), home=lambda: str(home))
    pinned.parent.mkdir(parents=True)
    pinned.write_text("#!/bin/sh\n")
    pinned.chmod(0o755)
    assert resolve_hc_binary({"PATH": "/usr/bin"}, str(state), home=lambda: str(home)) == str(pinned)
    chosen = tmp_path / "chosen-hc"
    chosen.write_text("#!/bin/sh\n")
    chosen.chmod(0o755)
    (state / "config.json").write_text(json.dumps({"hc_bin": str(chosen)}))
    assert resolve_hc_binary({}, str(state), home=lambda: str(home)) == str(chosen)
    # The test override needs GC_HC_TEST=1.
    assert resolve_hc_binary({"GC_HC_TEST_BIN": "/nope"}, str(state), home=lambda: str(home)) == str(chosen)
    (state / "config.json").write_text(json.dumps({"hc_bin": "relative/hc"}))
    with pytest.raises(ConfigError, match="absolute"):
        resolve_hc_binary({}, str(state), home=lambda: str(home))


def entry_env(tmp: Path, home: Path) -> Dict[str, str]:
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GC_EXEC_STATE_DIR": str(tmp / "R"),
        "GC_EXEC_CITY_PATH": "/cities/entry",
        "GC_HC_TEST": "1",
        "GC_HC_TEST_BIN": write_launcher(str(bindir / "herdr-core")),
        "ANTHROPIC_API_KEY": "sk-from-gcs-env",
        "LANG": "C.UTF-8",
    }


def invoke(env: Dict[str, str], *args: str, stdin: bytes = b"") -> "subprocess.CompletedProcess[bytes]":
    return subprocess.run(
        [sys.executable, "-I", "-S", str(ENTRY), *args], env=env, input=stdin, capture_output=True, timeout=60, check=False
    )


def core_environ(sock: str) -> Dict[str, str]:
    pid = raw_call(sock, "server.status", {})["result"]["pid"]
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    return dict(item.decode().split("=", 1) for item in raw.split(b"\0") if b"=" in item)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_start_starts_the_core_with_the_allowlist_and_the_packs_config(short_tmp: Path, home_dir: Path) -> None:
    env = entry_env(short_tmp, home_dir)
    paths = resolve_paths(env)
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 0, done.stderr
        started = core_environ(paths.socket)
        assert "ANTHROPIC_API_KEY" not in started and "GC_HC_TEST_BIN" not in started
        assert started["HC_SOCKET"] == paths.socket and started["XDG_CONFIG_HOME"] == paths.config_home
        assert started["HOME"] == pwd.getpwuid(os.getuid()).pw_dir  # the password database, never $HOME
        assert started["HC_RUNTIME"] == "1"
        assert Path(paths.config_file).read_text() == HC_CONFIG_TOML
        assert (Path(paths.config_file).parent / "templates").is_dir()
        assert Path(paths.core_lock).read_text() == paths.socket
        # A second start of another name reuses the running core.
        again = invoke(env, "start", "mc-b", stdin=b'{"command":"cat"}')
        assert again.returncode == 0, again.stderr
    finally:
        stop_cores(Path(paths.state_root))


def test_unscoped_ops_use_the_unscoped_bucket_never_the_cwd(short_tmp: Path, home_dir: Path) -> None:
    env = entry_env(short_tmp, home_dir)
    del env["GC_EXEC_CITY_PATH"]
    paths = resolve_paths(env)
    assert paths.city_key == "unscoped"
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 0, done.stderr
        assert invoke(env, "is-running", "mc-a").stdout.strip() == b"true"
    finally:
        stop_cores(Path(paths.state_root))


def test_a_failed_kick_backs_off(city: City) -> None:
    city.fake.close()  # type: ignore[union-attr]
    city.fake = None
    ctx = city.context()
    core.write_kick(ctx, core.KickRecord(at_ms=int(time.time() * 1000), ok=False, detail="boom"))
    assert core.kick(ctx) is False
    core.write_kick(ctx, core.KickRecord(at_ms=int(time.time() * 1000) - core.KICK_BACKOFF_MS - 1, ok=False, detail="old"))
    assert core.kick(ctx) is True
    deadline = time.monotonic() + 20
    while not os.path.exists(city.paths.socket) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert os.path.exists(city.paths.socket)


def test_no_kick_under_an_injected_fault(city: City) -> None:
    ctx = city.context(extra={"GC_RPP_FAULT": "unavailable"})
    assert core.kick(ctx) is False


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_attach_execs_hc_attach_and_reads_as_attached(short_tmp: Path, home_dir: Path) -> None:
    env = entry_env(short_tmp, home_dir)
    paths = resolve_paths(env)
    viewer = None
    try:
        assert invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}').returncode == 0
        assert invoke(env, "is-attached", "mc-a").stdout.strip() == b"false"
        viewer = subprocess.Popen(
            [sys.executable, "-I", "-S", str(ENTRY), "attach", "mc-a"], env=env, stdin=subprocess.DEVNULL
        )
        deadline = time.monotonic() + 15
        answer = b""
        while time.monotonic() < deadline:
            answer = invoke(env, "is-attached", "mc-a").stdout.strip()
            if answer == b"true":
                break
            time.sleep(0.1)
        assert answer == b"true"
        assert invoke(env, "attach", "nobody").returncode == 1
    finally:
        if viewer is not None:
            viewer.terminate()
            viewer.wait(timeout=10)
        stop_cores(Path(paths.state_root))


# --- a systemd-placed core ---------------------------------------------------------------

RECORDED_UNIT_KEYS = (
    # A transient user service shaped like hc's (RuntimeDirectory, KillMode=process),
    # systemd 255 on Ubuntu 24.04: its environ's key set, values not recorded.
    "DBUS_SESSION_BUS_ADDRESS GOCACHE GOMODCACHE GSM_SKIP_SSH_AGENT_WORKAROUND HOME INVOCATION_ID LANG "
    "LOGNAME MANAGERPID MEMORY_PRESSURE_WATCH MEMORY_PRESSURE_WRITE NPM_CONFIG_CACHE PATH PIP_CACHE_DIR "
    "PLAYWRIGHT_BROWSERS_PATH PROJECTS_ROOT RUNTIME_DIRECTORY SCCACHE_CACHE_SIZE SCCACHE_DIR SHELL "
    "SSH_AUTH_SOCK SYSTEMD_EXEC_PID TMPDIR USER UV_CACHE_DIR XDG_DATA_DIRS XDG_RUNTIME_DIR"
).split()


def systemd_unit(tmp: Path, expected: Dict[str, str], file_env: Dict[str, str]) -> Dict[str, str]:
    """A systemd-placed core's environ: the user manager's block, systemd's
    service variables, and the unit's EnvironmentFile (written as hc writes it)."""
    run = tmp / "run-user"
    unit_dir = run / "hc-serve-0a1b2c3d"
    unit_dir.mkdir(parents=True, mode=0o700)
    (unit_dir / "environment").write_text(core.format_environment_file(file_env))
    (unit_dir / "environment").chmod(0o600)
    actual = {key: f"manager-{key.lower()}" for key in RECORDED_UNIT_KEYS}
    actual.update(file_env)
    actual["RUNTIME_DIRECTORY"] = str(unit_dir)
    return actual


def unit_file_env(expected: Dict[str, str], run: Path) -> Dict[str, str]:
    return dict(expected, XDG_RUNTIME_DIR=str(run), HC_RUNTIME="1")


def test_the_packs_own_systemd_placed_core_is_accepted(tmp_path: Path) -> None:
    expected = dict(_expected(), XDG_RUNTIME_DIR=str(tmp_path / "run-user"))
    actual = systemd_unit(tmp_path, expected, unit_file_env(expected, tmp_path / "run-user"))
    assert core.foreign_reason(actual, expected) is None


def test_a_systemd_placed_core_started_with_secrets_is_refused(tmp_path: Path) -> None:
    expected = dict(_expected(), XDG_RUNTIME_DIR=str(tmp_path / "run-user"))
    started = dict(unit_file_env(expected, tmp_path / "run-user"), ANTHROPIC_API_KEY="sk-secret")
    actual = systemd_unit(tmp_path, expected, started)
    reason = core.foreign_reason(actual, expected)
    assert reason is not None and "ANTHROPIC_API_KEY" in reason and "sk-secret" not in reason


def test_a_systemd_placed_core_without_its_environment_file_is_refused(tmp_path: Path) -> None:
    expected = dict(_expected(), XDG_RUNTIME_DIR=str(tmp_path / "run-user"))
    actual = systemd_unit(tmp_path, expected, unit_file_env(expected, tmp_path / "run-user"))
    (Path(actual["RUNTIME_DIRECTORY"]) / "environment").unlink()
    reason = core.foreign_reason(actual, expected)
    assert reason is not None and "environment file" in reason


def test_a_runtime_directory_outside_the_users_runtime_dir_is_refused(tmp_path: Path) -> None:
    expected = dict(_expected(), XDG_RUNTIME_DIR=str(tmp_path / "elsewhere"))
    actual = systemd_unit(tmp_path, expected, unit_file_env(expected, tmp_path / "elsewhere"))
    assert core.foreign_reason(actual, expected) is not None


def test_environment_file_round_trips_hcs_quoting() -> None:
    env = {"EMPTY": "", "SECRET": " leading\tspaces\n\"quotes\" 'single' \\slash $dollar `ticks`\r\ntrailing "}
    text = core.format_environment_file(env)
    # hc's own fixture (platform/systemd.rs environment_file test).
    assert text == "EMPTY=\"\"\nSECRET=\" leading\tspaces\n\\\"quotes\\\" 'single' \\\\slash \\$dollar \\`ticks\\`\r\ntrailing \"\n"
    assert core.parse_environment_file(text) == env
    assert core.parse_environment_file('BROKEN="no end') is None


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_start_accepts_its_own_core_when_fake_hc_places_it_like_systemd(short_tmp: Path, home_dir: Path) -> None:
    env = entry_env(short_tmp, home_dir)
    run_user = short_tmp / "run-user"
    run_user.mkdir(mode=0o700)
    env["GC_HC_TEST_RUNTIME_DIR"] = str(run_user)
    write_launcher(env["GC_HC_TEST_BIN"], systemd=True)
    paths = resolve_paths(env)
    try:
        done = invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}')
        assert done.returncode == 0, done.stderr
        started = core_environ(paths.socket)
        assert "RUNTIME_DIRECTORY" in started and "INVOCATION_ID" in started and "SHELL" in started
        assert started["XDG_RUNTIME_DIR"] == str(run_user)
        # A unit started by someone else (its environment file names a secret) is refused.
        unit_file = Path(started["RUNTIME_DIRECTORY"]) / "environment"
        unit_file.write_text(unit_file.read_text() + 'OPENAI_API_KEY="sk-x"\n')
        refused = invoke(env, "start", "mc-b", stdin=b'{"command":"cat"}')
        assert refused.returncode == 1 and b"OPENAI_API_KEY" in refused.stderr and b"sk-x" not in refused.stderr
    finally:
        stop_cores(Path(paths.state_root))


def test_the_pack_config_must_be_a_private_regular_file(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    real = tmp_path / "elsewhere.json"
    real.write_text(json.dumps({"hc_bin": "/usr/bin/true"}))
    (state / "config.json").symlink_to(real)
    with pytest.raises(ConfigError, match="symlink"):
        resolve_hc_binary({}, str(state), home=lambda: str(tmp_path))


def test_whitespace_in_discovery_paths_is_refused_where_environments_read_lossily(city: City) -> None:
    ctx = city.context()
    core.check_discovery_paths({"HC_SOCKET": "/a b/s.sock", "HC_SESSION": "gc-1"}, lossy=False)
    with pytest.raises(OpError, match="whitespace"):
        core.check_discovery_paths({"HC_SOCKET": "/a b/s.sock", "HC_SESSION": "gc-1"}, lossy=True)
    core.check_discovery_paths(ctx.paths.discovery_env(), lossy=True)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_attach_refuses_while_the_core_is_down(short_tmp: Path, home_dir: Path) -> None:
    env = entry_env(short_tmp, home_dir)
    paths = resolve_paths(env)
    try:
        assert invoke(env, "start", "mc-a", stdin=b'{"command":"cat"}').returncode == 0
        ok_before = invoke(env, "is-running", "mc-a").stdout.strip()
        assert ok_before == b"true"
    finally:
        stop_cores(Path(paths.state_root))
    done = invoke(env, "attach", "mc-a")
    assert done.returncode == 1 and b"core" in done.stderr
    # Finding the core down kicks the pack's own start, never hc's CLI
    # autostart: the core that comes back carries only the allowlist.
    deadline = time.monotonic() + 20
    while not os.path.exists(paths.socket) and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        if os.path.exists(paths.socket):
            assert "ANTHROPIC_API_KEY" not in core_environ(paths.socket)
    finally:
        time.sleep(0.5)
        stop_cores(Path(paths.state_root))
