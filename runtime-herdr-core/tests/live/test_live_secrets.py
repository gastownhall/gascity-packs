"""Session secrets never stay on disk.

gc's session environment carries provider credentials and identity tokens.
The pack hands them to its launcher in a 0600 spawn file on tmpfs that the
launcher unlinks before reading, and gives hc only ``TERM``, so hc's
``terminals.json`` (kept 24 h) never holds them.

On the systemd lane the spawn files go where they go in production
(``/run/user/<uid>/gc-herdr-core/<city id>/``); the plain lane has no
``/run/user`` of its own and points the pack at a scratch directory instead.

(a) after a session ends, no secret value is anywhere under the state root,
    the spawn directory or the scratch runtime directory;
(b) a ``start`` SIGKILLed mid-flight, before its ``terminal.run`` (its spawn
    file still there, hc with no terminal of that name, so no launcher will
    unlink it), leaves no spawn file behind once the next op's sweep is due;
(c) a secret the agent echoes to its screen is gone from hc's state once the
    session is stopped (its record removed); what is found is reported.
"""

from __future__ import annotations

import os
import signal
import time
import uuid
from typing import List, Optional

import pytest

from gc_runtime_herdr_core.herdrcore.naming import terminal_name
from gc_runtime_herdr_core.herdrcore.spawnfile import MAX_AGE_S, SUFFIX
from livekit.crash import wait_until
from livekit.hcrpc import HcRpc
from livekit.pack import Pack
from livekit.scratch import Scratch


KILL_ATTEMPTS = 20
IN_FLIGHT_S = 1.0


def _secret() -> str:
    return f"live-secret-{uuid.uuid4().hex}"


def _spawn_files(scratch: Scratch) -> List[str]:
    found = []
    for here, _, files in os.walk(scratch.spawn_root):
        found += [os.path.join(here, f) for f in files if f.endswith(SUFFIX)]
    return sorted(found)


def test_a_session_secret_leaves_no_trace_after_the_session_ends(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    secret = _secret()
    answer = pack.start_agent("live-s", GC_HC_LIVE_TOKEN_UNDER_TEST=secret)
    assert answer.code == 0, answer.stderr
    assert secret not in answer.stderr
    scratch.agent_report("live-s", timeout_s=30)
    while_running = scratch.find_bytes(secret.encode())
    stopped = pack.stop("live-s")
    assert stopped.code == 0, stopped.stderr
    after = scratch.find_bytes(secret.encode())
    scratch.note("secret files while running", while_running)
    assert after == [], f"the session's secret is still on disk after it ended: {after}"
    assert _spawn_files(scratch) == []


def newest_mtime(paths: List[str]) -> Optional[float]:
    """The newest modification time among ``paths`` that still exist."""
    times = []
    for path in paths:
        try:
            times.append(os.stat(path).st_mtime)
        except FileNotFoundError:
            continue
    return max(times) if times else None


def test_a_start_killed_mid_flight_leaves_no_spawn_file(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    assert pack.start_agent("live-warm").code == 0  # the core is up: start reaches its spawn file fast
    rpc = HcRpc(scratch.paths().socket)
    city_id = scratch.paths().city_id
    secret = _secret()
    names: List[str] = []
    caught: List[str] = []
    for attempt in range(KILL_ATTEMPTS):
        name = f"live-cut{attempt}"
        names.append(name)
        config = pack.start_config(name, scratch.agent_command(), env=scratch.agent_env(name, GC_HC_LIVE_TOKEN_UNDER_TEST=secret))
        op = pack.popen("start", name, stdin=config)
        wait_until(lambda: bool(_spawn_files(scratch)) or op.poll() is not None, 30, step_s=0.002)
        if op.poll() is None:
            scratch.ownership.signal(op.pid, signal.SIGKILL)
        op.wait(timeout=10)
        time.sleep(IN_FLIGHT_S)  # a terminal.run already sent has registered by now
        left = _spawn_files(scratch)
        if left and not rpc.has_terminal(terminal_name(city_id, name)):
            caught = left
            break
        # Too late: the launcher has (or will have) the file. Start over clean.
        pack.stop(name)
        wait_until(lambda: not _spawn_files(scratch), 30)
    scratch.note("start killed before terminal.run, spawn file on disk", {"attempts": len(names), "caught": bool(caught)})
    if not caught:
        for name in names:
            pack.stop(name)
        pytest.skip(f"no SIGKILL in {KILL_ATTEMPTS} attempts landed between the spawn file and terminal.run")
    newest = newest_mtime(caught)
    assert newest is not None, f"the spawn files vanished with no launcher to take them: {caught}"
    time.sleep(max(0.0, newest + MAX_AGE_S + 1 - time.time()))
    assert [p for p in caught if os.path.exists(p)] == caught, "something other than the sweep removed the spawn file"
    assert pack.op("list-running").code == 0
    assert _spawn_files(scratch) == [], "a spawn file outlived the next op's sweep"
    for name in names:
        pack.stop(name)
    assert scratch.find_bytes(secret.encode()) == []


def test_a_secret_echoed_to_the_screen_is_gone_once_the_record_is(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    secret = _secret()
    answer = pack.start_agent("live-e", GC_HC_LIVE_ECHO=secret)
    assert answer.code == 0, answer.stderr
    scratch.agent_report("live-e", timeout_s=30)
    on_disk_while_running = scratch.find_bytes(secret.encode())
    assert pack.stop("live-e").code == 0
    after = scratch.find_bytes(secret.encode())
    scratch.note("echoed secret on disk", {"while running": on_disk_while_running, "after stop": after})
    assert after == [], f"the screen's secret is still on disk after the record was removed: {after}"
