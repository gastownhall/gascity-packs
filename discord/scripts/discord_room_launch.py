#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import discord_intake_common as common


def _optional_bool(enabled: bool, disabled: bool, *, enable_flag: str, disable_flag: str) -> bool | None:
    if enabled and disabled:
        raise SystemExit(f"choose only one of {enable_flag} or {disable_flag}")
    if enabled:
        return True
    if disabled:
        return False
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Enable launcher mode for a Discord root room")
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
    parser.add_argument("--enable-peer-fanout", action="store_true", help="Enable peer fanout in managed threads")
    parser.add_argument("--disable-peer-fanout", action="store_true", help="Disable peer fanout in managed threads")
    parser.add_argument(
        "--allow-untargeted-peer-fanout",
        action="store_true",
        help="Allow untargeted peer fanout inside managed threads",
    )
    parser.add_argument(
        "--disallow-untargeted-peer-fanout",
        action="store_true",
        help="Require explicit @@rig/alias peer targeting in managed threads",
    )
    parser.add_argument("conversation_id", help="Discord channel id for the root room")
    args = parser.parse_args(argv)

    default_handle = str(args.default_handle).strip().lower()
    if default_handle:
        try:
            qualified_handle, resolve_error = common.resolve_agent_handle(default_handle)
        except common.GCAPIError as exc:
            raise SystemExit(str(exc)) from exc
        if resolve_error:
            raise SystemExit(resolve_error)
        default_handle = qualified_handle

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

    policy: dict[str, Any] = {}
    if peer_fanout is not None:
        policy["peer_fanout_enabled"] = peer_fanout
    if untargeted_peer_fanout is not None:
        policy["allow_untargeted_peer_fanout"] = untargeted_peer_fanout

    try:
        config = common.set_room_launcher(
            common.load_config(),
            args.guild_id,
            args.conversation_id,
            response_mode=args.response_mode,
            default_qualified_handle=default_handle,
            policy=policy or None,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    launcher = common.resolve_room_launcher(config, args.conversation_id)
    print(json.dumps(launcher or {}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
