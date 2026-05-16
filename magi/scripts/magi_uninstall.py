"""Uninstaller for the magi pack.

Default behavior removes only the state.json entry for the chosen
target. `--really-purge --yes` additionally removes the deployed target
home after listing what will be removed. Closes any open install beads
with the `role:uninstall-closure` label so hook_post_install does not
re-mark the install as live.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from magi_common import CLIError
from magi_common import attach_file_log
from magi_common import bd_close
from magi_common import bd_create
from magi_common import bd_list_pack
from magi_common import bd_update
from magi_common import city_root
from magi_common import clear_inflight_sentinel
from magi_common import log_event
from magi_common import log_path
from magi_common import now_utc_iso
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import write_inflight_sentinel
from magi_common import write_state


_TARGET_CHOICES: tuple[str, ...] = ("claude", "codex", "gemini", "openai", "all")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-uninstall", allow_abbrev=False)
    parser.add_argument("--target", choices=_TARGET_CHOICES, required=True)
    parser.add_argument("--yes", action="store_true", help="Required for any mutation.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed; no mutations.")
    parser.add_argument(
        "--really-purge",
        action="store_true",
        help="Remove the deployed target home from disk. Requires --yes."
    )
    return parser


def _close_open_install_beads(target: str) -> int:
    closed = 0
    open_beads = bd_list_pack(
        status="open",
        extra_labels=[f"verb:install", f"target:{target}"],
        verb="uninstall"
    )
    for bead in open_beads:
        bead_id = bead.get("id")
        if not isinstance(bead_id, str): continue
        if bd_close(
            bead_id,
            outcome="interrupted",
            labels={"role": "uninstall-closure"},
            verb="uninstall"
        ):
            closed += 1
            log_event("uninstall", f"closed_open_install bead={bead_id} target={target}")
    return closed


def _purge_target_home(deploy_home: Path, verb_log: Path, dry_run: bool) -> int:
    if not deploy_home.exists():
        log_event("uninstall", f"target_home_absent path={deploy_home}")
        return 0
    log_event("uninstall", f"target_home_present path={deploy_home}")
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"would_remove {deploy_home}\n")
    if dry_run:
        log_event("uninstall", "dry_run skipping rmtree")
        return 0
    try:
        shutil.rmtree(deploy_home)
    except OSError as exc:
        log_event("uninstall", f"rmtree_failed path={deploy_home} err={exc}", level=logging.ERROR)
        return 1
    log_event("uninstall", f"target_home_removed path={deploy_home}")
    return 0


def _uninstall_one(target: str, args: argparse.Namespace) -> int:
    verb_log = log_path("uninstall", target)
    attach_file_log("uninstall", verb_log)
    state = read_state()
    installs = state.get("installs", {})
    if not isinstance(installs, dict): installs = {}
    entry = installs.get(target, {})
    if not isinstance(entry, dict): entry = {}
    deploy_home_raw = entry.get("target")
    deploy_home = Path(str(deploy_home_raw)).expanduser() if deploy_home_raw else None
    log_event("uninstall", f"start target={target} home={deploy_home} purge={args.really_purge}")

    bead_id = bd_create(
        title=f"magi uninstall --target {target}",
        body=f"target={target} purge={args.really_purge} dry_run={args.dry_run}",
        labels={"pack": "magi", "verb": "uninstall", "target": target, "role": "root"},
        verb="uninstall"
    )
    if bead_id: bd_update(bead_id, claim=True, verb="uninstall")
    if bead_id: write_inflight_sentinel(bead_id, "uninstall", target)

    rc = 0
    closed = False
    try:
        _close_open_install_beads(target)
        if args.really_purge:
            if not args.yes:
                log_event(
                    "uninstall",
                    "purge_requested_without_yes refusing to remove home",
                    level=logging.ERROR
                )
                rc = 2
            elif deploy_home is None:
                log_event("uninstall", "no_recorded_home cannot purge", level=logging.WARNING)
            else:
                rc = _purge_target_home(deploy_home, verb_log, args.dry_run)
        if not args.dry_run:
            installs[target] = {
                "installed": False,
                "target": None,
                "last_run_timestamp": now_utc_iso(),
                "last_run_rc": rc,
                "last_log": str(verb_log),
                "bead_id": bead_id,
                "feature_flags": {},
                "utilities_linked": False,
                "flag_fingerprint": None
            }
            state["installs"] = installs
            state["last_uninstall_timestamp"] = now_utc_iso()
            write_state(state)
        if bead_id:
            outcome = "0" if rc == 0 else "2" if rc == 2 else "1"
            bd_close(
                bead_id,
                outcome=outcome,
                labels={"role": "uninstall-closure"},
                verb="uninstall"
            )
            closed = True
        return rc
    finally:
        if bead_id and not closed:
            bd_close(
                bead_id,
                outcome="interrupted",
                labels={"role": "uninstall-closure"},
                verb="uninstall"
            )
        if bead_id: clear_inflight_sentinel(bead_id)


def main() -> int:
    """Entry point for magi-uninstall."""
    parser = _build_parser()
    args = parser.parse_args()
    if not args.yes and (args.really_purge):
        print("--really-purge requires --yes", file=sys.stderr)
        return 2
    try:
        city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    reconcile_orphans("uninstall")
    if args.target == "all":
        worst = 0
        for target in ("claude", "codex", "gemini", "openai"):
            rc = _uninstall_one(target, args)
            if rc > worst: worst = rc
        return worst
    return _uninstall_one(args.target, args)


if __name__ == "__main__":
    sys.exit(main())
