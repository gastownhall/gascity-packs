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


# Every read below returns (items, error). Returning a bare [] for both "the
# city has none of these" and "the read failed" is what made dr-3lhmr's outage
# unreadable from its own output: a status tool reported zero inbound events
# while the events endpoint had not answered at all, and zero is a measurement
# nobody took. The two answers are kept apart from here to the rendered line.


def _read(fetch) -> tuple[list[dict[str, Any]], str]:
    """Run one API read. Returns (items, "") or ([], why it could not be read)."""
    try:
        res = fetch()
    except common.GCAPIError as exc:
        return [], str(exc)
    return list(res.get("items") or []), ""


def _events(event_type: str, limit: int, since: str) -> tuple[list[dict[str, Any]], str]:
    """Fetch a slice of events. Returns (items, "") or ([], reason unreadable)."""
    qs = [f"type={event_type}", f"limit={limit}"]
    if since:
        qs.append(f"since={since}")
    url = f"{common.gc_api_base()}/v0/city/{common.gc_city_name()}/events?" + "&".join(qs)
    return _read(lambda: common._request("GET", url, csrf=False))


def _adapters() -> tuple[list[dict[str, Any]], str]:
    return _read(lambda: common.gc_get("/extmsg/adapters"))


def _bindings_for_session(session_id: str) -> tuple[list[dict[str, Any]], str]:
    return _read(lambda: common.gc_get(f"/extmsg/bindings?session_id={session_id}"))


def collect_status(*, session: str, since: str, limit: int) -> dict[str, Any]:
    """Gather the read-only state used by both human and JSON renderers."""
    unreadable: dict[str, str] = {}

    def _section(name: str, result: tuple[list[dict[str, Any]], str]) -> list[dict[str, Any]]:
        items, error = result
        if error:
            unreadable[name] = error
        return items

    # Each section is read and recorded independently, so one endpoint that
    # cannot answer costs its own line and nothing else. Before dr-3lhmr the
    # events read raised straight out of here: the adapters result was already
    # in hand, the bindings read below was never reached, and the caller saw a
    # traceback instead of either. Note the order -- adapters, inbound,
    # outbound, bindings -- since it decides which sections a mid-walk failure
    # discards and which it never attempts.
    adapters = _section("adapters", _adapters())
    inbound = _section("events.inbound", _events("extmsg.inbound", limit, since))
    outbound = _section("events.outbound", _events("extmsg.outbound", limit, since))

    if session:
        inbound = [
            e for e in inbound
            if (e.get("payload") or {}).get("target_session") == session
        ]
        outbound = [
            e for e in outbound
            if (e.get("payload") or {}).get("session") == session
        ]
        bindings = _section("bindings", _bindings_for_session(session))
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
        "unreadable": unreadable,
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
    unreadable = status.get("unreadable") or {}

    adapters = status["adapters"]
    if "adapters" in unreadable:
        lines.append(f"Adapters:  (UNREADABLE: {unreadable['adapters']})")
    elif adapters:
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
    for label, key, items in (("inbound: ", "events.inbound", inbound),
                              ("outbound:", "events.outbound", outbound)):
        if key in unreadable:
            lines.append(f"  {label} (UNREADABLE: {unreadable[key]})")
        else:
            lines.append(f"  {label} {len(items)}")

    if status["session"]:
        lines.append("")
        lines.append(f"Session {status['session']}:")
        bindings = status["bindings"]
        if "bindings" in unreadable:
            lines.append(f"  bindings: (UNREADABLE: {unreadable['bindings']})")
        elif not bindings:
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

    # 0 every section was read, 2 at least one could not be. A status tool that
    # exits 0 while blind to a section is asserting a state it never observed;
    # the sections it DID read are still printed above, because the failure of
    # one read is not a reason to withhold the others.
    return 2 if status.get("unreadable") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
