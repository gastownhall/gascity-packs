#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import discord_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bind a Discord conversation to named sessions")
    parser.add_argument("--kind", required=True, choices=("dm", "room"), help="Binding kind")
    parser.add_argument("--guild-id", default="", help="Discord guild id for room metadata")
    parser.add_argument(
        "--enable-ambient-read",
        action="store_true",
        help="Allow bound room messages to route without a bot mention; explicit @session_name targeting is still required",
    )
    parser.add_argument(
        "--disable-ambient-read",
        action="store_true",
        help="Require a bot mention before guild room messages are routed",
    )
    parser.add_argument("--enable-peer-fanout", action="store_true", help="Enable bridge-local peer fanout for room publishes")
    parser.add_argument("--disable-peer-fanout", action="store_true", help="Disable bridge-local peer fanout for this room")
    parser.add_argument(
        "--allow-untargeted-peer-fanout",
        action="store_true",
        help="Allow untargeted room publishes to fan out to every other bound participant",
    )
    parser.add_argument(
        "--disallow-untargeted-peer-fanout",
        action="store_true",
        help="Require explicit @session_name targeting for peer-triggered fanout",
    )
    parser.add_argument(
        "--max-peer-triggered-publishes-per-root",
        type=int,
        default=None,
        help="Budget for peer-triggered publishes per root human ingress",
    )
    parser.add_argument(
        "--max-total-peer-deliveries-per-root",
        type=int,
        default=None,
        help="Cap total peer deliveries per root human ingress",
    )
    parser.add_argument(
        "--max-peer-triggered-publishes-per-session-per-minute",
        type=int,
        default=None,
        help="Rate limit peer-triggered publishes per source session per minute",
    )
    parser.add_argument("conversation_id", help="Discord DM, channel, or thread id")
    parser.add_argument("session_name", nargs="+", help="Exact Gas City session name")
    args = parser.parse_args(argv)

    if args.enable_ambient_read and args.disable_ambient_read:
        raise SystemExit("choose only one of --enable-ambient-read or --disable-ambient-read")
    if args.enable_peer_fanout and args.disable_peer_fanout:
        raise SystemExit("choose only one of --enable-peer-fanout or --disable-peer-fanout")
    if args.allow_untargeted_peer_fanout and args.disallow_untargeted_peer_fanout:
        raise SystemExit("choose only one of --allow-untargeted-peer-fanout or --disallow-untargeted-peer-fanout")
    policy_updates: dict[str, object] = {}
    if args.enable_ambient_read:
        policy_updates["ambient_read_enabled"] = True
    if args.disable_ambient_read:
        policy_updates["ambient_read_enabled"] = False
    if args.enable_peer_fanout:
        policy_updates["peer_fanout_enabled"] = True
    if args.disable_peer_fanout:
        policy_updates["peer_fanout_enabled"] = False
    if args.allow_untargeted_peer_fanout:
        policy_updates["allow_untargeted_peer_fanout"] = True
    if args.disallow_untargeted_peer_fanout:
        policy_updates["allow_untargeted_peer_fanout"] = False
    if args.max_peer_triggered_publishes_per_root is not None:
        policy_updates["max_peer_triggered_publishes_per_root"] = args.max_peer_triggered_publishes_per_root
    if args.max_total_peer_deliveries_per_root is not None:
        policy_updates["max_total_peer_deliveries_per_root"] = args.max_total_peer_deliveries_per_root
    if args.max_peer_triggered_publishes_per_session_per_minute is not None:
        policy_updates["max_peer_triggered_publishes_per_session_per_minute"] = (
            args.max_peer_triggered_publishes_per_session_per_minute
        )
    if policy_updates and args.kind != "room":
        raise SystemExit("room policy flags require --kind room")

    try:
        config = common.set_chat_binding(
            common.load_config(),
            args.kind,
            args.conversation_id,
            args.session_name,
            guild_id=args.guild_id,
            policy=policy_updates or None,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    binding = common.resolve_chat_binding(config, common.chat_binding_id(args.kind, args.conversation_id))
    print(json.dumps(binding, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
