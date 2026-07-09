#!/bin/sh
set -eu

# Verify the discord-gateway can scope its GC-API calls. The gateway addresses
# the supervisor API as /v0/city/<workspace-name>/sessions, where <workspace-name>
# is resolved from city.toml [workspace] name, then .gc/site.toml workspace_name,
# then the city directory basename. If the resolved name does not match a RUNNING
# city in the supervisor's /v0/cities, scope discovery returns empty, the gateway
# health-probes the UNSCOPED /v0/sessions (404), and pins itself at 503 — inbound
# DMs/mentions then silently stop delivering. This check flags that misconfig.

scripts_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../scripts" && pwd)

python3 - "$scripts_dir" <<'PY'
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, sys.argv[1])
import discord_intake_common as common

# A missing/unreadable city.toml is itself a valid v2 case (workspace identity
# may live only in .gc/site.toml), so degrade to an empty config and let the
# resolver fall back to site.toml / the city-dir basename.
try:
    cfg = common.load_city_toml()
except Exception:  # noqa: BLE001 - diagnostic must not crash on config load
    cfg = {}
name = common.resolved_workspace_name(cfg)
if not name:
    print("discord scope: could not resolve a workspace name")
    print("Set [workspace] name in city.toml, workspace_name in .gc/site.toml, or run from the city directory.")
    sys.exit(2)

base = common.DEFAULT_SUPERVISOR_API_BASE
try:
    req = urllib.request.Request(
        base + "/v0/cities",
        headers={"Accept": "application/json", "User-Agent": "gas-city-discord/0.1", "X-GC-Request": "true"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        items = json.loads(resp.read().decode("utf-8")).get("items", [])
except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
    print(f"discord scope: supervisor API at {base} unreachable; cannot verify scope ({exc})")
    print("Start the supervisor, then re-run this check.")
    sys.exit(2)

running = sorted(
    n
    for n in (str(i.get("name", "")).strip() for i in items if isinstance(i, dict) and i.get("running") is not False)
    if n
)
if name in running:
    print(f"discord scope OK: workspace {name!r} matches a running city")
    sys.exit(0)

print(f"discord scope: workspace name {name!r} does not match any running city (running: {', '.join(running) or 'none'})")
print("The discord-gateway will health-probe the unscoped /v0/sessions (404) and stay 503; inbound DMs/mentions will not deliver.")
print("Fix: set [workspace] name (city.toml) or workspace_name (.gc/site.toml) to a running city, then `gc service restart discord-gateway`.")
sys.exit(2)
PY
