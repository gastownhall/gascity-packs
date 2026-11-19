"""hc's ``config.toml`` as hc v0.1.19 reads it (``crates/herdr-core/src/config.rs``).

hc deserializes the file with serde into ``Config``: every field is an
``Option``, and the struct has no ``deny_unknown_fields``, so a key hc does
not know is ignored while a known key of the wrong type fails the whole file.
serde's ``f64`` takes a TOML integer as well as a float; nothing else converts
(a boolean is never a number, a number never a string). A missing file is the
defaults. ``terminal.run`` loads the file on every call and fails with an
error of kind ``config``, message ``<path>: <error>``.

The file is ``$XDG_CONFIG_HOME/herdr-core/config.toml``. Unlike hc, fake-hc
never falls back to ``~/.config``: a core whose environment names no
``XDG_CONFIG_HOME`` reads no config, so a test never reads its user's.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Mapping, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - the 3.9 floor; tomli is tomllib's upstream
    import tomli as tomllib

CONFIG_LEAF = os.path.join("herdr-core", "config.toml")

HC_CONFIG_KEYS: Dict[str, str] = {
    "shell": "list of strings",
    "detach_key": "string",
    "wait_timeout": "f64",
    "notes": "bool",
    "notes_quiet": "f64",
    "headless": "string",
    "history_mb": "f64",
    "socket": "string",
    "machine_timeout": "f64",
}
"""hc v0.1.19 ``Config``: each key and the type serde reads it as."""

_EXPECTED = {"f64": "f64", "bool": "a boolean", "string": "a string", "list of strings": "a sequence"}
"""What serde says it expected, per type."""


class HcConfigError(Exception):
    """The file is not TOML, or a known key has the wrong type."""


def config_path(env: Mapping[str, str]) -> Optional[str]:
    """Where a core with ``env`` reads its config; None when it names no ``XDG_CONFIG_HOME``."""
    home = env.get("XDG_CONFIG_HOME", "")
    return os.path.join(home, CONFIG_LEAF) if home else None


def _unexpected(value: object) -> str:
    """serde's ``Unexpected`` wording for a TOML value."""
    if isinstance(value, bool):
        return f"boolean `{str(value).lower()}`"
    if isinstance(value, int):
        return f"integer `{value}`"
    if isinstance(value, float):
        return f"floating point `{value}`"
    if isinstance(value, str):
        return f"string {value!r}"
    if isinstance(value, list):
        return "sequence"
    if isinstance(value, dict):
        return "map"
    return "datetime"


def _fits(kind: str, value: object) -> bool:
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "f64":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    return isinstance(value, list)


def parse_hc_config(text: str) -> Dict[str, object]:
    """The settings ``text`` holds, checked as hc's serde checks them."""
    try:
        doc: Dict[str, object] = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise HcConfigError(f"TOML parse error: {err}") from None
    for key, kind in HC_CONFIG_KEYS.items():
        if key not in doc:
            continue
        value = doc[key]
        if not _fits(kind, value):
            raise HcConfigError(f"{key}: invalid type: {_unexpected(value)}, expected {_EXPECTED[kind]}")
        if kind == "list of strings":
            assert isinstance(value, list)
            for item in value:
                if not isinstance(item, str):
                    raise HcConfigError(f"{key}: invalid type: {_unexpected(item)}, expected a string")
    return doc


def load_hc_config(path: str) -> Dict[str, object]:
    """hc ``config::load``: the settings at ``path``, none when it is missing;
    :class:`HcConfigError` carries hc's ``<path>: <error>`` message."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as err:
        raise HcConfigError(f"{path}: {err}") from None
    try:
        return parse_hc_config(text)
    except HcConfigError as err:
        raise HcConfigError(f"{path}: {err}") from None
