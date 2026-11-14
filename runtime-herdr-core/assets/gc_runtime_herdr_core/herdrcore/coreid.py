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

* **The pack's own hc started it.** Once ``hc server start`` (or
  ``restart``) returns, the pack records the core that answers when its
  starter pid is the pid of the hc the pack ran and it asked launchd no
  earlier than the pack ran that hc. The record holds its pid, its process
  start token (with the boot the token counts from) and its ``server.status``
  core id, in :data:`IDENTITY_FILE` (0600 in the pack's 0700 state
  directory, written through a temp file and a rename). A live core that
  matches all of it is the pack's. A core another starter brought up at the
  same time, which the pack's hc found answering, names that starter, and is
  never recorded.
* **A holder of the city restarted it.** Its starter is a live holder of the
  city's socket, run by this user. A holder is spawned directly, with the
  environment its core restored, so it is judged by that environment
  (:func:`.core.foreign_reason`).

Any other launchd core was started by someone else's hc, and is foreign.
Everywhere else a core's environment can be judged, so nothing is recorded
(:mod:`.core`).

A record that is not a private regular file of this user is not read. A
start that records nothing leaves the previous record, which matches only
the process it names.
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from typing import Final, Optional, Sequence

from ..hc.types import StatusResult
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from .config import write_private_file
from .context import OpContext
from .procs import Proc, ProcError

IDENTITY_FILE: Final = "core-identity.json"

LAUNCHD_SENTINEL: Final = "--hc-launchd"
LAUNCHD_DIR_PREFIX: Final = "hc-launchd-"
LAUNCHD_READY: Final = "ready"
SENTINEL_SLOTS: Final = 3
"""The sentinel is argv[1] of hc's own binary; one slot more lets an
interpreted stand-in (a script run by its interpreter) match too."""

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
    (``<hc> --hc-launchd <dir>/ready``); None for any other argv."""
    for index in range(1, min(len(argv), SENTINEL_SLOTS)):
        if argv[index] != LAUNCHD_SENTINEL:
            continue
        if index + 1 >= len(argv):
            return None
        ready = argv[index + 1]
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
    return None


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


def read(ctx: OpContext) -> Optional[CoreIdentity]:
    """The recorded identity; None when there is none, or it is not a private
    regular file of this user, or not one's shape. It creates no state
    (doctor reads it too)."""
    path = os.path.join(ctx.pack_state, IDENTITY_FILE)
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
        doc = JsonObject.of(loads(raw))
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
    recorded, for a core that does not answer its socket."""
    identity = read(ctx)
    return (
        identity is not None
        and identity.pid == proc.pid
        and identity.start == proc.start
        and not proc.opaque
        and ctx.host.procs.boot() == identity.boot
    )
