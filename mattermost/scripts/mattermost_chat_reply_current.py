#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import mattermost_intake_common as common


def _load_body(args: argparse.Namespace) -> str:
    if args.body:
        return args.body
    if args.body_file:
        return pathlib.Path(args.body_file).read_text(encoding="utf-8")
    raise SystemExit("either --body or --body-file is required")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Reply to the latest Mattermost event seen by the current session")
    parser.add_argument("--session", default="", help="Override session selector")
    parser.add_argument("--tail", type=int, default=40, help="Transcript messages to search for Mattermost context")
    parser.add_argument("--conversation-id", default="", help="Mattermost channel id to reply in")
    parser.add_argument("--root-id", default="", help="Mattermost thread root post id to reply under")
    parser.add_argument("--reply-to", default="", help="Mattermost post id to reply to")
    parser.add_argument("--body", default="", help="Inline message body")
    parser.add_argument("--body-file", default="", help="Read the message body from a file")
    args = parser.parse_args(argv)

    body = _load_body(args)
    context: dict[str, str] = {}
    try:
        context = common.find_latest_mattermost_reply_context(args.session, tail=max(1, args.tail))
    except common.GCAPIError as exc:
        if not str(args.conversation_id).strip():
            raise SystemExit(str(exc)) from exc
        context = {}

    requested_conversation_id = str(args.conversation_id).strip() or str(context.get("publish_conversation_id", "")).strip()
    root_post_id = (
        str(args.root_id).strip()
        or str(args.reply_to).strip()
        or str(context.get("publish_root_post_id", "")).strip()
    )
    binding_id = str(context.get("publish_binding_id", "")).strip()

    if binding_id:
        config = common.load_config()
        binding = common.resolve_publish_route(config, binding_id)
        if not binding:
            raise SystemExit(f"binding not found: {binding_id}")
        source_identity: dict[str, str] = {}
        try:
            if args.session:
                source_identity = common.resolve_session_identity(args.session)
        except common.GCAPIError as exc:
            raise SystemExit(str(exc)) from exc
        try:
            payload = common.publish_binding_message(
                binding,
                body,
                requested_conversation_id=requested_conversation_id,
                trigger_id=str(context.get("publish_trigger_id", "")).strip(),
                reply_to_message_id=root_post_id,
                source_context=context or None,
                source_session_name=str(source_identity.get("session_name", "")).strip(),
                source_session_id=str(source_identity.get("session_id", "")).strip(),
            )
        except (ValueError, common.MattermostAPIError) as exc:
            raise SystemExit(str(exc)) from exc
        source_meta = common.derive_publish_source_metadata(context)
        payload["reply_context"] = {
            "session_selector": str(args.session).strip() or common.current_session_selector(),
            "binding_id": binding_id,
            "source_event_kind": str(source_meta.get("source_event_kind", "")).strip(),
            "root_ingress_receipt_id": str(source_meta.get("root_ingress_receipt_id", "")).strip(),
            "publish_conversation_id": requested_conversation_id,
            "publish_trigger_id": str(context.get("publish_trigger_id", "")).strip(),
            "publish_root_post_id": str(payload.get("record", {}).get("root_post_id", "")).strip() or root_post_id,
            "source_session_name": str(source_identity.get("session_name", "")).strip()
            or str(os.environ.get("GC_SESSION_NAME", "")).strip(),
            "source_session_id": str(source_identity.get("session_id", "")).strip()
            or str(os.environ.get("GC_SESSION_ID", "")).strip(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return common.peer_delivery_exit_code(payload.get("record", {}))

    conversation_id = requested_conversation_id
    if not conversation_id:
        raise SystemExit("latest mattermost event is missing publish_conversation_id")
    try:
        # Mattermost rejects a root_id that points at a reply, so walk the
        # reply target up to its thread root before posting.
        resolved_root_id = common.resolve_thread_root_id(conversation_id, root_post_id) if root_post_id else ""
        response = common.post_channel_message(
            conversation_id,
            body,
            root_id=resolved_root_id,
        )
    except common.MattermostAPIError as exc:
        raise SystemExit(str(exc)) from exc

    remote_message_id = str((response or {}).get("id", "")).strip()
    if not remote_message_id:
        raise SystemExit("mattermost publish returned no post id")

    result = {
        "record": {
            "remote_message_id": remote_message_id,
            "conversation_id": conversation_id,
            "root_post_id": resolved_root_id,
        },
        "response": response,
        "reply_context": {
            "session_selector": str(args.session).strip() or common.current_session_selector(),
            "binding_id": binding_id,
            "publish_conversation_id": conversation_id,
            "publish_root_post_id": resolved_root_id,
            "source_session_name": str(os.environ.get("GC_SESSION_NAME", "")).strip(),
            "source_session_id": str(os.environ.get("GC_SESSION_ID", "")).strip(),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
