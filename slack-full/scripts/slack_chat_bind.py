#!/usr/bin/env python3
"""Bind a Slack conversation to one or more named gc sessions.

v0: only ``--kind dm`` is supported. The underlying primitives in gc
already accept room/thread bindings; the slack-specific routing
semantics (ambient_read, peer_fanout, launcher mode) will land in
later iterations.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import slack_intake_common as common


def _slack_workspace_id() -> str:
    import os
    val = os.environ.get("SLACK_WORKSPACE_ID", "").strip()
    if not val:
        raise SystemExit("SLACK_WORKSPACE_ID must be set in the slack adapter env")
    return val


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Bind a Slack conversation to one or more named gc sessions",
    )
    parser.add_argument("--kind", required=True, choices=("dm",))
    parser.add_argument("conversation_id", help="Slack channel/DM id (e.g. D0B0TTS550F)")
    parser.add_argument("session_name", nargs="+", help="gc session name or id")
    args = parser.parse_args(argv)

    workspace_id = _slack_workspace_id()
    city = common.gc_city_name()
    conversation = {
        "scope_id": city,
        "provider": "slack",
        "account_id": workspace_id,
        "conversation_id": args.conversation_id,
        "kind": args.kind,
    }

    records: list[dict[str, Any]] = []
    for sess in args.session_name:
        try:
            res = common.gc_post(
                "/extmsg/bind",
                {"session_id": sess, "conversation": conversation},
            )
        except common.GCAPIError as exc:
            raise SystemExit(f"bind {sess}: {exc}") from exc
        records.append(res)

    cfg = common.load_pack_config()
    cfg.setdefault("bindings", {})
    binding_key = f"dm:{args.conversation_id}"
    cfg["bindings"][binding_key] = {
        "kind": "dm",
        "conversation": conversation,
        "session_names": list(args.session_name),
        "binding_records": [r.get("ID", "") for r in records],
    }
    common.save_pack_config(cfg)

    print(json.dumps({"binding_key": binding_key, "records": records}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
