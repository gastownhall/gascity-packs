"""Typed input outcomes: the ``input-outcome`` token's answers (gascity
``docs/reference/exec-session-provider.md``, "Typed input outcomes").

The four driving ops answer with their exit code, refined by at most one
line of stdout:

* exit 0: the input was delivered. Nothing is printed, except that a
  ``nudge`` may say ``delivered_unobserved`` (delivered, but the turn start
  was not seen) in one line;
* exit 80 (:attr:`~.exitcodes.ExitCode.INPUT_OUTCOME`): exactly one line
  ``{"outcome":"<word>","detail":"..."}`` naming a non-success word;
* exit 1 (an ordinary failure): the outcome is unknown.

A non-success word is never printed on exit 0, so a gc that does not read
the token sees exit 0 only for a delivery and an ordinary failure for exit
80: the answer is the same for every gc. Each word is the projection of one
outcome gc already acts on; this module adds no meaning of its own.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Dict, Final, FrozenSet, Literal, Tuple, get_args

from .exitcodes import ExitCode
from .jsonval import dumps
from .ops import OpResult
from .redact import Redactor

InputOp = Literal["nudge", "send-keys", "interrupt", "clear-scrollback"]
"""The driving ops ``input-outcome`` types."""

OutcomeWord = Literal[
    "delivered",
    "delivered_unobserved",
    "unconfirmed",
    "not_sent",
    "rejected",
    "busy",
    "pending_interaction",
    "unavailable",
    "gone",
]
"""gc's outcome words (gascity ``runtime.InputOutcome``)."""

INPUT_OPS: Final[Tuple[InputOp, ...]] = get_args(InputOp)
OUTCOME_WORDS: Final[Tuple[OutcomeWord, ...]] = get_args(OutcomeWord)
SUCCESS_WORDS: Final[FrozenSet[OutcomeWord]] = frozenset({"delivered", "delivered_unobserved"})
NON_SUCCESS_WORDS: Final[FrozenSet[OutcomeWord]] = frozenset(OUTCOME_WORDS) - SUCCESS_WORDS
NUDGE_ONLY_WORDS: Final[FrozenSet[OutcomeWord]] = frozenset(
    {"delivered_unobserved", "unconfirmed", "busy", "pending_interaction"}
)
"""Words only a ``nudge`` may answer; the other three ops answer the rest."""

DETAIL_CAP: Final = 1 << 10
"""The documented bound, in UTF-8 bytes, on an outcome line's detail."""


def allowed(op: InputOp, word: OutcomeWord) -> bool:
    """Whether ``op`` may answer ``word``."""
    return op == "nudge" or word not in NUDGE_ONLY_WORDS


@dataclass(frozen=True)
class InputOutcome:
    """One driving op's typed outcome and why (a short, secret-free reason)."""

    word: OutcomeWord
    detail: str = ""

    @property
    def delivered(self) -> bool:
        return self.word in SUCCESS_WORDS


def clean_detail(detail: str, redactor: Redactor) -> str:
    """``detail`` safe for one outcome line: redacted, control characters as
    spaces, undecodable characters dropped, and cut at :data:`DETAIL_CAP`
    UTF-8 bytes on a character boundary."""
    out = []
    size = 0
    for ch in redactor.redact(detail):
        if unicodedata.category(ch) == "Cs":
            continue  # a byte surrogateescape kept: no character to show
        if unicodedata.category(ch) == "Cc":
            ch = " "
        width = len(ch.encode("utf-8"))
        if size + width > DETAIL_CAP:
            break
        out.append(ch)
        size += width
    return "".join(out).strip()


def _line(word: OutcomeWord, detail: str) -> bytes:
    doc: Dict[str, str] = {"outcome": word}
    if detail:
        doc["detail"] = detail
    return (dumps(doc) + "\n").encode("ascii")


def outcome_result(op: InputOp, outcome: InputOutcome, redactor: Redactor) -> OpResult:
    """``outcome`` as ``op``'s answer: exit 0 for a delivery, exit 80 and one
    line for anything else. A word ``op`` may not answer is a pack bug
    (ValueError), never a line gc would read as malformed."""
    if not allowed(op, outcome.word):
        raise ValueError(f"{op} may not answer {outcome.word!r}")
    detail = clean_detail(outcome.detail, redactor)
    if outcome.word == "delivered":
        return OpResult.ok()
    if outcome.word == "delivered_unobserved":
        return OpResult.ok(_line(outcome.word, detail))
    message = outcome.word + (f": {detail}" if detail else "")
    return OpResult(ExitCode.INPUT_OUTCOME, _line(outcome.word, detail), message)
