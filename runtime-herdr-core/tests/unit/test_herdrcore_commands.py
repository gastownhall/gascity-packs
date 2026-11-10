"""``gc herdr-core install|status|upgrade|restart-core`` against fake-hc.

The in-process city (cityharness) serves the city's socket with fake-hc, and
its process table reads the in-process core as having the environment the
test gives it. Cores the commands start are standalone fake-hc processes,
stopped at teardown. Nothing here downloads, installs or runs a real
herdr-core: install reads a stub release directory and the "binary" it
installs is fake-hc's launcher."""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

import pytest
from cityharness import City
from fakehc import FakeHc
from fakehc.cli import write_launcher
from releasekit import TARGET, make_pin, publish, sha

from gc_runtime_herdr_core.herdrcore import install as installer
from gc_runtime_herdr_core.herdrcore.commands import run_command
from gc_runtime_herdr_core.herdrcore.core import core_env
from gc_runtime_herdr_core.herdrcore.pin import HcPin, host_target, load_pin

PACK = Path(__file__).resolve().parents[2]


def command_env(city: City, *, test_bin: bool = True) -> Dict[str, str]:
    env = dict(city.env)
    env["GC_CITY_PATH"] = env.pop("GC_EXEC_CITY_PATH")
    if not test_bin:
        del env["GC_HC_TEST_BIN"]
    return env


def run(city: City, name: str, *args: str, env: Optional[Mapping[str, str]] = None) -> Tuple[int, List[str], List[str]]:
    out: List[str] = []
    err: List[str] = []
    code = run_command(name, list(args), env or command_env(city), city.host, out.append, err.append)
    return code, out, err


def test_status_env_prints_the_cores_discovery_tuple(city: City) -> None:
    code, out, _ = run(city, "status", "--env")
    assert code == 0
    assert out == [f"{k}={v}" for k, v in sorted(city.paths.discovery_env().items())]


def test_status_reports_pin_install_and_running_core(city: City) -> None:
    code, out, _ = run(city, "status")
    assert code == 0
    text = "\n".join(out)
    assert "pin:       herdr-core 0.1.19" in text
    assert "is not installed" in text
    assert "running:   herdr-core 0.1.19" in text
    assert "started:   by the pack" in text


def test_status_reports_a_core_started_outside_the_pack(city: City) -> None:
    assert city.procs.core_environ is not None
    city.procs.core_environ["SSH_AUTH_SOCK"] = "/tmp/agent"
    code, out, _ = run(city, "status")
    assert code == 0 and "started:   outside the pack" in "\n".join(out)


# --- restart-core ----------------------------------------------------------------------


def test_restart_core_refuses_a_core_that_is_not_the_citys(city: City) -> None:
    assert city.procs.core_environ is not None
    city.procs.core_environ["HC_SESSION"] = "someone-elses"
    code, _, err = run(city, "restart-core")
    assert code == 1 and "not this city's core" in err[0] and "HC_SESSION" in err[0]
    assert city.fake is not None and city.fake.call_count("server.stop") == 0


def test_restart_core_refuses_a_core_of_another_state_root(city: City) -> None:
    assert city.procs.core_environ is not None
    city.procs.core_environ["XDG_STATE_HOME"] = "/elsewhere"
    code, _, err = run(city, "restart-core")
    assert code == 1 and "XDG_STATE_HOME" in err[0]
    assert city.fake is not None and city.fake.call_count("server.stop") == 0


def test_restart_core_refuses_while_terminals_run(city: City) -> None:
    assert city.start("mc-a").code == 0
    code, _, err = run(city, "restart-core")
    assert code == 1 and "1 terminal(s)" in err[0] and "gc stop" in err[0]
    assert city.fake is not None and city.fake.call_count("server.stop") == 0


def test_restart_core_replaces_a_foreign_started_core_of_the_city(city: City) -> None:
    assert city.procs.core_environ is not None
    city.procs.core_environ["OPENAI_API_KEY"] = "sk-x"  # started with gc's tokens: foreign
    assert city.start("mc-a").code == 1  # start refuses it, naming restart-core
    code, out, err = run(city, "restart-core")
    assert code == 0, err
    assert city.fake is not None and city.fake.call_count("server.stop") == 1
    assert out[-1].startswith("started the city's core with ")
    # The new core is the pack's: a session starts on it.
    city.procs.core_environ = None
    assert city.start("mc-a").code == 0


# --- install and upgrade ------------------------------------------------------------------


def stub_release(city: City, tmp: Path, *, version: str) -> Tuple[Dict[str, str], Path]:
    """A release of fake-hc's launcher as the herdr-core binary, and the
    command environment that installs from it."""

    launcher = write_launcher(str(tmp / "herdr-core"), version=version)
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        tar.add(launcher, arcname="herdr-core")
    data = out.getvalue()
    releases = tmp / "releases"
    publish(releases, version, data)
    env = command_env(city, test_bin=False)
    env["GC_HC_TEST_RELEASES"] = str(releases)
    return env, Path(city.home) / ".local/share/gc-runtime-herdr-core/hc" / version / "herdr-core"


PinSetter = Callable[[str, str], None]


@pytest.fixture
def set_pin(monkeypatch: pytest.MonkeyPatch) -> PinSetter:
    """Swap the pack's pin for one naming a stub release (whose archive cannot
    hash to the real pin's sha256)."""
    if host_target() != TARGET:
        pytest.skip(f"the stub release is built for {TARGET}")
    holder: Dict[str, HcPin] = {}

    def fake_load(path: Optional[str] = None) -> HcPin:
        return holder["pin"]

    for module in ("pin", "config", "commands"):
        monkeypatch.setattr(f"gc_runtime_herdr_core.herdrcore.{module}.load_pin", fake_load)

    def setter(version: str, digest: str) -> None:
        holder["pin"] = make_pin(version, digest)

    return setter


def archive_sha(tmp: Path, version: str) -> str:
    return sha((tmp / "releases" / version / f"herdr-core-{TARGET}.tar.gz").read_bytes())


def test_install_command_installs_the_pinned_stub(city: City, set_pin: PinSetter, tmp_path: Path) -> None:
    env, binary = stub_release(city, tmp_path, version="0.1.19")
    set_pin("0.1.19", archive_sha(tmp_path, "0.1.19"))
    code, out, err = run(city, "install", env=env)
    assert code == 0, err
    assert out[0] == f"installed herdr-core 0.1.19 ({TARGET}) at {binary}"
    code, out, _ = run(city, "install", env=env)
    assert code == 0 and out[0].startswith("herdr-core 0.1.19 is already installed")


def test_install_command_refuses_a_sha_mismatch(city: City, set_pin: PinSetter, tmp_path: Path) -> None:
    env, binary = stub_release(city, tmp_path, version="0.1.19")
    set_pin("0.1.19", "e" * 64)
    code, _, err = run(city, "install", env=env)
    assert code == 1 and "differs from the pin" in err[0]
    assert not binary.parent.exists()


def test_upgrade_hands_the_core_over_and_keeps_its_sessions(city: City, set_pin: PinSetter, tmp_path: Path) -> None:
    env, binary = stub_release(city, tmp_path, version="0.1.19")
    set_pin("0.1.19", archive_sha(tmp_path, "0.1.19"))
    code, _, err = run(city, "install", env=env)
    assert code == 0, err
    # The city's core is the pack's own, started from the pinned binary.
    assert city.fake is not None
    city.fake.close()
    core = FakeHc(city.paths.socket, next_version_file=os.path.join(city.paths.state_dir, "fake-next-version"))
    core.start()
    city.fake = core
    city.procs.core_environ = core_env(city.context(), str(binary))
    pinned = {"GC_HC_TEST_BIN": ""}  # sessions start with the pinned binary
    assert city.run("start", "mc-a", stdin=b'{"command":"cat"}', extra=pinned).code == 0
    core.set_version("0.1.18")  # an older build, below the pin's minimum
    code, out, err = run(city, "upgrade", env=env)
    assert code == 0, err
    assert out[-1] == "handed the city's core over from herdr-core 0.1.18 to 0.1.19; its sessions kept running"
    assert core.call_count("server.restart") == 1 and core.call_count("server.stop") == 0
    assert [t["labels"] for t in city.terminals(all_records=False) if t["state"] == "live"] != []
    assert city.run("is-running", "mc-a", extra=pinned).text.strip() == "true"
    code, out, _ = run(city, "upgrade", env=env)
    assert code == 0 and out[-1] == "the city's core already runs herdr-core 0.1.19"


def test_upgrade_refuses_a_core_started_outside_the_pack(city: City, set_pin: PinSetter, tmp_path: Path) -> None:
    env, binary = stub_release(city, tmp_path, version="0.1.19")
    set_pin("0.1.19", archive_sha(tmp_path, "0.1.19"))
    assert city.fake is not None
    city.fake.set_version("0.1.18")
    city.procs.core_environ = dict(core_env(city.context(), str(binary)), GITHUB_TOKEN="ghp_x")
    code, _, err = run(city, "upgrade", env=env)
    assert code == 1 and "restart-core" in err[0] and "ghp_x" not in err[0]
    assert city.fake.call_count("server.restart") == 0


# --- the shipped entry points -----------------------------------------------------------


def test_commands_are_discovered_by_gcs_convention() -> None:
    for name in ("install", "status", "upgrade", "restart-core"):
        script = PACK / "commands" / name / "run.sh"
        assert os.access(script, os.X_OK)
        assert script.read_text().splitlines()[1].endswith(f'x-command {name} "$@"')
        assert (PACK / "commands" / name / "command.toml").read_text().startswith("description = ")


def test_status_env_through_the_shipped_script(city: City) -> None:
    env = command_env(city)
    done = subprocess.run([str(PACK / "commands" / "status" / "run.sh"), "--env"], env=env, capture_output=True, timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.decode().splitlines()
    assert f"HC_SESSION={city.paths.session}" in lines


def test_an_unknown_command_is_a_usage_error(city: City) -> None:
    code, _, err = run(city, "frobnicate")
    assert code == 2 and "unknown command" in err[0]


def test_the_real_pin_is_what_install_downloads(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    fetched: List[str] = []

    def fetch(url: str, limit: int) -> bytes:
        fetched.append(url)
        raise installer.InstallError("offline")

    monkeypatch.setattr(installer, "https_fetch", lambda url, limit, **_: fetch(url, limit))
    code, _, err = run(city, "install", env=command_env(city, test_bin=False))
    assert code == 1 and "offline" in err[0]
    assert fetched == [f"https://releases.herdr.dev/core/{load_pin().version}/manifest.json"]
