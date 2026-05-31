#!/usr/bin/env python3
"""Register a per-session Slack identity override with the local adapter.

Each gc session can post to Slack under a distinct username + avatar
(``chat:write.customize`` scope). The adapter holds an in-memory + on-disk
registry keyed by session id; on every ``/publish`` it injects the
matching ``username``/``icon_url``/``icon_emoji`` into ``chat.postMessage``.
This command is the one-shot setup call — call it once at session start
(typically from the project-lead prompt) and every subsequent reply
posts under the chosen identity.

Reads the project's display name + avatar from ``.gc/project-brief.md``
when ``--from-brief`` is passed; otherwise takes ``--as``/``--avatar-url``/
``--avatar-emoji`` flags directly. The Slack app must have
``chat:write.customize`` granted (and be reinstalled) for the override
to take effect — without it, Slack ignores the username/icon and the
post falls through under the default bot identity.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

import slack_intake_common as common


_BRIEF_DISPLAY_NAME_RE = re.compile(r"^\s*display_name\s*:\s*(.+?)\s*$", re.MULTILINE)
_BRIEF_AVATAR_URL_RE = re.compile(r"^\s*avatar_url\s*:\s*(.+?)\s*$", re.MULTILINE)
_BRIEF_AVATAR_EMOJI_RE = re.compile(r"^\s*avatar_emoji\s*:\s*(.+?)\s*$", re.MULTILINE)


def _read_brief(path: pathlib.Path) -> dict[str, str]:
    """Pull display_name / avatar_url / avatar_emoji from .gc/project-brief.md.

    The brief is markdown; we look for simple ``key: value`` lines. Missing
    keys return empty strings — caller decides whether that's fatal.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    if m := _BRIEF_DISPLAY_NAME_RE.search(text):
        out["display_name"] = m.group(1).strip()
    if m := _BRIEF_AVATAR_URL_RE.search(text):
        out["avatar_url"] = m.group(1).strip()
    if m := _BRIEF_AVATAR_EMOJI_RE.search(text):
        out["avatar_emoji"] = m.group(1).strip()
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Register a per-session Slack identity override (chat:write.customize)",
    )
    parser.add_argument("--session", default="",
                        help="Session id to set identity for. Defaults to "
                             "the current session ($GC_SESSION_ID).")
    parser.add_argument("--as", dest="display_name", default="",
                        help="Display name to post under (e.g. 'Gas City PL').")
    parser.add_argument("--avatar-url", default="",
                        help="Avatar image URL. Mutually exclusive with --avatar-emoji.")
    parser.add_argument("--avatar-emoji", default="",
                        help="Avatar emoji name without colons (e.g. 'robot_face'). "
                             "Mutually exclusive with --avatar-url.")
    parser.add_argument("--from-brief", default="",
                        help="Path to .gc/project-brief.md to read display_name / "
                             "avatar_url / avatar_emoji from. Flag values still win "
                             "if both are set.")
    parser.add_argument("--remove", action="store_true",
                        help="Remove the identity override for the session "
                             "(DELETE /identity). Idempotent — missing entries "
                             "are not an error. All other identity flags are "
                             "ignored when --remove is set.")
    args = parser.parse_args(argv)

    if args.avatar_url and args.avatar_emoji:
        raise SystemExit("pass --avatar-url OR --avatar-emoji, not both")

    session_id = (args.session or "").strip()
    if not session_id:
        try:
            session_id = common.current_session_id()
        except common.GCAPIError as exc:
            raise SystemExit(str(exc)) from exc

    if args.remove:
        try:
            result = common.remove_identity_via_adapter(session_id=session_id)
        except common.AdapterError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps({
            "session_id": session_id,
            "removed": True,
            "result": result,
        }, indent=2))
        return 0

    display_name = args.display_name
    avatar_url = args.avatar_url
    avatar_emoji = args.avatar_emoji
    if args.from_brief:
        brief = _read_brief(pathlib.Path(args.from_brief))
        if not display_name:
            display_name = brief.get("display_name", "")
        if not avatar_url and not avatar_emoji:
            avatar_url = brief.get("avatar_url", "")
            avatar_emoji = brief.get("avatar_emoji", "")

    if not display_name and not avatar_url and not avatar_emoji:
        raise SystemExit(
            "no identity fields supplied — pass --as / --avatar-url / "
            "--avatar-emoji, or --from-brief pointing at a project-brief.md "
            "with at least one of display_name / avatar_url / avatar_emoji")

    try:
        result = common.register_identity_via_adapter(
            session_id=session_id,
            username=display_name,
            icon_url=avatar_url,
            icon_emoji=avatar_emoji,
        )
    except common.AdapterError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps({
        "session_id": session_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "avatar_emoji": avatar_emoji,
        "result": result,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
