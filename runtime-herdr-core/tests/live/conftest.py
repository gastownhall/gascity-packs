"""The live tier: the pack against a pinned, sha256-verified herdr-core.

Collected only with ``GC_HC_LIVE=1``; otherwise every test here skips. With
it, the run stops before anything is created unless the host is a GitHub
Actions runner or declared throwaway (:mod:`livekit.guard`). It needs:

* ``GC_HC_LIVE_BIN``: the pinned hc (``fetch_hc.py`` prints it);
* ``GC_HC_LIVE_LANE``: ``plain`` (a scratch runtime directory: no systemd
  placement) or ``systemd`` (the user's runtime directory under a running
  user manager: hc places its core and holders in ``hc-serve-*`` and
  ``hc-hold-*`` units). A systemd lane without a user manager fails the
  whole session loudly; it never passes as a plain run;
* ``GC_HC_LIVE_GC_BIN``: gc built at the pinned gascity commit (conformance).

Every test gets its own scratch root and must leave nothing behind
(:mod:`livekit.scratch`). Results and measurements go to the job summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parents[1]
for _entry in (PACK_ROOT / "assets", PACK_ROOT / "tests", HERE):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from livekit.plugin import *  # noqa: E402,F401,F403
