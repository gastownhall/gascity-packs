"""Which core is the pack's, where the core's live environment does not
show who started it: a core hc placed under launchd (macOS), and a core a
holder restarted under systemd.

**launchd.** On macOS hc starts the core as a one-shot launchd job (hc
``platform/macos_launchd.rs``): the job runs ``<hc> --hc-launchd``, which
forks, and the core execs as ``<hc> --hc-launchd <dir>/ready``, where
``<dir>`` is ``hc-launchd-<pid>-<ns>-<32 hex>``: ``<pid>`` is the process
that asked launchd for the core (the hc CLI that ran ``hc server start`` or
``hc server restart``, or a holder restarting a core that crashed, hc
``holder.rs``) and ``<ns>`` the wall-clock time it asked, in nanoseconds.
The job runs with launchd's environment and the core takes its starter's
only inside the process, so ``ps -E`` shows nothing of its starter. Such a
core is judged by its starter:

* **The pack's own hc started it.** Before the pack waits on the hc it
  runs for ``hc server start`` (or ``restart``), it adds that hc's pid and
  the wall-clock time it ran it to :data:`PENDING_FILE`, the list of the
  pack's recent starts, and once the hc ends, the time it ended. A launchd
  core whose starter pid is the pid of one of them, asked for within that
  one's time, is the pack's: until the hc is reaped its pid is no one
  else's, and after it ended nothing it asked for is newer. An entry whose
  hc never ended (the pack was killed waiting on it) counts as ended
  :data:`PENDING_OPEN_MS` after it began, longer than the pack ever waits
  on its hc. Each start changes only its own entry, so a start that checks
  while another start of the pack still runs, or after one whose hc timed
  out (hc asked launchd, the core came up late), accepts that start's
  core, however many starts ran since. When a start accepts it, or once
  ``hc server start`` returns and the core answers, the pack records the
  core: its pid, its process start token (with the boot the token counts
  from) and its ``server.status`` core id, in :data:`IDENTITY_FILE`. A live
  core that matches all of it is the pack's. An entry goes once that record
  supersedes it, once its start finished with the core answering, or, at a
  later start, once it ended more than :data:`PENDING_KEEP_MS` before. A
  core another starter brought up at the same time, which the pack's hc
  found answering, names that starter, and is never accepted.
* **A holder of the city restarted it.** Its starter is a live holder of the
  city's socket, run by this user, that started no later than the core was
  asked for (a later one has a pid that was another process's then). A
  holder is spawned directly, with the environment its core restored, so
  it is judged by that environment (:func:`.core.foreign_reason`). A start
  that accepts it records it as above, so it stays the pack's once that
  holder ends.

Any other launchd core was started by someone else's hc, and is foreign.

**systemd.** A core hc placed under systemd is judged by its unit's
environment file, where hc writes its starter's environment (:mod:`.core`).
A holder runs as a unit too, started by its core, so its environment is
that core's (the manager's block when that core started included, hc
``client.rs`` ``spawn_detached``), and a core a holder restarts has the
holder's whole environment in its file: names the pack never sets, which
are the pack's only by lineage. So when a start accepts a systemd core, the
pack records what every holder of that core carries: its environment less
systemd's service variables, as one SHA-256 digest per value, by name, in
:data:`LINEAGE_FILE`. A name the pack never sets is the pack's in a unit
file only with the value recorded for it (:class:`Lineage`). No live
holder is asked, so a holder a foreign core started never vouches for it,
and a core the pack's holder restarted stays the pack's once that holder
ends.

Everywhere else a core's environment can be judged, so nothing is recorded.
Only a start records: ``status`` and doctor only read (:mod:`.core`).

The files are 0600 in the pack's 0700 state directory, written through a
temp file and a rename; one that is not a private regular file of this user
is not read. A start that records nothing leaves the previous record, which
matches only the process (or the values) it names.
"""

from __future__ import annotations

import hashlib
import os
import stat
import time
from dataclasses import dataclass, replace
from typing import Callable, Final, Mapping, Optional, Sequence, Tuple

from ..hc.types import StatusResult
from ..rpp.flock import LockFileError, LockTimeout
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from .config import write_private_file
from .context import OpContext
from .procs import Proc, ProcError

IDENTITY_FILE: Final = "core-identity.json"
LINEAGE_FILE: Final = "core-lineage.json"
PENDING_FILE: Final = "core-start.json"
PENDING_LOCK: Final = "core-start"
"""Held while the pending starts are read and rewritten."""
PENDING_LOCK_WAIT_S: Final = 5.0
PENDING_ERRORS: Final = (OSError, StateDirError, LockTimeout, LockFileError)
"""What rewriting the pending starts raises."""
PENDING_OPEN_MS: Final = 2 * 60 * 1000
"""How long an entry whose hc never ended counts as running: far longer
than the pack waits on the hc it runs (``core.CORE_START_WAIT_S``, with
``upgrade``'s stop wait), so it bounds only an entry whose pack was killed
before it could close it."""
PENDING_KEEP_MS: Final = 10 * 60 * 1000
"""How long after its hc ended a later start keeps an entry."""
PENDING_MAX: Final = 32
"""The most entries kept (the newest)."""

LAUNCHD_SENTINEL: Final = "--hc-launchd"
LAUNCHD_DIR_PREFIX: Final = "hc-launchd-"
LAUNCHD_READY: Final = "ready"
_READ_LIMIT: Final = 4096
_PENDING_READ_LIMIT: Final = 16 << 10
_LINEAGE_READ_LIMIT: Final = 256 << 10
_HEX_LEN: Final = 32


@dataclass(frozen=True)
class LaunchdStart:
    """How a launchd-placed core was asked for."""

    starter_pid: int
    """The process that asked launchd for it."""
    asked_ns: int
    """When, on the wall clock, in nanoseconds."""


def launchd_start(argv: Sequence[str]) -> Optional[LaunchdStart]:
    """The starter of a core whose argv is hc's launchd form
    (``<hc> --hc-launchd <dir>/ready``); None for any other argv. The form
    is read from the end: ``ps`` prints argv joined by spaces, so an hc path
    with spaces reads as more than one word."""
    if len(argv) < 3 or argv[-2] != LAUNCHD_SENTINEL:
        return None
    ready = argv[-1]
    if os.path.basename(ready) != LAUNCHD_READY:
        return None
    name = os.path.basename(os.path.dirname(ready))
    if not name.startswith(LAUNCHD_DIR_PREFIX):
        return None
    fields = name[len(LAUNCHD_DIR_PREFIX) :].split("-")
    if len(fields) != 3 or not (fields[0].isdigit() and fields[1].isdigit()):
        return None
    if len(fields[2]) != _HEX_LEN or not all(c in "0123456789abcdefABCDEF" for c in fields[2]):
        return None
    pid = int(fields[0])
    return LaunchdStart(starter_pid=pid, asked_ns=int(fields[1])) if pid > 0 else None


@dataclass(frozen=True)
class CoreIdentity:
    """A core process the pack started."""

    pid: int
    start: str
    """The process's start token (:attr:`.procs.Proc.start`)."""
    boot: str
    """The boot the token counts from (:meth:`.procs.ProcSource.boot`)."""
    core_id: str
    """``server.status`` ``core.id``."""


def write(ctx: OpContext, identity: CoreIdentity) -> None:
    """Record ``identity`` (raises StateDirError or OSError)."""
    doc = {"pid": identity.pid, "start": identity.start, "boot": identity.boot, "core_id": identity.core_id}
    write_private_file(ctx.state_file(IDENTITY_FILE), (dumps(doc) + "\n").encode("utf-8"))


def _read_doc(ctx: OpContext, name: str, *, limit: int = _READ_LIMIT) -> Optional[JsonObject]:
    """``name`` in the pack's state; None when there is none, or it is not a
    private regular file of this user, or not JSON. It creates no state
    (doctor reads it too)."""
    path = os.path.join(ctx.pack_state, name)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None  # none, a symlink, or unreadable
    with os.fdopen(fd, "rb") as handle:
        st = os.fstat(handle.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            return None
        raw = handle.read(limit)
    try:
        return JsonObject.of(loads(raw))
    except (JsonShapeError, ValueError):
        return None


def read(ctx: OpContext) -> Optional[CoreIdentity]:
    """The recorded identity; None when there is none or it is not to be trusted."""
    doc = _read_doc(ctx, IDENTITY_FILE)
    if doc is None:
        return None
    try:
        return CoreIdentity(
            pid=doc.req_int("pid"),
            start=doc.req_str("start"),
            boot=doc.req_str("boot"),
            core_id=doc.req_str("core_id"),
        )
    except (JsonShapeError, ValueError):
        return None


def live(ctx: OpContext, pid: int) -> Optional[Proc]:
    """``pid`` as it runs now, readable and with a start token; None when
    that cannot be told."""
    try:
        proc = ctx.host.procs.process(pid)
    except ProcError:
        return None
    if proc is None or proc.opaque or proc.zombie or not proc.start:
        return None
    return proc


def record(ctx: OpContext, status: StatusResult, *, starter_pid: int, since_ms: int) -> bool:
    """Record the core behind ``status`` as the one the pack started, when it
    is a launchd-placed core that the hc the pack ran (pid ``starter_pid``)
    asked for at or after ``since_ms`` (wall clock, taken before that hc
    ran). Returns whether it was recorded."""
    proc = live(ctx, status.pid)
    start = None if proc is None else launchd_start(proc.argv)
    if start is None or start.starter_pid != starter_pid or start.asked_ns < since_ms * 1_000_000:
        return False
    return pin(ctx, status)


def pin(ctx: OpContext, status: StatusResult, *, superseding: Optional[PendingStart] = None) -> bool:
    """Record the core behind ``status``, which a start of the pack took as
    the pack's, by its pid, process start, boot and core id; the pending
    start ``superseding`` (the one that asked for it) then goes. Returns
    whether it was recorded: when it cannot be, that entry stays, and still
    names it. Never raises."""
    proc = live(ctx, status.pid)
    boot = ctx.host.procs.boot()
    if proc is None or boot is None:
        return False
    try:
        write(ctx, CoreIdentity(pid=status.pid, start=proc.start, boot=boot, core_id=status.core.id))
    except (OSError, StateDirError):
        return False
    if superseding is not None:
        try:
            finish_start(ctx, starter_pid=superseding.starter_pid, since_ms=superseding.since_ms)
        except PENDING_ERRORS:
            pass  # the record names the core; the entry ages out
    return True


# --- the pack's pending starts (launchd) -----------------------------------------------


@dataclass(frozen=True)
class PendingStart:
    """An hc the pack runs (or ran) to start the core."""

    starter_pid: int
    since_ms: int
    """Wall clock before the pack ran it."""
    until_ms: Optional[int]
    """Wall clock once it ended; None while it runs."""

    @property
    def end_ms(self) -> int:
        """When it ended; for one never closed, :data:`PENDING_OPEN_MS` after it began."""
        return self.since_ms + PENDING_OPEN_MS if self.until_ms is None else self.until_ms

    def is_of(self, starter_pid: int, since_ms: int) -> bool:
        """Whether this is the entry of the start that ran pid ``starter_pid`` at ``since_ms``."""
        return self.starter_pid == starter_pid and self.since_ms == since_ms

    def asked(self, start: LaunchdStart) -> bool:
        """Whether this hc asked launchd for the core ``start`` names."""
        if start.starter_pid != self.starter_pid or start.asked_ns < self.since_ms * 1_000_000:
            return False
        return start.asked_ns // 1_000_000 <= self.end_ms


def read_pending(ctx: OpContext) -> Tuple[PendingStart, ...]:
    """The pack's pending starts, oldest first; none when there are none or
    the file is not to be trusted."""
    doc = _read_doc(ctx, PENDING_FILE, limit=_PENDING_READ_LIMIT)
    if doc is None:
        return ()
    try:
        return tuple(
            PendingStart(starter_pid=entry.req_int("starter_pid"), since_ms=entry.req_int("since_ms"), until_ms=entry.opt_int("until_ms"))
            for entry in doc.obj_tuple("starts", required=True)
        )
    except (JsonShapeError, ValueError):
        return ()


def pending_start(ctx: OpContext, start: LaunchdStart) -> Optional[PendingStart]:
    """The pending start whose hc asked launchd for the core ``start`` names, if any."""
    return next((entry for entry in read_pending(ctx) if entry.asked(start)), None)


def _write_pending(ctx: OpContext, starts: Sequence[PendingStart]) -> None:
    if not starts:
        try:
            os.unlink(os.path.join(ctx.pack_state, PENDING_FILE))
        except FileNotFoundError:
            pass
        return
    doc = {"starts": [{"starter_pid": s.starter_pid, "since_ms": s.since_ms, "until_ms": s.until_ms} for s in starts]}
    write_private_file(ctx.state_file(PENDING_FILE), (dumps(doc) + "\n").encode("utf-8"))


def _rewrite_pending(ctx: OpContext, change: Callable[[Tuple[PendingStart, ...]], Sequence[PendingStart]]) -> None:
    """Rewrite the pending starts as ``change`` makes them, under
    :data:`PENDING_LOCK`; nothing is written when nothing changes."""
    with ctx.lock(PENDING_LOCK, shared=False, wait_s=PENDING_LOCK_WAIT_S):
        starts = read_pending(ctx)
        changed = tuple(change(starts))
        if changed != starts:
            _write_pending(ctx, changed)


def begin_start(ctx: OpContext, *, starter_pid: int, since_ms: int) -> None:
    """Add the hc the pack now runs to start the core (pid ``starter_pid``,
    run no earlier than ``since_ms``) to the pending starts. Every other
    entry stays, but for those that ended more than :data:`PENDING_KEEP_MS`
    ago, and the newest :data:`PENDING_MAX` are kept. Raises one of
    :data:`PENDING_ERRORS`."""
    now = wall_ms()
    entry = PendingStart(starter_pid=starter_pid, since_ms=since_ms, until_ms=None)

    def add(starts: Tuple[PendingStart, ...]) -> Sequence[PendingStart]:
        kept = [s for s in starts if s.end_ms + PENDING_KEEP_MS >= now and not s.is_of(starter_pid, since_ms)]
        return [*kept, entry][-PENDING_MAX:]

    _rewrite_pending(ctx, add)


def close_start(ctx: OpContext, *, starter_pid: int, since_ms: int, until_ms: int) -> None:
    """The hc of the pack's start that ran pid ``starter_pid`` at
    ``since_ms`` ended at ``until_ms``: nothing it asked for is newer. Every
    other entry is left alone. Raises one of :data:`PENDING_ERRORS`."""

    def close(starts: Tuple[PendingStart, ...]) -> Sequence[PendingStart]:
        return [replace(s, until_ms=until_ms) if s.is_of(starter_pid, since_ms) and s.until_ms is None else s for s in starts]

    _rewrite_pending(ctx, close)


def finish_start(ctx: OpContext, *, starter_pid: int, since_ms: int) -> None:
    """The pack's start that ran pid ``starter_pid`` at ``since_ms`` is over
    (it finished with the core answering, or a record names its core): its
    entry goes, and every other stays. Raises one of :data:`PENDING_ERRORS`."""
    _rewrite_pending(ctx, lambda starts: [s for s in starts if not s.is_of(starter_pid, since_ms)])


def wall_ms() -> int:
    """Now on the wall clock hc stamps a launchd start with."""
    return time.time_ns() // 1_000_000


def _matches(ctx: OpContext, identity: CoreIdentity, pid: int) -> bool:
    if identity.pid != pid:
        return False
    proc = live(ctx, pid)
    return proc is not None and proc.start == identity.start and ctx.host.procs.boot() == identity.boot


def started_by_pack(ctx: OpContext, status: StatusResult) -> bool:
    """Whether the core behind ``status`` is the one the pack recorded:
    the same pid, process start, boot and core id."""
    identity = read(ctx)
    return identity is not None and identity.core_id == status.core.id and _matches(ctx, identity, status.pid)


def is_recorded(ctx: OpContext, proc: Proc) -> bool:
    """Whether ``proc`` (from a snapshot) is the core process the pack
    recorded, or one a pending start of the pack asked for, for a core that
    does not answer its socket."""
    if proc.opaque:
        return False
    identity = read(ctx)
    if identity is not None and identity.pid == proc.pid and identity.start == proc.start and ctx.host.procs.boot() == identity.boot:
        return True
    start = launchd_start(proc.argv)
    return start is not None and pending_start(ctx, start) is not None


# --- the lineage of a systemd core ------------------------------------------------------


def value_digest(value: str) -> str:
    """What the lineage keeps of a value: its SHA-256, in hex."""
    return hashlib.sha256(value.encode("utf-8", "surrogateescape")).hexdigest()


@dataclass(frozen=True)
class Lineage:
    """What every holder of the systemd core a start of the pack accepted
    carries: a digest of each value, by name."""

    digests: Mapping[str, str]

    @classmethod
    def of(cls, env: Mapping[str, str]) -> Lineage:
        return cls(digests={key: value_digest(value) for key, value in env.items()})

    def carries(self, key: str, value: str) -> bool:
        """Whether ``key`` with ``value`` is what those holders carry."""
        return self.digests.get(key) == value_digest(value)


def read_lineage(ctx: OpContext) -> Optional[Lineage]:
    """The recorded lineage; None when there is none or it is not to be trusted."""
    doc = _read_doc(ctx, LINEAGE_FILE, limit=_LINEAGE_READ_LIMIT)
    if doc is None:
        return None
    try:
        return Lineage(digests=doc.str_map("digests", required=True))
    except (JsonShapeError, ValueError):
        return None


def write_lineage(ctx: OpContext, lineage: Lineage) -> None:
    """Record ``lineage`` in place of the last one, unless that is the same
    (raises StateDirError or OSError)."""
    if read_lineage(ctx) == lineage:
        return
    doc = {"digests": dict(sorted(lineage.digests.items()))}
    write_private_file(ctx.state_file(LINEAGE_FILE), (dumps(doc) + "\n").encode("utf-8"))
