"""provision and launch (``proc.provision`` with ``proc.launch``): gc's
un-welded start.

gc (from gastownhall/gascity#9226) starts a session of this pack in two ops:
``provision`` prepares the name, ``launch`` starts the agent. gc then writes
the launch's identity with ``set-meta``, publishes the ready prompt, answers
startup dialogs through the pack's ``watch-startup``, ``peek`` and
``send-keys``, runs ``session_setup`` on the host and queues the first turn,
which its nudge queue delivers once the agent takes input. Neither op types
anything. The welded ``start`` (:mod:`.lifecycle`) stays for every gc that
calls it, and still types the first turn.

**provision** does all a welded start does before its terminal: the core is
started or checked (a foreign one refused); under the name's lock a
``fresh_only`` provision finding any record exits 73, a live intact
incarnation is "already exists" (exit 1, nothing staged: gc sends the full
config when a live box may hold the name), and finished or broken records
are recycled as a start recycles them; then, unlocked, the config's files
are staged and its ``pre_start`` run (fatal), only what the config carries
(under ``fs.host`` gc does that host work itself and leaves it out). Last,
under the lock, it writes the name's provision record
(:mod:`.provisioned`): the identity to seed, and the session steps the
config carried, which run once the agent does. It creates no terminal, no
spawn file and no process, so ``is-running`` answers false, ``observe``
absent, and ``inventory`` leaves the name out, as while a welded start
stages and runs ``pre_start``. ``session_live`` is never run.

**launch** is the welded start's create without the first turn. Without an
unexpired provision record in a city at rest (parked or never started) it
exits 1 and starts no core: a late launch after ``gc stop`` or
``server-stop`` never revives the city. Under the name's lock, with every
record of the name (finished ones too):

* ``fresh_only`` and any record: exit 73, touching nothing;
* no provision record and no record: exit 1 (a ``stop`` between
  ``provision`` and ``launch`` dropped it);
* otherwise each earlier incarnation's tree is ended as a start ends it
  (the same refusal while its processes may survive), but its record stays;
  the new terminal is created (metadata first, observe.v1 rule 5, then the
  shims, the spawn file and ``terminal.run``) and only then are the earlier
  records removed, so the name is never listed absent mid-relaunch.

The new incarnation's metadata is the replaced incarnation's (less the
pack's own per-incarnation keys: a warm box keeps its metadata), then the
provision record's seed, then the launch env's non-empty identity keys and
``GC_CONTINUATION_EPOCH`` over them, so a key the config does not carry
keeps the box's value and ``get-meta`` answers the launch's identity from
the moment ``launch`` returns. Unlocked, ``launch`` waits for the agent's
processes; an agent that exits during startup fails a launch that is not
one-shot, and its box is left for gc's token-gated stop. Then it runs the
deferred session steps, or its own config's if it carries any, never both
(warnings only). It ignores the config's ``nudge``.
"""

from __future__ import annotations

from typing import List, Optional

from ..hc.errors import HcError
from ..hc.types import Terminal
from ..rpp.cancel import Cancelled
from ..rpp.exitcodes import ExitCode
from ..rpp.ops import OpError, OpResult
from ..rpp.wire import StartConfig, WireError, parse_start_config
from . import provisioned
from .context import OpContext
from .core import at_rest, ensure_core
from .lifecycle import (
    SESSION_LIVE_SKIPPED,
    Plan,
    await_ended,
    await_launched,
    carried_values,
    check_name,
    create,
    prepare,
    recycle_before_start,
    run_session_steps,
)
from .metastore import seed
from .provisioned import Provisioned, SessionSteps, steps_of
from .reads import list_city, session_arg


def _config(ctx: OpContext) -> StartConfig:
    try:
        cfg = parse_start_config(ctx.request.stdin)
    except WireError as err:
        raise OpError(str(err)) from None
    ctx.request.redactor.add_start_env(cfg.env)
    return cfg


def _nothing_provisioned(name: str) -> OpError:
    return OpError(f"nothing is provisioned for {name!r}: provision it first")


# --- provision -------------------------------------------------------------------------------


def op_provision(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    cfg = _config(ctx)
    try:
        return _provision(ctx, name, cfg)
    except HcError as err:
        if isinstance(err, Cancelled):
            raise
        raise OpError(f"cannot provision {name!r}: {err}") from None


def _provision(ctx: OpContext, name: str, cfg: StartConfig) -> OpResult:
    ensure_core(ctx)
    client = ctx.client()
    warnings: List[str] = []
    with ctx.name_lock(name, shared=False):
        records = list_city(client, ctx, name)
        refused = check_name(records, name, cfg.fresh_only)
        if refused is not None:
            return refused
        provisioned.sweep(ctx, ctx.host.now_ms())
        recycle_before_start(ctx, client, name, records, warnings)
        provisioned.drop(ctx, name)
    prepare(ctx, cfg, warnings)
    with ctx.name_lock(name, shared=False):
        # Re-checked: a start may have taken the name while this one staged.
        refused = check_name(list_city(client, ctx, name), name, cfg.fresh_only)
        if refused is not None:
            return refused
        provisioned.write(ctx, provisioned.of_config(name, cfg, ctx.host.now_ms()))
    if cfg.session_live:
        warnings.append(SESSION_LIVE_SKIPPED)
    return OpResult(ExitCode.OK, b"", "; ".join(warnings))


# --- launch ------------------------------------------------------------------------------------


def op_launch(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    cfg = _config(ctx)
    try:
        return _launch(ctx, name, cfg)
    except HcError as err:
        if isinstance(err, Cancelled):
            raise
        raise OpError(f"cannot launch {name!r}: {err}") from None


def _launch(ctx: OpContext, name: str, cfg: StartConfig) -> OpResult:
    if provisioned.read(ctx, name, ctx.host.now_ms()) is None and at_rest(ctx):
        raise _nothing_provisioned(name)  # never a core for a city at rest
    hc_bin = ensure_core(ctx)
    client = ctx.client()
    warnings: List[str] = []
    deferred: List[Optional[SessionSteps]] = []

    def plan(records: List[Terminal]) -> Plan:
        if cfg.fresh_only and records:
            raise OpError(f'session "{name}" already exists (fresh_only)', ExitCode.FRESH_COLLISION)
        record: Optional[Provisioned] = provisioned.read(ctx, name, ctx.host.now_ms())
        if record is None and not records:
            raise _nothing_provisioned(name)
        values = carried_values(ctx, records)
        recycle_before_start(ctx, client, name, records, warnings, keep=True)
        await_ended(ctx, client, records)
        if record is not None:
            values.update(record.values)
            deferred.append(record.steps)
        return Plan(meta=seed(name, cfg.env, work_dir=cfg.work_dir, values=values), replaced=records)

    created, scoped = create(ctx, client, hc_bin, name, cfg, warnings, plan)
    # A failure or a cancel from here on leaves the box: gc stops it when it
    # carries this launch's token (exec.go cleanupAfterFreshStartFailure).
    await_launched(ctx, client, created, cfg, scoped, warnings)
    own = steps_of(cfg)
    run_session_steps(ctx, name, cfg.env, own if own is not None else (deferred[0] if deferred else None), warnings)
    if cfg.session_live:
        warnings.append(SESSION_LIVE_SKIPPED)
    return OpResult(ExitCode.OK, b"", "; ".join(warnings))
