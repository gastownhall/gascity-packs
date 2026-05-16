"""bd hook target: append failure record to state.json on bead failure.

Registered against `on:bead.failed --label pack:magi`. Reads the bead
via bd_show only — zero bd writes (per code-review F6/D6). The failure
record is appended to state.json's `failures: []` list.
"""

from __future__ import annotations

import os
import sys

from magi_common import attach_file_log
from magi_common import bd_show
from magi_common import log_event
from magi_common import log_path
from magi_common import now_utc_iso
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import redact_secrets
from magi_common import write_state


def _resolve_bead_id() -> str | None:
    raw = os.environ.get("BD_BEAD_ID") or os.environ.get("MAGI_BEAD_ID")
    if raw: return raw
    if len(sys.argv) >= 2: return sys.argv[1]
    return None


def _failure_record(bead_id: str, bead: dict[str, object] | None) -> dict[str, object]:
    title = ""
    labels: list[str] = []
    if bead is not None:
        t = bead.get("title")
        if isinstance(t, str): title = t
        labels_raw = bead.get("labels")
        if isinstance(labels_raw, list):
            labels = [str(item) for item in labels_raw if isinstance(item, str)]
    return {
        "bead_id": bead_id,
        "title": title,
        "labels": labels,
        "recorded_at": now_utc_iso()
    }


def main() -> int:
    """Entry point for hook_on_failure."""
    os.environ["MAGI_HOOK_REENTRANT"] = "1"
    verb_log = log_path("hook-on-failure", "bd")
    attach_file_log("hook-on-failure", verb_log)
    reconcile_orphans("hook-on-failure")

    bead_id = _resolve_bead_id()
    if not bead_id:
        log_event("hook-on-failure", "no_bead_id received; exiting 0")
        return 0
    bead = bd_show(bead_id, verb="hook-on-failure")
    record = _failure_record(bead_id, bead)

    state = read_state()
    failures_raw = state.get("failures", [])
    failures: list[object] = list(failures_raw) if isinstance(failures_raw, list) else []
    failures.append(redact_secrets(record))
    state["failures"] = failures
    write_state(state)
    log_event("hook-on-failure", f"failure_recorded bead={bead_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
