"""Load and query the GasCity Cockpit ``/v0`` API contract.

``contract/v0.toml`` is the single, machine-readable declaration of what the
Cockpit extension depends on from the supervisor's ``/v0`` API:

- the pinned API version (``[api] required_version``) — the ``/v0`` surface is a
  moving dev build, so the extension pins a version and ``cockpit ready`` asserts
  the live ``info.version`` matches;
- the required-endpoint gate (``[endpoints] required``) — paths whose presence in
  ``/openapi.json`` ``cockpit ready`` checks before declaring a city Cockpit-ready;
- the extmsg adapter spec (``[extmsg]``) — the provider id + capabilities the
  Cockpit registers as (see :func:`adapter_registration_spec`).

Pure stdlib: TOML via ``tomllib`` (Python >= 3.11) with a ``tomli`` fallback.
"""

from __future__ import annotations

import os
from typing import Any, Optional

try:  # Python >= 3.11
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised only on < 3.11
    import tomli as tomllib  # type: ignore

CONTRACT_SCHEMA = "cockpit.v0"

# Fallbacks used only if the contract file omits a field; the shipped
# contract/v0.toml is authoritative.
DEFAULT_REQUIRED_API_VERSION = "0.1.0"
ADAPTER_PROVIDER = "cockpit"


class ContractError(Exception):
    """Raised when the contract file is missing, unparseable, or malformed."""


def default_contract_path() -> str:
    """Path to the pack's shipped ``contract/v0.toml``."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "contract", "v0.toml")


def load_contract(path: Optional[str] = None) -> dict[str, Any]:
    """Load and validate the contract TOML into a dict."""
    p = path or default_contract_path()
    try:
        with open(p, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as e:
        raise ContractError(f"contract not found: {p}") from e
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ContractError(f"cannot read contract {p}: {e}") from e

    schema = data.get("schema")
    if schema != CONTRACT_SCHEMA:
        raise ContractError(
            f"contract schema mismatch: expected {CONTRACT_SCHEMA!r}, got {schema!r}"
        )
    if "required_version" not in data.get("api", {}):
        raise ContractError("contract missing [api] required_version")
    return data


def required_api_version(contract: dict[str, Any]) -> str:
    return str(
        contract.get("api", {}).get("required_version", DEFAULT_REQUIRED_API_VERSION)
    )


def required_paths(contract: dict[str, Any]) -> list[str]:
    """The endpoint path templates the readiness gate asserts must exist."""
    return [str(x) for x in contract.get("endpoints", {}).get("required", [])]


def register_path(contract: dict[str, Any]) -> str:
    """The extmsg adapter-registration endpoint template (POST target)."""
    return str(
        contract.get("extmsg", {}).get(
            "register_path", "/v0/city/{cityName}/extmsg/adapters"
        )
    )


def adapter_registration_spec(
    contract: dict[str, Any],
    *,
    account_id: str = "default",
    name: str = "VS Code Cockpit",
    callback_url: Optional[str] = None,
) -> dict[str, Any]:
    """Build the POST body for ``/v0/city/{cityName}/extmsg/adapters``.

    This is the *spec* the host (cockpit-1ll.12) submits at RUNTIME — extmsg
    registration is an in-memory, ephemeral API call requiring a reachable
    ``callback_url``, not something a static pack install can durably do. See
    ``docs/DESIGN.md`` fork #2. Field casing mirrors the live
    ``ExtMsgAdapterRegisterInputBody`` / ``AdapterCapabilities`` schema.
    """
    ext = contract.get("extmsg", {})
    body: dict[str, Any] = {
        "provider": str(ext.get("adapter_provider", ADAPTER_PROVIDER)),
        "account_id": account_id,
        "name": name,
        "capabilities": {
            "SupportsChildConversations": bool(
                ext.get("supports_child_conversations", True)
            ),
            "SupportsAttachments": bool(ext.get("supports_attachments", False)),
            "MaxMessageLength": int(ext.get("max_message_length", 0)),
        },
    }
    if callback_url:
        body["callback_url"] = callback_url
    return body
