"""stderr redaction.

gc embeds a failed op's stderr verbatim in its errors and logs, so every line
the pack writes there goes through a :class:`Redactor`, which replaces with
:data:`REDACTED`:

* every value of a sensitive key (the markers of gc's
  ``execenv.IsSensitiveKey``) of at least four characters, from the op's own
  environment and from the session's;
* every session (start-config ``env``) value of eight characters or more,
  whatever its key: a session environment carries provider credentials under
  names no marker list predicts;
* ``GC_INSTANCE_TOKEN`` whatever its length (observe.v1 rule 10);
* the value of any ``KEY=value``, ``KEY: value`` or ``--flag value`` whose name
  looks secret (gc's ``execenv.RedactText`` pattern), which covers text the
  pack did not write itself, such as a backend's error message.
"""

from __future__ import annotations

import re
from typing import Final, Mapping, Set

REDACTED: Final = "[REDACTED]"

SENSITIVE_VALUE_MIN_LEN: Final = 4
"""gc's floor: shorter values of sensitive keys are left alone."""

START_ENV_VALUE_MIN_LEN: Final = 8
"""Session environment values this long are redacted whatever their key."""

INSTANCE_TOKEN_KEY: Final = "GC_INSTANCE_TOKEN"

_SENSITIVE_MARKERS: Final = (
    "PASSWORD",
    "TOKEN",
    "SECRET",
    "PRIVATE_KEY",
    "PRIVATE-KEY",
    "API_KEY",
    "API-KEY",
    "ACCESS_KEY",
    "ACCESS-KEY",
    "CREDENTIAL",
    "OAUTH",
    "AUTH_JSON",
    "AUTH-JSON",
)

_SECRET_ASSIGNMENT: Final = re.compile(
    r"(?i)((?:[A-Z0-9_.-]*(?:TOKEN|SECRET|PASSWORD|PRIVATE[_-]?KEY|API[_-]?KEY|ACCESS[_-]?KEY"
    r"|CREDENTIALS?|OAUTH|AUTH[_-]?JSON)[A-Z0-9_.-]*"
    r"|--?[A-Z0-9_.-]*(?:token|secret|password|private-key|api-key|access-key|credential|oauth)[A-Z0-9_.-]*)"
    r"\s*(?:=|:|\s)\s*)([^ \t\r\n,;]+)"
)


def is_sensitive_key(key: str) -> bool:
    """Whether an environment key likely holds a secret (gc's rule)."""
    upper = key.strip().upper()
    return bool(upper) and any(marker in upper for marker in _SENSITIVE_MARKERS)


class Redactor:
    """Collects secret values and scrubs them, and secret-looking assignments, from text."""

    def __init__(self) -> None:
        self._secrets: Set[str] = set()

    def add_secret(self, value: str) -> None:
        """Redact ``value`` (surrounding whitespace ignored) wherever it appears."""
        value = value.strip()
        if value:
            self._secrets.add(value)

    def add_process_env(self, env: Mapping[str, str]) -> None:
        """Redact the sensitive values of the op's own environment."""
        for key, value in env.items():
            if is_sensitive_key(key) and len(value.strip()) >= SENSITIVE_VALUE_MIN_LEN:
                self.add_secret(value)

    def add_start_env(self, env: Mapping[str, str]) -> None:
        """Redact a session environment (a start config's ``env``)."""
        for key, value in env.items():
            length = len(value.strip())
            if (
                key == INSTANCE_TOKEN_KEY
                or length >= START_ENV_VALUE_MIN_LEN
                or (is_sensitive_key(key) and length >= SENSITIVE_VALUE_MIN_LEN)
            ):
                self.add_secret(value)

    def redact(self, text: str) -> str:
        """``text`` with every known secret and secret assignment replaced."""
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, REDACTED)
        return _SECRET_ASSIGNMENT.sub(r"\1" + REDACTED, text)
