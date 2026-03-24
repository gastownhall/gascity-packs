#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import discord_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Enable launcher mode for a Discord root room via extmsg")
    parser.add_argument("--guild-id", required=True, help="Discord guild id")
    parser.add_argument(
        "--response-mode",
        default="mention_only",
        choices=("mention_only", "respond_all"),
        help="How root-room messages are routed",
    )
    parser.add_argument(
        "--default-handle",
        default="",
        help="Qualified rig/alias handle used for respond_all rooms",
    )
    parser.add_argument("conversation_id", help="Discord channel id for the root room")
    args = parser.parse_args(argv)

    config = common.load_config()
    app_id = str(config.get("app", {}).get("application_id", "")).strip()
    if not app_id:
        raise SystemExit("Discord app not configured. Run gc discord import-app first.")

    default_handle = str(args.default_handle).strip().lower()
    if default_handle:
        qualified_handle, resolve_error = common.resolve_agent_handle(default_handle)
        if resolve_error:
            raise SystemExit(resolve_error)
        default_handle = qualified_handle

    conversation = {
        "scope_id": args.guild_id,
        "provider": "discord",
        "account_id": app_id,
        "conversation_id": args.conversation_id,
        "kind": "room",
    }

    # Create group via extmsg API.
    group = common.gc_api_request("POST", "/v0/extmsg/groups", {
        "root_conversation": conversation,
        "mode": "launcher",
        "default_handle": default_handle,
        "metadata": {
            "response_mode": args.response_mode,
            "guild_id": args.guild_id,
        },
    })
    print(json.dumps(group, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
