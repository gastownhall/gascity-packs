"""The harness's hc conversations, against fake-hc only."""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Iterator, List

import pytest

from fakehc import FakeHc
from fakehc.cli import write_launcher
from soakanalysis import hc_role
from soakhc import CoreTuple, HcError, HcRpc, Teardown, conf_teardown, hc_env, lock_free, parse_status_env, runtime_of, wait_answers
from soaklib import NotOwned, ProcFS, signal_owned

from .soaktestkit import ProcTree


def test_parse_status_env() -> None:
    text = "HC_SESSION=gc-hc-soak\nHC_SOCKET=/run/user/1000/hc/gc-hc-soak.sock\nXDG_CONFIG_HOME=/R/hc-config\nXDG_STATE_HOME=/R\n"
    core = parse_status_env(text)
    assert core == CoreTuple("gc-hc-soak", "/run/user/1000/hc/gc-hc-soak.sock", "/R", "/R/hc-config")
    assert core.state_dir == "/R/herdr-core/gc-hc-soak"
    with pytest.raises(HcError, match="HC_SOCKET"):
        parse_status_env("HC_SESSION=x\nXDG_STATE_HOME=/R\nXDG_CONFIG_HOME=/c\n")


def test_hc_env_is_clean_and_carries_the_tuple() -> None:
    core = CoreTuple("s", "/sock", "/R", "/R/hc-config")
    env = hc_env(core, "/h/hc/0.1.19/herdr-core", {"HOME": "/home/soak", "USER": "soak", "XDG_RUNTIME_DIR": "/run/user/1000", "SECRET_TOKEN": "x"})
    assert env["PATH"].startswith("/h/hc/0.1.19:") and env["HC_SOCKET"] == "/sock" and env["XDG_STATE_HOME"] == "/R"
    assert "SECRET_TOKEN" not in env and env["LOGNAME"] == "soak" and env["LANG"] == "C.UTF-8"


def test_server_status_from_fake_hc(short_tmp: Path) -> None:
    fake = FakeHc(str(short_tmp / "hc.sock"), version="0.1.19")
    fake.start()
    try:
        rpc = HcRpc(fake.socket_path)
        status = rpc.status()
        # hc v0.1.19 starts a holder on demand, for the first terminal.run:
        # a fresh core lists none. fake-hc's one holder is the core itself.
        assert status.pid == os.getpid() and status.version == "0.1.19" and status.holders == ()
        assert status.live == 0 and rpc.answers()
        rpc.call("terminal.run", {"argv": ["/bin/sh", "-c", "exec cat"], "cwd": str(short_tmp), "no_parent": True, "no_notify": True})
        running = rpc.status()
        assert running.holders == (os.getpid(),) and running.live == 1
        assert wait_answers(rpc, 5.0) is not None
        assert fake.call_count("hello") >= 1 and fake.call_count("server.status") == 2 and fake.call_count("terminal.run") == 1
        assert fake.schema_violations == []
    finally:
        fake.close()
    assert not HcRpc(fake.socket_path, timeout_s=1.0).answers()
    with pytest.raises(HcError):
        HcRpc(str(short_tmp / "nothing.sock"), timeout_s=1.0).status()


@pytest.fixture
def scratch(short_tmp: Path) -> Iterator[Dict[str, str]]:
    """A scratch state root with one fake-hc core started the way a
    conformance run leaves one: ``<root>/herdr-core/<session>/core.lock``."""
    root = short_tmp / "state"
    root.mkdir(mode=0o700)
    hc = write_launcher(str(short_tmp / "herdr-core"))
    env = {
        "HOME": str(short_tmp),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HC_SESSION": "conf1",
        "HC_SOCKET": str(short_tmp / "c1.sock"),
        "XDG_STATE_HOME": str(root),
        "XDG_CONFIG_HOME": str(root / "hc-config"),
    }
    started = subprocess.run([hc, "server", "start"], env=env, capture_output=True, text=True, timeout=60)
    assert started.returncode == 0, started.stderr
    yield {"root": str(root), "hc": hc, "home": str(short_tmp)}
    # Whatever a failing test left: only fake-hc cores of this scratch root.
    procfs = ProcFS()
    for proc in runtime_of(procfs, str(root), os.getuid()):
        try:
            signal_owned(proc.pid, signal.SIGKILL, proc.start, lambda pid: None if hc_role(proc) else "not hc", procfs)
        except NotOwned:
            pass


def wait_core(procfs: ProcFS, root: str) -> List[int]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        found = [p.pid for p in runtime_of(procfs, root, os.getuid())]
        if found:
            return found
        time.sleep(0.05)
    return []


def test_conf_teardown_stops_the_scratch_core(scratch: Dict[str, str]) -> None:
    procfs = ProcFS()
    root = scratch["root"]
    assert wait_core(procfs, root)
    lock = Path(root, "herdr-core", "conf1", "core.lock")
    assert not lock_free(lock)
    result = conf_teardown(root, scratch["hc"], {"HOME": scratch["home"], "PATH": os.environ.get("PATH", "")}, procfs, unit_gone=lambda unit: True)
    assert result.ok, result.as_rec()
    assert [c["session"] for c in result.cores] == ["conf1"] and result.cores[0]["stop_exit"] == 0
    assert lock_free(lock) and runtime_of(procfs, root, os.getuid()) == []


def test_conf_teardown_kills_a_survivor_by_pid(scratch: Dict[str, str], tmp_path: Path) -> None:
    procfs = ProcFS()
    root = scratch["root"]
    pids = wait_core(procfs, root)
    assert pids
    deaf = tmp_path / "deaf-hc"
    deaf.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    deaf.chmod(0o755)
    result = conf_teardown(root, str(deaf), {"HOME": scratch["home"]}, procfs, wait_s=0.5, unit_gone=lambda unit: True)
    assert not result.ok
    assert [s["pid"] for s in result.survivors] == pids and all(s["killed"] for s in result.survivors)
    deadline = time.monotonic() + 10
    while runtime_of(procfs, root, os.getuid()) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert runtime_of(procfs, root, os.getuid()) == []


def test_conf_teardown_waits_for_a_lock_released_after_its_core_left(tmp_path: Path, proc_tree: ProcTree) -> None:
    root = tmp_path / "R"
    lock = root / "herdr-core" / "conf1" / "core.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text(str(tmp_path / "c1.sock") + "\n", encoding="utf-8")
    stop = tmp_path / "stop-hc"
    stop.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stop.chmod(0o755)
    procfs = ProcFS(str(proc_tree.root))  # no hc runtime left at all

    def hold() -> int:
        fd = os.open(str(lock), os.O_RDONLY)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def teardown(wait_s: float) -> Teardown:
        return conf_teardown(str(root), str(stop), {"HOME": str(tmp_path)}, procfs, wait_s=wait_s, unit_gone=lambda unit: True)

    release = threading.Timer(0.5, os.close, args=(hold(),))
    release.start()
    try:
        late = teardown(10.0)
    finally:
        release.join()
    assert late.ok and late.held_locks == [] and late.survivors == [], late.as_rec()
    fd = hold()
    try:
        held = teardown(0.3)
    finally:
        os.close(fd)
    assert not held.ok and held.held_locks == [str(lock)] and held.survivors == []


def test_conf_teardown_reports_units_left(scratch: Dict[str, str]) -> None:
    procfs = ProcFS()
    root = scratch["root"]
    assert wait_core(procfs, root)
    result = conf_teardown(root, scratch["hc"], {"HOME": scratch["home"]}, procfs, unit_gone=lambda unit: False)
    # fake-hc runs in the test's own cgroup, never in an hc-serve-* unit
    assert result.units_left == [] and result.ok
