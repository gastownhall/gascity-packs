"""The host's process table: one snapshot per op, read the way gc reads it.

On Linux the snapshot comes from ``/proc`` (an injectable root, so tests use
a fake tree); elsewhere from ``ps -ww``. A process's start-time token tells a
recycled pid from the process captured earlier, so nothing is signalled
unless it is still the same process.

A process that exits during the read is left out. One of this user's that
cannot be read is *opaque*: it has no name or command, and its parent is
the process whose children list (``task/*/children``) names it. A
``hidepid=1`` ``/proc`` refuses every non-dumpable process, even this
user's own (an ssh session's, ssh-agent). Only a subtree that reaches an
opaque process cannot tell that no agent runs there ("cannot tell", never
"not there"). A kernel that keeps no children lists cannot place an opaque
process, so there it fails the snapshot. Another user's process that cannot
be read is left out, as that ``/proc`` refuses every other user's: viewers
and agents are this user's processes.

Agent liveness follows gascity ``docs/reference/exec-session-provider.md``
"Agent liveness": a process matches when its command name's or argv[0]'s base
name is one of the names, or when argv[0] is an interpreter and its first
argument that is neither a flag nor a runner subcommand names one, with or
without its extension; ``kimi`` also matches ``kimi-code``, and ``gc`` the
base name of the session's gc binary.

The infrastructure verbs mirror gascity
``internal/runtime/proctable/infrastructure_argv.go``: such a process (gc's
managed Dolt watchdog, bd's database proxy, gc's nudge poller) and its whole
subtree are never killed with a session.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass, replace
from typing import Callable, Dict, Final, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

INTERPRETERS: Final = frozenset({"node", "bun", "npx", "deno"})
RUNNER_SUBCOMMANDS: Final = frozenset({"run", "exec", "x"})
NAME_ALIASES: Final[Mapping[str, Tuple[str, ...]]] = {"kimi": ("kimi-code",)}

MANAGED_DOLT_SCOPE_WATCHDOG_VERB: Final = "__gc-managed-dolt-scope-watchdog"
BD_PROXY_CHILD_VERB: Final = "db-proxy-child"
NUDGE_POLLER_VERB: Final = "nudge"
NUDGE_POLLER_SUBVERB: Final = "poll"

_PS_TIMEOUT_S: Final = 2.0


class ProcError(Exception):
    """The process table cannot be read."""


@dataclass(frozen=True)
class Proc:
    """One process as the snapshot saw it."""

    pid: int
    ppid: int
    uid: int
    start: str
    """A token for when the process started; equal tokens mean the same process."""
    comm: str
    argv: Tuple[str, ...]
    opaque: bool = False
    """Whether it, or the list of its children, could not be read: what runs
    under it cannot be told."""
    state: str = ""
    """The kernel's state letter; ``Z`` is a zombie: it runs nothing."""

    @property
    def zombie(self) -> bool:
        return self.state.startswith("Z")


Snapshot = Mapping[int, Proc]


class ProcSource:
    """Reads and signals processes. The base class reads the live host."""

    lossy_environ = False
    """Whether :meth:`environ` cuts values at whitespace (``ps -E``)."""

    def snapshot(self) -> Dict[int, Proc]:
        raise NotImplementedError

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        """``pid``'s environment; None when the process is gone.

        Raises :class:`ProcError` when it runs but cannot be read: that is
        "cannot tell", never "nothing there"."""
        raise NotImplementedError

    def kill(self, pid: int, sig: int) -> None:
        """Signal ``pid``; a process that is gone is not an error."""
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


class LinuxProcs(ProcSource):
    """``/proc`` under ``root``; ``uid`` is the user whose processes count
    (default: this process's): one that cannot be read is opaque, and
    another user's is left out."""

    def __init__(self, root: str = "/proc", *, uid: Optional[int] = None) -> None:
        self._root = root
        self._uid = os.getuid() if uid is None else uid

    def _read(self, pid: int, leaf: str) -> bytes:
        with open(os.path.join(self._root, str(pid), leaf), "rb") as handle:
            return handle.read()

    def _proc(self, pid: int) -> Optional[Proc]:
        try:
            uid = os.stat(os.path.join(self._root, str(pid))).st_uid
        except (FileNotFoundError, ProcessLookupError):
            return None  # gone between the listing and the read
        except OSError as err:
            raise ProcError(f"cannot read pid {pid}: {err.strerror}") from None
        try:
            stat_line = self._read(pid, "stat").decode("utf-8", "surrogateescape")
            cmdline = self._read(pid, "cmdline")
        except (FileNotFoundError, ProcessLookupError):
            return None
        except OSError:
            if uid != self._uid:
                return None  # another user's, hidden from this one
            return Proc(pid=pid, ppid=0, uid=uid, start="", comm="", argv=(), opaque=True)
        open_paren, close_paren = stat_line.find("("), stat_line.rfind(")")
        if open_paren < 0 or close_paren < open_paren:
            return None
        fields = stat_line[close_paren + 2 :].split()
        # fields[0] is the state (stat field 3): ppid is field 4, starttime field 22.
        if len(fields) < 20:
            return None
        try:
            ppid = int(fields[1])
        except ValueError:
            return None
        argv = tuple(part.decode("utf-8", "surrogateescape") for part in cmdline.split(b"\0") if part)
        return Proc(
            pid=pid,
            ppid=ppid,
            uid=uid,
            start=fields[19],
            comm=stat_line[open_paren + 1 : close_paren],
            argv=argv,
            state=fields[0],
        )

    def snapshot(self) -> Dict[int, Proc]:
        try:
            entries = os.listdir(self._root)
        except OSError as err:
            raise ProcError(f"cannot list {self._root}: {err.strerror}") from None
        out: Dict[int, Proc] = {}
        for entry in entries:
            if entry.isdigit():
                proc = self._proc(int(entry))
                if proc is not None:
                    out[proc.pid] = proc
        if any(proc.opaque for proc in out.values()):
            self._place(out)
        if not out:
            raise ProcError(f"{self._root} lists no process")
        return out

    def _children(self, pid: int) -> Optional[List[int]]:
        """The pids that ``pid``'s threads list as their children; None when
        it is gone or the kernel keeps no such lists. Raises OSError when
        they cannot be read."""
        try:
            tids = os.listdir(os.path.join(self._root, str(pid), "task"))
        except (FileNotFoundError, ProcessLookupError):
            return None
        kids: List[int] = []
        listed = False
        for tid in tids:
            try:
                raw = self._read(pid, os.path.join("task", tid, "children"))
            except (FileNotFoundError, ProcessLookupError):
                continue  # the thread exited, or the kernel keeps no lists
            listed = True
            kids.extend(int(word) for word in raw.split() if word.isdigit())
        return kids if listed else None

    def _place(self, out: Dict[int, Proc]) -> None:
        """Give each opaque process the parent whose children list names it (0
        when none does). A process whose list cannot be read turns opaque."""
        hidden = [proc for proc in out.values() if proc.opaque]
        parents: Dict[int, int] = {}
        listed = False
        for proc in list(out.values()):
            if proc.opaque or proc.uid != self._uid:
                continue
            try:
                kids = self._children(proc.pid)
            except OSError:
                out[proc.pid] = replace(proc, opaque=True)  # what runs under it cannot be told
                continue
            listed = listed or kids is not None
            parents.update((kid, proc.pid) for kid in kids or ())
        if not listed:
            raise ProcError(f"cannot place pid {hidden[0].pid}: {self._root} keeps no children lists")
        for proc in hidden:
            if proc.pid in parents:
                out[proc.pid] = replace(proc, ppid=parents[proc.pid])

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        try:
            raw = self._read(pid, "environ")
        except (FileNotFoundError, ProcessLookupError):
            return None
        except OSError as err:
            raise ProcError(f"cannot read the environment of pid {pid}: {err.strerror}") from None
        return parse_environ(raw)


class PsProcs(ProcSource):
    """``ps`` on hosts without ``/proc`` (macOS)."""

    lossy_environ = True

    def _ps(self, *args: str) -> str:
        try:
            done = subprocess.run(
                ["ps", *args],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=_PS_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as err:
            raise ProcError(f"ps: {err}") from None
        if done.returncode != 0:
            raise ProcError(f"ps exited {done.returncode}")
        return done.stdout.decode("utf-8", "surrogateescape")

    def snapshot(self) -> Dict[int, Proc]:
        out: Dict[int, Proc] = {}
        comms: Dict[int, str] = {}
        for line in self._ps("-axo", "pid=,comm=").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                comms[int(parts[0])] = parts[1]
        for line in self._ps("-ww", "-axo", "pid=,ppid=,uid=,stat=,lstart=,args=").splitlines():
            parts = line.split()
            # lstart is five words: "Mon Nov  9 08:00:00 2026".
            if len(parts) < 10 or not (parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit()):
                continue
            pid = int(parts[0])
            out[pid] = Proc(
                pid=pid,
                ppid=int(parts[1]),
                uid=int(parts[2]),
                start=" ".join(parts[4:9]),
                comm=comms.get(pid, ""),
                argv=tuple(parts[9:]),
                state=parts[3],
            )
        if not out:
            raise ProcError("ps lists no process")
        return out

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        # ps -E appends the environment to the command; values holding
        # spaces are cut at the space, which keeps keys and path values.
        try:
            text = self._ps("-E", "-ww", "-o", "command=", "-p", str(pid))
        except ProcError:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return None
            except PermissionError:
                pass
            raise
        env: Dict[str, str] = {}
        for word in text.split():
            key, sep, value = word.partition("=")
            if sep and key and (key[0].isalpha() or key[0] == "_") and all(c.isalnum() or c == "_" for c in key):
                env[key] = value
        return env


def default_source() -> ProcSource:
    """The live host's process table."""
    if sys.platform.startswith("linux") and os.path.isdir("/proc/self"):
        return LinuxProcs()
    return PsProcs()


def parse_environ(raw: bytes) -> Dict[str, str]:
    """A NUL-separated ``KEY=value`` block, as ``/proc/<pid>/environ`` holds it."""
    env: Dict[str, str] = {}
    for item in raw.split(b"\0"):
        key, sep, value = item.partition(b"=")
        if sep and key:
            env[key.decode("utf-8", "surrogateescape")] = value.decode("utf-8", "surrogateescape")
    return env


# --- trees -----------------------------------------------------------------------


def children_index(snapshot: Snapshot) -> Dict[int, List[int]]:
    """Each pid's direct children."""
    index: Dict[int, List[int]] = {}
    for proc in snapshot.values():
        index.setdefault(proc.ppid, []).append(proc.pid)
    return index


def subtree(snapshot: Snapshot, root: int, index: Optional[Mapping[int, List[int]]] = None) -> List[Proc]:
    """``root`` and every descendant, in breadth-first order."""
    if root not in snapshot:
        return []
    kids = children_index(snapshot) if index is None else index
    out: List[Proc] = []
    queue = [root]
    seen: Set[int] = set()
    while queue:
        pid = queue.pop(0)
        if pid in seen or pid not in snapshot:
            continue
        seen.add(pid)
        out.append(snapshot[pid])
        queue.extend(kids.get(pid, ()))
    return out


def is_infrastructure_argv(argv: Sequence[str]) -> bool:
    """gc's ``proctable.IsCityInfrastructureArgv``: argv[0] is ignored."""
    if len(argv) < 2:
        return False
    if argv[1] in (MANAGED_DOLT_SCOPE_WATCHDOG_VERB, BD_PROXY_CHILD_VERB):
        return True
    return argv[1] == NUDGE_POLLER_VERB and len(argv) > 2 and argv[2] == NUDGE_POLLER_SUBVERB


def fenced_pids(snapshot: Snapshot) -> FrozenSet[int]:
    """Every city-infrastructure process and its whole subtree."""
    index = children_index(snapshot)
    fenced: Set[int] = set()
    for proc in snapshot.values():
        if proc.pid not in fenced and is_infrastructure_argv(proc.argv):
            fenced.update(p.pid for p in subtree(snapshot, proc.pid, index))
    return frozenset(fenced)


# --- agent liveness ------------------------------------------------------------------


def expand_names(names: Iterable[str], gc_binary: str = "") -> FrozenSet[str]:
    """The process names to match, with gc's aliases."""
    out: Set[str] = set()
    for name in names:
        name = name.strip()
        if not name:
            continue
        out.add(name)
        out.update(NAME_ALIASES.get(name, ()))
        if name == "gc" and gc_binary:
            out.add(os.path.basename(gc_binary))
    return frozenset(out)


def matches(proc: Proc, names: FrozenSet[str]) -> bool:
    """Whether ``proc`` runs one of ``names`` (gc's process-table rules); a
    zombie runs nothing."""
    if proc.zombie:
        return False
    if os.path.basename(proc.comm) in names:
        return True
    if not proc.argv:
        return False
    head = os.path.basename(proc.argv[0])
    if head in names:
        return True
    if head not in INTERPRETERS:
        return False
    for arg in proc.argv[1:]:
        if arg.startswith("-") or arg in RUNNER_SUBCOMMANDS:
            continue
        base = os.path.basename(arg)
        return base in names or os.path.splitext(base)[0] in names
    return False


LAUNCHER_NAME: Final = "gc-herdr-core-launch"


LAUNCH_WRAPPERS: Final = frozenset({"systemd-run", "env"})
"""What the launcher execs on the way to the agent, keeping the pid."""


def is_launching(snapshot: Snapshot, root: int) -> bool:
    """Whether ``root`` has not reached the agent yet: it is still the pack's
    launcher, or ``systemd-run`` or ``env`` on the way to it with nothing
    started under it. A wrapper with children has launched: the agent is
    looked for among them."""
    proc = snapshot.get(root)
    if proc is None or not proc.argv:
        return False
    if any(os.path.basename(arg) == LAUNCHER_NAME for arg in proc.argv[:4]):
        return True
    if os.path.basename(proc.argv[0]) not in LAUNCH_WRAPPERS:
        return False
    return not any(p.ppid == root for p in snapshot.values())


def find_agent(snapshot: Snapshot, root: int, names: FrozenSet[str]) -> Optional[Proc]:
    """The first process under ``root`` (``root`` included) that runs one of ``names``."""
    for proc in subtree(snapshot, root):
        if matches(proc, names):
            return proc
    return None


def opaque_under(snapshot: Snapshot, root: int) -> bool:
    """Whether an opaque process runs under ``root`` (``root`` included): an
    agent there may be one that cannot be read."""
    return any(proc.opaque for proc in subtree(snapshot, root))


# --- killing ---------------------------------------------------------------------------


def still_same(source: ProcSource, proc: Proc, snapshot: Optional[Snapshot] = None) -> bool:
    """Whether ``proc`` is still running as the same process (same start
    token). An opaque process has no start token to compare, so it never is:
    nothing is signalled that could be a recycled pid."""
    if proc.opaque or not proc.start:
        return False
    current = (snapshot if snapshot is not None else source.snapshot()).get(proc.pid)
    return current is not None and not current.opaque and current.start == proc.start and not current.zombie


def kill_captured(
    source: ProcSource,
    procs: Sequence[Proc],
    *,
    grace_s: float = 2.0,
    pause: Callable[[float], None],
) -> List[Proc]:
    """TERM every captured process that is still the same process, then KILL
    whatever is left after ``grace_s``. Returns the processes still alive.

    Nothing is signalled unless a fresh read of the process table shows it is
    still the captured process: when the table cannot be re-read, every
    target is reported as surviving and none is signalled."""

    def alive(targets: Sequence[Proc]) -> Optional[List[Proc]]:
        try:
            now = source.snapshot()
        except ProcError:
            return None
        return [p for p in targets if still_same(source, p, now)]

    first = alive(procs)
    if first is None:
        return list(procs)
    remaining = first
    for proc in remaining:
        source.kill(proc.pid, signal.SIGTERM)
    waited = 0.0
    while remaining and waited < grace_s:
        pause(0.1)
        waited += 0.1
        current = alive(remaining)
        if current is None:
            return remaining
        remaining = current
    final = alive(remaining)
    if final is None:
        return remaining
    for proc in final:
        source.kill(proc.pid, signal.SIGKILL)
    if final:
        pause(0.1)
        after = alive(final)
        return final if after is None else after
    return final


def scan_environ(source: ProcSource, snapshot: Snapshot, key: str, value: str) -> List[Proc]:
    """This user's processes whose environment holds ``key=value``.

    A process whose environment cannot be read is skipped: a non-dumpable
    process of the user (ssh-agent, for one) has a root-owned ``environ``,
    and failing on it would fail every scan."""
    uid = os.getuid()
    found: List[Proc] = []
    for proc in snapshot.values():
        if proc.uid != uid or proc.pid == os.getpid():
            continue
        try:
            env = source.environ(proc.pid)
        except ProcError:
            continue
        if env is not None and env.get(key) == value:
            found.append(proc)
    return found
