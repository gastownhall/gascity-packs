"""Who started a core hc placed under launchd (macOS), whose environment
cannot be read.

On macOS hc starts the core as a one-shot launchd job (hc
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
  runs for ``hc server start`` (or ``restart``), it writes that hc's pid and
  the wall-clock time it ran it to :data:`PENDING_FILE`, and once the hc
  ends, the time it ended. A launchd core whose starter pid is that pid and
  that was asked for within that time is the pack's: until the hc is reaped
  its pid is no one else's, and after it ended nothing it asked for is
  newer. So a start that checks while another start of the pack still runs,
  or a start after one whose hc timed out (hc asked launchd, the core came
  up late), accepts it. On that first acceptance, or once ``hc server
  start`` returns and the core answers, the pack records the core: its pid,
  its process start token (with the boot the token counts from) and its
  ``server.status`` core id, in :data:`IDENTITY_FILE`. A live core that
  matches all of it is the pack's. The pending start is dropped once that
  record supersedes it, once a later start of the pack replaces it, or
  once its start finished with the core answering. A core another starter
  brought up at the same time, which the pack's hc found answering, names
  that starter, and is never accepted.
* **A holder of the city restarted it.** Its starter is a live holder of the
  city's socket, run by this user. A holder is spawned directly, with the
  environment its core restored, so it is judged by that environment
  (:func:`.core.foreign_reason`).

Any other launchd core was started by someone else's hc, and is foreign.
Everywhere else a core's environment can be judged, so nothing is recorded
(:mod:`.core`).

Both files are 0600 in the pack's 0700 state directory, written through a
temp file and a rename; one that is not a private regular file of this user
is not read. A start that records nothing leaves the previous record, which
matches only the process it names.
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from typing import Final, Optional, Sequence

from ..hc.types import StatusResult
from ..rpp.flock import LockTimeout
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from .config import write_private_file
from .context import OpContext
from .procs import Proc, ProcError

IDENTITY_FILE: Final = "core-identity.json"
PENDING_FILE: Final = "core-start.json"
PENDING_LOCK: Final = "core-start"
"""Held while the pending start is read and replaced."""
PENDING_LOCK_WAIT_S: Final = 5.0

LAUNCHD_SENTINEL: Final = "--hc-launchd"
LAUNCHD_DIR_PREFIX: Final = "hc-launchd-"
LAUNCHD_READY: Final = "ready"
_READ_LIMIT: Final = 4096
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


def _read_doc(ctx: OpContext, name: str) -> Optional[JsonObject]:
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
        raw = handle.read(_READ_LIMIT)
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
    boot = ctx.host.procs.boot()
    if proc is None or boot is None:
        return False
    start = launchd_start(proc.argv)
    if start is None or start.starter_pid != starter_pid or start.asked_ns < since_ms * 1_000_000:
        return False
    try:
        write(ctx, CoreIdentity(pid=status.pid, start=proc.start, boot=boot, core_id=status.core.id))
    except (OSError, StateDirError):
        return False
    return True


@dataclass(frozen=True)
class PendingStart:
    """The hc the pack runs (or ran) to start the core."""

    starter_pid: int
    since_ms: int
    """Wall clock before the pack ran it."""
    until_ms: Optional[int]
    """Wall clock once it ended; None while it runs."""

    def asked(self, start: LaunchdStart) -> bool:
        """Whether this hc asked launchd for the core ``start`` names."""
        if start.starter_pid != self.starter_pid or start.asked_ns < self.since_ms * 1_000_000:
            return False
        return self.until_ms is None or start.asked_ns // 1_000_000 <= self.until_ms


def read_pending(ctx: OpContext) -> Optional[PendingStart]:
    """The pending start; None when there is none or it is not to be trusted."""
    doc = _read_doc(ctx, PENDING_FILE)
    if doc is None:
        return None
    try:
        return PendingStart(
            starter_pid=doc.req_int("starter_pid"), since_ms=doc.req_int("since_ms"), until_ms=doc.opt_int("until_ms")
        )
    except (JsonShapeError, ValueError):
        return None


def _write_pending(ctx: OpContext, pending: PendingStart) -> None:
    doc = {"starter_pid": pending.starter_pid, "since_ms": pending.since_ms, "until_ms": pending.until_ms}
    write_private_file(ctx.state_file(PENDING_FILE), (dumps(doc) + "\n").encode("utf-8"))


def _drop_pending(ctx: OpContext, *, starter_pid: int, since_ms: Optional[int] = None) -> None:
    """Drop the pending start when it is still the one of ``starter_pid``
    (and ``since_ms``); call with :data:`PENDING_LOCK` held."""
    pending = read_pending(ctx)
    if pending is None or pending.starter_pid != starter_pid or (since_ms is not None and pending.since_ms != since_ms):
        return
    try:
        os.unlink(os.path.join(ctx.pack_state, PENDING_FILE))
    except FileNotFoundError:
        return


def begin_start(ctx: OpContext, *, starter_pid: int, since_ms: int) -> None:
    """Name the hc the pack now runs to start the core (pid ``starter_pid``,
    run no earlier than ``since_ms``), replacing any earlier pending start.
    Raises StateDirError, OSError or LockTimeout."""
    with ctx.lock(PENDING_LOCK, shared=False, wait_s=PENDING_LOCK_WAIT_S):
        _write_pending(ctx, PendingStart(starter_pid=starter_pid, since_ms=since_ms, until_ms=None))


def close_start(ctx: OpContext, *, starter_pid: int, until_ms: int) -> None:
    """The hc of the pending start ended at ``until_ms``: nothing it asked
    for is newer. A later start's pending entry is left alone. Raises
    StateDirError, OSError or LockTimeout."""
    with ctx.lock(PENDING_LOCK, shared=False, wait_s=PENDING_LOCK_WAIT_S):
        pending = read_pending(ctx)
        if pending is not None and pending.starter_pid == starter_pid and pending.until_ms is None:
            _write_pending(ctx, PendingStart(starter_pid=starter_pid, since_ms=pending.since_ms, until_ms=until_ms))


def finish_start(ctx: OpContext, *, starter_pid: int) -> None:
    """The start of ``starter_pid`` finished with the core answering: its
    pending entry goes. Raises StateDirError, OSError or LockTimeout."""
    with ctx.lock(PENDING_LOCK, shared=False, wait_s=PENDING_LOCK_WAIT_S):
        _drop_pending(ctx, starter_pid=starter_pid)


def accept_pending(ctx: OpContext, status: StatusResult, start: LaunchdStart) -> bool:
    """Whether the launchd core behind ``status`` (asked for as ``start``
    says) is the one the pack's pending start asked for. On that first
    acceptance it is recorded, and the record supersedes the pending entry;
    a record that cannot be written leaves the entry, which still names it."""
    pending = read_pending(ctx)
    if pending is None or not pending.asked(start):
        return False
    proc = live(ctx, status.pid)
    boot = ctx.host.procs.boot()
    if proc is None or boot is None:
        return True
    try:
        write(ctx, CoreIdentity(pid=status.pid, start=proc.start, boot=boot, core_id=status.core.id))
        with ctx.lock(PENDING_LOCK, shared=False, wait_s=PENDING_LOCK_WAIT_S):
            _drop_pending(ctx, starter_pid=pending.starter_pid, since_ms=pending.since_ms)
    except (OSError, StateDirError, LockTimeout):
        pass  # the pending entry still names it
    return True


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
    recorded, or one its pending start asked for, for a core that does not
    answer its socket."""
    if proc.opaque:
        return False
    identity = read(ctx)
    if identity is not None and identity.pid == proc.pid and identity.start == proc.start and ctx.host.procs.boot() == identity.boot:
        return True
    start = launchd_start(proc.argv)
    pending = read_pending(ctx) if start is not None else None
    return start is not None and pending is not None and pending.asked(start)
