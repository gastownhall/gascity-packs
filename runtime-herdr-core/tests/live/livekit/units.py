"""systemd unit names read from cgroup paths, and the one unit kill (K2) the
harness performs: on an ``hc-hold-*`` unit it found from a holder of its own
core, by that exact name, never by a pattern."""

from __future__ import annotations

import re
from typing import Final, List, Optional

_UNIT: Final = re.compile(r"[A-Za-z0-9:_.\\@-]+\.(service|scope)")
_HOLDER_UNIT: Final = re.compile(r"hc-hold-[A-Za-z0-9_.@-]+\.(service|scope)")
_SUFFIX: Final = re.compile(r"[A-Za-z0-9_-]+")

INFRA_SLICE: Final = "gascity-infra.slice"
AGENT_SLICE: Final = "gascity-agents.slice"


def unit_of(cgroup: str) -> Optional[str]:
    """The innermost ``.service`` or ``.scope`` on a cgroup path."""
    for part in reversed(cgroup.split("/")):
        if _UNIT.fullmatch(part):
            return part
    return None


def in_slice(cgroup: str, slice_name: str) -> bool:
    """Whether a cgroup path runs under ``slice_name``."""
    return slice_name in cgroup.split("/")


def is_holder_unit(unit: str) -> bool:
    """An hc holder's transient unit (``hc-hold-*``)."""
    return _HOLDER_UNIT.fullmatch(unit) is not None


def k2_argv(unit: str) -> List[str]:
    """The cgroup-wide SIGKILL of one holder unit; ValueError for any other name."""
    if not is_holder_unit(unit):
        raise ValueError(f"refusing to kill {unit!r}: not one hc holder unit")
    return ["systemctl", "--user", "kill", "--kill-whom=all", "--signal=SIGKILL", "--", unit]


def infra_unit(run_id: str, label: str) -> str:
    """The name the harness gives a stand-in infrastructure scope it creates."""
    if not _SUFFIX.fullmatch(run_id) or not _SUFFIX.fullmatch(label):
        raise ValueError(f"not a unit-name fragment: {run_id!r} / {label!r}")
    return f"gc-hc-live-{run_id}-{label}.scope"
