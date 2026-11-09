"""The op table and the handshake of runtime ``herdr-core``.

The handshake declares observe.v1 with ``report-attachment`` (v2-ready),
``report-activity``, ``city-scoped`` (each city key has its own core) and
``conformance-faults``. It never declares ``proc.exec``, ``proc.provision``
or ``input-fence``: under ``proc.exec`` gc would drive the box by piping tmux
commands to ``exec``. ``exec``, ``provision`` and ``check-image`` are absent
from the table, so they exit 2 without reading stdin; so, in this build, are
the driving ops (``nudge``, ``send-keys``, ``interrupt``,
``clear-scrollback``), ``watch-startup`` and ``copy-to``, which gc treats as
unimplemented.
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
from . import attach, lifecycle, reads
from .config import ConfigError
from .context import Host, OpContext
from .core import KICK_OP, run_kick
from .metastore import MetaError

OpFn = Callable[[OpContext], OpResult]


def _wrap(host: Host, fn: OpFn) -> Callable[[OpRequest], OpResult]:
    def handle(request: OpRequest) -> OpResult:
        try:
            return fn(OpContext(request, host))
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

    def spec(fn: OpFn, *, stdin: bool = False, deadline: DeadlineClass = "default", cap: int = SMALL_STDOUT_CAP) -> OpSpec:
        return OpSpec(handler=_wrap(host, fn), reads_stdin=stdin, deadline=deadline, stdout_cap=cap)

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
        "attach": spec(attach.op_attach, deadline="start"),
        KICK_OP: spec(_kick),
    }
    return table
