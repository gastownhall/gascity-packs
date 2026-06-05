"""cockpit — the GasCity Cockpit city-side enabler engine.

A pure-stdlib toolkit that makes a gas city *Cockpit-ready* and defines the
discovery handshake the VS Code extension needs. It does NOT run a backend; it is
a thin client of the supervisor's existing ``/v0`` HTTP API.

Public surface (what the CLI and the extension build on):

- :mod:`cockpit.contract`  — load the ``/v0`` API contract (``contract/v0.toml``):
  the pinned API version, the required-endpoint gate, and the extmsg adapter
  registration spec.
- :mod:`cockpit.discovery` — probe the live ``/v0`` API (:func:`~cockpit.discovery.probe_api`),
  assess readiness against the contract, and read/write the discovery descriptor
  the extension auto-discovers.
- :mod:`cockpit.cli`       — the ``ready`` / ``discover`` / ``contract`` /
  ``adapter`` command implementations.
"""

from __future__ import annotations

SCHEMA = "cockpit.v0"
__version__ = "0.1.0"

__all__ = ["SCHEMA", "__version__"]
