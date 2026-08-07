#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import mattermost_intake_common as common


def _load_body(args: argparse.Namespace) -> str:
    if args.body:
        return args.body
    if args.body_file:
        return pathlib.Path(args.body_file).read_text(encoding="utf-8")
    raise SystemExit("either --body or --body-file is required")


def _resolve_target(args: argparse.Namespace) -> tuple[str, str]:
    if args.request_id:
        request = common.load_request(args.request_id)
        if not request:
            raise SystemExit(f"request not found: {args.request_id}")
        channel_id = str(request.get("channel_id", "")).strip() or str(request.get("conversation_id", "")).strip()
        if not channel_id:
            raise SystemExit(f"request has no message target: {args.request_id}")
        root_id = args.root_id.strip() or str(request.get("root_id", "")).strip()
        return channel_id, root_id
    if args.channel_id:
        return args.channel_id, args.root_id.strip()
    raise SystemExit("either --request-id or --channel-id is required")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Post a message using the Mattermost workspace bot")
    parser.add_argument("--request-id", default="", help="Saved request id to route back to the original conversation")
    parser.add_argument("--channel-id", default="", help="Mattermost channel id")
    parser.add_argument("--root-id", default="", help="Mattermost thread root post id")
    parser.add_argument("--body", default="", help="Inline message body")
    parser.add_argument("--body-file", default="", help="Read the message body from a file")
    args = parser.parse_args(argv)

    target_channel, root_id = _resolve_target(args)
    body = _load_body(args)
    try:
        response = common.post_channel_message(target_channel, body, root_id)
    except common.MattermostAPIError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
