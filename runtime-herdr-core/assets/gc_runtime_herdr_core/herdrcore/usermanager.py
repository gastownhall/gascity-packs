"""The names in the systemd user manager's environment block.

Every unit the user manager runs gets that block, so a holder hc placed
under systemd carries it, and when the holder restarts a core that crashed
(hc ``holder.rs``) it hands the block on in the new core's environment file.
The pack's own core runs with the block too, and passes it to its programs,
so the block's names are not the starter's (:func:`.core.foreign_reason`).
The block is read as hc reads it (hc ``platform/systemd.rs``
``manager_env``): the manager's ``Environment`` property through ``busctl``.
"""

from __future__ import annotations

import subprocess
from typing import Final, FrozenSet, List, Optional

BUSCTL_TIMEOUT_S: Final = 2.0
BUSCTL_PATH: Final = "/usr/local/bin:/usr/bin:/bin"
BUSCTL_ARGV: Final = (
    "busctl",
    "--user",
    "--timeout=1",
    "get-property",
    "org.freedesktop.systemd1",
    "/org/freedesktop/systemd1",
    "org.freedesktop.systemd1.Manager",
    "Environment",
)

_ESCAPES: Final = {"a": "\x07", "b": "\x08", "f": "\x0c", "n": "\n", "r": "\r", "t": "\t", "v": "\x0b", "\\": "\\", "'": "'", '"': '"'}


def read_manager_keys(run_user: str) -> Optional[FrozenSet[str]]:
    """The names in the block of the user manager at ``run_user`` (its
    ``XDG_RUNTIME_DIR``); None when it cannot be read."""
    try:
        done = subprocess.run(
            list(BUSCTL_ARGV),
            env={"PATH": BUSCTL_PATH, "XDG_RUNTIME_DIR": run_user, "LC_ALL": "C"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=BUSCTL_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return parse_busctl_environment(done.stdout.decode("utf-8", "replace"))


def parse_busctl_environment(text: str) -> Optional[FrozenSet[str]]:
    """The names of ``busctl get-property``'s ``as N "K=V" ...`` reply; None
    when it is not that shape."""
    head = text.strip().split(" ", 2)
    if len(head) < 2 or head[0] != "as" or not head[1].isdigit():
        return None
    entries = _quoted_strings(head[2] if len(head) == 3 else "")
    if entries is None or len(entries) != int(head[1]):
        return None
    return frozenset(entry.split("=", 1)[0] for entry in entries if "=" in entry)


def _quoted_strings(text: str) -> Optional[List[str]]:
    """busctl's space-separated, C-escaped, double-quoted strings."""
    out: List[str] = []
    at = 0
    while True:
        while at < len(text) and text[at].isspace():
            at += 1
        if at >= len(text):
            return out
        if text[at] != '"':
            return None
        at += 1
        value: List[str] = []
        while True:
            if at >= len(text):
                return None
            ch = text[at]
            if ch == '"':
                at += 1
                break
            if ch == "\\":
                if at + 1 >= len(text):
                    return None
                code = text[at + 1]
                if code in _ESCAPES:
                    value.append(_ESCAPES[code])
                    at += 2
                elif code in "0123" and at + 3 < len(text) and all(c in "01234567" for c in text[at + 2 : at + 4]):
                    value.append(chr(int(text[at + 1 : at + 4], 8)))
                    at += 4
                else:
                    return None
                continue
            if ch < " ":
                return None
            value.append(ch)
            at += 1
        if at < len(text) and not text[at].isspace():
            return None
        out.append("".join(value))
