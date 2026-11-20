#!/usr/bin/env python3
"""Publish a message into a Slack channel named by id.

Differs from ``publish`` in that the conversation_id is supplied
explicitly. Used by mayor / chief-of-staff to reply into channels they
have no binding for, after receiving a ``Slack address-by-handle``
system reminder triggered by `@mayor:` / `@cos:` keyword routing from
any channel.

Routing (``--via``, default ``auto``): the publish goes through gc's
``/extmsg/outbound`` first, the same path ``reply-current`` uses, so a
post into a bind-room reaches the other sessions bound to that room
(peer fanout) and lands in the gc transcript. Only when gc refuses the
publish because this session has no binding or group participation for
the channel -- the address-by-handle case this verb exists for -- or gc
is not listening at all, does it fall back to the local adapter
``/publish``, which posts to Slack but is invisible to peers. Any other
gc failure is reported, not retried through the adapter: gc may already
have posted, and a second path would post a second copy. ``--via
adapter`` keeps the old adapter-only behavior; ``--via gc`` never falls
back.

The session id flows through on both paths so the adapter applies the
matching identity registry override (visible username + avatar).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import slack_intake_common as common
import slack_mrkdwn


def _load_body(args: argparse.Namespace) -> str:
    if args.body and args.body_file:
        raise SystemExit("pass --body OR --body-file, not both")
    body = ""
    if args.body:
        body = args.body
    elif args.body_file:
        body = pathlib.Path(args.body_file).read_text(encoding="utf-8")
    else:
        raise SystemExit("either --body or --body-file is required")
    if not args.raw:
        # gp-o42: tilde pairs render as strikethrough in Slack mrkdwn.
        body = slack_mrkdwn.escape_accidental_mrkdwn(body)
    return body


# gc's HandleOutbound refuses a publish it cannot attribute with one of these
# strings (internal/extmsg/outbound.go). Both mean gc posted nothing, so the
# adapter-direct fallback cannot double-post.
_GC_UNBOUND_MARKERS = (
    "no active binding for conversation",
    "does not own binding for conversation",
)
# urllib reports a gc that is not listening as a refused connect; nothing was
# sent, so falling back is safe. A timeout is deliberately absent: gc may have
# published before the response stalled.
_GC_UNREACHABLE_MARKERS = (
    "Connection refused",
)


def _gc_fallback_reason(exc: Exception) -> str:
    """Return why an adapter-direct fallback is safe after ``exc``, or ""."""
    text = str(exc)
    if any(marker in text for marker in _GC_UNBOUND_MARKERS):
        return "this session has no gc binding or room participation for the channel"
    if any(marker in text for marker in _GC_UNREACHABLE_MARKERS):
        return "the gc API is not reachable"
    return ""


def _publish_via_gc(args: argparse.Namespace, session_id: str, body: str) -> dict:
    return common.publish_via_gc_outbound(
        session_id=session_id,
        scope_id=common.gc_city_name(),
        provider="slack",
        account_id=os.environ.get("SLACK_WORKSPACE_ID", "").strip(),
        conversation_id=args.conversation_id,
        kind=args.kind,
        text=body,
        reply_to_message_id=args.thread_ts,
        idempotency_key=args.idempotency_key,
    )


def _publish_via_adapter(args: argparse.Namespace, session_id: str, body: str) -> dict:
    return common.publish_to_channel_via_adapter(
        session_id=session_id,
        conversation_id=args.conversation_id,
        text=body,
        kind=args.kind,
        thread_ts=args.thread_ts,
        idempotency_key=args.idempotency_key,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Publish into a Slack channel by id, bypassing gc binding lookup",
    )
    parser.add_argument("--conversation-id", required=True,
                        help="Slack channel id (C..., G..., or D...).")
    parser.add_argument("--kind", default="room",
                        choices=("dm", "room", "thread"),
                        help="Conversation kind for the conversation envelope. "
                             "Defaults to 'room' (channels).")
    parser.add_argument("--thread-ts", default="",
                        help="Slack message ts to thread under (optional).")
    parser.add_argument("--session", default="",
                        help="Session id to attribute this publish to "
                             "(applies identity override). Defaults to "
                             "$GC_SESSION_ID.")
    parser.add_argument("--idempotency-key", default="",
                        help="Caller-supplied idempotency key (optional).")
    parser.add_argument(
        "--via", choices=("auto", "gc", "adapter"), default="auto",
        help=("auto (default): publish through gc /extmsg/outbound so peers "
              "bound to the room see the post, and fall back to the local "
              "adapter only when gc refuses for lack of a binding or is not "
              "listening. gc: never fall back. adapter: post adapter-direct "
              "(peers bound to the room will not see it)."))
    parser.add_argument("--body", default="")
    parser.add_argument("--body-file", default="")
    parser.add_argument(
        "--raw", action="store_true",
        help=("Send the body verbatim, skipping the accidental-mrkdwn guard "
              "(by default, tildes that would pair into unintended Slack "
              "strikethrough are neutralized; deliberate ~word~ wrapping and "
              "code spans always pass through)."))
    args = parser.parse_args(argv)

    body = _load_body(args)

    session_id = (args.session or "").strip()
    if not session_id:
        try:
            session_id = common.current_session_id()
        except common.GCAPIError as exc:
            raise SystemExit(str(exc)) from exc

    if not os.environ.get("SLACK_WORKSPACE_ID", "").strip():
        raise SystemExit("SLACK_WORKSPACE_ID is not set; cannot construct conversation envelope")

    via = "adapter" if args.via == "adapter" else "gc"
    result = None
    if via == "gc":
        try:
            result = _publish_via_gc(args, session_id, body)
        except common.GCAPIError as exc:
            reason = _gc_fallback_reason(exc) if args.via == "auto" else ""
            if not reason:
                raise SystemExit(
                    f"gc publish failed: {exc}\n"
                    "The post may or may not exist; check the channel before "
                    "re-running (a re-run can post a second copy).") from exc
            print(f"warning: {reason}; posting adapter-direct. Sessions bound "
                  f"to {args.conversation_id} will not see this post.",
                  file=sys.stderr)
            via = "adapter"
    if via == "adapter":
        try:
            result = _publish_via_adapter(args, session_id, body)
        except common.AdapterError as exc:
            raise SystemExit(str(exc)) from exc

    print(json.dumps({
        "session_id": session_id,
        "conversation_id": args.conversation_id,
        "thread_ts": args.thread_ts,
        "via": via,
        "result": result,
    }, indent=2))

    delivered, failure_kind = common.interpret_publish_receipt(result)
    if not delivered:
        print(
            f"slack publish failed: delivered=false failure_kind={failure_kind or 'unknown'}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
