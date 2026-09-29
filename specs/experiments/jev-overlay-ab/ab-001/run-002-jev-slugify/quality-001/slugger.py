"""Small fixture module for the gascity pack build-basic inference gate."""


import re


def slugify(value: str) -> str:
    """Return a URL slug for value."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug
