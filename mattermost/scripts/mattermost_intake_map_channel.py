#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys

import mattermost_intake_common as common


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Map a Mattermost channel to a workflow target")
    parser.add_argument("team_id", help="Mattermost team id")
    parser.add_argument("channel_id", help="Mattermost channel id")
    parser.add_argument("target", help="gc sling target, usually rig/pool")
    parser.add_argument("--fix-formula", default=common.FIX_FORMULA_DEFAULT, help="Formula for /gc fix")
    args = parser.parse_args(argv)

    try:
        config = common.set_channel_mapping(
            common.load_config(),
            args.team_id,
            args.channel_id,
            args.target,
            args.fix_formula,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    key = common.normalize_channel_key(args.team_id, args.channel_id)
    print(json.dumps(config["channels"][key], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
