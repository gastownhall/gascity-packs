"""start, stop and kill-object.

**start** (welded: gc's ``start`` both prepares the box and launches the
agent):

1. Start or check the city's core (:func:`.core.ensure_core`); a core the
   pack did not start is refused.
2. Under the name's lock: a ``fresh_only`` start finding any record exits 73;
   a live intact incarnation is "already exists" (exit 1); every finished
   record and every live broken incarnation of the name is recycled first
   (tree kill, then removed), or gc would read "already exists" every pass
   while the broken record stays. While an earlier incarnation's processes
   may survive that kill, the start exits 1 and launches nothing beside them,
   for up to :data:`START_REFUSAL_LIMIT_MS` from the first refusal, recorded
   in the record's metadata, else in a label of the record (from the
   record's creation when neither takes it, so an older record is then not
   refused at all); then it warns, removes that record and goes ahead beside
   them.
3. Unlocked: stage the start config's files and run ``pre_start`` (fatal).
4. Under the lock again, re-checked: write the incarnation's metadata
   (identity first, observe.v1 rule 5), the shims and a spawn file, then
   ``terminal.run`` the launcher and label the pid. The run is sent once: hc
   may have run a request whose reply was lost, so the start looks that
   terminal up by its ``gc.obj`` (finished too) and never runs the command
   twice. A cancel or failure from here on removes the spawn file, the
   terminal and then the metadata; the metadata stays while the terminal may
   outlive the start, as one without it reads ``identity: {}``. When hc
   cannot read the created record afresh or list the city's boxes, the
   terminal's tree is ended (unless its pid started after the terminal was
   created: a recycled one) but the box stays, its token unscanned, for
   gc's stop. A created terminal hc no longer holds is still looked for by
   its token before its metadata goes.
5. Unlocked: ``session_setup`` and the setup script (warnings only), then the
   first turn. A cancel or failure from here on leaves the box, for gc stops
   the box a failed start leaves. ``session_live`` (tmux theming and
   keybindings) is never run:
   ``start`` warns that it is not applied. The first turn: once the agent is
   ready (its prompt, read as gc reads it, see :mod:`.readiness`; else its
   delay, at most the wait's, as in gc; else its first status report; else
   output that settled), the config's ``nudge`` is sent through the nudge
   path (a send hc got whole is delivered). A wait that runs out without
   readiness types it all the same, as gc's tmux and herdr providers do on
   a probe that timed out (nothing in gc types an exec runtime's first turn
   later). A wait the op's deadline cuts short (it ends
   :data:`FIRST_TURN_RESERVE_S` before it, so with less left there is no
   wait at all) types it too once some screen settled during it, the pack's
   own choice (gc's tmux provider returns before it types, and gc's herdr
   provider skips the turn), and withholds it when none did, as a dialog
   may not be drawn yet. A turn typed without readiness warns. A bare
   "rate limit" mention delays the turn, and withholds it only on a menu
   (see :mod:`.readiness`). gc answers startup dialogs only once ``start`` returns, so a
   screen that shows one is never ready, and one still showing when the
   wait settles or ends withholds the turn (a known limit: nothing types it
   later). A withheld turn or a refusal types nothing, warns, and records
   ``GC_STARTUP_DELIVERY_UNCONFIRMED`` in the metadata.

**stop** and **kill-object** end an incarnation's whole process tree:
descendants are captured, with their start times, before hc's kill (hc ends
the program's process groups, and since 0.1.19 no detached descendant);
infrastructure and its subtree are pruned from the kill set (city
infrastructure, and tmux: see :func:`.procs.fenced_pids`); what is left and
still the same process gets TERM, then KILL. A descendant whose parent
exited is re-parented out of the agent's subtree: a daemon (fork, ``setsid``,
parent exits) while the agent still runs, every child once the agent is
gone. So whatever the record's state, the incarnation's processes are also
found by its ``GC_INSTANCE_TOKEN`` in their environment, and each of them
dies, one the agent meant to outlive it too. That is wider than gc's orphan
sweep, which ends only orphan roots of sessions gc no longer runs (and does
not run for this pack): a shared per-user daemon first started from inside
the box (a Bazel or Gradle server, an ssh ControlMaster, a gpg-agent)
carries the token and dies with it, by design. One started
during the kill (a TERM handler's ``setsid`` child) was in no capture, so
once what was captured is dead the token is looked for again, fenced
afresh, until a scan finds nothing. A process of the tree that cannot be
read (opaque: it has no start time to fence by) is never signalled,
together with everything under it: an infrastructure process that cannot
be read cannot be recognised by its command line, so its children would
lose the infrastructure fence. Nor is one that turns opaque before its
signal, as its pid may have been recycled. When such a process is found,
when a process outlives its KILL, when one still carries the token after
the last of those scans (a daemon that respawns), or when the process
table cannot be read (hc's kill still happens), the op exits 1
("descendants may survive") and the record and its metadata stay: gc's
retry (the next stop or start, or a corpse kill) finds what is left by the
token. A process whose environment does not carry the token, or cannot be
read, is not found that way.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Final, Iterable, List, Mapping, Optional, Set, Tuple, Union

from ..hc.client import HcClient
from ..hc.errors import HcCancelled, HcError, HcProtocolError, HcRpcError
from ..hc.types import RunSpec, Terminal
from ..rpp.cancel import Cancelled
from ..rpp.exitcodes import ExitCode
from ..rpp.flock import LockTimeout
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.ops import OpError, OpResult
from ..rpp.statedir import StateDirError
from ..rpp.wire import KillOutcome, StartConfig, WireError, parse_kill_object_request, parse_start_config
from . import activity, shim, spawnfile
from .attach import attached, viewer_targets
from .command import run_bounded
from .config import read_private_file, write_private_file
from .context import OpContext
from .core import core_env, ensure_core
from .envplan import STRIPPED, scope_env, scope_prefix
from .metastore import Meta, MetaError, seed
from .naming import LABEL_OBJ, LABEL_PID, LABEL_REFUSED, LABEL_SESSION, new_object_nonce, session_labels, terminal_name
from .procs import (
    Proc,
    ProcError,
    Snapshot,
    children_index,
    expand_names,
    fenced_pids,
    find_agent,
    is_launching,
    kill_captured,
    scan_environ,
    subtree,
)
from .readiness import delays_first_turn, shows_ready_prompt, withholds_first_turn
from .reads import agent_state, list_city, meta_store, session_arg, unreachable
from .records import box_object, is_intact, newest, object_of
from .staging import StagingError, stage

INSTANCE_TOKEN_KEY: Final = "GC_INSTANCE_TOKEN"
STARTUP_UNCONFIRMED_KEY: Final = "GC_STARTUP_DELIVERY_UNCONFIRMED"
TERM_ENV: Final = {"TERM": "xterm-256color"}
"""All the environment hc is given for a terminal (it persists it): the
session's travels in the spawn file."""

ONE_SHOT: Final = "one_shot"
SESSION_LIVE_SKIPPED: Final = (
    "session_live is not applied on this runtime: it styles and binds a tmux server, and herdr-core runs no tmux server"
)
"""gc's ``session_live`` is tmux theming, keybindings and status bars. Run on
the host it would reach whatever tmux server it finds (an inherited
``TMUX``, else the user's default one), so it is never run."""
SETUP_TIMEOUT_S: Final = 30.0
LAUNCH_WAIT_S: Final = 5.0
AGENT_WAIT_S: Final = 30.0
READY_WAIT_S: Final = 60.0
READY_POLL_S: Final = 0.25
SETTLE_S: Final = 1.0
IN_DIALOG: Final = "the agent shows a startup dialog, which gc answers once start returns"
NOT_SEEN: Final = "the op's deadline ended the wait before the agent's screen settled"
"""Why a wait the op's deadline cut short withholds the turn when no screen
settled during it: a dialog may not be drawn yet."""
RAN_OUT: Final = "the wait ran out"
CUT_SHORT: Final = "the op's deadline cut the wait short"
FIRST_TURN_RESERVE_S: Final = 5.0
ROLLBACK_S: Final = 1.5
RM_WAIT_S: Final = 3.0
RESCANS: Final = 3
"""How many rounds of killing what still carries the instance token follow
a kill; whatever carries it after the last round (a daemon that respawns
when signalled) may survive."""
START_REFUSAL_LIMIT_MS: Final = 15 * 60 * 1000
"""How long starts are refused while an earlier incarnation's processes may
survive (one unkillable, one respawned from outside the kill, a process
table that cannot be read); a start after that warns and goes ahead."""
REFUSED_SINCE_KEY: Final = "GC_HERDR_CORE_START_REFUSED_SINCE_MS"
FIRST_REFUSAL: Final = "the first refusal"
CREATED: Final = "the earlier incarnation's creation, as no refusal can be recorded for it"
"""What a refused start's limit counts from (:func:`_refused_since`), as its message names it."""
DEFAULT_AGENT_SLICE: Final = "gascity-agents.slice"
USERSCOPE_FILE: Final = "userscope.json"
USERSCOPE_ENV: Final = "GC_HC_TEST_USERSCOPE"
"""Test-only: ``1`` lets a test run probe the user manager (off by default under ``GC_HC_TEST=1``)."""
SYSTEMD_RUN_ENV: Final = "GC_HC_TEST_SYSTEMD_RUN"
"""Test-only: the systemd-run to probe and launch with."""
SCOPE_FAILURE_BACKOFF_MS: Final = 5 * 60 * 1000
ROOT_START_SLACK_MS: Final = 5_000
"""How long after its terminal's creation a box's program may have started
by the process table's clock (the launcher's exec, clock skew); a process
at that pid that started later is another one."""
CORE_START_SLACK_MS: Final = 5_000
"""Two reads of one core's start time differ by at most this; a wider gap
(a suspend, a clock step) only costs one more probe."""


# --- killing an incarnation -------------------------------------------------------------------


def _remove_record(client: HcClient, record: Terminal, pause: Callable[[float], None]) -> None:
    end = time.monotonic() + RM_WAIT_S
    while True:
        try:
            client.remove(record.address)
            return
        except HcRpcError as err:
            if err.kind == "not_found":
                return
            if err.kind != "live" or time.monotonic() >= end:
                raise
        pause(0.1)


def _capture(ctx: OpContext, record: Terminal, token: str, snapshot: Snapshot) -> List[Proc]:
    """The incarnation's processes: the agent's subtree while the record is
    live, and every process that carries the incarnation's instance token.
    A descendant whose parent exited is re-parented out of the subtree, a
    daemon (fork, ``setsid``, parent exits) while the agent still runs as
    much as every child of a finished or broken one: only the token finds
    it, so it is looked for whatever the record's state."""
    captured: Dict[int, Proc] = {}
    if record.pid is not None and record.is_live:
        captured.update((p.pid, p) for p in subtree(snapshot, record.pid))
    if token:
        captured.update((p.pid, p) for p in scan_environ(ctx.host.procs, snapshot, INSTANCE_TOKEN_KEY, token))
    return list(captured.values())


def _hc_kill(client: HcClient, record: Terminal) -> Optional[HcError]:
    """hc's kill of a live record: the error to raise once the tree is dead."""
    if not record.is_live:
        return None
    try:
        client.kill(record.address)
    except HcRpcError as err:
        return None if err.kind in ("not_found", "finished") else err
    except HcError as err:
        return err
    return None


def _own_root(snapshot: Snapshot, record: Terminal) -> Optional[Proc]:
    """The live record's program as ``snapshot`` shows it, if any."""
    return snapshot.get(record.pid) if record.pid is not None and record.is_live else None


def _never_killed(snapshot: Snapshot, record: Terminal, protected: Iterable[Terminal], own: Optional[Proc]) -> Set[int]:
    """Infrastructure (city infrastructure and tmux, each with its whole
    subtree), this process, and every other intact incarnation's tree.
    ``own`` is the record's program as first captured: a tmux server above
    it fences none of its tree while its pid still runs that process (a
    pid reused since, a tmux pane's, is fenced as every pane is)."""
    current = None if own is None else snapshot.get(own.pid)
    same = own is not None and current is not None and bool(own.start) and current.start == own.start
    keep: Set[int] = set(fenced_pids(snapshot, own=own.pid if same and own is not None else None)) | {os.getpid()}
    for other in protected:
        if other.address != record.address and other.pid is not None and is_intact(other):
            keep.update(p.pid for p in subtree(snapshot, other.pid))
    return keep


def _reap(ctx: OpContext, snapshot: Snapshot, captured: List[Proc], keep: Set[int], wait: Callable[[float], None]) -> List[str]:
    """Kill what was captured, less ``keep``; returns what may survive."""
    problems: List[str] = []
    targets, unsure = kill_targets(snapshot, captured, keep=keep)
    if unsure:
        problems.append("under a process that cannot be read, so never signalled: " + ", ".join(str(p.pid) for p in unsure[:8]))
    survivors = kill_captured(ctx.host.procs, targets, pause=wait)
    if survivors:
        problems.append("still running: " + ", ".join(str(p.pid) for p in survivors[:8]))
    return problems


def _rescan(
    ctx: OpContext, record: Terminal, own: Optional[Proc], token: str, protected: List[Terminal], wait: Callable[[float], None]
) -> List[str]:
    """Kill what carries ``token`` now, fenced afresh as the first kill was,
    until a scan finds nothing; returns what may survive, as does a carrier
    still found after :data:`RESCANS` kills."""
    kills = 0
    while True:
        try:
            snapshot = ctx.host.procs.snapshot()
        except ProcError as err:
            return [f"cannot read the process table ({err})"]
        keep = _never_killed(snapshot, record, protected, own)
        found = [p for p in scan_environ(ctx.host.procs, snapshot, INSTANCE_TOKEN_KEY, token) if p.pid not in keep]
        if not found:
            return []
        if kills == RESCANS:
            # No "token" in the text: the redactor takes the word after it for a secret.
            return ["still respawning after the kill: " + ", ".join(str(p.pid) for p in found[:8])]
        kills += 1
        problems = _reap(ctx, snapshot, found, keep, wait)
        if problems:
            return problems


def kill_incarnation(
    ctx: OpContext,
    client: HcClient,
    record: Terminal,
    meta: Optional[Meta],
    *,
    protected: Iterable[Terminal] = (),
    pause: Optional[Callable[[float], None]] = None,
    remover: Optional[Callable[[], HcClient]] = None,
) -> List[str]:
    """End ``record``'s program tree, then remove the record; returns what may
    survive. While anything may, the record stays (and the caller keeps its
    metadata), so the next stop, kill or start finds what is left by the
    instance token. A process the kill itself started (a TERM handler's
    ``setsid`` child) was in no capture: before the record goes, the token
    is scanned for again. ``pause`` waits between checks (default: the op's,
    which a cancel ends); ``remover`` gives the client that removes the
    record once the process work is done (default: ``client``), so a
    rollback's short budget is not spent by the scans before it."""
    wait = ctx.request.cancel.pause if pause is None else pause
    others = list(protected)
    token = "" if meta is None else meta.values.get(INSTANCE_TOKEN_KEY, "")
    problems: List[str] = []
    try:
        snapshot: Optional[Snapshot] = ctx.host.procs.snapshot()
    except ProcError as err:
        snapshot = None
        problems.append(f"cannot read the process table ({err})")
    captured = [] if snapshot is None else _capture(ctx, record, token, snapshot)
    own = None if snapshot is None else _own_root(snapshot, record)
    kill_error = _hc_kill(client, record)
    if snapshot is not None:
        problems += _reap(ctx, snapshot, captured, _never_killed(snapshot, record, others, own), wait)
    if kill_error is not None:
        raise kill_error  # the tree is dead either way; the record stays for the next try
    if not problems and token:
        problems = _rescan(ctx, record, own, token, others, wait)
    if not problems:
        _remove_record(client if remover is None else remover(), record, wait)
    return problems


def kill_targets(snapshot: Snapshot, captured: List[Proc], *, keep: Set[int]) -> Tuple[List[Proc], List[Proc]]:
    """Split ``captured`` (less ``keep``) into what may be signalled and what
    may survive: every opaque process and its whole subtree is never
    signalled, since an unreadable one may be city infrastructure."""
    index = children_index(snapshot)
    shadowed: Set[int] = set()
    for proc in snapshot.values():
        if proc.opaque and proc.pid not in shadowed:
            shadowed.update(p.pid for p in subtree(snapshot, proc.pid, index))
    signal: List[Proc] = []
    unsure: List[Proc] = []
    for proc in captured:
        if proc.pid in keep:
            continue
        (unsure if proc.pid in shadowed else signal).append(proc)
    return signal, unsure


def _forget(ctx: OpContext, obj: Optional[str]) -> None:
    if obj is None:
        return
    try:
        meta_store(ctx).remove(obj)
    except MetaError:
        pass
    activity.forget(ctx, [obj])


def _read_meta(ctx: OpContext, record: Terminal) -> Optional[Meta]:
    obj = object_of(record)
    if obj is None:
        return None
    try:
        return meta_store(ctx).read(obj)
    except MetaError:
        return None


@dataclass
class _Refusals:
    """A start's recycle: what may survive a record the start goes ahead
    beside, and when each record still refused stops being refused (ms),
    with what that is counted from."""

    abandoned: List[str]
    until_ms: List[Tuple[int, str]]


def _recycle(ctx: OpContext, client: HcClient, records: List[Terminal], *, refusals: Optional[_Refusals] = None) -> List[str]:
    """End and remove ``records``; every other live box of the city is
    protected. Returns what may survive: that record stays, and so does its
    metadata. With ``refusals`` (a start's), a record whose processes have
    kept surviving for :data:`START_REFUSAL_LIMIT_MS` is removed all the same,
    and what may survive it is reported there instead."""
    if not records:
        return []
    city = list_city(client, ctx, finished=False)
    problems: List[str] = []
    for record in records:
        meta = _read_meta(ctx, record)
        survived = kill_incarnation(ctx, client, record, meta, protected=city)
        if survived and refusals is not None:
            since, anchor = _refused_since(ctx, client, record, meta)
            until = since + START_REFUSAL_LIMIT_MS
            if ctx.host.now_ms() >= until:
                _remove_record(client, record, ctx.request.cancel.pause)
                refusals.abandoned.extend(survived)
                survived = []
            else:
                refusals.until_ms.append((until, anchor))
        if survived:
            problems += survived
            continue
        _forget(ctx, object_of(record))
    return problems


def _refused_since(ctx: OpContext, client: HcClient, record: Terminal, meta: Optional[Meta]) -> Tuple[int, str]:
    """When starts began to be refused over ``record``'s survivors (ms), and
    what that counts from: the first refusal, recorded in its metadata or,
    when that cannot be written (no metadata, a failed write), in a label of
    the record, which lasts as long as the record does. When neither takes
    it, the record's creation, so no record is refused forever: one older
    than :data:`START_REFUSAL_LIMIT_MS` is then not refused at all."""
    for since in ("" if meta is None else meta.values.get(REFUSED_SINCE_KEY, ""), record.labels.get(LABEL_REFUSED, "")):
        if since.isdigit():
            return int(since), FIRST_REFUSAL
    now = ctx.host.now_ms()
    if _record_refusal(ctx, client, record, meta, str(now)):
        return now, FIRST_REFUSAL
    return record.created_ms, CREATED


def _record_refusal(ctx: OpContext, client: HcClient, record: Terminal, meta: Optional[Meta], now: str) -> bool:
    """Record the first refusal over ``record``: in its metadata, else in its
    ``LABEL_REFUSED`` label; False when neither takes it."""
    obj = object_of(record)
    if obj is not None and meta is not None:
        try:
            meta_store(ctx).write(obj, meta.with_value(REFUSED_SINCE_KEY, now))
            return True
        except (MetaError, OSError):  # a full disk too: never refused forever over it
            pass
    try:
        client.label(record.address, {LABEL_REFUSED: now})
    except HcCancelled:
        raise
    except HcError:
        return False
    return True


def _utc(ms: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))


def _recycle_before_start(ctx: OpContext, client: HcClient, name: str, records: List[Terminal], warnings: List[str]) -> None:
    """Recycle ``records`` for a new incarnation, which never runs beside an
    earlier one's processes, unless they have kept surviving for
    :data:`START_REFUSAL_LIMIT_MS`: the start then warns and goes ahead."""
    refusals = _Refusals(abandoned=[], until_ms=[])
    survived = _recycle(ctx, client, records, refusals=refusals)
    if refusals.abandoned:
        warnings.append(
            f"started {name!r} beside an earlier incarnation's processes, which may still run: " + "; ".join(refusals.abandoned)
        )
    if survived:
        until, anchor = max(refusals.until_ms)
        raise OpError(
            f"cannot start {name!r} while an earlier incarnation's processes may survive: "
            + "; ".join(survived)
            + f" (end them, or from {_utc(until)}, {START_REFUSAL_LIMIT_MS // 60000} minutes after {anchor},"
            + " the start goes ahead beside them)"
        )


# --- stop ---------------------------------------------------------------------------------------


def op_stop(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    client = ctx.client()
    try:
        with ctx.name_lock(name, shared=False):
            records = list_city(client, ctx, name)
            problems = _recycle(ctx, client, records)
    except HcError as err:
        unreachable(ctx, err)
        raise OpError(f"cannot stop {name!r}: {err}") from None
    if problems:
        return OpResult.fail(f"stopped {name!r}, but descendants may survive (the box stays for a retry): " + "; ".join(problems))
    return OpResult.ok()


# --- kill-object --------------------------------------------------------------------------------


def op_kill_object(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    try:
        request = parse_kill_object_request(ctx.request.stdin)
    except WireError as err:
        raise OpError(str(err)) from None
    client = ctx.client()
    try:
        with ctx.name_lock(name, shared=False):
            outcome = _kill_object(ctx, client, name, request.box.id, request.box.created, request.mode)
    except HcError as err:
        unreachable(ctx, err)
        raise OpError(f"cannot kill the object: {err}") from None
    if isinstance(outcome, OpResult):
        return outcome
    return OpResult.answer(outcome)


def _kill_object(ctx: OpContext, client: HcClient, name: str, address: str, created: str, mode: str) -> Union[KillOutcome, OpResult]:
    try:
        record = client.get(address)
    except HcRpcError as err:
        if err.kind == "not_found":
            return "gone"
        raise
    if box_object(record).created != created:
        return "gone"
    if record.labels.get(LABEL_SESSION) != name:
        return "renamed"
    meta = _read_meta(ctx, record)
    try:
        snapshot = ctx.host.procs.snapshot()
        is_attached = attached(ctx, record, viewer_targets(ctx, snapshot), object_of(record))
    except ProcError:
        snapshot = None
        is_attached = True  # cannot tell: never kill what someone may watch
    if mode == "corpse":
        if is_intact(record) or is_attached:
            return "live"
    else:
        if not is_intact(record) or is_attached or snapshot is None or meta is None or record.pid is None:
            return "changed"
        # Not known dead while launching, or when the box runs a process that
        # cannot be read: only a definite "dead" is killed.
        state, _ = agent_state(snapshot, record, meta.process_names(), meta)
        if state != "dead":
            return "changed"
    problems = kill_incarnation(ctx, client, record, meta, protected=list_city(client, ctx, finished=False))
    if problems:
        return OpResult.fail("killed, but descendants may survive (the box stays for a retry): " + "; ".join(problems))
    _forget(ctx, object_of(record))
    return "killed"


# --- start ---------------------------------------------------------------------------------------


def _setup_env(ctx: OpContext, session: Mapping[str, str], extra: Mapping[str, str]) -> Dict[str, str]:
    """gc's environment with the session's applied, for setup commands; never
    hc's variables (gc may itself run inside an hc terminal)."""
    env = {k: v for k, v in ctx.env.items() if k not in STRIPPED}
    for key, value in session.items():
        if value == "":
            env.pop(key, None)
        else:
            env[key] = value
    env.update(extra)
    return env


def _setup_cwd(cfg: StartConfig) -> str:
    return cfg.work_dir if cfg.work_dir and os.path.isdir(cfg.work_dir) else "/"


def _run_setup(ctx: OpContext, command: str, env: Mapping[str, str], cwd: str) -> Optional[str]:
    budget = ctx.request.deadline.budget(SETUP_TIMEOUT_S, margin=FIRST_TURN_RESERVE_S)
    if budget <= 0:
        return "no time left"
    done = run_bounded(["/bin/sh", "-c", command], env=env, cwd=cwd, timeout_s=budget, cancel=ctx.request.cancel)
    if done.ok:
        return None
    state = "timed out" if done.returncode is None else f"exited {done.returncode}"
    return state + (f": {done.output.splitlines()[-1]}" if done.output else "")


def _agent_slice(ctx: OpContext, session: Mapping[str, str]) -> str:
    """The slice agents run under: the session's ``GC_AGENT_SLICE``, else gc's
    own (as tmux reads it), else the default."""
    return session.get("GC_AGENT_SLICE") or ctx.env.get("GC_AGENT_SLICE", "") or DEFAULT_AGENT_SLICE


def _systemd_run(ctx: OpContext) -> Optional[str]:
    if ctx.test and ctx.env.get(SYSTEMD_RUN_ENV, ""):
        return ctx.env[SYSTEMD_RUN_ENV]
    return shutil.which("systemd-run", path="/usr/bin:/bin:/usr/local/bin")


@dataclass(frozen=True)
class CoreProcess:
    """The core process a probe ran under: its pid and start time."""

    pid: int
    started_ms: int

    def same(self, other: CoreProcess) -> bool:
        return self.pid == other.pid and abs(self.started_ms - other.started_ms) <= CORE_START_SLACK_MS


def _forget_probe(ctx: OpContext) -> None:
    try:
        os.unlink(ctx.state_file(USERSCOPE_FILE))
    except FileNotFoundError:
        pass


def _cached_probe(ctx: OpContext, core: CoreProcess, scope: spawnfile.Scope) -> Optional[Tuple[bool, str]]:
    """A still-valid probe verdict: a success for this core process and
    scope, or a failure younger than the backoff."""
    try:
        raw = read_private_file(ctx.state_file(USERSCOPE_FILE))
        if raw is None:
            return None
        doc = JsonObject.of(loads(raw))
        cached_core = CoreProcess(pid=doc.req_int("pid"), started_ms=doc.req_int("started_ms"))
        if not cached_core.same(core) or doc.req_str("slice") != scope.slice or doc.req_str("systemd_run") != scope.systemd_run:
            return None
        ok = doc.req_bool("ok")
        if not ok and ctx.host.now_ms() - doc.req_int("at_ms") >= SCOPE_FAILURE_BACKOFF_MS:
            return None
        return ok, doc.str_or("detail", "")
    except (JsonShapeError, StateDirError):
        return None


def _user_scope(
    ctx: OpContext, client: HcClient, hc_bin: str, session: Mapping[str, str], warnings: List[str]
) -> Optional[spawnfile.Scope]:
    """The scope agents are launched in, when the user manager the core uses
    can place one: probed with exactly the launcher's ``systemd-run`` argv and
    manager access, kept for the core process on success and for a short
    backoff on failure. Without a user manager hc shares no holder cgroup, so
    there is nothing to escape."""
    if ctx.test and ctx.env.get(USERSCOPE_ENV, "") != "1":
        return None
    if not sys.platform.startswith("linux"):
        return None
    manager = core_env(ctx, hc_bin)
    run_user = manager.get("XDG_RUNTIME_DIR", "")
    if not run_user or not os.path.exists(os.path.join(run_user, "systemd", "private")):
        return None
    systemd_run = _systemd_run(ctx)
    if systemd_run is None:
        warnings.append("agents are not re-scoped out of the holder's cgroup: no systemd-run")
        return None
    agent_slice = _agent_slice(ctx, session)
    if not agent_slice.endswith(".slice") or "/" in agent_slice:
        warnings.append(f"agents are not re-scoped out of the holder's cgroup: GC_AGENT_SLICE {agent_slice!r} is not a slice")
        return None
    scope = spawnfile.Scope(
        systemd_run=systemd_run,
        slice=agent_slice,
        runtime_dir=run_user,
        bus=manager.get("DBUS_SESSION_BUS_ADDRESS", ""),
    )
    status = client.server_status()
    core = CoreProcess(pid=status.pid, started_ms=ctx.host.now_ms() - status.uptime_ms)
    verdict = _cached_probe(ctx, core, scope)
    if verdict is None:
        done = run_bounded(
            [*scope_prefix(scope), "/bin/true"],
            env=dict(scope_env(scope), PATH="/usr/bin:/bin"),
            cwd="/",
            timeout_s=max(0.1, ctx.request.deadline.budget(3.0)),
            cancel=ctx.request.cancel,
        )
        detail = "" if done.ok else (done.output.splitlines()[-1] if done.output else f"systemd-run exited {done.returncode}")
        verdict = (done.ok, detail)
        doc = {
            "pid": core.pid,
            "started_ms": core.started_ms,
            "slice": scope.slice,
            "systemd_run": scope.systemd_run,
            "ok": done.ok,
            "at_ms": ctx.host.now_ms(),
            "detail": detail,
        }
        write_private_file(ctx.state_file(USERSCOPE_FILE), (dumps(doc) + "\n").encode("ascii"))
    ok, detail = verdict
    if not ok:
        warnings.append(f"agents are not re-scoped out of the holder's cgroup: {detail}")
        return None
    return scope


def _spawn_dir(ctx: OpContext) -> str:
    override = ctx.env.get(spawnfile.ROOT_ENV, "") if ctx.test else ""
    return spawnfile.directory(ctx.paths.city_id, override=override or None)


def sweep_spawn_files(ctx: OpContext) -> None:
    """Every op's housekeeping: spawn files a killed start left behind."""
    try:
        spawnfile.sweep(_spawn_dir(ctx))
    except (OSError, StateDirError):
        pass


def _launcher_argv(ctx: OpContext, spawn_path: str) -> List[str]:
    launcher = os.path.join(ctx.host.pack_dir, "assets", "bin", "gc-herdr-core-launch")
    return [ctx.host.python, "-I", "-S", launcher, spawn_path]


def _check_name(records: List[Terminal], name: str, fresh_only: bool) -> Optional[OpResult]:
    if records and fresh_only:
        return OpResult.fail(f'session "{name}" already exists (fresh_only)', ExitCode.FRESH_COLLISION)
    current = newest(records, name)
    if current is not None and is_intact(current):
        return OpResult.fail(f'session "{name}" already exists')
    return None


def op_start(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    try:
        cfg = parse_start_config(ctx.request.stdin)
    except WireError as err:
        raise OpError(str(err)) from None
    ctx.request.redactor.add_start_env(cfg.env)
    try:
        return _start(ctx, name, cfg)
    except HcError as err:
        if isinstance(err, Cancelled):
            raise
        raise OpError(f"cannot start {name!r}: {err}") from None


def _start(ctx: OpContext, name: str, cfg: StartConfig) -> OpResult:
    hc_bin = ensure_core(ctx)
    client = ctx.client()
    warnings: List[str] = []
    with ctx.name_lock(name, shared=False):
        records = list_city(client, ctx, name)
        refused = _check_name(records, name, cfg.fresh_only)
        if refused is not None:
            return refused
        _recycle_before_start(ctx, client, name, records, warnings)
    try:
        warnings += stage(cfg, cfg.env.get("GC_PROVIDER", ""))
    except StagingError as err:
        raise OpError(str(err)) from None
    pre_env = _setup_env(ctx, cfg.env, {})
    for index, command in enumerate(cfg.pre_start):
        failed = _run_setup(ctx, command, pre_env, _setup_cwd(cfg))
        if failed is not None:
            raise OpError(f"pre_start[{index}] {failed}")
    record, scoped = _create(ctx, client, hc_bin, name, cfg, warnings)
    # A failure or a cancel from here on leaves the box, as a dead one stays
    # (_fail_if_ended): gc stops the box of a start that failed (gascity
    # internal/runtime/exec/exec.go cleanupAfterStartFailure).
    waited = _await_agent(ctx, record, cfg)
    if waited is not None:
        warnings.append(waited)
    try:
        _fail_if_ended(client, record, cfg)
    except OpError:
        if scoped:
            _forget_probe(ctx)  # the launch disproved the probe's success
        raise
    setup_env = _setup_env(ctx, cfg.env, {"GC_SESSION": name})
    for index, command in enumerate(cfg.session_setup):
        failed = _run_setup(ctx, command, setup_env, _setup_cwd(cfg))
        if failed is not None:
            warnings.append(f"session_setup[{index}] {failed}")
    if cfg.session_setup_script:
        failed = _run_setup(ctx, cfg.session_setup_script, setup_env, _setup_cwd(cfg))
        if failed is not None:
            warnings.append(f"session_setup_script {failed}")
    if cfg.nudge:
        failed = first_turn(ctx, client, name, record, cfg)
        if failed is not None:
            warnings.append(failed)
    if cfg.session_live:
        warnings.append(SESSION_LIVE_SKIPPED)
    return OpResult(ExitCode.OK, b"", "; ".join(warnings))


def _create(
    ctx: OpContext, client: HcClient, hc_bin: str, name: str, cfg: StartConfig, warnings: List[str]
) -> Tuple[Terminal, bool]:
    """Create the incarnation; returns its record and whether it was launched in a scope."""
    store = meta_store(ctx)
    with ctx.name_lock(name, shared=False):
        records = list_city(client, ctx, name)
        refused = _check_name(records, name, cfg.fresh_only)
        if refused is not None:
            raise OpError(refused.message, refused.code)
        _recycle_before_start(ctx, client, name, records, warnings)
        if cfg.work_dir and not os.path.isdir(cfg.work_dir):
            raise OpError("work_dir is not an existing directory after staging and pre_start")
        obj = new_object_nonce()
        store.write(obj, seed(name, cfg.env, work_dir=cfg.work_dir))
        spawn_path = ""
        created: Optional[Terminal] = None
        pending = False
        try:
            shim.install(ctx.shim_dir, pack_dir=ctx.host.pack_dir, python=ctx.host.python, hc_bin=hc_bin, env=ctx.paths.discovery_env())
            scope = _user_scope(ctx, client, hc_bin, cfg.env, warnings)
            spawn = spawnfile.SpawnSpec(
                env=cfg.env,
                command=cfg.command,
                work_dir=cfg.work_dir,
                shim_dir=ctx.shim_dir,
                scope=scope,
            )
            spawn_path = spawnfile.create(_spawn_dir(ctx), obj, spawn)
            spec = RunSpec(
                argv=tuple(_launcher_argv(ctx, spawn_path)),
                cwd=cfg.work_dir or ctx.host.home(),
                env=TERM_ENV,
                labels=session_labels(ctx.paths.city_id, name, obj),
                name=terminal_name(ctx.paths.city_id, name),
            )
            # Sent once: a run whose reply was lost or timed out may have
            # started the program, so its terminal is looked up by gc.obj
            # (finished too: a quick command may be done), never run again.
            try:
                created = client.run(spec)
            except HcRpcError as err:
                if err.kind == "name_taken":
                    raise OpError(f'session "{name}" already exists') from None
                raise
            except HcError as err:
                pending = err.written and not isinstance(err, HcProtocolError)
                if not pending or isinstance(err, HcCancelled):
                    raise
                found = client.list_terminals(labels={LABEL_OBJ: obj}, include_finished=True).terminals
                if not found:
                    raise
                created = found[0]
            if created.pid is not None:
                created = client.label(created.address, {LABEL_PID: str(created.pid)})
            return created, scope is not None
        except BaseException:
            if spawn_path:
                spawnfile.remove(spawn_path)  # a run hc still starts late finds nothing to launch
            _undo(ctx, created, obj, pending=pending)
            raise


def _undo(ctx: OpContext, created: Optional[Terminal], obj: str, *, pending: bool) -> None:
    """Remove what a failed or canceled create left: the incarnation's
    terminal tree (found by its ``gc.obj`` when ``run`` gave none) and every
    process carrying its instance token, as the program may already have
    started a daemon (every other live box of the city is protected, as in
    ``stop``), then its metadata. When hc cannot read the created record
    afresh or list the city's boxes, the tree is still ended
    (:func:`_reap_trees`) but nothing is looked for by the token. A created
    record hc no longer holds is still looked for by the token (never by
    run's pid, which may be recycled), as the metadata about to go holds
    its only copy. The metadata stays when the terminal may outlive the start:
    a rollback call failed, part of its tree may survive (the record stays
    too), or none was found for a ``pending`` run (one hc never answered).
    Inventory removes metadata that no record carries once it is old."""
    rollback = ctx.rollback_client(ROLLBACK_S + 1.0)
    try:
        meta: Optional[Meta] = meta_store(ctx).read(obj)
    except MetaError:
        meta = None
    try:
        if created is not None:
            # Read afresh: run's reply may be seconds old, and a pid that
            # ended since may already run an unrelated process.
            try:
                # Gone (hc removed it, or its core lost it): what it started
                # is still found by the token, never by run's stale pid.
                targets = _current(rollback, created) or [replace(created, pid=None)]
            except HcError:
                _reap_trees(ctx, [created])  # it may live on: end it from run's reply
                return
        else:
            targets = list(rollback.list_terminals(labels={LABEL_OBJ: obj}, include_finished=True).terminals)
        try:
            city = list_city(rollback, ctx, finished=False) if targets else []
        except HcError:
            _reap_trees(ctx, targets)
            return
        for record in targets:
            # The op's pause ends at its cancel; the rollback's own deadline bounds this one.
            survived = kill_incarnation(
                ctx, rollback, record, meta, protected=city, pause=time.sleep, remover=lambda: ctx.rollback_client(ROLLBACK_S + 1.0)
            )
            if survived:
                return
    except (HcError, ProcError):
        return
    if pending and not targets:
        return
    try:
        _forget(ctx, obj)
    except (OSError, StateDirError):
        pass


def _current(client: HcClient, record: Terminal) -> List[Terminal]:
    """``record`` as hc holds it now; none when it is gone."""
    try:
        return [client.get(record.address)]
    except HcRpcError as err:
        if err.kind == "not_found":
            return []
        raise


def _reap_trees(ctx: OpContext, targets: List[Terminal]) -> None:
    """End each live target's subtree, here: a rollback's kill when hc
    cannot read the created record or list the city's boxes. Without that
    list, another box carrying the same token cannot be told from this one,
    so nothing is looked for by the token. A target's pid may be stale (the
    record may be seconds old): a root that did not start by the record's
    creation (:data:`ROOT_START_SLACK_MS`), or whose start cannot be told,
    is a recycled pid's and is never signalled. The record and its metadata
    stay: gc stops the box a failed start leaves, and that stop finds the
    rest by the token."""
    snapshot = ctx.host.procs.snapshot()
    for record in targets:
        if record.pid is None or not record.is_live or record.pid not in snapshot:
            continue
        started = ctx.host.procs.started_ms(snapshot[record.pid])
        if started is None or started > record.created_ms + ROOT_START_SLACK_MS:
            continue
        keep = _never_killed(snapshot, record, (), _own_root(snapshot, record))
        _reap(ctx, snapshot, subtree(snapshot, record.pid), keep, time.sleep)


def _await_agent(ctx: OpContext, record: Terminal, cfg: StartConfig) -> Optional[str]:
    """Wait until the launcher has exec'd the agent and, when the config names
    the agent's processes, until one runs (tmux's 30 s wait); a warning when
    it did not come."""
    if record.pid is None:
        return None
    names = expand_names(cfg.process_names, cfg.env.get("GC_BIN", ""))
    limit = AGENT_WAIT_S if names else LAUNCH_WAIT_S
    end = time.monotonic() + max(0.0, min(limit, ctx.request.deadline.remaining() - FIRST_TURN_RESERVE_S))
    while True:
        try:
            snapshot = ctx.host.procs.snapshot()
        except ProcError:
            return None
        if record.pid not in snapshot or snapshot[record.pid].zombie:
            return None  # the program already ended: start checks the record
        if not is_launching(snapshot, record.pid) and (not names or find_agent(snapshot, record.pid, names) is not None):
            return None
        if time.monotonic() >= end:
            return "the agent's processes did not appear in time" if names else "the launcher did not start the agent in time"
        ctx.request.cancel.pause(0.05)


def _fail_if_ended(client: HcClient, record: Terminal, cfg: StartConfig) -> None:
    """A start whose agent already exited failed, unless the command is one-shot.
    The dead box stays: gc reads its screen and stops it."""
    if cfg.lifecycle == ONE_SHOT:
        return
    current = client.get(record.address)
    if current.is_live:
        return
    how = f"exit code {current.exit_code}" if current.exit_code is not None else f"signal {current.signal}"
    raise OpError(f"the agent exited during startup ({how})")


# --- the first turn ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Unready:
    """A wait that ended without readiness: the terminal to type the first
    turn into all the same, and why it was not seen ready."""

    terminal: Terminal
    why: str


def _ready(ctx: OpContext, client: HcClient, record: Terminal, cfg: StartConfig) -> Union[Terminal, _Unready, str, None]:
    """Wait until the agent can take its first turn: its terminal then, why it
    cannot (a startup dialog shows), or None if it ended first. A screen
    showing a dialog is never ready, in any mode. A wait that ends with no
    dialog on screen gives the terminal too (:class:`_Unready`), as gc's
    providers type the turn on a probe that timed out, and nothing in gc
    types it later; see :func:`_at_the_waits_end` for one the op's deadline
    cuts short."""
    begun = time.monotonic()
    wait = max(0.0, min(READY_WAIT_S, ctx.request.deadline.remaining() - FIRST_TURN_RESERVE_S))
    end = begun + wait
    # A delay is a guess at readiness, cut to the wait as gc cuts it to its
    # probe timeout.
    delay_until = begun + min(cfg.ready_delay_ms / 1000.0, READY_WAIT_S) if cfg.ready_delay_ms > 0 else None
    last_screen: Optional[str] = None
    stable_since = begun
    seen = False  # a non-empty screen settled during the wait
    while True:
        current = client.get(record.address)
        if not current.is_live:
            return None
        screen = client.read_screen(record.address).text
        now = time.monotonic()  # one reading for both: a delay as long as the wait passes at its end
        if screen != last_screen:
            last_screen, stable_since = screen, now
        settled = bool(screen.strip()) and now - stable_since >= SETTLE_S
        seen = seen or settled
        in_dialog = withholds_first_turn(screen, cfg.ready_prompt_prefix)
        if in_dialog and settled:  # gc answers it once start returns: the wait would outlast it
            return IN_DIALOG
        if not delays_first_turn(screen, cfg.ready_prompt_prefix) and _shows_ready(cfg, current, screen, settled, now, delay_until):
            return current
        if now >= end:
            return _at_the_waits_end(current, in_dialog, cut=wait < READY_WAIT_S, seen=seen)
        ctx.request.cancel.pause(READY_POLL_S)


def _at_the_waits_end(current: Terminal, in_dialog: bool, *, cut: bool, seen: bool) -> Union[_Unready, str]:
    """What a wait that ran out without readiness gives: why the turn is
    withheld (a dialog on screen; or, for a wait the op's deadline ``cut``
    short, no screen ``seen`` to settle, as a dialog may not be drawn yet),
    else the terminal to type it into all the same. Typing on a cut wait is
    the pack's own choice: gc's tmux provider returns before it types, and
    gc's herdr provider skips the turn."""
    if in_dialog:
        return IN_DIALOG
    if cut and not seen:
        return NOT_SEEN
    return _Unready(current, CUT_SHORT if cut else RAN_OUT)


def _shows_ready(
    cfg: StartConfig, current: Terminal, screen: str, settled: bool, now: float, delay_until: Optional[float]
) -> bool:
    """Its prompt shows; else its delay passed; else it reported a status; else its output settled."""
    if cfg.ready_prompt_prefix:
        return shows_ready_prompt(screen, cfg.ready_prompt_prefix)
    if delay_until is not None:
        return now >= delay_until
    return current.reported or settled


def first_turn(ctx: OpContext, client: HcClient, name: str, record: Terminal, cfg: StartConfig) -> Optional[str]:
    """Type the start config's nudge once the agent is ready; a warning when
    it was not delivered, or was typed without readiness."""
    from .inputs import deliver  # the nudge path: a send hc got whole is delivered

    try:
        ready = _ready(ctx, client, record, cfg)
    except HcError as err:
        return _unconfirmed(ctx, name, record, f"the first turn was not sent: {err}")
    if ready is None:
        if cfg.lifecycle == ONE_SHOT:
            return "the agent ended before its first turn"
        raise OpError("the agent exited during startup, before its first turn")
    if isinstance(ready, str):
        return _unconfirmed(ctx, name, record, f"the first turn was withheld: {ready}")
    target, unready = (ready.terminal, ready.why) if isinstance(ready, _Unready) else (ready, "")
    result = deliver(ctx, client, name, target, cfg.nudge, retry_unavailable=True)
    if result.outcome != "delivered":
        return _unconfirmed(ctx, name, record, f"the first turn was not delivered: {result.detail or result.outcome}")
    return f"the first turn was typed without readiness: {unready}" if unready else None


def _unconfirmed(ctx: OpContext, name: str, record: Terminal, detail: str) -> str:
    obj = object_of(record)
    if obj is not None:
        try:
            with ctx.name_lock(name, shared=False):
                store = meta_store(ctx)
                meta = store.read(obj) or Meta(session=name)
                store.write(obj, meta.with_value(STARTUP_UNCONFIRMED_KEY, detail))
        except (LockTimeout, MetaError, OSError, Cancelled):
            pass
    return detail
