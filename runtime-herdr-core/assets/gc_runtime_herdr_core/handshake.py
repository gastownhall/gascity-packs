"""What runtime ``herdr-core`` declares in its handshake.

v2-ready (``observe.v1`` with ``report-attachment``), ``report-activity``,
``city-scoped`` (each city key has its own core), ``conformance-faults``,
``server-lifecycle`` (``server-stop`` ends the city's core and sessions) and
``fs.host`` (boxes run on gc's host as gc's user with gc's filesystem view,
so gc stages the work dir and runs ``pre_start`` and ``session_setup`` on the
host itself and leaves them out of the start config), locality ``local``. A token is declared only together with the ops that
implement it and the tests that prove them. ``proc.exec``, ``proc.provision``
and ``input-fence`` never are: under ``proc.exec`` gc would drive the box by
piping tmux commands to ``exec``.

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
        "fs.host",
    ),
    locality="local",
)
