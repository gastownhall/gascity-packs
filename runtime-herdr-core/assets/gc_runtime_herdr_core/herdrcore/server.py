"""``server-stop`` (``server-lifecycle``): end the city's core and every
session the pack started for the city with it.

gc runs it after its own stops, as a backstop: a session those stops could
not see ends with the server. Exit 0 means the city's core is gone and no
program of the city's sessions runs; with nothing running it has nothing to
do and exits 0, so a second call exits 0. Exit 1 names what may survive.

**With the core answering**, every record of the city (finished ones too)
is ended as ``stop`` ends it, under its name's lock: the whole process tree,
the incarnation's re-parented processes found by its instance token, city
infrastructure fenced. A record whose metadata cannot be read has its tree
ended, but it stays with its metadata and the op exits 1: its re-parented
processes cannot be looked for. A terminal the city did not start (a
person's, or one an agent opened through the in-agent ``hc``) is foreign:
it survives, and while one runs the core keeps running for it. Otherwise
the city is parked (:mod:`.core`: no read starts its core again until the
next start), the core is stopped (``server.stop``) once nothing of the city
may survive, and the pack waits until it is gone; what its holders still
run is then looked for as below.

**With the core not answering its socket**, hc may still keep the city's
records: it keeps them across a core restart, finished, and one left would
refuse gc's next start of its name (``fresh_only``) while every read of the
parked city answers it absent. So while the pack keeps an incarnation's
metadata (it does until the record is removed), the core is started (the
op holds the kick lock) and the city stopped with it, as above. A core that
cannot be started, or a core of the city listening on another socket
(``core.lock``), makes the op exit 1 with the city unparked, so reads kick
the core back. With no metadata kept, the city is parked as well (a core
already down at teardown stays down). Its programs may still run under
their holders (:mod:`.corescan`), so they are looked for all the same:
each incarnation the pack keeps metadata for is found by its program's pid
and start time (read in this boot), as a holder's program carrying its
instance token, and by that token, and its tree is ended; a holder left
with no program is ended too, and one still running a foreign program is
left for it. A core process that runs but does not answer, a process table
that cannot be read, a process that outlives its kill, a holder that runs
a process that cannot be read, one that still runs a program while an
incarnation's metadata names neither its program nor a token, or an
incarnation's program the fence keeps (a box whose program is a tmux
client), makes the op exit 1. A core that answers but fails (a wedged
core) is not swept around: its programs may run, and the op exits 1.

**Parking.** The whole op holds the kick lock (:mod:`.core`), so a kick
in flight finishes first and none starts the core while the op sweeps. At
its end, whatever its exit, the mark is cleared again when anything of the
core still runs (a holder, a core): a core kept for what runs is not
parked, so reads kick it back to adopt what is left, and gc reads definite
answers again instead of an unknown that never lets it send a start.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Dict, Final, FrozenSet, List, Optional, Set

from ..hc.client import HcClient
from ..hc.errors import HcError, HcUnreachable
from ..hc.types import Terminal
from ..rpp.cancel import Cancelled
from ..rpp.exitcodes import ExitCode
from ..rpp.flock import LockFileError, LockTimeout
from ..rpp.ops import OpError, OpResult
from ..rpp.statedir import StateDirError
from . import corescan
from .config import ConfigError
from .context import OpContext
from .core import CORE_START_WAIT_S, KICK_LOCK, check_core_lock, park, start_core, unpark
from .lifecycle import INSTANCE_TOKEN_KEY, fenced, forget, kill_incarnation, reap, rescan
from .metastore import Meta, MetaError
from .naming import LABEL_CITY, LABEL_SESSION, city_label
from .procs import LAUNCHER_NAME, Proc, ProcError, Snapshot, kill_captured, scan_environ_any, subtree
from .reads import meta_store, read_meta
from .records import object_of
from .spawnfile import SUFFIX as SPAWN_SUFFIX

CORE_GONE_WAIT_S: Final = 10.0
"""How long a stopped core may take to close its socket and exit."""
CORE_GONE_POLL_S: Final = 0.1
KICK_WAIT_S: Final = CORE_START_WAIT_S + 1.0
"""How long a kick in flight may take to finish its core start."""

UNREACHABLE_SURVIVORS: Final = "the city's sessions may survive"


def op_server_stop(ctx: OpContext) -> OpResult:
    if ctx.fault:
        return OpResult.fail(f"the backend is unavailable (GC_RPP_FAULT=unavailable): {UNREACHABLE_SURVIVORS}")
    client = ctx.client()
    warnings: List[str] = []
    try:
        # A kick in flight finishes first, and none starts until server-stop
        # is done: a core it started after the last look would outlive the stop.
        with ctx.lock(KICK_LOCK, shared=False, wait_s=max(0.0, ctx.request.deadline.budget(KICK_WAIT_S))):
            try:
                problems = _stop_with_core(ctx, client, warnings)
            except HcUnreachable:
                problems = _stop_core_down(ctx, client, warnings)
            except HcError as err:
                problems = [f"the city's core does not answer as it should ({err})"]
            problems += _unpark_if_running(ctx)
    except (LockTimeout, LockFileError) as err:
        detail = "" if isinstance(err, LockTimeout) else f" ({err})"
        return OpResult.fail(f"a start of the city's core is in flight{detail}: {UNREACHABLE_SURVIVORS}")
    if problems:
        return OpResult.fail("the city's sessions may survive: " + "; ".join(problems))
    return OpResult(ExitCode.OK, b"", "; ".join(warnings))


def _is_city(ctx: OpContext, terminal: Terminal) -> bool:
    return terminal.labels.get(LABEL_CITY) == city_label(ctx.paths.city_id)


def _stop_with_core(ctx: OpContext, client: HcClient, warnings: List[str]) -> List[str]:
    """End every record of the city, then park it and stop the core unless a
    foreign terminal still runs. Raises :class:`HcUnreachable` when the core
    does not answer."""
    client.hello()
    records = [t for t in client.list_terminals(include_finished=True).terminals if _is_city(ctx, t)]
    problems: List[str] = []
    for name in sorted({t.labels.get(LABEL_SESSION, "") for t in records}):
        problems += _end_session(ctx, client, name)
    if problems:
        return problems  # the core stays: the records it holds find what is left
    live = client.list_terminals(include_finished=False).terminals
    left = [t for t in live if _is_city(ctx, t)]
    if left:
        return ["still listed: " + ", ".join(t.address for t in left[:8])]
    if live:
        return []  # foreign terminals run on it: the core stays for them
    _park(ctx, warnings)  # before the stop: no read in between kicks a start
    client.server_stop()
    problems = _await_core_gone(ctx)
    if problems:
        return problems
    return sweep_without_core(ctx, session=None, end_holders=True)


def _stop_core_down(ctx: OpContext, client: HcClient, warnings: List[str]) -> List[str]:
    """The core does not answer its socket. hc keeps its records across a
    core restart, finished, and one left behind would refuse gc's next start
    of its name (``fresh_only``) while every read of the parked city answers
    it absent. So while the pack keeps an incarnation's metadata, which it
    does as long as hc may keep its record, the core is started (the op
    holds the kick lock, so no kick races it) and the city stopped with it,
    which removes them. A core of the city listening on another socket, or
    one that cannot be started, is reported and leaves the city unparked
    (one parked before too: its empty answer would hide what hc keeps), so
    reads kick the core back; its programs are swept for all the same."""
    try:
        check_core_lock(ctx)  # a core of the city elsewhere may run its programs: never a second one
    except (OpError, StateDirError) as err:
        return [str(err)] + sweep_without_core(ctx, session=None, end_holders=True)
    if _may_hold_records(ctx):
        try:
            start_core(ctx, ctx.hc_binary())
            return _stop_with_core(ctx, client, warnings)
        except (ConfigError, OpError, StateDirError, OSError, HcError) as err:
            if isinstance(err, Cancelled):
                raise
            failed = f"hc may keep the city's records, and its core cannot be started to remove them ({err})"
            return [failed] + _unpark(ctx) + sweep_without_core(ctx, session=None, end_holders=True)
    _park(ctx, warnings)  # gc reads right after its stop: no read may start the core again
    return sweep_without_core(ctx, session=None, end_holders=True)


def _may_hold_records(ctx: OpContext) -> bool:
    """Whether hc may keep a record of the city: the pack keeps metadata of
    an incarnation from before its record is created until ``stop`` or
    ``server-stop`` removes it (or cannot tell)."""
    try:
        return bool(meta_store(ctx).objects())
    except (OSError, StateDirError):
        return True


def _park(ctx: OpContext, warnings: List[str]) -> None:
    try:
        park(ctx)
    except (StateDirError, OSError) as err:
        warnings.append(f"the city is not marked stopped, so the next read may start its core again ({err})")


def _unpark_if_running(ctx: OpContext) -> List[str]:
    """Clear the mark when anything of the core still runs (a holder, a
    core): what it runs keeps the city's business open, and gc, reading
    unknown while it runs, would never send the start that unparks. A core
    kept for what runs is not parked; reads kick it back to adopt it."""
    if corescan.nothing_runs(ctx):
        return []
    return _unpark(ctx)


def _unpark(ctx: OpContext) -> List[str]:
    try:
        unpark(ctx)
    except OpError as err:
        return [err.message]
    return []


def _end_session(ctx: OpContext, client: HcClient, name: str) -> List[str]:
    """End every record of ``name`` under its lock, as ``stop`` does; every
    other live terminal's tree is protected."""
    with ctx.name_lock(name, shared=False):
        labels = {LABEL_CITY: city_label(ctx.paths.city_id), LABEL_SESSION: name}
        records = list(client.list_terminals(labels=labels, include_finished=True).terminals)
        protected = list(client.list_terminals(include_finished=False).terminals)
        problems: List[str] = []
        for record in records:
            meta, readable = read_meta(ctx, record)
            survived = kill_incarnation(ctx, client, record, meta, protected=protected, remove=readable)
            if not readable:
                # Its re-parented processes cannot be looked for: the record
                # and its metadata stay for a retry.
                survived.append("its metadata cannot be read, so its re-parented processes cannot be looked for")
            if survived:
                problems.append(f"{name!r}: " + "; ".join(survived))
                continue
            forget(ctx, object_of(record))
        return problems


def _await_core_gone(ctx: OpContext) -> List[str]:
    """Wait until the stopped core neither answers nor runs."""
    end = time.monotonic() + max(0.0, ctx.request.deadline.budget(CORE_GONE_WAIT_S))
    probe = ctx.client(probe=True)
    while True:
        try:
            probe.hello()
            answering = True
        except HcUnreachable:
            answering = False
        except HcError:
            answering = True
        running: List[Proc] = []
        if not answering:
            try:
                running = corescan.core_processes(ctx, ctx.host.procs.snapshot())
            except ProcError as err:
                return [f"cannot read the process table ({err})"]
            if not running:
                return []
        if time.monotonic() >= end:
            what = "still answers" if answering else "still runs: " + ", ".join(str(p.pid) for p in running[:4])
            return [f"the city's core was stopped but {what}"]
        ctx.request.cancel.pause(CORE_GONE_POLL_S)


# --- without the core ------------------------------------------------------------------------------


def _metas(ctx: OpContext, session: Optional[str], problems: List[str]) -> Dict[str, Meta]:
    """The incarnations the pack keeps metadata for (``session``'s only, when given)."""
    store = meta_store(ctx)
    found: Dict[str, Meta] = {}
    try:
        objects = store.objects()
    except OSError as err:
        problems.append(f"cannot list the sessions' metadata ({err.strerror})")
        return found
    for obj in sorted(objects):
        try:
            meta = store.read(obj)
        except MetaError as err:
            problems.append(f"cannot read an incarnation's metadata ({err})")
            continue
        if meta is not None and (session is None or meta.session == session):
            found[obj] = meta
    return found


def _program(snapshot: Snapshot, meta: Meta, holder_pids: Set[int], boot: Optional[str]) -> Optional[Proc]:
    """The incarnation's program, found by the pid ``run`` gave: still the
    same process (its start time, read in this boot), or, when that cannot
    be told, a program of one of the city's holders. A start time read in
    another boot names nothing that still runs: no process outlives a
    reboot, and the same tick count may name another."""
    if meta.pid <= 0:
        return None
    proc = snapshot.get(meta.pid)
    if proc is None or proc.zombie or proc.opaque:
        return None
    if meta.pid_start and meta.boot == boot:
        return proc if proc.start == meta.pid_start else None
    if meta.pid_start and meta.boot and boot:
        return None
    return proc if proc.ppid in holder_pids else None


def _programs(
    ctx: OpContext, snapshot: Snapshot, metas: Dict[str, Meta], holder_pids: Set[int], carriers: List[Proc]
) -> List[Proc]:
    """The incarnations' programs: each found by its pid (:func:`_program`),
    and each carrier of an instance token that a city holder runs (a
    holder's child is a terminal's program, its pid kept or not). Every one
    is a root of the kill, so a tmux server above it fences none of its
    tree, and one the fence keeps is reported."""
    boot = ctx.host.procs.boot()
    found: Dict[int, Proc] = {}
    for meta in metas.values():
        proc = _program(snapshot, meta, holder_pids, boot)
        if proc is not None:
            found[proc.pid] = proc
    for proc in carriers:
        if proc.ppid in holder_pids:
            found.setdefault(proc.pid, proc)
    return list(found.values())


def _launching(snapshot: Snapshot, holder_pids: Set[int], objects: FrozenSet[str], every: bool) -> List[Proc]:
    """Programs of the city's holders still in the pack's launcher, whose
    spawn file names one of ``objects`` (any, when ``every``)."""
    found: List[Proc] = []
    for proc in snapshot.values():
        if proc.ppid not in holder_pids or proc.opaque:
            continue
        if not any(os.path.basename(arg) == LAUNCHER_NAME for arg in proc.argv[:4]):
            continue
        spawn = os.path.basename(proc.argv[-1]) if proc.argv else ""
        obj = spawn[: -len(SPAWN_SUFFIX)] if spawn.endswith(SPAWN_SUFFIX) else ""
        if every or obj in objects:
            found.append(proc)
    return found


def sweep_without_core(
    ctx: OpContext,
    *,
    session: Optional[str],
    end_holders: bool,
    wait: Optional[Callable[[float], None]] = None,
) -> List[str]:
    """End, without the core, the programs of every incarnation the pack
    keeps metadata for (``session``'s only, when given): found by pid and
    start time, as a city holder's program carrying an instance token, by
    the launcher's spawn file and by instance token, then the token scanned
    for again as ``stop`` does (:func:`.lifecycle.rescan`).
    Infrastructure (city infrastructure and tmux) is fenced as every kill
    fences it (:func:`.lifecycle.fenced`, the programs found the kill's
    own), and so are the city's holders. With ``end_holders``, a holder of the city's core
    left with no program is ended too, one still running a foreign program
    is left for it, and a core process that does not answer is reported.
    Returns what may survive. The metadata stays, as hc may keep the
    records: ``stop`` removes them once a core answers again, and a
    core-down ``server-stop`` starts the core to (:func:`_stop_core_down`)."""
    pause = ctx.request.cancel.pause if wait is None else wait
    problems: List[str] = []
    try:
        snapshot = ctx.host.procs.snapshot()
    except ProcError as err:
        return [f"cannot read the process table ({err})"]
    metas = _metas(ctx, session, problems)
    holder_pids = {proc.pid for proc in corescan.holders(snapshot, ctx.paths)}
    tokens = frozenset(meta.values.get(INSTANCE_TOKEN_KEY, "") for meta in metas.values()) - {""}
    carriers = scan_environ_any(ctx.host.procs, snapshot, INSTANCE_TOKEN_KEY, tokens)
    programs = _programs(ctx, snapshot, metas, holder_pids, carriers)
    roots = programs + _launching(snapshot, holder_pids, frozenset(metas), every=session is None)
    captured: Dict[int, Proc] = {}
    for root in roots:
        captured.update((p.pid, p) for p in subtree(snapshot, root.pid))
    captured.update((p.pid, p) for p in carriers)

    def keep_of(now: Snapshot) -> Set[int]:
        return fenced(now, roots) | holder_pids

    keep = keep_of(snapshot)
    if captured:
        problems += reap(ctx, snapshot, list(captured.values()), keep, pause)
    if not problems and tokens:
        problems += rescan(ctx, tokens, keep_of, pause)
    kept = [proc for proc in programs if proc.pid in keep]
    if kept:
        # Known by pid and start time, yet fenced (a box whose program is a
        # tmux client): only the core can end it.
        problems.append("an incarnation's program is infrastructure, so never signalled: " + ", ".join(str(p.pid) for p in kept[:8]))
    if end_holders:
        blind = any(meta.pid <= 0 and not meta.values.get(INSTANCE_TOKEN_KEY, "") for meta in metas.values())
        problems += _end_holders(ctx, pause, blind=blind)
    return problems


def _end_holders(ctx: OpContext, pause: Callable[[float], None], *, blind: bool) -> List[str]:
    """End every holder of the city's core that runs no program any more; one
    that still does runs a foreign one (the city's were killed before) and is
    left for it, unless what it runs cannot be read, or an incarnation
    (``blind``) names neither its program nor a token: then the city's may
    survive under it. Report the core when it runs without answering.
    Returns what may survive."""
    try:
        snapshot = ctx.host.procs.snapshot()
    except ProcError as err:
        return [f"cannot read the process table ({err})"]
    problems: List[str] = []
    idle: List[Proc] = []
    unreadable: List[Proc] = []
    busy: List[Proc] = []
    for holder in corescan.holders(snapshot, ctx.paths):
        running = [p for p in subtree(snapshot, holder.pid)[1:] if not p.zombie]
        if not running:
            idle.append(holder)
        elif any(p.opaque for p in running):
            unreadable.append(holder)
        else:
            busy.append(holder)
    if unreadable:
        problems.append(
            "a holder of the city's core runs a process that cannot be read: " + ", ".join(str(p.pid) for p in unreadable[:8])
        )
    if blind and busy:
        problems.append(
            "an incarnation's metadata names neither its program nor its instance marker, and a holder of the city's core "
            "still runs a program: " + ", ".join(str(p.pid) for p in busy[:8])
        )
    survivors = kill_captured(ctx.host.procs, idle, pause=pause)
    if survivors:
        problems.append("a holder of the city's core still runs: " + ", ".join(str(p.pid) for p in survivors[:8]))
    cores = corescan.core_processes(ctx, snapshot)
    if cores:
        problems.append("the city's core runs but does not answer: " + ", ".join(str(p.pid) for p in cores[:4]))
    return problems
