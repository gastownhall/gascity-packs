"""Ops that use a box's screen or work directory directly: watch-startup and copy-to.

``watch-startup`` streams the screen (one ``{"content": ...}`` line now and on
every change, read every 250 ms) while gc clears startup dialogs, which
saves gc one ``peek`` process per poll. It reads only the screen, never
history: reading a full-screen program's history scrolls it by sending it
input.

``copy-to`` copies a file or directory into the session's work directory,
never outside it: nothing is written through a symlink (see ``staging``).
"""

from __future__ import annotations

import os
from typing import Final, Optional

from ..hc.errors import HcError
from ..rpp.ops import OpError, OpResult
from ..rpp.wire import WatchStartupEvent
from .context import OpContext
from .reads import current_record, live_record, read_meta, session_arg
from .staging import StagingError, stage_path

WATCH_POLL_S: Final = 0.25


def op_watch_startup(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    record = current_record(ctx, name)
    if record is None:
        raise OpError(f"no session {name!r}")
    last: Optional[str] = None
    client = ctx.client(read=True)
    while ctx.request.deadline.budget(WATCH_POLL_S) > 0:
        try:
            text = client.read_screen(record.address).text
        except HcError as err:
            raise OpError(f"cannot read the screen: {err}") from None
        if text != last:
            ctx.request.emit((WatchStartupEvent(content=text).encode() + "\n").encode("ascii"))
            last = text
        ctx.request.cancel.pause(WATCH_POLL_S)
    return OpResult.ok()


def op_copy_to(ctx: OpContext) -> OpResult:
    args = ctx.request.args
    if len(args) < 2:
        raise OpError("usage: copy-to <name> <src> [rel-dst]")
    name, src = args[0], args[1]
    rel = args[2] if len(args) > 2 else ""
    record = live_record(ctx, name)
    if record is None:
        raise OpError(f"no running session {name!r}")
    meta, _ = read_meta(ctx, record)
    work_dir = meta.work_dir if meta is not None and meta.work_dir else record.cwd
    if not os.path.isabs(work_dir):
        raise OpError(f"{name!r} has no absolute work directory")
    try:
        stage_path(src, work_dir, rel)
    except (OSError, StagingError) as err:
        raise OpError(f"copy-to: {err}") from None
    return OpResult.ok()
