#!/usr/bin/env python3
"""Register a handle -> session alias with the local Slack adapter.

Used for cross-channel address-by-handle. When a Slack inbound parses
`@<handle>:` and the handle matches an alias, the adapter delivers the
message to the aliased session via gc's session-message API regardless
of channel binding. Empty session id removes the alias.

Typical use: at startup, register
    @mayor -> <mayor session id>
    @cos   -> <chief-of-staff session id>
so humans can address them from any channel.
"""

from __future__ import annotations

import argparse
import json
import sys

import slack_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Register a handle -> session alias with the slack adapter",
    )
    parser.add_argument("--handle", required=True,
                        help="Handle to alias (e.g. 'mayor', 'cos').")
    parser.add_argument("--session", default="",
                        help="Session id to map this handle to. Empty removes "
                             "the alias (equivalent to --remove).")
    parser.add_argument("--remove", action="store_true",
                        help="Explicitly remove the alias via DELETE "
                             "/handle-alias. Idempotent — missing entries "
                             "are not an error. --session is ignored when "
                             "--remove is set.")
    args = parser.parse_args(argv)

    handle = args.handle.strip().lstrip("@")
    if not handle:
        raise SystemExit("--handle is required and cannot be only whitespace or '@'")

    if args.remove:
        try:
            result = common.remove_handle_alias_via_adapter(handle=handle)
        except common.AdapterError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps({
            "handle": handle,
            "removed": True,
            "result": result,
        }, indent=2))
        return 0

    try:
        result = common.register_handle_alias_via_adapter(
            handle=handle,
            session_id=args.session.strip(),
        )
    except common.AdapterError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps({
        "handle": handle,
        "session_id": args.session.strip(),
        "result": result,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
