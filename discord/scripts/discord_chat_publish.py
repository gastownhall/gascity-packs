#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import discord_intake_common as common


def _load_body(args: argparse.Namespace) -> str:
    if args.body:
        return args.body
    if args.body_file:
        return pathlib.Path(args.body_file).read_text(encoding="utf-8")
    raise SystemExit("either --body or --body-file is required")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Publish a Discord-visible message via extmsg")
    parser.add_argument("--conversation-id", required=True, help="Discord channel or thread id")
    parser.add_argument("--guild-id", default="", help="Discord guild id (scope)")
    parser.add_argument("--reply-to", default="", help="Discord message id to reply to")
    parser.add_argument(
        "--session",
        default="",
        help="Session name publishing this message (defaults to current session)",
    )
    parser.add_argument("--body", default="", help="Inline message body")
    parser.add_argument("--body-file", default="", help="Read the message body from a file")
    args = parser.parse_args(argv)

    body = _load_body(args)
    config = common.load_config()
    app_id = str(config.get("app", {}).get("application_id", "")).strip()
    if not app_id:
        raise SystemExit("Discord app not configured. Run gc discord import-app first.")

    session_id = args.session or os.environ.get("GC_SESSION_NAME", "") or os.environ.get("GC_SESSION_ID", "")
    if not session_id:
        raise SystemExit("no session identity: pass --session or set GC_SESSION_NAME")

    conversation = {
        "scope_id": args.guild_id or "global",
        "provider": "discord",
        "account_id": app_id,
        "conversation_id": args.conversation_id,
        "kind": "room",
    }

    result = common.gc_api_request("POST", "/v0/extmsg/outbound", {
        "session_id": session_id,
        "conversation": conversation,
        "text": body,
        "reply_to_message_id": args.reply_to,
    })
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
