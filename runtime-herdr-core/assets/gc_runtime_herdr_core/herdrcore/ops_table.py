"""The op table and the handshake of runtime ``herdr-core``.

The handshake (:mod:`..handshake`) declares observe.v1 with
``report-attachment`` (v2-ready), ``report-activity``, ``city-scoped`` (each
city key has its own core), ``conformance-faults``, ``server-lifecycle``
(``server-stop``), ``carrier.ops``, ``idle-boundary``, ``input-outcome`` and
``fs.host``. It never declares ``proc.exec``, ``proc.provision`` or
``input-fence``: under ``proc.exec`` gc would drive the box by piping tmux
commands to ``exec``. ``exec``, ``provision`` and ``check-image`` are absent
from the table, so they exit 2 without reading stdin.

An op that names no city (``GC_EXEC_CITY_PATH`` unset or empty: ``gc
runtime check`` or ``conformance`` run outside a city, or a direct call) is
answered before anything is resolved, started, kicked or read: ``observe``
answers unknown, ``inventory`` incomplete, and every other op but
``protocol`` exits 1 naming the variable.

The table is data: each op names the module and function that handle it,
and the handler's module is imported only when that op runs. gc runs every
op as a fresh process, so an op pays for exactly the code it uses; a read
never loads ``start``'s or the core's code. This module therefore imports
none of the handler modules (nor :mod:`.core`) at module level, and only
the entry imports it.
"""

from __future__ import annotations

import importlib
from typing import Callable, Dict, Final, Mapping

from ..rpp.flock import LockFileError, LockTimeout
from ..rpp.frozen import frozen
from ..rpp.ops import (
    INVENTORY_STDOUT_CAP,
    OBSERVE_STDOUT_CAP,
    SMALL_STDOUT_CAP,
    DeadlineClass,
    OpError,
    OpRequest,
    OpResult,
    OpSpec,
    OpTable,
    handshake_op,
)
from ..rpp.statedir import OP_CITY_ENV, StateDirError, city_named
from ..handshake import HANDSHAKE
from .config import ConfigError
from .context import Host, OpContext, no_city_message
from .metastore import MetaError
from .naming import KICK_OP
from .spawnfile import sweep_spawn_files

OpFn = Callable[[OpContext], OpResult]
NoCityAnswer = Callable[[], OpResult]
"""An op's answer when it names no city."""


def _refuse() -> OpResult:
    raise OpError(no_city_message(OP_CITY_ENV))


@frozen
class OpDecl:
    """An op's handler, by module (under ``herdrcore``) and function, and
    the transport facts about it. ``no_city`` names the function of the
    same module that answers when the op names no city; an op without one
    refuses (exit 1, naming the variable)."""

    module: str
    function: str
    stdin: bool = False
    deadline: DeadlineClass = "default"
    cap: int = SMALL_STDOUT_CAP
    housekeeping: bool = True
    no_city: str = ""


OP_SPECS: Final[Mapping[str, OpDecl]] = {
    "start": OpDecl("lifecycle", "op_start", stdin=True, deadline="start"),
    "stop": OpDecl("lifecycle", "op_stop"),
    "kill-object": OpDecl("lifecycle", "op_kill_object", stdin=True),
    "observe": OpDecl("reads", "op_observe", stdin=True, deadline="probe", cap=OBSERVE_STDOUT_CAP, no_city="observe_unknown"),
    "inventory": OpDecl("reads", "op_inventory", cap=INVENTORY_STDOUT_CAP, no_city="inventory_unknown"),
    "is-running": OpDecl("reads", "op_is_running"),
    "process-alive": OpDecl("reads", "op_process_alive", stdin=True),
    "list-running": OpDecl("reads", "op_list_running", cap=INVENTORY_STDOUT_CAP),
    "is-attached": OpDecl("reads", "op_is_attached", deadline="probe"),
    "get-last-activity": OpDecl("reads", "op_get_last_activity"),
    "peek": OpDecl("reads", "op_peek", cap=OBSERVE_STDOUT_CAP),
    "get-meta": OpDecl("reads", "op_get_meta"),
    "set-meta": OpDecl("reads", "op_set_meta", stdin=True),
    "remove-meta": OpDecl("reads", "op_remove_meta"),
    "nudge": OpDecl("inputs", "op_nudge", stdin=True),
    "send-keys": OpDecl("inputs", "op_send_keys"),
    "interrupt": OpDecl("inputs", "op_interrupt"),
    "clear-scrollback": OpDecl("inputs", "op_clear_scrollback"),
    "watch-startup": OpDecl("screen", "op_watch_startup", deadline="start"),
    "attach": OpDecl("attach", "op_attach", deadline="start"),
    "copy-to": OpDecl("screen", "op_copy_to"),
    "server-stop": OpDecl("server", "op_server_stop"),
    KICK_OP: OpDecl("ops_table", "op_kick_core", housekeeping=False),
}
"""Every op but ``protocol`` (the static handshake)."""


def _lazy(module: str, name: str) -> OpFn:
    """The handler ``module.name``, imported when the op runs."""

    def run(ctx: OpContext) -> OpResult:
        fn: OpFn = getattr(importlib.import_module(f"{__package__}.{module}"), name)
        return fn(ctx)

    return run


def _lazy_answer(module: str, name: str) -> NoCityAnswer:
    """The no-city answer ``module.name``, imported when an op names no city."""

    def answer() -> OpResult:
        fn: NoCityAnswer = getattr(importlib.import_module(f"{__package__}.{module}"), name)
        return fn()

    return answer


def _wrap(host: Host, fn: OpFn, *, housekeeping: bool = True, no_city: NoCityAnswer = _refuse) -> Callable[[OpRequest], OpResult]:
    def handle(request: OpRequest) -> OpResult:
        if not city_named(request.env, OP_CITY_ENV):
            return no_city()  # before any context: nothing is resolved, started, kicked or read
        try:
            ctx = OpContext(request, host)
            if housekeeping:
                sweep_spawn_files(ctx)
            return fn(ctx)
        except (StateDirError, ConfigError, MetaError, LockFileError) as err:
            raise OpError(str(err)) from None
        except LockTimeout as err:
            raise OpError(f"busy: {err}") from None

    return handle


def op_kick_core(ctx: OpContext) -> OpResult:
    """The detached core start a read kicked (:func:`.core.run_kick`)."""
    from .core import run_kick

    run_kick(ctx)
    return OpResult.ok()


def build_ops(host: Host) -> OpTable:
    """The op table for ``host``."""
    table: Dict[str, OpSpec] = {"protocol": handshake_op(HANDSHAKE)}
    for op, decl in OP_SPECS.items():
        no_city = _lazy_answer(decl.module, decl.no_city) if decl.no_city else _refuse
        table[op] = OpSpec(
            handler=_wrap(host, _lazy(decl.module, decl.function), housekeeping=decl.housekeeping, no_city=no_city),
            reads_stdin=decl.stdin,
            deadline=decl.deadline,
            stdout_cap=decl.cap,
        )
    return table
