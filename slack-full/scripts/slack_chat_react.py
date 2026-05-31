#!/usr/bin/env python3
"""Add an emoji reaction to a Slack message.

Default mode is `--current`: looks up the latest inbound transcript
entry routed to this session and reacts on that message. This is what
agents use as a "got it, working on a reply" receipt.

Explicit mode lets a caller name the channel + ts directly:

    gc slack react --conversation-id C0... --message-id 1234.5678 --emoji eyes

Emoji name is forwarded verbatim minus surrounding colons (so "eyes"
or ":eyes:" both work).
"""

from __future__ import annotations

import argparse
import json
import sys

import slack_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Add an emoji reaction to the latest inbound Slack message "
            "for this session, or to an explicit (channel, ts) pair."
        ),
    )
    parser.add_argument("--session", default="", help="Override session id")
    parser.add_argument(
        "--current",
        action="store_true",
        help=(
            "React on the latest inbound message routed to this session "
            "(resolved via gc transcript). This is the default — pass it "
            "for clarity or omit it; if --conversation-id is given, "
            "explicit mode wins."
        ),
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Slack channel id (explicit mode; requires --message-id).",
    )
    parser.add_argument(
        "--message-id",
        default="",
        help="Slack message ts (explicit mode; requires --conversation-id).",
    )
    parser.add_argument(
        "--emoji",
        default="eyes",
        help="Emoji name without colons (default: eyes).",
    )
    args = parser.parse_args(argv)

    explicit = bool(args.conversation_id) or bool(args.message_id)
    if explicit:
        if not (args.conversation_id and args.message_id):
            raise SystemExit(
                "--conversation-id and --message-id must be passed together"
            )
        conv_id = args.conversation_id
        msg_id = args.message_id
    else:
        session_id = (args.session or "").strip()
        if not session_id:
            try:
                session_id = common.current_session_id()
            except common.GCAPIError as exc:
                raise SystemExit(str(exc)) from exc
        match = common.find_latest_inbound_message_id_for_session(session_id)
        if match is None:
            raise SystemExit(
                "no recent inbound transcript entry for this session; "
                "pass --conversation-id and --message-id explicitly"
            )
        msg_id, conv = match
        conv_id = conv["conversation_id"]

    try:
        result = common.react_via_adapter(
            conversation_id=conv_id,
            message_id=msg_id,
            emoji=args.emoji,
        )
    except common.AdapterError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps({
        "conversation_id": conv_id,
        "message_id": msg_id,
        "emoji": args.emoji,
        "result": result,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
