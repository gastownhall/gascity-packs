"""hc client failures.

Every failure says whether the request may have reached the core
(:attr:`HcError.written`), because the outcome of a driving op hangs on it:
when nothing was written nothing can have been typed, but once a request may
have reached hc, hc may still act on it. A ``send`` is typed only once nobody
has typed for about 3 s (hc.openrpc.json ``terminal.send``), however long that
takes, so a send whose reply was lost may still be typed later.

A request cut short (:attr:`HcError.partial`) was written, but hc acts on
none of it: hc parses a request only as a whole line, and no prefix of one
parses. A request short only of its newline is whole, as hc runs the last
line it reads when the connection ends (``crates/herdr-core/src/server.rs``,
``connection``).
"""

from __future__ import annotations

from typing import Final, FrozenSet, Literal, Optional, cast, get_args

from ..rpp.cancel import Cancelled

ErrorKind = Literal[
    "invalid_params",
    "name_taken",
    "spawn_failed",
    "unavailable",
    "invalid_template",
    "not_found",
    "machine_unknown",
    "config",
    "live",
    "finished",
    "needs_framed",
    "blocked",
    "status_mismatch",
    "needs_target",
    "not_text",
    "io",
    "edit_failed",
    "conflict",
    "internal",
    "needs_update",
    "unsupported_generation",
    "already_added",
    "unreachable",
    "hc_missing",
    "incompatible",
]
"""The ``data.kind`` values in hc's schema at the pinned tag (the stable
discriminator of an hc error)."""

KNOWN_ERROR_KINDS: Final[FrozenSet[str]] = frozenset(get_args(ErrorKind))


class HcError(Exception):
    """A call to the core failed."""

    def __init__(self, method: str, message: str, *, written: bool, partial: bool = False) -> None:
        Exception.__init__(self, f"{method}: {message}")
        self.method = method
        self.written = written  # whether the request may have reached the core
        self.partial = partial  # whether only part of it did, which hc never acts on


class HcUnreachable(HcError):
    """No core answered the socket (missing, refused, or connect timed out); nothing was written."""

    def __init__(self, method: str, message: str) -> None:
        HcError.__init__(self, method, message, written=False)


class HcTimeout(HcError):
    """The call's budget ran out, before writing (no time left) or while waiting for the reply."""


class HcConnectionLost(HcError):
    """The core closed or reset the connection before its reply."""


class HcProtocolError(HcError):
    """The core's reply was not a well-formed answer to the request."""


class HcGateError(HcError):
    """The core is a protocol generation or version this pack does not drive."""

    def __init__(self, method: str, message: str) -> None:
        HcError.__init__(self, method, message, written=False)


class HcRpcError(HcError):
    """The core answered with a JSON-RPC error."""

    def __init__(self, method: str, *, kind: str, code: int, message: str, hint: str) -> None:
        HcError.__init__(self, method, f"{kind or 'error'}: {message}", written=True)
        self.kind = kind
        self.code = code
        self.hint = hint

    @property
    def known_kind(self) -> Optional[ErrorKind]:
        """The kind, when it is one the pinned schema names."""
        return cast(ErrorKind, self.kind) if self.kind in KNOWN_ERROR_KINDS else None


class HcCancelled(HcError, Cancelled):
    """The op was canceled while the call was in flight."""

    def __init__(self, method: str, reason: str, *, written: bool, partial: bool = False) -> None:
        HcError.__init__(self, method, f"canceled ({reason})", written=written, partial=partial)
        self.reason = reason
