"""Duration parsing for the fixture repository."""

import re

_PATTERN = re.compile(r"(\d+)([hms])")
_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int:
    """Return the number of seconds described by text, for example "1h30m"."""
    stripped = text.strip(" \t\n\r\v\f")
    if not stripped:
        raise ValueError(f"empty duration: {text!r}")

    order = "hms"
    last_rank = -1
    total_seconds = 0
    pos = 0
    matched_any = False
    for match in _PATTERN.finditer(stripped):
        if match.start() != pos:
            raise ValueError(f"malformed duration: {text!r}")
        unit = match.group(2)
        rank = order.index(unit)
        if rank <= last_rank:
            raise ValueError(f"repeated or out-of-order unit in duration: {text!r}")
        last_rank = rank
        total_seconds += int(match.group(1)) * _UNIT_SECONDS[unit]
        pos = match.end()
        matched_any = True

    if pos != len(stripped) or not matched_any:
        raise ValueError(f"malformed duration: {text!r}")

    return total_seconds
