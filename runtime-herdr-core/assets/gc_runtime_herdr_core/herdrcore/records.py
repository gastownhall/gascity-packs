"""hc terminal records read as gc boxes.

A gc session's box is the newest terminal record carrying its ``gc.session``
label (newest by ``created_ms``, then by address). An incarnation is
*intact* while its record is live and the program the pack started still
runs in it: a pid, equal to the ``gc.pid`` label once ``run`` returned, and
no reason marking a lost holder, a core restart that found no holder, a
death by signal of a kept terminal, or a spawn still pending. Anything else
that is live is *broken*: a kept terminal running a replacement shell, or
waiting for one. A broken or finished incarnation is a dead box.

The box's object is ``{"id": tN, "created": RFC 3339 of created_ms}``: an
address is never reused on a core, and ``created`` tells a wiped state
directory's reused address apart.
"""

from __future__ import annotations

from typing import Dict, Final, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from ..hc.types import Terminal
from ..rpp.wire import BoxObject, rfc3339_ms
from .naming import LABEL_OBJ, LABEL_PID, LABEL_SESSION

BROKEN_REASONS: Final[FrozenSet[str]] = frozenset({"holder_lost", "stopped_by_restart", "signaled", "spawn_pending"})


def _address_number(address: str) -> int:
    digits = address[1:] if address.startswith("t") else ""
    return int(digits) if digits.isdigit() else -1


def _age_key(terminal: Terminal) -> Tuple[int, int]:
    return (terminal.created_ms, _address_number(terminal.address))


def newest_first(terminals: Sequence[Terminal]) -> List[Terminal]:
    """``terminals`` newest first."""
    return sorted(terminals, key=_age_key, reverse=True)


def for_session(terminals: Sequence[Terminal], name: str) -> List[Terminal]:
    """The records carrying gc name ``name``, newest first."""
    return newest_first([t for t in terminals if t.labels.get(LABEL_SESSION) == name])


def newest(terminals: Sequence[Terminal], name: str) -> Optional[Terminal]:
    found = for_session(terminals, name)
    return found[0] if found else None


def is_intact(terminal: Terminal) -> bool:
    """Whether the incarnation the pack started still runs in the record."""
    if not terminal.is_live or terminal.pid is None or terminal.reason in BROKEN_REASONS:
        return False
    recorded = terminal.labels.get(LABEL_PID)
    if recorded is None:
        # run returned but its pid label is not written yet; a kept
        # terminal may already run a replacement shell.
        return not terminal.keep
    return recorded == str(terminal.pid)


def is_broken(terminal: Terminal) -> bool:
    """Live, but not running the incarnation the pack started."""
    return terminal.is_live and not is_intact(terminal)


def box_object(terminal: Terminal) -> BoxObject:
    return BoxObject(id=terminal.address, created=rfc3339_ms(max(0, terminal.created_ms)))


def object_of(terminal: Terminal) -> Optional[str]:
    """The record's ``gc.obj`` nonce, when it carries one."""
    return terminal.labels.get(LABEL_OBJ)


def group_by_session(terminals: Sequence[Terminal]) -> Mapping[str, List[Terminal]]:
    """gc name to its records, newest first."""
    groups: Dict[str, List[Terminal]] = {}
    for terminal in terminals:
        name = terminal.labels.get(LABEL_SESSION)
        if name is not None:
            groups.setdefault(name, []).append(terminal)
    return {name: newest_first(found) for name, found in groups.items()}
