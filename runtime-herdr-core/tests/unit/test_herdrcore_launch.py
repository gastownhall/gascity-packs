"""The agent launcher, its spawn files and the in-agent hc shim."""

from __future__ import annotations

import io
import json
import os
import socket
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

import pytest
from cityharness import City

from gc_runtime_herdr_core.herdrcore import envplan, launch, shim, spawnfile
from gc_runtime_herdr_core.herdrcore.spawnfile import Scope, SpawnSpec
from gc_runtime_herdr_core.rpp.cancel import CancelToken

PACK_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PACK_ROOT / "assets" / "bin" / "gc-herdr-core-launch"
OBJ = "0123456789abcdef0123456789abcdef"

CORE_SIDE = {
    "PATH": "/opt/hc/bin:/usr/bin:/bin",
    "HOME": "/home/u",
    "HC_SCOPE": "123-abc",
    "HC_SOCKET": "/r/hc.sock",
    "HC_SESSION": "gc-0123456789",
    "HC_TERMINAL_ID": "t4",
    "HC_TERMINAL_SOCKET": "/r/hc.sock",
    "XDG_STATE_HOME": "/r",
    "XDG_CONFIG_HOME": "/r/hc-config",
    "XDG_RUNTIME_DIR": "/run/user/1000",
    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
    "TERM": "xterm-256color",
}


# --- environment ------------------------------------------------------------------------


def test_agent_env_strips_hc_and_the_cores_own_state_and_applies_the_session() -> None:
    session = {
        "XDG_CONFIG_HOME": "/home/u/.config",
        "GC_AGENT": "mayor",
        "GC_CONTROLLER_TOKEN": "",
        "TERM": "",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }
    env = envplan.agent_env(dict(CORE_SIDE, GC_CONTROLLER_TOKEN="leaked"), session, "/r/shim/bin")
    for gone in ("HC_SCOPE", "HC_SOCKET", "HC_SESSION", "XDG_STATE_HOME", "GC_CONTROLLER_TOKEN", "TERM"):
        assert gone not in env, gone
    assert env["XDG_CONFIG_HOME"] == "/home/u/.config"
    assert env["HC_TERMINAL_ID"] == "t4" and env["HC_TERMINAL_SOCKET"] == "/r/hc.sock"
    assert env["PATH"] == "/r/shim/bin:/usr/local/bin:/usr/bin:/bin"
    assert env["GC_AGENT"] == "mayor"


def test_agent_env_keeps_the_users_runtime_dir_and_bus() -> None:
    # gc's session environment never sets them; keyrings, systemctl --user
    # and rootless containers need them, as a tmux pane has them.
    env = envplan.agent_env(CORE_SIDE, {}, "/s")
    assert env["XDG_RUNTIME_DIR"] == "/run/user/1000"
    assert env["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/run/user/1000/bus"
    assert "XDG_STATE_HOME" not in env and "XDG_CONFIG_HOME" not in env


def test_agent_env_never_carries_hc_scope_even_from_the_session() -> None:
    env = envplan.agent_env(CORE_SIDE, {"HC_SCOPE": "x", "HC_SOCKET": "/elsewhere"}, "/s")
    assert "HC_SCOPE" not in env and "HC_SOCKET" not in env


def test_launch_argv_without_a_user_manager_runs_the_command_in_place() -> None:
    assert envplan.launch_argv("claude --x", None, "/bin/zsh") == ["/bin/sh", "-c", "claude --x"]
    assert envplan.launch_argv("", None, "/bin/zsh") == ["/bin/zsh"]


SCOPE = Scope(
    systemd_run="/usr/bin/systemd-run",
    slice="gascity-agents.slice",
    runtime_dir="/run/user/1000",
    bus="unix:path=/run/user/1000/bus",
)


def test_launch_argv_rescopes_under_the_agent_slice_with_a_generic_description() -> None:
    argv = envplan.launch_argv("claude --secret-flag", SCOPE, "/bin/sh")
    assert argv == list(envplan.scope_prefix(SCOPE)) + ["/bin/sh", "-c", "claude --secret-flag"]
    assert argv[:8] == [
        "/usr/bin/systemd-run",
        "--user",
        "--scope",
        "--slice=gascity-agents.slice",
        "--collect",
        "--quiet",
        "--description=gascity agent",
        "--",
    ]


def test_systemd_run_reaches_the_manager_the_probe_used() -> None:
    env = envplan.scoped_env({"PATH": "/x", "XDG_RUNTIME_DIR": "/elsewhere"}, SCOPE)
    assert env["XDG_RUNTIME_DIR"] == "/run/user/1000" and env["DBUS_SESSION_BUS_ADDRESS"] == SCOPE.bus


def test_the_launcher_falls_back_to_an_unwrapped_launch(tmp_path: Path) -> None:
    out = tmp_path / "ran"
    gone = Scope(systemd_run=str(tmp_path / "no-systemd-run"), slice="gascity-agents.slice", runtime_dir=str(tmp_path), bus="")
    path = spawnfile.create(
        str(tmp_path), OBJ, SpawnSpec(env={}, command=f"echo ok > {out}", work_dir=str(tmp_path), shim_dir="/s", scope=gone)
    )
    done = subprocess.run(
        [sys.executable, "-I", "-S", str(LAUNCHER), path],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert out.read_text().strip() == "ok"
    assert b"not re-scoped" in done.stderr


# --- spawn files ----------------------------------------------------------------------------


def spec(**env: str) -> SpawnSpec:  # noqa: D103
    return SpawnSpec(env=env, command="true", work_dir="/", shim_dir="/s", scope=None)


def test_spawn_dir_is_tmpfs_and_private(tmp_path: Path) -> None:
    run_user = tmp_path / "run-user"
    run_user.mkdir()
    city_dir = Path(spawnfile.directory("c" * 64, run_user=str(run_user)))
    assert city_dir == run_user / "gc-herdr-core" / ("c" * 64)
    for level in (city_dir, city_dir.parent):
        assert stat.S_IMODE(level.stat().st_mode) == 0o700
    shm = tmp_path / "shm"
    shm.mkdir()
    fallback = Path(spawnfile.directory("d" * 64, run_user=str(tmp_path / "absent"), shm=str(shm), uid=os.getuid()))
    assert fallback == shm / f"gc-herdr-core-{os.getuid()}" / ("d" * 64)


def test_spawn_file_is_exclusive_private_and_never_follows_links(tmp_path: Path) -> None:
    path = Path(spawnfile.create(str(tmp_path), OBJ, spec(SECRET="s3cr3t-value")))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        spawnfile.create(str(tmp_path), OBJ, spec())
    path.unlink()
    target = tmp_path / "elsewhere"
    target.write_text("")
    os.symlink(target, path)
    with pytest.raises(OSError):
        spawnfile.create(str(tmp_path), OBJ, spec())
    assert target.read_text() == ""


def test_sweep_removes_only_old_spawn_files(tmp_path: Path) -> None:
    old = tmp_path / ("a" * 32 + ".json")
    new = tmp_path / ("b" * 32 + ".json")
    for path in (old, new):
        path.write_text("{}")
    past = time.time() - 300
    os.utime(old, (past, past))
    assert spawnfile.sweep(str(tmp_path)) == 1
    assert not old.exists() and new.exists()


def test_every_op_sweeps_its_citys_spawn_files(city: City) -> None:
    city.spawn_dir.mkdir(parents=True, exist_ok=True)
    stale = city.spawn_dir / ("e" * 32 + ".json")
    stale.write_text('{"env":{"TOKEN":"x"}}')
    past = time.time() - 300
    os.utime(stale, (past, past))
    assert city.run("is-running", "anyone").code == 0
    assert not stale.exists()


def test_launcher_unlinks_the_spawn_file_before_it_parses(tmp_path: Path) -> None:
    path = Path(spawnfile.create(str(tmp_path), OBJ, spec()))
    path.write_bytes(b"{not json")  # still 0600, ours
    err = io.StringIO()
    assert launch.main(["launch", str(path)], {}, stderr=err) == launch.EXIT_CANNOT_LAUNCH
    assert not path.exists()
    assert "malformed" in err.getvalue()


def test_launcher_refuses_a_shared_spawn_file(tmp_path: Path) -> None:
    path = Path(spawnfile.create(str(tmp_path), OBJ, spec()))
    path.chmod(0o644)
    err = io.StringIO()
    assert launch.main(["launch", str(path)], {}, stderr=err) == launch.EXIT_CANNOT_LAUNCH
    assert not path.exists() and "private" in err.getvalue()


def test_launcher_execs_the_agent_with_its_environment(tmp_path: Path) -> None:
    out = tmp_path / "env.json"
    command = f"{sys.executable} -c 'import json, os, sys; json.dump(dict(os.environ), open(sys.argv[1], \"w\"))' {out}"
    path = spawnfile.create(
        str(tmp_path),
        OBJ,
        SpawnSpec(env={"GC_AGENT": "a", "UNSET_ME": ""}, command=command, work_dir=str(tmp_path), shim_dir="/shim", scope=None),
    )
    base = dict(CORE_SIDE, PATH=os.environ.get("PATH", "/usr/bin:/bin"), UNSET_ME="x")
    done = subprocess.run([sys.executable, "-I", "-S", str(LAUNCHER), path], env=base, timeout=30, check=False)
    assert done.returncode == 0
    env: Dict[str, str] = json.loads(out.read_text())
    assert env["GC_AGENT"] == "a" and "UNSET_ME" not in env and "HC_SCOPE" not in env
    assert env["PATH"].startswith("/shim:") and env["PWD"] == str(tmp_path)
    assert not Path(path).exists()


# --- the shim ---------------------------------------------------------------------------------


def render_shim(tmp_path: Path, hc_bin: Path, sock: Path) -> Path:
    shim_dir = tmp_path / "shim" / "bin"
    shim.install(
        str(shim_dir),
        pack_dir=str(PACK_ROOT),
        python=sys.executable,
        hc_bin=str(hc_bin),
        env={"HC_SESSION": "gc-x", "HC_SOCKET": str(sock), "XDG_STATE_HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "c")},
    )
    return shim_dir / "hc"


def test_shim_refuses_while_the_core_is_down(short_tmp: Path) -> None:
    sentinel = short_tmp / "hc-ran"
    hc_bin = short_tmp / "herdr-core"
    hc_bin.write_text(f"#!/bin/sh\ntouch {sentinel}\n")
    hc_bin.chmod(0o755)
    hc = render_shim(short_tmp, hc_bin, short_tmp / "down.sock")
    done = subprocess.run([str(hc), "ls"], capture_output=True, timeout=30, check=False)
    assert done.returncode == 1
    assert b"down" in done.stderr
    assert not sentinel.exists(), "the hc CLI would have autostarted a core"
    assert stat.S_IMODE(hc.stat().st_mode) == 0o700
    assert (hc.parent / "herdr-core").read_bytes() == hc.read_bytes()


def test_shim_execs_hc_with_the_cores_tuple(short_tmp: Path) -> None:
    sock = short_tmp / "up.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(sock))
    listener.listen(4)
    accepter = threading.Thread(target=lambda: listener.accept(), daemon=True)
    accepter.start()
    out = short_tmp / "seen"
    hc_bin = short_tmp / "herdr-core"
    hc_bin.write_text(f'#!/bin/sh\necho "$HC_SOCKET $HC_SESSION ${{HC_SCOPE:-none}} $*" > {out}\n')
    hc_bin.chmod(0o755)
    hc = render_shim(short_tmp, hc_bin, sock)
    env = {"PATH": "/usr/bin:/bin", "HC_SOCKET": "/wrong.sock", "HC_SESSION": "default", "HC_SCOPE": "1-x"}
    done = subprocess.run([str(hc), "ls", "--json"], env=env, timeout=30, check=False)
    listener.close()
    assert done.returncode == 0
    assert out.read_text().split() == [str(sock), "gc-x", "none", "ls", "--json"]


def test_start_writes_the_shims_and_puts_them_first(city: City) -> None:
    out = city.root / "path.txt"
    config = json.dumps({"command": f"echo $PATH > {out}; exec cat"})
    assert city.start("mc-a", config).code == 0
    deadline = time.monotonic() + 10
    while not out.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    shim_dir = Path(city.paths.state_root) / "shim" / "bin"
    assert out.read_text().split(":")[0] == str(shim_dir)
    assert (shim_dir / "hc").exists() and (shim_dir / "herdr-core").exists()


# --- start cancels cleanly --------------------------------------------------------------------


def test_a_canceled_start_leaves_no_spawn_file_terminal_or_metadata(city: City) -> None:
    city.fake.delay_reply("terminal.run", 1.0)  # type: ignore[union-attr]
    cancel = CancelToken()
    results = []
    worker = threading.Thread(
        target=lambda: results.append(city.run("start", "mc-a", stdin=b'{"command":"cat"}', cancel=cancel)),
        daemon=True,
    )
    worker.start()
    deadline = time.monotonic() + 10
    while city.fake.call_count("terminal.run") == 0 and time.monotonic() < deadline:  # type: ignore[union-attr]
        time.sleep(0.01)
    cancel.cancel("terminated")
    worker.join(timeout=20)
    assert results and results[0].code == 1
    assert not city.spawn_dir.exists() or list(city.spawn_dir.iterdir()) == []
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and any(t["state"] == "live" for t in city.terminals()):
        time.sleep(0.05)
    assert [t for t in city.terminals() if t["state"] == "live"] == []
    assert list(Path(city.context().state_dir("meta")).iterdir()) == []


# --- the re-scope probe ---------------------------------------------------------------------

def scope_city(city: City) -> Dict[str, str]:
    run_user = city.root / "run-user"
    (run_user / "systemd").mkdir(parents=True)
    (run_user / "systemd" / "private").write_text("")
    (run_user / "bus").write_text("")
    log = city.root / "systemd-run.log"
    code = city.root / "systemd-run.code"
    code.write_text("0")
    fake = city.root / "systemd-run"
    # Like `systemd-run --scope`: record the call, then exec what follows `--`.
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> {log}\n'
        f"env | grep -E '^(XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS)=' >> {log}\n"
        f'code=$(cat {code}); [ "$code" = 0 ] || exit "$code"\n'
        'while [ "$1" != "--" ]; do shift; done; shift\n'
        'exec "$@"\n'
    )
    fake.chmod(0o755)
    return {
        "GC_HC_TEST_USERSCOPE": "1",
        "GC_HC_TEST_SYSTEMD_RUN": str(fake),
        "GC_HC_TEST_RUNTIME_DIR": str(run_user),
    }


def probes(city: City) -> List[str]:
    log = city.root / "systemd-run.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return [line for line in lines if line.startswith("--user") and line.endswith("/bin/true")]


def test_the_probe_runs_what_the_launcher_runs(city: City) -> None:
    extra = scope_city(city)
    done = city.run("start", "mc-a", stdin=b'{"command":"cat","env":{"GC_AGENT_SLICE":"team.slice"}}', extra=extra)
    assert done.code == 0, done.stderr
    [probe] = probes(city)
    assert probe.split()[:7] == ["--user", "--scope", "--slice=team.slice", "--collect", "--quiet", "--description=gascity", "agent"]
    log = (city.root / "systemd-run.log").read_text()
    assert f"XDG_RUNTIME_DIR={city.root / 'run-user'}" in log and "DBUS_SESSION_BUS_ADDRESS=unix:path=" in log


def test_gc_agent_slice_falls_back_to_gcs_own_environment(city: City) -> None:
    extra = dict(scope_city(city), GC_AGENT_SLICE="ops.slice")
    assert city.run("start", "mc-a", stdin=b'{"command":"cat"}', extra=extra).code == 0
    assert "--slice=ops.slice" in probes(city)[0]


def test_a_slice_that_is_not_a_slice_is_not_used(city: City) -> None:
    extra = scope_city(city)
    done = city.run("start", "mc-a", stdin=b'{"command":"cat","env":{"GC_AGENT_SLICE":"agents.service"}}', extra=extra)
    assert done.code == 0
    assert probes(city) == [] and "not re-scoped" in done.stderr


def test_a_failed_probe_warns_and_retries_after_a_backoff(city: City) -> None:
    import json as json_mod

    extra = scope_city(city)
    (city.root / "systemd-run.code").write_text("1")
    first = city.run("start", "mc-a", stdin=b'{"command":"cat"}', extra=extra)
    assert first.code == 0 and "not re-scoped" in first.stderr
    assert city.run("start", "mc-b", stdin=b'{"command":"cat"}', extra=extra).code == 0
    assert len(probes(city)) == 1, "a failure is kept for the backoff"
    cache = Path(city.context().state_file("userscope.json"))
    doc = json_mod.loads(cache.read_text())
    doc["at_ms"] -= 10 * 60 * 1000
    cache.write_text(json_mod.dumps(doc))
    (city.root / "systemd-run.code").write_text("0")
    third = city.run("start", "mc-c", stdin=b'{"command":"cat"}', extra=extra)
    assert len(probes(city)) == 2 and "not re-scoped" not in third.stderr


def test_a_success_is_kept_for_that_core_process_only(city: City) -> None:
    extra = scope_city(city)
    assert city.run("start", "mc-a", stdin=b'{"command":"cat"}', extra=extra).code == 0
    assert city.run("start", "mc-b", stdin=b'{"command":"cat"}', extra=extra).code == 0
    assert len(probes(city)) == 1
    city.fake.restart_core()  # type: ignore[union-attr]
    assert city.run("start", "mc-c", stdin=b'{"command":"cat"}', extra=extra).code == 0
    assert len(probes(city)) == 2


def test_a_scoped_launch_that_dies_drops_the_cached_success(city: City) -> None:
    extra = scope_city(city)
    assert city.run("start", "mc-a", stdin=b'{"command":"cat"}', extra=extra).code == 0
    cache = Path(city.context().state_file("userscope.json"))
    assert cache.exists()
    # The probe passes but the scoped launch itself fails: the agent dies at once.
    fake = Path(extra["GC_HC_TEST_SYSTEMD_RUN"])
    fake.write_text(fake.read_text().replace('exec "$@"', 'case "$*" in *"/bin/true") exec "$@" ;; esac; exit 1'))
    cache.unlink()
    done = city.run("start", "mc-b", stdin=b'{"command":"cat"}', extra=extra)
    assert done.code == 1 and "exited during startup" in done.stderr
    assert not cache.exists(), "a success the launch disproved is not kept"
