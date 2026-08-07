#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import mattermost_intake_common as common


def _read_optional_file(path: str | None) -> str:
    if not path:
        return ""
    return pathlib.Path(path).read_text(encoding="utf-8").strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Import Mattermost server metadata into the Mattermost pack")
    parser.add_argument("--server-url", required=True, help="Mattermost server base URL, e.g. https://mattermost.example.com")
    parser.add_argument("--command-name", default=common.COMMAND_NAME_DEFAULT, help="Slash command root name")
    parser.add_argument("--bot-token", default="", help="Mattermost bot personal access token")
    parser.add_argument("--bot-token-file", default="", help="Read the Mattermost bot token from a file")
    parser.add_argument("--verification-token", default="", help="Slash command verification token")
    parser.add_argument("--verification-token-file", default="", help="Read the verification token from a file")
    parser.add_argument("--team-allowlist", action="append", default=[], help="Optional allowed team id")
    parser.add_argument("--channel-allowlist", action="append", default=[], help="Optional allowed channel id")
    parser.add_argument("--role-allowlist", action="append", default=[], help="Optional allowed Mattermost role name")
    args = parser.parse_args(argv)

    bot_token = args.bot_token.strip() or _read_optional_file(args.bot_token_file)
    verification_token = args.verification_token.strip() or _read_optional_file(args.verification_token_file)
    try:
        if verification_token:
            verification_token = common.validate_command_token(verification_token)
        config = common.import_app_config(
            common.load_config(),
            {
                "site_url": args.server_url,
                "command_name": args.command_name,
                "team_allowlist": args.team_allowlist,
                "channel_allowlist": args.channel_allowlist,
                "channel_role_allowlist": args.role_allowlist,
            },
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if bot_token:
        common.save_bot_token(bot_token)
    if verification_token:
        common.save_command_token(verification_token)
    print(json.dumps(common.redact_config(config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
