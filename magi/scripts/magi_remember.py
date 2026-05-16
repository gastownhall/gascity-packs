"""bd memory wrapper for the magi pack.

Subcommands:
  remember <key> <value>  — `bd remember --key magi:<key> "<value>"`
  recall <key>            — `bd recall magi:<key>`
  list                    — `bd memories` filtered by magi: prefix
"""

from __future__ import annotations

import argparse
import json
import sys

from magi_common import BD_DEFAULT_TIMEOUT_SECONDS
from magi_common import CLIError
from magi_common import attach_file_log
from magi_common import bd_available_current
from magi_common import bd_remember
from magi_common import city_root
from magi_common import log_event
from magi_common import log_path
from magi_common import reconcile_orphans
from magi_common import redact_secrets
from magi_common import try_bd


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-remember", allow_abbrev=False)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    remember = sub.add_parser("remember", help="Persist a magi-prefixed memory entry.")
    remember.add_argument("key", help="Memory key (will be stored as magi:<key>).")
    remember.add_argument("value", help="Memory value (redacted if secret).")

    recall = sub.add_parser("recall", help="Recall a magi memory entry by key.")
    recall.add_argument("key", help="Memory key (looked up as magi:<key>).")

    sub.add_parser("list", help="List all magi-prefixed memory entries.")
    return parser


def _do_remember(args: argparse.Namespace) -> int:
    verb_log = log_path("remember", "bd")
    attach_file_log("remember", verb_log)
    log_event("remember", f"key={args.key}")
    if not bd_available_current():
        print("bd unavailable", file=sys.stderr)
        return 1
    if bd_remember(args.key, args.value, verb="remember"): return 0
    print("bd remember failed", file=sys.stderr)
    return 1


def _do_recall(args: argparse.Namespace) -> int:
    verb_log = log_path("recall", "bd")
    attach_file_log("recall", verb_log)
    log_event("recall", f"key={args.key}")
    result = try_bd(
        ["recall", f"magi:{args.key}"],
        timeout=BD_DEFAULT_TIMEOUT_SECONDS,
        verb="recall"
    )
    if result is None or result.returncode != 0: return 1
    print(result.stdout.rstrip())
    return 0


def _do_list() -> int:
    verb_log = log_path("recall", "list")
    attach_file_log("recall", verb_log)
    result = try_bd(
        ["memories", "--query", "magi:", "--json"],
        timeout=BD_DEFAULT_TIMEOUT_SECONDS,
        verb="recall"
    )
    if result is None or result.returncode != 0:
        print("bd memories failed", file=sys.stderr)
        return 1
    try:
        payload = json.loads(result.stdout.strip() or "[]")
    except json.JSONDecodeError:
        print(result.stdout.rstrip())
        return 0
    filtered = []
    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                key_value = entry.get("key")
                if isinstance(key_value, str) and key_value.startswith("magi:"):
                    filtered.append(entry)
    print(json.dumps(redact_secrets(filtered), indent=2, sort_keys=True))
    return 0


def main() -> int:
    """Entry point for magi-remember."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    reconcile_orphans("remember")
    if args.subcommand == "remember": return _do_remember(args)
    if args.subcommand == "recall": return _do_recall(args)
    if args.subcommand == "list": return _do_list()
    print(f"unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
