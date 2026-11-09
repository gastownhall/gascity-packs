"""start, stop and kill-object.

**start**:

1. Start or check the city's core (:func:`.core.ensure_core`); a core the
   pack did not start is refused.
2. Under the name's lock: a ``fresh_only`` start finding any record exits 73;
   a live intact incarnation is "already exists" (exit 1); every finished
   record and every live broken incarnation of the name is ended and removed
   first, or gc would read "already exists" every pass while the broken
   record stays.
3. Still under the lock: write the incarnation's metadata (identity first,
   observe.v1 rule 5), then ``terminal.run`` the command and label the pid. A
   reply lost after hc started the terminal is retried; ``name_taken`` by this
   incarnation's own terminal is success. A cancel or failure from here on
   removes the terminal and the metadata.

A ``work_dir`` that is not an existing directory fails the start; without
one the program starts in the user's home.

hc persists every ``terminal.run`` environment in plaintext for a day, so
this build gives hc nothing but ``TERM`` and runs the command with the
core's own minimal environment. A start config that carries what only the
agent launcher can apply (a session environment beyond the identity keys,
staging, setup commands, a first turn) is refused rather than silently
dropped.

**stop** and **kill-object** end the incarnation with ``terminal.kill``
(hangup, terminate, kill to the program's process groups), then remove the
record and the metadata.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Final, List, Optional, Union

from ..hc.client import HcClient
from ..hc.errors import HcConnectionLost, HcError, HcRpcError, HcTimeout
from ..hc.types import RunSpec, Terminal
from ..rpp.exitcodes import ExitCode
from ..rpp.ops import OpError, OpResult
from ..rpp.statedir import StateDirError
from ..rpp.wire import IDENTITY_KEYS, KillOutcome, StartConfig, WireError, parse_kill_object_request, parse_start_config
from . import activity
from .attach import attached, viewer_targets
from .context import OpContext
from .core import ensure_core
from .metastore import MetaError, seed
from .naming import LABEL_OBJ, LABEL_PID, LABEL_SESSION, new_object_nonce, session_labels, terminal_name
from .procs import ProcError, expand_names, find_agent
from .reads import list_city, meta_store, session_arg, unreachable
from .records import box_object, is_intact, newest, object_of

TERM_ENV: Final = {"TERM": "xterm-256color"}
"""All the environment hc is given for a terminal (it persists it)."""

ROLLBACK_S: Final = 1.5
RM_WAIT_S: Final = 3.0


# --- ending an incarnation ----------------------------------------------------------------------


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


def end_incarnation(ctx: OpContext, client: HcClient, record: Terminal) -> None:
    """Kill ``record``'s program (when live) and remove the record."""
    if record.is_live:
        try:
            client.kill(record.address)
        except HcRpcError as err:
            if err.kind not in ("not_found", "finished"):
                raise
    _remove_record(client, record, ctx.request.cancel.pause)


def _forget(ctx: OpContext, obj: Optional[str]) -> None:
    if obj is None:
        return
    try:
        meta_store(ctx).remove(obj)
    except MetaError:
        pass
    activity.forget(ctx, [obj])


def _recycle(ctx: OpContext, client: HcClient, records: List[Terminal]) -> None:
    for record in records:
        end_incarnation(ctx, client, record)
        _forget(ctx, object_of(record))


# --- stop ---------------------------------------------------------------------------------------


def op_stop(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    client = ctx.client()
    try:
        with ctx.name_lock(name, shared=False):
            _recycle(ctx, client, list_city(client, ctx, name))
    except HcError as err:
        unreachable(ctx, err)
        raise OpError(f"cannot stop {name!r}: {err}") from None
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
    obj = object_of(record)
    try:
        meta = None if obj is None else meta_store(ctx).read(obj)
    except MetaError:
        meta = None
    try:
        snapshot = ctx.host.procs.snapshot()
        is_attached = attached(ctx, record, viewer_targets(ctx, snapshot), obj)
    except ProcError:
        snapshot = None
        is_attached = True  # cannot tell: never kill what someone may watch
    if mode == "corpse":
        if is_intact(record) or is_attached:
            return "live"
    else:
        if not is_intact(record) or is_attached or snapshot is None or meta is None or record.pid is None:
            return "changed"
        names = meta.process_names()
        if not names or find_agent(snapshot, record.pid, expand_names(names, meta.gc_bin)) is not None:
            return "changed"
    end_incarnation(ctx, client, record)
    _forget(ctx, obj)
    return "killed"


# --- start ---------------------------------------------------------------------------------------


def unsupported_fields(cfg: StartConfig) -> List[str]:
    """What ``cfg`` asks for that only the agent launcher can apply."""
    fields: List[str] = []
    if any(value and key not in IDENTITY_KEYS for key, value in cfg.env.items()):
        fields.append("a session environment")
    for field_name, value in (
        ("pack_overlay_dirs", bool(cfg.pack_overlay_dirs)),
        ("overlay_dir", bool(cfg.overlay_dir)),
        ("copy_files", bool(cfg.copy_files)),
        ("pre_start", bool(cfg.pre_start)),
        ("session_setup", bool(cfg.session_setup)),
        ("session_setup_script", bool(cfg.session_setup_script)),
        ("nudge", bool(cfg.nudge)),
    ):
        if value:
            fields.append(field_name)
    return fields


def _check_name(records: List[Terminal], name: str, fresh_only: bool) -> Optional[OpResult]:
    if records and fresh_only:
        return OpResult.fail(f'session "{name}" already exists (fresh_only)', ExitCode.FRESH_COLLISION)
    current = newest(records, name)
    if current is not None and is_intact(current):
        return OpResult.fail(f'session "{name}" already exists')
    return None


def _run_terminal(ctx: OpContext, client: HcClient, spec: RunSpec, obj: str) -> Terminal:
    """``terminal.run``, retried once after a lost reply; our own ``name_taken`` is success."""
    for attempt in (1, 2):
        try:
            return client.run(spec)
        except HcRpcError as err:
            if err.kind != "name_taken":
                raise
            for record in list_city(client, ctx, spec.labels[LABEL_SESSION], finished=False):
                if object_of(record) == obj:
                    return record
            raise OpError(f'session "{spec.labels[LABEL_SESSION]}" already exists') from None
        except (HcConnectionLost, HcTimeout) as err:
            if not err.written or attempt == 2:
                raise
    raise OpError("terminal.run did not answer")


def op_start(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    try:
        cfg = parse_start_config(ctx.request.stdin)
    except WireError as err:
        raise OpError(str(err)) from None
    ctx.request.redactor.add_start_env(cfg.env)
    refused = unsupported_fields(cfg)
    if refused:
        raise OpError(
            "this build cannot apply " + ", ".join(refused) + " yet (the agent launcher that carries them is not in it)"
        )
    if cfg.work_dir and not os.path.isdir(cfg.work_dir):
        raise OpError("work_dir is not an existing directory")
    ensure_core(ctx)
    client = ctx.client()
    with ctx.name_lock(name, shared=False):
        records = list_city(client, ctx, name)
        collision = _check_name(records, name, cfg.fresh_only)
        if collision is not None:
            return collision
        _recycle(ctx, client, records)
        obj = new_object_nonce()
        meta_store(ctx).write(obj, seed(name, cfg.env, work_dir=cfg.work_dir))
        created: Optional[Terminal] = None
        try:
            created = _run_terminal(
                ctx,
                client,
                RunSpec(
                    argv=("/bin/sh", "-c", cfg.command) if cfg.command else ("/bin/sh",),
                    cwd=cfg.work_dir or ctx.host.home(),
                    env=TERM_ENV,
                    labels=session_labels(ctx.paths.city_id, name, obj),
                    name=terminal_name(ctx.paths.city_id, name),
                ),
                obj,
            )
            if created.pid is not None:
                client.label(created.address, {LABEL_PID: str(created.pid)})
        except BaseException:
            _undo(ctx, created, obj)
            raise
    return OpResult.ok()


def _undo(ctx: OpContext, created: Optional[Terminal], obj: str) -> None:
    """Remove what a failed or canceled start left: the incarnation's
    terminal (found by its ``gc.obj`` when ``run``'s reply never came) and
    its metadata."""
    rollback = ctx.rollback_client(ROLLBACK_S + 1.0)
    try:
        targets = [created] if created is not None else []
        if not targets:
            targets = list(rollback.list_terminals(labels={LABEL_OBJ: obj}, include_finished=True).terminals)
        for record in targets:
            if record.is_live:
                rollback.kill(record.address)
            rollback.remove(record.address)
    except HcError:
        pass
    try:
        _forget(ctx, obj)
    except (OSError, StateDirError):
        pass
