"""Shared pieces of the herdr-core soak harness: the host guard, the paths a
city's data lives under, append-only JSON lines, ``/proc`` reads, running a
command, and the one way the harness signals a process.

Standard library only (Python 3.9 or later). Nothing here talks to hc.
"""

from __future__ import annotations

import json
import os
import signal as signals
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

Rec = Dict[str, Any]
"""One JSON-lines record."""

GUARD_FILE = "/etc/gc-soak-throwaway"
MACHINE_ID_FILE = "/etc/machine-id"
LINE_LIMIT = 4096
"""Every JSON line the harness or an agent writes stays under this many bytes,
so one ``write(2)`` on an ``O_APPEND`` descriptor never interleaves."""

INFRA_ARGV1 = frozenset({"db-proxy-child", "__gc-managed-dolt-scope-watchdog"})
"""argv[1] of a city infrastructure process (with ``nudge poll``)."""


class Refused(Exception):
    """This host is not the soak VM."""


def guard(throwaway: str = GUARD_FILE, machine_id: str = MACHINE_ID_FILE) -> None:
    """Refuse unless ``throwaway`` holds this host's own machine id.

    Only the VM's provisioning writes that file, so every harness tool refuses
    on the operator host and on any machine it was copied to."""
    try:
        want = Path(machine_id).read_text(encoding="utf-8").strip()
        have = Path(throwaway).read_text(encoding="utf-8").strip()
    except OSError as err:
        raise Refused(
            f"the soak harness runs only on the disposable soak VM ({throwaway} is missing or unreadable: {err.strerror})"
        ) from None
    if not want or have != want:
        raise Refused(f"the soak harness runs only on the disposable soak VM ({throwaway} does not hold this host's machine id)")


# --- JSON lines ---------------------------------------------------------------------


def encode_line(rec: Mapping[str, Any], limit: int = LINE_LIMIT) -> bytes:
    """``rec`` as one JSON line under ``limit`` bytes: the longest string
    values are cut (and the record marked ``truncated``) until it fits."""
    work: Rec = dict(rec)
    line = (json.dumps(work, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    while len(line) >= limit:
        longest = max(
            ((k, v) for k, v in work.items() if isinstance(v, str)),
            key=lambda kv: len(kv[1]),
            default=None,
        )
        if longest is None or len(longest[1]) <= 16:
            work = {k: work[k] for k in ("ev", "t", "kind") if k in work}
            work["truncated"] = True
            line = (json.dumps(work, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            break
        key, value = longest
        work[key] = value[: max(16, len(value) - (len(line) - limit) - 64)]
        work["truncated"] = True
        line = (json.dumps(work, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return line


def append_jsonl(path: Path, rec: Mapping[str, Any], mode: int = 0o600) -> None:
    """Append one record with a single ``write(2)`` on an ``O_APPEND`` descriptor."""
    line = encode_line(rec)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, mode)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def read_jsonl(path: Path) -> List[Rec]:
    """Every whole JSON object line of ``path`` (none when it is missing); a
    torn or foreign line is skipped."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return []
    return parse_jsonl(data.decode("utf-8", errors="replace").splitlines())


def obj(value: Any) -> Rec:
    """``value`` when it is a JSON object, else an empty one."""
    return value if isinstance(value, dict) else {}


def parse_jsonl(lines: Iterable[str]) -> List[Rec]:
    out: List[Rec] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def last_json_object(text: str) -> Optional[Rec]:
    """The last line of ``text`` that is a JSON object (gc prints one per ``--json`` call)."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    try:
        whole = json.loads(text)
    except ValueError:
        return None
    return whole if isinstance(whole, dict) else None


def write_atomic(path: Path, text: str, mode: int = 0o600) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.rename(tmp, path)


def iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


# --- paths --------------------------------------------------------------------------


@dataclass(frozen=True)
class SoakPaths:
    """Where things live on the VM for the user running the harness."""

    home: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "SoakPaths":
        return cls(home=Path(env.get("HOME") or os.path.expanduser("~")))

    @property
    def data_root(self) -> Path:
        return self.home / "soak-data"

    @property
    def current(self) -> Path:
        return self.data_root / "current"

    @property
    def cities(self) -> Path:
        return self.home / "cities"

    @property
    def harness(self) -> Path:
        return self.home / "soak"

    @property
    def pack(self) -> Path:
        return self.home / "packs" / "runtime-herdr-core"

    @property
    def pack_entry(self) -> Path:
        return self.pack / "assets" / "bin" / "gc-runtime-herdr-core"

    @property
    def live_src(self) -> Path:
        return self.home / "src" / "gascity-packs"

    @property
    def pin_backup(self) -> Path:
        """The pack copy's pinned ``hc-pin.json``, saved by the upgrade drill
        before it writes the upgrade pin (the restore's source when the VM has
        no gascity-packs clone)."""
        return self.home / "packs" / "runtime-herdr-core.hc-pin.json"

    @property
    def state_root(self) -> Path:
        """``R``: the pack's and hc's state root (the default; never overridden for a city)."""
        return self.home / ".local" / "state" / "gc-runtime-herdr-core"

    @property
    def hc_share(self) -> Path:
        return self.home / ".local" / "share" / "gc-runtime-herdr-core"

    def pinned_hc(self, version: str) -> Path:
        return self.hc_share / "hc" / version / "herdr-core"

    @property
    def optrace(self) -> Path:
        return self.data_root / "optrace" / "optrace.log"


@dataclass(frozen=True)
class City:
    """One city the harness watches and where its data goes."""

    name: str
    path: Path
    data: Path
    mode: str

    @property
    def agents(self) -> Path:
        return self.data / "agents"

    @property
    def cmd(self) -> Path:
        return self.data / "cmd"

    def file(self, name: str) -> Path:
        return self.data / name

    def flag(self, name: str) -> bool:
        """Whether a marker file (``PAUSE``, ``DRILL``, ``CONFORMANCE``, ``ABORTED``) exists."""
        return (self.data / name).exists()

    @property
    def events(self) -> Path:
        return self.data / "gc-events" / "events.jsonl"


def parse_env_file(text: str) -> Dict[str, str]:
    """``KEY=value`` lines (systemd ``EnvironmentFile`` subset: no quoting)."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def city_from_env(env: Mapping[str, str], paths: SoakPaths) -> City:
    """The active city: ``SOAK_CITY``/``SOAK_DATA`` from the environment (the
    harness units), else ``~/soak-data/current/soak.env``."""
    values: Dict[str, str] = {}
    soak_env = paths.current / "soak.env"
    if soak_env.exists():
        values = parse_env_file(soak_env.read_text(encoding="utf-8"))
    for key in ("SOAK_CITY", "SOAK_DATA", "SOAK_MODE"):
        if env.get(key):
            values[key] = env[key]
    if not values.get("SOAK_CITY") or not values.get("SOAK_DATA"):
        raise LookupError("no active city: run `soak city-init` first (no SOAK_CITY/SOAK_DATA and no current soak.env)")
    city_path = Path(values["SOAK_CITY"])
    return City(name=city_path.name, path=city_path, data=Path(values["SOAK_DATA"]), mode=values.get("SOAK_MODE", "warn"))


# --- /proc ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcStat:
    pid: int
    comm: str
    state: str
    ppid: int
    utime: int
    stime: int
    cutime: int
    cstime: int
    start: int
    """Start time in clock ticks after boot: with the pid, a process's identity."""
    rss_pages: int


def parse_stat(text: str) -> ProcStat:
    """``/proc/<pid>/stat``; the command name may hold spaces and parentheses."""
    head, _, rest = text.rpartition(")")
    pid_s, _, comm = head.partition(" (")
    f = rest.split()
    # f[0] is field 3 (state); field n is f[n - 3].
    return ProcStat(
        pid=int(pid_s),
        comm=comm,
        state=f[0],
        ppid=int(f[1]),
        utime=int(f[11]),
        stime=int(f[12]),
        cutime=int(f[13]),
        cstime=int(f[14]),
        start=int(f[19]),
        rss_pages=int(f[21]),
    )


def parse_environ(raw: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in raw.split(b"\0"):
        if b"=" in item:
            key, value = item.split(b"=", 1)
            out[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return out


def parse_cgroup(text: str) -> str:
    """The cgroup v2 path (``0::<path>``), or the last line's path."""
    path = ""
    for line in text.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3:
            path = parts[2]
            if parts[0] == "0":
                return path
    return path


def unit_of(cgroup: str) -> Optional[str]:
    """The innermost ``.service`` or ``.scope`` on a cgroup path."""
    for part in reversed(cgroup.split("/")):
        if part.endswith((".service", ".scope")):
            return part
    return None


@dataclass(frozen=True)
class ProcInfo:
    """What the harness knows about one process at one read."""

    pid: int
    ppid: int
    uid: int
    comm: str
    start: int
    state: str
    argv: Tuple[str, ...]
    env: Mapping[str, str]
    cgroup: str
    rss_kib: int
    cpu_ticks: int
    age_s: float

    @property
    def argv1(self) -> str:
        return self.argv[1] if len(self.argv) > 1 else ""


class ProcFS:
    """Reads a ``/proc`` tree (the host's by default; tests pass a synthetic one)."""

    def __init__(self, root: str = "/proc") -> None:
        self.root = Path(root)
        self._page_kib = max(1, os.sysconf("SC_PAGE_SIZE") // 1024) if hasattr(os, "sysconf") else 4
        self._hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100

    @property
    def hz(self) -> int:
        return int(self._hz)

    def pids(self) -> List[int]:
        try:
            return sorted(int(n) for n in os.listdir(self.root) if n.isdigit())
        except OSError:
            return []

    def _read(self, pid: int, name: str) -> Optional[bytes]:
        try:
            return (self.root / str(pid) / name).read_bytes()
        except OSError:
            return None

    def stat(self, pid: int) -> Optional[ProcStat]:
        raw = self._read(pid, "stat")
        if raw is None:
            return None
        try:
            return parse_stat(raw.decode("utf-8", "replace"))
        except (ValueError, IndexError):
            return None

    def argv(self, pid: int) -> Optional[Tuple[str, ...]]:
        raw = self._read(pid, "cmdline")
        if raw is None:
            return None
        if not raw:
            return ()
        return tuple(p.decode("utf-8", "replace") for p in raw.rstrip(b"\0").split(b"\0"))

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        raw = self._read(pid, "environ")
        return None if raw is None else parse_environ(raw)

    def cgroup(self, pid: int) -> Optional[str]:
        raw = self._read(pid, "cgroup")
        return None if raw is None else parse_cgroup(raw.decode("utf-8", "replace"))

    def uid(self, pid: int) -> Optional[int]:
        raw = self._read(pid, "status")
        if raw is None:
            return None
        for line in raw.decode("utf-8", "replace").splitlines():
            if line.startswith("Uid:"):
                return int(line.split()[1])
        return None

    def uptime_s(self) -> float:
        try:
            return float((self.root / "uptime").read_text(encoding="utf-8").split()[0])
        except (OSError, ValueError, IndexError):
            return 0.0

    def boot_id(self) -> str:
        try:
            return (self.root / "sys" / "kernel" / "random" / "boot_id").read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"

    def info(self, pid: int, uptime: Optional[float] = None) -> Optional[ProcInfo]:
        st = self.stat(pid)
        if st is None:
            return None
        up = self.uptime_s() if uptime is None else uptime
        uid = self.uid(pid)
        return ProcInfo(
            pid=pid,
            ppid=st.ppid,
            uid=-1 if uid is None else uid,
            comm=st.comm,
            start=st.start,
            state=st.state,
            argv=self.argv(pid) or (),
            env=self.environ(pid) or {},
            cgroup=self.cgroup(pid) or "",
            rss_kib=st.rss_pages * self._page_kib,
            cpu_ticks=st.utime + st.stime,
            age_s=max(0.0, up - st.start / self.hz),
        )

    def snapshot(self, uid: Optional[int] = None) -> Dict[int, ProcInfo]:
        """Every readable process (of ``uid`` when given)."""
        up = self.uptime_s()
        out: Dict[int, ProcInfo] = {}
        for pid in self.pids():
            info = self.info(pid, up)
            if info is None or info.state.startswith("Z"):
                continue
            if uid is not None and info.uid != uid:
                continue
            out[pid] = info
        return out

    def alive(self, pid: int, start: int) -> bool:
        st = self.stat(pid)
        return st is not None and st.start == start and not st.state.startswith("Z")


def descendants(snapshot: Mapping[int, ProcInfo], roots: Iterable[int]) -> List[int]:
    """Every process under ``roots`` (the roots excluded)."""
    children: Dict[int, List[int]] = {}
    for proc in snapshot.values():
        children.setdefault(proc.ppid, []).append(proc.pid)
    out: List[int] = []
    stack = list(roots)
    seen = set(stack)
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in seen:
                seen.add(child)
                out.append(child)
                stack.append(child)
    return out


def is_infra(proc: ProcInfo) -> bool:
    """City infrastructure by argv, as gc and the pack spot it."""
    if proc.argv1 in INFRA_ARGV1:
        return True
    return len(proc.argv) > 2 and proc.argv[1] == "nudge" and proc.argv[2] == "poll"


# --- signals ------------------------------------------------------------------------


class NotOwned(Exception):
    """The harness may not signal that process, or it is gone."""


_SYS_PIDFD_SEND_SIGNAL = 424
_SYS_PIDFD_OPEN = 434
"""The same numbers on x86_64 and aarch64 (and every architecture since Linux 5.3)."""


def _pidfd_calls() -> Tuple[Callable[[int], int], Callable[[int, int], None]]:
    """``pidfd_open`` and ``pidfd_send_signal``: Python's own (3.9+ built on a
    glibc that has them), else the raw syscalls through ctypes."""
    py_open: Optional[Callable[[int], int]] = getattr(os, "pidfd_open", None)
    py_send: Optional[Callable[[int, int], None]] = getattr(signals, "pidfd_send_signal", None)
    if py_open is not None and py_send is not None:
        return py_open, py_send
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    syscall = libc.syscall
    syscall.restype = ctypes.c_long

    def raw_open(pid: int) -> int:
        fd = int(syscall(ctypes.c_long(_SYS_PIDFD_OPEN), ctypes.c_int(pid), ctypes.c_uint(0)))
        if fd < 0:
            err = ctypes.get_errno()
            raise ProcessLookupError(err, os.strerror(err)) if err == 3 else OSError(err, os.strerror(err))
        return fd

    def raw_send(fd: int, sig: int) -> None:
        rc = int(syscall(ctypes.c_long(_SYS_PIDFD_SEND_SIGNAL), ctypes.c_int(fd), ctypes.c_int(sig), None, ctypes.c_uint(0)))
        if rc < 0:
            err = ctypes.get_errno()
            raise ProcessLookupError(err, os.strerror(err)) if err == 3 else OSError(err, os.strerror(err))

    return raw_open, raw_send


def signal_owned(pid: int, sig: int, start: int, owns: Callable[[int], Optional[str]], procfs: ProcFS) -> None:
    """Signal ``pid`` only if it is still the process started at ``start`` and
    ``owns(pid)`` returns ``None`` (else the refusal reason).

    The pidfd is opened first, then the process is judged, then the signal
    goes through the pidfd: a pid reused in between is never signalled."""
    pidfd_open, send = _pidfd_calls()
    try:
        fd = pidfd_open(pid)
    except ProcessLookupError:
        raise NotOwned(f"pid {pid} is gone") from None
    try:
        if not procfs.alive(pid, start):
            raise NotOwned(f"pid {pid} is no longer the process started at tick {start}")
        reason = owns(pid)
        if reason is not None:
            raise NotOwned(f"pid {pid}: {reason}")
        try:
            send(fd, sig)
        except ProcessLookupError:
            pass
    finally:
        os.close(fd)


# --- commands -----------------------------------------------------------------------


@dataclass(frozen=True)
class CmdResult:
    argv: Tuple[str, ...]
    code: int
    out: str
    err: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0

    def json(self) -> Optional[Rec]:
        return last_json_object(self.out)

    def tail(self, n: int = 600) -> str:
        text = (self.err or self.out).strip()
        return text[-n:]


def run(
    argv: Sequence[str],
    *,
    cwd: Optional[str] = None,
    timeout: float = 120.0,
    env: Optional[Mapping[str, str]] = None,
    stdin: Optional[str] = None,
) -> CmdResult:
    """Run a command to completion; a timeout is exit 124, a missing binary 127."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            env=None if env is None else dict(env),
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as err:
        out = err.stdout if isinstance(err.stdout, str) else (err.stdout or b"").decode("utf-8", "replace")
        errs = err.stderr if isinstance(err.stderr, str) else (err.stderr or b"").decode("utf-8", "replace")
        return CmdResult(tuple(argv), 124, out, errs, time.monotonic() - t0, timed_out=True)
    except FileNotFoundError as err:
        return CmdResult(tuple(argv), 127, "", str(err), time.monotonic() - t0)
    return CmdResult(tuple(argv), proc.returncode, proc.stdout, proc.stderr, time.monotonic() - t0)


def cmd_record(action: str, res: CmdResult, **extra: Any) -> Rec:
    rec: Rec = {
        "t": time.time(),
        "action": action,
        "argv": list(res.argv),
        "exit": res.code,
        "dur_s": round(res.duration_s, 3),
    }
    parsed = res.json()
    if parsed is not None:
        rec["json"] = parsed
    else:
        rec["tail"] = res.tail(400)
    rec.update(extra)
    return rec


@dataclass
class Clock:
    """Wall and monotonic time, replaceable in tests."""

    wall: Callable[[], float] = field(default=time.time)
    mono: Callable[[], float] = field(default=time.monotonic)
