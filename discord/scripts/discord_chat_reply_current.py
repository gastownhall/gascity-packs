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
    parser = argparse.ArgumentParser(description="Reply to the latest Discord event in the current session")
    parser.add_argument("--session", default="", help="Override session selector")
    parser.add_argument("--tail", type=int, default=40, help="Transcript messages to search for Discord context")
    parser.add_argument("--conversation-id", default="", help="Discord channel/thread ID to reply in (skips transcript search)")
    parser.add_argument("--reply-to", default="", help="Discord message ID to reply to")
    parser.add_argument("--body", default="", help="Inline message body")
    parser.add_argument("--body-file", default="", help="Read the message body from a file")
    args = parser.parse_args(argv)

    body = _load_body(args)

    # Use explicit IDs if provided, otherwise search transcript.
    conversation_id = str(args.conversation_id).strip()
    reply_to = str(args.reply_to).strip()
    if not conversation_id:
        try:
            context = common.find_latest_discord_reply_context(args.session, tail=max(1, args.tail))
        except common.GCAPIError as exc:
            raise SystemExit(str(exc)) from exc
        conversation_id = str(context.get("publish_conversation_id", "")).strip()
        if not conversation_id:
            raise SystemExit("latest discord event is missing publish_conversation_id")
        if not reply_to:
            reply_to = str(context.get("publish_reply_to_discord_message_id", "")).strip()

    # Post directly to Discord.
    try:
        response = common.post_channel_message(
            conversation_id,
            body,
            reply_to_message_id=reply_to,
        )
    except common.DiscordAPIError as exc:
        raise SystemExit(str(exc)) from exc

    remote_message_id = str((response or {}).get("id", "")).strip()
    if not remote_message_id:
        raise SystemExit("discord publish returned no message id")

    result = {
        "record": {
            "remote_message_id": remote_message_id,
            "conversation_id": conversation_id,
            "reply_to": reply_to,
        },
        "response": response,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
