"""Where the live tier may run: a GitHub Actions runner, or a host its
operator names as throwaway. Never anywhere else.

A real herdr-core's holder-loss sweep kills every process carrying a
terminal's ``HC_SCOPE`` and all their descendants, and the holder-crash suite
SIGKILLs holders and cgroups on purpose. A maintainer's host runs other
cities, a Herdr app and personal terminals, so the harness refuses to start
there: it needs ``GITHUB_ACTIONS=true`` (set by every Actions runner), or
:data:`THROWAWAY_ENV` set to the exact value of ``$HOME`` (an opt-in that
cannot be satisfied by an exported ``1`` or by ``CI=true``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

LIVE_ENV: Final = "GC_HC_LIVE"
"""``1`` asks for the live suites; without it they skip."""
THROWAWAY_ENV: Final = "GC_HC_LIVE_THROWAWAY_HOST"
"""Set to this host's ``$HOME`` to declare the host disposable."""
HC_BIN_ENV: Final = "GC_HC_LIVE_BIN"
"""The pinned, verified hc binary the suites drive (``fetch_hc.py`` prints it)."""
GC_BIN_ENV: Final = "GC_HC_LIVE_GC_BIN"
"""The gc binary the conformance suite runs (built at the pinned gascity commit)."""
LANE_ENV: Final = "GC_HC_LIVE_LANE"
"""``plain`` or ``systemd``: where the core is placed."""
REFUSED_EXIT: Final = 2


class Refused(Exception):
    """This host may not run the live tier."""


@dataclass(frozen=True)
class Clearance:
    """Proof that :func:`clearance` accepted the host; scratch roots need one."""

    why: str


def live_requested(environ: Mapping[str, str]) -> bool:
    """Whether the live suites were asked for (``GC_HC_LIVE=1``)."""
    return environ.get(LIVE_ENV, "") == "1"


def clearance(environ: Mapping[str, str]) -> Clearance:
    """A :class:`Clearance` for a runner or a declared throwaway host;
    :class:`Refused` for every other host."""
    if environ.get("GITHUB_ACTIONS", "") == "true":
        return Clearance(why="GitHub Actions runner")
    home = environ.get("HOME", "")
    if home and environ.get(THROWAWAY_ENV, "") == home:
        return Clearance(why=f"throwaway host ({THROWAWAY_ENV} names $HOME)")
    raise Refused(
        "the herdr-core live tier refuses to run on this host: it kills hc holders and cgroups on purpose. "
        f"It runs only where GITHUB_ACTIONS=true, or where {THROWAWAY_ENV} equals $HOME on a disposable machine."
    )
