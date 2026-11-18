"""The op table and the handshake of runtime ``herdr-core``.

The handshake (:mod:`..handshake`) declares observe.v1 with
``report-attachment`` (v2-ready), ``report-activity``, ``city-scoped`` (each
city key has its own core), ``conformance-faults``, ``server-lifecycle``
(``server-stop``), ``carrier.ops``, ``idle-boundary``, ``input-outcome`` and
``fs.host``. It never declares ``proc.exec``, ``proc.provision`` or
``input-fence``: under ``proc.exec`` gc would drive the box by piping tmux
commands to ``exec``. ``exec``, ``provision`` and ``check-image`` are absent
from the table, so they exit 2 without reading stdin.

The table is data: each op names the module and function that handle it,
and the handler's module is imported only when that op runs. gc runs every
op as a fresh process, so an op pays for exactly the code it uses; a read
never loads ``start``'s or the core's code. This module therefore imports
none of the handler modules (nor :mod:`.core`) at module level.
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
from ..rpp.statedir import StateDirError
from ..handshake import HANDSHAKE
from .config import ConfigError
from .context import Host, OpContext
from .metastore import MetaError
from .spawnfile import sweep_spawn_files

OpFn = Callable[[OpContext], OpResult]

KICK_OP: Final = "x-kick-core"
"""The pack's own detached core start (:func:`.core.kick`), never run by gc."""


@frozen
class OpDecl:
    """An op's handler, by module (under ``herdrcore``) and function, and
    the transport facts about it."""

    module: str
    function: str
    stdin: bool = False
    deadline: DeadlineClass = "default"
    cap: int = SMALL_STDOUT_CAP
    housekeeping: bool = True


OP_SPECS: Final[Mapping[str, OpDecl]] = {
    "start": OpDecl("lifecycle", "op_start", stdin=True, deadline="start"),
    "stop": OpDecl("lifecycle", "op_stop"),
    "kill-object": OpDecl("lifecycle", "op_kill_object", stdin=True),
    "observe": OpDecl("reads", "op_observe", stdin=True, deadline="probe", cap=OBSERVE_STDOUT_CAP),
    "inventory": OpDecl("reads", "op_inventory", cap=INVENTORY_STDOUT_CAP),
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


def _wrap(host: Host, fn: OpFn, *, housekeeping: bool = True) -> Callable[[OpRequest], OpResult]:
    def handle(request: OpRequest) -> OpResult:
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
        table[op] = OpSpec(
            handler=_wrap(host, _lazy(decl.module, decl.function), housekeeping=decl.housekeeping),
            reads_stdin=decl.stdin,
            deadline=decl.deadline,
            stdout_cap=decl.cap,
        )
    return table
