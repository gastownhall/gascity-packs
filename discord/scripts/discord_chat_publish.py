#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Publish a Discord-visible message through a saved chat binding")
    parser.add_argument("--binding", required=True, help="Binding id such as room:1234567890")
    parser.add_argument("--conversation-id", default="", help="Discord channel or thread id to publish into")
    parser.add_argument("--trigger", default="", help="Original Discord message id for reply threading")
    parser.add_argument("--reply-to", default="", help="Explicit Discord message id to reply to")
    parser.add_argument(
        "--source-event-kind",
        default="",
        choices=("", "discord_human_message", "discord_peer_publication"),
        help="Optional source event kind for peer-fanout-capable publishes",
    )
    parser.add_argument(
        "--source-ingress-receipt-id",
        default="",
        help="Ingress receipt id for the source Discord event; used to derive the root for human-originated fanout",
    )
    parser.add_argument(
        "--root-ingress-receipt-id",
        default="",
        help="Root ingress receipt id for peer-fanout-capable publishes",
    )
    parser.add_argument(
        "--source-session",
        default="",
        help="Optional exact session name or id to attribute this publish to instead of the current session env",
    )
    parser.add_argument("--body", default="", help="Inline message body")
    parser.add_argument("--body-file", default="", help="Read the message body from a file")
    args = parser.parse_args(argv)

    body = _load_body(args)
    config = common.load_config()
    binding = common.resolve_chat_binding(config, args.binding)
    if not binding:
        raise SystemExit(f"binding not found: {args.binding}")
    source_context = {}
    if args.source_event_kind:
        source_context["kind"] = args.source_event_kind
    if args.source_ingress_receipt_id:
        source_context["ingress_receipt_id"] = args.source_ingress_receipt_id
    if args.root_ingress_receipt_id:
        source_context["root_ingress_receipt_id"] = args.root_ingress_receipt_id
    source_identity = {}
    try:
        if args.source_session:
            source_identity = common.resolve_session_identity(args.source_session)
    except common.GCAPIError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        payload = common.publish_binding_message(
            binding,
            body,
            requested_conversation_id=args.conversation_id,
            trigger_id=args.trigger,
            reply_to_message_id=args.reply_to,
            source_context=source_context or None,
            source_session_name=str(source_identity.get("session_name", "")).strip(),
            source_session_id=str(source_identity.get("session_id", "")).strip(),
        )
    except (ValueError, common.DiscordAPIError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, indent=2, sort_keys=True))
    return common.peer_delivery_exit_code(payload.get("record", {}))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
