"""When the pack starts a city's core, and when it must not.

A core is started by a session ``start``, by a read's kick for a city that
has started and is not at rest, by ``server-stop`` removing the records hc
keeps, and by ``restart-core`` and ``upgrade``. Never by a read of a city no
core has ever run for (``gc doctor`` before ``gc start``): with nothing of
it running, that city reads empty, which is the truth, since hc keeps every
record, live or finished, under the session's state directory and creates
it before any core or holder of the session runs. Never for an op that
names no city. fake-hc only.
"""

from __future__ import annotations

import dataclasses
import json
import os
import stat
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pytest
from cityharness import MACHINE, City, make_city
from fakehc import FakeHc
from conftest import teardown_cores
from test_herdrcore_server import no_core_started, spawned, start_config, start_holder

from gc_runtime_herdr_core.hc.paths import HcPaths, ensure_dirs, resolve_paths
from gc_runtime_herdr_core.herdrcore import core
from gc_runtime_herdr_core.herdrcore.commands import run_command
from gc_runtime_herdr_core.herdrcore.context import OpContext
from gc_runtime_herdr_core.herdrcore.naming import KICK_OP
from gc_runtime_herdr_core.herdrcore.ops_table import build_ops
from gc_runtime_herdr_core.rpp.cancel import CancelToken, Deadline
from gc_runtime_herdr_core.rpp.ops import OpError, OpRequest
from gc_runtime_herdr_core.rpp.redact import Redactor
from gc_runtime_herdr_core.rpp.statedir import DOCTOR_CITY_ENV, OP_CITY_ENV

__all__ = ["spawned"]  # the fixture, imported for the tests below

OPS: Dict[str, Tuple[Tuple[str, ...], bytes]] = {
    "start": (("mc-a",), start_config("exec cat").encode()),
    "provision": (("mc-a",), start_config("exec cat").encode()),
    "launch": (("mc-a",), start_config("exec cat").encode()),
    "stop": (("mc-a",), b""),
    "kill-object": ((), b'{"session":"mc-a","box":"t1"}'),
    "observe": (("mc-a",), b"cat\n"),
    "inventory": ((), b""),
    "is-running": (("mc-a",), b""),
    "process-alive": (("mc-a",), b"cat\n"),
    "list-running": ((), b""),
    "is-attached": (("mc-a",), b""),
    "get-last-activity": (("mc-a",), b""),
    "peek": (("mc-a", "10"), b""),
    "get-meta": (("mc-a", "k"), b""),
    "set-meta": (("mc-a", "k"), b"v"),
    "remove-meta": (("mc-a", "k"), b""),
    "nudge": (("mc-a",), b"hello"),
    "send-keys": (("mc-a", "Enter"), b""),
    "interrupt": (("mc-a",), b""),
    "clear-scrollback": (("mc-a",), b""),
    "watch-startup": (("mc-a",), b""),
    "attach": (("mc-a",), b""),
    "copy-to": (("mc-a", "/etc/hostname"), b""),
    "server-stop": ((), b""),
    KICK_OP: ((), b""),
}
"""Every op but ``protocol``, with arguments and stdin it accepts."""


@pytest.fixture
def fresh(short_tmp: Path, home_dir: Path) -> Iterator[City]:
    """A city no core has ever run for: no hc state directory."""
    made = make_city(short_tmp, home_dir)
    try:
        yield made
    finally:
        teardown_cores(made.root / "R")
        if made.fake is not None:
            made.fake.close()


def no_trace_of_a_core(city: City) -> None:
    assert no_core_started(city, wait_s=2.0), "no op started a core"
    assert not os.path.exists(city.paths.state_dir), "nothing created the core's state"
    assert not os.path.exists(os.path.join(city.context().pack_state, core.KICK_FILE)), "no kick ran"


def test_every_op_is_covered(fresh: City) -> None:
    assert set(OPS) == set(build_ops(fresh.host)) - {"protocol"}


# --- a city no core has ever run for ------------------------------------------------------


def test_reads_of_a_never_started_city_answer_an_empty_city_and_start_no_core(fresh: City) -> None:
    inventory = fresh.run("inventory")
    assert (inventory.code, json.loads(inventory.stdout)) == (0, {"complete": True, "sessions": []}), inventory.stderr
    observed = fresh.run("observe", "mc-a", stdin=b"cat\n")
    assert (observed.code, json.loads(observed.stdout)) == (0, {"state": "absent"}), observed.stderr
    for op, stdin in (("is-running", b""), ("process-alive", b"cat\n"), ("is-attached", b"")):
        done = fresh.run(op, "mc-a", stdin=stdin)
        assert (done.code, done.text.strip()) == (0, "false"), (op, done.stderr)
    listed = fresh.run("list-running")
    assert (listed.code, listed.text) == (0, ""), listed.stderr
    assert fresh.run("peek", "mc-a").code == 66
    for op, args in (("get-meta", ("mc-a", "k")), ("get-last-activity", ("mc-a",))):
        done = fresh.run(op, *args)
        assert (done.code, done.text) == (0, ""), (op, done.stderr)
    no_trace_of_a_core(fresh)


def test_gc_doctors_reads_of_a_never_started_city_start_no_core(fresh: City) -> None:
    """``gc doctor`` before ``gc start``: liveness probes, then the
    orphan-sessions check's inventory."""
    for _ in range(3):
        assert fresh.run("is-running", "mc-a").text.strip() == "false"
    for _ in range(2):
        inventory = fresh.run("inventory")
        assert json.loads(inventory.stdout) == {"complete": True, "sessions": []}, inventory.stderr
    no_trace_of_a_core(fresh)


def test_the_first_start_of_a_never_started_city_starts_its_core(fresh: City) -> None:
    done = fresh.start("mc-a", start_config("exec cat"))
    assert done.code == 0, done.stderr
    assert fresh.run("is-running", "mc-a").text.strip() == "true"


def test_the_first_provision_of_a_never_started_city_starts_its_core(fresh: City) -> None:
    done = fresh.run("provision", "mc-a", stdin=start_config("exec cat").encode())
    assert done.code == 0, done.stderr
    assert not no_core_started(fresh, wait_s=0.5), "provision starts the core, as start does"
    assert fresh.run("is-running", "mc-a").text.strip() == "false", "and launches no agent"
    launched = fresh.run("launch", "mc-a", stdin=start_config("exec cat").encode())
    assert launched.code == 0, launched.stderr
    assert fresh.run("is-running", "mc-a").text.strip() == "true"


def test_a_launch_into_a_never_started_city_refuses_and_starts_no_core(fresh: City) -> None:
    done = fresh.run("launch", "mc-a", stdin=start_config("exec cat").encode())
    assert done.code == 1 and "nothing is provisioned" in done.stderr, done.stderr
    no_trace_of_a_core(fresh)


def test_a_never_started_city_with_a_holder_running_cannot_tell_and_is_kicked(fresh: City, spawned: List[int]) -> None:
    """Something of the session runs, so its state is not known to be
    empty: reads answer unknown, and the core is kicked back to adopt it."""
    start_holder(fresh, [{"argv": ["sleep", "600"]}], spawned)
    assert json.loads(fresh.run("inventory").stdout) == {"complete": False, "sessions": []}
    assert json.loads(fresh.run("observe", "mc-a", stdin=b"cat\n").stdout) == {"state": "unknown"}
    assert not no_core_started(fresh, wait_s=20.0), "the core is kicked"


def test_a_city_whose_core_ran_is_still_kicked(fresh: City) -> None:
    """A core that ended without server-stop (a crash, a reboot) may have
    left records hc answers for: reads stay unknown and kick it back."""
    fresh.start_core()
    assert fresh.fake is not None
    fresh.fake.close()
    fresh.fake = None
    assert os.path.isdir(fresh.paths.state_dir)
    assert json.loads(fresh.run("inventory").stdout) == {"complete": False, "sessions": []}
    assert not no_core_started(fresh, wait_s=20.0), "the core is kicked"


def test_a_state_directory_that_cannot_be_examined_is_not_taken_for_never_started(fresh: City) -> None:
    if os.getuid() == 0:
        pytest.skip("root examines any directory")
    parent = Path(fresh.paths.state_dir).parent
    parent.mkdir(parents=True)
    ctx: OpContext = fresh.context()
    assert core.never_started(ctx)
    parent.chmod(0)
    try:
        assert not core.never_started(ctx), "an lstat that fails but for ENOENT cannot tell"
        assert not core.at_rest(ctx)
    finally:
        parent.chmod(stat.S_IRWXU)


# --- an op that names no city ---------------------------------------------------------------


def without_city(city: City, value: Optional[str]) -> City:
    """``city`` run as an op that names no city: its city path unset, or empty."""
    env = {k: v for k, v in city.env.items() if k != OP_CITY_ENV}
    if value is not None:
        env[OP_CITY_ENV] = value
    return dataclasses.replace(city, env=env)


def bucket_paths(city: City) -> HcPaths:
    """The fixed bucket's core: where an op that names no city would look."""
    env = {k: v for k, v in city.env.items() if k != OP_CITY_ENV}
    paths = resolve_paths(env, machine=MACHINE, home=city.host.home)
    assert paths.city_key == "unscoped" and not paths.scoped
    return paths


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_an_op_that_names_no_city_refuses_or_answers_unknown_and_starts_no_core(fresh: City, value: Optional[str]) -> None:
    nowhere = without_city(fresh, value)
    for op, (args, stdin) in OPS.items():
        done = nowhere.run(op, *args, stdin=stdin)
        if op == "observe":
            assert (done.code, json.loads(done.stdout)) == (0, {"state": "unknown"}), done.stderr
        elif op == "inventory":
            assert (done.code, json.loads(done.stdout)) == (0, {"complete": False, "sessions": []}), done.stderr
        else:
            assert done.code == 1, (op, done.code, done.stderr)
            assert OP_CITY_ENV in done.stderr, (op, done.stderr)
    paths = bucket_paths(fresh)
    assert no_core_started(dataclasses.replace(fresh, paths=paths), wait_s=2.0)
    assert not (fresh.root / "R" / "herdr-core").exists(), "nothing created a core's state"


def test_an_op_that_names_no_city_never_uses_a_core_already_running_for_none(fresh: City) -> None:
    paths = bucket_paths(fresh)
    ensure_dirs(paths)
    fake = FakeHc(paths.socket)
    fake.start()
    try:
        nowhere = without_city(fresh, None)
        observed = nowhere.run("observe", "mc-a", stdin=b"cat\n")
        assert json.loads(observed.stdout) == {"state": "unknown"}
        started = nowhere.start("mc-a", start_config("exec cat"))
        assert started.code == 1 and OP_CITY_ENV in started.stderr, started.stderr
        assert fake.call_count("terminal.run") == 0 and fake.call_count("terminal.list") == 0
    finally:
        fake.close()
    assert fake.schema_violations == []


def unscoped_context(city: City) -> OpContext:
    request = OpRequest(
        op="test",
        args=(),
        stdin=b"",
        env={k: v for k, v in city.env.items() if k != OP_CITY_ENV},
        cancel=CancelToken(),
        deadline=Deadline.after(30.0),
        redactor=Redactor(),
    )
    return OpContext(request, city.host)


def test_no_core_is_ever_started_or_kicked_for_no_city(fresh: City) -> None:
    ctx = unscoped_context(fresh)
    assert not ctx.paths.scoped
    assert core.kick_due(ctx) is False
    assert core.kick(ctx) is False
    with pytest.raises(OpError) as refused:
        core.start_core(ctx, fresh.env["GC_HC_TEST_BIN"])
    assert OP_CITY_ENV in refused.value.message
    core.run_kick(ctx)
    paths = bucket_paths(fresh)
    assert no_core_started(dataclasses.replace(fresh, paths=paths), wait_s=2.0)
    assert not os.path.exists(paths.state_dir)


@pytest.mark.parametrize("command", ["restart-core", "upgrade"])
def test_core_commands_refuse_a_command_that_names_no_city(fresh: City, command: str) -> None:
    """gc runs pack commands with GC_CITY_PATH; without it a command names no
    city and touches no core, not even one serving the fixed bucket."""
    paths = bucket_paths(fresh)
    ensure_dirs(paths)
    fake = FakeHc(paths.socket)
    fake.start()
    releases = fresh.root / "no-releases"
    releases.mkdir()
    env = {k: v for k, v in fresh.env.items() if k not in (OP_CITY_ENV, DOCTOR_CITY_ENV)}
    env["GC_HC_TEST_RELEASES"] = str(releases)  # never the real release server
    out: List[str] = []
    err: List[str] = []
    try:
        code = run_command(command, [], env, fresh.host, out.append, err.append)
        assert code == 1, (out, err)
        assert any(DOCTOR_CITY_ENV in line for line in err), err
        assert fake.call_count("server.stop") == 0 and fake.call_count("server.restart") == 0
    finally:
        fake.close()
    assert fake.schema_violations == []


def command_without_city(city: City, value: Optional[str]) -> Dict[str, str]:
    """A pack command's environment that names no city: ``GC_CITY_PATH`` unset, or empty."""
    env = {k: v for k, v in city.env.items() if k not in (OP_CITY_ENV, DOCTOR_CITY_ENV)}
    if value is not None:
        env[DOCTOR_CITY_ENV] = value
    return env


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_status_without_a_city_reports_the_pin_and_no_core(fresh: City, value: Optional[str]) -> None:
    out: List[str] = []
    err: List[str] = []
    assert run_command("status", [], command_without_city(fresh, value), fresh.host, out.append, err.append) == 0, err
    assert out[0].startswith("pin:") and out[-1] == f"core:      no city ({DOCTOR_CITY_ENV} is unset or empty)", out
    assert not (fresh.root / "R" / "herdr-core").exists()


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_status_env_refuses_a_command_that_names_no_city(fresh: City, value: Optional[str]) -> None:
    """The fixed bucket's tuple would let hc's own CLI (``env $(gc herdr-core
    status --env) herdr-app``) autostart a core for no city."""
    out: List[str] = []
    err: List[str] = []
    code = run_command("status", ["--env"], command_without_city(fresh, value), fresh.host, out.append, err.append)
    assert code == 1 and out == [], out
    assert any(DOCTOR_CITY_ENV in line for line in err), err


# --- the backup guards: each refuses on its own -----------------------------------------------


def test_kick_due_refuses_no_city_whose_bucket_is_not_at_rest(fresh: City) -> None:
    """The bucket's state directory exists and is not parked, so only the
    no-city guard keeps a kick from starting a core for it."""
    ctx = unscoped_context(fresh)
    ensure_dirs(ctx.paths)
    assert not core.at_rest(ctx)
    assert core.kick_due(ctx) is False
    core.run_kick(ctx)
    assert no_core_started(dataclasses.replace(fresh, paths=ctx.paths), wait_s=2.0)
    assert not os.path.exists(os.path.join(ctx.pack_state, core.KICK_FILE)), "no kick ran"


def test_run_starter_refuses_no_city_on_its_own(fresh: City) -> None:
    """``run_starter`` refuses a call that names no city even when its caller
    did not: the starter it would run is never spawned."""
    ctx = unscoped_context(fresh)
    ensure_dirs(ctx.paths)
    marker = fresh.root / "starter-ran"
    with pytest.raises(OpError) as refused:
        core.run_starter(ctx, ["/bin/sh", "-c", f"touch '{marker}'"], env={}, timeout_s=10.0)
    assert OP_CITY_ENV in refused.value.message
    assert not marker.exists(), "the starter never ran"
