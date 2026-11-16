"""fake-hc reads the core's config.toml as hc v0.1.19 does
(``crates/herdr-core/src/config.rs``): ``$XDG_CONFIG_HOME/herdr-core/config.toml``,
a missing file is the defaults, unknown keys are ignored (no
``deny_unknown_fields``), and a known key of the wrong type fails
``terminal.run`` (and ``hc attach``) with an error of kind ``config`` whose
message is ``<path>: <error>``."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterator

import pytest

from fakehc import FakeHc
from fakehc.rawclient import raw_call

from gc_runtime_herdr_core.herdrcore.config import HC_CONFIG_TOML

CLI = Path(__file__).resolve().parents[1] / "fakehc" / "cli.py"


@pytest.fixture
def config_home(short_tmp: Path) -> Path:
    home = short_tmp / "cfg"
    (home / "herdr-core").mkdir(parents=True)
    return home


@pytest.fixture
def core(short_tmp: Path, config_home: Path) -> Iterator[FakeHc]:
    fake = FakeHc(
        str(short_tmp / "hc.sock"),
        base_env={"PATH": "/usr/bin:/bin", "HOME": str(short_tmp), "XDG_CONFIG_HOME": str(config_home)},
    )
    fake.start()
    try:
        yield fake
    finally:
        fake.close()
    assert fake.schema_violations == [], "fake-hc schema guard:\n" + "\n".join(fake.schema_violations)


def write_config(config_home: Path, text: str) -> Path:
    path = config_home / "herdr-core" / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def run(fake: FakeHc, workdir: Path) -> Dict[str, Any]:
    params = {"argv": ["/bin/sh", "-c", "exec sleep 30"], "cwd": str(workdir), "no_parent": True, "no_notify": True}
    return raw_call(fake.socket_path, "terminal.run", params)


@pytest.mark.parametrize(
    "text, key",
    [
        ("notes = false\nnotes_quiet = true\n", "notes_quiet"),  # what the pack wrote before hc v0.1.19 refused it
        ('notes = "off"\n', "notes"),
        ('history_mb = "16"\n', "history_mb"),
        ("wait_timeout = true\n", "wait_timeout"),
        ("machine_timeout = [30]\n", "machine_timeout"),
        ("headless = 200\n", "headless"),
        ("detach_key = false\n", "detach_key"),
        ("socket = 1\n", "socket"),
        ('shell = "bash"\n', "shell"),
        ('shell = ["bash", 1]\n', "shell"),
    ],
)
def test_run_refuses_a_known_key_of_the_wrong_type(core: FakeHc, config_home: Path, short_tmp: Path, text: str, key: str) -> None:
    path = write_config(config_home, text)
    reply = run(core, short_tmp)
    assert "error" in reply, f"fake-hc ran a program under a config hc refuses: {text!r}"
    error = reply["error"]
    assert error["data"]["kind"] == "config"
    assert error["message"].startswith(f"{path}: ")
    assert key in error["message"]
    assert raw_call(core.socket_path, "terminal.list", {"all": True})["result"]["terminals"] == []


def test_run_refuses_a_file_that_is_not_toml(core: FakeHc, config_home: Path, short_tmp: Path) -> None:
    path = write_config(config_home, "notes = \n")
    error = run(core, short_tmp)["error"]
    assert error["data"]["kind"] == "config" and error["message"].startswith(f"{path}: ")


def test_run_accepts_what_hcs_serde_accepts(core: FakeHc, config_home: Path, short_tmp: Path) -> None:
    # An integer is a valid f64; unknown keys and tables are ignored.
    write_config(
        config_home,
        'notes = true\nnotes_quiet = 3\nhistory_mb = 5.5\nwait_timeout = 180\nmachine_timeout = 30.0\n'
        'headless = "200x120"\ndetach_key = "ctrl+]"\nshell = ["bash", "-l"]\nsocket = "/tmp/x.sock"\n'
        "someday = true\n[later]\nnotes = 1\n",
    )
    assert "result" in run(core, short_tmp)


def test_run_accepts_the_packs_generated_config(core: FakeHc, config_home: Path, short_tmp: Path) -> None:
    write_config(config_home, HC_CONFIG_TOML)
    reply = run(core, short_tmp)
    assert "result" in reply, reply


def test_a_missing_config_is_the_defaults(core: FakeHc, short_tmp: Path) -> None:
    assert "result" in run(core, short_tmp)


def test_a_fixed_config_is_read_fresh(core: FakeHc, config_home: Path, short_tmp: Path) -> None:
    write_config(config_home, "notes_quiet = true\n")
    assert run(core, short_tmp)["error"]["data"]["kind"] == "config"
    write_config(config_home, "notes_quiet = 3\n")
    assert "result" in run(core, short_tmp)


def test_attach_refuses_a_config_hc_refuses(short_tmp: Path, config_home: Path) -> None:
    path = write_config(config_home, "notes_quiet = true\n")
    env = {
        "HC_SOCKET": str(short_tmp / "hc.sock"),
        "XDG_STATE_HOME": str(short_tmp / "state"),
        "XDG_CONFIG_HOME": str(config_home),
    }
    done = subprocess.run(
        [sys.executable, str(CLI), "attach", "t1"], env=env, capture_output=True, text=True, timeout=30
    )
    assert done.returncode == 1
    error = json.loads(done.stderr)
    assert error["data"]["kind"] == "config" and error["message"].startswith(f"{path}: ")
