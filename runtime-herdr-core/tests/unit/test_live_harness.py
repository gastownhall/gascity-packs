"""The live tier's harness logic, checked without a real herdr-core.

The live suites (``tests/live``) drive a pinned hc on throwaway CI runners
only. What decides whether they run, what they may kill, which outcome each
holder-crash case expects, and how a run cleans up is plain logic, and it is
checked here: against fake /proc trees, fake-hc as the hc binary, and only
processes these tests start themselves.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List

import pytest

import releasekit
from fakehc.cli import write_launcher
from fakehc.procfs import add_proc
from gc_runtime_herdr_core.herdrcore.infra_argv import is_infrastructure_argv
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs
from livekit import cases, guard, units
from livekit.fetch import FetchError, fetch_pinned, unverified
from livekit.hcrpc import HcRpc
from livekit.owned import NotOwned, Ownership
from livekit.pack import Pack
from livekit.scratch import Scratch, open_scratch

PACK_ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = PACK_ROOT / "tests" / "live"
CI = {"GITHUB_ACTIONS": "true"}


# --- refusal -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"CI": "true"},
        {"GITHUB_ACTIONS": "1"},
        {"GITHUB_ACTIONS": "TRUE"},
        {"HOME": "/home/me", guard.THROWAWAY_ENV: "1"},
        {"HOME": "/home/me", guard.THROWAWAY_ENV: "/home/other"},
        {"HOME": "", guard.THROWAWAY_ENV: ""},
        {guard.THROWAWAY_ENV: "/home/me"},
    ],
)
def test_the_harness_refuses_every_host_but_a_runner_or_an_explicit_throwaway(environ: Dict[str, str]) -> None:
    with pytest.raises(guard.Refused) as refused:
        guard.clearance(environ)
    assert "GITHUB_ACTIONS=true" in str(refused.value)
    assert guard.THROWAWAY_ENV in str(refused.value)


def test_a_github_runner_is_cleared() -> None:
    assert guard.clearance(CI).why == "GitHub Actions runner"


def test_a_throwaway_host_is_cleared_only_by_naming_its_home() -> None:
    cleared = guard.clearance({"HOME": "/home/me", guard.THROWAWAY_ENV: "/home/me"})
    assert "throwaway" in cleared.why


def test_live_runs_only_when_asked() -> None:
    assert guard.live_requested({guard.LIVE_ENV: "1"})
    assert not guard.live_requested({})
    assert not guard.live_requested({guard.LIVE_ENV: "true"})


def _live_pytest(env: Dict[str, str], tmp_path: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(LIVE_DIR), "-q", "-p", "no:cacheprovider"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _host_env(tmp_path: Path) -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in {"GITHUB_ACTIONS", guard.THROWAWAY_ENV, guard.LIVE_ENV}}
    env["HOME"] = str(tmp_path / "home")
    env["TMPDIR"] = str(tmp_path)
    return env


def test_the_live_suites_skip_unless_asked(tmp_path: Path) -> None:
    done = _live_pytest(_host_env(tmp_path), tmp_path)
    assert done.returncode in (0, 5), done.stdout + done.stderr
    assert "passed" not in done.stdout and "failed" not in done.stdout, done.stdout


def test_the_live_suites_refuse_a_maintainer_host_before_doing_anything(tmp_path: Path) -> None:
    env = _host_env(tmp_path)
    env[guard.LIVE_ENV] = "1"
    env[guard.HC_BIN_ENV] = str(tmp_path / "never-run")
    before = sorted(os.listdir(tmp_path))
    done = _live_pytest(env, tmp_path)
    assert done.returncode == guard.REFUSED_EXIT, done.stdout + done.stderr
    assert "refuses to run" in done.stdout + done.stderr
    assert sorted(os.listdir(tmp_path)) == before, "a refused run created files"


def test_fetch_hc_refuses_a_maintainer_host(tmp_path: Path) -> None:
    env = _host_env(tmp_path)
    done = subprocess.run(
        [sys.executable, str(LIVE_DIR / "fetch_hc.py"), str(tmp_path / "hc")],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == guard.REFUSED_EXIT, done.stderr
    assert "refuses to run" in done.stderr
    assert not (tmp_path / "hc").exists()


# --- the holder-crash matrix ---------------------------------------------------------


def test_k1_runs_every_case_on_both_lanes_and_k2_only_c_and_d_on_systemd() -> None:
    runs = {(r.case.name, r.kill, r.lane): r for r in cases.matrix()}
    for lane in ("plain", "systemd"):
        for name in "ABCD":
            assert runs[(name, "K1", lane)].deferred is None
    assert runs[("C", "K2", "systemd")].deferred is None
    assert runs[("D", "K2", "systemd")].deferred is None
    for name in "AB":
        reason = runs[(name, "K2", "systemd")].deferred
        assert reason is not None and "infrastructure scope" in reason
    assert not [key for key in runs if key[1] == "K2" and key[2] == "plain"]


def test_the_witness_dies_only_under_the_cgroup_kill() -> None:
    assert cases.witness_expectation("K1") == "survives"
    assert cases.witness_expectation("K2") == "dies"


def test_only_the_negative_control_is_swept() -> None:
    for run in cases.matrix():
        if run.deferred is not None:
            continue
        assert run.expect == ("swept" if run.case.name == "C" else "survives"), run


def test_the_cases_turn_the_launcher_and_the_infrastructure_scope_on_and_off() -> None:
    a, b, c, d = (cases.CASES[name] for name in "ABCD")
    assert (a.strip, a.rescope, a.infra_scope) == (True, True, True)
    assert (b.strip, b.rescope, b.infra_scope) == (True, False, True)
    assert (c.strip, c.rescope, c.infra_scope) == (False, False, False)
    assert (d.strip, d.rescope, d.infra_scope) == (True, True, False)


def test_placement_expectations_follow_the_holder_crash_matrix() -> None:
    for name in "ABCD":
        for role in cases.ROLES:
            assert cases.in_holder_cgroup(cases.CASES[name], role, "plain") is None
    on = {name: {role: cases.in_holder_cgroup(cases.CASES[name], role, "systemd") for role in cases.ROLES} for name in "ABCD"}
    assert on["A"] == {"watchdog": False, "dolt": False, "proxy": False}
    assert on["B"] == {"watchdog": False, "dolt": False, "proxy": True}
    assert on["C"] == {"watchdog": True, "dolt": True, "proxy": True}
    assert on["D"] == {"watchdog": False, "dolt": False, "proxy": False}


# --- units and cgroups ---------------------------------------------------------------


def test_unit_of_reads_the_innermost_unit() -> None:
    base = "/user.slice/user-1001.slice/user@1001.service"
    assert units.unit_of(f"{base}/app.slice/hc-hold-0a1b.service") == "hc-hold-0a1b.service"
    assert units.unit_of(f"{base}/gascity-agents.slice/run-r42.scope") == "run-r42.scope"
    assert units.unit_of(f"{base}/app.slice/hc-serve-gc-1.service/sub") == "hc-serve-gc-1.service"
    assert units.unit_of("/") is None
    assert units.in_slice(f"{base}/gascity-agents.slice/run-r42.scope", "gascity-agents.slice")
    assert not units.in_slice(f"{base}/app.slice/hc-hold-1.service", "gascity-agents.slice")


@pytest.mark.parametrize(
    "unit",
    ["hc-hold-*.service", "hc-serve-x.service", "user@1001.service", "hc-hold-.service", "hc-hold-a b.service", "--all", "hc-hold-x.slice"],
)
def test_k2_kills_only_one_named_holder_unit(unit: str) -> None:
    with pytest.raises(ValueError):
        units.k2_argv(unit)


def test_k2_argv_is_a_cgroup_wide_sigkill_of_the_unit() -> None:
    assert units.k2_argv("hc-hold-0a1b.service") == [
        "systemctl", "--user", "kill", "--kill-whom=all", "--signal=SIGKILL", "--", "hc-hold-0a1b.service",
    ]


def test_infra_scope_unit_names_carry_the_run() -> None:
    name = units.infra_unit("ab12cd", "A-K1")
    assert name.startswith("gc-hc-live-ab12cd-") and name.endswith(".scope")
    with pytest.raises(ValueError):
        units.infra_unit("ab12cd", "A K1")


# --- ownership --------------------------------------------------------------------------


@pytest.fixture
def fake_proc(tmp_path: Path) -> Path:
    root = tmp_path / "proc"
    add_proc(root, 1, ppid=0, argv=["init"])
    add_proc(root, 100, ppid=1, argv=["hc", "serve"], env={"XDG_STATE_HOME": "/tmp/hclive-x/state", "HC_RUNTIME": "1"})
    add_proc(root, 200, ppid=1, argv=["python3", "db-proxy-child"], env={"GC_HC_LIVE_RUN": "run1"})
    add_proc(root, 300, ppid=1, argv=["dolt", "sql-server"], env={"GC_HC_LIVE_RUN": "other"})
    add_proc(root, 400, ppid=1, argv=["sleep", "9"], start=777)
    add_proc(root, 500, ppid=1, argv=["hc", "serve"], env={"XDG_STATE_HOME": "/tmp/hclive-x/state-other"})
    return root


def test_ownership_is_the_run_mark_the_state_root_or_a_recorded_start(fake_proc: Path) -> None:
    own = Ownership("run1", "/tmp/hclive-x/state", LinuxProcs(str(fake_proc)))
    assert own.owns(100) and own.owns(200)
    assert not own.owns(300) and not own.owns(400) and not own.owns(500) and not own.owns(1)
    own.record(400)
    assert own.owns(400)
    add_proc(fake_proc, 400, ppid=1, argv=["sleep", "9"], start=778)  # the pid was reused
    assert not own.owns(400)
    assert own.owns(100, runtime_only=True) and not own.owns(200, runtime_only=True)


def test_runtime_processes_and_marked_processes_are_listed_apart(fake_proc: Path) -> None:
    own = Ownership("run1", "/tmp/hclive-x/state", LinuxProcs(str(fake_proc)))
    assert [p.pid for p in own.runtime()] == [100]
    assert [p.pid for p in own.marked()] == [200]


def test_a_core_carrying_the_run_mark_is_one_an_agent_started(tmp_path: Path) -> None:
    root = tmp_path / "proc"
    state = "/tmp/hclive-x/state"
    add_proc(root, 1, ppid=0, argv=["init"])
    # The pack's core and holder: the scratch root, an allowlisted env without the mark.
    add_proc(root, 100, ppid=1, argv=["herdr-core", "serve"], env={"XDG_STATE_HOME": state, "HC_RUNTIME": "1"})
    add_proc(root, 101, ppid=1, argv=["herdr-core", "hold"], env={"XDG_STATE_HOME": state, "HC_RUNTIME": "1"})
    # An agent and its stand-in: marked, but not hc runtime.
    add_proc(root, 200, ppid=1, argv=["python3", "agent.py"], env={"GC_HC_LIVE_RUN": "run1", "XDG_STATE_HOME": "/tmp/hclive-x/agent-state"})
    # hc's CLI autostarted a core from the agent's env on the city's own state root...
    add_proc(root, 300, ppid=1, argv=["herdr-core", "serve"], env={"XDG_STATE_HOME": state, "GC_HC_LIVE_RUN": "run1"})
    # ...or on the agent's own state directory.
    add_proc(root, 400, ppid=1, argv=["hc", "serve"], env={"XDG_STATE_HOME": "/tmp/hclive-x/agent-state", "GC_HC_LIVE_RUN": "run1", "HC_RUNTIME": "1"})
    # Another run's agent-started core is not this run's.
    add_proc(root, 500, ppid=1, argv=["hc", "serve"], env={"GC_HC_LIVE_RUN": "other", "HC_RUNTIME": "1"})
    own = Ownership("run1", state, LinuxProcs(str(root)))
    assert [p.pid for p in own.runtime_from_agents()] == [300, 400]


def test_core_status_refuses_a_holder_outside_the_scratch_root(
    scratch: Scratch, started: List["subprocess.Popen[bytes]"], monkeypatch: pytest.MonkeyPatch
) -> None:
    from livekit import crash
    from livekit.hcrpc import CoreStatus

    assert Pack(scratch).start("live-h", "exec sleep 300").code == 0
    real = HcRpc(scratch.paths().socket).status()
    assert crash.core_status(scratch).holders == real.holders
    stranger = _sleep({})
    started.append(stranger)
    monkeypatch.setattr(HcRpc, "status", lambda self: CoreStatus(pid=real.pid, version=real.version, holders=(stranger.pid,)))
    with pytest.raises(AssertionError, match="not hc runtime"):
        crash.core_status(scratch)
    assert not scratch.ownership.owns(stranger.pid), "a stranger listed as a holder was adopted"


def test_a_fresh_core_lists_no_holder_and_owned_core_does_not_need_one(scratch: Scratch) -> None:
    from livekit import crash

    paths = scratch.paths()
    os.makedirs(os.path.dirname(paths.socket), mode=0o700, exist_ok=True)
    env = dict(os.environ)
    env.update(scratch.hc_cli_env(paths.session, paths.socket))
    done = subprocess.run([scratch.hc_bin, "server", "start"], env=env, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    assert crash.wait_until(HcRpc(paths.socket).answers, 15)
    assert crash.owned_core(scratch).holders == ()
    with pytest.raises(AssertionError, match="no holder"):
        crash.core_status(scratch)


@pytest.fixture
def started() -> Iterator[List["subprocess.Popen[bytes]"]]:
    procs: List["subprocess.Popen[bytes]"] = []
    yield procs
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


def _sleep(env: Dict[str, str]) -> "subprocess.Popen[bytes]":
    return subprocess.Popen(["sleep", "60"], env=dict(env, PATH=os.environ.get("PATH", "/usr/bin:/bin")))


def test_signal_refuses_a_process_the_run_does_not_own(started: List["subprocess.Popen[bytes]"]) -> None:
    stranger = _sleep({})
    started.append(stranger)
    own = Ownership("run-x", "/nonexistent", LinuxProcs())
    with pytest.raises(NotOwned):
        own.signal(stranger.pid, signal.SIGKILL)
    time.sleep(0.1)
    assert stranger.poll() is None, "a process the run does not own was signalled"


def test_signal_kills_a_marked_process(started: List["subprocess.Popen[bytes]"]) -> None:
    marked = _sleep({"GC_HC_LIVE_RUN": "run-y"})
    started.append(marked)
    own = Ownership("run-y", "/nonexistent", LinuxProcs())
    _wait_for(lambda: own.owns(marked.pid))  # the environ is readable once exec is done
    own.signal(marked.pid, signal.SIGKILL)
    assert marked.wait(timeout=10) == -signal.SIGKILL


def test_signal_of_a_gone_pid_is_not_ownership(started: List["subprocess.Popen[bytes]"]) -> None:
    gone = _sleep({"GC_HC_LIVE_RUN": "run-z"})
    gone.kill()
    gone.wait(timeout=10)
    own = Ownership("run-z", "/nonexistent", LinuxProcs())
    with pytest.raises(NotOwned):
        own.signal(gone.pid, signal.SIGKILL)


def _wait_for(predicate: "object", timeout: float = 10.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if callable(predicate) and predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition never held")


# --- the job summary ----------------------------------------------------------------------


def _report(when: str, outcome: str, longrepr: object = None) -> pytest.TestReport:
    return pytest.TestReport("tests/live/test_x.py::test_y", ("x", 1, "y"), {}, outcome, longrepr, when)  # type: ignore[arg-type]


def test_the_summary_lists_calls_failed_setups_and_failed_teardowns() -> None:
    from livekit.plugin import summary_row

    assert summary_row(_report("call", "passed")) == ("test_y", "passed", "")
    assert summary_row(_report("setup", "passed")) is None
    assert summary_row(_report("teardown", "passed")) is None
    failed_setup = summary_row(_report("setup", "failed", "boom\nsetup broke"))
    assert failed_setup == ("test_y", "error (setup)", "setup broke")
    left = summary_row(_report("teardown", "failed", "x\nteardown left the run's processes or units behind"))
    assert left == ("test_y", "error (teardown)", "teardown left the run's processes or units behind")


# --- the pinned fetch ------------------------------------------------------------------------


def test_fetch_pinned_installs_the_verified_binary(tmp_path: Path) -> None:
    data = releasekit.archive(b"#!/bin/sh\nexit 0\n")
    releases = tmp_path / "releases"
    releasekit.publish(releases, "0.1.19", data)
    pin = releasekit.make_pin("0.1.19", releasekit.sha(data))
    binary = fetch_pinned(pin, str(tmp_path / "hc"), target=releasekit.TARGET, releases_dir=str(releases))
    assert Path(binary).read_bytes() == b"#!/bin/sh\nexit 0\n"
    assert os.access(binary, os.X_OK)


def test_only_the_fetched_pinned_binary_is_verified(tmp_path: Path) -> None:
    data = releasekit.archive(b"#!/bin/sh\nexit 0\n")
    releases = tmp_path / "releases"
    releasekit.publish(releases, "0.1.19", data)
    pin = releasekit.make_pin("0.1.19", releasekit.sha(data))
    binary = fetch_pinned(pin, str(tmp_path / "hc"), target=releasekit.TARGET, releases_dir=str(releases))
    assert unverified(binary, pin, target=releasekit.TARGET) is None

    stray = tmp_path / "elsewhere" / "herdr-core"
    stray.parent.mkdir()
    stray.write_bytes(b"#!/bin/sh\nexit 0\n")
    stray.chmod(0o755)
    assert unverified(str(stray), pin, target=releasekit.TARGET) is not None

    os.chmod(binary, 0o755)
    Path(binary).write_bytes(b"#!/bin/sh\nexit 1\n")  # tampered after the install
    assert unverified(binary, pin, target=releasekit.TARGET) is not None


def test_the_live_suites_refuse_an_unverified_hc_binary(tmp_path: Path, fake_bin: Path) -> None:
    env = _host_env(tmp_path)
    # A declared throwaway HOME (a temp dir) clears the guard; fake-hc is the
    # binary, and the run must stop at it before any scratch root exists.
    env.update({guard.LIVE_ENV: "1", guard.THROWAWAY_ENV: env["HOME"], guard.LANE_ENV: "plain", guard.HC_BIN_ENV: str(fake_bin)})
    env.pop("GITHUB_STEP_SUMMARY", None)
    done = subprocess.run(
        [sys.executable, "-m", "pytest", str(LIVE_DIR / "test_live_placement.py"), "-q", "-p", "no:cacheprovider"],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    assert done.returncode == 2, done.stdout + done.stderr
    assert "not the pinned, verified hc" in done.stdout + done.stderr


def test_fetch_pinned_refuses_an_asset_whose_sha256_differs_from_the_pin(tmp_path: Path) -> None:
    data = releasekit.archive()
    releases = tmp_path / "releases"
    releasekit.publish(releases, "0.1.19", data, manifest_sha="0" * 64)
    pin = releasekit.make_pin("0.1.19", "0" * 64)
    with pytest.raises(FetchError, match="sha256"):
        fetch_pinned(pin, str(tmp_path / "hc"), target=releasekit.TARGET, releases_dir=str(releases))
    assert not (tmp_path / "hc" / "0.1.19").exists()


def test_the_pack_pin_names_a_sha256_for_the_runner() -> None:
    from gc_runtime_herdr_core.herdrcore.pin import load_pin

    entry = load_pin().target("linux-x86_64")
    assert len(entry.sha256) == 64


# --- hc RPC, a scratch root and the pack against fake-hc -----------------------------------


@pytest.fixture
def fake_bin(short_tmp: Path) -> Path:
    path = short_tmp / "bin" / "herdr-core"
    path.parent.mkdir()
    write_launcher(str(path))
    return path


@pytest.fixture
def scratch(fake_bin: Path) -> Iterator[Scratch]:
    made = open_scratch(guard.clearance(CI), "plain", str(fake_bin), python=sys.executable)
    yield made
    made.close()


def test_a_scratch_root_is_private_and_short(scratch: Scratch) -> None:
    for path in (scratch.base, scratch.state_root, scratch.runtime_dir, scratch.spawn_root, scratch.work):
        assert os.path.isdir(path)
        assert os.stat(path).st_mode & 0o077 == 0, path
    assert len(scratch.paths().socket) < 100


def test_the_pack_env_carries_the_lane_and_never_the_callers_state(scratch: Scratch) -> None:
    env = scratch.pack_env(rescope=True)
    assert env["GC_HC_TEST"] == "1" and env["GC_HC_TEST_BIN"] == scratch.hc_bin
    assert env["GC_EXEC_STATE_DIR"] == scratch.state_root
    assert env["GC_HC_TEST_RUNTIME_DIR"] == scratch.runtime_dir  # plain lane: no user manager
    assert "GC_HC_TEST_USERSCOPE" not in env  # nothing to re-scope out of without one
    assert env["GC_HC_TEST_SPAWN_ROOT"] == scratch.spawn_root
    assert env["GC_EXEC_CITY_PATH"] == scratch.city_path


def test_the_systemd_lane_leaves_spawn_files_at_their_production_location(fake_bin: Path) -> None:
    made = open_scratch(guard.clearance(CI), "systemd", str(fake_bin), python=sys.executable)
    try:
        env = made.pack_env()
        assert "GC_HC_TEST_SPAWN_ROOT" not in env and "GC_HC_TEST_RUNTIME_DIR" not in env
        city_id = made.paths().city_id
        assert made.spawn_root == f"/run/user/{os.getuid()}/gc-herdr-core/{city_id}"
        assert not made.spawn_root.startswith(made.base)
    finally:
        assert made.close() == []


def test_teardown_stops_every_core_and_removes_the_root(fake_bin: Path) -> None:
    made = open_scratch(guard.clearance(CI), "plain", str(fake_bin), python=sys.executable)
    pack = Pack(made)
    answer = pack.start("live-a", f"exec sleep 300")
    assert answer.code == 0, answer.stderr
    rpc = HcRpc(made.paths().socket)
    status = rpc.status()
    assert status.holders and made.ownership.owns(status.pid, runtime_only=True)
    report = made.close()
    assert report == [], report
    assert not os.path.exists(made.base)
    with pytest.raises(OSError):
        rpc.status()


def test_teardown_reports_and_kills_a_runtime_process_that_outlives_the_stop(fake_bin: Path) -> None:
    made = open_scratch(guard.clearance(CI), "plain", str(fake_bin), python=sys.executable)
    straggler = subprocess.Popen(["sleep", "300"], env={"PATH": "/usr/bin:/bin", "XDG_STATE_HOME": made.state_root, "HC_RUNTIME": "1"})
    try:
        _wait_for(lambda: made.ownership.owns(straggler.pid, runtime_only=True))
        report = made.close(grace_s=0.5)
        assert any(str(straggler.pid) in line for line in report), report
        assert straggler.wait(timeout=10) == -signal.SIGKILL
    finally:
        if straggler.poll() is None:
            straggler.kill()
            straggler.wait()


def test_teardown_kills_the_runs_marked_survivors_without_complaint(fake_bin: Path) -> None:
    made = open_scratch(guard.clearance(CI), "plain", str(fake_bin), python=sys.executable)
    survivor = subprocess.Popen(["sleep", "300"], env={"PATH": "/usr/bin:/bin", "GC_HC_LIVE_RUN": made.run_id})
    try:
        _wait_for(lambda: made.ownership.owns(survivor.pid))
        assert made.close() == []
        assert survivor.wait(timeout=10) == -signal.SIGKILL
    finally:
        if survivor.poll() is None:
            survivor.kill()
            survivor.wait()


def test_hc_rpc_reads_holders_and_keeps_a_terminal(scratch: Scratch) -> None:
    pack = Pack(scratch)
    assert pack.start("live-k", "exec sleep 300").code == 0
    seen = pack.observe("live-k")
    assert seen.state == "running"
    address = seen.object["id"]
    rpc = HcRpc(scratch.paths().socket)
    rpc.keep(address, True)
    assert rpc.terminal(address).keep is True
    assert rpc.status().holders
    assert rpc.has_terminal(address) and not rpc.has_terminal("no-such-terminal")


def test_pack_kill_object_refuses_a_live_box_and_clears_a_dead_one(scratch: Scratch) -> None:
    pack = Pack(scratch)
    assert pack.start("live-o", "exec sleep 300").code == 0
    obj = pack.observe("live-o").object
    refused = pack.kill_object("live-o", obj)
    assert (refused.code, refused.stdout.strip()) == (0, "live")
    HcRpc(scratch.paths().socket).kill(obj["id"])
    dead = pack.wait_state("live-o", ("dead",), 10)
    assert dead.state == "dead" and dead.object == obj
    killed = pack.kill_object("live-o", dead.object)
    assert (killed.code, killed.stdout.strip()) == (0, "killed")
    assert pack.observe("live-o").state == "absent"


def test_restart_after_death_brings_a_dead_box_back(scratch: Scratch) -> None:
    pack = Pack(scratch)
    assert pack.start_agent("live-r").code == 0
    first = pack.observe("live-r").object
    HcRpc(scratch.paths().socket).kill(first["id"])
    again = pack.restart_after_death("live-r", timeout_s=20)
    assert again.state == "running" and again.object != first


# --- the agent and the infrastructure stand-ins ---------------------------------------------


def _agent(scratch: Scratch, name: str, **extra: str) -> "subprocess.Popen[bytes]":
    env = dict(scratch.agent_env(name, **extra), PATH=os.environ.get("PATH", "/usr/bin:/bin"))
    return subprocess.Popen([sys.executable, str(LIVE_DIR / "agent.py")], env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)


def test_the_agent_spawns_detached_infrastructure_with_gcs_argv(scratch: Scratch) -> None:
    agent = _agent(scratch, "a1", GC_HC_LIVE_SPAWN="infra,orphan")
    try:
        report = scratch.agent_report("a1", timeout_s=20, want=("infra", "orphan"))
        procs = LinuxProcs().snapshot()
        watchdog, dolt, proxy = (report.infra[role] for role in ("watchdog", "dolt", "proxy"))
        assert is_infrastructure_argv(procs[watchdog].argv), procs[watchdog].argv
        assert is_infrastructure_argv(procs[proxy].argv), procs[proxy].argv
        assert procs[dolt].ppid == watchdog
        assert is_infrastructure_argv(procs[report.orphan["fenced"]].argv)
        assert procs[report.orphan["sleep"]].argv[0].endswith("sleep")
        assert os.getsid(proxy) == proxy and os.getsid(report.orphan["sleep"]) == report.orphan["sleep"]
        assert scratch.ping_store(report.store_socket)
        assert report.pid == agent.pid
    finally:
        agent.kill()
        agent.wait(timeout=10)
    assert scratch.close() == []


def test_the_agents_witness_drops_hc_scope_and_keeps_the_run_mark(scratch: Scratch) -> None:
    agent = _agent(scratch, "a5", GC_HC_LIVE_SPAWN="witness", HC_SCOPE="12-abcdef")
    try:
        report = scratch.agent_report("a5", timeout_s=20, want=("witness",))
        assert report.witness is not None
        env = scratch.ownership.procs.environ(report.witness) or {}
        assert "HC_SCOPE" not in env and env.get("GC_HC_LIVE_RUN") == scratch.run_id
        assert os.getsid(report.witness) == report.witness
        procs = LinuxProcs().snapshot()
        ancestor = procs[report.witness].ppid
        while ancestor > 1 and ancestor in procs:
            assert ancestor != agent.pid, "the witness is the agent's descendant: hc's sweep would take it"
            ancestor = procs[ancestor].ppid
        assert scratch.ownership.alive(report.witness)
    finally:
        agent.kill()
        agent.wait(timeout=10)
    assert scratch.close() == []


def test_the_agent_logs_each_input_line_with_its_time(scratch: Scratch) -> None:
    agent = _agent(scratch, "a2")
    try:
        scratch.agent_report("a2", timeout_s=20)
        assert agent.stdin is not None
        agent.stdin.write(b"xxxTOKEN-1\n")
        agent.stdin.flush()
        _wait_for(lambda: "TOKEN-1" in scratch.input_text("a2"))
        lines = scratch.input_lines("a2")
        assert lines[-1].text == "xxxTOKEN-1" and lines[-1].at > 0
    finally:
        agent.kill()
        agent.wait(timeout=10)


def test_the_agent_runs_hc_from_its_path_on_request(scratch: Scratch, tmp_path: Path) -> None:
    bindir = tmp_path / "pathbin"
    bindir.mkdir()
    fake = bindir / "hc"
    fake.write_text("#!/bin/sh\necho 'hc: the city herdr-core is down' >&2\nexit 1\n")
    fake.chmod(0o755)
    env = dict(scratch.agent_env("a3"), PATH=f"{bindir}:/usr/bin:/bin")
    agent = subprocess.Popen([sys.executable, str(LIVE_DIR / "agent.py")], env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    try:
        scratch.agent_report("a3", timeout_s=20)
        probe = scratch.run_hc_in_agent("a3", timeout_s=20)
        assert probe.code == 1 and "down" in probe.stderr and probe.argv0 == str(fake)
    finally:
        agent.kill()
        agent.wait(timeout=10)


def test_the_store_stand_in_answers_until_killed(scratch: Scratch) -> None:
    agent = _agent(scratch, "a4", GC_HC_LIVE_SPAWN="infra")
    try:
        report = scratch.agent_report("a4", timeout_s=20, want=("infra",))
        assert scratch.ping_store(report.store_socket)
        scratch.ownership.signal(report.infra["dolt"], signal.SIGKILL)
        _wait_for(lambda: not scratch.ping_store(report.store_socket))
    finally:
        agent.kill()
        agent.wait(timeout=10)


def test_secret_scan_finds_a_canary_anywhere_under_the_roots(scratch: Scratch) -> None:
    nested = Path(scratch.state_root) / "herdr-core" / "x"
    nested.mkdir(parents=True)
    (nested / "terminals.json").write_bytes(b'{"env":{"K":"canary-123"}}')
    assert scratch.find_bytes(b"canary-123") == [str(nested / "terminals.json")]
    assert scratch.find_bytes(b"canary-999") == []


def test_newest_mtime_tolerates_spawn_files_that_vanish(tmp_path: Path) -> None:
    from test_live_secrets import newest_mtime

    kept = tmp_path / "a.json"
    kept.write_text("{}")
    os.utime(kept, (1000.0, 1000.0))
    assert newest_mtime([str(kept), str(tmp_path / "gone.json")]) == 1000.0
    assert newest_mtime([str(tmp_path / "gone.json")]) is None
    assert newest_mtime([]) is None


def test_ping_store_is_false_for_no_socket(scratch: Scratch) -> None:
    assert not scratch.ping_store(os.path.join(scratch.work, "absent.sock"))
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(os.path.join(scratch.work, "mute.sock"))
        sock.listen(1)
        assert not scratch.ping_store(os.path.join(scratch.work, "mute.sock"), timeout_s=0.3)


def test_the_live_report_is_json(scratch: Scratch) -> None:
    scratch.note("exactly-once", {"attempts": 1})
    assert json.loads(json.dumps(scratch.notes))["exactly-once"] == {"attempts": 1}


def test_teardown_removes_the_root_even_when_a_step_fails(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    made = open_scratch(guard.clearance(CI), "plain", str(fake_bin), python=sys.executable)

    def broken(problems: List[str]) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(made, "_stop_cores", broken)
    report = made.close()
    assert any("boom" in line for line in report), report
    assert not os.path.exists(made.base)


def test_a_scratch_root_needs_the_hosts_clearance(fake_bin: Path) -> None:
    with pytest.raises(TypeError):
        open_scratch("GITHUB_ACTIONS=true", "plain", str(fake_bin))  # type: ignore[arg-type]


# --- the suites' own code, run against fake-hc --------------------------------------------
#
# Most live suites need a real hc (holders, the sweep, a person's quiet
# hold). These need only what fake-hc models, so their harness code runs
# here end to end on the plain lane.


@pytest.mark.parametrize(
    "module, name",
    [
        ("test_live_secrets", "test_a_session_secret_leaves_no_trace_after_the_session_ends"),
        ("test_live_secrets", "test_a_secret_echoed_to_the_screen_is_gone_once_the_record_is"),
        ("test_live_foreign_core", "test_start_refuses_a_core_started_outside_the_pack"),
        ("test_live_placement", "test_the_lane_places_the_core_holders_and_agents_as_named"),
    ],
)
def test_live_suite_runs_against_fake_hc(fake_bin: Path, module: str, name: str) -> None:
    import importlib

    suite = getattr(importlib.import_module(module), name)
    made = open_scratch(guard.clearance(CI), "plain", str(fake_bin), python=sys.executable)
    try:
        suite(made)
    finally:
        report = made.close()
    assert report == [], report
