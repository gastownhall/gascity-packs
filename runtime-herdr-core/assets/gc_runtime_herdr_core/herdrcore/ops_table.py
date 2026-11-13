"""The op table and the handshake of runtime ``herdr-core``.

The handshake (:mod:`..handshake`) declares observe.v1 with
``report-attachment`` (v2-ready), ``report-activity``, ``city-scoped`` (each
city key has its own core), ``conformance-faults``, ``server-lifecycle``
(``server-stop``), ``carrier.ops``, ``idle-boundary`` and ``input-outcome``;
not ``fs.host`` yet. It never declares ``proc.exec``, ``proc.provision``
or ``input-fence``: under ``proc.exec`` gc would drive the box by piping tmux
commands to ``exec``. ``exec``, ``provision`` and ``check-image`` are absent
from the table, so they exit 2 without reading stdin.
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
from ..rpp.statedir import StateDirError
from ..handshake import HANDSHAKE
from . import attach, inputs, lifecycle, reads, screen, server
from .config import ConfigError
from .context import Host, OpContext
from .core import KICK_OP, run_kick
from .metastore import MetaError

OpFn = Callable[[OpContext], OpResult]


def _wrap(host: Host, fn: OpFn, *, housekeeping: bool = True) -> Callable[[OpRequest], OpResult]:
    def handle(request: OpRequest) -> OpResult:
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

    def spec(fn: OpFn, *, stdin: bool = False, deadline: DeadlineClass = "default", cap: int = SMALL_STDOUT_CAP, housekeeping: bool = True) -> OpSpec:
        return OpSpec(handler=_wrap(host, fn, housekeeping=housekeeping), reads_stdin=stdin, deadline=deadline, stdout_cap=cap)

    table: Dict[str, OpSpec] = {
        "protocol": handshake_op(HANDSHAKE),
        "start": spec(lifecycle.op_start, stdin=True, deadline="start"),
        "stop": spec(lifecycle.op_stop),
        "kill-object": spec(lifecycle.op_kill_object, stdin=True),
        "observe": spec(reads.op_observe, stdin=True, deadline="probe", cap=OBSERVE_STDOUT_CAP),
        "inventory": spec(reads.op_inventory, cap=INVENTORY_STDOUT_CAP),
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
