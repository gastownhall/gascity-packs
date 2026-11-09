"""Whether anyone watches a box, and the ``attach`` op.

hc counts no viewers (no field anywhere in its API), so attachment is read
from the host, in one process snapshot. A box is attached when either:

1. the pack's own ``attach`` for the incarnation runs: it holds the
   incarnation's attach lock for its whole life (an inherited descriptor),
   so a lock that cannot be taken is a viewer; or
2. one of this user's processes runs ``herdr-core attach`` or ``hc attach``
   on the box's terminal (by address or name) against this city's core: its
   environment names this core's socket or session.

The city's core is private (a session no person's ``hc`` uses by default),
so these are its only viewers short of a client that bypasses the CLI.
When the snapshot cannot be read the answer is "cannot tell" (exit 1 from
``is-attached``), which gc reads as attached.
"""

from __future__ import annotations

import fcntl
import os
from typing import FrozenSet, Optional, Set, Tuple

from ..hc.types import Terminal
from ..rpp.flock import LockFileError
from ..rpp.ops import OpError, OpResult
from .config import ConfigError
from .context import OpContext
from .procs import ProcError, Snapshot
from .records import object_of

ATTACH_COMMANDS = frozenset({"herdr-core", "hc"})


def lock_held(path: str) -> bool:
    """Whether another process holds ``path``'s lock."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    except OSError as err:
        raise LockFileError(f"cannot open {path}: {err.strerror}") from None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def _attach_target(argv: Tuple[str, ...]) -> Optional[str]:
    if len(argv) < 3 or os.path.basename(argv[0]) not in ATTACH_COMMANDS or argv[1] != "attach":
        return None
    for arg in argv[2:]:
        if not arg.startswith("-"):
            return arg
    return None


def viewer_targets(ctx: OpContext, snapshot: Snapshot) -> FrozenSet[str]:
    """The terminals this user's ``hc attach`` processes watch on this city's core."""
    uid = os.getuid()
    targets: Set[str] = set()
    for proc in snapshot.values():
        if proc.uid != uid:
            continue
        target = _attach_target(proc.argv)
        if target is None:
            continue
        env = ctx.host.procs.environ(proc.pid)
        if env is None:
            continue
        if env.get("HC_SOCKET") == ctx.paths.socket or env.get("HC_SESSION") == ctx.paths.session:
            targets.add(target)
    return frozenset(targets)


def attached(ctx: OpContext, record: Terminal, viewers: FrozenSet[str], obj: Optional[str]) -> bool:
    """Whether ``record`` has a viewer, given this snapshot's ``viewers``."""
    if obj is not None and lock_held(ctx.attach_lock_path(obj)):
        return True
    return record.address in viewers or (record.name is not None and record.name in viewers)


def snapshot_viewers(ctx: OpContext) -> FrozenSet[str]:
    """One snapshot's viewers; :class:`ProcError` when it cannot be read."""
    return viewer_targets(ctx, ctx.host.procs.snapshot())




def op_attach(ctx: OpContext) -> OpResult:
    """Exec ``herdr-core attach`` on the box, holding its attach lock."""
    from .reads import live_record, session_arg  # reads uses this module's rule

    name = session_arg(ctx.request)
    record = live_record(ctx, name)
    if record is None:
        raise OpError(f"no running session {name!r}")
    obj = object_of(record)
    try:
        hc_bin = ctx.hc_binary()
    except ConfigError as err:
        raise OpError(str(err)) from None
    env = {k: v for k, v in ctx.env.items() if k != "HC_SCOPE"}
    env.update(ctx.paths.discovery_env())
    if obj is not None:
        fd = os.open(ctx.attach_lock_path(obj), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fcntl.flock(fd, fcntl.LOCK_SH)
        os.set_inheritable(fd, True)
    os.execve(hc_bin, [hc_bin, "attach", record.address], env)
    raise OpError("exec of hc attach returned")


