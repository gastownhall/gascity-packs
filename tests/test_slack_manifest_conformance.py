"""Slack-manifest conformance, applied to every Slack manifest in the repo.

Reported by a user in gastownhall/gascity-packs#63: importing
``slack-full/manifest/app.json`` into a real workspace failed Slack's
manifest validator on two counts, and the pack's own test suite was
green the whole time. The pack-local tests asserted the manifest's
*shape*; Slack rejects on *rules the shape satisfies*. This file
encodes the rules, and it runs against every manifest in the repo
rather than the one pack that happened to get reported, because the
same two mistakes were sitting in a second manifest nobody had tried
to import yet (``slack-full/manifest/agent-app.json``).

Discovery is by content, not by a hand-maintained path list: any
``*.json`` under the repo carrying an ``oauth_config`` key is a Slack
manifest and is checked. A new pack that ships one is covered on the
day it lands, with no edit here.

Rules, each with the Slack behaviour it stands in for:

  * ``features.slash_commands`` must be absent or non-empty. Slack's
    validator rejects ``[]`` outright ("must NOT have fewer than 1
    items"), so the empty-list-as-placeholder idiom fails at import.
  * every subscribed ``bot_events`` entry carries its required
    ``oauth_config.scopes.bot`` scope. Slack refuses to install an app
    whose event subscriptions exceed its granted scopes.
  * every subscribed event is one this file knows the scope rule for.
    Without this the previous rule would silently pass on any event
    added later, which is the shape of a guard that can never go red.

Schema reference: https://api.slack.com/reference/manifests
"""

from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Slack's event -> required-bot-scope table, for the events our packs
# subscribe to. Adding an event subscription to any manifest without
# adding its row here fails test_every_subscribed_event_has_a_known_scope_rule,
# which is deliberate: an unmapped event would otherwise make the
# scope check vacuously true for that event.
EVENT_REQUIRED_SCOPE = {
    "app_mention": "app_mentions:read",
    "message.channels": "channels:history",
    "message.groups": "groups:history",
    "message.im": "im:history",
    "message.mpim": "mpim:history",
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


def test_discovery_found_the_known_manifests() -> None:
    # Control on the discovery step itself: if the walk silently
    # stopped matching, every rule below would pass on an empty set.
    names = {_rel(p) for p in MANIFESTS}
    expected = {
        "slack-channel/manifest/app.json",
        "slack-full/manifest/agent-app.json",
        "slack-full/manifest/app.json",
        "slack-mini/manifest/app.json",
    }
    missing = expected - names
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
        "Slack's manifest validator rejects it. Omit the key until there is "
        "a command to declare (gastownhall/gascity-packs#63)."
    )


def test_every_subscribed_event_has_a_known_scope_rule(
    manifest: dict, manifest_path: pathlib.Path
) -> None:
    events = (
        manifest.get("settings", {})
        .get("event_subscriptions", {})
        .get("bot_events", [])
    )
    unmapped = sorted(set(events) - set(EVENT_REQUIRED_SCOPE))
    assert not unmapped, (
        f"{_rel(manifest_path)}: no scope rule known for {unmapped}. Add the "
        "event -> required-scope row to EVENT_REQUIRED_SCOPE in this file, or "
        "the scope check below passes vacuously for it."
    )


def test_subscribed_events_have_their_required_scopes(
    manifest: dict, manifest_path: pathlib.Path
) -> None:
    events = (
        manifest.get("settings", {})
        .get("event_subscriptions", {})
        .get("bot_events", [])
    )
    scopes = set(manifest.get("oauth_config", {}).get("scopes", {}).get("bot", []))
    missing = {
        EVENT_REQUIRED_SCOPE[event]: event
        for event in events
        if event in EVENT_REQUIRED_SCOPE
        and EVENT_REQUIRED_SCOPE[event] not in scopes
    }
    assert not missing, (
        f"{_rel(manifest_path)}: bot_events subscribed without their required "
        "bot scope — Slack refuses the install. Missing "
        + ", ".join(f"{scope} (for {event})" for scope, event in sorted(missing.items()))
    )
