#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import mattermost_intake_common as common

DEFAULT_EMOJI = "eyes"
DEFAULT_TRANSCRIPT_TAIL = 40


def _failure_kind(exc: common.MattermostAPIError) -> str:
    status = getattr(exc, "status_code", None)
    if status == 404:
        return "not_found"
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limited"
    if status == 400:
        return "invalid_request"
    return "error"


def _resolve_target(args: argparse.Namespace) -> tuple[str, str, str, dict[str, str]]:
    """Return (mode, conversation_id, post_id, source_context)."""
    conversation_id = str(args.conversation_id).strip()
    post_id = str(args.message_id).strip()
    if conversation_id or post_id:
        if args.current:
            raise SystemExit("--current cannot be combined with --conversation-id/--message-id")
        if not (conversation_id and post_id):
            raise SystemExit("--conversation-id and --message-id must be passed together")
        return "explicit", conversation_id, post_id, {}

    try:
        context = common.find_latest_mattermost_reply_context(args.session, tail=DEFAULT_TRANSCRIPT_TAIL)
    except common.GCAPIError as exc:
        raise SystemExit(
            f"{exc}; pass --conversation-id <channel_id> --message-id <post_id> to react to a specific post"
        ) from exc

    post_id = str(context.get("mattermost_post_id", "")).strip() or str(context.get("publish_trigger_id", "")).strip()
    conversation_id = str(context.get("publish_conversation_id", "")).strip()
    if not post_id:
        raise SystemExit(
            "latest mattermost event has no post id; pass --conversation-id and --message-id explicitly"
        )
    return "current", conversation_id, post_id, context


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Add an emoji reaction to the latest inbound Mattermost post for this session"
    )
    parser.add_argument("--emoji", default=DEFAULT_EMOJI, help="Mattermost emoji_name, no colons (default: eyes)")
    parser.add_argument("--session", default="", help="Override session selector")
    parser.add_argument("--conversation-id", default="", help="Explicit Mattermost channel id (requires --message-id)")
    parser.add_argument("--message-id", default="", help="Explicit Mattermost post id (requires --conversation-id)")
    parser.add_argument("--current", action="store_true", help="React to the latest inbound post (the default)")
    args = parser.parse_args(argv)

    emoji_name = common.normalize_emoji_name(args.emoji)
    if not emoji_name:
        raise SystemExit("--emoji must be a non-empty emoji name such as eyes")

    mode, conversation_id, post_id, context = _resolve_target(args)
    session_selector = str(args.session).strip() or common.current_session_selector()

    receipt: dict[str, object] = {
        "delivered": False,
        "mode": mode,
        "emoji": emoji_name,
        "conversation_id": conversation_id,
        "post_id": post_id,
        "session_selector": session_selector,
        "binding_id": str(context.get("publish_binding_id", "")).strip(),
        "user_id": "",
        "failure_kind": "",
        "error": "",
    }

    try:
        bot_user_id = common.resolve_bot_user_id()
        if not bot_user_id:
            raise common.MattermostAPIError("could not resolve the bot user id from GET /users/me")
        receipt["user_id"] = bot_user_id
        # Re-adding a reaction the bot already owns is a no-op server side.
        response = common.add_message_reaction(post_id, emoji_name, user_id=bot_user_id)
    except common.MattermostAPIError as exc:
        receipt["failure_kind"] = _failure_kind(exc)
        receipt["error"] = str(exc)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 1

    receipt["delivered"] = True
    receipt["reaction"] = response
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
