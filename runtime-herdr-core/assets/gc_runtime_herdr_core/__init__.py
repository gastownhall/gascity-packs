"""runtime-herdr-core: a Gas City runtime backed by herdr-core (hc).

gc drives it through the Runtime Provider Protocol (RPP v0): one process per
op, ``gc-runtime-herdr-core <op> <args...>``. The package is layered:

* :mod:`.rpp` is the provider-neutral RPP kit: wire shapes, exit codes, the
  per-op runner, cancellation and deadlines, redaction, private state and
  locks. It knows nothing about herdr-core.
* :mod:`.hc` is the herdr-core client: deterministic discovery of a city's
  core, the version gate, and typed JSON-RPC methods.

Everything is standard library only and runs on Python 3.9 or later.
"""

from __future__ import annotations

from typing import Final

PACK_NAME: Final = "runtime-herdr-core"
PACK_VERSION: Final = "0.1.0"
RUNTIME_NAME: Final = "herdr-core"
