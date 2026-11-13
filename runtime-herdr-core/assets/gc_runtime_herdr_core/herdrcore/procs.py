"""The host's process table: one snapshot per op, read the way gc reads it.

On Linux the snapshot comes from ``/proc`` (an injectable root, so tests use
a fake tree); elsewhere from ``ps -ww``. A process's start-time token tells a
recycled pid from the process captured earlier, so nothing is signalled
unless it is still the same process. On Linux the token counts clock ticks
from boot, so one kept across ops holds only with the boot it was read in
(:meth:`ProcSource.boot`): after a reboot it may name another process.

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

Infrastructure is never killed with a session, nor is anything under it.
The infrastructure verbs (:mod:`.infra_argv`) mirror gascity
``internal/runtime/proctable/infrastructure_argv.go`` (gc's managed Dolt
watchdog, bd's database proxy, gc's nudge poller), and tmux follows its
``isInfrastructureCommand`` (gc never reports a tmux server or client as a
session's root, and never signals one): a tmux server copies its founder's
environment, so one founded from inside a session carries that session's
identity into every pane it later runs, the user's own shells and editors
and, for a server a gc command founded, a whole tmux-runtime city. As in
gc, tmux is known by its exact names: a renamed tmux (``tmux-next``) or a
GNU ``screen`` server is not fenced. Fencing everything under a server is
the pack's own choice: gc fences the tmux process alone and reads each
pane as a root of its own, but the token scan here would end every pane
of a server founded from inside the session. The fence covers only what
still runs under a server: a process detached from a pane (re-parented to
init) is not fenced, and work an agent runs under tmux is, so it outlives
the session's stop.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from typing import Callable, Collection, Dict, Final, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .infra_argv import is_infrastructure_argv

INTERPRETERS: Final = frozenset({"node", "bun", "npx", "deno"})
RUNNER_SUBCOMMANDS: Final = frozenset({"run", "exec", "x"})
NAME_ALIASES: Final[Mapping[str, Tuple[str, ...]]] = {"kimi": ("kimi-code",)}

TMUX_NAMES: Final = frozenset({"tmux", "tmux:", "tmux: server", "tmux: client"})
"""gc's ``isInfrastructureCommand``: the tmux executable, and the titles tmux
sets through setproctitle (``tmux:`` is the first word ``ps`` splits off a
titled ``tmux: server``). Exact, path-stripped: a ``tmux-*`` wrapper may be
an agent."""

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

    def environs(self, pids: Iterable[int]) -> Dict[int, Dict[str, str]]:
        """The environments of ``pids``, one :meth:`environ` each; a process
        that is gone or cannot be read is left out."""
        out: Dict[int, Dict[str, str]] = {}
        for pid in pids:
            try:
                env = self.environ(pid)
            except ProcError:
                continue
            if env is not None:
                out[pid] = env
        return out

    def exe(self, pid: int) -> Optional[str]:
        """The path of the executable ``pid`` runs; None when it cannot be told."""
        return None

    def cgroup(self, pid: int) -> Optional[str]:
        """``pid``'s control group path (Linux, cgroup v2 or the systemd
        hierarchy); None when it cannot be told."""
        return None

    def socket_holders(self, path: str, pids: Iterable[int]) -> Optional[Set[int]]:
        """Which of ``pids`` hold a Unix socket bound at ``path``; None when
        that cannot be told."""
        return None

    def started_ms(self, proc: Proc) -> Optional[int]:
        """When ``proc`` started, in wall-clock milliseconds; None when that
        cannot be told."""
        return None

    def boot(self) -> Optional[str]:
        """The boot the start-time tokens count from: a token kept with
        another boot's names another process. Empty where tokens are
        wall-clock times, which hold across boots; None when it cannot be
        told."""
        return ""

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

    def exe(self, pid: int) -> Optional[str]:
        try:
            return os.readlink(os.path.join(self._root, str(pid), "exe"))
        except OSError:
            return None

    def cgroup(self, pid: int) -> Optional[str]:
        try:
            raw = self._read(pid, "cgroup").decode("utf-8", "surrogateescape")
        except OSError:
            return None
        return parse_cgroup(raw)

    def socket_holders(self, path: str, pids: Iterable[int]) -> Optional[Set[int]]:
        try:
            with open(os.path.join(self._root, "net", "unix"), "rb") as handle:
                table = handle.read().decode("utf-8", "surrogateescape")
        except OSError:
            return None
        inodes: Set[str] = set()
        for line in table.splitlines()[1:]:
            fields = line.split(None, 7)
            if len(fields) == 8 and fields[7] == path:
                inodes.add(f"socket:[{fields[6]}]")
        holders: Set[int] = set()
        if not inodes:
            return holders
        for pid in pids:
            fd_dir = os.path.join(self._root, str(pid), "fd")
            try:
                fds = os.listdir(fd_dir)
            except OSError:
                continue
            for fd in fds:
                try:
                    if os.readlink(os.path.join(fd_dir, fd)) in inodes:
                        holders.add(pid)
                        break
                except OSError:
                    continue
        return holders

    def started_ms(self, proc: Proc) -> Optional[int]:
        """The boot time (``btime`` in ``stat``) plus the start time's clock ticks."""
        if not proc.start.isdigit():
            return None
        try:
            with open(os.path.join(self._root, "stat"), "rb") as handle:
                lines = handle.read().decode("ascii", "replace").splitlines()
            ticks = os.sysconf("SC_CLK_TCK")
        except (OSError, ValueError):
            return None
        for line in lines:
            words = line.split()
            if len(words) == 2 and words[0] == "btime" and words[1].isdigit() and ticks > 0:
                return int(words[1]) * 1000 + int(proc.start) * 1000 // ticks
        return None

    def boot(self) -> Optional[str]:
        """The kernel's boot id (``sys/kernel/random/boot_id``): ``starttime``
        counts clock ticks from boot."""
        try:
            with open(os.path.join(self._root, "sys", "kernel", "random", "boot_id"), "rb") as handle:
                text = handle.read().decode("ascii", "replace").strip()
        except OSError:
            return None
        return text or None

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

    def started_ms(self, proc: Proc) -> Optional[int]:
        """``lstart`` ("Mon Nov 9 08:00:00 2026", local time), to the second."""
        try:
            return int(time.mktime(time.strptime(proc.start, "%a %b %d %H:%M:%S %Y"))) * 1000
        except (ValueError, OverflowError):
            return None

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
        return _ps_environ(text.split())

    def exe(self, pid: int) -> Optional[str]:
        # macOS ps prints the executable's full path as comm.
        try:
            text = self._ps("-o", "comm=", "-p", str(pid)).strip()
        except ProcError:
            return None
        return text if text.startswith("/") else None

    def environs(self, pids: Iterable[int]) -> Dict[int, Dict[str, str]]:
        # One ps for every process, as gc's proctable reads them on macOS;
        # a ps per process when that one fails.
        wanted = set(pids)
        try:
            text = self._ps("-E", "-ww", "-axo", "pid=,command=")
        except ProcError:
            return ProcSource.environs(self, wanted)
        out: Dict[int, Dict[str, str]] = {}
        for line in text.splitlines():
            words = line.split()
            if words and words[0].isdigit() and int(words[0]) in wanted:
                out[int(words[0])] = _ps_environ(words[1:])
        return out


def _ps_environ(words: Iterable[str]) -> Dict[str, str]:
    """The ``KEY=value`` words of a ``ps -E`` command, the command's own too.

    Lossy: an argv word of that form reads as environment, and a value is
    cut at whitespace. A false token match needs the literal token on a
    command line (gc mints it as 32 random hex characters, a secret)."""
    env: Dict[str, str] = {}
    for word in words:
        key, sep, value = word.partition("=")
        if sep and key and (key[0].isalpha() or key[0] == "_") and all(c.isalnum() or c == "_" for c in key):
            env[key] = value
    return env


def parse_cgroup(text: str) -> Optional[str]:
    """The path of ``/proc/<pid>/cgroup``: the unified (``0::``) entry, else
    the systemd hierarchy's (``name=systemd``)."""
    fallback: Optional[str] = None
    for line in text.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        if parts[0] == "0" and parts[1] == "":
            return parts[2]
        if parts[1] == "name=systemd":
            fallback = parts[2]
    return fallback


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


def subtree(
    snapshot: Snapshot, root: int, index: Optional[Mapping[int, List[int]]] = None, *, prune: Collection[int] = ()
) -> List[Proc]:
    """``root`` and every descendant, in breadth-first order; a descendant in
    ``prune`` is left out, and so is everything under it."""
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
        queue.extend(kid for kid in kids.get(pid, ()) if kid not in prune)
    return out


def is_tmux(proc: Proc) -> bool:
    """Whether ``proc`` is a tmux server or client: its command name or its
    argv[0] is one of :data:`TMUX_NAMES`, path-stripped."""
    heads = (proc.comm, proc.argv[0] if proc.argv else "")
    return any(os.path.basename(head.strip()) in TMUX_NAMES for head in heads if head.strip())


def fenced_pids(snapshot: Snapshot, *, own: Collection[int] = ()) -> FrozenSet[int]:
    """Every infrastructure process (city infrastructure, tmux) and its whole
    subtree. A tmux server above one of ``own`` (the programs a kill ends:
    their core was started from a tmux pane) fences none of that program's
    tree; one inside it still fences its own subtree."""
    index = children_index(snapshot)
    fenced: Set[int] = set()
    for proc in snapshot.values():
        if is_infrastructure_argv(proc.argv):
            fenced.update(p.pid for p in subtree(snapshot, proc.pid, index))
        elif is_tmux(proc) and proc.pid not in fenced:
            fenced.update(p.pid for p in subtree(snapshot, proc.pid, index, prune=own))
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


def still_same(proc: Proc, snapshot: Snapshot) -> Optional[bool]:
    """Whether the captured ``proc`` still runs as the same process (same
    start token): False when its pid is gone, a zombie or another process;
    None when that cannot be told, as it was captured without a start token
    or its pid now reads opaque. Such a process may survive, and is never
    signalled: its pid may have been recycled."""
    current = snapshot.get(proc.pid)
    if current is None or current.zombie:
        return False
    if proc.opaque or not proc.start or current.opaque:
        return None
    return current.start == proc.start


def kill_captured(
    source: ProcSource,
    procs: Sequence[Proc],
    *,
    grace_s: float = 2.0,
    pause: Callable[[float], None],
) -> List[Proc]:
    """TERM every captured process that is still the same process, then KILL
    whatever is left after ``grace_s``. Returns the processes that may still
    run: those that outlived their KILL, and those that could not be told
    from what was captured (:func:`still_same` is None on a re-read), which
    are never signalled again.

    Nothing is signalled unless a fresh read of the process table shows it is
    still the captured process: when the table cannot be re-read, every
    target not yet known to have ended is reported as surviving and none is
    signalled."""
    unsure: List[Proc] = []

    def alive(targets: Sequence[Proc]) -> Optional[List[Proc]]:
        try:
            now = source.snapshot()
        except ProcError:
            return None
        same: List[Proc] = []
        for proc in targets:
            fate = still_same(proc, now)
            if fate is None:
                unsure.append(proc)
            elif fate:
                same.append(proc)
        return same

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
            return remaining + unsure
        remaining = current
    final = alive(remaining)
    if final is None:
        return remaining + unsure
    for proc in final:
        source.kill(proc.pid, signal.SIGKILL)
    if final:
        pause(0.1)
        after = alive(final)
        return (final if after is None else after) + unsure
    return unsure


def scan_environ(source: ProcSource, snapshot: Snapshot, key: str, value: str) -> List[Proc]:
    """This user's processes whose environment holds ``key=value``.

    A process whose environment cannot be read is skipped: a non-dumpable
    process of the user (ssh-agent, for one) has a root-owned ``environ``,
    and failing on it would fail every scan."""
    return scan_environ_any(source, snapshot, key, frozenset({value}))


def scan_environ_any(source: ProcSource, snapshot: Snapshot, key: str, values: FrozenSet[str]) -> List[Proc]:
    """This user's processes whose environment holds ``key`` set to one of
    ``values`` (never an empty one), read as :func:`scan_environ` reads."""
    wanted = values - {""}
    if not wanted:
        return []
    uid = os.getuid()
    mine = [proc for proc in snapshot.values() if proc.uid == uid and proc.pid != os.getpid()]
    envs = source.environs(proc.pid for proc in mine)
    return [proc for proc in mine if envs.get(proc.pid, {}).get(key, "") in wanted]
