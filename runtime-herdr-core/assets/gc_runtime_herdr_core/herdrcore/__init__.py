"""Runtime semantics: how gc's RPP ops map onto a city's herdr-core.

:mod:`.context` resolves an op's city, core and private state;
:mod:`.core` starts and checks the city's core; :mod:`.records` reads hc's
terminal records as gc boxes; :mod:`.ops_table` is the op table and the
handshake. Nothing here reads the process environment: every op works from
its :class:`~..rpp.ops.OpRequest`.
"""

from __future__ import annotations
