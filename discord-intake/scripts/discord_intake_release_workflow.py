#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import discord_intake_common as common


def workflow_key_from_args(args: argparse.Namespace) -> tuple[str, str]:
    if args.request_id:
        request = common.load_request(args.request_id)
        if not request:
            raise SystemExit(f"request not found: {args.request_id}")
        workflow_key = str(request.get("workflow_key", "")).strip()
        if not workflow_key:
            raise SystemExit(f"request has no workflow key: {args.request_id}")
        return workflow_key, str(request.get("request_id", "")).strip()
    if not args.guild_id or not args.conversation_id:
        raise SystemExit("either --request-id or <guild_id> <conversation_id> is required")
    workflow_key = common.build_workflow_key(args.guild_id, args.conversation_id, args.command)
    linked = common.load_workflow_link(workflow_key) or {}
    return workflow_key, str(linked.get("request_id", "")).strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Release a stuck Discord workflow lock")
    parser.add_argument("guild_id", nargs="?", help="Discord guild id")
    parser.add_argument("conversation_id", nargs="?", help="Discord conversation id (channel or thread)")
    parser.add_argument("--request-id", default="", help="Release the workflow key recorded on an existing request")
    parser.add_argument("--command", default="fix", help="Slash command name, default: fix")
    args = parser.parse_args(argv)

    workflow_key, request_id = workflow_key_from_args(args)
    common.remove_workflow_link(workflow_key)

    released = {
        "workflow_key": workflow_key,
        "released": True,
    }
    if request_id:
        request = common.load_request(request_id)
        if request:
            request["workflow_released_at"] = common.utcnow()
            common.save_request(request)
            released["request_id"] = request_id
    print(json.dumps(released, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
