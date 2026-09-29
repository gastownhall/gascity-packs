"""Duration parsing for the fixture repository."""

import re

_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
_GROUP_RE = re.compile(r"(\d+)([hms])")
_FULL_RE = re.compile(r"(?:\d+[hms])+")


def parse_duration(text: str) -> int:
    """Return the number of seconds described by text, for example "1h30m"."""
    stripped = text.strip()
    if not stripped or not _FULL_RE.fullmatch(stripped):
        raise ValueError(f"invalid duration: {text!r}")

    total = 0
    seen_order = []
    for number, unit in _GROUP_RE.findall(stripped):
        if unit in seen_order:
            raise ValueError(f"duplicate unit {unit!r} in duration: {text!r}")
        if seen_order and _UNIT_SECONDS[unit] > _UNIT_SECONDS[seen_order[-1]]:
            raise ValueError(f"units out of order in duration: {text!r}")
        seen_order.append(unit)
        total += int(number) * _UNIT_SECONDS[unit]

    return total
