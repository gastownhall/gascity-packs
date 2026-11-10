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

**With the core not answering its socket**, the city is parked as well (a
core already down at teardown stays down), and its programs may still run under
their holders (:mod:`.corescan`). Each incarnation the pack keeps metadata
for is found by its program's pid and start time and by its instance token,
and its tree is ended; a holder left with no program is ended too, and one
still running a foreign program is left for it. A core process that runs
but does not answer, a process table that cannot be read, a process that
outlives its kill, a holder that runs a process that cannot be read, or one
that still runs a program while an incarnation's metadata names neither its
program nor a token, makes the op exit 1. A core that answers but fails (a
wedged core) is not swept around: its programs may run, and the op exits 1.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Dict, Final, FrozenSet, List, Optional, Set

from ..hc.client import HcClient
from ..hc.errors import HcError, HcUnreachable
from ..hc.types import Terminal
from ..rpp.exitcodes import ExitCode
from ..rpp.ops import OpResult
from ..rpp.statedir import StateDirError
from . import corescan
from .context import OpContext
from .core import park
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

UNREACHABLE_SURVIVORS: Final = "the city's sessions may survive"


def op_server_stop(ctx: OpContext) -> OpResult:
    if ctx.fault:
        return OpResult.fail(f"the backend is unavailable (GC_RPP_FAULT=unavailable): {UNREACHABLE_SURVIVORS}")
    client = ctx.client()
    warnings: List[str] = []
    try:
        problems = _stop_with_core(ctx, client, warnings)
    except HcUnreachable:
        _park(ctx, warnings)  # gc reads right after its stop: no read may start the core again
        problems = sweep_without_core(ctx, session=None, end_holders=True)
    except HcError as err:
        return OpResult.fail(f"the city's core does not answer as it should ({err}): {UNREACHABLE_SURVIVORS}")
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


def _park(ctx: OpContext, warnings: List[str]) -> None:
    try:
        park(ctx)
    except (StateDirError, OSError) as err:
        warnings.append(f"the city is not marked stopped, so the next read may start its core again ({err})")


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


def _program(snapshot: Snapshot, meta: Meta, holder_pids: Set[int]) -> Optional[Proc]:
    """The incarnation's program, found by the pid ``run`` gave: still the
    same process (its start time), or, when that was not read, a program of
    one of the city's holders."""
    if meta.pid <= 0:
        return None
    proc = snapshot.get(meta.pid)
    if proc is None or proc.zombie or proc.opaque:
        return None
    if meta.pid_start:
        return proc if proc.start == meta.pid_start else None
    return proc if proc.ppid in holder_pids else None


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
    start time, by the launcher's spawn file and by instance token, then
    the token scanned for again as ``stop`` does (:func:`.lifecycle.rescan`).
    Infrastructure (city infrastructure and tmux) is fenced as every kill
    fences it (:func:`.lifecycle.fenced`, the programs found the kill's
    own), and so are the city's holders. With ``end_holders``, a holder of the city's core
    left with no program is ended too, one still running a foreign program
    is left for it, and a core process that does not answer is reported.
    Returns what may survive. The metadata stays: a core that starts again
    shows the records, which ``stop`` and ``start`` recycle."""
    pause = ctx.request.cancel.pause if wait is None else wait
    problems: List[str] = []
    try:
        snapshot = ctx.host.procs.snapshot()
    except ProcError as err:
        return [f"cannot read the process table ({err})"]
    metas = _metas(ctx, session, problems)
    holder_pids = {proc.pid for proc in corescan.holders(snapshot, ctx.paths)}
    tokens = frozenset(meta.values.get(INSTANCE_TOKEN_KEY, "") for meta in metas.values()) - {""}
    captured: Dict[int, Proc] = {}
    roots = [proc for proc in (_program(snapshot, meta, holder_pids) for meta in metas.values()) if proc is not None]
    roots += _launching(snapshot, holder_pids, frozenset(metas), every=session is None)
    for root in roots:
        captured.update((p.pid, p) for p in subtree(snapshot, root.pid))
    captured.update((p.pid, p) for p in scan_environ_any(ctx.host.procs, snapshot, INSTANCE_TOKEN_KEY, tokens))

    def keep_of(now: Snapshot) -> Set[int]:
        return fenced(now, roots) | holder_pids

    if captured:
        problems += reap(ctx, snapshot, list(captured.values()), keep_of(snapshot), pause)
    if not problems and tokens:
        problems += rescan(ctx, tokens, keep_of, pause)
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
