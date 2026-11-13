"""The driving ops: nudge, send-keys, interrupt and clear-scrollback.

Under ``carrier.ops`` these are the only way gc drives a box, and under
``input-outcome`` each answers with a typed outcome (:mod:`..rpp.outcome`):
exit 0 when the input was delivered, exit 80 with one outcome line for every
other outcome, exit 1 when the outcome is unknown.

Input goes to the box's current incarnation by its terminal address, never
by name, and only while that incarnation is intact: a kept terminal's
replacement shell is not the agent. A name whose newest record is finished
or broken, or that no record carries, is ``gone`` (no running box holds it),
exactly when ``observe`` would answer ``dead`` or ``absent``.

hc's answers map onto gc's words:

* hc refused: ``not_found``/``finished`` are ``gone``; ``blocked`` (the
  program waits on its own question) is ``pending_interaction``;
  ``unavailable`` (the terminal is starting or waits for a shell) is
  ``not_sent``; ``status_mismatch`` is ``busy``; any other kind is exit 1,
  naming it;
* the core is down: ``unavailable``; it is a version the pack does not
  drive: exit 1, "hc version unsupported";
* the request never reached hc, or reached it cut short (hc acts on no part
  of a request): ``not_sent``;
* a tmux key with no hc spelling: ``rejected``, before anything is sent.

A ``nudge`` whose request reached hc whole is delivered, like tmux's
fire-and-forget ``send-keys``: hc types a send once a person stops typing and
finishes it after the pack stops waiting, so one it still holds at the op's
deadline, or whose reply was lost, is typed later, and gc must not send it
again. It answers ``delivered_unobserved``, as does a send hc typed into a
program that reports its status but was not seen starting the turn; a
program that never reports status is plain ``delivered`` (tmux parity). The
accepted limit: a nudge hc still holds is lost if the core dies before the
person stops typing. A ``send-keys``, ``interrupt`` or ``clear-scrollback``
whose request was written but whose reply never came exits 1 (unknown): a
retried Esc or Ctrl-C can end the program.

No lock is held across a ``send``, which hc may hold for as long as a person
types, so ``observe`` keeps answering within its 4 s.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Final, List, Mapping, Optional, Sequence, Tuple, Union

from ..hc.client import HcClient
from ..hc.errors import HcError, HcGateError, HcRpcError, HcUnreachable
from ..hc.types import SendResult, Terminal
from ..rpp.ops import OpResult
from ..rpp.outcome import InputOp, InputOutcome, OutcomeWord, outcome_result
from . import activity
from .context import OpContext
from .reads import list_city, unreachable
from .records import is_intact, newest, object_of

GONE_KINDS: Final = frozenset({"not_found", "finished"})

REFUSALS: Final[Mapping[str, OutcomeWord]] = {
    "not_found": "gone",
    "finished": "gone",
    "blocked": "pending_interaction",
    "unavailable": "not_sent",
    "status_mismatch": "busy",
}
"""hc's refusal kinds as gc's words, for ``nudge``. The other ops answer the
two nudge-only words with ``not_sent``; hc refuses neither keys nor an
interrupt with them."""

REFUSAL_DETAILS: Final[Mapping[str, str]] = {
    "not_found": "the box's terminal is gone",
    "finished": "the box's program has ended",
    "blocked": "pending interaction: the agent is waiting on its own question; nothing was typed",
    "unavailable": "the terminal is not ready for input; nothing was typed",
    "status_mismatch": "the program's status did not allow it; nothing was typed",
}

VERSION_KINDS: Final = frozenset({"needs_update", "unsupported_generation", "incompatible"})

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

UNSUPPORTED_CORE: Final = "hc version unsupported: run gc doctor"


@dataclass(frozen=True)
class Unknown:
    """An answer gc reads as untyped (exit 1): the outcome is unknown, or the
    failure is no outcome gc acts on."""

    detail: str


Answer = Union[InputOutcome, Unknown]


def answer_result(ctx: OpContext, op: InputOp, answer: Answer) -> OpResult:
    """``answer`` as ``op``'s exit code and stdout."""
    if isinstance(answer, Unknown):
        return OpResult.fail(answer.detail)
    return outcome_result(op, answer, ctx.request.redactor)


def _unsent(err: HcError) -> Answer:
    """A call that failed before hc could act on it."""
    if isinstance(err, HcGateError):
        return Unknown(f"{UNSUPPORTED_CORE} ({err})")
    if isinstance(err, HcUnreachable):
        return InputOutcome("unavailable", f"cannot reach the city's core; nothing was sent: {err}")
    return InputOutcome("not_sent", f"nothing reached the core: {err}")


def _refused(op: InputOp, err: HcRpcError) -> Answer:
    """hc's definitive refusal: nothing was typed."""
    word = REFUSALS.get(err.kind)
    if word is None:
        if err.kind in VERSION_KINDS:
            return Unknown(f"{UNSUPPORTED_CORE} ({err})")
        return Unknown(f"the core refused the input ({err.kind or 'an error with no kind'}): {err}")
    if op != "nudge" and word in ("busy", "pending_interaction"):
        word = "not_sent"
    return InputOutcome(word, REFUSAL_DETAILS.get(err.kind, f"nothing was typed ({err.kind})"))


def _target(
    ctx: OpContext, name: str, *, send_reserve: Optional[float] = None
) -> Union[Tuple[HcClient, Terminal], Answer]:
    """The client and the intact incarnation to drive, or the answer when there is none."""
    if not name:
        return InputOutcome("gone", "no session name")
    client = ctx.client(send_reserve=send_reserve)
    try:
        record = newest(list_city(client, ctx, name), name)
    except HcRpcError as err:
        return Unknown(f"cannot list the city's terminals: {err}")
    except HcError as err:
        unreachable(ctx, err)
        if isinstance(err, HcGateError):
            return Unknown(f"{UNSUPPORTED_CORE} ({err})")
        return InputOutcome("unavailable", f"cannot reach the city's core; nothing was sent: {err}")
    if record is None:
        return InputOutcome("gone", "no box holds the name")
    if not is_intact(record):
        return InputOutcome("gone", "the box's program has ended")
    return client, record


def _noted(ctx: OpContext, record: Terminal) -> None:
    obj = object_of(record)
    if obj is not None:
        activity.note_input(ctx, obj)


def _sent(result: SendResult) -> InputOutcome:
    if result.started is False:
        return InputOutcome("delivered_unobserved", "the program reports its status but was not seen starting the turn")
    return InputOutcome("delivered")


def deliver(ctx: OpContext, client: HcClient, record: Terminal, text: str, *, retry_unavailable: bool = False) -> Answer:
    """Send ``text`` to ``record``.

    A send whose request reached hc whole is delivered unless hc answers
    that nothing was typed: hc finishes a send after its client stops
    waiting, so one it still holds for a person's pause, or whose reply was
    lost, is typed, and answering it as anything gc retries would make gc's
    queue send it again."""
    while True:
        try:
            result = client.send(record.address, text)
        except HcRpcError as err:
            if retry_unavailable and err.kind == "unavailable" and ctx.request.deadline.budget(1.0) > 0.5:
                ctx.request.cancel.pause(0.5)
                continue
            return _refused("nudge", err)
        except HcError as err:
            if not err.written or err.partial:
                return _unsent(err)
            _noted(ctx, record)
            return InputOutcome("delivered_unobserved", f"hc took the text, but its answer did not arrive: {err}")
        _noted(ctx, record)
        return _sent(result)


def nudge(ctx: OpContext, name: str, text: str) -> Answer:
    target = _target(ctx, name, send_reserve=NUDGE_SEND_RESERVE_S)
    if not isinstance(target, tuple):
        return target
    client, record = target
    return deliver(ctx, client, record, text)


def _written_unknown(what: str, err: HcError) -> Answer:
    """A key op's call that failed after its request may have reached hc."""
    if not err.written or err.partial:
        return _unsent(err)
    return Unknown(f"outcome unknown: {what} may have reached the program ({err})")


def send_keys(ctx: OpContext, name: str, tmux_keys: Sequence[str]) -> Answer:
    keys, bad = translate_keys(tmux_keys)
    if keys is None:
        return InputOutcome("rejected", f"tmux key {bad!r} has no herdr-core spelling; nothing was typed")
    target = _target(ctx, name)
    if not isinstance(target, tuple):
        return target
    client, record = target
    if not keys:
        return InputOutcome("delivered")
    try:
        client.keys(record.address, keys)
    except HcRpcError as err:
        return _refused("send-keys", err)
    except HcError as err:
        return _written_unknown("the keys", err)
    _noted(ctx, record)
    return InputOutcome("delivered")


def interrupt(ctx: OpContext, name: str) -> Answer:
    target = _target(ctx, name)
    if not isinstance(target, tuple):
        return target
    client, record = target
    try:
        # Whatever hc saw (stopped, exited, still working): the stop key was pressed.
        client.interrupt(record.address)
    except HcRpcError as err:
        return _refused("interrupt", err)
    except HcError as err:
        # Never retried: a second Ctrl-C can end the program.
        return _written_unknown("the interrupt", err)
    return InputOutcome("delivered")


def clear_scrollback(ctx: OpContext, name: str) -> Answer:
    """hc keeps no scrollback a client can clear: delivered (a no-op) to the
    box's intact incarnation, confirmed by its own ``terminal.get``."""
    target = _target(ctx, name)
    if not isinstance(target, tuple):
        return target
    client, record = target
    try:
        current = client.get(record.address)
    except HcRpcError as err:
        return _refused("clear-scrollback", err)
    except HcError as err:
        return _written_unknown("clearing the scrollback", err)
    if not is_intact(current):
        return InputOutcome("gone", "the box's program has ended")
    return InputOutcome("delivered")


def _name(ctx: OpContext) -> str:
    return ctx.request.args[0] if ctx.request.args else ""


def op_nudge(ctx: OpContext) -> OpResult:
    text = ctx.request.stdin.decode("utf-8", "surrogateescape")
    return answer_result(ctx, "nudge", nudge(ctx, _name(ctx), text))


def op_send_keys(ctx: OpContext) -> OpResult:
    return answer_result(ctx, "send-keys", send_keys(ctx, _name(ctx), ctx.request.args[1:]))


def op_interrupt(ctx: OpContext) -> OpResult:
    return answer_result(ctx, "interrupt", interrupt(ctx, _name(ctx)))


def op_clear_scrollback(ctx: OpContext) -> OpResult:
    return answer_result(ctx, "clear-scrollback", clear_scrollback(ctx, _name(ctx)))


__all__ = [
    "Answer",
    "Unknown",
    "deliver",
    "op_clear_scrollback",
    "op_interrupt",
    "op_nudge",
    "op_send_keys",
    "translate_key",
    "translate_keys",
]

