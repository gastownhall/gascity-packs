"""Formula wrapper for the magi pack.

Subcommands:
  list           — `bd formula list`
  show <name>    — `bd formula show <name>`
  cook <name>    — `bd cook <name>`
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from magi_common import BD_DEFAULT_TIMEOUT_SECONDS
from magi_common import CLIError
from magi_common import attach_file_log
from magi_common import bd_available_current
from magi_common import city_root
from magi_common import log_event
from magi_common import log_path
from magi_common import reconcile_orphans
from magi_common import try_bd


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-formulas", allow_abbrev=False)
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("list", help="List bd formulas.")
    show = sub.add_parser("show", help="Show a bd formula by name.")
    show.add_argument("name", help="Formula name.")
    cook = sub.add_parser("cook", help="Cook a bd formula by name.")
    cook.add_argument("name", help="Formula name.")
    return parser


def _do_list() -> int:
    result = try_bd(["formula", "list"], timeout=BD_DEFAULT_TIMEOUT_SECONDS, verb="formulas")
    if result is None: return 1
    if result.stdout: print(result.stdout.rstrip())
    if result.stderr: print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode


def _do_show(name: str) -> int:
    result = try_bd(["formula", "show", name], timeout=BD_DEFAULT_TIMEOUT_SECONDS, verb="formulas")
    if result is None: return 1
    if result.stdout: print(result.stdout.rstrip())
    if result.stderr: print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode


def _do_cook(name: str) -> int:
    verb_log = log_path("formulas", "cook")
    attach_file_log("formulas", verb_log)
    log_event("formulas", f"cook_start formula={name}")
    if not bd_available_current():
        print("bd unavailable", file=sys.stderr)
        return 1
    with verb_log.open("a", encoding="utf-8") as handle:
        proc = subprocess.run(
            ["bd", "cook", name],
            stdout=handle,
            stderr=subprocess.STDOUT,
            timeout=BD_DEFAULT_TIMEOUT_SECONDS * 12,
            check=False
        )
    log_event("formulas", f"cook_done formula={name} rc={proc.returncode}")
    return proc.returncode


def main() -> int:
    """Entry point for magi-formulas."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    reconcile_orphans("formulas")
    if args.subcommand == "list": return _do_list()
    if args.subcommand == "show": return _do_show(args.name)
    if args.subcommand == "cook": return _do_cook(args.name)
    print(f"unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
