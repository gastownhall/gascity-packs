#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import discord_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Register guild-scoped Discord commands")
    parser.add_argument("guild_id", nargs="+", help="One or more Discord guild ids")
    args = parser.parse_args(argv)

    config = common.load_config()
    results: dict[str, object] = {}
    for guild_id in args.guild_id:
        results[guild_id] = common.sync_guild_commands(config, guild_id)
    print(json.dumps({"guilds": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
