"""fake-hc as a ``herdr-core`` binary: the double the pack's own executable
starts and drives, end to end, in place of a real core.

    cli.py server start     start a detached core for this environment's
                            session (if none answers) and print its status
    cli.py server status    print the running core's status (exit 1 if none)
    cli.py server stop      stop the core and every program it runs
    cli.py server restart   hand the running core over to this build (programs
                            survive), or start one if none answers
    cli.py serve            be the core (what ``server start`` spawns)
    cli.py --hc-launchd <dir>/ready
                            be the core as hc runs it under launchd (macOS)
    cli.py hold --socket <s>
                            stand in for a holder: start a core when none
                            answers, as a holder does after a crash, then
                            hold until killed
    cli.py attach <tN>      stand in for a viewer: hold until killed

Discovery follows hc ``crates/herdr-core/src/paths.rs`` for what the pack
sets: ``HC_SESSION``, ``HC_SOCKET`` and ``XDG_STATE_HOME``. Unlike hc it
requires ``HC_SOCKET``, so it can never bind a socket under
``/run/user/<uid>`` or the caller's real state directory. ``serve`` takes
``<state>/core.lock`` with a non-blocking flock and writes its socket path
there, as hc does (``server.rs`` ``serve``), and starts detached with
``HC_RUNTIME=1`` and no ``HC_SCOPE`` (``client.rs`` ``spawn_detached``).

A standalone core differs from hc in one way: its programs are its own
children, so they end with it (a real core's holders keep them). A core
reads and writes ``<state>/core.json`` (its permanent id) as hc does
(``server.rs`` ``load_identity``). Requests
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
import uuid
from typing import Any, Dict, List, Optional, Tuple

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


VERSION_ENV = "FAKEHC_VERSION"
"""Set by :func:`write_launcher`: the hc version this build reports. Never
passed on to the core it starts (a real hc's version is its binary's)."""

NEXT_VERSION_FILE = "fake-next-version"
"""Where ``server restart`` leaves this build's version for the running core."""

PLACEMENT_ENV = "FAKEHC_PLACEMENT"
"""Set by :func:`write_launcher`: where ``server start`` places the core.
``systemd`` places it as hc does under a user manager, in the core's
``XDG_RUNTIME_DIR`` (a test's stand-in for ``/run/user/<uid>``);
``systemd-legacy`` as under systemd older than 244, which names no
``RUNTIME_DIRECTORY``; ``launchd`` as hc does on macOS, where the core
process runs as ``--hc-launchd <dir>/ready`` with launchd's environment and
takes the starter's only in-process (:func:`launchd_argv`)."""

PLACEMENTS = ("systemd", "systemd-legacy", "launchd")

LAUNCHD_BLOCK = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "SHELL": "/bin/zsh",
    "TMPDIR": "/var/folders/zz/T/",
    "SSH_AUTH_SOCK": "/private/tmp/com.apple.launchd.x/Listeners",
    "XPC_SERVICE_NAME": "0",
    "XPC_FLAGS": "0x0",
    "__CF_USER_TEXT_ENCODING": "0x1F5:0x0:0x0",
}
"""What a launchd job runs with besides the user's HOME, USER and LOGNAME
(launchd's defaults; values synthetic)."""

LAUNCHD_SENTINEL = "--hc-launchd"
"""hc's launchd core: ``<hc> --hc-launchd <dir>/ready``, ``<dir>`` being
``hc-launchd-<starter pid>-<ns>-<32 hex>`` (hc ``platform/macos_launchd.rs``).
fake-hc's ``ready`` is a private file holding the starter's environment,
which the core restores in-process and removes, as hc's handshake does."""

CORE_JSON = "core.json"

SERVICE = (
    "INVOCATION_ID", "RUNTIME_DIRECTORY", "JOURNAL_STREAM", "SYSTEMD_EXEC_PID", "MANAGERPID", "MANAGERPIDFDID",
    "MEMORY_PRESSURE_WATCH", "MEMORY_PRESSURE_WRITE", "NOTIFY_SOCKET", "WATCHDOG_PID", "WATCHDOG_USEC",
    "LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES",
)
"""hc ``platform/systemd.rs`` ``SERVICE``: never written to a unit's environment file."""

MANAGER_BLOCK = {
    "SHELL": "/bin/bash",
    "XDG_DATA_DIRS": "/usr/share",
    "SSH_AUTH_SOCK": "/run/user/agent.sock",
    "TMPDIR": "/tmp",
    "GOCACHE": "/home/u/.cache/go",
}
"""Keys a real user manager's environment block carried (recorded, values synthetic)."""


def _quoted(value: str) -> str:
    return "".join("\\" + ch if ch in '\\"$`' else ch for ch in value)


def _starter(env: Dict[str, str]) -> Dict[str, str]:
    """The starter's environment as the core takes it: none of fake-hc's own settings."""
    return {k: v for k, v in env.items() if k not in ("HC_SCOPE", PLACEMENT_ENV, VERSION_ENV)}


def systemd_child_env(env: Dict[str, str], root: str, *, legacy: bool = False) -> Dict[str, str]:  # root: the runtime dir
    """:func:`systemd_unit_env`'s environ."""
    return systemd_unit_env(env, root, legacy=legacy)[0]


def systemd_unit_env(
    env: Dict[str, str], root: str, *, legacy: bool = False, verb: str = "serve"
) -> Tuple[Dict[str, str], str]:
    """A systemd-placed core's (or, ``verb="hold"``, holder's) environ and
    unit name, built as hc's ``platform::systemd::spawn``
    does: the starter's environment (no service variables) plus the runtime
    dir and HC_RUNTIME goes to ``<RuntimeDirectory>/environment`` (0600 in a
    0700 dir); the unit then runs with the manager's block, that file, and
    systemd's own service variables. ``legacy``: systemd older than 244,
    which sets no RUNTIME_DIRECTORY (nor SYSTEMD_EXEC_PID, 248, nor the
    MEMORY_PRESSURE_* pair, 254)."""
    starter = {k: v for k, v in _starter(env).items() if k not in SERVICE}
    starter["XDG_RUNTIME_DIR"] = root
    starter["HC_RUNTIME"] = "1"
    unit = f"hc-{verb}-{uuid.uuid4().hex[:8]}"
    unit_dir = os.path.join(root, unit)
    os.makedirs(unit_dir, mode=0o700)
    fd = os.open(os.path.join(unit_dir, "environment"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("".join(f'{k}="{_quoted(v)}"\n' for k, v in sorted(starter.items())))
    child = dict(MANAGER_BLOCK)
    child.update(starter)
    if legacy:
        child.update({"INVOCATION_ID": uuid.uuid4().hex, "JOURNAL_STREAM": "8:12345", "MANAGERPID": "1234"})
        return child, unit
    child.update(
        {
            "INVOCATION_ID": uuid.uuid4().hex,
            "MANAGERPID": "1234",
            "MEMORY_PRESSURE_WATCH": "/sys/fs/cgroup/user.slice/memory.pressure",
            "MEMORY_PRESSURE_WRITE": "c29tZQ==",
            "RUNTIME_DIRECTORY": unit_dir,
            "SYSTEMD_EXEC_PID": "4321",
        }
    )
    return child, unit


def launchd_child_env(env: Dict[str, str]) -> Dict[str, str]:
    """A launchd-placed core's environ: launchd's, never the starter's."""
    child = dict(LAUNCHD_BLOCK)
    for key in ("HOME", "USER", "LOGNAME"):
        if key in env:
            child[key] = env[key]
    return child


def server_start(env: Dict[str, str]) -> int:
    paths = _paths(env)
    if _answers(paths["socket"]):
        return _print_status(paths["socket"])
    spawn_core(env, starter_pid=os.getpid())
    deadline = time.monotonic() + START_WAIT_S
    while time.monotonic() < deadline:
        if _answers(paths["socket"]):
            return _print_status(paths["socket"])
        time.sleep(0.02)
    print(f"core did not start within {int(START_WAIT_S)} s", file=sys.stderr)
    return 1


def launchd_argv(starter_pid: int, state: str, starter: Dict[str, str], version: str) -> List[str]:
    """hc's launchd core argv, with the starter's environment and the version
    in its ``ready`` file."""
    ready_dir = os.path.join(state, f"hc-launchd-{starter_pid}-{time.time_ns()}-{uuid.uuid4().hex}")
    os.mkdir(ready_dir, 0o700)
    ready = os.path.join(ready_dir, "ready")
    fd = os.open(ready, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"env": starter, "version": version}, handle)
    return [sys.executable, os.path.abspath(__file__), LAUNCHD_SENTINEL, ready]


def spawn_core(env: Dict[str, str], *, starter_pid: int) -> None:
    """Start a detached core with ``env`` placed as :data:`PLACEMENT_ENV`
    says, asked for by ``starter_pid`` (hc ``client.rs`` ``spawn_core``)."""
    paths = _paths(env)
    os.makedirs(paths["state"], mode=0o700, exist_ok=True)
    runtime_dir = env.get("XDG_RUNTIME_DIR", "")
    placement = env.get(PLACEMENT_ENV, "")
    version = env.get(VERSION_ENV, "") or "0.1.19"
    argv = [sys.executable, os.path.abspath(__file__), "serve", version]
    if placement in ("systemd", "systemd-legacy") and runtime_dir:
        child_env = systemd_child_env(env, runtime_dir, legacy=placement == "systemd-legacy")
    elif placement == "launchd":
        child_env = launchd_child_env(env)
        argv = launchd_argv(starter_pid, paths["state"], dict(_starter(env), HC_RUNTIME="1", XPC_SERVICE_NAME="0"), version)
    else:
        child_env = _starter(env)
        child_env["HC_RUNTIME"] = "1"
    with open(os.path.join(paths["state"], "core.log"), "ab") as log:
        subprocess.Popen(
            argv,
            env=child_env,
            cwd="/",
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )


def hold(env: Dict[str, str]) -> int:
    """A holder's stand-in: a core that crashed is started again by its
    holder (hc ``holder.rs`` ``supervise``), with the holder's environment
    and the holder as its starter."""
    paths = _paths(env)
    env = {k: v for k, v in env.items() if k != "_HC_RESPONSIBLE_PID"}  # hc drops its re-exec mark in-process
    if not _answers(paths["socket"]):
        spawn_core(env, starter_pid=os.getpid())
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())
    while not stop.is_set():
        stop.wait(0.2)
    return 0


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


def server_restart(env: Dict[str, str]) -> int:
    paths = _paths(env)
    if not _answers(paths["socket"]):
        return server_start(env)
    version = env.get(VERSION_ENV) or "0.1.19"
    with open(os.path.join(paths["state"], NEXT_VERSION_FILE), "w", encoding="utf-8") as handle:
        handle.write(version)
    reply = raw_call(paths["socket"], "server.restart", {}, timeout=30.0)
    if "result" not in reply:
        return 1
    deadline = time.monotonic() + START_WAIT_S
    while time.monotonic() < deadline:
        try:
            hello = raw_call(paths["socket"], "hello", {}, timeout=1.0)
        except (OSError, ValueError):
            hello = {}
        if hello.get("result", {}).get("version") == version:
            return _print_status(paths["socket"])
        time.sleep(0.02)
    return 1


def serve(env: Dict[str, str], version: str = "0.1.19") -> int:
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
    fake = FakeHc(
        paths["socket"],
        base_env=env,
        core_id=_core_id(paths["state"]),
        core_name=socket.gethostname(),
        version=version,
        next_version_file=os.path.join(paths["state"], NEXT_VERSION_FILE),
    )
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


def _core_id(state: str) -> str:
    """The state directory's permanent core id, made on first start (hc
    ``server.rs`` ``load_identity``)."""
    path = os.path.join(state, CORE_JSON)
    try:
        with open(path, encoding="utf-8") as handle:
            return str(json.load(handle)["id"])
    except FileNotFoundError:
        pass
    core_id = uuid.uuid4().hex
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"id": core_id, "name": socket.gethostname()}, handle)
    os.rename(tmp, path)
    return core_id


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
    from fakehc.hcconfig import HcConfigError, config_path, load_hc_config

    paths = _paths(env)
    path = config_path(env)
    try:
        if path is not None:
            load_hc_config(path)  # hc attach.rs reads its detach_key, and fails on a bad file
    except HcConfigError as err:
        print(json.dumps({"code": -32000, "message": str(err), "data": {"kind": "config", "hint": ""}}), file=sys.stderr)
        return 1
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
        if argv[:2] == ["server", "restart"]:
            return server_restart(env)
        if argv[:1] == ["serve"]:
            return serve(env, *argv[1:2])
        if argv[:1] == [LAUNCHD_SENTINEL] and len(argv) == 2:
            with open(argv[1], encoding="utf-8") as handle:
                ready = json.load(handle)
            os.unlink(argv[1])
            os.rmdir(os.path.dirname(argv[1]))
            return serve(dict(ready["env"]), str(ready["version"]))
        if len(argv) == 3 and argv[:2] == ["hold", "--socket"]:
            return hold(env)
        if len(argv) == 2 and argv[0] == "attach":
            return attach(env, argv[1])
        raise Usage(
            "usage: fake-hc server start|status|stop|restart | serve [version] | --hc-launchd <ready> "
            "| hold --socket <socket> | attach <terminal>"
        )
    except Usage as err:
        print(f"fake-hc: {err}", file=sys.stderr)
        return 2


def write_launcher(
    path: str, *, python: Optional[str] = None, systemd: bool = False, placement: str = "", version: str = "0.1.19"
) -> str:
    """A ``herdr-core``-named executable at ``path`` that runs this CLI under
    ``python`` (default: this interpreter, which has the schema tooling).

    It is a Python script, not a shell wrapper: a shell would add ``PWD`` to
    the environment, and a real hc binary is exec'd with exactly the
    environment its caller gave it. ``placement`` (one of
    :data:`PLACEMENTS`) places the core it starts as hc does there
    (:data:`PLACEMENT_ENV`); ``systemd`` is ``placement="systemd"``."""
    if systemd:
        placement = placement or "systemd"
    if placement and placement not in PLACEMENTS:
        raise ValueError(f"unknown placement {placement!r}")
    interpreter = python or sys.executable
    if any(ch.isspace() for ch in interpreter):
        raise ValueError("the interpreter path must not contain whitespace (it goes in a shebang)")
    script = (
        f"#!{interpreter}\n"
        "import os, runpy, sys\n"
        + (f"os.environ[{PLACEMENT_ENV!r}] = {placement!r}\n" if placement else "")
        + f"os.environ[{VERSION_ENV!r}] = {version!r}\n"
        +
        f"sys.argv[0] = {os.path.abspath(__file__)!r}\n"
        f"runpy.run_path({os.path.abspath(__file__)!r}, run_name='__main__')\n"
    )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    os.chmod(path, 0o755)
    return path


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], dict(os.environ)))
