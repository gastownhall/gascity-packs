"""Duration parsing for the fixture repository."""

import re

_UNIT_ORDER = ("h", "m", "s")
_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
_TOKEN_RE = re.compile(r"(\d+)([a-zA-Z])")


def parse_duration(text: str) -> int:
    """Return the number of seconds described by text, for example "1h30m"."""
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"invalid duration: {text!r}")

    pos = 0
    total = 0
    matched_any = False
    min_unit_index = 0
    for match in _TOKEN_RE.finditer(stripped):
        if match.start() != pos:
            raise ValueError(f"invalid duration: {text!r}")
        value, unit = match.groups()
        if unit not in _UNIT_SECONDS:
            raise ValueError(f"invalid duration: {text!r}")
        unit_index = _UNIT_ORDER.index(unit)
        if unit_index < min_unit_index:
            raise ValueError(f"invalid duration: {text!r}")
        min_unit_index = unit_index + 1
        total += int(value) * _UNIT_SECONDS[unit]
        pos = match.end()
        matched_any = True

    if not matched_any or pos != len(stripped):
        raise ValueError(f"invalid duration: {text!r}")

    return total
