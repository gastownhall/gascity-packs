"""Session secrets never stay on disk.

gc's session environment carries provider credentials and identity tokens.
The pack hands them to its launcher in a 0600 spawn file on tmpfs that the
launcher unlinks before reading, and gives hc only ``TERM``, so hc's
``terminals.json`` (kept 24 h) never holds them.

(a) after a session ends, no secret value is anywhere under the state root,
    the spawn directory or the scratch runtime directory;
(b) a ``start`` SIGKILLed mid-flight leaves no spawn file behind once the
    next op's sweep is due;
(c) a secret the agent echoes to its screen is gone from hc's state once the
    session is stopped (its record removed); what is found is reported.
"""

from __future__ import annotations

import os
import signal
import time
import uuid
from typing import List

from gc_runtime_herdr_core.herdrcore.spawnfile import MAX_AGE_S, SUFFIX
from livekit.crash import wait_until
from livekit.pack import Pack
from livekit.scratch import Scratch


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


def test_a_start_killed_mid_flight_leaves_no_spawn_file(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    assert pack.start_agent("live-warm").code == 0  # the core is up: start reaches its spawn file fast
    secret = _secret()
    caught = False
    for attempt in range(10):
        name = f"live-cut{attempt}"
        config = pack.start_config(name, scratch.agent_command(), env=scratch.agent_env(name, GC_HC_LIVE_TOKEN_UNDER_TEST=secret))
        op = pack.popen("start", name, stdin=config)
        wait_until(lambda: bool(_spawn_files(scratch)) or op.poll() is not None, 30, step_s=0.002)
        if op.poll() is None:
            scratch.ownership.signal(op.pid, signal.SIGKILL)
        op.wait(timeout=10)
        if _spawn_files(scratch):
            caught = True
            break
        pack.stop(name)
    scratch.note("start killed with its spawn file on disk", caught)
    if caught:
        left = _spawn_files(scratch)
        newest = max(os.stat(p).st_mtime for p in left)
        time.sleep(max(0.0, newest + MAX_AGE_S + 1 - time.time()))
    assert pack.op("list-running").code == 0
    assert _spawn_files(scratch) == [], "a spawn file outlived the next op's sweep"
    for name in [f"live-cut{n}" for n in range(10)]:
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
