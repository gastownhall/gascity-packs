#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import mattermost_intake_common as common


def _optional_bool(enabled: bool, disabled: bool, *, enable_flag: str, disable_flag: str) -> bool | None:
    if enabled and disabled:
        raise SystemExit(f"choose only one of {enable_flag} or {disable_flag}")
    if enabled:
        return True
    if disabled:
        return False
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bind a Mattermost conversation to one or more named sessions")
    parser.add_argument("--kind", required=True, choices=("dm", "room"), help="Binding kind")
    parser.add_argument("--team-id", default="", help="Mattermost team id")
    parser.add_argument(
        "--root-id",
        default="",
        help="Bind a single thread inside the channel instead of the whole channel",
    )
    parser.add_argument("--enable-ambient-read", action="store_true", help="Accept unmentioned messages in a bound room")
    parser.add_argument("--disable-ambient-read", action="store_true", help="Disable unmentioned room intake")
    parser.add_argument(
        "--allow-untargeted-ambient-delivery",
        action="store_true",
        help="For a single-session ambient room, route untargeted messages to that bound session",
    )
    parser.add_argument(
        "--disallow-untargeted-ambient-delivery",
        action="store_true",
        help="Require explicit @session_name targeting for ambient room messages",
    )
    parser.add_argument("--enable-peer-fanout", action="store_true", help="Enable peer fanout for bound room publishes")
    parser.add_argument("--disable-peer-fanout", action="store_true", help="Disable peer fanout for bound room publishes")
    parser.add_argument(
        "--allow-untargeted-peer-fanout",
        action="store_true",
        help="Allow untargeted peer fanout inside a peer-enabled room",
    )
    parser.add_argument(
        "--disallow-untargeted-peer-fanout",
        action="store_true",
        help="Require explicit peer targets for peer fanout",
    )
    parser.add_argument("--max-peer-triggered-publishes-per-root", type=int, default=None)
    parser.add_argument("--max-total-peer-deliveries-per-root", type=int, default=None)
    parser.add_argument("--max-peer-triggered-publishes-per-session-per-minute", type=int, default=None)
    parser.add_argument(
        "--enable-thread-replies",
        action="store_true",
        help="Reply-current threads replies under the message being answered (default)",
    )
    parser.add_argument(
        "--disable-thread-replies",
        action="store_true",
        help="Force reply-current to post flat, top-level messages instead of threading. Valid for --kind room or dm.",
    )
    parser.add_argument("conversation_id", help="Mattermost channel id (DM channels are channels too)")
    parser.add_argument("session_name", nargs="+", help="Gas City session name(s)")
    args = parser.parse_args(argv)

    ambient_read = _optional_bool(
        args.enable_ambient_read,
        args.disable_ambient_read,
        enable_flag="--enable-ambient-read",
        disable_flag="--disable-ambient-read",
    )
    untargeted_ambient_delivery = _optional_bool(
        args.allow_untargeted_ambient_delivery,
        args.disallow_untargeted_ambient_delivery,
        enable_flag="--allow-untargeted-ambient-delivery",
        disable_flag="--disallow-untargeted-ambient-delivery",
    )
    peer_fanout = _optional_bool(
        args.enable_peer_fanout,
        args.disable_peer_fanout,
        enable_flag="--enable-peer-fanout",
        disable_flag="--disable-peer-fanout",
    )
    untargeted_peer_fanout = _optional_bool(
        args.allow_untargeted_peer_fanout,
        args.disallow_untargeted_peer_fanout,
        enable_flag="--allow-untargeted-peer-fanout",
        disable_flag="--disallow-untargeted-peer-fanout",
    )

    thread_replies = _optional_bool(
        args.enable_thread_replies,
        args.disable_thread_replies,
        enable_flag="--enable-thread-replies",
        disable_flag="--disable-thread-replies",
    )

    room_policy: dict[str, Any] = {}
    if ambient_read is not None:
        room_policy["ambient_read_enabled"] = ambient_read
    if untargeted_ambient_delivery is not None:
        room_policy["allow_untargeted_ambient_delivery"] = untargeted_ambient_delivery
    if peer_fanout is not None:
        room_policy["peer_fanout_enabled"] = peer_fanout
    if untargeted_peer_fanout is not None:
        room_policy["allow_untargeted_peer_fanout"] = untargeted_peer_fanout
    if args.max_peer_triggered_publishes_per_root is not None:
        room_policy["max_peer_triggered_publishes_per_root"] = args.max_peer_triggered_publishes_per_root
    if args.max_total_peer_deliveries_per_root is not None:
        room_policy["max_total_peer_deliveries_per_root"] = args.max_total_peer_deliveries_per_root
    if args.max_peer_triggered_publishes_per_session_per_minute is not None:
        room_policy["max_peer_triggered_publishes_per_session_per_minute"] = args.max_peer_triggered_publishes_per_session_per_minute

    if args.kind != "room" and room_policy:
        raise SystemExit("room policy flags require --kind room")

    # thread_replies applies to any binding kind (unlike the room-only peer
    # policy above), so it's merged in after the room-only guard.
    if thread_replies is not None:
        room_policy["thread_replies"] = thread_replies

    root_id = str(args.root_id).strip()
    if root_id and args.kind != "room":
        raise SystemExit("--root-id requires --kind room")
    # A Mattermost thread is not its own channel, so a thread binding is keyed
    # by the channel id plus the thread root post id.
    conversation_id = common.mattermost_conversation_key(args.conversation_id, root_id)

    try:
        config = common.set_chat_binding(
            common.load_config(),
            args.kind,
            conversation_id,
            args.session_name,
            team_id=args.team_id,
            policy=room_policy or None,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    binding = common.resolve_chat_binding(config, common.chat_binding_id(args.kind, conversation_id))
    print(json.dumps(binding or {}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
