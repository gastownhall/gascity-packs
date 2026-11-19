"""The agent gc's un-welded launch contract starts in a box.

    <python> agent.py

With ``GC_CONTRACT_DIALOG=1`` it first shows Claude's "Bypass Permissions
mode" warning, which gc's dialog pass answers (Down, Enter), and then
scrolls it off the screen. Then it draws a ``❯ `` prompt and, for every
line of input, draws the prompt again. Each line of input it reads is
appended to ``GC_CONTRACT_INPUT`` as one JSON string, so the harness reads
exactly what was typed, and in which order.
"""

from __future__ import annotations

import json
import os
import sys

PROMPT = "❯ "
SCROLL = "\n" * 400
"""Enough blank lines to push a drawn dialog out of every screen read."""


def _log(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")


def _show(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def main() -> int:
    log = os.environ["GC_CONTRACT_INPUT"]
    if os.environ.get("GC_CONTRACT_DIALOG") == "1":
        _show(" WARNING: Claude Code running in Bypass Permissions mode\n\n ❯ 1. No, exit\n   2. Yes, I accept\n")
        line = sys.stdin.readline()
        if not line:
            return 0
        _log(log, line.rstrip("\n"))
        _show(SCROLL)
    _show(PROMPT)
    for line in sys.stdin:
        _log(log, line.rstrip("\n"))
        _show("\n" + PROMPT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
