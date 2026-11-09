"""fake-hc as a ``herdr-core`` binary: the double the pack's own executable
starts and drives, end to end, in place of a real core.

    cli.py server start     start a detached core for this environment's
                            session (if none answers) and print its status
    cli.py server status    print the running core's status (exit 1 if none)
    cli.py server stop      stop the core and every program it runs
    cli.py serve            be the core (what ``server start`` spawns)
    cli.py attach <tN>      stand in for a viewer: hold until killed

Discovery follows hc ``crates/herdr-core/src/paths.rs`` for what the pack
sets: ``HC_SESSION``, ``HC_SOCKET`` and ``XDG_STATE_HOME``. Unlike hc it
requires ``HC_SOCKET``, so it can never bind a socket under
``/run/user/<uid>`` or the caller's real state directory. ``serve`` takes
``<state>/core.lock`` with a non-blocking flock and writes its socket path
there, as hc does (``server.rs`` ``serve``), and starts detached with
``HC_RUNTIME=1`` and no ``HC_SCOPE`` (``client.rs`` ``spawn_detached``).

A standalone core differs from hc in one way: its programs are its own
children, so they end with it (a real core's holders keep them). Requests
or results that leave the vendored schema are appended to
``<state>/schema-violations.log``, which a harness requires to be absent.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fakehc.rawclient import raw_call  # noqa: E402

START_WAIT_S = 15.0
"""How long ``server start`` waits for the new core (hc ``client.rs`` START_WAIT)."""

VIOLATIONS_LOG = "schema-violations.log"


class Usage(Exception):
    pass


def _paths(env: Dict[str, str]) -> Dict[str, str]:
    session = (env.get("HC_SESSION") or "default").strip() or "default"
    sock = env.get("HC_SOCKET", "")
    if not sock:
        raise Usage("fake-hc needs HC_SOCKET (it never binds a default socket)")
    state_home = env.get("XDG_STATE_HOME", "")
    if not state_home or not os.path.isabs(state_home):
        raise Usage("fake-hc needs an absolute XDG_STATE_HOME")
    state = os.path.join(state_home, "herdr-core", session)
    return {"session": session, "socket": sock, "state": state}


def _answers(sock: str) -> bool:
    try:
        raw_call(sock, "hello", {}, timeout=1.0)
    except (OSError, ValueError):
        return False
    return True


def _print_status(sock: str) -> int:
    reply = raw_call(sock, "server.status", {}, timeout=5.0)
    if "error" in reply:
        print(json.dumps(reply["error"]), file=sys.stderr)
        return 1
    print(json.dumps(reply["result"]))
    return 0


def server_start(env: Dict[str, str]) -> int:
    paths = _paths(env)
    if _answers(paths["socket"]):
        return _print_status(paths["socket"])
    os.makedirs(paths["state"], mode=0o700, exist_ok=True)
    child_env = {k: v for k, v in env.items() if k != "HC_SCOPE"}
    child_env["HC_RUNTIME"] = "1"
    with open(os.path.join(paths["state"], "core.log"), "ab") as log:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "serve"],
            env=child_env,
            cwd="/",
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    deadline = time.monotonic() + START_WAIT_S
    while time.monotonic() < deadline:
        if _answers(paths["socket"]):
            return _print_status(paths["socket"])
        time.sleep(0.02)
    print(f"core did not start within {int(START_WAIT_S)} s", file=sys.stderr)
    return 1


def server_status(env: Dict[str, str]) -> int:
    paths = _paths(env)
    if not _answers(paths["socket"]):
        print("no core is running", file=sys.stderr)
        return 1
    return _print_status(paths["socket"])


def server_stop(env: Dict[str, str]) -> int:
    paths = _paths(env)
    if not _answers(paths["socket"]):
        return 0
    reply = raw_call(paths["socket"], "server.stop", {}, timeout=30.0)
    return 0 if "result" in reply else 1


def serve(env: Dict[str, str]) -> int:
    from fakehc.server import FakeHc

    paths = _paths(env)
    os.makedirs(paths["state"], mode=0o700, exist_ok=True)
    lock = os.open(os.path.join(paths["state"], "core.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0  # another core serves this session
    os.ftruncate(lock, 0)
    os.write(lock, os.fsencode(paths["socket"]))
    os.makedirs(os.path.dirname(paths["socket"]), mode=0o700, exist_ok=True)
    fake = FakeHc(paths["socket"], base_env=env, core_name=socket.gethostname())
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda signum, frame: done.set())
    signal.signal(signal.SIGINT, lambda signum, frame: done.set())
    fake.start()
    try:
        while not done.is_set() and not fake.stopped.is_set():
            done.wait(0.1)
            _flush_violations(fake, paths["state"])
    finally:
        fake.close()
        _flush_violations(fake, paths["state"])
    return 0


_flushed: Dict[int, int] = {}


def _flush_violations(fake: Any, state: str) -> None:
    found: List[str] = list(fake.schema_violations)
    done = _flushed.get(id(fake), 0)
    if len(found) > done:
        with open(os.path.join(state, VIOLATIONS_LOG), "a", encoding="utf-8") as log:
            for line in found[done:]:
                log.write(line + "\n")
        _flushed[id(fake)] = len(found)


def attach(env: Dict[str, str], terminal: str) -> int:
    paths = _paths(env)
    reply = raw_call(paths["socket"], "terminal.get", {"terminal": terminal}, timeout=5.0)
    if "error" in reply:
        print(json.dumps(reply["error"]), file=sys.stderr)
        return 1
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())
    while not stop.is_set():
        stop.wait(0.2)
    return 0


def main(argv: List[str], env: Dict[str, str]) -> int:
    try:
        if argv[:2] == ["server", "start"]:
            return server_start(env)
        if argv[:2] == ["server", "status"]:
            return server_status(env)
        if argv[:2] == ["server", "stop"]:
            return server_stop(env)
        if argv[:1] == ["serve"]:
            return serve(env)
        if len(argv) == 2 and argv[0] == "attach":
            return attach(env, argv[1])
        raise Usage("usage: fake-hc server start|status|stop | serve | attach <terminal>")
    except Usage as err:
        print(f"fake-hc: {err}", file=sys.stderr)
        return 2


def write_launcher(path: str, *, python: Optional[str] = None) -> str:
    """A ``herdr-core``-named executable at ``path`` that runs this CLI under
    ``python`` (default: this interpreter, which has the schema tooling).

    It is a Python script, not a shell wrapper: a shell would add ``PWD`` to
    the environment, and a real hc binary is exec'd with exactly the
    environment its caller gave it."""
    interpreter = python or sys.executable
    if any(ch.isspace() for ch in interpreter):
        raise ValueError("the interpreter path must not contain whitespace (it goes in a shebang)")
    script = (
        f"#!{interpreter}\n"
        "import runpy, sys\n"
        f"sys.argv[0] = {os.path.abspath(__file__)!r}\n"
        f"runpy.run_path({os.path.abspath(__file__)!r}, run_name='__main__')\n"
    )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    os.chmod(path, 0o755)
    return path


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], dict(os.environ)))
