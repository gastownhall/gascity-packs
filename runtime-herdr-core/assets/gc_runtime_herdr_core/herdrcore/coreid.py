"""The identity of the core the pack started.

The pack judges a running core by the environment it was started with
(:func:`.core.foreign_reason`), but on some hosts a core's process
environment does not show it. On macOS hc starts the core as a launchd job,
which runs with launchd's default environment, and restores the starter's
environment only inside the process (hc ``platform/macos_launchd.rs``), so
``ps -E`` shows none of the discovery tuple. Under systemd older than 244 a
unit gets no ``RUNTIME_DIRECTORY``, so the environment file hc wrote for it
cannot be found from the process, and its live environment is the user
manager's.

So once ``hc server start`` returns, the pack records which core answered:
its pid, its process start token (with the boot the token counts from) and
its ``server.status`` core id, in :data:`IDENTITY_FILE` (0600 in the pack's
0700 state directory, written through a temp file and a rename). A live
core that matches all of it is the pack's own; any other core is judged by
its environment. A recycled pid has another start token, and a core of
another state another core id, so neither matches.

Only a core that started after the pack ran ``hc server start`` is
recorded: a core someone else started first, which ``hc server start``
found answering, is never taken for the pack's. A start that records
nothing leaves the previous record, which matches only the process it
names. A record that is not a private
regular file of this user is not read.
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from typing import Final, Optional

from ..hc.types import StatusResult
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from .config import write_private_file
from .context import OpContext
from .procs import Proc, ProcError

IDENTITY_FILE: Final = "core-identity.json"

START_SLACK_MS: Final = 2000
"""How far before ``hc server start`` ran a recorded core's start may read:
``ps`` gives start times to the second, ``/proc`` to the boot second plus
clock ticks."""

_READ_LIMIT: Final = 4096


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


def _live(ctx: OpContext, pid: int) -> Optional[Proc]:
    """``pid`` as it runs now, with a start token; None when that cannot be told."""
    try:
        proc = ctx.host.procs.process(pid)
    except ProcError:
        return None
    if proc is None or proc.opaque or proc.zombie or not proc.start:
        return None
    return proc


def record(ctx: OpContext, status: StatusResult, *, since_ms: int) -> bool:
    """Record the core behind ``status`` as the one the pack started, when
    its process started no earlier than ``since_ms`` (wall clock, taken
    before ``hc server start`` ran). Returns whether it was recorded; a core
    that cannot be told is not, and is then judged by its environment."""
    proc = _live(ctx, status.pid)
    boot = ctx.host.procs.boot()
    if proc is None or boot is None:
        return False
    started = ctx.host.procs.started_ms(proc)
    if started is None or started < since_ms - START_SLACK_MS:
        return False
    try:
        write(ctx, CoreIdentity(pid=status.pid, start=proc.start, boot=boot, core_id=status.core.id))
    except (OSError, StateDirError):
        return False
    return True


def wall_ms() -> int:
    """Now on the wall clock that process start times are read in."""
    return int(time.time() * 1000)


def _matches(ctx: OpContext, identity: CoreIdentity, pid: int) -> bool:
    if identity.pid != pid:
        return False
    proc = _live(ctx, pid)
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
