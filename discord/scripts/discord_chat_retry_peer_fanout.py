#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import discord_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Retry peer fanout for a previously published Discord room message")
    parser.add_argument("--include-unknown", action="store_true", help="Also retry targets currently marked delivery_unknown")
    parser.add_argument("--target", action="append", default=[], help="Retry only the named session target (repeatable)")
    parser.add_argument("publish_id", help="Saved publish id to redrive")
    args = parser.parse_args(argv)

    try:
        record = common.retry_peer_fanout(
            args.publish_id,
            include_unknown=args.include_unknown,
            target_session_names=args.target,
        )
    except (ValueError, common.GCAPIError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(record, indent=2, sort_keys=True))
    return common.peer_delivery_exit_code(record)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
