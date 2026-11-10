"""The read ops: observe, inventory, is-running, process-alive, list-running,
is-attached, get-last-activity, peek and the metadata ops.

Every read asks the core afresh (observe.v1 rule 6). A read that finds the
core down answers unknown (``observe``), incomplete (``inventory``) or exit
1, and kicks a start for the next pass. ``observe`` takes the name's lock
shared with a bounded wait, so it answers within gc's 4 s while a start,
stop or a held nudge works on the name. Absence is answered only when the
core, reachable, holds no record of the name, live or finished (rule 7).
``is-running`` and ``process-alive`` answer only whether the name runs: with
the core down and nothing of it running (no holder, no core process), they
answer ``false`` and kick nothing.

A city whose core ``server-stop`` stopped (parked, :mod:`.core`) stays
stopped: no read kicks a start, and with nothing of the core running every
read answers an empty city (``observe`` absent, ``inventory`` complete and
empty, no session running, attached or on screen). That is the truth: the
pack ended and removed every record before it stopped the core, and only a
start, which clears the mark first, creates one.
"""

from __future__ import annotations

from typing import Dict, Final, FrozenSet, List, Optional, Sequence, Tuple

from ..hc.client import HcClient
from ..hc.errors import HcError, HcRpcError, HcUnreachable
from ..hc.types import Terminal
from ..rpp.exitcodes import ExitCode
from ..rpp.flock import LockFileError, LockTimeout
from ..rpp.ops import OpError, OpRequest, OpResult
from ..rpp.statedir import StateDirError
from ..rpp.wire import (
    AgentState,
    InventoryAnswer,
    InventoryEntry,
    ObserveAnswer,
    encode_bool,
    readable_name,
    rfc3339_ms,
)
from . import activity
from .attach import attached, viewer_targets
from .context import Host, OpContext
from .core import kick, parked
from .corescan import nothing_runs
from .metastore import Meta, MetaError, MetaStore
from .naming import LABEL_CITY, LABEL_SESSION, city_label
from .procs import ProcError, Snapshot, expand_names, find_agent, is_launching, opaque_under
from .records import box_object, group_by_session, is_intact, newest, object_of

META_GC_AGE_S: Final = 600.0
"""A metadata file no record carries is removed once it is this old (a
start writes it before its terminal exists)."""


def session_arg(request: OpRequest) -> str:
    if not request.args or not request.args[0]:
        raise OpError("missing session name")
    return request.args[0]


def stdin_names(request: OpRequest) -> List[str]:
    text = request.stdin.decode("utf-8", "surrogateescape")
    return [line.strip() for line in text.splitlines() if line.strip()]


def list_city(client: HcClient, ctx: OpContext, name: Optional[str] = None, *, finished: bool = True) -> List[Terminal]:
    """The city's records (one session's when ``name`` is given)."""
    labels = {LABEL_CITY: city_label(ctx.paths.city_id)}
    if name is not None:
        labels[LABEL_SESSION] = name
    return list(client.list_terminals(labels=labels, include_finished=finished).terminals)


def meta_store(ctx: OpContext) -> MetaStore:
    return MetaStore(ctx.state_dir("meta"))


def read_meta(ctx: OpContext, record: Terminal) -> Tuple[Optional[Meta], bool]:
    """The record's metadata and whether it was readable."""
    obj = object_of(record)
    if obj is None:
        return None, True
    try:
        return meta_store(ctx).read(obj), True
    except (MetaError, StateDirError, OSError):
        return None, False


def unreachable(ctx: OpContext, err: HcError) -> None:
    """A read found the core down or failing: kick a start when it is down
    (never while it is parked)."""
    if isinstance(err, HcUnreachable):
        kick(ctx)


def city_stopped(ctx: OpContext, err: HcError) -> bool:
    """Whether the core does not answer because ``server-stop`` stopped it,
    and nothing of it runs: the city holds no session."""
    return isinstance(err, HcUnreachable) and parked(ctx) and nothing_runs(ctx)


def agent_state(
    snapshot: Optional[Snapshot], record: Terminal, names: Sequence[str], meta: Optional[Meta]
) -> Tuple[Optional[AgentState], Optional[str]]:
    """``alive``/``dead`` with the agent's pid, or (None, None) when it cannot
    be told: while the launcher has not reached the agent, or when no agent is
    found but the box runs a process that cannot be read."""
    if snapshot is None or record.pid is None or not names or is_launching(snapshot, record.pid):
        return None, None
    wanted = expand_names(names, "" if meta is None else meta.gc_bin)
    found = find_agent(snapshot, record.pid, wanted)
    if found is not None:
        return "alive", str(found.pid)
    if opaque_under(snapshot, record.pid):
        return None, None  # the agent may be the process that cannot be read
    return "dead", None


def try_snapshot(host: Host) -> Optional[Snapshot]:
    try:
        return host.procs.snapshot()
    except ProcError:
        return None


# --- observe ------------------------------------------------------------------------------


def op_observe(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    names = stdin_names(ctx.request)
    try:
        with ctx.name_lock(name, shared=True):
            records = list_city(ctx.client(read=True, probe=True), ctx, name)
            record = newest(records, name)
            if record is None:
                return OpResult.answer(ObserveAnswer(state="absent").encode())
            meta, readable = read_meta(ctx, record)
    except (LockTimeout, LockFileError):
        return OpResult.answer(ObserveAnswer(state="unknown").encode())
    except HcError as err:
        if city_stopped(ctx, err):
            return OpResult.answer(ObserveAnswer(state="absent").encode())
        unreachable(ctx, err)
        return OpResult.answer(ObserveAnswer(state="unknown").encode())
    identity = None if not readable else ({} if meta is None else meta.identity())
    if not is_intact(record):
        return OpResult.answer(ObserveAnswer(state="dead", box=box_object(record), identity=identity).encode())
    state, pid = agent_state(try_snapshot(ctx.host) if names else None, record, names, meta)
    if not names and record.pid is not None:
        pid = str(record.pid)  # no names to judge by: the box's program, a host process (fs.host)
    return OpResult.answer(
        ObserveAnswer(state="running", box=box_object(record), agent=state, agent_pid=pid, identity=identity).encode()
    )


# --- inventory -----------------------------------------------------------------------------


def _collect_garbage(ctx: OpContext, live_objects: FrozenSet[str]) -> None:
    store = meta_store(ctx)
    now = ctx.host.now_ms() / 1000.0
    stale = [obj for obj, mtime in store.objects().items() if obj not in live_objects and now - mtime > META_GC_AGE_S]
    for obj in stale:
        store.remove(obj)
    activity.forget(ctx, stale)


SCREEN_READ_RESERVE_S: Final = 2.0
"""inventory stops reading screens once this little of its deadline is left."""


def refresh_screens(ctx: OpContext, client: HcClient, records: Sequence[Terminal]) -> Dict[str, activity.Seen]:
    """Read the screen of every running agent that has never reported OSC 7501
    status (its only activity signal) and update the activity cache, one read
    per such box while the op's deadline allows. Returns the cache without
    the boxes this pass did not read, so they read as active now, never at a
    stale time; their stored entries stay for the next comparison."""
    seen = activity.cached(ctx)
    for record in records:
        obj = object_of(record)
        if obj is None or record.reported or not is_intact(record):
            continue
        seen.pop(obj, None)
        if ctx.request.deadline.remaining() <= SCREEN_READ_RESERVE_S:
            continue
        try:
            screen = client.read_screen(record.address).text
        except HcError:
            continue
        seen[obj] = activity.note_screen(ctx, obj, screen)
    return seen


def op_inventory(ctx: OpContext) -> OpResult:
    client = ctx.client(read=True)
    try:
        records = list_city(client, ctx)
    except HcError as err:
        if city_stopped(ctx, err):
            return OpResult.answer(InventoryAnswer(complete=True, sessions=()).encode())
        unreachable(ctx, err)
        return OpResult.answer(InventoryAnswer(complete=False, sessions=()).encode())
    snapshot = try_snapshot(ctx.host)
    try:
        viewers = None if snapshot is None else viewer_targets(ctx, snapshot)
    except ProcError:
        viewers = None  # attachment cannot be told this pass
    newest_records = [found[0] for found in group_by_session(records).values()]
    seen = refresh_screens(ctx, client, newest_records)
    complete = True
    entries: List[InventoryEntry] = []
    for name, found in sorted(group_by_session(records).items()):
        if readable_name(name):
            entries.append(_inventory_entry(ctx, name, found[0], snapshot, viewers, seen))
        else:
            complete = False
    try:
        _collect_garbage(ctx, frozenset(obj for obj in (object_of(r) for r in records) if obj is not None))
    except (OSError, StateDirError):
        pass  # housekeeping only; the next inventory tries again
    return OpResult.answer(InventoryAnswer(complete=complete, sessions=tuple(entries)).encode())


def _inventory_entry(
    ctx: OpContext,
    name: str,
    record: Terminal,
    snapshot: Optional[Snapshot],
    viewers: Optional[FrozenSet[str]],
    seen: Dict[str, activity.Seen],
) -> InventoryEntry:
    """The inventory entry of ``name``, whose newest record is ``record``."""
    meta, readable = read_meta(ctx, record)
    running = is_intact(record)
    agent: Optional[AgentState] = None
    if running and meta is not None:
        agent, _ = agent_state(snapshot, record, meta.process_names(), meta)
    is_attached: Optional[bool] = None
    if viewers is not None:
        try:
            is_attached = attached(ctx, record, viewers, object_of(record))
        except LockFileError:
            is_attached = None
    last = rfc3339_ms(activity.last_activity_ms(ctx, record, activity.object_seen(record, seen))) if running else None
    return InventoryEntry(
        name=name,
        state="running" if running else "dead",
        box=box_object(record),
        agent=agent,
        attached=is_attached,
        last_activity=last,
        restart_requested=None if not readable else bool(meta is not None and meta.values.get("GC_RESTART_REQUESTED")),
        identity=None if not readable else ({} if meta is None else meta.identity()),
    )


# --- liveness --------------------------------------------------------------------------------


def current_record(ctx: OpContext, name: str, *, liveness: bool = False) -> Optional[Terminal]:
    """The name's newest record, live or finished; exit 1 when the core cannot be read.

    With ``liveness`` (the ops that answer only whether the name runs), a
    core that does not answer while nothing of it runs (no holder of its
    socket, no core process: :func:`.corescan.nothing_runs`) answers no
    record, and kicks no start: nothing of the name runs, and a core started
    for that answer would outlive a stopped city. Every read answers no
    record for a parked city (:func:`city_stopped`)."""
    try:
        return newest(list_city(ctx.client(read=True), ctx, name), name)
    except HcError as err:
        if isinstance(err, HcUnreachable) and (liveness or parked(ctx)) and nothing_runs(ctx):
            return None
        unreachable(ctx, err)
        raise OpError(f"cannot read the city's core: {err}") from None


def live_record(ctx: OpContext, name: str) -> Optional[Terminal]:
    """The name's newest record while its incarnation is intact."""
    record = current_record(ctx, name)
    return record if record is not None and is_intact(record) else None


def op_is_running(ctx: OpContext) -> OpResult:
    record = current_record(ctx, session_arg(ctx.request), liveness=True)
    return OpResult.answer(encode_bool(record is not None and is_intact(record)))


def op_process_alive(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    names = stdin_names(ctx.request)
    record = current_record(ctx, name, liveness=True)
    if record is None or not is_intact(record):
        return OpResult.answer("false")
    if not names:
        return OpResult.answer("true")
    meta, _ = read_meta(ctx, record)
    state, _ = agent_state(try_snapshot(ctx.host), record, names, meta)
    if state is None:
        return OpResult.ok()  # cannot tell: empty, which gc reads as alive, never dead
    return OpResult.answer(encode_bool(state == "alive"))


def op_list_running(ctx: OpContext) -> OpResult:
    prefix = ctx.request.args[0] if ctx.request.args else ""
    try:
        records = list_city(ctx.client(read=True), ctx, finished=False)
    except HcError as err:
        if city_stopped(ctx, err):
            return OpResult.ok()
        unreachable(ctx, err)
        raise OpError(f"cannot read the city's core: {err}") from None
    names = sorted(
        name
        for name, found in group_by_session(records).items()
        if name.startswith(prefix) and is_intact(found[0]) and readable_name(name)
    )
    return OpResult.ok("".join(n + "\n" for n in names).encode("utf-8", "surrogateescape"))


def op_is_attached(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    record = current_record(ctx, name)
    if record is None:
        return OpResult.answer("false")
    try:
        viewers = viewer_targets(ctx, ctx.host.procs.snapshot())
        return OpResult.answer(encode_bool(attached(ctx, record, viewers, object_of(record))))
    except (ProcError, LockFileError) as err:
        raise OpError(f"cannot tell whether {name!r} is attached: {err}") from None


def op_get_last_activity(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    record = current_record(ctx, name)
    if record is None or not is_intact(record):
        return OpResult.ok()
    obj = object_of(record)
    seen: Optional[activity.Seen] = None
    if obj is not None and not record.reported:
        try:
            screen = ctx.client(read=True).read_screen(record.address).text
        except HcError as err:
            raise OpError(f"cannot read the screen: {err}") from None
        seen = activity.note_screen(ctx, obj, screen)
    elif obj is not None:
        seen = activity.cached(ctx).get(obj)
    return OpResult.answer(rfc3339_ms(activity.last_activity_ms(ctx, record, seen)))


# --- peek ------------------------------------------------------------------------------------


def op_peek(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    raw = ctx.request.args[1] if len(ctx.request.args) > 1 else "0"
    try:
        lines = int(raw)
    except ValueError:
        raise OpError(f"peek: lines must be an integer, got {raw!r}") from None
    record = current_record(ctx, name)
    if record is None:
        return OpResult.fail(f"no screen for {name!r}", ExitCode.NO_SCREEN)
    try:
        text = ctx.client(read=True).read_screen(record.address).text
    except HcRpcError as err:
        if err.kind == "not_found":
            return OpResult.fail(f"no screen for {name!r}", ExitCode.NO_SCREEN)
        raise OpError(f"cannot read the screen: {err}") from None
    except HcError as err:
        raise OpError(f"cannot read the screen: {err}") from None
    rows = text.split("\n")
    if lines > 0:
        rows = rows[-lines:]
    return OpResult.ok(("\n".join(rows) + "\n").encode("utf-8", "surrogateescape"))


# --- metadata ----------------------------------------------------------------------------------


def _meta_args(request: OpRequest) -> Tuple[str, str]:
    name = session_arg(request)
    if len(request.args) < 2 or not request.args[1]:
        raise OpError("missing metadata key")
    return name, request.args[1]


def _meta_target(ctx: OpContext, name: str) -> Optional[Tuple[str, Optional[Meta]]]:
    record = current_record(ctx, name)
    if record is None:
        return None
    obj = object_of(record)
    if obj is None:
        raise OpError(f"{name!r} runs in a terminal the pack did not start")
    try:
        return obj, meta_store(ctx).read(obj)
    except MetaError as err:
        raise OpError(str(err)) from None


def op_get_meta(ctx: OpContext) -> OpResult:
    name, key = _meta_args(ctx.request)
    target = _meta_target(ctx, name)
    if target is None or target[1] is None:
        return OpResult.ok()
    return OpResult.ok(target[1].values.get(key, "").encode("utf-8", "surrogateescape"))


def _mutate_meta(ctx: OpContext, name: str, key: str, value: Optional[str]) -> OpResult:
    with ctx.name_lock(name, shared=False):
        target = _meta_target(ctx, name)
        if target is None:
            if value is None:
                return OpResult.ok()
            raise OpError(f"no session {name!r}")
        obj, meta = target
        current = meta if meta is not None else Meta(session=name)
        meta_store(ctx).write(obj, current.with_value(key, value))
    return OpResult.ok()


def op_set_meta(ctx: OpContext) -> OpResult:
    name, key = _meta_args(ctx.request)
    return _mutate_meta(ctx, name, key, ctx.request.stdin.decode("utf-8", "surrogateescape"))


def op_remove_meta(ctx: OpContext) -> OpResult:
    name, key = _meta_args(ctx.request)
    return _mutate_meta(ctx, name, key, None)


__all__ = [
    "op_get_last_activity",
    "op_get_meta",
    "op_inventory",
    "op_is_attached",
    "op_is_running",
    "op_list_running",
    "op_observe",
    "op_peek",
    "op_process_alive",
    "op_remove_meta",
    "op_set_meta",
]
