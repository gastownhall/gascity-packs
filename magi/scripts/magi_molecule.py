"""Molecule operations for the magi pack.

Subcommands:
  bootstrap [<project-path>]  — create parent bead + child chain
  pour <formula>              — hand off to `bd mol pour`
  wisp <formula>              — hand off to `bd mol wisp`
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

from magi_common import BD_DEFAULT_TIMEOUT_SECONDS
from magi_common import CLIError
from magi_common import attach_file_log
from magi_common import bd_available_current
from magi_common import bd_close
from magi_common import bd_create
from magi_common import bd_dep
from magi_common import bd_update
from magi_common import city_root
from magi_common import load_policy
from magi_common import log_event
from magi_common import log_path
from magi_common import now_utc_iso
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import write_state


_BOOTSTRAP_CHAIN: tuple[str, ...] = (
    "doctor",
    "install",
    "bootstrap-project",
    "status",
    "analyze"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-molecule", allow_abbrev=False)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Create the magi bootstrap molecule chain.")
    bootstrap.add_argument(
        "project_path",
        nargs="?",
        default=None,
        help="Optional project path; defaults to $GC_CITY_PATH."
    )
    bootstrap.add_argument("--no-bd", action="store_true")

    pour = sub.add_parser("pour", help="Hand off to bd mol pour.")
    pour.add_argument("formula", help="Formula name.")

    wisp = sub.add_parser("wisp", help="Hand off to bd mol wisp.")
    wisp.add_argument("formula", help="Formula name.")

    return parser


def _bootstrap(args: argparse.Namespace) -> int:
    project_path = args.project_path or os.environ.get("GC_CITY_PATH")
    if not project_path:
        print("project_path required (or set GC_CITY_PATH)", file=sys.stderr)
        return 2

    verb_log = log_path("molecule", "bootstrap")
    attach_file_log("molecule", verb_log)
    log_event("molecule", f"bootstrap_start project={project_path}")

    policy = load_policy("molecule")
    raw_value = policy.get("bootstrap_chain")
    chain: tuple[str, ...]
    if isinstance(raw_value, list) and all(isinstance(item, str) for item in raw_value):
        chain = tuple(str(item) for item in raw_value)
    else:
        chain = _BOOTSTRAP_CHAIN

    if args.no_bd or not bd_available_current():
        log_event("molecule", "bd_unavailable_or_disabled chain only logged")
        for child in chain: log_event("molecule", f"chain_step name={child} project={project_path}")
        return 0

    parent_id = bd_create(
        title=f"magi molecule bootstrap project={project_path}",
        body=f"chain={','.join(chain)}",
        labels={"pack": "magi", "verb": "molecule", "target": "project", "role": "root"},
        verb="molecule"
    )
    if not parent_id:
        log_event("molecule", "bd_create_failed", level=logging.WARNING)
        return 1
    bd_update(parent_id, claim=True, verb="molecule")

    child_ids: list[str] = []
    for step in chain:
        verb_label = step if step != "bootstrap-project" else "bootstrap-project"
        child = bd_create(
            title=f"magi molecule child: {step}",
            body=f"parent={parent_id} step={step} project={project_path}",
            labels={"pack": "magi", "verb": verb_label, "target": "project", "role": "child"},
            verb="molecule"
        )
        if child:
            child_ids.append(child)
            bd_dep(parent_id, child, verb="molecule")

    bd_close(parent_id, outcome="0", verb="molecule")
    state = read_state()
    state["molecule"] = {
        "bootstrap_root_id": parent_id,
        "child_ids": child_ids,
        "last_run_timestamp": now_utc_iso(),
        "project_path": project_path
    }
    write_state(state)
    log_event("molecule", f"bootstrap_done parent={parent_id} children={len(child_ids)}")
    return 0


def _passthrough(args: argparse.Namespace, op: str) -> int:
    if not bd_available_current():
        print("bd not available", file=sys.stderr)
        return 1
    verb_log = log_path("molecule", op)
    attach_file_log("molecule", verb_log)
    with verb_log.open("a", encoding="utf-8") as handle:
        proc = subprocess.run(
            ["bd", "mol", op, args.formula],
            stdout=handle,
            stderr=subprocess.STDOUT,
            timeout=BD_DEFAULT_TIMEOUT_SECONDS * 6,
            check=False
        )
    log_event("molecule", f"{op}_done formula={args.formula} rc={proc.returncode}")
    return proc.returncode


def main() -> int:
    """Entry point for magi-molecule."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    reconcile_orphans("molecule")
    if args.subcommand == "bootstrap": return _bootstrap(args)
    if args.subcommand in {"pour", "wisp"}: return _passthrough(args, args.subcommand)
    print(f"unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
