"""What runtime ``herdr-core`` declares in its handshake.

v2-ready (``observe.v1`` with ``report-attachment``), ``report-activity``,
``city-scoped`` (each city key has its own core), ``conformance-faults``,
``server-lifecycle`` (``server-stop`` ends the city's core and sessions),
``carrier.ops`` (gc drives the box only through the pack's own ``nudge``,
``peek``, ``send-keys``, ``interrupt`` and ``clear-scrollback``),
``idle-boundary`` (``peek`` shows the agent's screen, and ``set-meta`` /
``get-meta`` keep its ready prompt) and ``input-outcome`` (the driving ops'
typed answers), locality ``local``. A token is declared only together with
the ops that implement it and the tests that prove them. ``proc.exec``,
``proc.provision`` and ``input-fence`` never are: under ``proc.exec`` gc
would drive the box by piping tmux commands to ``exec``.

``fs.host`` is not declared yet, so gc sends the full start config and the
pack stages and runs the host work itself (``start`` does what its config
carries, and also handles a config that omits it). With ``fs.host`` gc
would scan the process table for this pack and, before a session starts
again, end every untracked root carrying its ``GC_SESSION_ID``: it reads
each pane of a tmux server founded inside a box (possibly the user's
default server) as such a root. The token waits until gc fences
tmux-parented processes in that scan.

Kept apart from the op table so the ``protocol`` op loads no backend code.
"""

from __future__ import annotations

from typing import Final

from .rpp.wire import Handshake

HANDSHAKE: Final = Handshake(
    capabilities=(
        "observe.v1",
        "report-attachment",
        "report-activity",
        "city-scoped",
        "conformance-faults",
        "server-lifecycle",
        "carrier.ops",
        "idle-boundary",
        "input-outcome",
    ),
    locality="local",
)
