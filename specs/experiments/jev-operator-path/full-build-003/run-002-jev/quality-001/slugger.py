"""Small fixture module for the gascity pack build-basic inference gate."""

import re


def slugify(value: str) -> str:
    """Return a URL slug for value."""
    parts = re.split(r"[^a-z0-9]+", value.lower())
    return "-".join(p for p in parts if p)
