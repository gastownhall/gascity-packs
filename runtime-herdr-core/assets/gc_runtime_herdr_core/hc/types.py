"""Typed hc records (hc.openrpc.json at the pinned tag).

Only the fields the pack reads are kept; :mod:`.parse` ignores the rest, so a
core whose records grow ("the API only grows") changes nothing here. Status
words, reasons and states are kept as the strings hc sent, because its schema
types them as free strings: a word added in a patch release must not fail a
whole listing. The closed vocabularies are read through ``Literal``-typed
accessors (:attr:`ProgramStatus.word`, :attr:`Terminal.end_reason`) that give
None for a word the pack does not know. OSC 7501 status text (``title``,
``msg``) is dropped at the edge: gc's ``runtime.ProgramStatus`` carries no
text either (gascity ``internal/runtime/program_status.go``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, FrozenSet, Literal, Mapping, Optional, Tuple, cast, get_args

StatusWord = Literal["idle", "working", "done", "blocked", "error"]
"""The words hc's OSC 7501 parser keeps (``clear`` removes a record)."""

EndReason = Literal[
    "exited",
    "killed",
    "server_stop",
    "host_shutdown",
    "holder_lost",
    "stopped_by_restart",
    "signaled",
    "spawn_pending",
]
"""Why a program ended or is pending (Terminal ``reason``, hc v0.1.19)."""

_STATUS_WORDS: Final[FrozenSet[str]] = frozenset(get_args(StatusWord))
_END_REASONS: Final[FrozenSet[str]] = frozenset(get_args(EndReason))


@dataclass(frozen=True)
class CoreInfo:
    id: str
    """Permanent random id of the core's state; reset only when state is wiped."""
    name: str


@dataclass(frozen=True)
class HelloResult:
    generation: int
    version: str
    core: CoreInfo
    framed: bool
    methods: Tuple[str, ...]
    features: Tuple[str, ...]


@dataclass(frozen=True)
class HolderInfo:
    pid: int
    instance: str
    current: bool
    terminals: int


@dataclass(frozen=True)
class StatusResult:
    """``server.status``: the core process and its holders."""

    core: CoreInfo
    version: str
    pid: int
    uptime_ms: int
    holder: Optional[HolderInfo]
    holders: Tuple[HolderInfo, ...]
    live: int
    finished: int
    installed_by: Optional[str]


@dataclass(frozen=True)
class StopResult:
    stopped: bool


@dataclass(frozen=True)
class ProgramStatus:
    """One OSC 7501 record, without its text."""

    state: str
    """idle, working, done, blocked or error: the program's own word."""
    kind: Optional[str]
    """permission, question or auth (blocked only)."""
    app: str
    progress: Optional[int]

    @property
    def word(self) -> Optional[StatusWord]:
        """``state`` as a known status word; None for a word this pack does not know."""
        return cast(StatusWord, self.state) if self.state in _STATUS_WORDS else None


@dataclass(frozen=True)
class Foreground:
    """What runs in a terminal now (polled by hc about twice a second)."""

    pid: int
    name: str
    argv: Tuple[str, ...]
    cwd: str


@dataclass(frozen=True)
class Terminal:
    """A terminal record: live, or finished until pruned (24 h or 500 records)."""

    address: str
    """``tN``: this terminal forever on this core, never reused."""
    labels: Mapping[str, str]
    argv: Tuple[str, ...]
    cwd: str
    state: str
    created_ms: int
    screen: str
    cols: int
    rows: int
    name: Optional[str]
    pid: Optional[int]
    foreground: Optional[Foreground]
    reason: Optional[str]
    exit_code: Optional[int]
    signal: Optional[int]
    finished_ms: Optional[int]
    keep: bool
    parent: Optional[str]
    status: Optional[ProgramStatus]
    records: Mapping[str, ProgramStatus]
    reported: bool
    """Whether the program ever sent an OSC 7501 report."""
    status_ms: Optional[int]
    turn: int
    """Goes up each time the root status leaves ``working``."""

    @property
    def is_live(self) -> bool:
        return self.state == "live"

    @property
    def is_finished(self) -> bool:
        return self.state == "finished"

    @property
    def end_reason(self) -> Optional[EndReason]:
        """``reason`` as a known word; None when absent or a word this pack does not know."""
        return cast(EndReason, self.reason) if self.reason in _END_REASONS else None


@dataclass(frozen=True)
class ListResult:
    terminals: Tuple[Terminal, ...]
    hidden_finished: int


@dataclass(frozen=True)
class SendResult:
    turn: int
    status: Optional[str]
    """The program's status word when the text went in (None: it never said)."""
    started: Optional[bool]
    """Whether it went ``working`` within hc's window; None when it never reports status."""


@dataclass(frozen=True)
class KeysResult:
    turn: int
    status: Optional[str]


@dataclass(frozen=True)
class InterruptResult:
    outcome: str
    """stopped, exited, still_working or unknown."""
    key: str


@dataclass(frozen=True)
class ReadResult:
    text: str
    how: str
    complete: bool
    why: Optional[str]


@dataclass(frozen=True)
class RemoveResult:
    removed: str


@dataclass(frozen=True)
class RunSpec:
    """What the pack asks ``terminal.run`` for. The client adds the fixed
    parameters (``keep: false``, ``no_parent: true``, ``no_notify: true``)
    and never sends ``caller`` or ``parent``: a terminal with a parent ends
    with its parent's program, and hc types notes about it into the parent
    (hc.openrpc.json ``terminal.run``: ``outlive_parent``, ``no_notify``)."""

    argv: Tuple[str, ...]
    cwd: str
    env: Mapping[str, str]
    labels: Mapping[str, str]
    name: str
