"""What the harness asks of hc: the city core's discovery tuple (from the
pack's ``gc herdr-core status --env``), ``server.status`` over the core's
socket, and the teardown of the cores a conformance run left under a scratch
state root.

Tested only against fake-hc.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from soakanalysis import hc_role
from soaklib import NotOwned, ProcFS, ProcInfo, Rec, run, signal_owned, unit_of

HC_UNIT_PREFIXES = ("hc-serve-", "hc-hold-")
TEARDOWN_WAIT_S = 15.0


class HcError(Exception):
    """hc answered with an error, or could not be reached."""


@dataclass(frozen=True)
class CoreTuple:
    """The variables that name one core: what it is started with and how clients find it."""

    session: str
    socket: str
    state_home: str
    config_home: str

    def env(self) -> Dict[str, str]:
        return {
            "HC_SESSION": self.session,
            "HC_SOCKET": self.socket,
            "XDG_STATE_HOME": self.state_home,
            "XDG_CONFIG_HOME": self.config_home,
        }

    @property
    def state_dir(self) -> str:
        """The core's own state directory (its logs, records and ``core.lock``)."""
        return os.path.join(self.state_home, "herdr-core", self.session)


def parse_status_env(text: str) -> CoreTuple:
    """``gc herdr-core status --env`` output: ``KEY=value`` lines."""
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.strip().split("=", 1)
            values[key] = value
    missing = [k for k in ("HC_SESSION", "HC_SOCKET", "XDG_STATE_HOME", "XDG_CONFIG_HOME") if not values.get(k)]
    if missing:
        raise HcError(f"`gc herdr-core status --env` named no {', '.join(missing)}")
    return CoreTuple(values["HC_SESSION"], values["HC_SOCKET"], values["XDG_STATE_HOME"], values["XDG_CONFIG_HOME"])


def core_tuple(city_dir: str, gc_bin: str = "gc") -> CoreTuple:
    res = run([gc_bin, "herdr-core", "status", "--env"], cwd=city_dir, timeout=60.0)
    if not res.ok:
        raise HcError(f"`gc herdr-core status --env` exited {res.code}: {res.tail(300)}")
    return parse_status_env(res.out)


def hc_env(core: CoreTuple, hc_bin: str, base: Mapping[str, str]) -> Dict[str, str]:
    """A clean environment for running the pinned hc against ``core`` (``env -i`` plus the tuple)."""
    env = {
        "HOME": base.get("HOME", ""),
        "USER": base.get("USER", ""),
        "LOGNAME": base.get("LOGNAME", base.get("USER", "")),
        "LANG": "C.UTF-8",
        "PATH": f"{os.path.dirname(hc_bin)}:/usr/local/bin:/usr/bin:/bin",
    }
    for key in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        if base.get(key):
            env[key] = base[key]
    env.update(core.env())
    return env


# --- JSON-RPC --------------------------------------------------------------------------


@dataclass(frozen=True)
class CoreStatus:
    pid: int
    version: str
    holders: Tuple[int, ...]
    live: int
    raw: Rec = field(compare=False, default_factory=dict)


class HcRpc:
    """Plain JSON-RPC to a core: one request per connection, after ``hello``."""

    def __init__(self, socket_path: str, timeout_s: float = 10.0) -> None:
        self.socket_path = socket_path
        self.timeout_s = timeout_s

    def call(self, method: str, params: Optional[Mapping[str, Any]] = None) -> Rec:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(self.timeout_s)
                conn.connect(self.socket_path)
                reader = conn.makefile("rb")
                if method != "hello":
                    self._exchange(conn, reader, 0, "hello", {})
                return self._exchange(conn, reader, 1, method, dict(params or {}))
        except (OSError, ValueError) as err:
            raise HcError(f"{method}: {err}") from None

    @staticmethod
    def _exchange(conn: socket.socket, reader: Any, rid: int, method: str, params: Mapping[str, Any]) -> Rec:
        request = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": dict(params)}) + "\n"
        conn.sendall(request.encode("utf-8"))
        while True:
            line = reader.readline(1 << 24)
            if not line.endswith(b"\n"):
                raise HcError(f"{method}: the core closed the connection")
            doc = json.loads(line)
            if not isinstance(doc, dict) or doc.get("id") != rid:
                continue  # a notification
            error = doc.get("error")
            if isinstance(error, dict):
                raise HcError(f"{method}: {error.get('message', error)}")
            result = doc.get("result")
            if not isinstance(result, dict):
                raise HcError(f"{method}: no result object")
            return result

    def status(self) -> CoreStatus:
        result = self.call("server.status")
        holders = tuple(
            int(h["pid"]) for h in result.get("holders") or [] if isinstance(h, dict) and isinstance(h.get("pid"), int)
        )
        pid = result.get("pid")
        if not isinstance(pid, int):
            raise HcError("server.status: no pid")
        live = result.get("live")
        return CoreStatus(pid, str(result.get("version", "")), holders, live if isinstance(live, int) else 0, result)

    def answers(self) -> bool:
        try:
            self.call("hello")
        except HcError:
            return False
        return True


# --- the conformance run's scratch cores -----------------------------------------------------


def lock_free(path: Path) -> bool:
    """Whether nobody holds ``path``'s flock (as ``flock --nonblock <lock> true``)."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    finally:
        os.close(fd)
    return True


def runtime_of(procfs: ProcFS, root: str, uid: int) -> List[ProcInfo]:
    """hc cores and holders of this user whose ``XDG_STATE_HOME`` is ``root``."""
    return [
        p for p in procfs.snapshot(uid).values() if hc_role(p) is not None and p.env.get("XDG_STATE_HOME") == root
    ]


def systemd_unit_gone(unit: str) -> bool:
    res = run(["systemctl", "--user", "show", "-p", "ActiveState", "-p", "LoadState", "--", unit], timeout=30.0)
    if not res.ok:
        return True
    values = dict(line.split("=", 1) for line in res.out.splitlines() if "=" in line)
    return values.get("LoadState") == "not-found" or values.get("ActiveState") in ("inactive", "failed", "")


@dataclass
class Teardown:
    root: str
    cores: List[Rec] = field(default_factory=list)
    survivors: List[Rec] = field(default_factory=list)
    held_locks: List[str] = field(default_factory=list)
    units_left: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.survivors or self.held_locks or self.units_left)

    def as_rec(self) -> Rec:
        return {
            "root": self.root,
            "cores": self.cores,
            "survivors": self.survivors,
            "held_locks": self.held_locks,
            "units_left": self.units_left,
            "ok": self.ok,
        }


def conf_teardown(
    root: str,
    hc_bin: str,
    base_env: Mapping[str, str],
    procfs: ProcFS,
    *,
    uid: Optional[int] = None,
    wait_s: float = TEARDOWN_WAIT_S,
    unit_gone: Callable[[str], bool] = systemd_unit_gone,
) -> Teardown:
    """Stop every core a conformance run left under ``root`` with the pinned
    hc, then check that nothing of it remains; a survivor is named and killed
    by pid after the ownership check."""
    me = os.getuid() if uid is None else uid
    result = Teardown(root=root)
    units = {u for u in (unit_of(p.cgroup) for p in runtime_of(procfs, root, me)) if u and u.startswith(HC_UNIT_PREFIXES)}
    locks = sorted(Path(root, "herdr-core").glob("*/core.lock"))
    for lock in locks:
        session = lock.parent.name
        try:
            sock = lock.read_text(encoding="utf-8").strip()
        except OSError:
            sock = ""
        core = CoreTuple(session, sock, root, os.path.join(root, "hc-config"))
        res = run([hc_bin, "server", "stop"], env=hc_env(core, hc_bin, base_env), timeout=60.0)
        result.cores.append({"session": session, "socket": sock, "stop_exit": res.code, "tail": res.tail(300)})
    # An exiting core stops reading as hc runtime before the kernel releases
    # its lock: wait for both before judging either.
    deadline = time.monotonic() + wait_s
    left = runtime_of(procfs, root, me)
    while (left or not all(lock_free(lock) for lock in locks)) and time.monotonic() < deadline:
        time.sleep(0.2)
        left = runtime_of(procfs, root, me)
    for proc in left:
        unit = unit_of(proc.cgroup)
        if unit and unit.startswith(HC_UNIT_PREFIXES):
            units.add(unit)
        entry: Rec = {"pid": proc.pid, "start": proc.start, "argv": list(proc.argv[:3]), "unit": unit}
        try:
            signal_owned(proc.pid, signal.SIGKILL, proc.start, _owner(procfs, root, me), procfs)
            entry["killed"] = True
        except NotOwned as err:
            entry["killed"] = False
            entry["why"] = str(err)
        result.survivors.append(entry)
    result.held_locks = [str(lock) for lock in locks if not lock_free(lock)]
    result.units_left = sorted(u for u in units if not unit_gone(u))
    return result


def _owner(procfs: ProcFS, root: str, uid: int) -> Callable[[int], Optional[str]]:
    def owns(pid: int) -> Optional[str]:
        info = procfs.info(pid)
        if info is None:
            return "gone"
        if info.uid != uid:
            return "another user's process"
        if hc_role(info) is None:
            return "not hc runtime"
        if info.env.get("XDG_STATE_HOME") != root:
            return "hc runtime of another state root"
        return None

    return owns


def wait_answers(rpc: HcRpc, timeout_s: float) -> Optional[float]:
    """Seconds until the core answers, or None."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if rpc.answers():
            return time.monotonic() - t0
        time.sleep(0.5)
    return None


__all__: Sequence[str] = (
    "CoreStatus",
    "CoreTuple",
    "HcError",
    "HcRpc",
    "Teardown",
    "conf_teardown",
    "core_tuple",
    "hc_env",
    "lock_free",
    "parse_status_env",
    "wait_answers",
)
