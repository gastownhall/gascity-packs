"""Small fixture module for the gascity pack build-basic inference gate."""

import re


def slugify(value: str) -> str:
    """Return a URL slug for value."""
    groups = re.findall(r"[a-zA-Z0-9]+", value)
    return "-".join(group.lower() for group in groups)
