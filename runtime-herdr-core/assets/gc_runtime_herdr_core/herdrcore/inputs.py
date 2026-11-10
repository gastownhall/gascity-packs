"""The driving ops: nudge, send-keys, interrupt and clear-scrollback.

Input goes to the box's current incarnation by its terminal address, never
by name, and only while that incarnation is intact: a kept terminal's
replacement shell is not the agent. Outcomes follow RPP v0: delivered, or a
box that is gone, exits 0 (best-effort input, exec-session-provider.md
"Conventions"); a refusal exits 1 with the reason and nothing typed:

* hc refused (``blocked``: the agent waits on its own question; ``unavailable``:
  the terminal is still starting or waits for a shell; a failed
  precondition);
* the request never reached hc (the core is down, or refused on its hello),
  or a ``nudge``'s reached it cut short (hc acts on no part of a request);
* a tmux key with no hc spelling.

A ``nudge`` whose request reached hc whole is delivered, like tmux's
fire-and-forget ``send-keys``: hc types a send only once a person stops
typing and finishes it after the pack stops waiting, so one it still holds
at the op's deadline, or whose reply was lost, is typed later, and gc must
not send it again. The accepted limit: a nudge hc still holds is lost if the
core dies before the person stops typing. ``send-keys`` and ``interrupt``
whose reply was lost after the write answer exit 1 ("unconfirmed").

No lock is held across a ``send``, which hc may hold for as long as a person
types, so ``observe`` keeps answering within its 4 s.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Final, List, Literal, Mapping, Optional, Sequence, Tuple

from ..hc.client import HcClient
from ..hc.errors import HcError, HcRpcError
from ..hc.types import Terminal
from ..rpp.ops import OpError, OpResult
from . import activity
from .context import OpContext
from .reads import list_city, session_arg, unreachable
from .records import is_intact, newest, object_of

GONE_KINDS: Final = frozenset({"not_found", "finished"})

TMUX_KEYS: Final[Mapping[str, str]] = {
    "Enter": "enter",
    "Escape": "esc",
    "Esc": "esc",
    "Tab": "tab",
    "BTab": "shift+tab",
    "BSpace": "backspace",
    "Space": "space",
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
    "Home": "home",
    "End": "end",
    "PageUp": "pageup",
    "PgUp": "pageup",
    "PPage": "pageup",
    "PageDown": "pagedown",
    "PgDn": "pagedown",
    "NPage": "pagedown",
    "IC": "insert",
    "Insert": "insert",
    "DC": "delete",
    "Delete": "delete",
    **{f"F{n}": f"f{n}" for n in range(1, 13)},
}
"""tmux key names gc sends (``send-keys``) and their hc names (hc ``src/keys.rs``)."""

HC_CHARACTERS: Final = frozenset(string.ascii_lowercase + string.digits + "`\\[],=-.';/")
"""The characters hc names a key by (its ``key_code``); an upper-case letter is ``shift+<letter>``."""

TMUX_MODIFIERS: Final[Mapping[str, str]] = {"C-": "ctrl+", "M-": "alt+", "S-": "shift+"}


def _character(ch: str) -> Optional[str]:
    if ch in HC_CHARACTERS:
        return ch
    if ch == " ":
        return "space"
    if ch in string.ascii_uppercase:
        return "shift+" + ch.lower()
    return None


def translate_key(key: str) -> Optional[List[str]]:
    """``key`` (a tmux key name or literal text) as hc key names; None when hc has no spelling."""
    if key in TMUX_KEYS:
        return [TMUX_KEYS[key]]
    prefix = ""
    rest = key
    while len(rest) > 2 and rest[:2] in TMUX_MODIFIERS:
        prefix += TMUX_MODIFIERS[rest[:2]]
        rest = rest[2:]
    if prefix:
        base = TMUX_KEYS.get(rest) or (rest.lower() if len(rest) == 1 else None)
        if base is None or (len(base) == 1 and base not in HC_CHARACTERS):
            return None
        return [prefix + base]
    if not key:
        return None
    out: List[str] = []
    for ch in key:
        name = _character(ch)
        if name is None:
            return None
        out.append(name)
    return out


def translate_keys(keys: Sequence[str]) -> Tuple[Optional[List[str]], str]:
    """All of ``keys`` translated, or None and the first key that cannot be."""
    out: List[str] = []
    for key in keys:
        names = translate_key(key)
        if names is None:
            return None, key
        out.extend(names)
    return out, ""


NUDGE_SEND_RESERVE_S: Final = 5.0
"""A nudge's ``send`` stops waiting this long before the op's deadline. A
send hc still holds is delivered, so that answer must reach gc: one cut off
by gc's own kill reads as a failure, and the queue would resend the text."""


def _target(ctx: OpContext, name: str, *, send_reserve: Optional[float] = None) -> Tuple[HcClient, Optional[Terminal]]:
    client = ctx.client(send_reserve=send_reserve)
    try:
        record = newest(list_city(client, ctx, name, finished=False), name)
    except HcError as err:
        unreachable(ctx, err)
        raise OpError(f"not sent: cannot reach the city's core: {err}") from None
    return client, (record if record is not None and is_intact(record) else None)


Outcome = Literal["delivered", "gone", "pending_interaction", "not_sent", "unconfirmed"]


@dataclass(frozen=True)
class Delivery:
    outcome: Outcome
    detail: str = ""

    @property
    def answered_ok(self) -> bool:
        """Whether RPP v0 answers it with exit 0 (delivered, or the box is gone)."""
        return self.outcome in ("delivered", "gone")


def _refused(err: HcRpcError) -> Delivery:
    if err.kind in GONE_KINDS:
        return Delivery("gone")
    if err.kind == "blocked":
        return Delivery("pending_interaction", "pending interaction: the agent is waiting on its own question; nothing was typed")
    if err.kind == "unavailable":
        return Delivery("not_sent", "not sent: the terminal is not ready for input; nothing was typed")
    return Delivery("not_sent", f"not sent: {err}")


def _lost(what: str, err: HcError) -> Delivery:
    if err.written:
        return Delivery("unconfirmed", f"unconfirmed: {what} may still be typed ({err})")
    return Delivery("not_sent", f"not sent: {err}")


def deliver(
    ctx: OpContext, client: HcClient, name: str, record: Terminal, text: str, *, retry_unavailable: bool = False
) -> Delivery:
    """Send ``text`` to ``record``.

    A send whose request reached hc whole is delivered unless hc answers
    that nothing was typed: hc finishes a send after its client stops
    waiting, so one it still holds for a person's pause, or whose reply was
    lost, is typed; and answering it as a failure would make gc's queue
    send it again. Only a send never written, one cut short (hc acts on no
    part of a request), or one hc refused, is not sent."""
    obj = object_of(record)
    while True:
        try:
            client.send(record.address, text)
        except HcRpcError as err:
            if retry_unavailable and err.kind == "unavailable" and ctx.request.deadline.budget(1.0) > 0.5:
                ctx.request.cancel.pause(0.5)
                continue
            return _refused(err)
        except HcError as err:
            if not err.written or err.partial:
                return Delivery("not_sent", f"not sent: {err}")
        if obj is not None:
            activity.note_input(ctx, obj)
        return Delivery("delivered")


def op_nudge(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    text = ctx.request.stdin.decode("utf-8", "surrogateescape")
    client, record = _target(ctx, name, send_reserve=NUDGE_SEND_RESERVE_S)
    if record is None:
        return OpResult.ok()
    result = deliver(ctx, client, name, record, text)
    return OpResult.ok() if result.answered_ok else OpResult.fail(result.detail)


def _answer(result: Delivery) -> OpResult:
    return OpResult.ok() if result.answered_ok else OpResult.fail(result.detail)


def op_send_keys(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request)
    keys, bad = translate_keys(ctx.request.args[1:])
    if keys is None:
        return OpResult.fail(f"rejected: tmux key {bad!r} has no herdr-core spelling; nothing was typed")
    client, record = _target(ctx, name)
    if record is None or not keys:
        return OpResult.ok()
    try:
        client.keys(record.address, keys)
    except HcRpcError as err:
        return _answer(_refused(err))
    except HcError as err:
        return _answer(_lost("the keys", err))
    obj = object_of(record)
    if obj is not None:
        activity.note_input(ctx, obj)
    return OpResult.ok()


def op_interrupt(ctx: OpContext) -> OpResult:
    name = session_arg(ctx.request) if ctx.request.args and ctx.request.args[0] else ""
    if not name:
        return OpResult.ok()
    client, record = _target(ctx, name)
    if record is None:
        return OpResult.ok()
    try:
        client.interrupt(record.address)
    except HcRpcError as err:
        return _answer(_refused(err))
    except HcError as err:
        # Never retried: a second Ctrl-C can end the program.
        return _answer(_lost("the interrupt", err))
    return OpResult.ok()


def op_clear_scrollback(ctx: OpContext) -> OpResult:
    # hc keeps no scrollback a client can clear: delivered (a no-op) or gone.
    _target(ctx, session_arg(ctx.request))
    return OpResult.ok()
