"""bd hook target: refresh state.json after an install bead closes.

Registered against `on:bead.closed --label pack:magi:install` with the
filters `NOT role:uninstall-closure AND NOT role:hook-trigger`. This
script reads the bead via bd_show only and never calls a bd write
helper. Failure to read is logged and the hook exits 0 — the verb
that triggered this should not be punished for an unreadable bead.
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
from magi_common import write_state


def _resolve_bead_id() -> str | None:
    raw = os.environ.get("BD_BEAD_ID") or os.environ.get("MAGI_BEAD_ID")
    if raw: return raw
    if len(sys.argv) >= 2: return sys.argv[1]
    return None


def _is_uninstall_closure(bead: dict[str, object]) -> bool:
    labels = bead.get("labels")
    if not isinstance(labels, list): return False
    return any(
        isinstance(label, str) and label in {"role:uninstall-closure", "role:hook-trigger"}
        for label in labels
    )


def _extract_target(bead: dict[str, object]) -> str | None:
    labels = bead.get("labels")
    if not isinstance(labels, list): return None
    for label in labels:
        if isinstance(label, str) and label.startswith("target:"): return label[len("target:"):]
    return None


def main() -> int:
    """Entry point for hook_post_install."""
    # Setting MAGI_HOOK_REENTRANT prevents any accidental bd write inside a
    # subprocess this hook may invoke from re-firing the same hook.
    os.environ["MAGI_HOOK_REENTRANT"] = "1"
    verb_log = log_path("hook-post-install", "bd")
    attach_file_log("hook-post-install", verb_log)
    reconcile_orphans("hook-post-install")

    bead_id = _resolve_bead_id()
    if not bead_id:
        log_event("hook-post-install", "no_bead_id received; exiting 0")
        return 0
    bead = bd_show(bead_id, verb="hook-post-install")
    if bead is None:
        log_event("hook-post-install", f"bd_show_failed bead={bead_id}; exiting 0")
        return 0
    if _is_uninstall_closure(bead):
        log_event("hook-post-install", f"skipped_uninstall_or_hook bead={bead_id}")
        return 0

    target = _extract_target(bead)
    state = read_state()
    installs_raw = state.get("installs", {})
    installs: dict[str, object] = dict(installs_raw) if isinstance(installs_raw, dict) else {}
    entry_raw = installs.get(target, {}) if target else {}
    entry: dict[str, object] = dict(entry_raw) if isinstance(entry_raw, dict) else {}
    entry["last_hook_refresh"] = now_utc_iso()
    entry["last_hook_bead"] = bead_id
    if target:
        installs[target] = entry
        state["installs"] = installs
        write_state(state)
        log_event("hook-post-install", f"state_refreshed target={target} bead={bead_id}")
    else:
        log_event("hook-post-install", f"no_target_label bead={bead_id} state unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
