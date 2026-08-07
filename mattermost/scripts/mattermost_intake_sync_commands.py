#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import mattermost_intake_common as common


def _redact_command(command: object) -> object:
    if not isinstance(command, dict):
        return command
    body = dict(command)
    if body.get("token"):
        body["token"] = "[redacted]"
    return body


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Register team-scoped Mattermost slash commands")
    parser.add_argument("team_id", nargs="+", help="One or more Mattermost team ids")
    args = parser.parse_args(argv)

    config = common.load_config()
    results: dict[str, object] = {}
    had_errors = False
    for team_id in args.team_id:
        try:
            results[team_id] = {
                "status": "ok",
                "command": _redact_command(common.sync_team_commands(config, team_id)),
            }
        except common.MattermostAPIError as exc:
            had_errors = True
            results[team_id] = {
                "status": "error",
                "error": str(exc),
            }
    print(json.dumps({"teams": results}, indent=2, sort_keys=True))
    return 1 if had_errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
