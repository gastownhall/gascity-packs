"""Probe the live ``/v0`` API, assess Cockpit-readiness, and publish the
discovery descriptor the VS Code extension auto-discovers.

The discovery handshake (PRD decision #4): a small JSON descriptor — API base
URL + version + auth model — published at a well-known runtime path under
``GC_HOME`` so the extension finds the supervisor API without lsof/guessing.

NOTE (``docs/DESIGN.md`` fork #3): the *clean* implementation writes this
descriptor from the supervisor itself at listener-bind time. Until that lands
upstream, this module lets the pack/operator publish it via
``cockpit discover --write``.

Pure stdlib: ``urllib.request`` for the probe, ``json`` for the descriptor.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

DEFAULT_BASE_URL = "http://127.0.0.1:8372"
DESCRIPTOR_RELPATH = os.path.join("runtime", "cockpit", "api-descriptor.json")
DESCRIPTOR_KIND = "gascity-cockpit-api-descriptor"
DESCRIPTOR_SCHEMA_VERSION = 1

# Errors that mean "the API did not answer cleanly" — never raised to the caller;
# folded into the probe's ``errors`` list instead.
_PROBE_ERRORS = (urllib.error.URLError, OSError, ValueError, TimeoutError)


def gc_home() -> str:
    """The gascity runtime root: ``$GC_HOME``, else ``~/.gc``."""
    return os.environ.get("GC_HOME") or os.path.expanduser(os.path.join("~", ".gc"))


def descriptor_path(home: Optional[str] = None) -> str:
    """Well-known path the discovery descriptor is published to."""
    return os.path.join(home or gc_home(), DESCRIPTOR_RELPATH)


def _http_get_json(url: str, timeout: float) -> Any:
    """GET a URL and parse JSON. Indirection point monkeypatched in tests."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (localhost)
        return json.loads(resp.read().decode("utf-8"))


def probe_api(base_url: str = DEFAULT_BASE_URL, timeout: float = 4.0) -> dict[str, Any]:
    """Probe the supervisor ``/v0`` API for version, paths, and health.

    Reachability is defined by a successful ``/openapi.json`` fetch (the codegen
    source of truth). ``/health`` is best-effort and never gates reachability.
    """
    base = base_url.rstrip("/")
    result: dict[str, Any] = {
        "base_url": base,
        "reachable": False,
        "api_version": None,
        "api_title": None,
        "paths": [],
        "health_status": None,
        "build_id": None,
        "errors": [],
    }
    try:
        spec = _http_get_json(base + "/openapi.json", timeout)
    except _PROBE_ERRORS as e:
        result["errors"].append(f"openapi: {e}")
        return result

    result["reachable"] = True
    info = spec.get("info", {}) if isinstance(spec, dict) else {}
    result["api_version"] = info.get("version")
    result["api_title"] = info.get("title")
    paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
    result["paths"] = sorted(paths.keys())

    try:
        health = _http_get_json(base + "/health", timeout)
        if isinstance(health, dict):
            result["health_status"] = health.get("status")
            result["build_id"] = health.get("build_id")
    except _PROBE_ERRORS as e:
        result["errors"].append(f"health: {e}")
    return result


def fetch_city_readiness(base_url: str, city: str, timeout: float = 4.0) -> dict[str, Any]:
    """Best-effort per-city readiness; returns ``{"error": ...}`` on failure."""
    url = base_url.rstrip("/") + f"/v0/city/{city}/readiness"
    try:
        data = _http_get_json(url, timeout)
        return data if isinstance(data, dict) else {"value": data}
    except _PROBE_ERRORS as e:
        return {"error": str(e)}


def assess_readiness(
    probe: dict[str, Any], required_version: str, required_paths: list[str]
) -> dict[str, Any]:
    """Compare a probe result to the contract: version + required endpoints."""
    reachable = bool(probe.get("reachable"))
    version_ok = reachable and probe.get("api_version") == required_version
    have = set(probe.get("paths") or [])
    missing = (
        [p for p in required_paths if p not in have] if reachable else list(required_paths)
    )
    ready = reachable and version_ok and not missing
    return {
        "ready": ready,
        "reachable": reachable,
        "version_ok": version_ok,
        "found_version": probe.get("api_version"),
        "required_version": required_version,
        "missing_paths": missing,
    }


def build_descriptor(
    probe: dict[str, Any],
    *,
    cities: Optional[list[str]] = None,
    home: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build the discovery descriptor from a probe result."""
    home = home or gc_home()
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    token_file = os.path.join(home, "controller.token")
    return {
        "schema_version": DESCRIPTOR_SCHEMA_VERSION,
        "kind": DESCRIPTOR_KIND,
        "base_url": probe.get("base_url"),
        "api_version": probe.get("api_version"),
        "api_title": probe.get("api_title"),
        # v1 is localhost-trust (PRD decision #5): the /v0 API does not enforce a
        # bearer token today. controller.token is referenced as the local
        # capability token so a future remote/auth story is additive, not a
        # rewrite. See docs/DESIGN.md.
        "auth": {
            "type": "localhost-trust",
            "token_file": token_file if os.path.exists(token_file) else None,
        },
        "cities": cities or [],
        "discovered_at": ts,
        "source": "cockpit discover (pack-side probe)",
    }


def write_descriptor(descriptor: dict[str, Any], path: Optional[str] = None) -> str:
    """Atomically write the descriptor, creating parent dirs. Returns the path."""
    p = path or descriptor_path()
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(json.dumps(descriptor, indent=2) + "\n")
    os.replace(tmp, p)
    return p


def read_descriptor(path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Read a previously published descriptor, or ``None`` if absent/unreadable."""
    p = path or descriptor_path()
    try:
        with open(p) as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return None
