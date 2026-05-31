#!/usr/bin/env python3
"""Read-only diagnostics for the slack pack: adapters, bindings, recent traffic.

Replaces the curl-jq one-liners that pile up while debugging:

    GET /extmsg/adapters
    GET /extmsg/bindings?session_id=...
    GET /events?type=extmsg.inbound
    GET /events?type=extmsg.outbound

Default output is a human-readable summary. ``--json`` prints the same
data as a single object for scripting. ``--session`` narrows the
binding + recent-activity views to one session.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import slack_intake_common as common


def _events(event_type: str, limit: int, since: str) -> list[dict[str, Any]]:
    """Fetch a slice of events. Returns [] on transport failure or empty."""
    qs = [f"type={event_type}", f"limit={limit}"]
    if since:
        qs.append(f"since={since}")
    url = f"{common.gc_api_base()}/v0/city/{common.gc_city_name()}/events?" + "&".join(qs)
    try:
        res = common._request("GET", url, csrf=False)
    except common.GCAPIError:
        return []
    return list(res.get("items") or [])


def _adapters() -> list[dict[str, Any]]:
    try:
        res = common.gc_get("/extmsg/adapters")
    except common.GCAPIError:
        return []
    return list(res.get("items") or [])


def _bindings_for_session(session_id: str) -> list[dict[str, Any]]:
    try:
        res = common.gc_get(f"/extmsg/bindings?session_id={session_id}")
    except common.GCAPIError:
        return []
    return list(res.get("items") or [])


def collect_status(*, session: str, since: str, limit: int) -> dict[str, Any]:
    """Gather the read-only state used by both human and JSON renderers."""
    adapters = _adapters()
    inbound = _events("extmsg.inbound", limit, since)
    outbound = _events("extmsg.outbound", limit, since)

    if session:
        inbound = [
            e for e in inbound
            if (e.get("payload") or {}).get("target_session") == session
        ]
        outbound = [
            e for e in outbound
            if (e.get("payload") or {}).get("session") == session
        ]
        bindings = _bindings_for_session(session)
    else:
        bindings = []

    return {
        "adapters": adapters,
        "session": session,
        "bindings": bindings,
        "events": {
            "since": since or None,
            "limit": limit,
            "inbound": inbound,
            "outbound": outbound,
        },
    }


def _fmt_event(direction: str, evt: dict[str, Any]) -> str:
    payload = evt.get("payload") or {}
    ts = (evt.get("ts") or evt.get("emitted_at") or evt.get("created_at") or "")[11:19]
    conv = payload.get("conversation_id") or "?"
    if direction == "in":
        target = payload.get("target_session") or payload.get("actor") or "?"
        return f"in   {ts:>8}  {conv}  → {target}"
    target = payload.get("session") or evt.get("subject") or "?"
    return f"out  {ts:>8}  {conv}  ← {target}"


def format_status(status: dict[str, Any]) -> str:
    lines: list[str] = []

    adapters = status["adapters"]
    if adapters:
        lines.append("Adapters:")
        for a in adapters:
            provider = a.get("provider") or "?"
            account = a.get("account_id") or "?"
            name = a.get("name") or ""
            tail = f" (name={name})" if name else ""
            lines.append(f"  {provider}/{account}{tail}")
    else:
        lines.append("Adapters:  (none registered — slack inbound + outbound publishing won't work)")

    events = status["events"]
    inbound = events["inbound"]
    outbound = events["outbound"]
    window = events["since"] or f"last {events['limit']}"
    lines.append("")
    lines.append(f"Events ({window}):")
    lines.append(f"  inbound:  {len(inbound)}")
    lines.append(f"  outbound: {len(outbound)}")

    if status["session"]:
        lines.append("")
        lines.append(f"Session {status['session']}:")
        bindings = status["bindings"]
        if not bindings:
            lines.append("  bindings: (none)")
        else:
            lines.append("  bindings:")
            for b in bindings:
                conv = b.get("Conversation") or {}
                cid = conv.get("conversation_id") or "?"
                kind = conv.get("kind") or "?"
                bstatus = b.get("Status") or "?"
                lines.append(f"    {cid}  kind={kind}  status={bstatus}")

    recent = []
    for evt in inbound[-5:]:
        recent.append(("in", evt))
    for evt in outbound[-5:]:
        recent.append(("out", evt))
    recent.sort(key=lambda pair: pair[1].get("ts")
                or pair[1].get("emitted_at")
                or pair[1].get("created_at") or "")
    if recent:
        lines.append("")
        lines.append("Recent activity:")
        for direction, evt in recent[-10:]:
            lines.append("  " + _fmt_event(direction, evt))

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Show slack pack status: adapters, bindings, recent traffic",
    )
    parser.add_argument("--session", default="",
                        help="Restrict bindings + activity to a single session id")
    parser.add_argument("--since", default="",
                        help="Event window (e.g. 5m, 1h). Default: most recent --limit events.")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max events to scan per direction. Default: 50")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    if args.limit < 1:
        raise SystemExit("--limit must be a positive integer")

    try:
        status = collect_status(
            session=args.session.strip(),
            since=args.since.strip(),
            limit=args.limit,
        )
    except common.GCAPIError as exc:
        raise SystemExit(str(exc)) from exc

    if args.as_json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(format_status(status))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
