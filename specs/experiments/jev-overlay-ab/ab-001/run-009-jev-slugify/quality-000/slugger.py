"""Small fixture module for the gascity pack build-basic inference gate."""


import re


def slugify(value: str) -> str:
    """Return a URL slug for value."""
    runs = re.findall(r"[A-Za-z0-9]+", value)
    return "-".join(runs).lower()
