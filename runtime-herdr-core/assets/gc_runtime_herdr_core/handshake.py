"""What runtime ``herdr-core`` declares in its handshake.

v2-ready (``observe.v1`` with ``report-attachment``), ``report-activity``,
``city-scoped`` (each city key has its own core), ``conformance-faults``,
``server-lifecycle`` (``server-stop`` ends the city's core and sessions),
``carrier.ops`` (gc drives the box only through the pack's own ``nudge``,
``peek``, ``send-keys``, ``interrupt`` and ``clear-scrollback``),
``idle-boundary`` (``peek`` shows the agent's screen, and ``set-meta`` /
``get-meta`` keep its ready prompt), ``input-outcome`` (the driving ops'
typed answers) and ``fs.host`` (boxes run on gc's host as gc's user, so gc
stages the work dir, runs ``pre_start`` and ``session_setup`` on the host and
leaves them out of the start config), locality ``local``, which ``fs.host``
requires. A token is declared only together with the ops that implement it
and the tests that prove them. ``proc.exec``, ``proc.provision`` and
``input-fence`` never are: under ``proc.exec`` gc would drive the box by
piping tmux commands to ``exec``. gc's process-table cleanup never treats a
tmux server or client carrying a ``GC_SESSION_ID`` (one founded inside a
box), or anything under it, as a session root, unless the pack declares
``proc.exec`` without ``carrier.ops`` (gc then reads its agent as running
in the box's tmux). That fence needs a gc that contains
gastownhall/gascity#9129: one built from gastownhall/gascity#9032 up to it
honors ``fs.host`` without the fence (see the README's Status).

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
        "fs.host",
    ),
    locality="local",
)
