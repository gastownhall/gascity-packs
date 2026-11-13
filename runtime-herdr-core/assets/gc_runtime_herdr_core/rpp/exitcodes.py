"""RPP v0 exit codes (gascity ``docs/reference/exec-session-provider.md`` "Exit Codes")."""

from __future__ import annotations

import enum


class ExitCode(enum.IntEnum):
    """The exit codes an op may end with, and what gc reads from each."""

    OK = 0
    """An answer, including "no such session" where the op allows it."""

    FAIL = 1
    """Untyped failure; gc embeds stderr verbatim, so it must hold no secrets."""

    UNKNOWN_OP = 2
    """Unknown operation: gc's forward-compatibility no-op, except for start
    and ops the handshake declares, where it is a failure."""

    NO_SCREEN = 66
    """peek, from a v2-ready script: nothing holds a screen for the name."""

    FRESH_COLLISION = 73
    """A fresh_only start refusing a name some box holds."""

    TEMPFAIL = 75
    """start only: the backend is at capacity; gc retries."""

    INPUT_OUTCOME = 80
    """nudge, send-keys, interrupt and clear-scrollback only, from a script
    declaring ``input-outcome``: the input was not delivered, and stdout
    carries exactly one outcome line naming why (:mod:`.outcome`)."""
