from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

EVENT_REQUIRED_SCOPE = {
    "app_mention": "app_mentions:read",
    "message.channels": "channels:history",
    "message.groups": "groups:history",
    "message.im": "im:history",
    "message.mpim": "mpim:history",
}

EXPECTED_MANIFESTS = {
    "slack-channel/manifest/app.json",
    "slack-channel/manifest/app-socket.json",
    "slack-full/manifest/agent-app.json",
    "slack-full/manifest/app.json",
    "slack-mini/manifest/app.json",
    "slack-mini/manifest/app-socket.json",
}


def _slack_manifests() -> list[pathlib.Path]:
    found = []
    for path in sorted(REPO_ROOT.rglob("*.json")):
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        if isinstance(doc, dict) and "oauth_config" in doc:
            found.append(path)
    return found


MANIFESTS = _slack_manifests()


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _bot_events(manifest: dict) -> list[str]:
    return (
        manifest.get("settings", {})
        .get("event_subscriptions", {})
        .get("bot_events", [])
    )


def test_discovery_found_the_known_manifests() -> None:
    names = {_rel(p) for p in MANIFESTS}
    missing = EXPECTED_MANIFESTS - names
    assert not missing, f"manifest discovery missed: {sorted(missing)}"


@pytest.fixture(scope="module", params=MANIFESTS, ids=_rel)
def manifest_path(request: pytest.FixtureRequest) -> pathlib.Path:
    return request.param


@pytest.fixture(scope="module")
def manifest(manifest_path: pathlib.Path) -> dict:
    with manifest_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_slash_commands_absent_or_non_empty(
    manifest: dict, manifest_path: pathlib.Path
) -> None:
    features = manifest.get("features", {})
    if "slash_commands" not in features:
        return
    cmds = features["slash_commands"]
    assert isinstance(cmds, list), (
        f"{_rel(manifest_path)}: features.slash_commands must be a list"
    )
    assert cmds, (
        f"{_rel(manifest_path)}: features.slash_commands is an empty array; "
        "Slack rejects it at import. Omit the key until a command exists "
        "(gastownhall/gascity-packs#63)."
    )


def test_every_subscribed_event_has_a_known_scope_rule(
    manifest: dict, manifest_path: pathlib.Path
) -> None:
    unmapped = sorted(set(_bot_events(manifest)) - set(EVENT_REQUIRED_SCOPE))
    assert not unmapped, (
        f"{_rel(manifest_path)}: no scope rule known for {unmapped}; add the "
        "event to EVENT_REQUIRED_SCOPE"
    )


def test_subscribed_events_have_their_required_scopes(
    manifest: dict, manifest_path: pathlib.Path
) -> None:
    scopes = set(manifest.get("oauth_config", {}).get("scopes", {}).get("bot", []))
    missing = {
        EVENT_REQUIRED_SCOPE[event]: event
        for event in _bot_events(manifest)
        if event in EVENT_REQUIRED_SCOPE
        and EVENT_REQUIRED_SCOPE[event] not in scopes
    }
    assert not missing, (
        f"{_rel(manifest_path)}: bot_events subscribed without their required "
        "bot scope, which Slack refuses at install. Missing "
        + ", ".join(f"{scope} (for {event})" for scope, event in sorted(missing.items()))
    )
