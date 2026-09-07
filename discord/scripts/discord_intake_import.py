#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import discord_intake_common as common


def _read_optional_file(path: str | None) -> str:
    if not path:
        return ""
    try:
        value = pathlib.Path(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"could not read bot token file {path!r}: {exc.strerror or 'I/O error'}") from exc
    if not value:
        raise ValueError("bot token file is empty")
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Import Discord app metadata into the Discord pack")
    parser.add_argument("--app", default="", help="Optional named app identity")
    parser.add_argument("--application-id", required=True, help="Discord application id")
    parser.add_argument("--public-key", required=True, help="Discord interaction public key (hex)")
    parser.add_argument("--command-name", default=common.COMMAND_NAME_DEFAULT, help="Slash command root name")
    token_group = parser.add_mutually_exclusive_group()
    token_group.add_argument("--bot-token", default=None, help="Discord bot token")
    token_group.add_argument("--bot-token-file", default=None, help="Read the Discord bot token from a file")
    parser.add_argument("--guild-allowlist", action="append", default=None, help="Optional allowed guild id")
    parser.add_argument("--channel-allowlist", action="append", default=None, help="Optional allowed parent channel id")
    parser.add_argument("--role-allowlist", action="append", default=None, help="Optional allowed Discord role id")
    args = parser.parse_args(argv)

    app_name = ""
    try:
        app_name = common.validate_app_name(args.app)
        if args.bot_token_file is not None:
            bot_token = _read_optional_file(args.bot_token_file)
        elif args.bot_token is not None:
            bot_token = str(args.bot_token).strip()
            if not bot_token:
                raise ValueError("bot token is empty")
        else:
            bot_token = ""
        requested_application_id = common.validate_application_id(args.application_id)
        if app_name and bot_token:
            current_user = common.discord_api_request("GET", "/users/@me", bot_token=bot_token)
            authenticated_user_id = str(current_user.get("id", "")).strip() if isinstance(current_user, dict) else ""
            if authenticated_user_id != requested_application_id:
                raise ValueError(
                    f"Discord app {app_name!r} token authenticated as user {authenticated_user_id or '<unknown>'!r}, "
                    f"not configured application_id {requested_application_id!r}"
                )
        app_fields = {
            "application_id": args.application_id,
            "public_key": args.public_key,
            "command_name": args.command_name,
        }
        for field_name in ("guild_allowlist", "channel_allowlist", "role_allowlist"):
            value = getattr(args, field_name)
            if value is not None:
                app_fields[field_name] = value
        config = common.import_app_config(
            common.load_config(),
            app_fields,
            app_name=app_name,
            bot_token=bot_token or None,
        )
    except common.DiscordAPIError as exc:
        status = f" (HTTP {exc.status_code})" if exc.status_code is not None else ""
        raise SystemExit(f"failed to authenticate Discord bot token for app {app_name!r}{status}") from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except OSError as exc:
        raise SystemExit(f"failed to save Discord app credentials: {exc}") from exc
    print(json.dumps(common.redact_config(config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
