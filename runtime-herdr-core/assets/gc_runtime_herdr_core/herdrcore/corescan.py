"""The city's core and holders in the process table, for when the core does
not answer its socket.

hc runs every terminal's program under a *holder*, a process its core
spawns as ``<hc> hold --socket <holder socket>``, where the holder socket is
``<session>.holder.<8 hex>.sock`` beside the core's socket (herdr-core
``crates/herdr-core/src/runtime.rs`` ``start_holder``, ``paths.rs``). Holders
outlive their core: a core that starts again adopts them. So a core that
does not answer says nothing about whether the city's programs run, but a
process table holding no holder of the city's socket does: then no program
of the city's core runs.

The core itself is ``<hc> serve``, started with the pack's discovery tuple
(:mod:`.core`), so its environment names the city's socket. A core of the
city's session may listen on another socket (``core.lock`` names it,
herdr-core #200); its holders are then beside that one, so while it
answers, what runs cannot be told from the city's socket.

A process of this user that cannot be read is not taken for a holder or a
core: hc's are ordinary processes of the user, whose command lines read.
"""

from __future__ import annotations

import os
import socket
from typing import Final, List, Optional, Sequence

from ..hc.paths import HcPaths
from ..rpp.statedir import StateDirError
from .config import read_private_file
from .context import OpContext
from .procs import Proc, ProcError, Snapshot

HOLD_VERB: Final = "hold"
SERVE_VERB: Final = "serve"
SOCKET_FLAG: Final = "--socket"
SOCKET_SUFFIX: Final = ".sock"
VERB_SLOTS: Final = 3
"""The verb is argv[1] of hc's own binary; one slot more lets an interpreted
stand-in (a script run by its interpreter) match too."""


def holder_prefix(paths: HcPaths) -> str:
    """What every holder socket of the city's core starts with: hc puts
    ``<socket minus .sock>.holder.<id>.sock`` beside an ``HC_SOCKET``."""
    base = paths.socket[: -len(SOCKET_SUFFIX)] if paths.socket.endswith(SOCKET_SUFFIX) else paths.socket
    return base + ".holder."


def _verb_at(argv: Sequence[str], verb: str) -> Optional[int]:
    for index in range(1, min(len(argv), VERB_SLOTS)):
        if argv[index] == verb:
            return index
    return None


def is_holder_of(proc: Proc, prefix: str) -> bool:
    """Whether ``proc`` is a holder whose socket starts with ``prefix``."""
    if proc.opaque or proc.zombie:
        return False
    at = _verb_at(proc.argv, HOLD_VERB)
    if at is None:
        return False
    rest = proc.argv[at + 1 :]
    for index, arg in enumerate(rest[:-1]):
        if arg == SOCKET_FLAG:
            socket = rest[index + 1]
            return socket.startswith(prefix) and socket.endswith(SOCKET_SUFFIX)
    return False


def holders(snapshot: Snapshot, paths: HcPaths) -> List[Proc]:
    """The holders of the city's core that run now (this user's)."""
    prefix = holder_prefix(paths)
    uid = os.getuid()
    return [proc for proc in snapshot.values() if proc.uid == uid and is_holder_of(proc, prefix)]


def core_processes(ctx: OpContext, snapshot: Snapshot) -> List[Proc]:
    """The city's core processes that run now: ``serve`` with the city's
    socket in their environment. One whose environment cannot be read is
    left out."""
    uid = os.getuid()
    candidates = [
        proc
        for proc in snapshot.values()
        if proc.uid == uid
        and proc.pid != os.getpid()
        and not proc.opaque
        and not proc.zombie
        and _verb_at(proc.argv, SERVE_VERB) is not None
    ]
    envs = ctx.host.procs.environs(proc.pid for proc in candidates)
    return [proc for proc in candidates if envs.get(proc.pid, {}).get("HC_SOCKET") == ctx.paths.socket]


LOCK_PROBE_S: Final = 0.5


def listener_elsewhere(ctx: OpContext) -> Optional[str]:
    """The socket a core of the city's session listens on when ``core.lock``
    names one other than the city's and something answers there; None when
    the lock names the city's socket, none or a stale one. Raises
    StateDirError when the lock cannot be read."""
    raw = read_private_file(ctx.paths.core_lock)
    if not raw:
        return None
    listening = os.fsdecode(raw.strip())
    if listening == ctx.paths.socket:
        return None
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        probe.settimeout(LOCK_PROBE_S)
        probe.connect(listening)
    except OSError:
        return None  # a stale lock: nobody listens there
    finally:
        probe.close()
    return listening


def nothing_runs(ctx: OpContext) -> bool:
    """Whether no program of the city's core can run: no core of the city's
    session listens elsewhere, and the process table reads and holds neither
    a holder of its socket nor its core (one that does not answer may still
    run what it started). Asked only once the core did not answer; False
    when it cannot be told."""
    if ctx.backend_unavailable:
        return False
    try:
        if listener_elsewhere(ctx) is not None:
            return False
    except StateDirError:
        return False
    try:
        snapshot = ctx.host.procs.snapshot()
    except ProcError:
        return False
    return not holders(snapshot, ctx.paths) and not core_processes(ctx, snapshot)
