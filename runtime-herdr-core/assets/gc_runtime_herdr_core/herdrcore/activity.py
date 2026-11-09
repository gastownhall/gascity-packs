"""A box's last activity (``report-activity``), tmux's ``window_activity`` in hc terms.

* A program that is ``working`` or ``blocked`` is active now.
* A program that reports OSC 7501 status was last active at the later of its
  last status change and the pack's last input to it.
* A program that never reported was last active when its screen last
  changed. hc keeps no output time (an upstream ask), so the pack hashes the
  screen when ``get-last-activity`` reads it and keeps, per incarnation, the
  hash and when it last changed in ``activity.json``, written only when
  something changed. A missing or unreadable entry reads as "changed now".

``inventory`` refreshes the same cache with one screen read per running
agent that never reported (tmux's ``window_activity`` is read the same way,
per window), within its deadline; an incarnation it could not read keeps its
cached entry, and one with none reads as active at its start.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Dict, Final, Iterable, Mapping, Optional

from ..hc.types import Terminal
from ..rpp.flock import LockFileError, LockTimeout
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from ..rpp.statedir import StateDirError
from .config import read_private_file, write_private_file
from .context import OpContext
from .records import object_of

ACTIVITY_FILE: Final = "activity.json"
ACTIVE_WORDS: Final = frozenset({"working", "blocked"})
_LOCK_WAIT_S: Final = 0.5


@dataclass(frozen=True)
class Seen:
    screen_hash: str = ""
    changed_ms: int = 0
    input_ms: int = 0


def _load(ctx: OpContext) -> Dict[str, Seen]:
    try:
        raw = read_private_file(ctx.state_file(ACTIVITY_FILE))
        if raw is None:
            return {}
        doc = JsonObject.of(loads(raw))
        return {
            obj: Seen(
                screen_hash=entry.str_or("hash", ""),
                changed_ms=entry.int_or("changed_ms", 0),
                input_ms=entry.int_or("input_ms", 0),
            )
            for obj, entry in doc.obj_map("objects").items()
        }
    except (JsonShapeError, StateDirError, OSError):
        return {}


def _store(ctx: OpContext, seen: Mapping[str, Seen]) -> None:
    doc = {
        "objects": {
            obj: {"hash": s.screen_hash, "changed_ms": s.changed_ms, "input_ms": s.input_ms}
            for obj, s in seen.items()
        }
    }
    write_private_file(ctx.state_file(ACTIVITY_FILE), (dumps(doc) + "\n").encode("ascii"))


def _update(ctx: OpContext, obj: str, change: Callable[[Seen], Seen]) -> Seen:
    try:
        with ctx.lock("activity", shared=False, wait_s=_LOCK_WAIT_S):
            seen = _load(ctx)
            before = seen.get(obj)
            after = change(before or Seen())
            if after != before:
                seen[obj] = after
                _store(ctx, seen)
            return after
    except (LockTimeout, LockFileError, StateDirError, OSError):
        return change(Seen())


def note_screen(ctx: OpContext, obj: str, screen: str) -> Seen:
    """What the screen of ``obj`` reads now; returns the updated entry."""
    digest = hashlib.sha256(screen.encode("utf-8", "surrogateescape")).hexdigest()
    now = ctx.host.now_ms()

    def change(s: Seen) -> Seen:
        if s.screen_hash == digest and s.changed_ms:
            return s
        return Seen(digest, now, s.input_ms)

    return _update(ctx, obj, change)


def cached(ctx: OpContext) -> Dict[str, Seen]:
    """The whole cache, for inventory."""
    return _load(ctx)


def forget(ctx: OpContext, objects: Iterable[str]) -> None:
    gone = set(objects)
    if not gone:
        return
    try:
        with ctx.lock("activity", shared=False, wait_s=_LOCK_WAIT_S):
            seen = _load(ctx)
            kept = {obj: s for obj, s in seen.items() if obj not in gone}
            if len(kept) != len(seen):
                _store(ctx, kept)
    except (LockTimeout, LockFileError, StateDirError, OSError):
        return


def last_activity_ms(ctx: OpContext, record: Terminal, seen: Optional[Seen]) -> int:
    """When ``record``'s program was last active, by the rules above."""
    now = ctx.host.now_ms()
    word = None if record.status is None else record.status.state
    if word in ACTIVE_WORDS:
        return now
    input_ms = 0 if seen is None else seen.input_ms
    if record.reported:
        return max(record.status_ms or record.created_ms, input_ms)
    if seen is None or not seen.changed_ms:
        return max(record.created_ms, input_ms)
    return max(seen.changed_ms, input_ms)


def object_seen(record: Terminal, seen: Mapping[str, Seen]) -> Optional[Seen]:
    obj = object_of(record)
    return None if obj is None else seen.get(obj)

