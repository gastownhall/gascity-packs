"""start, stop and kill-object.

**start** (welded: gc's ``start`` both prepares the box and launches the
agent):

1. Start or check the city's core (:func:`.core.ensure_core`); a core the
   pack did not start is refused.
2. Under the name's lock: a ``fresh_only`` start finding any record exits 73;
   a live intact incarnation is "already exists" (exit 1); every finished
   record and every live broken incarnation of the name is recycled first
   (tree kill, then removed), or gc would read "already exists" every pass
   while the broken record stays.
3. Unlocked: stage the start config's files and run ``pre_start`` (fatal).
4. Under the lock again, re-checked: write the incarnation's metadata
   (identity first, observe.v1 rule 5), the shims and a spawn file, then
   ``terminal.run`` the launcher and label the pid. The run is sent once: hc
   may have run a request whose reply was lost, so the start looks that
   terminal up by its ``gc.obj`` (finished too) and never runs the command
   twice. A cancel or failure from here on removes the spawn file, the
   terminal and then the metadata; the metadata stays while the terminal may
   outlive the start, as one without it reads ``identity: {}``.
5. Unlocked: ``session_setup`` and the setup script (warnings only), then the
   first turn, then ``session_live`` (warnings only, as tmux runs it): once the agent is ready (its prompt, its delay, its first
   status report, or output that settled), the config's ``nudge`` is sent
   through the nudge path (written is delivered). A refusal types nothing and records
   ``GC_STARTUP_DELIVERY_UNCONFIRMED`` in the metadata.

**stop** and **kill-object** end an incarnation's whole process tree:
descendants are captured, with their start times, before hc's kill (hc ends
the program's process groups, and since 0.1.19 no detached descendant); city
infrastructure and its subtree are pruned from the kill set; what is left
and still the same process gets TERM, then KILL. A broken incarnation's
agent may already be gone with its children re-parented, so they are also
found by the incarnation's ``GC_INSTANCE_TOKEN`` in their environment. When
the process table cannot be read the kill still happens, but the op exits 1
("descendants may survive") so gc retries. A process of the tree that cannot
be read (opaque: it has no start time to fence by) is never signalled, and
is reported the same way.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass
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
from .naming import LABEL_OBJ, LABEL_PID, LABEL_SESSION, new_object_nonce, session_labels, terminal_name
from .procs import Proc, ProcError, expand_names, fenced_pids, find_agent, is_launching, kill_captured, scan_environ, subtree
from .reads import agent_state, list_city, meta_store, session_arg, unreachable
from .records import BROKEN_REASONS, box_object, is_broken, is_intact, newest, object_of
from .staging import StagingError, stage

INSTANCE_TOKEN_KEY: Final = "GC_INSTANCE_TOKEN"
STARTUP_UNCONFIRMED_KEY: Final = "GC_STARTUP_DELIVERY_UNCONFIRMED"
TERM_ENV: Final = {"TERM": "xterm-256color"}
"""All the environment hc is given for a terminal (it persists it): the
session's travels in the spawn file."""

ONE_SHOT: Final = "one_shot"
SETUP_TIMEOUT_S: Final = 30.0
LAUNCH_WAIT_S: Final = 5.0
AGENT_WAIT_S: Final = 30.0
READY_WAIT_S: Final = 60.0
READY_POLL_S: Final = 0.25
SETTLE_S: Final = 1.0
FIRST_TURN_RESERVE_S: Final = 5.0
ROLLBACK_S: Final = 1.5
RM_WAIT_S: Final = 3.0
DEFAULT_AGENT_SLICE: Final = "gascity-agents.slice"
USERSCOPE_FILE: Final = "userscope.json"
USERSCOPE_ENV: Final = "GC_HC_TEST_USERSCOPE"
"""Test-only: ``1`` lets a test run probe the user manager (off by default under ``GC_HC_TEST=1``)."""
SYSTEMD_RUN_ENV: Final = "GC_HC_TEST_SYSTEMD_RUN"
"""Test-only: the systemd-run to probe and launch with."""
SCOPE_FAILURE_BACKOFF_MS: Final = 5 * 60 * 1000
CORE_START_SLACK_MS: Final = 5_000
"""Two reads of one core's start time differ by at most this; a wider gap
(a suspend, a clock step) only costs one more probe."""


# --- killing an incarnation -------------------------------------------------------------------


def _needs_identity_scan(record: Terminal) -> bool:
    return is_broken(record) or (record.is_finished and record.reason in BROKEN_REASONS)


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


def kill_incarnation(
    ctx: OpContext,
    client: HcClient,
    record: Terminal,
    meta: Optional[Meta],
    *,
    protected: Iterable[Terminal] = (),
    pause: Optional[Callable[[float], None]] = None,
) -> List[str]:
    """End ``record``'s program tree and remove the record; returns what may
    survive. ``pause`` waits between checks (default: the op's, which a
    cancel ends)."""
    wait = ctx.request.cancel.pause if pause is None else pause
    problems: List[str] = []
    procs = ctx.host.procs
    try:
        snapshot: Optional[Dict[int, Proc]] = procs.snapshot()
    except ProcError as err:
        snapshot = None
        problems.append(f"cannot read the process table ({err})")
    captured: Dict[int, Proc] = {}
    if snapshot is not None:
        if record.pid is not None and record.is_live:
            captured.update((p.pid, p) for p in subtree(snapshot, record.pid))
        token = "" if meta is None else meta.values.get(INSTANCE_TOKEN_KEY, "")
        if token and _needs_identity_scan(record):
            captured.update((p.pid, p) for p in scan_environ(procs, snapshot, INSTANCE_TOKEN_KEY, token))
    kill_error: Optional[HcError] = None
    if record.is_live:
        try:
            client.kill(record.address)
        except HcRpcError as err:
            if err.kind not in ("not_found", "finished"):
                kill_error = err
        except HcError as err:
            kill_error = err
    if snapshot is not None:
        keep: Set[int] = set(fenced_pids(snapshot)) | {os.getpid()}
        for other in protected:
            if other.address != record.address and other.pid is not None and is_intact(other):
                keep.update(p.pid for p in subtree(snapshot, other.pid))
        targets = [p for pid, p in captured.items() if pid not in keep]
        opaque = [p for p in targets if p.opaque]
        if opaque:
            problems.append("cannot read, so never signalled: " + ", ".join(str(p.pid) for p in opaque[:8]))
        survivors = kill_captured(procs, [p for p in targets if not p.opaque], pause=wait)
        if survivors:
            problems.append("still running: " + ", ".join(str(p.pid) for p in survivors[:8]))
    if kill_error is not None:
        raise kill_error  # the tree is dead either way; the record stays for the next try
    _remove_record(client, record, wait)
    return problems


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


def _recycle(ctx: OpContext, client: HcClient, records: List[Terminal]) -> List[str]:
    """End and remove ``records``; every other live box of the city is protected."""
    if not records:
        return []
    city = list_city(client, ctx, finished=False)
    problems: List[str] = []
    for record in records:
        problems += kill_incarnation(ctx, client, record, _read_meta(ctx, record), protected=city)
        _forget(ctx, object_of(record))
    return problems


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
        return OpResult.fail(f"stopped {name!r}, but descendants may survive: " + "; ".join(problems))
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
    _forget(ctx, object_of(record))
    if problems:
        return OpResult.fail("killed, but descendants may survive: " + "; ".join(problems))
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
        warnings += _recycle(ctx, client, records)
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
    for index, command in enumerate(cfg.session_live):
        failed = _run_setup(ctx, command, setup_env, _setup_cwd(cfg))
        if failed is not None:
            warnings.append(f"session_live[{index}] {failed}")
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
        warnings += _recycle(ctx, client, records)
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
    terminal tree (found by its ``gc.obj`` when ``run`` gave none), then its
    metadata. The metadata stays when the terminal may outlive the start: a
    rollback call failed, or none was found for a ``pending`` run (one hc
    never answered). Inventory removes metadata that no record carries once
    it is old."""
    rollback = ctx.rollback_client(ROLLBACK_S + 1.0)
    try:
        if created is not None:
            targets = [created]
        else:
            targets = list(rollback.list_terminals(labels={LABEL_OBJ: obj}, include_finished=True).terminals)
        for record in targets:
            # The op's pause ends at its cancel; the rollback's own deadline bounds this one.
            kill_incarnation(ctx, rollback, record, None, pause=time.sleep)
    except (HcError, ProcError):
        return
    if pending and not targets:
        return
    try:
        _forget(ctx, obj)
    except (OSError, StateDirError):
        pass


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


def _ready(ctx: OpContext, client: HcClient, record: Terminal, cfg: StartConfig) -> Optional[Terminal]:
    """Wait until the agent can take its first turn; None if it ended first."""
    budget = min(READY_WAIT_S, ctx.request.deadline.remaining() - FIRST_TURN_RESERVE_S)
    end = time.monotonic() + max(0.0, budget)
    delay_until = time.monotonic() + cfg.ready_delay_ms / 1000.0 if cfg.ready_delay_ms > 0 else None
    last_screen: Optional[str] = None
    stable_since = time.monotonic()
    current = record
    while True:
        current = client.get(record.address)
        if not current.is_live:
            return None
        screen = client.read_screen(record.address).text
        if cfg.ready_prompt_prefix:
            if any(line.lstrip().startswith(cfg.ready_prompt_prefix) for line in screen.splitlines()):
                return current
        elif delay_until is not None:
            if time.monotonic() >= delay_until:
                return current
        elif current.reported:
            return current
        else:
            if screen != last_screen:
                last_screen, stable_since = screen, time.monotonic()
            elif screen.strip() and time.monotonic() - stable_since >= SETTLE_S:
                return current
        if time.monotonic() >= end:
            return current
        ctx.request.cancel.pause(READY_POLL_S)


def first_turn(ctx: OpContext, client: HcClient, name: str, record: Terminal, cfg: StartConfig) -> Optional[str]:
    """Type the start config's nudge once the agent is ready; a warning when it was not delivered."""
    from .inputs import deliver  # the nudge path: a written send is delivered

    try:
        ready = _ready(ctx, client, record, cfg)
    except HcError as err:
        return _unconfirmed(ctx, name, record, f"the first turn was not sent: {err}")
    if ready is None:
        if cfg.lifecycle == ONE_SHOT:
            return "the agent ended before its first turn"
        raise OpError("the agent exited during startup, before its first turn")
    result = deliver(ctx, client, name, ready, cfg.nudge, retry_unavailable=True)
    if result.outcome == "delivered":
        return None
    return _unconfirmed(ctx, name, record, f"the first turn was not delivered: {result.detail or result.outcome}")


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
