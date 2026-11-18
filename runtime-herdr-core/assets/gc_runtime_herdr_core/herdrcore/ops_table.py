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
"""

from __future__ import annotations

from typing import Callable, Dict

from ..rpp.flock import LockFileError, LockTimeout
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
from . import attach, inputs, lifecycle, reads, screen, server
from .config import ConfigError
from .context import Host, OpContext, no_city_message
from .core import KICK_OP, run_kick
from .metastore import MetaError

OpFn = Callable[[OpContext], OpResult]
NoCityAnswer = Callable[[], OpResult]
"""An op's answer when it names no city."""


def _refuse() -> OpResult:
    raise OpError(no_city_message(OP_CITY_ENV))


def _wrap(host: Host, fn: OpFn, *, housekeeping: bool = True, no_city: NoCityAnswer = _refuse) -> Callable[[OpRequest], OpResult]:
    def handle(request: OpRequest) -> OpResult:
        if not city_named(request.env, OP_CITY_ENV):
            return no_city()  # before any context: nothing is resolved, started, kicked or read
        try:
            ctx = OpContext(request, host)
            if housekeeping:
                lifecycle.sweep_spawn_files(ctx)
            return fn(ctx)
        except (StateDirError, ConfigError, MetaError, LockFileError) as err:
            raise OpError(str(err)) from None
        except LockTimeout as err:
            raise OpError(f"busy: {err}") from None

    return handle


def _kick(ctx: OpContext) -> OpResult:
    run_kick(ctx)
    return OpResult.ok()


def build_ops(host: Host) -> OpTable:
    """The op table for ``host``."""

    def spec(
        fn: OpFn,
        *,
        stdin: bool = False,
        deadline: DeadlineClass = "default",
        cap: int = SMALL_STDOUT_CAP,
        housekeeping: bool = True,
        no_city: NoCityAnswer = _refuse,
    ) -> OpSpec:
        return OpSpec(
            handler=_wrap(host, fn, housekeeping=housekeeping, no_city=no_city), reads_stdin=stdin, deadline=deadline, stdout_cap=cap
        )

    table: Dict[str, OpSpec] = {
        "protocol": handshake_op(HANDSHAKE),
        "start": spec(lifecycle.op_start, stdin=True, deadline="start"),
        "stop": spec(lifecycle.op_stop),
        "kill-object": spec(lifecycle.op_kill_object, stdin=True),
        "observe": spec(reads.op_observe, stdin=True, deadline="probe", cap=OBSERVE_STDOUT_CAP, no_city=reads.observe_unknown),
        "inventory": spec(reads.op_inventory, cap=INVENTORY_STDOUT_CAP, no_city=reads.inventory_unknown),
        "is-running": spec(reads.op_is_running),
        "process-alive": spec(reads.op_process_alive, stdin=True),
        "list-running": spec(reads.op_list_running, cap=INVENTORY_STDOUT_CAP),
        "is-attached": spec(reads.op_is_attached, deadline="probe"),
        "get-last-activity": spec(reads.op_get_last_activity),
        "peek": spec(reads.op_peek, cap=OBSERVE_STDOUT_CAP),
        "get-meta": spec(reads.op_get_meta),
        "set-meta": spec(reads.op_set_meta, stdin=True),
        "remove-meta": spec(reads.op_remove_meta),
        "nudge": spec(inputs.op_nudge, stdin=True),
        "send-keys": spec(inputs.op_send_keys),
        "interrupt": spec(inputs.op_interrupt),
        "clear-scrollback": spec(inputs.op_clear_scrollback),
        "watch-startup": spec(screen.op_watch_startup, deadline="start"),
        "attach": spec(attach.op_attach, deadline="start"),
        "copy-to": spec(screen.op_copy_to),
        "server-stop": spec(server.op_server_stop),
        KICK_OP: spec(_kick, housekeeping=False),
    }
    return table
