"""The herdr-core (hc) client.

Where a city's core lives (:mod:`.paths`), the version gate (:mod:`.version`),
typed records and their parsers (:mod:`.types`, :mod:`.parse`), the failures
(:mod:`.errors`) and the JSON-RPC client itself (:mod:`.client`). Facts about
hc come from its OpenRPC schema at the pinned tag (``tests/fakehc``).
"""

from __future__ import annotations
