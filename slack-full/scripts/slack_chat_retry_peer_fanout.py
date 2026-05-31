#!/usr/bin/env python3
"""Retry failed Slack peer-fanout deliveries.

Walks recent ``extmsg.peer_fanout_failed`` events and re-issues a peer
notification for each one that has not already been retried successfully.
The actual retry + audit-event emission happens server-side via
``POST /v0/city/{cityName}/extmsg/peer-fanout/retry``; this CLI is a
discoverer + dispatcher.

Idempotence is provided by the ``original_seq`` field on the audit event:
if a prior ``extmsg.peer_fanout_retried`` event exists with
``payload.success == true`` and a matching ``original_seq``, that
candidate is skipped. Re-running the command on the same set with no
transient changes is therefore a no-op.

Cooldown: a small constant delay between attempts keeps a local burst
from amplifying a Slack rate-limit storm.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import slack_intake_common as common


DEFAULT_SINCE = "1h"
# RETRIED_LOOKBACK is the window over which we look for prior successful
# retries when building the dedupe set. It is decoupled from --since
# (which scopes the candidate failed events): a failure inside the
# --since window can correspond to a successful retry that happened
# *before* the window, and re-firing that retry would produce duplicate
# Slack nudges. 7d is generous coverage for any reasonable operator
# cadence and bounded enough not to re-scan the entire event log.
RETRIED_LOOKBACK = "7d"
DEFAULT_LIMIT = 200
DEFAULT_MAX = 50
DEFAULT_COOLDOWN_SECONDS = 0.25


def _events(event_type: str, *, since: str, limit: int) -> list[dict[str, Any]]:
    qs = [f"type={event_type}", f"limit={limit}"]
    if since:
        qs.append(f"since={since}")
    url = (
        f"{common.gc_api_base()}/v0/city/{common.gc_city_name()}/events?"
        + "&".join(qs)
    )
    try:
        res = common._request("GET", url, csrf=False)
    except common.GCAPIError:
        return []
    return list(res.get("items") or [])


def _successful_retried_seqs(retried_events: list[dict[str, Any]]) -> set[int]:
    """Collect original_seq values that already have a successful retry recorded."""
    seqs: set[int] = set()
    for evt in retried_events:
        payload = evt.get("payload") or {}
        if not payload.get("success"):
            continue
        original_seq = payload.get("original_seq")
        if isinstance(original_seq, int):
            seqs.add(original_seq)
    return seqs


def _failed_seq(evt: dict[str, Any]) -> int | None:
    seq = evt.get("seq")
    if isinstance(seq, int):
        return seq
    return None


def _retry_request_body(evt: dict[str, Any]) -> dict[str, Any] | None:
    """Build the POST body for /extmsg/peer-fanout/retry from a failed event."""
    payload = evt.get("payload") or {}
    target_session = (payload.get("target_session") or "").strip()
    conversation_id = (payload.get("conversation_id") or "").strip()
    provider = (payload.get("provider") or "").strip()
    if not target_session or not conversation_id or not provider:
        return None
    seq = _failed_seq(evt)
    if seq is None:
        return None
    return {
        "original_seq": seq,
        "target_session": target_session,
        "actor_display_name": (payload.get("actor_display_name") or "").strip(),
        "actor_kind": (payload.get("actor_kind") or "agent").strip(),
        "text": payload.get("text") or "",
        "conversation": {
            "scope_id": (payload.get("scope_id") or common.gc_city_name()),
            "provider": provider,
            "account_id": (payload.get("account_id") or ""),
            "conversation_id": conversation_id,
            "kind": (payload.get("kind") or "room"),
        },
    }


def _post_retry(body: dict[str, Any]) -> dict[str, Any]:
    url = (
        f"{common.gc_api_base()}/v0/city/{common.gc_city_name()}"
        f"/extmsg/peer-fanout/retry"
    )
    return common._request("POST", url, body)


def _cooldown(seconds: float) -> None:
    """Sleep between retries. Pulled out so tests can stub it to a no-op."""
    if seconds > 0:
        time.sleep(seconds)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Retry failed Slack peer-fanout deliveries.",
    )
    parser.add_argument("--since", default=DEFAULT_SINCE,
                        help=f"Go duration window for failed events (default {DEFAULT_SINCE}).")
    parser.add_argument("--conversation", default="",
                        help="Restrict retries to a single conversation_id.")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX,
                        help=f"Cap on retry attempts per run (default {DEFAULT_MAX}).")
    parser.add_argument("--cooldown-seconds", type=float,
                        default=DEFAULT_COOLDOWN_SECONDS,
                        help="Sleep between retries to avoid rate-limit amplification.")
    args = parser.parse_args(argv)

    failed = _events(
        "extmsg.peer_fanout_failed",
        since=args.since,
        limit=DEFAULT_LIMIT,
    )
    # Use a wider window for the retried-events lookup so a successful
    # retry that fell outside --since still suppresses re-delivery.
    # Without this, re-running the command with the same --since after
    # a successful retry happened earlier would re-fire that retry.
    retried = _events(
        "extmsg.peer_fanout_retried",
        since=RETRIED_LOOKBACK,
        limit=DEFAULT_LIMIT,
    )
    already_succeeded = _successful_retried_seqs(retried)

    convo_filter = args.conversation.strip()
    if convo_filter:
        failed = [
            e for e in failed
            if (e.get("payload") or {}).get("conversation_id") == convo_filter
        ]

    candidates = list(failed)

    successes = 0
    failures = 0
    skipped = 0
    attempts = 0
    attempted_details: list[dict[str, Any]] = []
    skipped_details: list[dict[str, Any]] = []

    for evt in candidates:
        seq = _failed_seq(evt)
        if seq is None:
            continue
        if seq in already_succeeded:
            skipped += 1
            skipped_details.append({"original_seq": seq, "reason": "already_retried"})
            continue
        if attempts >= args.max:
            break

        body = _retry_request_body(evt)
        if body is None:
            skipped += 1
            skipped_details.append({"original_seq": seq, "reason": "incomplete_payload"})
            continue

        if attempts > 0:
            _cooldown(args.cooldown_seconds)
        attempts += 1

        try:
            result = _post_retry(body)
        except common.GCAPIError as exc:
            failures += 1
            attempted_details.append({
                "original_seq": seq,
                "target_session": body["target_session"],
                "success": False,
                "error": str(exc),
            })
            continue

        success = bool(result.get("success"))
        if success:
            successes += 1
        else:
            failures += 1
        attempted_details.append({
            "original_seq": seq,
            "target_session": body["target_session"],
            "success": success,
            "error": result.get("error") or "",
        })

    summary = {
        "since": args.since,
        "conversation": convo_filter or None,
        "candidates": len(candidates),
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "skipped": skipped,
        "attempted": attempted_details,
        "skipped_details": skipped_details,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
