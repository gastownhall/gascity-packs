"""Structural validation for manifest/app.json (pack-relative).

This pack ships a canonical Slack app manifest at ``manifest/app.json``
(pack-relative — i.e. relative to this slack-full/ directory). The
manifest is the source of truth for the slack-full's OAuth scopes,
bot events, and slash commands.

These tests guard against accidental breakage of that file:

  * the JSON parses cleanly,
  * the top-level keys Slack's manifest schema requires are present,
  * the scopes and bot_events arrays are non-empty (catches a
    well-meaning edit that empties them out),
  * scopes are unique and sorted (style guard — keeps diffs readable).

Schema reference: https://api.slack.com/reference/manifests
"""

from __future__ import annotations

import json
import pathlib

import pytest

PACK_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_PATH = PACK_DIR / "manifest" / "app.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST_PATH.is_file(), f"manifest missing: {MANIFEST_PATH}"
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_parses_as_json(manifest: dict) -> None:
    assert isinstance(manifest, dict)


def test_manifest_has_display_information(manifest: dict) -> None:
    di = manifest.get("display_information")
    assert isinstance(di, dict), "display_information must be an object"
    assert di.get("name"), "display_information.name is required"
    assert di.get("description"), "display_information.description is required"


def test_manifest_has_bot_user(manifest: dict) -> None:
    bot = manifest.get("features", {}).get("bot_user")
    assert isinstance(bot, dict), "features.bot_user must be an object"
    assert bot.get("display_name"), "features.bot_user.display_name is required"


def test_manifest_declares_bot_scopes(manifest: dict) -> None:
    scopes = manifest.get("oauth_config", {}).get("scopes", {}).get("bot")
    assert isinstance(scopes, list) and scopes, (
        "oauth_config.scopes.bot must be a non-empty array"
    )
    # Every scope the live adapter actually relies on must be present.
    # If the adapter starts using something new, add it here AND to the
    # manifest in the same change.
    # Each subscribed message.* bot event Slack delivers requires the
    # matching *:history scope on the install. If we subscribe to
    # message.channels but only declare im:history, Slack rejects the
    # install or silently drops the channel subscription. Lock the
    # invariant scope-by-event into this assertion.
    required = {
        "channels:history",
        "chat:write",
        "chat:write.customize",
        "files:read",
        "files:write",
        "groups:history",
        "im:history",
        "mpim:history",
        "reactions:write",
    }
    missing = required - set(scopes)
    assert not missing, f"manifest missing required bot scopes: {sorted(missing)}"
    # im:read was historically declared but no adapter code path uses
    # it (DMs flow through im:history events). Guard against re-adding
    # an over-broad scope without a justifying call site.
    assert "im:read" not in scopes, (
        "im:read is over-broad — adapter has no im.list / conversations.open "
        "call site. Remove it or open a bead documenting the planned use."
    )


def test_manifest_scopes_unique_and_sorted(manifest: dict) -> None:
    scopes = manifest["oauth_config"]["scopes"]["bot"]
    assert len(scopes) == len(set(scopes)), "duplicate scopes detected"
    assert scopes == sorted(scopes), "scopes must be sorted alphabetically"


def test_manifest_subscribes_to_required_bot_events(manifest: dict) -> None:
    events = (
        manifest.get("settings", {})
        .get("event_subscriptions", {})
        .get("bot_events")
    )
    assert isinstance(events, list) and events, (
        "settings.event_subscriptions.bot_events must be a non-empty array"
    )
    # The adapter dispatches across all four message channel-type
    # buckets plus app_mention. Drop one and that channel type goes
    # silent; the assertion locks the full set in.
    required = {
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim",
    }
    missing = required - set(events)
    assert not missing, f"manifest missing required bot events: {sorted(missing)}"


def test_manifest_bot_events_unique_and_sorted(manifest: dict) -> None:
    events = manifest["settings"]["event_subscriptions"]["bot_events"]
    assert len(events) == len(set(events)), "duplicate bot events detected"
    assert events == sorted(events), "bot events must be sorted alphabetically"


def test_manifest_slash_commands_field_present(manifest: dict) -> None:
    # gc-cby.2 (sync-commands) needs this field to exist as a list so
    # it can append/diff. Empty is fine today; missing is not.
    cmds = manifest.get("features", {}).get("slash_commands")
    assert isinstance(cmds, list), "features.slash_commands must be a list"
