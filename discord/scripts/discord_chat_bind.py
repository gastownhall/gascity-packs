#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import discord_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bind a Discord conversation to a session via extmsg")
    parser.add_argument("--kind", required=True, choices=("dm", "room"), help="Binding kind")
    parser.add_argument("--guild-id", default="", help="Discord guild id (used as scope_id)")
    parser.add_argument("conversation_id", help="Discord DM, channel, or thread id")
    parser.add_argument("session_name", nargs="+", help="Gas City session name(s)")
    args = parser.parse_args(argv)

    config = common.load_config()
    app_id = str(config.get("app", {}).get("application_id", "")).strip()
    if not app_id:
        raise SystemExit("Discord app not configured. Run gc discord import-app first.")

    conversation = {
        "scope_id": args.guild_id or "global",
        "provider": "discord",
        "account_id": app_id,
        "conversation_id": args.conversation_id,
        "kind": args.kind,
    }

    results = []
    for session in args.session_name:
        # Create binding via extmsg API.
        resp = common.gc_api_request("POST", "/v0/extmsg/bindings", {
            "conversation": conversation,
            "session_id": session,
        })
        results.append(resp)

        # Ensure transcript membership so the session sees conversation history.
        try:
            common.gc_api_request("POST", "/v0/extmsg/transcript/membership", {
                "conversation": conversation,
                "session_id": session,
                "backfill_policy": "all",
                "owner": "binding",
            })
        except common.GCAPIError:
            pass  # Best-effort; binding is the primary operation.

    if len(results) == 1:
        print(json.dumps(results[0], indent=2, sort_keys=True))
    else:
        print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
