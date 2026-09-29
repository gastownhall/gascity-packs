"""Duration parsing for the fixture repository."""

import re

_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
_GROUP_RE = re.compile(r"(\d+)([hms])")


def parse_duration(text: str) -> int:
    """Return the number of seconds described by text, for example "1h30m"."""
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"empty duration string: {text!r}")

    pos = 0
    total = 0
    last_unit_index = -1
    for match in _GROUP_RE.finditer(stripped):
        if match.start() != pos:
            raise ValueError(f"invalid duration string: {text!r}")
        number, unit = match.group(1), match.group(2)
        unit_index = "hms".index(unit)
        if unit_index <= last_unit_index:
            raise ValueError(f"units out of order or repeated: {text!r}")
        last_unit_index = unit_index
        total += int(number) * _UNIT_SECONDS[unit]
        pos = match.end()

    if pos != len(stripped):
        raise ValueError(f"invalid duration string: {text!r}")

    return total
