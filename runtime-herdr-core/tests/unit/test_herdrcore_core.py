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
from typing import Dict, FrozenSet

import pytest
from cityharness import City
from conftest import stop_cores
from fakehc.cli import write_launcher
from fakehc.rawclient import raw_call

from gc_runtime_herdr_core.hc.paths import resolve_paths
from gc_runtime_herdr_core.herdrcore import core
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


def test_a_systemd_unit_may_carry_the_user_managers_environment() -> None:
    actual = dict(_expected(), INVOCATION_ID="abc", JOURNAL_STREAM="8:1", DISPLAY=":0")
    managers: FrozenSet[str] = frozenset({"DISPLAY"})
    assert core.foreign_reason(actual, _expected(), manager_keys=lambda: managers) is None
    unread = core.foreign_reason(actual, _expected(), manager_keys=lambda: None)
    assert unread is not None and "manager" in unread
    stray = dict(actual, OPENAI_API_KEY="k")
    assert core.foreign_reason(stray, _expected(), manager_keys=lambda: managers) is not None


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
