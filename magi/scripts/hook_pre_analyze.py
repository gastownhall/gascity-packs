"""bd hook target: probe LM Studio before an analyze bead claims.

Registered against `on:bead.opened --label verb:analyze`. Reads the
bead via bd_show only. Probes ${LM_STUDIO_URL:-http://localhost:1234}
via urllib with a 3s connect timeout and 10s overall timeout. Exits 0
when LM Studio responds with a 2xx; exits 2 otherwise.
"""

from __future__ import annotations

import os
import socket
import sys
import urllib.error
import urllib.request

from magi_common import attach_file_log
from magi_common import bd_show
from magi_common import log_event
from magi_common import log_path
from magi_common import reconcile_orphans


_DEFAULT_URL: str = "http://localhost:1234"
_PROBE_TIMEOUT_SECONDS: float = 10.0
_PROBE_CONNECT_TIMEOUT_SECONDS: float = 3.0


def _resolve_bead_id() -> str | None:
    raw = os.environ.get("BD_BEAD_ID") or os.environ.get("MAGI_BEAD_ID")
    if raw: return raw
    if len(sys.argv) >= 2: return sys.argv[1]
    return None


def _probe(url: str) -> int:
    target = url.rstrip("/") + "/v1/models"
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_PROBE_CONNECT_TIMEOUT_SECONDS)
    try:
        request = urllib.request.Request(target, method="GET")
        with urllib.request.urlopen(request, timeout=_PROBE_TIMEOUT_SECONDS) as response:
            status = response.status
            if 200 <= status < 300:
                log_event("hook-pre-analyze", f"lm_studio_ok status={status} url={target}")
                return 0
            log_event("hook-pre-analyze", f"lm_studio_bad_status status={status} url={target}")
            return 2
    except urllib.error.URLError as exc:
        log_event("hook-pre-analyze", f"lm_studio_unreachable url={target} err={exc.reason}")
        return 2
    except socket.timeout:
        log_event("hook-pre-analyze", f"lm_studio_timeout url={target}")
        return 2
    except OSError as exc:
        log_event("hook-pre-analyze", f"lm_studio_oserror url={target} err={exc}")
        return 2
    finally:
        socket.setdefaulttimeout(original_timeout)


def main() -> int:
    """Entry point for hook_pre_analyze."""
    os.environ["MAGI_HOOK_REENTRANT"] = "1"
    verb_log = log_path("hook-pre-analyze", "bd")
    attach_file_log("hook-pre-analyze", verb_log)
    reconcile_orphans("hook-pre-analyze")

    bead_id = _resolve_bead_id()
    if bead_id:
        bd_show(bead_id, verb="hook-pre-analyze")  # read-only sanity probe
    url = os.environ.get("LM_STUDIO_URL", _DEFAULT_URL)
    return _probe(url)


if __name__ == "__main__":
    sys.exit(main())
